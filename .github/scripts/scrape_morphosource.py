#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup

# Constants
SEARCH_URL = "https://www.morphosource.org/concern/media?utf8=%E2%9C%93&q=X-ray+Computed+Tomography&search_field=all_fields"
LAST_COUNT_FILE = "last_count.txt"

def get_current_record_count():
    """
    Scrape MorphoSource to find how many "X-ray Computed Tomography" records exist.
    """
    response = requests.get(SEARCH_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # This is just an example. Adjust to match the actual structure of the site:
    # Often sites show something like: "1 - 25 of 999 results" or "999 results found".
    # You need to inspect the actual HTML to locate the correct tag or text. 
    results_info = soup.find("span", class_="search-pagination__count")  # Hypothetical
    if not results_info:
        # If we cannot find the results count element, handle gracefully:
        raise ValueError("Could not find the results count element on the page.")

    # This might be text like: "1 - 25 of 101 results"
    # You need to parse it or extract the last numeric piece.
    text = results_info.get_text(strip=True)
    # Let's assume the text ends with something like " of 101 results"
    # Very naive approach: split by space and take the second to last entry:
    parts = text.split()
    total_count_str = parts[-2]  # e.g. "101"
    total_count = int(total_count_str)
    return total_count

def load_last_count():
    """
    Load the previously recorded number of records from file.
    """
    if not os.path.exists(LAST_COUNT_FILE):
        return 0
    with open(LAST_COUNT_FILE, "r") as f:
        try:
            return int(f.read().strip())
        except ValueError:
            return 0

def save_last_count(count):
    """
    Save the current record count to file.
    """
    with open(LAST_COUNT_FILE, "w") as f:
        f.write(str(count))

def parse_new_records():
    """
    Optionally parse new records from the page to get details. For demonstration,
    let's just return some placeholder text. In a real scenario, you'd parse each
    record's metadata, e.g. title, ID, link, etc.
    """
    # Example: Just returning a placeholder. 
    # You would adapt BeautifulSoup code to gather each new record’s data.
    return "List of new record details here (adapt as needed)."

def main():
    current_count = get_current_record_count()
    last_count = load_last_count()

    if current_count > last_count:
        # There's new data
        new_records_count = current_count - last_count
        details = parse_new_records()

        # Update the local text file
        save_last_count(current_count)

        # Print GitHub Actions outputs
        print(f"::set-output name=new_data::true")
        print(f"::set-output name=details::We found {new_records_count} new records.\n{details}")
    else:
        # No new data
        print(f"::set-output name=new_data::false")
        print(f"::set-output name=details::No new records found.")

if __name__ == "__main__":
    main()
