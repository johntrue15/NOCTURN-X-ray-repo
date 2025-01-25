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
            base_dir / '.github/workflows' / file_name,
            base_dir / '.github/scripts' / file_name
        ]
    else:
        # For generated files, look in .github/generated first
        search_paths = [
            base_dir / '.github/workflows' / file_name,
            base_dir / '.github/scripts' / file_name,
            base_dir / '.github/generated/workflows' / file_name,
            base_dir / '.github/generated/scripts' / file_name,
            base_dir / '.github/generated/.github/workflows' / file_name,
            base_dir / '.github/generated/.github/scripts' / file_name
        ]
    
    # Try each possible location
    for path in search_paths:
        logger.info(f"Checking path: {path}")
        if path.exists():
            logger.info(f"Found file at: {path}")
            return path
    
    # If not found in expected locations, do a recursive search
    logger.info("File not found in expected locations, doing recursive search...")
    
    # For original files, only search in .github directory
    if file_type == 'original':
        search_dir = base_dir / '.github'
    else:
        search_dir = base_dir
        
    all_files = list(search_dir.rglob(file_name))
    
    if all_files:
        # Sort files to prefer .github/workflows and .github/scripts paths
        all_files.sort(key=lambda p: (
            '.github/workflows' not in str(p),
            '.github/scripts' not in str(p),
            str(p)
        ))
        chosen_file = all_files[0]
        logger.info(f"Using file: {chosen_file}")
        return chosen_file
        
    logger.warning(f"File not found: {file_name}")
    logger.info("Directory contents:")
    for p in base_dir.rglob('*'):
        logger.info(f"  {p}")
    return None

def get_claude_prompt(original_content, generated_content, file_path):
    """Create prompt for Claude to analyze and combine code"""
    is_yaml = file_path.endswith('.yml') or file_path.endswith('.yaml')
    
    base_prompt = f"""You are an expert code reviewer. Please analyze and combine these two versions of code into a single improved version.
The first is the original code, and the second contains generated updates that need to be integrated.

Original file ({file_path}):
```
{original_content}
```

Generated updates ({file_path}):
```
{generated_content}
```

Important instructions:
1. Preserve the core functionality and structure of the original code
2. Integrate the new features and improvements from the generated updates
3. Keep the file structure consistent with the original
"""

    if is_yaml:
        base_prompt += """
4. Preserve all job and step names from both versions
5. Keep all environment variables and secrets
6. Maintain the same job dependencies and conditions
7. Preserve any existing error handling and notifications
"""
    else:
        base_prompt += """
4. Keep all imports and function signatures from both versions
5. Use comments to mark significant changes
6. Include ALL functions from both versions unless they are exact duplicates
7. Preserve any existing error handling and logging
"""

    base_prompt += "\nReturn only the entire combined code which is wrapped in triple backticks without any explanation."

    return base_prompt

def validate_combined_code(original, generated, combined, file_path):
    """Validate that the combined code is reasonable"""
    if not combined or len(combined.strip()) < 10:
        logger.error(f"Combined code for {file_path} is too short")
        return False
        
    # Check line counts
    orig_lines = len(original.split('\n'))
    gen_lines = len(generated.split('\n'))
    comb_lines = len(combined.split('\n'))
    
    # For YAML files, be more lenient with line count differences
    is_yaml = file_path.endswith('.yml') or file_path.endswith('.yaml')
    if is_yaml:
        # Allow more variation in YAML files due to formatting differences
        if comb_lines < min(orig_lines, gen_lines) * 0.7:
            logger.error(f"Combined YAML ({comb_lines} lines) is too short compared to inputs ({orig_lines}, {gen_lines} lines)")
            return False
        if comb_lines > max(orig_lines, gen_lines) * 1.5:
            logger.error(f"Combined YAML ({comb_lines} lines) is suspiciously long")
            return False
    else:
        # Stricter validation for Python files
        if comb_lines < min(orig_lines, gen_lines):
            logger.error(f"Combined code ({comb_lines} lines) is shorter than inputs ({orig_lines}, {gen_lines} lines)")
            return False
        if comb_lines > max(orig_lines, gen_lines) * 2:
            logger.error(f"Combined code ({comb_lines} lines) is suspiciously long")
            return False
    
    # For YAML files, check key sections are preserved
    if is_yaml:
        orig_sections = extract_yaml_sections(original)
        comb_sections = extract_yaml_sections(combined)
        missing_sections = [s for s in orig_sections if s not in comb_sections]
        if missing_sections:
            logger.error(f"Combined YAML is missing sections: {missing_sections}")
            return False
    else:
        # For Python files, check functions and imports
        orig_funcs = extract_function_names(original)
        comb_funcs = extract_function_names(combined)
        missing_funcs = [f for f in orig_funcs if f not in comb_funcs]
        if missing_funcs:
            logger.error(f"Combined code is missing functions: {missing_funcs}")
            return False
            
        orig_imports = extract_imports(original)
        comb_imports = extract_imports(combined)
        missing_imports = [i for i in orig_imports if i not in comb_imports]
        if missing_imports:
            logger.error(f"Combined code is missing imports: {missing_imports}")
            return False
    
    return True

def extract_yaml_sections(yaml_content):
    """Extract top-level sections from YAML content"""
    sections = []
    current_section = None
    
    for line in yaml_content.split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and not stripped.startswith('-'):
            if not line.startswith(' '):  # Top-level key
                current_section = stripped.split(':')[0]
                sections.append(current_section)
                
    return sections

