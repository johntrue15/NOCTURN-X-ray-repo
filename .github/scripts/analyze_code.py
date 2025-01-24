import os
import re
import json
import argparse
from pathlib import Path
from github import Github
import logging
import shutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_claude_conversation(artifacts_dir):
    """Load the Claude conversation from artifacts"""
    # List all files in artifacts directory
    logger.info(f"Searching for Claude conversation in {artifacts_dir}")
    for path in Path(artifacts_dir).rglob('*'):
        logger.info(f"Found: {path}")
        
        # Try to load any JSON file that might be the conversation
        if path.suffix == '.json':
            try:
                with open(path) as f:
                    data = json.load(f)
                    # Verify it's a Claude conversation by checking for required fields
                    if all(key in data for key in ['claude_response', 'system_prompt', 'user_prompt']):
                        logger.info(f"Found valid Claude conversation at {path}")
                        return data
            except Exception as e:
                logger.warning(f"Failed to load {path}: {e}")
                continue
    
    raise ValueError(f"Could not find valid Claude conversation file in {artifacts_dir}")

def analyze_code_block(content):
    """Analyze a code block for merge markers and existing code references"""
    needs_merge = False
    merge_markers = []
    
    # Look for common markers of existing code
    patterns = [
        r'#\s*\.\.\.\s*\(existing\s+(?:steps|code)\s*\.\.\.\s*\)',
        r'#\s*\.{3}\s*existing\s+(?:steps|code)\s*\.{3}\s*',
        r'#\s*existing\s+(?:steps|code)\s*\.{3}\s*',
        r'\/\/\s*\.{3}\s*existing\s+(?:code|steps)\s*\.{3}\s*'
    ]
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                needs_merge = True
                merge_markers.append({
                    'line': i + 1,
                    'marker': line.strip()
                })
                
    return needs_merge, merge_markers

def get_original_file(repo, file_path, branch='main'):
    """Get the original file content from the repository"""
    try:
        content = repo.get_contents(file_path, ref=branch)
        return content.decoded_content.decode('utf-8')
    except Exception as e:
        logger.warning(f"Could not get original file {file_path}: {str(e)}")
        return None

def merge_code_blocks(original_content, generated_content, merge_markers):
    """Merge original and generated code based on merge markers"""
    if not original_content:
        return generated_content
        
    result = []
    gen_lines = generated_content.split('\n')
    orig_lines = original_content.split('\n')
    
    i = 0
    while i < len(gen_lines):
        line = gen_lines[i]
        
        # Check if this line is a merge marker
        is_marker = False
        for marker in merge_markers:
            if marker['line'] - 1 == i:
                is_marker = True
                # Find the corresponding section in original code
                section_start = None
                section_end = None
                
                # Simple heuristic: look for the next non-empty line after the marker
                j = i + 1
                while j < len(gen_lines) and not gen_lines[j].strip():
                    j += 1
                    
                if j < len(gen_lines):
                    next_content = gen_lines[j].strip()
                    # Find this content in original file
                    for k, orig_line in enumerate(orig_lines):
                        if orig_line.strip() == next_content:
                            section_start = k
                            break
                            
                if section_start is not None:
                    # Add original code section
                    result.extend(orig_lines[section_start:])
                    i = j  # Skip past the marker
                    break
                
        if not is_marker:
            result.append(line)
            i += 1
            
    return '\n'.join(result)

