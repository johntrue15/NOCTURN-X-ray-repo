#!/usr/bin/env python3
import os
import sys
import json
import time
import random
from morphosource_api import MorphoSourceAPI, MorphoSourceAPIError, MorphoSourceTemporarilyUnavailable

LAST_MODIFIED_FILE = ".github/last_modified_record.json"

def get_top_modified_record(max_retries=3):
    """Get the most recently modified record from MorphoSource using the API"""
    api = MorphoSourceAPI()
    
    for attempt in range(max_retries):
        try:
            # Use API to get the most recently modified record
            api_record = api.get_latest_modified_record(query="X-Ray Computed Tomography")
            
            if not api_record:
                raise ValueError("No records found in API response")
            
            # Normalize the record to match the old scraping format
            normalized = api.normalize_record(api_record)
            
            # Convert to the format expected by the rest of the script
            record = {
                "id": normalized["id"],
                "title": normalized["title"],
                "detail_url": normalized["detail_url"]
            }
            
            # Add metadata fields directly to record (old format)
            for key, value in normalized["metadata"].items():
                record[key] = value
            
            # Debug output
            print(f"Retrieved most recently modified record via API: {record['id']}", file=sys.stderr)
            
            return record
            
        except MorphoSourceTemporarilyUnavailable as e:
            print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                # Longer backoff with jitter
                sleep_time = (5 ** (attempt + 1)) + random.uniform(0, 5)
                print(f"Backing off for {sleep_time:.1f} seconds...", file=sys.stderr)
                time.sleep(sleep_time)
                continue
            
            # On final failure, write to GitHub output and exit gracefully
            write_github_output(False, f"MorphoSource appears to be having issues. Error: {str(e)}")
            sys.exit(0)  # Exit gracefully to prevent GitHub Action failure
        except MorphoSourceAPIError as e:
            print(f"API error (attempt {attempt + 1}/{max_retries}): {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                sleep_time = (5 ** (attempt + 1)) + random.uniform(0, 5)
                print(f"Backing off for {sleep_time:.1f} seconds...", file=sys.stderr)
                time.sleep(sleep_time)
                continue
            
            # On final failure, write to GitHub output and exit gracefully
            write_github_output(False, f"API error: {str(e)}")
            sys.exit(0)

    raise ValueError("Failed to get top modified record after all retries")

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
    try:
        # Get the most recently modified record
        current_record = get_top_modified_record()
        print(f"Current top modified record: {current_record.get('title')}", file=sys.stderr)
        
        # Load the previously saved record
        last_record = load_last_modified_record()
        
        # Check if we need to compare with a recent release
        recent_release_tag = os.environ.get("RECENT_RELEASE_TAG")
        if recent_release_tag:
            print(f"Checking against recent release: {recent_release_tag}", file=sys.stderr)
            try:
                import subprocess
                release_info = subprocess.check_output(
                    ['gh', 'release', 'view', recent_release_tag, '--json', 'body'], 
                    text=True,
                    env=dict(os.environ, GH_TOKEN=os.environ.get("GITHUB_TOKEN", ""))
                )
                import json
                release_body = json.loads(release_info)['body']
                
                # Compare the current record with the recent release
                if compare_with_recent_release(current_record, release_body):
                    print("The modified record is the same as in the recent release, skipping", file=sys.stderr)
                    
                    # Still update our last_modified_record.json if needed
                    if last_record is None or current_record.get('id') != last_record.get('id'):
                        save_last_modified_record(current_record)
                        
                    write_github_output(False, "The modified record is the same as in the recent release")
                    return
            except Exception as e:
                print(f"Error comparing with recent release: {str(e)}", file=sys.stderr)
                # Continue with normal processing if comparison fails
        
        if last_record is None:
            # First time running this script
            print("No previous record found. This is the first run.", file=sys.stderr)
            save_last_modified_record(current_record)
            message = format_release_message(current_record, is_new=False)
            write_github_output(True, message)
        elif current_record.get('id') != last_record.get('id'):
            # Different record ID - a new record has been modified
            print(f"New modified record detected. Old: {last_record.get('id')}, New: {current_record.get('id')}", file=sys.stderr)
            save_last_modified_record(current_record)
            message = format_release_message(current_record, is_new=True)
            write_github_output(True, message)
        else:
            # Same record - no changes
            print("No changes in the most recently modified record.", file=sys.stderr)
            write_github_output(False, "No changes in the most recently modified record.")
            
    except MorphoSourceTemporarilyUnavailable as e:
        print(f"Server Error: {str(e)}", file=sys.stderr)
        write_github_output(False, f"Error: MorphoSource is temporarily unavailable. Please try again later.")
        sys.exit(0)  # Exit gracefully
        
    except Exception as e:
        print(f"Error in main: {str(e)}", file=sys.stderr)
        write_github_output(False, f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main() 