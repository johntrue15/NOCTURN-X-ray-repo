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
BASE_URL = "https://www.morphosource.org"
LAST_COUNT_FILE = "last_count.txt"

def get_current_record_count():
    """
    Scrape MorphoSource to find how many "X-ray Computed Tomography" records exist.
    Uses the <meta name="totalResults" content="..."> tag.
    """
    response = requests.get(SEARCH_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the meta tag with name="totalResults"
    results_meta = soup.find("meta", {"name": "totalResults"})
    if not results_meta or not results_meta.get("content"):
        raise ValueError("Could not find the 'totalResults' meta tag on the page.")

    total_count = int(results_meta["content"])
    return total_count

def parse_new_records():
    """
    Parses the search results page for the first record, then loads that record’s detail page.
    Returns a string summary of the new record details.
    """
    session = requests.Session()

    # 1) Load the main search results page
    resp = session.get(SEARCH_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 2) Find the first li with class "document blacklight-media"
    first_li = soup.select_one("div#search-results li.document.blacklight-media")
    if not first_li:
        return "No first record found."

    # 3) Extract the link to the detail page
    #    The snippet shows <h3 class="search-result-title"><a href="/concern/media/000699076?locale=en">Title</a></h3>
    title_el = first_li.select_one("h3.search-result-title a")
    if not title_el:
        return "First record has no title link."

    first_title = title_el.get_text(strip=True)
    relative_url = title_el.get("href", "")
    detail_url = BASE_URL + relative_url

    # 4) Load the detail page to get more info
    detail_resp = session.get(detail_url)
    detail_resp.raise_for_status()
    detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

    # Example: parse the <title> ... </title> from the detail page
    # You could also parse any other details from that page’s HTML structure.
    page_title = detail_soup.title.string if detail_soup.title else "No detail page title found"

    # Build a short summary
    summary = (
        f"**First Record Title (from search results):** {first_title}\n"
        f"**Detail Page URL:** {detail_url}\n"
        f"**Detail Page <title>:** {page_title}\n"
    )
    return summary

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

def main():
    current_count = get_current_record_count()
    last_count = load_last_count()

    if current_count > last_count:
        # There's new data
        new_records_count = current_count - last_count

        # Parse the first record details (or more if you wish)
        details = parse_new_records()

        # Update the local text file so we don’t repeatedly fire for the same records
        save_last_count(current_count)

        # Print GitHub Actions outputs
        print("::set-output name=new_data::true")
        # Include how many new records, plus the first record’s summary
        message = f"We found {new_records_count} new records.\n\n{details}"
        print(f"::set-output name=details::{message}")

    else:
        # No new data
        print("::set-output name=new_data::false")
        print("::set-output name=details::No new records found.")

if __name__ == "__main__":
    main()
