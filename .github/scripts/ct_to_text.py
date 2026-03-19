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

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

RE_RECORD_HEADER = re.compile(r'^New Record #(\d+)\s+Title:\s*(.*)$', re.IGNORECASE)


def extract_all_json_blocks(body: str) -> list[dict]:
    """
    Extract ALL ```json ... ``` code blocks from a release body.
    Returns a list of parsed dicts (one per block).
    """
    results = []
    search_start = 0
    while True:
        json_start = body.find("```json", search_start)
        if json_start == -1:
            break
        json_end = body.find("```", json_start + 7)
        if json_end == -1:
            break
        json_str = body[json_start + 7:json_end].strip()
        try:
            results.append(json.loads(json_str))
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse JSON block at offset {json_start}: {e}", file=sys.stderr)
        search_start = json_end + 3
    return results


def extract_json_from_body(body: str):
    """Extract the first JSON block (backwards-compatible)."""
    blocks = extract_all_json_blocks(body)
    return blocks[0] if blocks else None


def is_api_release(body: str):
    """Check if this is a MorphoSource API release (has JSON data)."""
    return "### Full API JSON for" in body


def is_multi_record_release(body: str):
    """Check if the release contains multiple records."""
    return "Records included in this release:" in body


def parse_single_api_record(body: str, json_data: dict) -> dict | None:
    """
    Parse metadata surrounding a single JSON block and combine with the
    parsed JSON to build a record dict.
    """
    lines = body.splitlines()
    record_id = None
    record_title = None
    detail_url = None

    for line in lines:
        line = line.strip()
        if line.startswith("- **id:**"):
            record_id = line.split("`")[1] if "`" in line else None
        elif line.startswith("- **title:**"):
            record_title = line.split("**title:**", 1)[1].strip()
        elif line.startswith("- **detail page:**"):
            detail_url = line.split("**detail page:**", 1)[1].strip()

    json_id = json_data.get("id", "N/A")
    if isinstance(json_id, list):
        json_id = json_id[0] if json_id else "N/A"

    json_title = None
    for key in ("title", "title_tesim", "title_ssi"):
        val = json_data.get(key)
        if isinstance(val, list) and val:
            json_title = val[0]
            break
        elif isinstance(val, str) and val:
            json_title = val
            break

    record = {
        "record_number": record_id or json_id,
        "title": json_title or record_title or "N/A",
        "detail_url": detail_url,
        "api_data": json_data,
    }

    return record


def parse_multi_record_release(body: str) -> list[dict]:
    """
    Parse a release body that contains multiple record sections, each with
    its own JSON block.  Sections are delimited by '## Record N:' headers.
    """
    json_blocks = extract_all_json_blocks(body)
    if not json_blocks:
        return []

    # Split body into per-record sections using the ## Record header
    section_pattern = re.compile(r'^## Record \d+:', re.MULTILINE)
    section_starts = [m.start() for m in section_pattern.finditer(body)]

    records = []
    for i, json_data in enumerate(json_blocks):
        # Get the section text surrounding this JSON block
        if i < len(section_starts):
            start = section_starts[i]
            end = section_starts[i + 1] if i + 1 < len(section_starts) else len(body)
            section_text = body[start:end]
        else:
            section_text = body

        record_id = None
        record_title = None
        detail_url = None
        visibility = None

        for line in section_text.splitlines():
            line = line.strip()
            if line.startswith("- **id:**"):
                record_id = line.split("`")[1] if "`" in line else None
            elif line.startswith("- **title:**"):
                record_title = line.split("**title:**", 1)[1].strip()
            elif line.startswith("- **detail page:**"):
                detail_url = line.split("**detail page:**", 1)[1].strip()
            elif line.startswith("- **visibility:**"):
                visibility = line.split("**visibility:**", 1)[1].strip()

        json_id = json_data.get("id", "N/A")
        if isinstance(json_id, list):
            json_id = json_id[0] if json_id else "N/A"

        json_title = None
        for key in ("title", "title_tesim", "title_ssi"):
            val = json_data.get(key)
            if isinstance(val, list) and val:
                json_title = val[0]
                break
            elif isinstance(val, str) and val:
                json_title = val
                break

        record = {
            "record_number": record_id or json_id,
            "title": json_title or record_title or "N/A",
            "detail_url": detail_url,
            "visibility": visibility,
            "api_data": json_data,
        }

        rn = record.get("record_number", "")
        if rn and rn != "N/A":
            records.append(record)

    return records


