#!/usr/bin/env python3
"""
ct_to_text.py

Reads a file containing the release body, parses lines like:
  New Record #XXXX Title: ...
Then calls a model to generate a textual summary focusing on taxonomy.
Prints the summary to stdout for your workflow to capture.
"""

import os
import re
import sys

try:
    from openai import OpenAI
except ImportError:
    print("Error: `openai` library or your custom O1 model is missing.")
    sys.exit(1)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY is not set in environment.")

RE_RECORD_HEADER = re.compile(r'^New Record #(\d+)\s+Title:\s*(.*)$', re.IGNORECASE)

def parse_records_from_body(body: str):
    lines = body.splitlines()
    records = []
    current_record = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = RE_RECORD_HEADER.match(line)
        if match:
            # finalize previous if any
            if current_record:
                records.append(current_record)
            current_record = {}
            current_record["record_number"] = match.group(1)
            current_record["title"] = match.group(2)
            continue

        if ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()

            kl = key.lower()
            if kl.startswith("detail page url"):
                current_record["detail_url"] = val
            elif kl == "object":
                current_record["Object"] = val
            elif kl == "taxonomy":
                current_record["Taxonomy"] = val
            elif kl == "element or part":
                current_record["Element or Part"] = val
            elif kl == "data manager":
                current_record["Data Manager"] = val
            elif kl == "date uploaded":
                current_record["Date Uploaded"] = val
            elif kl == "publication status":
                current_record["Publication Status"] = val
            elif kl == "rights statement":
                current_record["Rights Statement"] = val
            elif kl == "cc license":
                current_record["CC License"] = val

    if current_record:
        records.append(current_record)

    return records

def generate_text_for_records(records):
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY is missing."

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_content = ["Below are new CT records from a Morphosource release:\n"]
    for i, rec in enumerate(records, start=1):
        user_content.append(f"Record {i}:")
        user_content.append(f" - Record Number: {rec.get('record_number','N/A')}")
        user_content.append(f" - Title: {rec.get('title','N/A')}")
        user_content.append(f" - URL: {rec.get('detail_url','N/A')}")
        for field in ["Object","Taxonomy","Element or Part","Data Manager","Date Uploaded",
                      "Publication Status","Rights Statement","CC License"]:
            if field in rec:
                user_content.append(f" - {field}: {rec[field]}")
        user_content.append("")

    user_content.append("You are a scientific writer with expertise in analyzing morphological data. You have received metadata from X-ray computed tomography scans of various biological specimens. Please compose a multi paragraph, one for each record/species, 200-word plain-English description that emphasizes each specimen’s species (taxonomy) and object details. Focus on identifying notable anatomical or morphological features that may be revealed by the CT scanning process. Avoid discussions of copyright or publication status. Make the final description readable for a broad audience, yet scientifically informed. Write with clarity and accuracy, highlighting the significance of the scans for understanding the organism’s structure and potential insights into its biology or evolution.")
    try:
        resp = client.chat.completions.create(
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
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error calling o1-mini model: {e}"

def main():
    if len(sys.argv) < 2:
        print("Usage: ct_to_text.py <release_body_file>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    if not os.path.isfile(release_body_file):
        print(f"File '{release_body_file}' not found.")
        sys.exit(1)

    with open(release_body_file, 'r', encoding='utf-8') as f:
        body = f.read()

    if not body.strip():
        print("No release body found or file is empty.")
        sys.exit(0)

    records = parse_records_from_body(body)
    if not records:
        print("No records found in the release body.")
        sys.exit(0)

    description = generate_text_for_records(records)
    print(description)

if __name__ == "__main__":
    main()
