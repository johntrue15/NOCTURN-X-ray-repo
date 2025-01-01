#!/usr/bin/env python3
"""
ct_to_text.py

1. Reads a file containing the release body (e.g., 'release_body.txt'), which has lines like:
   New Record #104236 Title: Endocast [Mesh] [CT]
   Detail Page URL: ...
   Object: ...
   Taxonomy: ...
2. Parses these lines into a list of "record" dicts.
3. Calls the "o1-mini" model (via openai) to summarize them, focusing on species/taxonomy.
4. Prints the summary to stdout.
"""

import os
import re
import sys

# Import your special "OpenAI" with the "o1-mini" model support
try:
    from openai import OpenAI
except ImportError:
    print("Error: `openai` library or your custom O1 model is not installed. Please install.")
    sys.exit(1)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Regex to detect lines like "New Record #104236 Title: ..."
RE_RECORD_HEADER = re.compile(r'^New Record #(\d+)\s+Title:\s*(.*)$', re.IGNORECASE)

def parse_records_from_body(body: str):
    """
    Looks for lines like:
      New Record #XXXX Title: something
      Detail Page URL: ...
      Object: ...
      Taxonomy: ...
      ...
    Returns a list of dicts with keys:
      {
        "record_number": ...,
        "title": ...,
        "detail_url": ...,
        "Object": ...,
        "Taxonomy": ...,
        ...
      }
    """
    lines = body.splitlines()
    records = []
    current_record = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue  # skip blank lines

        match = RE_RECORD_HEADER.match(line)
        if match:
            # If we already have a record in progress, finalize it
            if current_record:
                records.append(current_record)
            current_record = {}
            current_record["record_number"] = match.group(1)
            current_record["title"] = match.group(2)
            continue

        # If line has "Key: Value"
        if ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()

            klower = key.lower()
            if klower.startswith("detail page url"):
                current_record["detail_url"] = val
            elif klower == "object":
                current_record["Object"] = val
            elif klower == "taxonomy":
                current_record["Taxonomy"] = val
            elif klower == "element or part":
                current_record["Element or Part"] = val
            elif klower == "data manager":
                current_record["Data Manager"] = val
            elif klower == "date uploaded":
                current_record["Date Uploaded"] = val
            elif klower == "publication status":
                current_record["Publication Status"] = val
            elif klower == "rights statement":
                current_record["Rights Statement"] = val
            elif klower == "cc license":
                current_record["CC License"] = val
            # else ignore or store if you want

    # Add last record if present
    if current_record:
        records.append(current_record)

    return records

def generate_text_for_records(records):
    """
    Calls the 'o1-mini' model to generate a summary focusing on
    species/taxonomy and ignoring irrelevant fields.
    """
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY is not set."

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_content = ["Below are new X-ray CT records from a Morphosource release:\n"]
    for i, rec in enumerate(records, start=1):
        record_num = rec.get("record_number", "N/A")
        title = rec.get("title", "N/A")
        detail_url = rec.get("detail_url", "N/A")
        
        user_content.append(f"Record {i}:")
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
        "You are a scientific writer with expertise in analyzing morphological data. You have received metadata from X-ray computed tomography scans of various biological specimens. Please compose a three paragraph 250-word plain-English description that emphasizes each specimen’s species (taxonomy) and object details. Focus on identifying notable anatomical or morphological features that may be revealed by the CT scanning process. Avoid discussions of copyright or publication status. Make the final description readable for a broad audience, yet scientifically informed. Write with clarity and accuracy, highlighting the significance of the scans for understanding the organism’s structure and potential insights into its biology or evolution. Add useful information about the species and its typical size, weight, conservation status, etc. "
        "ignoring any copyright statuses."
    )

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
        return f"Error calling o1-mini model: {e}"

def main():
    if len(sys.argv) < 2:
        print("Usage: ct_to_text.py <release_body_file>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    if not os.path.isfile(release_body_file):
        print(f"File '{release_body_file}' does not exist.")
        sys.exit(1)

    with open(release_body_file, "r", encoding="utf-8") as f:
        release_body = f.read()

    if not release_body.strip():
        print("No release body found or file is empty.")
        sys.exit(0)

    # 1. Parse records from the release body
    records = parse_records_from_body(release_body)
    if not records:
        print("No records found in release body.")
        sys.exit(0)

    # 2. Generate text from the O1-mini model
    description = generate_text_for_records(records)

    # 3. Print to stdout so the workflow can capture it
    print(description)

if __name__ == "__main__":
    import os
    main()
