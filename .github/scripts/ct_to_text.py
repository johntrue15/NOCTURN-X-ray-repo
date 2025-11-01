#!/usr/bin/env python3

import os
import re
import sys
import json

try:
    from openai import OpenAI
except ImportError:
    print("Error: The 'openai' library (or your custom O1-mini package) is missing.")
    sys.exit(1)

# We assume you set OPENAI_API_KEY in your GitHub Actions environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Regex to detect lines like "New Record #104236 Title: Endocast [Mesh] [CT]"
RE_RECORD_HEADER = re.compile(r'^New Record #(\d+)\s+Title:\s*(.*)$', re.IGNORECASE)

def extract_json_from_body(body: str):
    """
    Extracts JSON data from a MorphoSource API release body.
    The JSON is typically in a markdown code block like:
    ```json
    { ... }
    ```
    
    Returns the parsed JSON dict or None if not found.
    """
    # Look for JSON code block
    json_start = body.find("```json")
    if json_start == -1:
        return None
    
    # Find the end of the code block
    json_end = body.find("```", json_start + 7)
    if json_end == -1:
        return None
    
    # Extract the JSON content
    json_str = body[json_start + 7:json_end].strip()
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse JSON from release body: {e}", file=sys.stderr)
        return None

def is_api_release(body: str):
    """Check if this is a MorphoSource API release (has JSON data)"""
    return "### Full API JSON for latest record" in body

def parse_api_record(body: str):
    """
    Parses a MorphoSource API release body to extract record information.
    
    Returns a dict with record information or None if parsing fails.
    """
    json_data = extract_json_from_body(body)
    if not json_data:
        return None
    
    # Extract metadata from the release body (outside JSON)
    lines = body.splitlines()
    record_id = None
    record_title = None
    detail_url = None
    
    for line in lines:
        line = line.strip()
        if line.startswith("- **id:**"):
            # Extract ID from: - **id:** `000620417`
            record_id = line.split("`")[1] if "`" in line else None
        elif line.startswith("- **title:**"):
            # Extract title from: - **title:** Head, Mouthparts...
            record_title = line.split("**title:**", 1)[1].strip()
        elif line.startswith("- **detail page:**"):
            # Extract URL from: - **detail page:** https://...
            detail_url = line.split("**detail page:**", 1)[1].strip()
    
    # Build a record dict similar to the old format
    # Handle case where json_data["id"] might be a list
    json_id = json_data.get("id", "N/A")
    if isinstance(json_id, list):
        json_id = json_id[0] if json_id else "N/A"
    
    record = {
        "record_number": record_id or json_id,
        "title": record_title or json_data.get("title_tesim", ["N/A"])[0] if isinstance(json_data.get("title_tesim"), list) else "N/A",
        "detail_url": detail_url,
        "api_data": json_data  # Include the full API JSON for analysis
    }
    
    return record

def parse_records_from_body(body: str):
    """
    Parses the release body, looking for lines like:
      New Record #XXXX Title: ...
    Then captures subsequent lines of the form 'Key: Value'
    
    Also handles API releases with JSON data.
    
    Returns a list of dicts, each representing a record's data.
    Skips records with invalid record numbers.
    """
    # Check if this is an API release with JSON
    if is_api_release(body):
        api_record = parse_api_record(body)
        if api_record and api_record.get("record_number", "").replace("N/A", ""):
            return [api_record]
        return []
    
    # Original parsing logic for traditional releases
    records = []
    lines = body.splitlines()
    current_record = {}

    for line in lines:
        line = line.strip()
        # Skip empty lines
        if not line:
            continue

        # See if this line starts a new record
        match = RE_RECORD_HEADER.match(line)
        if match:
            # If we already have a record in progress, validate and finalize it
            if current_record:
                # Only add records that have valid record numbers (not N/A)
                record_num = current_record.get("record_number", "")
                if record_num.isdigit():  # Only add if record_number is a valid number
                    records.append(current_record)
            
            # Start new record
            record_num = match.group(1)
            if record_num.lower() != "n/a" and record_num.isdigit():
                current_record = {
                    "record_number": record_num,
                    "title": match.group(2)
                }
            else:
                current_record = {}  # Skip invalid records
            continue

        # Only process key-value pairs if we have a valid record
        if current_record and ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            kl = key.lower()

            # We can store known fields in canonical keys
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

            # Also store the raw key-value in case we need it
            current_record[key] = val

    # After the loop, validate and add final record if needed
    if current_record:
        record_num = current_record.get("record_number", "")
        if record_num.isdigit():
            records.append(current_record)

    return records

