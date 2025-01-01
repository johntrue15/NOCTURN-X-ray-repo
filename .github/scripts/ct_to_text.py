#!/usr/bin/env python3
"""
ct_to_text.py

Scrapes the top N X-ray Computed Tomography records from MorphoSource,
then calls the OpenAI ChatCompletion API to generate a short textual
description based on the metadata. Outputs the result to GITHUB_OUTPUT
so that subsequent workflow steps can access it as 'steps.[id].outputs.description'.
"""

import os
import requests
import openai
from bs4 import BeautifulSoup

# Constants
SEARCH_URL = (
    "https://www.morphosource.org/catalog/media?locale=en"
    "&q=X-Ray+Computed+Tomography&search_field=all_fields"
    "&sort=system_create_dtsi+desc"
)
BASE_URL = "https://www.morphosource.org"

def parse_top_records(n=3):
    """
    Scrapes the first n <li> elements from MorphoSource's search results for "X-Ray Computed Tomography".
    Returns a list of dicts, each containing relevant metadata like title, detail URL, object, taxonomy, etc.
    """
    resp = requests.get(SEARCH_URL)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Grab up to n results from the search page
    li_list = soup.select("div#search-results li.document.blacklight-media")[:n]
    records = []

    for li in li_list:
        record = {}

        # Title and detail URL
        title_el = li.select_one("h3.search-result-title a")
        if title_el:
            record["title"] = title_el.get_text(strip=True)
            record["detail_url"] = BASE_URL + title_el.get("href", "")
        else:
            record["title"] = "N/A"
            record["detail_url"] = None

        # Additional metadata from <dl class="dl-horizontal">
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

def generate_text_for_records(records):
    """
    Uses OpenAI's ChatCompletion API to generate a concise textual description
    for the given list of record metadata.
    """
    # Ensure we have the API key
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OPENAI_API_KEY not set in environment.")

    # Build a 'system' message to instruct the assistant
    system_message = {
        "role": "system",
        "content": (
            "You are a scientific assistant with knowledge of biology and zoology. "
            "Provide a concise description for these X-ray Computed Tomography records."
        ),
    }

    # Build a 'user' message that contains the record metadata
    user_content_lines = []
    user_content_lines.append("Below are several CT scan records from MorphoSource.\n")
    for i, rec in enumerate(records, start=1):
        user_content_lines.append(f"Record {i}:")
        user_content_lines.append(f" Title: {rec.get('title', 'N/A')}")
        user_content_lines.append(f" URL: {rec.get('detail_url', 'N/A')}")
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
                user_content_lines.append(f" {key}: {rec[key]}")
        user_content_lines.append("")  # Blank line separating each record
    user_content_lines.append(
        "Please summarize these scans, focusing on the species or taxonomy and any notable details."
    )
    user_message = {"role": "user", "content": "\n".join(user_content_lines)}

    # Create the ChatCompletion request
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[system_message, user_message],
        max_tokens=600,
        temperature=0.7,
    )

    # Extract the assistant's response
    return response.choices[0].message["content"].strip()

def main():
    # Scrape top 3 records
    records = parse_top_records(n=3)
    if not records:
        description = "No CT records found on MorphoSource."
    else:
        description = generate_text_for_records(records)

    # Write final text to GITHUB_OUTPUT so the workflow can reference 'steps.[id].outputs.description'
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write("description<<EOF\n")
            fh.write(description + "\n")
            fh.write("EOF\n")
    else:
        # Fallback: just print it
        print(description)

if __name__ == "__main__":
    main()
