import os
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_directories():
    """Create necessary directory structure"""
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
        
    # Get files and ensure they're in the correct format
    files = metadata.get('generated_files', [])
    # Remove .github/ prefix if present
    files = [f.replace('.github/', '') for f in files]
    logger.info(f"Found {len(files)} files in metadata: {files}")
    return files

def find_file(file_name):
    """Find a file in the generated directories"""
    base_dir = Path('.github/generated')
    
    # List all files in generated directory
    logger.info(f"Searching for {file_name} in {base_dir}")
    all_files = list(base_dir.rglob('*'))
    logger.info(f"Found {len(all_files)} total files")
    
    # Find files matching the name
    matches = [f for f in all_files if f.is_file() and f.name == Path(file_name).name]
    if matches:
        logger.info(f"Found matching file at: {matches[0]}")
        return matches[0]
    return None

def process_files():
    """Main function to process and analyze files"""
    try:
        # Setup directories
        staging_dir = setup_directories()
        
        # Get files from metadata
        files = get_files_from_metadata()
        logger.info("Processing files from metadata...")
        
        # Process each file
        success_count = 0
        for file in files:
            try:
                # Find the file
                source_path = find_file(Path(file).name)
                if not source_path:
                    logger.warning(f"File not found: {file}")
                    logger.info("Contents of .github/generated:")
                    for p in Path('.github/generated').rglob('*'):
                        logger.info(f"  {p}")
                    continue
                
                # Read and save the file
                with open(source_path) as f:
                    file_content = f.read()
                
                # Save to staging
                output_path = staging_dir / file
                os.makedirs(output_path.parent, exist_ok=True)
                with open(output_path, 'w') as f:
                    f.write(file_content)
                logger.info(f"Saved file to staging: {output_path}")
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
