#!/usr/bin/env python3
import sys, os, re

try:
    import openai
except ImportError:
    print("Please install openai or your custom O1-mini model library.")
    sys.exit(1)

def parse_records_from_body(body):
    # Example: look for lines "New Record #XXXX Title: something"
    # We'll do a simple parse. Adjust to your needs.
    record_pattern = re.compile(r'^New Record #(\d+)\s+Title:\s*(.*)$', re.IGNORECASE)
    lines = body.splitlines()
    records = []
    current_record = {}

    for line in lines:
        line=line.strip()
        if not line:
            continue
        match = record_pattern.match(line)
        if match:
            # If we had a record in progress, add it
            if current_record:
                records.append(current_record)
            current_record = {}
            current_record["record_number"] = match.group(1)
            current_record["title"] = match.group(2)
        elif ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            current_record[key] = val
    if current_record:
        records.append(current_record)
    return records

def generate_text_for_records(records):
    """
    Here you'd call openai API or your custom logic to generate a summary.
    For demo, we'll just build a short string.
    """
    if not records:
        return "No new records to summarize."

    summary_lines = []
    summary_lines.append("**CT to Text Analysis**\n")

    for i, rec in enumerate(records, start=1):
        summary_lines.append(f"Record {i}: #{rec.get('record_number','???')} - {rec.get('title','N/A')}")
        # Possibly incorporate data like 'Object', 'Taxonomy', etc. from rec
    return "\n".join(summary_lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: ct_to_text.py <release_body_file>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    if not os.path.isfile(release_body_file):
        print(f"Release body file '{release_body_file}' not found.")
        sys.exit(1)

    with open(release_body_file, "r", encoding="utf-8") as f:
        body = f.read()

    # Parse the "New Record" lines
    records = parse_records_from_body(body)
    # Summarize
    summary = generate_text_for_records(records)
    print(summary)

if __name__ == "__main__":
    main()
