#!/usr/bin/env python3
import os
import requests
import openai
from bs4 import BeautifulSoup

SEARCH_URL = (
    "https://www.morphosource.org/catalog/media?locale=en"
    "&q=X-Ray+Computed+Tomography&search_field=all_fields"
    "&sort=system_create_dtsi+desc"
)
BASE_URL = "https://www.morphosource.org"

def parse_top_records(n=3):
    """
    Grab the first n records from MorphoSource X-Ray CT search results.
    Return a list of metadata dicts that we can feed to OpenAI.
    """
    resp = requests.get(SEARCH_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    li_list = soup.select("div#search-results li.document.blacklight-media")[:n]
    records = []
    for li in li_list:
        record = {}
        title_el = li.select_one("h3.search-result-title a")
        if title_el:
            record["title"] = title_el.get_text(strip=True)
            record["detail_url"] = BASE_URL + title_el.get("href", "")
        else:
            record["title"] = "N/A"
            record["detail_url"] = None

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
    Calls OpenAI API with a prompt that includes the metadata
    and requests a textual description of the CT data.
    """
    # Build a single prompt string or do multiple calls per record.
    # Here, we show a single call that includes data about each record.
    prompt_lines = []
    prompt_lines.append("You are a scientific assistant. Provide a short textual description for these X-ray CT records based on the metadata given:")
    prompt_lines.append("")

    for i, rec in enumerate(records, start=1):
        prompt_lines.append(f"Record {i}:")
        prompt_lines.append(f" Title: {rec.get('title', 'N/A')}")
        prompt_lines.append(f" URL: {rec.get('detail_url', 'N/A')}")
        for key in ["Object", "Taxonomy", "Element or Part", "Data Manager", "Date Uploaded", "Publication Status", "Rights Statement", "CC License"]:
            if key in rec:
                prompt_lines.append(f" {key}: {rec[key]}")
        prompt_lines.append("")

    prompt_lines.append("Generate a concise, plain-English summary describing the significance of these CT scans and what they represent, focusing on the species name or taxonomy if possible.")
    prompt = "\n".join(prompt_lines)

    # OpenAI API call
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OPENAI_API_KEY not set in environment.")

    response = openai.Completion.create(
        model="text-davinci-003",   # or "gpt-3.5-turbo" with Chat API
        prompt=prompt,
        max_tokens=300,
        temperature=0.7,
    )
    # Extract the text from the response
    text_output = response.choices[0].text.strip()
    return text_output

def main():
    records = parse_top_records(n=3)
    if not records:
        description = "No records found for X-Ray Computed Tomography."
    else:
        description = generate_text_for_records(records)

    # Output the final description to GITHUB_OUTPUT
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write("description<<EOF\n")
            fh.write(description + "\n")
            fh.write("EOF\n")
    else:
        print(description)

if __name__ == "__main__":
    main()
