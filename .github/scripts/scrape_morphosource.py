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
LAST_COUNT_FILE = ".github/last_count.txt"

def get_current_record_count():
    """
    Scrape MorphoSource to find how many X-ray CT records exist,
    by looking at <meta name="totalResults" content="...">
    """
    response = requests.get(SEARCH_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    meta_tag = soup.find("meta", {"name": "totalResults"})
    if not meta_tag or not meta_tag.get("content"):
        raise ValueError("Could not find the 'totalResults' meta tag on the page.")
    return int(meta_tag["content"])

def parse_new_records():
    """
    Example logic:
      1) Load the same search page
      2) Find the first record block
      3) Extract the link, then request that detail page
      4) Return a summary of the data
    """
    session = requests.Session()
    resp = session.get(SEARCH_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find first <li> with class="document blacklight-media"
    first_li = soup.select_one("div#search-results li.document.blacklight-media")
    if not first_li:
        return "No first record found."

    # Extract the link from the <h3> tag
    title_el = first_li.select_one("h3.search-result-title a")
    if not title_el:
        return "No title link for first record."

    first_title = title_el.get_text(strip=True)
    detail_url = BASE_URL + title_el.get("href", "")

    # Load the detail page
    detail_resp = session.get(detail_url)
    detail_resp.raise_for_status()
    detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

    # Example: grab <title> from detail page
    detail_page_title = detail_soup.title.string if detail_soup.title else "No detail page title"

    # Build a multi-line summary
    summary = (
        f"**First Record Title (from search results):** {first_title}\n"
        f"**Detail Page URL:** {detail_url}\n"
        f"**Detail Page <title>:** {detail_page_title}\n"
    )
    return summary

def load_last_count():
    """
    Load the previously recorded count from file.
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

    new_records = current_count - last_count
    github_output = os.environ.get("GITHUB_OUTPUT")  # GitHub sets this env var

    if new_records > 0:
        # Parse more info about the new records (if desired)
        details = parse_new_records()

        # Save the new count
        save_last_count(current_count)

        # If we have the GitHub output file, write keys to it
        if github_output:
            with open(github_output, "a") as fh:
                fh.write("new_data=true\n")
                # For multi-line content, use '<<EOF' syntax
                fh.write("details<<EOF\n")
                fh.write(f"We found {new_records} new records.\n\n{details}\n")
                fh.write("EOF\n")
        else:
            print("Warning: GITHUB_OUTPUT not found; cannot set step outputs.")
    else:
        # No new data
        if github_output:
            with open(github_output, "a") as fh:
                fh.write("new_data=false\n")
                fh.write("details<<EOF\nNo new records found.\nEOF\n")
        else:
            print("Warning: GITHUB_OUTPUT not found; cannot set step outputs.")

if __name__ == "__main__":
    main()