def generate_text_for_records(records):
    """
    Calls the gpt-4o-mini model to generate descriptions for valid records.
    Handles both traditional records and API records with JSON data.
    """
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY is missing."

    # If no valid records found, provide clear message
    if not records:
        return "No valid records found to summarize. The release may contain malformed or incomplete data."

    # Initialize the client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Build a user prompt that includes each record's metadata
    user_content = ["Below are new CT records from a MorphoSource release:\n"]
    for rec in records:
        record_num = rec.get("record_number", "N/A")
        user_content.append(f"Record #{record_num}:")
        user_content.append(f" - Title: {rec.get('title','N/A')}")
        user_content.append(f" - URL: {rec.get('detail_url','N/A')}")

        # Check if this is an API record with JSON data
        if "api_data" in rec:
            user_content.append("\nAPI Data:")
            api_data = rec["api_data"]
            
            # Extract relevant fields from API JSON
            for key, value in api_data.items():
                # Skip internal/technical fields
                if key.startswith("system_") or key.startswith("has_") or key.startswith("is"):
                    continue
                if key in ["id", "accessControl_ssim", "depositor_ssim", "depositor_tesim"]:
                    continue
                
                # Format the value nicely
                if isinstance(value, list):
                    if value:
                        value_str = ", ".join(str(v) for v in value)
                        user_content.append(f" - {key}: {value_str}")
                elif value:
                    user_content.append(f" - {key}: {value}")
        else:
            # Traditional record format
            for field in [
                "Object",
                "Taxonomy",
                "Element or Part",
                "Data Manager",
                "Date Uploaded",
                "Publication Status",
                "Rights Statement",
                "CC License",
            ]:
                if field in rec:
                    user_content.append(f" - {field}: {rec[field]}")
        
        user_content.append("")  # Blank line separator

    # Add instructions for a ~200-word multi-paragraph summary
    user_content.append(
        "You are a scientific writer with expertise in analyzing morphological data. "
        "You have received metadata from X-ray computed tomography scans of various biological specimens. "
        "Please compose a multi-paragraph, one for each record/species, ~200-word plain-English description that "
        "emphasizes each specimen's species (taxonomy) and object details. Focus on identifying notable anatomical "
        "or morphological features that may be revealed by the CT scanning process. Avoid discussions of copyright "
        "or publication status. Make the final description readable for a broad audience, yet scientifically informed. "
        "Highlight the significance of the scans for understanding the organism's structure and potential insights "
        "into its biology or evolution."
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
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
        return f"Error calling gpt-4o-mini model: {e}"

def main():
    """
    1. Reads a single argument <release_body_file>
    2. Parses it for "New Record #..." blocks
    3. Calls generate_text_for_records(records) to produce a multi-paragraph text
    4. Prints the final text to stdout
    """
    if len(sys.argv) < 2:
        print("Usage: ct_to_text.py <release_body_file>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    if not os.path.isfile(release_body_file):
        print(f"File '{release_body_file}' not found.")
        sys.exit(1)

    with open(release_body_file, "r", encoding="utf-8") as f:
        body = f.read()

    # Parse records
    records = parse_records_from_body(body)
    
    # Build output with record metadata
    output_parts = []
    
    # Add metadata header for each record
    for rec in records:
        record_num = rec.get("record_number", "N/A")
        title = rec.get("title", "N/A")
        detail_url = rec.get("detail_url", "N/A")
        
        output_parts.append(f"## Record #{record_num}")
        output_parts.append(f"**Title:** {title}")
        if detail_url and detail_url != "N/A":
            output_parts.append(f"**Detail Page:** {detail_url}")
        output_parts.append("")
    
    # Generate final text using the gpt-4o-mini model
    description = generate_text_for_records(records)
    output_parts.append("## Analysis")
    output_parts.append(description)
    
    print("\n".join(output_parts))

if __name__ == "__main__":
    main()
