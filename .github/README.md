# MorphoSource X-Ray Computed Tomography Scraper

This repository contains a GitHub Actions workflow (`parse_morphosource.yml`) and a Python script (`scrape_morphosource.py`) that automatically:

- Scrapes MorphoSource for new records containing “X-Ray Computed Tomography.”  
- Runs on a schedule every 12 hours (or manually, on demand).  
- Parses the first record’s details (title, link, and detail-page title).  
- Creates or updates a GitHub Release if any new records are found.

---

## Table of Contents
1. [Overview](#overview)  
2. [How It Works](#how-it-works)  
3. [Project Structure](#project-structure)  
4. [Setup](#setup)  
5. [Usage](#usage)  
6. [Customization](#customization)

---

## Overview

### Script: `scrape_morphosource.py`
- Uses [Requests](https://pypi.org/project/requests/) and [Beautiful Soup](https://pypi.org/project/beautifulsoup4/) to fetch MorphoSource’s X-Ray CT data.  
- Locates the `<meta name="totalResults">` tag to determine how many total records currently exist.  
- Compares that number to a locally stored `last_count.txt` value.  
- If new records exist, it parses the first record’s detail link, fetches that page, and returns a short summary.

### Workflow: `.github/workflows/parse_morphosource.yml`
- Runs on a cron schedule every 12 hours.  
- Checks out the repository code, installs dependencies, and executes `scrape_morphosource.py`.  
- If new records are found, creates or updates a GitHub Release named “MorphoSource Updates” with details from the script’s output.

---

## How It Works

1. **Search Page**: The script hits the URL:
    ```bash
    https://www.morphosource.org/catalog/media?locale=en&q=X-Ray+Computed+Tomography&search_field=all_fields&sort=system_create_dtsi+desc
    ```
2. **Count Extraction**: It looks for:
    ```html
    <meta name="totalResults" content="...">
    ```
    to determine the total number of X-ray CT records.
3. **Comparison**: It reads a local file, `last_count.txt`. If `totalResults` > `last_count`, the script recognizes new records.
4. **First Record Parsing**: It finds the first search result `<li>` block and extracts:  
   - Title link  
   - Detail page link  
   - Loads that detail page to parse the `<title>...</title>` or other metadata.
5. **Outputs**: The script saves the new count to `last_count.txt`, then prints its results to the GitHub Actions Environment Files so that subsequent workflow steps can read the text.
6. **GitHub Release**: If new records exist, the workflow calls `actions/create-release@v1` to create or update a release in your repository. The body of the release includes:  
   - Number of new records  
   - First record’s title and detail page link

---

## Project Structure

```graphql
.
├─ .github/
│  ├─ workflows/
│  │  └─ parse_morphosource.yml  # The GitHub Actions workflow
│  └─ scripts/
│     └─ scrape_morphosource.py  # The Python scraper script
├─ last_count.txt                # Stores the last known total count of records
└─ README.md                     # This README