def parse_records_from_body(body: str):
    """
    Parses the release body, handling:
      1. Multi-record API releases (## Record 1: ... ## Record 2: ...)
      2. Single-record API releases (### Full API JSON for latest record)
      3. Legacy releases (New Record #XXXX Title: ...)

    Returns a list of dicts, each representing a record.
    """
    # Multi-record API release
    if is_multi_record_release(body):
        records = parse_multi_record_release(body)
        if records:
            return records

    # Single-record API release
    if is_api_release(body):
        json_data = extract_json_from_body(body)
        if json_data:
            api_record = parse_single_api_record(body, json_data)
            if api_record and api_record.get("record_number", "").replace("N/A", ""):
                return [api_record]
        return []

    # Legacy format: "New Record #XXXX Title: ..."
    records = []
    lines = body.splitlines()
    current_record = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = RE_RECORD_HEADER.match(line)
        if match:
            if current_record:
                record_num = current_record.get("record_number", "")
                if record_num.isdigit():
                    records.append(current_record)

            record_num = match.group(1)
            if record_num.lower() != "n/a" and record_num.isdigit():
                current_record = {
                    "record_number": record_num,
                    "title": match.group(2)
                }
            else:
                current_record = {}
            continue

        if current_record and ":" in line:
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

            current_record[key] = val

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

    if not records:
        return "No valid records found to summarize. The release may contain malformed or incomplete data."

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_content = [f"Below are {len(records)} new CT record(s) from a MorphoSource release:\n"]
    for rec in records:
        record_num = rec.get("record_number", "N/A")
        user_content.append(f"Record #{record_num}:")
        user_content.append(f" - Title: {rec.get('title','N/A')}")
        user_content.append(f" - URL: {rec.get('detail_url','N/A')}")

        if "api_data" in rec:
            user_content.append("\nAPI Data:")
            api_data = rec["api_data"]

            for key, value in api_data.items():
                if key.startswith("system_") or key.startswith("has_") or key.startswith("is"):
                    continue
                if key in ["id", "accessControl_ssim", "depositor_ssim", "depositor_tesim"]:
                    continue

                if isinstance(value, list):
                    if value:
                        value_str = ", ".join(str(v) for v in value)
                        user_content.append(f" - {key}: {value_str}")
                elif value:
                    user_content.append(f" - {key}: {value}")
        else:
            for field in [
                "Object", "Taxonomy", "Element or Part", "Data Manager",
                "Date Uploaded", "Publication Status", "Rights Statement", "CC License",
            ]:
                if field in rec:
                    user_content.append(f" - {field}: {rec[field]}")

        user_content.append("")

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
    if len(sys.argv) < 2:
        print("Usage: ct_to_text.py <release_body_file>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    if not os.path.isfile(release_body_file):
        print(f"File '{release_body_file}' not found.")
        sys.exit(1)

    with open(release_body_file, "r", encoding="utf-8") as f:
        body = f.read()

    records = parse_records_from_body(body)

    print(f"Parsed {len(records)} record(s) from release body", file=sys.stderr)

    output_parts = []

    for rec in records:
        record_num = rec.get("record_number", "N/A")
        title = rec.get("title", "N/A")
        detail_url = rec.get("detail_url", "N/A")

        output_parts.append(f"## Record #{record_num}")
        output_parts.append(f"**Title:** {title}")
        if detail_url and detail_url != "N/A":
            output_parts.append(f"**Detail Page:** {detail_url}")

        # Include media ID explicitly for downstream scoring
        if "api_data" in rec:
            media_id = rec["api_data"].get("id", "")
            if isinstance(media_id, list):
                media_id = media_id[0] if media_id else ""
            if media_id:
                output_parts.append(f"**Media ID:** {media_id}")

            vis = rec["api_data"].get("visibility_ssi") or rec["api_data"].get("visibility")
            if isinstance(vis, list):
                vis = vis[0] if vis else ""
            if vis:
                output_parts.append(f"**Visibility:** {vis}")

        output_parts.append("")

    description = generate_text_for_records(records)
    output_parts.append("## Analysis")
    output_parts.append(description)

    print("\n".join(output_parts))


if __name__ == "__main__":
    main()
