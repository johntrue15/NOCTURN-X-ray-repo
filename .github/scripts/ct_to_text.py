#!/usr/bin/env python3

import sys
import os
import re

try:
    import openai
except ImportError:
    # If you're not using the openai library, you can comment this out or replace with your own custom library.
    print("Note: `openai` library not found. If you plan to call GPT APIs, install it via pip.")
    # We won't exit(1) here in case you're using local summarization logic.

def parse_records_from_body(body: str):
    """
    Parse lines like:
      New Record #104236 Title: Endocast [Mesh] [CT]
    And gather subsequent lines such as:
      Object: ...
      Taxonomy: ...
      Element or Part: ...
      etc.
    
    Returns a list of dicts, each representing one "New Record".
    """
    records = []
    
    # Regex to detect "New Record #XXXX Title: Something"
    new_record_pattern = re.compile(r'^New Record #(\d+)\s+Title:\s*(.*)$', re.IGNORECASE)

    lines = body.splitlines()
    current_record = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if line indicates a new record
        match = new_record_pattern.match(line)
        if match:
            # If there's an unfinished record, store it
            if current_record:
                records.append(current_record)
            current_record = {}
            current_record["record_number"] = match.group(1)
            current_record["title"] = match.group(2)
            continue

        # Otherwise, if the line looks like "Key: Value"
        if ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            current_record[key] = val

    # If there's a last record still in progress
    if current_record:
        records.append(current_record)

    return records

def generate_summary(records):
    """
    Generates a simple textual summary of the records found.
    If you want to integrate an OpenAI API call, do it here.
    """
    if not records:
        return "No new records found in this release."

    summary_lines = []
    summary_lines.append("CT to Text Analysis:\n")
    for i, rec in enumerate(records, start=1):
        record_number = rec.get("record_number", "???")
        title = rec.get("title", "N/A")

        summary_lines.append(f"Record {i} - #{record_number}: {title}")
        # Optionally, include more fields like 'Object', 'Taxonomy', etc.:
        # object_val = rec.get("Object")
        # if object_val:
        #     summary_lines.append(f"  Object: {object_val}")
        # ...and so on.

    return "\n".join(summary_lines)

def main():
    """
    Main entry point:
      1) Reads a file name from sys.argv[1] (the 'release_body.txt').
      2) Parses it for new morphosource records.
      3) Generates a text summary.
      4) Prints it to stdout.
    """
    if len(sys.argv) < 2:
        print("Usage: ct_to_text.py <release_body_file>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    if not os.path.isfile(release_body_file):
        print(f"Error: file '{release_body_file}' not found.")
        sys.exit(1)

    # Read the entire release body
    with open(release_body_file, "r", encoding="utf-8") as f:
        body_text = f.read()

    # 1) Parse the release body
    records = parse_records_from_body(body_text)

    # 2) Generate a summary (stub or real AI logic)
    summary = generate_summary(records)

    # 3) Print the result to stdout so the GitHub Actions workflow can capture it
    print(summary)

if __name__ == "__main__":
    main()
