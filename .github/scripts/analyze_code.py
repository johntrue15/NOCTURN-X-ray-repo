import os
import json
import logging
from pathlib import Path
from anthropic import Anthropic

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Claude client
anthropic = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"

def setup_directories():
    """Create necessary directory structure"""
    staging_dir = Path('staging/.github')
    staging_dir.mkdir(parents=True, exist_ok=True)
    return staging_dir

def get_files_from_metadata():
    """Get list of files to process from metadata.json"""
    # Try multiple possible locations for metadata.json
    possible_paths = [
        Path('.github/generated/metadata.json'),
        Path('.github/generated/.github/metadata.json'),
        Path('.github/metadata.json')
    ]
    
    for metadata_path in possible_paths:
        logger.info(f"Looking for metadata.json at: {metadata_path}")
        if metadata_path.exists():
            logger.info(f"Found metadata.json at: {metadata_path}")
            with open(metadata_path) as f:
                metadata = json.load(f)
            files = metadata.get('generated_files', [])
            files = [f.replace('.github/', '') for f in files]
            logger.info(f"Found {len(files)} files in metadata: {files}")
            return files
            
    # If metadata.json not found, try to find files directly
    logger.warning("metadata.json not found, searching for files directly")
    files = []
    
    # Look for workflow files
    workflow_files = list(Path('.github/generated').rglob('combined_ct_images_to_text.yml'))
    if workflow_files:
        files.append('workflows/combined_ct_images_to_text.yml')
        
    # Look for script files
    script_files = list(Path('.github/generated').rglob('url_screenshot_check.py'))
    if script_files:
        files.append('scripts/url_screenshot_check.py')
        
    if files:
        logger.info(f"Found {len(files)} files by direct search: {files}")
        return files
        
    raise FileNotFoundError("No files found to process")

def find_file(file_name, directory, file_type=None):
    """Find a file in the specified directory"""
    base_dir = Path(directory)
    logger.info(f"Searching for {file_name} in {base_dir}")
    
    # Define search paths based on file type
    if file_type == 'original':
        # For original files in main branch
        search_paths = [
            base_dir / 'workflows' / file_name,
            base_dir / 'scripts' / file_name,
            base_dir / '.github/workflows' / file_name,
            base_dir / '.github/scripts' / file_name
        ]
    else:
        # For generated files, check both locations
        search_paths = [
            base_dir / 'workflows' / file_name,
            base_dir / 'scripts' / file_name,
            base_dir / '.github/workflows' / file_name,
            base_dir / '.github/scripts' / file_name,
            base_dir / 'generated/workflows' / file_name,
            base_dir / 'generated/scripts' / file_name
        ]
    
    # Try each possible location
    for path in search_paths:
        logger.info(f"Checking path: {path}")
        if path.exists():
            logger.info(f"Found file at: {path}")
            return path
            
    # If not found, do a recursive search
    logger.info("File not found in expected locations, doing recursive search...")
    all_files = list(base_dir.rglob(file_name))
    
    if all_files:
        # If multiple files found, prefer the one in .github/workflows or .github/scripts
        for file in all_files:
            if '.github/workflows' in str(file) or '.github/scripts' in str(file):
                logger.info(f"Using preferred path: {file}")
                return file
        # Otherwise use the first one found
        logger.info(f"Using found path: {all_files[0]}")
        return all_files[0]
        
    logger.warning(f"File not found: {file_name}")
    logger.info("Directory contents:")
    for p in base_dir.rglob('*'):
        logger.info(f"  {p}")
    return None

def get_claude_prompt(original_content, generated_content, file_path):
    """Create prompt for Claude to analyze and combine code"""
    prompt = f"""Please analyze and combine these two code files into a single improved version.
The first is the original code, and the second contains updates to be integrated.

Original file ({file_path}):
```
{original_content}
```

Generated updates ({file_path}):
```
{generated_content}
```

Please provide the complete combined code incorporating the updates while preserving the original structure.
Return only the code without any explanation, wrapped in triple backticks."""

    return prompt

def call_claude(prompt):
    """Call Claude API to get combined code"""
    try:
        system_prompt = """You are an expert programmer helping to combine code files.
        You will receive an original file and updates to be integrated.
        Your response must be the combined code wrapped in triple backticks."""
        
        response = anthropic.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            temperature=0,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": prompt
            }],
            extra_headers={
                "anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"
            }
        )
        
        logger.info(f"Got response from Claude: {response.content[0].text[:100]}...")
        return response.content[0].text

    except Exception as e:
        logger.error(f"Error calling Claude API: {e}")
        raise

def extract_code(response):
    """Extract code from Claude's response"""
    # Remove any explanatory text before/after code block
    start = response.find("```")
    end = response.rfind("```")
    
    if start != -1 and end != -1:
        code = response[start+3:end].strip()
        # Remove language identifier if present
        if code.startswith(('python', 'yaml')):
            code = code[code.find('\n')+1:]
        return code.strip()
    
    logger.error("Could not extract code from Claude response")
    return None

def process_files():
    """Main function to process and analyze files"""
    try:
        staging_dir = setup_directories()
        files = get_files_from_metadata()
        logger.info("Processing files from metadata...")
        
        success_count = 0
        for file in files:
            try:
                file_name = Path(file).name
                logger.info(f"Processing file: {file_name}")
                
                # Find original and generated files
                original_path = find_file(file_name, 'main-files/.github', file_type='original')
                generated_path = find_file(file_name, '.github/generated')
                
                if not original_path or not generated_path:
                    logger.warning(f"Could not find both versions of {file}")
                    logger.info(f"Original path: {original_path}")
                    logger.info(f"Generated path: {generated_path}")
                    continue
                
                # Read both files
                with open(original_path) as f:
                    original_content = f.read()
                with open(generated_path) as f:
                    generated_content = f.read()
                
                # Get Claude's combined version
                prompt = get_claude_prompt(original_content, generated_content, file)
                response = call_claude(prompt)
                
                # Extract and save code
                combined_code = extract_code(response)
                if combined_code:
                    output_path = staging_dir / file
                    os.makedirs(output_path.parent, exist_ok=True)
                    with open(output_path, 'w') as f:
                        f.write(combined_code)
                    logger.info(f"Saved combined file: {output_path}")
                    success_count += 1
                
            except Exception as e:
                logger.error(f"Error processing {file}: {e}", exc_info=True)
                continue
                
        if success_count == 0:
            raise Exception("No files were successfully processed")
            
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    process_files()
