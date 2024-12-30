#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup

# Constants
SEARCH_URL = (
    "https://www.morphosource.org/catalog/media?locale=en"
    "&q=X-Ray+Computed+Tomography&search_field=all_fields"
    "&sort=system_create_dtsi+desc"
)
LAST_COUNT_FILE = "last_count.txt"

def get_current_record_count():
    """
    Scrape MorphoSource to find how many "X-ray Computed Tomography" records exist.
    Looks for the <meta name="totalResults" content="..."> tag in the page.
    """
    response = requests.get(SEARCH_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # The <meta name="totalResults" content="104233"> gives us the total count
    results_meta = soup.find("meta", {"name": "totalResults"})
    if not results_meta or not results_meta.get("content"):
        raise ValueError("Could not find the 'totalResults' meta tag on the page.")

    total_count = int(results_meta["content"])
    return total_count

def load_last_count():
    """
    Load the previously recorded number of records from file.
    Returns 0 if file doesn't exist or contains invalid data.
    """
    if not os.path.exists(LAST_COUNT_FILE):
        return 0
    try:
        with open(LAST_COUNT_FILE, "r") as f:
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
    Optionally parse new records from the page to get details.
    For demonstration, just return a placeholder string.
    In a real scenario, you'd parse actual new entries.
    """
    # Placeholder. You could fetch the page again and gather detailed info
    # for each newly added record, then build a string or JSON summary.
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
        print("::set-output name=new_data::true")
        print(f"::set-output name=details::Found {new_records_count} new records.\n{details}")
    else:
        # No new data
        print("::set-output name=new_data::false")
        print("::set-output name=details::No new records found.")

if __name__ == "__main__":
    main()
