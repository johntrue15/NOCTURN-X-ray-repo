import os
import re
import json
import logging
import shutil
from pathlib import Path
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

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
    # Create staging directory
    staging_dir = Path('staging/.github')
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    return staging_dir

def get_files_from_metadata():
    """Get list of files to process from metadata.json"""
    metadata_path = Path('.github/generated/metadata.json')
    if not metadata_path.exists():
        logger.error("metadata.json not found")
        raise FileNotFoundError("metadata.json not found")
        
    with open(metadata_path) as f:
        metadata = json.load(f)
        
    files = metadata.get('generated_files', [])
    logger.info(f"Found {len(files)} files in metadata: {files}")
    return files

def copy_generated_files(files, staging_dir):
    """Copy generated files to staging directory"""
    for file in files:
        src_file = Path('.github/generated') / file
        dst_dir = staging_dir / Path(file).parent
        dst_file = staging_dir / file
        
        logger.info(f"Copying {file}:")
        logger.info(f"  From: {src_file}")
        logger.info(f"  To: {dst_file}")
        
        if src_file.exists():
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            logger.info("Successfully copied file")
        else:
            logger.warning(f"Source file not found: {src_file}")
            logger.info("Contents of .github/generated:")
            for p in Path('.github/generated').rglob('*'):
                logger.info(f"  {p}")

def verify_staged_files(files, staging_dir):
    """Verify all required files exist in staging"""
    missing_files = []
    for file in files:
        staged_file = staging_dir / file
        if not staged_file.exists():
            missing_files.append(file)
            
    if missing_files:
        logger.error(f"Missing required files in staging: {missing_files}")
        raise FileNotFoundError(f"Required files not found in staging: {missing_files}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_claude(prompt):
    """Call Claude API with retries"""
    try:
        system_prompt = """You are an expert programmer helping to combine code files. 
        You will receive an original file from main and updates to be integrated. 
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

def extract_code(response, file_path):
    """Extract code from Claude's response"""
    # Try different code block patterns
    patterns = [
        r'```(?:yaml|python)?\n(.*?)```',  # Standard code block with language
        r'```(.*?)```',                    # Simple code block
        r'^(.*?)$'                         # Entire response if no code blocks
    ]
    
    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Remove any ```yaml or ```python prefix if it got included
            code = re.sub(r'^```(?:yaml|python)\n', '', code)
            code = re.sub(r'\n```$', '', code)
            logger.info(f"Successfully extracted code for {file_path} using pattern: {pattern}")
            return code
            
    logger.error(f"Could not extract code from response for {file_path}")
    logger.error(f"Response was: {response[:200]}...")
    return None

def get_claude_prompt(original_file, generated_file, file_path):
    """Create prompt for Claude to combine files"""
    prompt = f"""Please combine these two code files into a single updated version.
The first file is the original from main, and the second contains updates to be integrated.

Original file ({file_path}):
```
{original_file}
```

Generated updates ({file_path}):
```
{generated_file}
```

Please provide the complete combined code incorporating the updates while preserving the original structure.
Return only the code without any explanation, wrapped in triple backticks."""

    return prompt

def process_files():
    """Main function to process and analyze files"""
    try:
        # Setup directories
        staging_dir = setup_directories()
        
        # Get files from metadata
        files = get_files_from_metadata()
        
        # Process each file
        success_count = 0
        for file in files:
            try:
                # Get files from generated directory
                original_path = Path('.github/generated') / file
                generated_path = original_path  # We'll use the same file for now
                
                logger.info(f"Looking for file at: {original_path}")
                if not original_path.exists():
                    logger.warning(f"File not found: {original_path}")
                    logger.info("Contents of .github/generated:")
                    for p in Path('.github/generated').rglob('*'):
                        logger.info(f"  {p}")
                    continue
                    
                # Read the file
                with open(original_path) as f:
                    file_content = f.read()
                    
                # Save to staging
                output_path = staging_dir / file
                os.makedirs(output_path.parent, exist_ok=True)
                with open(output_path, 'w') as f:
                    f.write(file_content)
                logger.info(f"Saved file to staging: {output_path}")
                success_count += 1
                
            except Exception as e:
                logger.error(f"Error processing {file}: {e}")
                continue
                
        if success_count == 0:
            raise Exception("No files were successfully processed")
            
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}")
        raise

if __name__ == '__main__':
    process_files()
