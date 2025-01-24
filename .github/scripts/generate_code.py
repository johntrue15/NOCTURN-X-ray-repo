import os
import json
import anthropic
import requests
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
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
        
        # Improved system prompt
        system_prompt = """You are a helpful AI assistant that generates code based on GitHub issues. 
        Your task is to:
        1. Analyze the issue description and comments
        2. Generate appropriate code implementation
        3. Include necessary imports and documentation
        4. Return complete, working code files
        
        Format your response as valid Python code without any markdown or explanations."""
        
        # Create message for Claude
        message = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=4096,
            temperature=0.7,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Generate code implementation for this issue:\n\n{issue_content}"
                }
            ]
        )
        
        # Extract the response and verify it's not empty
        code_response = message.content[0].text.strip()
        if not code_response:
            raise ValueError("Claude returned empty response")
            
        logger.info("Successfully generated code response")
        
        # Create the output directory
        output_dir = Path('.github/generated')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save the generated code
        output_file = output_dir / 'generated_code.py'
        with open(output_file, 'w') as f:
            f.write(code_response)
            
        logger.info(f"Saved generated code to {output_file}")
        
        # Create a metadata file with issue information
        metadata = {
            "issue_number": issue_number,
            "repo": repo,
            "generated_files": [str(output_file)]
        }
        
        with open(output_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error generating code: {str(e)}")
        raise

if __name__ == "__main__":
    main()
