# Pre-Bot-Era Scripts

This folder contains the original scripts that used web scraping to collect data from MorphoSource.org before they implemented bot detection.

## Why These Scripts Were Archived

MorphoSource.org added bot detection mechanisms that prevented our GitHub Actions from scraping data using BeautifulSoup and requests. As a result, we've migrated to using the official MorphoSource REST API.

## Archived Scripts

- `scrape_morphosource.py` - Original scraping script
- `daily.py` - Daily check using web scraping
- `monthly.py` - Monthly collection using web scraping
- `check_modified_morphosource.py` - Modified record check using web scraping

## Migration to API

The new API-based scripts are located in `.github/scripts/` and use the `MORPHOSOURCE_API_KEY` secret to authenticate with the MorphoSource REST API.

API Documentation: https://morphosource.stoplight.io/docs/morphosource-api/rm6bqdolcidct-morpho-source-rest-api

## Historical Note

These scripts worked reliably until approximately early 2025 when MorphoSource implemented Cloudflare bot protection or similar anti-scraping measures.