def extract_function_names(code):
    """Extract function names from code"""
    import re
    pattern = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    return re.findall(pattern, code)

def extract_imports(code):
    """Extract import statements from code"""
    import re
    pattern = r'^(?:from\s+[\w.]+\s+)?import\s+[\w,\s]+$'
    return [line.strip() for line in code.split('\n') if re.match(pattern, line.strip())]

def call_claude(prompt):
    """Call Claude API to get combined code"""
    try:
        logger.info("Calling Claude API...")
        
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
        
        logger.info("Received response from Claude")
        return response.content[0].text

    except Exception as e:
        logger.error(f"Error calling Claude API: {e}")
        raise

def extract_code(response):
    """Extract code from Claude's response"""
    logger.info("Extracting code from response...")
    
    # Remove any explanatory text before/after code block
    start = response.find("```")
    end = response.rfind("```")
    
    if start != -1 and end != -1:
        code = response[start+3:end].strip()
        # Remove language identifier if present
        if code.startswith(('python', 'yaml')):
            code = code[code.find('\n')+1:]
        logger.info(f"Successfully extracted code block ({len(code)} chars)")
        return code.strip()
    
    logger.error("Could not find code block markers in response")
    logger.error(f"Response starts with: {response[:200]}")
    return None

def process_files():
    """Main function to process and analyze files"""
    try:
        staging_dir = setup_directories()
        files = get_files_from_metadata()
        logger.info("Processing files from metadata...")
        
        success_count = 0
        results = []  # Track results for logging
        
        for file in files:
            try:
                file_name = Path(file).name
                logger.info(f"\n{'='*80}\nProcessing file: {file_name}")
                
                # Find original and generated files
                original_path = find_file(file_name, 'main-files', file_type='original')
                generated_path = find_file(file_name, '.github/generated')
                
                if not original_path or not generated_path:
                    msg = f"Could not find both versions of {file}"
                    logger.warning(msg)
                    results.append({"file": file, "status": "error", "message": msg})
                    continue
                
                # Read both files
                try:
                    with open(original_path) as f:
                        original_content = f.read()
                    with open(generated_path) as f:
                        generated_content = f.read()
                except Exception as e:
                    msg = f"Error reading files: {e}"
                    logger.error(msg)
                    results.append({"file": file, "status": "error", "message": msg})
                    continue
                
                # Debug file contents
                logger.info(f"Original file ({original_path}):\n{'-'*40}\n{original_content[:500]}...\n")
                logger.info(f"Generated file ({generated_path}):\n{'-'*40}\n{generated_content[:500]}...\n")
                
                # Get Claude's combined version
                prompt = get_claude_prompt(original_content, generated_content, file)
                logger.info(f"Sending prompt to Claude:\n{'-'*40}\n{prompt[:500]}...\n")
                
                response = call_claude(prompt)
                
                # Save Claude's response for debugging
                response_file = Path("logs") / f"claude_response_{file_name}.txt"
                os.makedirs(response_file.parent, exist_ok=True)
                with open(response_file, 'w') as f:
                    f.write(f"Original File: {original_path}\n")
                    f.write(f"Generated File: {generated_path}\n")
                    f.write(f"\nPrompt:\n{prompt}\n")
                    f.write(f"\nResponse:\n{response}")
                
                # Extract and validate code
                combined_code = extract_code(response)
                if not combined_code:
                    msg = "Failed to extract code from Claude's response"
                    logger.error(msg)
                    results.append({"file": file, "status": "error", "message": msg})
                    continue
                
                logger.info(f"Extracted combined code:\n{'-'*40}\n{combined_code[:500]}...\n")
                
                if validate_combined_code(original_content, generated_content, combined_code, file):
                    # Fix the staging directory path structure
                    if file.startswith('workflows/'):
                        rel_path = 'workflows'
                    elif file.startswith('scripts/'):
                        rel_path = 'scripts'
                    else:
                        rel_path = ''
                    
                    output_path = staging_dir / '.github' / rel_path / file_name
                    os.makedirs(output_path.parent, exist_ok=True)
                    
                    with open(output_path, 'w') as f:
                        f.write(combined_code)
                    
                    msg = f"Successfully combined and saved: {output_path}"
                    logger.info(msg)
                    results.append({"file": file, "status": "success", "message": msg})
                    success_count += 1
                else:
                    msg = f"Validation failed for combined code"
                    logger.error(msg)
                    logger.error(f"Line counts - Original: {len(original_content.split('\n'))}, " +
                               f"Generated: {len(generated_content.split('\n'))}, " +
                               f"Combined: {len(combined_code.split('\n'))}")
                    results.append({"file": file, "status": "error", "message": msg})
                    continue
                
            except Exception as e:
                msg = f"Error processing {file}: {str(e)}"
                logger.error(msg, exc_info=True)
                results.append({"file": file, "status": "error", "message": msg})
                continue
        
        # Save results summary
        summary_file = Path("logs") / "combination_results.json"
        with open(summary_file, 'w') as f:
            json.dump({
                "total_files": len(files),
                "successful_combinations": success_count,
                "results": results
            }, f, indent=2)
        
        if success_count == 0:
            raise Exception("No files were successfully processed")
            
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    process_files()
