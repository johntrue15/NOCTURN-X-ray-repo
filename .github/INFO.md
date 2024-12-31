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
```

**parse_morphosource.yml**  
Defines when and how the workflow runs.

**scrape_morphosource.py**  
The script that scrapes MorphoSource and outputs data.

**last_count.txt**  
Gets created or updated automatically—tracks how many records we last saw.

---

## Setup

1. **Clone/Download** this repository to your local machine or fork it on GitHub.  
2. **Install Python 3** (if you’re running locally).  
3. **Install Dependencies**: The script needs `requests` and `beautifulsoup4`. You can install these via:
   ```bash
   pip install requests beautifulsoup4

### Configure a Token (Optional)
By default, the workflow uses the built-in `GITHUB_TOKEN` (provided by GitHub Actions).  
If you want to use a custom token (e.g., `MY_GITHUB_TOKEN`), set it as a repository secret and update the workflow accordingly.

---

## Usage

### Automatic (Scheduled)
By default, the workflow is scheduled (`cron: "0 */12 * * *"`) to run every 12 hours.  
This means you don’t have to do anything—GitHub Actions will run the checks automatically and update the release when new records are found.

### Manual (On Demand)
You can manually run the workflow from GitHub’s Actions tab:

1. Go to **Actions** in your repository.  
2. Select the “Parse MorphoSource Data” workflow.  
3. Click **“Run workflow.”**

The script will run, check for new records, and update (or create) the release if there’s an increase.

---

## Customization

1. **Change the Cron**: Modify `cron: "0 */12 * * *"` in `.github/workflows/parse_morphosource.yml` to suit your schedule.  
2. **Scrape More Details**: In `scrape_morphosource.py`, you can expand `parse_new_records()` to gather more fields (e.g., Date Uploaded, Object, Taxonomy). Incorporate them into the final output string.  
3. **Different Release Behavior**:
   - If you’d prefer a new release each time, change the `tag_name` or release naming logic (e.g., append timestamps).  
   - If you’d rather store data in a JSON file, see [`actions/upload-artifact`](https://github.com/actions/upload-artifact).
