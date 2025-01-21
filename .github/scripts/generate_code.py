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
    
    # Initialize Claude client
    client = anthropic.Client(api_key)
    
    # Get issue details including comments
    issue_content = get_issue_details(issue_number, repo, github_token)
    
    # Prepare the prompt
    prompt = f"""Human: The user has opened an issue requesting code changes or new code. 
Here are the full issue details and any subsequent comments:

{issue_content}

Please provide ONLY the code implementation that addresses this request. 
Do not include explanations or disclaimers.
