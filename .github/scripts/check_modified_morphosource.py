#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup
import time
import sys
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import random
import json

# URL sorted by modification date (descending)
SEARCH_URL = (
    "https://www.morphosource.org/catalog/media?locale=en"
    "&q=X-Ray+Computed+Tomography&search_field=all_fields"
    "&sort=system_modified_dtsi+desc"
)
BASE_URL = "https://www.morphosource.org"
LAST_MODIFIED_FILE = ".github/last_modified_record.json"

class MorphoSourceTemporarilyUnavailable(Exception):
    """Custom exception for when MorphoSource is temporarily unavailable"""
    pass

def create_session():
    """Create a requests session with retry strategy"""
    session = requests.Session()
    
    # More conservative retry strategy
    retry_strategy = Retry(
        total=3,  # total number of retries
        backoff_factor=5,  # will wait 5, 10, 20 seconds between retries
        status_forcelist=[429, 500, 502, 503, 504],  # status codes to retry on
        allowed_methods=["GET"],  # only retry GET requests
        respect_retry_after_header=True,  # honor server's retry-after header
        raise_on_status=True
    )
    
    # Create adapter with shorter timeouts
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=1,  # reduce concurrent connections
        pool_maxsize=1
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def check_for_server_error(response_text, response_status):
    """Enhanced check for server issues"""
    # Check for specific error page
    if "MorphoSource temporarily unavailable (500)" in response_text:
        raise MorphoSourceTemporarilyUnavailable("MorphoSource is temporarily unavailable (500 error)")
    
    # Check for very slow responses (indicated by minimal content)
    if len(response_text.strip()) < 100:
        raise MorphoSourceTemporarilyUnavailable("MorphoSource returned minimal content - possible server issues")
    
    # Check for error status codes
    if response_status >= 400:
        raise MorphoSourceTemporarilyUnavailable(f"MorphoSource returned error status {response_status}")

def get_top_modified_record(max_retries=3):
    """Get the most recently modified record from MorphoSource"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    session = create_session()
    
    for attempt in range(max_retries):
        try:
            # Shorter initial timeout
            response = session.get(
                SEARCH_URL, 
                headers=headers, 
                timeout=(5, 30)  # (connect timeout, read timeout)
            )
            response.raise_for_status()
            
            # Debug output
            print(f"Response status code: {response.status_code}", file=sys.stderr)
            print(f"Response size: {len(response.text)} bytes", file=sys.stderr)
            print("First 500 characters of response:", response.text[:500], file=sys.stderr)
            
            # Enhanced error checking
            check_for_server_error(response.text, response.status_code)
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Get the first (most recently modified) record
            record_element = soup.select_one("div#search-results li.document.blacklight-media")
            
            if not record_element:
                raise ValueError("No records found in search results")
                
            record = {}
            
            # 1) Title & detail link
            title_el = record_element.select_one("h3.search-result-title a")
            if title_el:
                record["title"] = title_el.get_text(strip=True)
                record["detail_url"] = BASE_URL + title_el.get("href", "")
                # Extract ID from URL
                import re
                if match := re.search(r'/media/(\d+)', record["detail_url"]):
                    record["id"] = match.group(1)
                else:
                    record["id"] = "unknown"
            else:
                record["title"] = "No Title"
                record["detail_url"] = None
                record["id"] = "unknown"

            # 2) Additional metadata from dt/dd pairs
            metadata_dl = record_element.select_one("div.metadata dl.dl-horizontal")
            if metadata_dl:
                items = metadata_dl.select("div.index-field-item")
                for item in items:
                    dt = item.select_one("dt")
                    dd = item.select_one("dd")
                    if dt and dd:
                        field_name = dt.get_text(strip=True).rstrip(":")
                        field_value = dd.get_text(strip=True)
                        record[field_name] = field_value
            
            return record
            
        except (requests.RequestException, MorphoSourceTemporarilyUnavailable) as e:
            print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                # Longer backoff with more jitter
                sleep_time = (5 ** (attempt + 1)) + random.uniform(0, 5)
                print(f"Backing off for {sleep_time:.1f} seconds...", file=sys.stderr)
                time.sleep(sleep_time)
                continue
            
            # On final failure, write to GitHub output and exit gracefully
            write_github_output(False, f"MorphoSource appears to be having issues. Error: {str(e)}")
            sys.exit(0)  # Exit gracefully to prevent GitHub Action failure

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

def main():
    try:
        # Get the most recently modified record
        current_record = get_top_modified_record()
        print(f"Current top modified record: {current_record.get('title')}", file=sys.stderr)
        
        # Load the previously saved record
        last_record = load_last_modified_record()
        
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