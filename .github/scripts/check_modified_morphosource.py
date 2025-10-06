#!/usr/bin/env python3
import os
import sys
import json
import logging
from morphosource_api import MorphoSourceAPIClient

LAST_MODIFIED_FILE = ".github/last_modified_record.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_top_modified_record(api_client):
    """Get the most recently modified record from MorphoSource API"""
    try:
        # Get recently modified records from API
        modified_records = api_client.get_modified_records(count=1)
        
        if not modified_records:
            raise ValueError("No modified records found")
        
        api_record = modified_records[0]
        
        # Convert to legacy format
        record = {
            "title": api_record.get('title', api_record.get('name', 'No Title')),
            "detail_url": f"https://www.morphosource.org/concern/media/{api_record.get('id', '')}",
            "id": api_record.get('id', 'unknown')
        }
        
        # Add metadata fields
        metadata_mapping = {
            'object_id': 'Object',
            'taxonomy': 'Taxonomy',
            'element': 'Element or Part',
            'data_manager': 'Data Manager',
            'date_uploaded': 'Date Uploaded',
            'publication_status': 'Publication Status',
            'rights_statement': 'Rights Statement',
            'cc_license': 'CC License'
        }
        
        for api_field, display_name in metadata_mapping.items():
            if api_field in api_record:
                record[display_name] = api_record[api_field]
        
        return record
        
    except Exception as e:
        logger.error(f"Failed to get modified record from API: {e}")
        write_github_output(False, f"MorphoSource API error: {str(e)}")
        sys.exit(0)  # Exit gracefully to prevent GitHub Action failure

def load_last_modified_record():
    """Load the previously saved most recently modified record"""
    if not os.path.exists(LAST_MODIFIED_FILE):
        return None
    try:
        with open(LAST_MODIFIED_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None

def save_last_modified_record(record):
    """Save the most recently modified record"""
    os.makedirs(os.path.dirname(LAST_MODIFIED_FILE), exist_ok=True)
    with open(LAST_MODIFIED_FILE, "w") as f:
        json.dump(record, f, indent=2)

def format_release_message(record, is_new=True):
    """Format the release message for a modified record"""
    lines = []
    
    if is_new:
        lines.append("A newly modified X-ray Computed Tomography record was found on MorphoSource.")
    else:
        lines.append("First time tracking modified X-ray Computed Tomography records on MorphoSource.")
    
    lines.append("")
    lines.append(f"Record Title: {record.get('title', 'N/A')}")
    lines.append(f"Detail Page URL: {record.get('detail_url', 'N/A')}")
    lines.append(f"Record ID: {record.get('id', 'N/A')}")

    for key in [
        "Object",
        "Taxonomy",
        "Element or Part",
        "Data Manager",
        "Date Uploaded",
        "Publication Status",
        "Rights Statement",
        "CC License",
    ]:
        if key in record:
            lines.append(f"{key}: {record[key]}")
    
    return "\n".join(lines)

def write_github_output(is_modified, message):
    """Helper function to write GitHub output"""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"is_modified={str(is_modified).lower()}\n")
            fh.write("details<<EOF\n")
            fh.write(message + "\n")
            fh.write("EOF\n")

def compare_with_recent_release(current_record, release_body):
    """
    Compare the current modified record with a recent release to avoid duplicates
    
    Args:
        current_record: The current modified record from MorphoSource
        release_body: The body text of a recent MorphoSource release
        
    Returns:
        bool: True if the records are the same, False otherwise
    """
    # Check if record ID is in the release body
    record_id = current_record.get('id', '')
    if record_id != 'unknown' and record_id in release_body:
        return True
        
    # Check if record title is in the release body
    record_title = current_record.get('title', '')
    if record_title and record_title in release_body:
        return True
        
    # Check if detail URL is in the release body
    detail_url = current_record.get('detail_url', '')
    if detail_url and detail_url in release_body:
        return True
        
    # Check for object identifier
    object_id = current_record.get('Object', '')
    if object_id and object_id in release_body:
        # Additional check to avoid false positives
        taxonomy = current_record.get('Taxonomy', '')
        if taxonomy and taxonomy in release_body:
            return True
            
    return False

def main():
    # Get API key from environment
    api_key = os.environ.get('MORPHOSOURCE_API_KEY')
    if not api_key:
        logger.error("MORPHOSOURCE_API_KEY environment variable not set")
        write_github_output(False, "Error: MORPHOSOURCE_API_KEY not configured")
        sys.exit(1)
    
    try:
        # Initialize API client
        api_client = MorphoSourceAPIClient(api_key)
        logger.info("MorphoSource API client initialized")
        
        # Get the most recently modified record
        current_record = get_top_modified_record(api_client)
        logger.info(f"Current top modified record: {current_record.get('title')}")
        
        # Load the previously saved record
        last_record = load_last_modified_record()
        
        # Check if we need to compare with a recent release
        recent_release_tag = os.environ.get("RECENT_RELEASE_TAG")
        if recent_release_tag:
            logger.info(f"Checking against recent release: {recent_release_tag}")
            try:
                import subprocess
                release_info = subprocess.check_output(
                    ['gh', 'release', 'view', recent_release_tag, '--json', 'body'], 
                    text=True,
                    env=dict(os.environ, GH_TOKEN=os.environ.get("GITHUB_TOKEN", ""))
                )
                release_body = json.loads(release_info)['body']
                
                # Compare the current record with the recent release
                if compare_with_recent_release(current_record, release_body):
                    logger.info("The modified record is the same as in the recent release, skipping")
                    
                    # Still update our last_modified_record.json if needed
                    if last_record is None or current_record.get('id') != last_record.get('id'):
                        save_last_modified_record(current_record)
                        
                    write_github_output(False, "The modified record is the same as in the recent release")
                    return
            except Exception as e:
                logger.warning(f"Error comparing with recent release: {str(e)}")
                # Continue with normal processing if comparison fails
        
        if last_record is None:
            # First time running this script
            logger.info("No previous record found. This is the first run.")
            save_last_modified_record(current_record)
            message = format_release_message(current_record, is_new=False)
            write_github_output(True, message)
        elif current_record.get('id') != last_record.get('id'):
            # Different record ID - a new record has been modified
            logger.info(f"New modified record detected. Old: {last_record.get('id')}, New: {current_record.get('id')}")
            save_last_modified_record(current_record)
            message = format_release_message(current_record, is_new=True)
            write_github_output(True, message)
        else:
            # Same record - no changes
            logger.info("No changes in the most recently modified record.")
            write_github_output(False, "No changes in the most recently modified record.")
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        write_github_output(False, f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 