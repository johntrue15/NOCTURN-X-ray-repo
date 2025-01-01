#!/usr/bin/env python3
"""
ct_to_text.py

1. Fetches the latest release from GitHub.
2. Parses the release body to find record metadata (matching your known format).
3. Calls the O1-mini model to generate a textual description focusing on taxonomy/object.
"""

import os
import re
import requests

# If you have the new "OpenAI" package for the o1-mini model:
from openai import OpenAI

# In many repos, you'd NOT hardcode your key. We'll illustrate environment variable usage:
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not set. You may need to set it manually.")

# Replace these with your actual GitHub repo owner and repo name
GITHUB_OWNER = "OWNER"
GITHUB_REPO = "REPO"

# Example: "https://api.github.com/repos/OWNER/REPO/releases/latest"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def fetch_latest_release_body(github_token: str = "") -> str:
    """
    Fetch the latest release from GitHub using the GitHub API.
    Returns the release body text.
    If `github_token` is provided, it will be used to authenticate.
    """
    headers = {}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    resp = requests.get(LATEST_RELEASE_URL, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    body = data.get("body", "")
    return body


def parse_records_from_body(body: str):
    """
    Given the release body with lines like:

      A new increase ...
      We found 3 new records (old record value: 104233).

      New Record #104236 Title: Endocast [Mesh] [CT]
      Detail Page URL: https://...
      Object: UMMZ:mammals:172254
      Taxonomy: Hesperoptenus tickelli
      ...

    This function parses out each "New Record #..." block and returns
    a list of dicts with fields: title, detail_url, object, taxonomy, etc.
    """

    # We'll split by blank lines or detect "New Record #"
    lines = body.splitlines()

    records = []
    current_record = {}
    record_number_pattern = re.compile(r"^New Record #(\d+)\s+Title:\s*(.*)$", re.IGNORECASE)

    for line in lines:
        line = line.strip()

        # Detect a new record line:
        match = record_number_pattern.match(line)
        if match:
            # If we have an existing record in progress, append it
            if current_record:
                records.append(current_record)
            current_record = {}
            record_num = match.group(1)
            record_title = match.group(2)
            current_record["record_number"] = record_num
            current_record["title"] = record_title
            continue

        # Check for key-value lines (e.g. "Detail Page URL: https://...")
        if ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            # We'll store them in a way that matches your previous code:
            if key.lower().startswith("detail page url"):
                current_record["detail_url"] = val
            elif key.lower() == "object":
                current_record["Object"] = val
            elif key.lower() == "taxonomy":
                current_record["Taxonomy"] = val
            elif key.lower() == "element or part":
                current_record["Element or Part"] = val
            elif key.lower() == "data manager":
                current_record["Data Manager"] = val
            elif key.lower() == "date uploaded":
                current_record["Date Uploaded"] = val
            elif key.lower() == "publication status":
                current_record["Publication Status"] = val
            elif key.lower() == "rights statement":
                current_record["Rights Statement"] = val
            elif key.lower() == "cc license":
                current_record["CC License"] = val
            # else: ignore lines we don't care about, or store them as needed

    # Append the last record if present
    if current_record:
        records.append(current_record)

    return records


def generate_text_for_records(records):
    """
    Uses the O1-mini model to generate a summary of the provided X-ray CT metadata.
    Based on the snippet you provided.
    """
    if not OPENAI_API_KEY:
        return "Error: No OPENAI_API_KEY set."

    # Initialize the client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Prepare user content
    user_content = ["Below are CT scan records from a recent GitHub Release:\n"]
    for i, rec in enumerate(records, start=1):
        user_content.append(f"Record {i}:")
        record_num = rec.get("record_number", "???")
        title = rec.get("title", "N/A")
        detail_url = rec.get("detail_url", "N/A")
        user_content.append(f" - Record Number: {record_num}")
        user_content.append(f" - Title: {title}")
        user_content.append(f" - URL: {detail_url}")

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
                user_content.append(f" - {key}: {rec[key]}")
        user_content.append("")  # blank line

    user_content.append(
        "Write a concise description focusing on species/taxonomy and object details. "
        "Ignore copyright or publication status."
    )

    # Call the model
    try:
        response = client.chat.completions.create(
            model="o1-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "\n".join(user_content)
                        }
                    ]
                }
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating text: {e}"


def main():
    # We can read a GITHUB_TOKEN from environment if needed for private repos
    github_token = os.environ.get("GITHUB_TOKEN", "")

    # 1. Fetch latest release body
    release_body = fetch_latest_release_body(github_token=github_token)
    if not release_body:
        print("No release body found. Exiting.")
        return

    # 2. Parse the records from the release body
    records = parse_records_from_body(release_body)
    if not records:
        print("No records found in the release body. Exiting.")
        return

    # 3. Generate text
    description = generate_text_for_records(records)
    print("\n--- Generated Description ---\n")
    print(description)


if __name__ == "__main__":
    main()
