import os
import re
import json
import logging
import anthropic
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Claude client
claude = anthropic.Client(os.environ.get('ANTHROPIC_API_KEY'))
CLAUDE_MODEL = "claude-3-sonnet-20240229"

@retry(stop=after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_claude(prompt):
    """Call Claude API to get response with retries"""
    try:
        system_prompt = """You are an expert programmer helping to combine code files. 
        You will receive an original file from main and updates to be integrated. 
        Provide only the combined code without any explanation."""
        
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        return response.content[0].text

    except Exception as e:
        logger.error(f"Error calling Claude API: {e}")
        raise

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

def process_files(generated_dir, output_dir):
    """Process original and generated files"""
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Find generated files
    generated_files = {}
    for path in Path(generated_dir).rglob('*'):
        if path.is_file() and path.suffix in ['.py', '.yml', '.yaml', '.json']:
            # Skip files already in complete directory
            if 'complete' in str(path):
                continue
            rel_path = path.relative_to(generated_dir)
            generated_files[rel_path] = path

    logger.info(f"Found {len(generated_files)} generated files to process")
    
    # Process each file
    for rel_path, generated_path in generated_files.items():
        try:
            # Get original file from main branch files in .github/main directory
            original_path = Path('.github/main') / rel_path
            if not original_path.exists():
                logger.warning(f"Original file not found: {original_path}")
                continue
                
            # Read both files
            with open(original_path) as f:
                original_content = f.read()
            with open(generated_path) as f:
                generated_content = f.read()
                
            # Get Claude's combined version
            prompt = get_claude_prompt(original_content, generated_content, str(rel_path))
            response = call_claude(prompt)
            
            # Extract code from response
            code_pattern = r'```(?:\w+)?\n(.*?)```'
            match = re.search(code_pattern, response, re.DOTALL)
            if not match:
                logger.error(f"Could not extract code from Claude's response for {rel_path}")
                continue
                
            combined_code = match.group(1).strip()
            
            # Save combined file to complete directory in issue branch
            output_path = Path(output_dir) / rel_path
            os.makedirs(output_path.parent, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(combined_code)
                
            logger.info(f"Saved combined file: {output_path}")
            
        except Exception as e:
            logger.error(f"Error processing {rel_path}: {e}")
            continue

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--branch', required=True)
    parser.add_argument('--artifacts-dir', required=True)
    args = parser.parse_args()
    
    try:
        # Process files using paths in the issue branch
        process_files(
            generated_dir=args.artifacts_dir,
            output_dir=os.path.join(args.artifacts_dir, 'complete')
        )
        
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
