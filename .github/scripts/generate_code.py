import os
import json
import anthropic
import requests
from pathlib import Path
import logging
import datetime

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_issue_details(issue_number, repo, token):
    """Fetch issue details including comments from GitHub API"""
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Get issue details
    issue_url = f'https://api.github.com/repos/{repo}/issues/{issue_number}'
    issue_response = requests.get(issue_url, headers=headers)
    issue_data = issue_response.json()
    
    # Get issue comments
    comments_url = f'{issue_url}/comments'
    comments_response = requests.get(comments_url, headers=headers)
    comments_data = comments_response.json()
    
    # Combine issue body and comments
    full_conversation = [
        f"Issue Title: {issue_data['title']}\n\n",
        f"Issue Description:\n{issue_data['body']}\n\n"
    ]
    
    for comment in comments_data:
        full_conversation.append(f"Comment by {comment['user']['login']}:\n{comment['body']}\n\n")
    
    return "".join(full_conversation)

def main():
    try:
        # Get environment variables
        api_key = os.getenv('ANTHROPIC_API_KEY')
        github_token = os.getenv('GITHUB_TOKEN')
        issue_number = os.getenv('ISSUE_NUMBER')
        repo = os.getenv('REPO')
        
        if not all([api_key, github_token, issue_number, repo]):
            raise ValueError("Missing required environment variables")
        
        logger.info(f"Processing issue #{issue_number} from {repo}")
        
        # Initialize Claude client
        client = anthropic.Anthropic(api_key=api_key)
        
        # Get issue details including comments
        issue_content = get_issue_details(issue_number, repo, github_token)
        logger.info("Successfully fetched issue details")
        
        # Improved system prompt
        system_prompt = """You are a helpful AI assistant that generates code based on GitHub issues. 
        Your task is to:
        1. Analyze the issue description and comments
        2. Generate appropriate code implementation
        3. Include necessary imports and documentation
        4. Return complete, working code files
        
        IMPORTANT: You must return valid Python code that can be executed. Do not include any markdown formatting or explanations - only the code itself."""
        
        logger.info("Sending request to Claude...")
        
        # Create message for Claude
        message = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=4096,
            temperature=0.7,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Generate code implementation for this issue. Return only the code, no explanations or markdown:\n\n{issue_content}"
                }
            ]
        )
        
        # Extract the response and verify it's not empty
        code_response = message.content[0].text.strip()
        logger.info(f"Received response from Claude (length: {len(code_response)})")
        
        if not code_response:
            raise ValueError("Claude returned empty response")
        
        # Log first few characters of response for debugging
        logger.info(f"First 100 chars of response: {code_response[:100]}")
            
        # Create the output directory
        output_dir = Path('.github/generated')
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")
        
        # Save the generated code
        output_file = output_dir / 'generated_code.py'
        with open(output_file, 'w') as f:
            f.write(code_response)
            
        logger.info(f"Saved generated code to {output_file}")
        
        # Verify file was written correctly
        if not output_file.exists():
            raise ValueError(f"Failed to create output file: {output_file}")
            
        file_size = output_file.stat().st_size
        logger.info(f"Generated file size: {file_size} bytes")
        
        # Create a metadata file with issue information
        metadata = {
            "issue_number": issue_number,
            "repo": repo,
            "generated_files": [str(output_file)],
            "generation_timestamp": datetime.datetime.now().isoformat(),
            "code_length": len(code_response)
        }
        
        metadata_file = output_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        logger.info("Successfully created metadata file")
        
    except Exception as e:
        logger.error(f"Error generating code: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
