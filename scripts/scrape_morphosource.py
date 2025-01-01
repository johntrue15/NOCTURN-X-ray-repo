#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup

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
    by looking at <meta name='totalResults' content='...'>.
    """
    response = requests.get(SEARCH_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    meta_tag = soup.find("meta", {"name": "totalResults"})
    if not meta_tag or not meta_tag.get("content"):
        raise ValueError("Could not find the 'totalResults' meta tag on the page.")
    return int(meta_tag["content"])

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
    Parse the first n records from the search results page.
    Returns a list of dicts, each containing relevant metadata.
    """
    session = requests.Session()
    resp = session.get(SEARCH_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Grab the first n LI elements with class="document blacklight-media"
    all_li = soup.select("div#search-results li.document.blacklight-media")
    top_li = all_li[:n]

    results = []
    for li in top_li:
        record = {}

        # 1) Record Title and Detail Page URL
        title_el = li.select_one("h3.search-result-title a")
        if title_el:
            record["title"] = title_el.get_text(strip=True)
            record["detail_url"] = BASE_URL + title_el.get("href", "")
        else:
            record["title"] = "No Title"
            record["detail_url"] = None

        # 2) Now parse the metadata fields inside <dl class="dl-horizontal">
        metadata_dl = li.select_one("div.metadata dl.dl-horizontal")
        if metadata_dl:
            items = metadata_dl.select("div.index-field-item")
            for item in items:
                dt = item.select_one("dt")
                dd = item.select_one("dd")
                if not dt or not dd:
                    continue
                field_name = dt.get_text(strip=True).rstrip(":")
                field_value = dd.get_text(strip=True)
                record[field_name] = field_value
        else:
            pass

        results.append(record)

    return results

def format_release_message(new_records, old_count, records):
    """
    Build the multiline release body with:
    - A header about how many new records (plus old count).
    - A block for each record in reverse order.
    """
    lines = []
    lines.append("A new increase in X-ray Computed Tomography records was found on MorphoSource.")
    lines.append("")
    lines.append(f"We found {new_records} new records (old record value: {old_count}).")
    lines.append("")

    # If old_count = 13323 and new_records = 3,
    # we want the first record to be #13326, then #13325, then #13324
    # i.e. old_count + new_records - (i-1)
    # We'll parse records in normal order but label them in descending order.
    for i, r in enumerate(records, start=1):
        record_number = old_count + new_records - (i - 1)
        # The highest number for the first record in the list
        # (since i = 1 for the "first" parsed record).
        lines.append(f"New Record #{record_number} Title: {r.get('title', 'N/A')}")
        lines.append(f"Detail Page URL: {r.get('detail_url', 'N/A')}")

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
            if key in r:
                lines.append(f"{key}: {r[key]}")
        lines.append("")  # blank line after each record

    return "\n".join(lines)

def main():
    current_count = get_current_record_count()
    old_count = load_last_count()
    new_records = current_count - old_count

    github_output = os.environ.get("GITHUB_OUTPUT", "")

    if new_records > 0:
        top_records = parse_top_records(n=3)
        save_last_count(current_count)

        message = format_release_message(new_records, old_count, top_records)

        if github_output:
            with open(github_output, "a") as fh:
                fh.write("new_data=true\n")
                fh.write("details<<EOF\n")
                fh.write(message + "\n")
                fh.write("EOF\n")
        else:
            print("Warning: GITHUB_OUTPUT not found.")
    else:
        if github_output:
            with open(github_output, "a") as fh:
                fh.write("new_data=false\n")
                fh.write("details<<EOF\nNo new records found.\nEOF\n")

if __name__ == "__main__":
    main()
