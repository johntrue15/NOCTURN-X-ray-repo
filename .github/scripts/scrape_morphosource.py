#!/usr/bin/env python3
import os
import sys
from morphosource_api import MorphoSourceAPI, MorphoSourceAPIError, MorphoSourceTemporarilyUnavailable

LAST_COUNT_FILE = ".github/last_count.txt"

def get_current_record_count(max_retries=3):
    """Get the current total count of X-ray CT records using the API"""
    api = MorphoSourceAPI()
    
    for attempt in range(max_retries):
        try:
            # Use API to get total count
            count = api.get_total_count(query="X-Ray Computed Tomography")
            
            # Debug output
            print(f"API returned count: {count}", file=sys.stderr)
            return count
            
        except MorphoSourceTemporarilyUnavailable as e:
            print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                import time
                import random
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
                import time
                import random
                sleep_time = (5 ** (attempt + 1)) + random.uniform(0, 5)
                print(f"Backing off for {sleep_time:.1f} seconds...", file=sys.stderr)
                time.sleep(sleep_time)
                continue
            
            # On final failure, write to GitHub output and exit gracefully
            write_github_output(False, f"API error: {str(e)}")
            sys.exit(0)

    raise ValueError("Failed to get record count after all retries")

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

def parse_top_records(n=3):
    """
    Get the first n records (descending by creation date) using the API.
    Returns a list of dicts containing relevant metadata.
    """
    api = MorphoSourceAPI()
    
    try:
        # Use API to get latest records
        api_records = api.get_latest_records(n=n, query="X-Ray Computed Tomography")
        
        # Normalize records to match the old scraping format
        records = []
        for api_record in api_records:
            normalized = api.normalize_record(api_record)
            
            # Convert to the format expected by the release message
            record = {
                "title": normalized["title"],
                "detail_url": normalized["detail_url"]
            }
            
            # Add metadata fields directly to record (old format)
            for key, value in normalized["metadata"].items():
                record[key] = value
            
            records.append(record)
        
        # Debug output
        print(f"Retrieved {len(records)} records via API", file=sys.stderr)
        
        return records

    except MorphoSourceAPIError as e:
        print(f"API error while fetching records: {e}", file=sys.stderr)
        write_github_output(False, f"MorphoSource API error while fetching records. Error: {str(e)}")
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
    try:
        current_count = get_current_record_count()
        print(f"Current count: {current_count}", file=sys.stderr)
        
        old_count = load_last_count()
        print(f"Old count: {old_count}", file=sys.stderr)
        
        new_records = current_count - old_count
        print(f"New records: {new_records}", file=sys.stderr)

        if new_records != 0:  # Handle both positive and negative changes
            records_to_fetch = min(abs(new_records), 3)  # Use abs() to handle negative
            top_records = parse_top_records(n=records_to_fetch)
            save_last_count(current_count)  # Always save the current count
            message = format_release_message(new_records, old_count, top_records)
            write_github_output(True, message)
        else:
            write_github_output(False, "No changes in record count.")
            
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
