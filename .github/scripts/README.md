# Scripts

This folder contains Python scripts used in the automation of the MorphoSource scraper workflow.

---

## Scripts

### 1. `scrape_morphosource.py`
- **Purpose**: Scrapes MorphoSource for new “X-Ray Computed Tomography” records.
- **Key Functions**:
  - Fetches the total count of records from the `<meta name="totalResults">` tag.
  - Compares the current total to the previously stored value in `last_count.txt`.
  - If new records are found, parses details from the first new record.
  - Outputs relevant data for use in the GitHub Actions workflow.

---

## Usage

You typically won’t run these scripts directly in production. Instead, they are executed by the GitHub Actions workflow (`parse_morphosource.yml`). However, if you want to run a script locally:

1. **Install Python 3** (if not already available).
2. **Install Dependencies**:
   ```bash
   pip install requests beautifulsoup4
   ```

### Run the script

```bash
python scrape_morphosource.py
```

## Customization

Feel free to modify these scripts to fit your needs:

- **Change the data extracted** (e.g., collect object type, taxonomy, date uploaded).  
- **Update output format** (e.g., JSON instead of text).  
- **Integrate with other services** (e.g., post to Slack, update a database).  

> **Note**: If you make changes, you should also update the workflow file (`.github/workflows/parse_morphosource.yml`) accordingly.
