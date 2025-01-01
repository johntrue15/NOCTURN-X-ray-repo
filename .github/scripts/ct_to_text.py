#!/usr/bin/env python3

import sys
import os
import re

try:
    import openai  # or from openai import OpenAI if you have a custom "o1-mini"
except ImportError:
    print("Please install the openai library (or your custom model library).")
    sys.exit(1)

def parse_records_from_body(body):
    """
    Looks for lines like:
      New Record #104236 Title: Endocast [Mesh] [CT]
    Then collects additional fields from the subsequent lines with 'Key: Value' format.
    Returns a list of dicts, each representing a new record.
    """
    record_pattern = re.compile(r'^New Record #(\d+)\s+Title:\s*(.*)$', re.IGNORECASE)
    lines = body.splitlines()
    records = []
    current_record = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = record_pattern.match(line)
        if match:
            # If we already have a record in progress, store it
            if current_record:
                records.append(current_record)
            current_record = {}
            current_record["record_number"] = match.group(1)
            current_record["title"] = match.group(2)
            continue

        # If we see something like 'Object: USNM:HERP:...'
        if ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            current_record[key] = val

    # Add the last record if in progress
    if current_record:
        records.append(current_record)

    return records

def generate_summary(records):
    """
    Stub that simply lists each record found. In real usage, you might call openai API here.
    """
    if not records:
        return "No new records found in this release."

    lines = []
    lines.append("CT to Text Analysis:\n")
    for i, rec in enumerate(records, start=1):
        lines.append(f"Record {i}: # {rec.get('record_number')} - {rec.get('title','N/A')}")
        # Optional: include more data like 'Object', 'Taxonomy', etc.

    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: ct_to_text.py <release_body_file>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    if not os.path.isfile(release_body_file):
        print(f"Error: file '{release_body_file}' not found.")
        sys.exit(1)

    with open(release_body_file, "r", encoding="utf-8") as f:
        body = f.read()

    # Parse records from the release body
    records = parse_records_from_body(body)

    # Generate a textual summary
    summary = generate_summary(records)

    # Print to stdout so the workflow can capture it
    print(summary)

if __name__ == "__main__":
    main()
