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
        
        # Create output directory with simpler structure
        output_dir = Path('.github/generated/complete')
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")
        
        review_comments = []
        processed_files = []
        
        for file_path, generated_content in code_blocks:
            try:
                # Analyze the generated code
                needs_merge, merge_markers = analyze_code_block(generated_content)
                
                # Use just the filename for output
                simple_name = Path(file_path).name
                output_file = output_dir / simple_name
                logger.info(f"Saving to simplified path: {output_file}")
                
                if needs_merge:
                    # Get original file content
                    original_content = get_original_file(repo, file_path)
                    if original_content:
                        # Merge the code
                        final_content = merge_code_blocks(original_content, generated_content, merge_markers)
                        review_comments.append(f"- Merged changes in `{file_path}` with existing code")
                        logger.info(f"Merged changes for {file_path}")
                    else:
                        final_content = generated_content
                        review_comments.append(f"- Could not find original file `{file_path}` to merge with")
                        logger.warning(f"Could not find original file {file_path} for merging")
                else:
                    final_content = generated_content
                    review_comments.append(f"- Generated new file `{file_path}`")
                    logger.info(f"Generated new file {file_path}")
                
                # Save the final code
                with open(output_file, 'w') as f:
                    f.write(final_content)
                
                processed_files.append(str(output_file))
                logger.info(f"Saved file to: {output_file}")
                
                # Also save original path mapping
                with open(output_dir / 'path_mapping.json', 'w') as f:
                    json.dump({simple_name: file_path}, f, indent=2)
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}", exc_info=True)
                continue
        
        if not processed_files:
            raise ValueError("No files were processed successfully")
            
        # List all generated files
        logger.info("Generated files:")
        for path in Path(output_dir).rglob('*'):
            if path.is_file():
                logger.info(f"  {path}")
        
        # Create review comment
        review_comment = "## Code Analysis Results\n\n"
        review_comment += "Analyzed generated code and performed the following actions:\n\n"
        review_comment += '\n'.join(review_comments)
        review_comment += "\n\nGenerated files:\n"
        for file in processed_files:
            review_comment += f"- {file}\n"
        
        review_file = Path('.github/generated/review_comment.md')
        review_file.parent.mkdir(parents=True, exist_ok=True)
        with open(review_file, 'w') as f:
            f.write(review_comment)
        
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
