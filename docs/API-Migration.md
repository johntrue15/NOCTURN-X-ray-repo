# MorphoSource API Migration Guide

## Overview

This repository has been migrated from web scraping to using the official MorphoSource REST API. This change was necessary due to bot detection mechanisms implemented by MorphoSource.org.

## Why the Migration?

Previously, this repository used BeautifulSoup to scrape data from MorphoSource.org. However, the website implemented bot detection (likely Cloudflare or similar), which prevented our GitHub Actions from successfully collecting data. The official API provides a more reliable and respectful way to access MorphoSource data.

## API Documentation

The official MorphoSource API documentation is available at:
https://morphosource.stoplight.io/docs/morphosource-api/rm6bqdolcidct-morpho-source-rest-api

## Setup Requirements

### 1. Obtain a MorphoSource API Key

To use the MorphoSource API, you need an API key:

1. Create an account or log in to [MorphoSource.org](https://www.morphosource.org)
2. Navigate to your account settings
3. Generate an API key
4. Store it securely

### 2. Configure GitHub Secret

Add the API key as a GitHub repository secret:

1. Go to your repository's Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `MORPHOSOURCE_API_KEY`
4. Value: Your MorphoSource API key
5. Click "Add secret"

## Architecture Changes

### New Components

#### 1. API Client Library (`morphosource_api.py`)

A dedicated Python client for interacting with the MorphoSource API:

```python
from morphosource_api import MorphoSourceAPIClient

# Initialize client
api_client = MorphoSourceAPIClient(api_key)

# Search for X-ray CT records
results = api_client.search_media(
    query="X-Ray Computed Tomography",
    page=1,
    per_page=100
)

# Get all records
all_records = api_client.get_all_xray_ct_records()

# Get recent records
recent = api_client.get_recent_records(count=10)

# Get modified records
modified = api_client.get_modified_records(count=10)
```

#### 2. Updated Scripts

All scripts have been updated to use the API client:

- **scrape_morphosource.py**: Checks for new records using API
- **daily.py**: Daily data collection using API
- **monthly.py**: Monthly full collection using API
- **check_modified_morphosource.py**: Tracks modified records using API

### Data Format Compatibility

The API client includes a `parse_record_to_legacy_format()` method that converts API responses to match the old scraping format, ensuring backward compatibility with existing code that processes the data.

## Workflow Updates

All GitHub Actions workflows have been updated to pass the `MORPHOSOURCE_API_KEY` environment variable:

```yaml
- name: Run Script
  env:
    MORPHOSOURCE_API_KEY: ${{ secrets.MORPHOSOURCE_API_KEY }}
  run: python .github/scripts/script_name.py
```

### Updated Workflows

1. **daily.yml** - Daily MorphoSource Check
2. **monthly.yml** - Monthly MorphoSource Collection
3. **parse_morphosource.yml** - Parse MorphoSource Data
4. **modified_morphosource.yml** - Check Modified MorphoSource Records

## API Features

### Rate Limiting

The API client includes built-in rate limiting (0.5-second delays between requests) to be respectful to the MorphoSource API servers.

### Error Handling

Comprehensive error handling with exponential backoff for failed requests:

```python
# Automatic retries with backoff
result = api_client._make_request(
    endpoint='catalog/media',
    params={'page': 1},
    max_retries=3
)
```

### Logging

All API operations are logged for debugging and monitoring:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Benefits of API Migration

1. **Reliability**: No more bot detection issues
2. **Performance**: API is optimized for programmatic access
3. **Maintainability**: Official API means fewer breaking changes
4. **Compliance**: Using the official API respects MorphoSource's terms of service
5. **Features**: Access to additional API-only features

## Archived Code

The original web scraping code has been preserved in the `Pre-Bot-Era` directory for historical reference and potential fallback if needed.

See: [Pre-Bot-Era/README.md](../Pre-Bot-Era/README.md)

## Testing

To test the API integration locally:

```bash
# Set environment variable
export MORPHOSOURCE_API_KEY="your-api-key-here"

# Test the scraper
python .github/scripts/scrape_morphosource.py

# Test daily collection
python .github/scripts/daily.py --data-dir ./test_data --output-dir ./test_output

# Test monthly collection
python .github/scripts/monthly.py --output-dir ./test_monthly
```

## Troubleshooting

### API Key Not Found

If you see "MORPHOSOURCE_API_KEY environment variable not set":

1. Verify the secret is configured in GitHub
2. Check the workflow file includes the `env:` section
3. Ensure the secret name matches exactly: `MORPHOSOURCE_API_KEY`

### API Authentication Errors

If you see authentication errors:

1. Verify your API key is valid
2. Check if the API key has expired
3. Ensure the API key has the necessary permissions

### API Response Format Changes

If the API response format changes:

1. Check the official API documentation
2. Update field mappings in `morphosource_api.py`
3. Update the `parse_record_to_legacy_format()` method

## Future Enhancements

Potential improvements for the API integration:

1. **Caching**: Implement response caching to reduce API calls
2. **Batch Operations**: Use batch API endpoints if available
3. **Webhooks**: Subscribe to MorphoSource webhooks for real-time updates
4. **Advanced Filtering**: Utilize API filtering capabilities
5. **Pagination Optimization**: Implement concurrent page fetching

## Support

For issues related to:

- **API Integration**: Open an issue in this repository
- **MorphoSource API**: Contact MorphoSource support
- **API Key**: Check MorphoSource account settings

## References

- [MorphoSource API Documentation](https://morphosource.stoplight.io/docs/morphosource-api/rm6bqdolcidct-morpho-source-rest-api)
- [Pre-Bot-Era Archive](../Pre-Bot-Era/README.md)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
