#!/usr/bin/env python3

import os
import json
import time
import re
import requests
from github import Github

# Initialize GitHub client
token = os.environ.get("GITHUB_TOKEN")
repo_name = os.environ.get("REPO")
g = Github(token)
repo = g.get_repo(repo_name)

def extract_morphosource_data(release_body):
    """Extract the original MorphoSource release tag from the analysis release body"""
    match = re.search(r'Analysis for MorphoSource release: (morphosource-updates-[^\s]+)', release_body)
    if match:
        return match.group(1)
    return None

def get_morphosource_release(ms_tag):
    """Get the original MorphoSource release data"""
    try:
        release = repo.get_release(ms_tag)
        return release.body
    except:
        print(f"Could not find MorphoSource release with tag: {ms_tag}")
        return None

def extract_ct_analysis(release_body, release_type):
    """Extract the CT analysis text from the release body"""
    # Remove the header section that references MorphoSource
    clean_body = re.sub(r'Analysis for MorphoSource release: [^\n]+\n+', '', release_body)
    
    if release_type == "3d":
        # Remove the orientation views section for 3D analysis
        clean_body = re.sub(r'### Orientation Views[\s\S]+', '', clean_body)
    
    return clean_body.strip()

def create_fine_tuning_entry(morphosource_data, ct_analysis, is_preferred=True):
    """Create a fine-tuning entry in the expected format"""
    # For input, use the MorphoSource release data
    # For output, use the CT analysis text
    
    entry = {
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": morphosource_data
                }
            ],
            "tools": [],
            "parallel_tool_calls": True
        }
    }
    
    # Create the preferred and non-preferred outputs
    # For now, we're using a simple placeholder for non-preferred
    ct_output = {
        "role": "assistant",
        "content": ct_analysis
    }
    
    # Create a simplified/generic version for the alternative output
    simplified_output = {
        "role": "assistant",
        "content": "This CT scan shows anatomical structures typical for this species."
    }
    
    if is_preferred:
        entry["preferred_output"] = [ct_output]
        entry["non_preferred_output"] = [simplified_output]
    else:
        entry["preferred_output"] = [simplified_output]
        entry["non_preferred_output"] = [ct_output]
    
    return entry

# Get releases
releases = list(repo.get_releases())
if not releases:
    print("No releases found.")
    exit(0)

# Find CT analysis releases
ct_analysis_releases = []
for release in releases:
    if release.tag_name.startswith("ct_image_analysis-") or release.tag_name.startswith("ct_slice_analysis-"):
        release_type = "3d" if release.tag_name.startswith("ct_image_analysis-") else "2d"
        ct_analysis_releases.append((release, release_type))

if not ct_analysis_releases:
    print("No CT analysis releases found.")
    exit(0)

print(f"Found {len(ct_analysis_releases)} CT analysis releases.")

# Process each release
for release, release_type in ct_analysis_releases:
    release_id = release.id
    release_title = release.title
    release_body = release.body
    
    print(f"Processing reactions for {release_type} release: {release_title} (ID: {release_id})")
    
    # Ensure the directory exists
    os.makedirs("data/reactions/jsonl", exist_ok=True)
    output_file = f"data/reactions/jsonl/release-{release_id}.jsonl"
    
    # Check if we've already processed this release recently
    if os.path.exists(output_file) and (time.time() - os.path.getmtime(output_file)) < 86400:  # 24 hours
        print(f"Recent reaction data for release {release_id} already exists. Checking for new reactions...")
    
    # Get the original MorphoSource data
    ms_tag = extract_morphosource_data(release_body)
    if not ms_tag:
        print(f"Could not extract MorphoSource tag from release: {release_title}")
        continue
    
    morphosource_data = get_morphosource_release(ms_tag)
    if not morphosource_data:
        print(f"Could not get MorphoSource data for tag: {ms_tag}")
        continue
    
    # Extract the CT analysis text
    ct_analysis = extract_ct_analysis(release_body, release_type)
    
    # Get reactions using GitHub REST API
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.squirrel-girl-preview+json"
    }
    
    api_url = f"https://api.github.com/repos/{repo_name}/releases/{release_id}/reactions"
    response = requests.get(api_url, headers=headers)
    reactions = response.json() if response.status_code == 200 else []
    
    # Process the reaction data
    reaction_data = {}
    for reaction in reactions:
        content = reaction["content"]  # 👍, 👎, 😄, etc.
        user = reaction["user"]["login"]
        
        # Classify based on reaction
        is_positive = content in ["👍", "🎉", "❤️", "🚀", "😄"]
        
        # Create fine-tuning entry
        entry = create_fine_tuning_entry(morphosource_data, ct_analysis, is_positive)
        
        # Add to our reaction data
        if user not in reaction_data:
            reaction_data[user] = entry
    
    # Write to JSONL file
    with open(output_file, 'w') as f:
        for user, entry in reaction_data.items():
            f.write(json.dumps(entry) + '\n')
    
    print(f"Saved {len(reaction_data)} reactions to {output_file}") 