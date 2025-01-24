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
                # Try multiple possible locations for each file
                possible_paths = [
                    Path('.github/generated') / file,  # Direct path
                    Path('.github/generated/scripts') / Path(file).name,  # In scripts subdir
                    Path('.github/generated/workflows') / Path(file).name,  # In workflows subdir
                    Path('.github/generated/.github/scripts') / Path(file).name,  # Nested scripts
                    Path('.github/generated/.github/workflows') / Path(file).name,  # Nested workflows
                ]
                
                file_found = False
                for original_path in possible_paths:
                    logger.info(f"Looking for file at: {original_path}")
                    if original_path.exists():
                        file_found = True
                        logger.info(f"Found file at: {original_path}")
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
                        break
                
                if not file_found:
                    logger.warning(f"File not found in any location: {file}")
                    logger.info("Contents of .github/generated:")
                    for p in Path('.github/generated').rglob('*'):
                        logger.info(f"  {p}")
                    
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
