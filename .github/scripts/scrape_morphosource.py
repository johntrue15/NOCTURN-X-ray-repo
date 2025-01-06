#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup
import time

SEARCH_URL = (
    "https://www.morphosource.org/catalog/media?locale=en"
    "&q=X-Ray+Computed+Tomography&search_field=all_fields"
    "&sort=system_create_dtsi+desc"
)
BASE_URL = "https://www.morphosource.org"
LAST_COUNT_FILE = ".github/last_count.txt"

def get_current_record_count(max_retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(SEARCH_URL, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Debug output
            print(f"Response status code: {response.status_code}")
            print("First 500 characters of response:", response.text[:500])
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Try multiple methods to find the count
            # Method 1: Meta tag
            meta_tag = soup.find("meta", {"name": "totalResults"})
            if meta_tag and meta_tag.get("content"):
                return int(meta_tag["content"])
                
            # Method 2: Search results count text
            results_text = soup.select_one("div.page-links")
            if results_text:
                text = results_text.get_text()
                import re
                if match := re.search(r'(\d+)\s+results?', text):
                    return int(match.group(1))
            
            # Method 3: Count actual results
            results = soup.select("div#search-results li.document.blacklight-media")
            if results:
                return len(results)
                
            if attempt < max_retries - 1:
                time.sleep(5)  # Wait before retry
                continue
                
            raise ValueError("Could not find result count using any method")
            
        except requests.RequestException as e:
            print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            raise

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
    with open(LAST_COUNT_FILE, "w") as f:
        f.write(str(count))

def parse_top_records(n=3):
    """
    Grabs the first n <li class="document blacklight-media"> from the search results
    (descending by creation date). Returns a list of dicts containing relevant metadata.
    """
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    resp = session.get(SEARCH_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    li_list = soup.select("div#search-results li.document.blacklight-media")[:n]
    records = []
    for li in li_list:
        record = {}

        # 1) Title & detail link
        title_el = li.select_one("h3.search-result-title a")
        if title_el:
            record["title"] = title_el.get_text(strip=True)
            record["detail_url"] = BASE_URL + title_el.get("href", "")
        else:
            record["title"] = "No Title"
            record["detail_url"] = None

        # 2) Additional metadata from dt/dd pairs
        metadata_dl = li.select_one("div.metadata dl.dl-horizontal")
        if metadata_dl:
            items = metadata_dl.select("div.index-field-item")
            for item in items:
                dt = item.select_one("dt")
                dd = item.select_one("dd")
                if dt and dd:
                    field_name = dt.get_text(strip=True).rstrip(":")
                    field_value = dd.get_text(strip=True)
                    record[field_name] = field_value

        records.append(record)

    return records

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

    # Example: if old_count=104235 and new_records=1,
    # the new record number is 104236
    # if new_records=3, they are 104236, 104235, 104234 (descending).
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

def main():
    try:
        current_count = get_current_record_count()
        print(f"Current count: {current_count}")  # Debug output
        
        old_count = load_last_count()
        print(f"Old count: {old_count}")  # Debug output
        
        new_records = current_count - old_count
        print(f"New records: {new_records}")  # Debug output

        github_output = os.environ.get("GITHUB_OUTPUT", "")

        if new_records > 0:
            # Only fetch as many records as are new, up to a maximum of 3
            records_to_fetch = min(new_records, 3)
            top_records = parse_top_records(n=records_to_fetch)

            # Update the stored count
            save_last_count(current_count)

            message = format_release_message(new_records, old_count, top_records)

            if github_output:
                with open(github_output, "a") as fh:
                    fh.write("new_data=true\n")
                    fh.write("details<<EOF\n")
                    fh.write(message + "\n")
                    fh.write("EOF\n")
        else:
            if github_output:
                with open(github_output, "a") as fh:
                    fh.write("new_data=false\n")
                    fh.write("details<<EOF\nNo new records found.\nEOF\n")
                    
    except Exception as e:
        print(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()
