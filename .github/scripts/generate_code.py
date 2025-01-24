import os
import json
import anthropic
import requests
from pathlib import Path
import logging
import datetime
import re

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_code_needed(issue_content):
    """Extract file paths listed under 'Code Needed:' section"""
    code_needed_match = re.search(r'Code Needed:\s*(.*?)(?=\n\n|\Z)', issue_content, re.DOTALL)
    if not code_needed_match:
        return []
    
    # Extract file paths after "Code Needed:"
    file_paths = []
    lines = code_needed_match.group(1).strip().split('\n')
    for line in lines:
        # Clean up the line and check if it's a file path
        path = line.strip()
        if path and ('/' in path or '.' in path):
            file_paths.append(path)
    
    logger.info(f"Found code needed files: {file_paths}")
    return file_paths

def download_existing_code(file_paths, repo, token):
    """Download existing code from the repository"""
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    
    existing_code = {}
    for path in file_paths:
        try:
            # Get file content from GitHub
            url = f'https://api.github.com/repos/{repo}/contents/{path}'
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                content = response.text
                existing_code[path] = content
                logger.info(f"Successfully downloaded: {path}")
            else:
                logger.warning(f"File not found or error downloading {path}: {response.status_code}")
                existing_code[path] = None
                
        except Exception as e:
            logger.error(f"Error downloading {path}: {str(e)}")
            existing_code[path] = None
    
    return existing_code

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
        
        # Extract required file paths
        required_files = extract_code_needed(issue_content)
        if not required_files:
            logger.warning("No 'Code Needed:' section found in issue")
            
        # Download existing code if available
        existing_code = download_existing_code(required_files, repo, github_token)
        
        # Create prompt with existing code context
        context = "Here are the files that need to be created or modified:\n\n"
        for path, content in existing_code.items():
            if content:
                context += f"Existing file {path}:\n```\n{content}\n```\n\n"
            else:
                context += f"New file to create: {path}\n\n"
        
        # Improved system prompt
        system_prompt = """You are a helpful AI assistant that generates code based on GitHub issues. 
        Your task is to:
        1. Analyze the issue description and comments
        2. Generate or modify the requested files
        3. Include necessary imports and documentation
        4. Return complete, working code files
        
        For each file, format your response as:
        ```language:path/to/file
        // complete file contents here
        ```
        
        Do not include any explanations or markdown formatting outside the code blocks."""
        
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
                    "content": f"Generate or modify the following files based on this issue:\n\n{context}\nIssue details:\n{issue_content}"
                }
            ]
        )
        
        # Extract the response and verify it's not empty
        code_response = message.content[0].text.strip()
        logger.info(f"Received response from Claude (length: {len(code_response)})")
        
        if not code_response:
            raise ValueError("Claude returned empty response")
        
        # Parse code blocks from response
        code_blocks = re.finditer(r'```[\w-]*:?(.*?)\n(.*?)```', code_response, re.DOTALL)
        
        # Create the output directory
        output_dir = Path('.github/generated')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        generated_files = []
        for block in code_blocks:
            file_path = block.group(1).strip()
            code_content = block.group(2).strip()
            
            if not file_path:
                logger.warning("Code block found without file path, skipping")
                continue
                
            # Create subdirectories if needed
            full_path = output_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the generated code
            with open(full_path, 'w') as f:
                f.write(code_content)
                
            generated_files.append(str(full_path))
            logger.info(f"Saved generated code to {full_path}")
        
        if not generated_files:
            raise ValueError("No valid code blocks found in Claude's response")
        
        # Create metadata file
        metadata = {
            "issue_number": issue_number,
            "repo": repo,
            "generated_files": generated_files,
            "generation_timestamp": datetime.datetime.now().isoformat(),
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
