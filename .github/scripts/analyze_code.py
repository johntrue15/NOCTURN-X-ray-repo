import os
import re
import json
import argparse
from pathlib import Path
from github import Github
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_claude_conversation(artifacts_dir):
    """Load the Claude conversation from artifacts"""
    conv_file = Path(artifacts_dir) / 'claude_conversation.json'
    if not conv_file.exists():
        logger.warning("Claude conversation file not found")
        return None
        
    with open(conv_file) as f:
        return json.load(f)

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--issue', required=True)
    parser.add_argument('--branch', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--artifacts-dir', required=True)
    args = parser.parse_args()
    
    # Initialize GitHub client
    gh = Github(os.environ['GITHUB_TOKEN'])
    repo = gh.get_repo(args.repo)
    
    # Load Claude conversation
    conversation = load_claude_conversation(args.artifacts_dir)
    if not conversation:
        raise ValueError("Could not load Claude conversation")
        
    # Parse code blocks from Claude's response
    code_blocks = re.finditer(r'```(?:\w+:)?([^\n]+)\n(.*?)```', conversation['claude_response'], re.DOTALL)
    
    # Create output directory
    output_dir = Path('.github/generated/complete')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    review_comments = []
    processed_files = []
    
    for block in code_blocks:
        file_path = block.group(1).strip()
        generated_content = block.group(2).strip()
        
        # Analyze the generated code
        needs_merge, merge_markers = analyze_code_block(generated_content)
        
        if needs_merge:
            # Get original file content
            original_content = get_original_file(repo, file_path)
            if original_content:
                # Merge the code
                final_content = merge_code_blocks(original_content, generated_content, merge_markers)
                review_comments.append(f"- Merged changes in `{file_path}` with existing code")
            else:
                final_content = generated_content
                review_comments.append(f"- Could not find original file `{file_path}` to merge with")
        else:
            final_content = generated_content
            review_comments.append(f"- Generated new file `{file_path}`")
        
        # Save the final code
        output_file = output_dir / file_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            f.write(final_content)
            
        processed_files.append(file_path)
        
    # Create review comment
    review_comment = "## Code Analysis Results\n\n"
    review_comment += "Analyzed generated code and performed the following actions:\n\n"
    review_comment += '\n'.join(review_comments)
    
    with open('.github/generated/review_comment.md', 'w') as f:
        f.write(review_comment)
        
    logger.info(f"Processed {len(processed_files)} files")

if __name__ == '__main__':
    main()