def parse_code_blocks(response):
    """Parse code blocks from Claude's response"""
    # First try exact pattern with language
    pattern = r'```(\w+):([^`\n]+)\n(.*?)\n```'
    matches = list(re.finditer(pattern, response, re.DOTALL))
    
    if not matches:
        # Try without language
        pattern = r'```([^`\n]+)\n(.*?)\n```'
        matches = list(re.finditer(pattern, response, re.DOTALL))
    
    if not matches:
        # Try most lenient pattern
        pattern = r'```.*?([^:\n]+)(?:\n|\s*)(.*?)```'
        matches = list(re.finditer(pattern, response, re.DOTALL))
    
    if not matches:
        logger.error("No code blocks found in response")
        logger.error("Response preview:")
        logger.error(response[:1000])
        return []
    
    parsed_blocks = []
    for match in matches:
        try:
            groups = match.groups()
            if len(groups) == 3:
                # First pattern with language
                _, file_path, content = groups
            elif len(groups) == 2:
                # Second or third pattern
                file_path, content = groups
            else:
                logger.warning(f"Unexpected match groups: {groups}")
                continue
            
            file_path = file_path.strip().strip(':')  # Remove any trailing colons
            content = content.strip()
            
            if not file_path:
                logger.warning("Code block found without file path")
                continue
            
            # Log the raw match for debugging
            logger.debug(f"Raw match: {match.group(0)[:100]}...")
            logger.info(f"Found code block for {file_path} ({len(content)} chars)")
            
            parsed_blocks.append((file_path, content))
            
        except Exception as e:
            logger.error(f"Error parsing code block: {e}")
            logger.error(f"Match groups: {match.groups()}")
            logger.error(f"Raw match: {match.group(0)[:100]}...")
            continue
    
    if parsed_blocks:
        logger.info(f"Successfully parsed {len(parsed_blocks)} code blocks")
    else:
        logger.error("No valid code blocks could be parsed")
        logger.error("Full response:")
        logger.error(response)
    
    return parsed_blocks

def combine_code_files(original_path, generated_path, output_path):
    """Combine original file with generated updates"""
    if not os.path.exists(original_path):
        # If original doesn't exist, just copy generated file
        shutil.copy2(generated_path, output_path)
        return
        
    with open(original_path, 'r') as f:
        original = f.read()
    with open(generated_path, 'r') as f:
        generated = f.read()
        
    # TODO: Implement smart merging logic here
    # For now, use generated version if it exists, otherwise keep original
    output = generated if os.path.exists(generated_path) else original
    
    # Write combined output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(output)

def process_code_blocks(repo_path, generated_dir):
    """Process code blocks and combine with original files"""
    complete_dir = os.path.join(generated_dir, 'complete')
    os.makedirs(complete_dir, exist_ok=True)
    
    # Track file mappings
    path_mapping = {}
    
    for root, _, files in os.walk(generated_dir):
        for file in files:
            if file.endswith(('.py', '.yml', '.yaml', '.json')):
                generated_path = os.path.join(root, file)
                
                # Skip files in complete dir
                if 'complete' in generated_path:
                    continue
                    
                # Get original path relative to repo
                rel_path = os.path.relpath(generated_path, generated_dir)
                original_path = os.path.join(repo_path, rel_path)
                
                # Output path in complete dir
                output_path = os.path.join(complete_dir, os.path.basename(file))
                
                # Combine files
                combine_code_files(original_path, generated_path, output_path)
                
                # Track mapping
                path_mapping[os.path.basename(file)] = rel_path
                
    # Save path mapping
    mapping_path = os.path.join(complete_dir, 'path_mapping.json')
    with open(mapping_path, 'w') as f:
        json.dump(path_mapping, f, indent=2)
        
    return list(path_mapping.values())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--issue', required=True)
    parser.add_argument('--branch', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--artifacts-dir', required=True)
    args = parser.parse_args()
    
    try:
        # Initialize GitHub client
        gh = Github(os.environ['GITHUB_TOKEN'])
        repo = gh.get_repo(args.repo)
        
        # Load Claude conversation
        conversation = load_claude_conversation(args.artifacts_dir)
        logger.info("Successfully loaded Claude conversation")
        
        # Parse code blocks from Claude's response
        code_blocks = parse_code_blocks(conversation['claude_response'])
        if not code_blocks:
            raise ValueError("No code blocks found in Claude's response")
            
        logger.info(f"Found {len(code_blocks)} code blocks to process")
        
        # Process code blocks
        processed_files = process_code_blocks(
            repo_path='.',
            generated_dir=os.path.join('.github', 'generated')
        )
        
        logger.info(f"Successfully processed {len(processed_files)} files")
        
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}", exc_info=True)
        # List directory contents for debugging
        logger.error("Directory contents:")
        for path in Path('.').rglob('*'):
            logger.error(f"  {path}")
        raise

if __name__ == '__main__':
    main()
