import json
import os
import sys
import argparse
import logging
from datetime import datetime
import random

def setup_logging(log_dir):
    """Configure logging to file and console"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'test_daily.log')),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def modify_records(records, num_to_modify=5):
    """Modify the first N records to simulate changes"""
    modified_records = records.copy()
    
    for i in range(min(num_to_modify, len(modified_records))):
        # Add a test modification to the title
        modified_records[i]['title'] = f"TEST MODIFIED - {modified_records[i]['title']}"
        modified_records[i]['metadata']['Test Status'] = 'Modified'
        modified_records[i]['scraped_date'] = datetime.now().isoformat()
    
    # Remove the modified records to simulate them being gone
    modified_records = modified_records[num_to_modify:]
    
    return modified_records

def create_release_notes(output_dir, test_info, logger):
    """Create formatted release notes"""
    release_notes_path = os.path.join(output_dir, 'release_notes.txt')
    try:
        with open(release_notes_path, 'w') as f:
            f.write("# Test Daily Check Report\n")
            f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Summary\n")
            f.write(f"Removed {test_info['records_removed']} record(s) for testing\n\n")
            
            f.write("## Modified Records\n")
            f.write("| Title | Object ID | Taxonomy | Element | Data Manager | Status | Link |\n")
            f.write("|-------|-----------|----------|---------|--------------|--------|------|\n")
            
            for record in test_info['removed_records']:
                f.write(
                    f"| {record['title']} | {record['object_id']} | {record['taxonomy']} | "
                    f"{record['element']} | {record['data_manager']} | {record['status']} | "
                    f"[View]({record['url']}) |\n"
                )
            
            f.write("\n## Attestations\n")
            f.write("<!-- ATTESTATION_URLS -->\n")
            
        logger.info(f"Created release notes at: {release_notes_path}")
        
    except Exception as e:
        logger.error(f"Error creating release notes: {e}")
        raise

def create_test_data(source_dir, output_dir, logger):
    """Create test data by modifying the source data"""
    try:
        # Load source data
        source_file = os.path.join(source_dir, 'morphosource_data_complete.json')
        logger.info(f"Loading source data from: {source_file}")
        
        with open(source_file, 'r') as f:
            source_data = json.load(f)
        
        # Modify records
        modified_data = modify_records(source_data)
        removed_records = source_data[:5]  # The records we removed
        logger.info(f"Modified {len(source_data) - len(modified_data)} records")
        
        # Save modified data
        output_file = os.path.join(output_dir, 'morphosource_data_complete.json')
        with open(output_file, 'w') as f:
            json.dump(modified_data, f, indent=2)
        
        logger.info(f"Saved modified data to: {output_file}")
        
        # Create test info with detailed record information
        info = {
            'original_count': len(source_data),
            'modified_count': len(modified_data),
            'records_removed': len(source_data) - len(modified_data),
            'test_date': datetime.now().isoformat(),
            'removed_records': [{
                'title': record['title'],
                'object_id': record['metadata'].get('Object', 'N/A'),
                'taxonomy': record['metadata'].get('Taxonomy', 'N/A'),
                'element': record['metadata'].get('Element', 'N/A'),
                'data_manager': record['metadata'].get('Data Manager', 'N/A'),
                'status': record['metadata'].get('Publication Status', 'N/A'),
                'url': record['url']
            } for record in removed_records]
        }
        
        # Save test info
        with open(os.path.join(output_dir, 'test_info.json'), 'w') as f:
            json.dump(info, f, indent=2)
            
        # Create release notes
        create_release_notes(output_dir, info, logger)
        
        return len(modified_data)
        
    except Exception as e:
        logger.error(f"Error creating test data: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Create Test Data for Daily Check')
    parser.add_argument('--source-dir', type=str, required=True,
                      help='Directory containing source data files')
    parser.add_argument('--output-dir', type=str, required=True,
                      help='Directory to store test files')
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Setup logging
    logger = setup_logging(args.output_dir)
    
    try:
        total_records = create_test_data(args.source_dir, args.output_dir, logger)
        logger.info(f"Test data creation complete. Total records: {total_records}")
        return 0
        
    except Exception as e:
        logger.error(f"Error in test data creation: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 