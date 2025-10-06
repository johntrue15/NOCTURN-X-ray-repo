#!/usr/bin/env python3
import os
import sys
import logging
from morphosource_api import MorphoSourceAPIClient

LAST_COUNT_FILE = ".github/last_count.txt"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_current_record_count(api_client):
    """Get current count of X-ray CT records using API"""
    try:
        # Get first page to find total count
        result = api_client.search_media(page=1, per_page=1)
        
        # Extract total count from API response
        # The actual field name may vary based on API implementation
        total_count = result.get('meta', {}).get('total', 0)
        
        if total_count == 0:
            # Fallback: try different field names
            total_count = result.get('total', result.get('total_count', 0))
        
        logger.info(f"Current record count from API: {total_count}")
        return total_count
        
    except Exception as e:
        logger.error(f"Failed to get record count from API: {e}")
        write_github_output(False, f"MorphoSource API error: {str(e)}")
        sys.exit(0)  # Exit gracefully to prevent GitHub Action failure

def load_last_count():
    if not os.path.exists(LAST_COUNT_FILE):
        return 0
    try:
        with open(LAST_COUNT_FILE, "r") as f:
            return int(f.read().strip())
    except ValueError:
        return 0

def save_last_count(count):
    os.makedirs(os.path.dirname(LAST_COUNT_FILE), exist_ok=True)
    with open(LAST_COUNT_FILE, "w") as f:
        f.write(str(count))

def parse_top_records(api_client, n=3):
    """
    Get the first n records from MorphoSource API
    (descending by creation date). Returns a list of dicts containing relevant metadata.
    """
    try:
        # Get recent records from API
        api_records = api_client.get_recent_records(count=n)
        
        records = []
        for api_record in api_records:
            # Convert API format to legacy format
            record = {
                "title": api_record.get('title', api_record.get('name', 'No Title')),
                "detail_url": f"https://www.morphosource.org/concern/media/{api_record.get('id', '')}"
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
            
            records.append(record)
        
        return records
        
    except Exception as e:
        logger.error(f"Failed to parse records from API: {e}")
        write_github_output(False, f"MorphoSource API error while parsing records: {str(e)}")
        sys.exit(0)  # Exit gracefully to prevent GitHub Action failure

def format_release_message(new_records, old_count, records):
    """
    Creates a multiline string for the Release body:
      - How many new records (plus old record value)
      - Then each record in descending order, labeled as "New Record #..."
    """
    lines = []
    lines.append("A new increase in X-ray Computed Tomography records was found on MorphoSource.")
    lines.append("")
    lines.append(f"We found {new_records} new record(s) (old record value: {old_count}).")
    lines.append("")

    for i, rec in enumerate(records, start=1):
        record_number = old_count + new_records - (i - 1)
        lines.append(f"New Record #{record_number} Title: {rec.get('title', 'N/A')}")
        lines.append(f"Detail Page URL: {rec.get('detail_url', 'N/A')}")

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
            if key in rec:
                lines.append(f"{key}: {rec[key]}")
        lines.append("")  # Blank line after each record

    return "\n".join(lines)

def write_github_output(is_new_data, message):
    """Helper function to write GitHub output"""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"new_data={str(is_new_data).lower()}\n")
            fh.write("details<<EOF\n")
            fh.write(message + "\n")
            fh.write("EOF\n")

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
        
        current_count = get_current_record_count(api_client)
        logger.info(f"Current count: {current_count}")
        
        old_count = load_last_count()
        logger.info(f"Old count: {old_count}")
        
        new_records = current_count - old_count
        logger.info(f"New records: {new_records}")

        if new_records != 0:  # Handle both positive and negative changes
            records_to_fetch = min(abs(new_records), 3)  # Use abs() to handle negative
            top_records = parse_top_records(api_client, n=records_to_fetch)
            save_last_count(current_count)  # Always save the current count
            message = format_release_message(new_records, old_count, top_records)
            write_github_output(True, message)
        else:
            write_github_output(False, "No changes in record count.")
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        write_github_output(False, f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
