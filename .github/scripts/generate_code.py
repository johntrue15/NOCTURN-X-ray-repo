import os
import json
import anthropic
import requests
from pathlib import Path

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
    # Get environment variables
    api_key = os.getenv('ANTHROPIC_API_KEY')
    github_token = os.getenv('GITHUB_TOKEN')
    issue_number = os.getenv('ISSUE_NUMBER')
    repo = os.getenv('REPO')
    
    # Initialize Claude client with the correct syntax
    client = anthropic.Anthropic(api_key=api_key)
    
    # Get issue details including comments
    issue_content = get_issue_details(issue_number, repo, github_token)
    
    # Create message for Claude
    message = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=4096,
        temperature=0.7,
        system="You are a helpful AI assistant that generates code based on GitHub issues. Provide only the code implementation without any explanations or markdown formatting.",
        messages=[
            {
                "role": "user",
                "content": f"Here are the full issue details and comments:\n\n{issue_content}\n\nPlease provide the code implementation that addresses this request."
            }
        ]
    )
    
    # Extract the response
    code_response = message.content[0].text
    
    # Create the .github/generated directory if it doesn't exist
    output_dir = Path('.github/generated')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the generated code
    output_file = output_dir / 'generated_code.py'
    with open(output_file, 'w') as f:
        f.write(code_response)

if __name__ == "__main__":
    main()
