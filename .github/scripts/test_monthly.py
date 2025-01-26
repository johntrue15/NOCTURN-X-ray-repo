import json
import os
import sys
from datetime import datetime
import argparse
import logging
import re

def setup_logging(log_dir):
    """Configure logging to file and console"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'test_collection.log')),
            logging.StreamHandler()
        ]
    )

def create_attestation_template(record_count, total_records, modified_records, subject_name, subject_digest=None):
    """Create attestation JSON template"""
    return {
        "_type": "https://in-toto.io/Statement/v0.1",
        "subject": [{
            "name": subject_name,
            "digest": {
                "sha256": subject_digest or ""
            }
        }],
        "predicateType": "https://in-toto.io/attestation/release/v0.1",
        "predicate": {
            "purl": f"pkg:github/{os.environ.get('GITHUB_REPOSITORY', '')}",
            "version": os.environ.get('GITHUB_SHA', ''),
            "metadata": {
                "buildInvocationId": os.environ.get('GITHUB_RUN_ID', ''),
                "completeness": {
                    "parameters": True,
                    "environment": True,
                    "materials": True
                },
                "test_parameters": {
                    "record_count": str(record_count)
                },
                "stats": {
                    "total_records": str(total_records),
                    "modified_records": str(modified_records)
                }
            }
        }
    }

def extract_sha256_from_log(log_message):
    """Extract SHA256 from attestation log message"""
    match = re.search(r'@sha256:([a-f0-9]+)', log_message)
    return match.group(1) if match else None

def create_test_data(output_dir, record_count):
    setup_logging(output_dir)
    logger = logging.getLogger(__name__)
    
    logger.info(f"Creating {record_count} test records in {output_dir}")
    
    # Create test records
    records = []
    for i in range(record_count):
        record = {
            'id': f'test-{i}',
            'title': f'Test Record {i}',
            'url': f'https://example.com/record/{i}',
            'metadata': {
                'Object': f'Object-{i}',
                'Publication Status': 'Test'
            },
            'scraped_date': datetime.now().isoformat()
        }
        records.append(record)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Save data files with full paths
    data_file = os.path.join(output_dir, 'morphosource_data_complete.json')
    stats_file = os.path.join(output_dir, 'monthly_stats.json')
    notes_file = os.path.join(output_dir, 'monthly_release_notes.txt')
    
    logger.info(f"Writing data files to {output_dir}")
    
    # Save complete dataset
    with open(data_file, 'w') as f:
        json.dump(records, f, indent=2)
    
    # Save stats
    stats = {
        'total_records': len(records),
        'modified_records': 0,
        'new_records': len(records),
        'collection_date': datetime.now().isoformat()
    }
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    # Create attestation template
    attestation = create_attestation_template(
        record_count=record_count,
        total_records=len(records),
        modified_records=0,
        subject_name='morphosource_data_complete.json'
    )
    
    # If we have a log message with SHA256, update the template
    log_message = os.environ.get('ATTEST_LOG_MESSAGE', '')
    if log_message:
        sha256 = extract_sha256_from_log(log_message)
        if sha256:
            attestation['subject'][0]['digest']['sha256'] = sha256
    
    # Save attestation template
    attestation_file = os.path.join(output_dir, 'attestation.json')
    with open(attestation_file, 'w') as f:
        json.dump(attestation, f, indent=2)
    
    # Create release notes
    release_notes = [
        "# Test Collection Report\n",
        f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        "## Summary\n",
        f"- Total Records: {len(records)}\n",
        f"- Generated Records: {record_count}\n\n",
        "## Attestations\n",
        "<!-- ATTESTATION_URLS -->\n\n",
        "## Details\n",
        "This is a test collection of generated records.\n"
    ]
    
    with open(notes_file, 'w') as f:
        f.writelines(release_notes)
    
    # Log completion
    logger.info(f"Successfully created {len(records)} test records")
    return len(records)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test Data Generator')
    parser.add_argument('--output-dir', type=str, required=True,
                    help='Directory to store output files')
    parser.add_argument('--record-count', type=int, required=True,
                    help='Number of test records to generate')
    args = parser.parse_args()
    
    total_records = create_test_data(args.output_dir, args.record_count)
