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

def extract_code_blocks(response):
    """Extract code blocks from Claude's response"""
    # Updated patterns to handle file paths in code block headers
    patterns = [
        r'```(?:yaml|python)?:?(?:[^\n]*?)\n(.*?)```',  # Code block with optional language and file path
        r'```(.*?)```',                                  # Simple code block
        r'^(.*?)$'                                       # Entire response if no code blocks
    ]
    
    code_blocks = []
    for pattern in patterns:
        matches = re.finditer(pattern, response, re.DOTALL)
        for match in matches:
            code = match.group(1).strip()
            # Remove any language or file path markers
            code = re.sub(r'^```(?:yaml|python)?:?[^\n]*\n', '', code)
            code = re.sub(r'\n```$', '', code)
            if code:
                code_blocks.append(code)
                logger.info(f"Found code block using pattern: {pattern}")
                logger.info(f"Code preview: {code[:100]}...")
    
    if not code_blocks:
        logger.error("No code blocks found in response")
        logger.error(f"Response preview:\n{response[:500]}")
        raise ValueError("No valid code blocks found in Claude's response")
        
    return code_blocks

def save_claude_conversation(output_dir, conversation_data, is_error=False):
    """Save Claude conversation to a consistent location"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filename = 'claude_conversation_error.json' if is_error else 'claude_conversation.json'
    conv_file = output_dir / filename
    
    with open(conv_file, 'w') as f:
        json.dump(conversation_data, f, indent=2)
    logger.info(f"Saved Claude conversation to {conv_file}")
    return conv_file

def save_generated_files(code_blocks, needed_files):
    """Save code blocks to appropriate files"""
    os.makedirs('.github/generated', exist_ok=True)
    
    # Map file paths to code blocks
    file_map = {}
    for code in code_blocks:
        for file_path in needed_files:
            if file_path.endswith('.yml') and 'name: MorphoSource Analysis Workflow' in code:
                file_map[file_path] = code
            elif file_path.endswith('.py') and 'from selenium import webdriver' in code:
                file_map[file_path] = code
    
    # Save files
    for file_path, code in file_map.items():
        output_path = os.path.join('.github/generated', file_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(code)
        logger.info(f"Saved generated file: {output_path}")

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
        CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
        
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
        
        # Define system prompt
        system_prompt = """You are a helpful AI assistant that generates code based on GitHub issues. 
        Your task is to:
        1. Analyze the issue description and comments
        2. Generate or modify the requested files
        3. Include necessary imports and documentation
        4. Return complete, working code files
        
        IMPORTANT: For each file, you must format your response exactly like this:
        ```language:full/path/to/file
        [file contents here]
        ```
        
        For example:
        ```yaml:.github/workflows/example.yml
        name: Example Workflow
        on: push
        ```
        
        ```python:.github/scripts/example.py
        import os
        def main():
            pass
        ```
        
        Do not include any explanations or markdown formatting outside the code blocks."""
        
        # Store the full prompt
        prompt = f"Generate or modify the following files based on this issue:\n\n{context}\nIssue details:\n{issue_content}"
        
        logger.info("Sending request to Claude...")
        
        # Create message for Claude with updated model and token settings
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            temperature=0.7,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            extra_headers={
                "anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"
            }
        )
        
        # Extract the response
        code_response = message.content[0].text.strip()
        logger.info(f"Received response from Claude (length: {len(code_response)})")
        
        # Save conversation immediately after receiving response
        conversation = {
            "timestamp": datetime.datetime.now().isoformat(),
            "issue_number": issue_number,
            "system_prompt": system_prompt,
            "user_prompt": prompt,
            "claude_response": code_response
        }
        
        output_dir = Path('.github/generated')
        conv_file = save_claude_conversation(output_dir, conversation)
        
        # Parse code blocks using the new function
        code_blocks = extract_code_blocks(code_response)
        if not code_blocks:
            logger.error("Response preview:")
            logger.error(code_response[:1000])
            raise ValueError("No valid code blocks found in Claude's response")
        
        # Save the code blocks to files
        save_generated_files(code_blocks, required_files)
        
        # Update metadata
        metadata = {
            "issue_number": issue_number,
            "repo": repo,
            "generated_files": required_files,
            "generation_timestamp": datetime.datetime.now().isoformat(),
            "claude_conversation": str(conv_file)
        }
        
        metadata_file = output_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        logger.info("Successfully created metadata file")
        
    except Exception as e:
        logger.error(f"Error generating code: {str(e)}", exc_info=True)
        if 'prompt' in locals() and 'code_response' in locals():
            # Save error conversation
            error_conversation = {
                "timestamp": datetime.datetime.now().isoformat(),
                "issue_number": issue_number,
                "system_prompt": system_prompt,
                "user_prompt": prompt,
                "claude_response": code_response,
                "error": str(e)
            }
            try:
                save_claude_conversation(Path('.github/generated'), error_conversation, is_error=True)
            except:
                logger.error("Failed to save error conversation", exc_info=True)
        raise

if __name__ == "__main__":
    main()
