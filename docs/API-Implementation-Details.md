# API Implementation Details

This document provides technical details about the implementation changes made during the migration from web scraping to the MorphoSource API.

## Overview of Changes

All scripts that previously used BeautifulSoup and requests to scrape MorphoSource have been refactored to use the official MorphoSource REST API.

## Core Components

### 1. MorphoSource API Client (`morphosource_api.py`)

**Purpose**: Centralized API client that handles all communication with the MorphoSource API.

**Key Features**:
- Session management with authentication headers
- Automatic retry logic with exponential backoff
- Rate limiting to respect API servers
- Logging for debugging
- Backward compatibility through format conversion

**Main Methods**:

```python
# Search for media records
search_media(query, sort, page, per_page)

# Get specific media by ID
get_media_by_id(media_id)

# Get all X-ray CT records
get_all_xray_ct_records(max_pages, progress_callback)

# Get recent records
get_recent_records(count)

# Get modified records
get_modified_records(since, count)

# Convert API format to legacy format
parse_record_to_legacy_format(api_record)
```

## Script Changes

### 2. scrape_morphosource.py

**Before**: 
- Used BeautifulSoup to parse HTML
- Made HTTP requests with custom retry logic
- Parsed HTML structure to extract record counts and details

**After**:
- Uses `MorphoSourceAPIClient` for all operations
- Calls `get_current_record_count()` via API
- Calls `parse_top_records()` using `get_recent_records()` API method
- Converts API responses to legacy format for compatibility

**Key Changes**:
```python
# Old approach
def get_current_record_count():
    response = session.get(SEARCH_URL, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    meta_tag = soup.find("meta", {"name": "totalResults"})
    return int(meta_tag["content"])

# New approach
def get_current_record_count(api_client):
    result = api_client.search_media(page=1, per_page=1)
    total_count = result.get('meta', {}).get('total', 0)
    return total_count
```

### 3. daily.py

**Before**:
- Initialized with base URL
- Used requests to fetch pages
- Parsed HTML with BeautifulSoup

**After**:
- Initialized with `MorphoSourceAPIClient` instance
- Uses API methods to fetch records
- Converts API records to legacy format

**Key Changes**:
```python
# Old approach
class DailyMorphoSourceExtractor:
    def __init__(self, base_url: str, data_dir: str = 'data'):
        self.base_url = base_url
        # ...
    
    def get_all_records(self, latest_stored_id: str = None):
        url = f"{self.base_url}&page={page}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Parse HTML...

# New approach
class DailyMorphoSourceExtractor:
    def __init__(self, api_client: MorphoSourceAPIClient, data_dir: str = 'data'):
        self.api_client = api_client
        # ...
    
    def get_all_records(self, latest_stored_id: str = None):
        result = self.api_client.search_media(page=page, per_page=100)
        api_records = result.get('data', result.get('results', []))
        for api_record in api_records:
            record = self.api_client.parse_record_to_legacy_format(api_record)
            # Process record...
```

### 4. monthly.py

**Before**:
- Used requests to fetch all pages sequentially
- Parsed each page with BeautifulSoup
- Extracted records from HTML structure

**After**:
- Uses `get_all_xray_ct_records()` API method
- Includes progress callback for monitoring
- Converts API records to legacy format

**Key Changes**:
```python
# Old approach
def collect_all_records(self):
    while True:
        url = f"{self.base_url}&page={page}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        records = soup.find_all('div', class_='search-result-wrapper')
        for record_elem in records:
            record = self.parse_record(record_elem)
            # Process record...

# New approach
def collect_all_records(self):
    def progress_callback(page, total_pages, records_so_far):
        self.logger.info(f"Page: {page}/{total_pages}, Records: {records_so_far}")
    
    api_records = self.api_client.get_all_xray_ct_records(
        progress_callback=progress_callback
    )
    for api_record in api_records:
        record = self.api_client.parse_record_to_legacy_format(api_record)
        # Process record...
```

### 5. check_modified_morphosource.py

**Before**:
- Searched for modified records by sorting HTML results
- Parsed first result from HTML

**After**:
- Uses `get_modified_records()` API method
- Gets records sorted by modification date from API

**Key Changes**:
```python
# Old approach
def get_top_modified_record():
    response = session.get(SEARCH_URL_MODIFIED, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    record_element = soup.select_one("div#search-results li.document")
    # Parse HTML structure...

# New approach
def get_top_modified_record(api_client):
    modified_records = api_client.get_modified_records(count=1)
    api_record = modified_records[0]
    record = {
        "title": api_record.get('title'),
        "detail_url": f"https://www.morphosource.org/concern/media/{api_record.get('id')}",
        "id": api_record.get('id')
    }
    # Map metadata fields...
```

## Workflow Integration

All workflow files have been updated to pass the `MORPHOSOURCE_API_KEY` environment variable:

```yaml
- name: Run Script
  env:
    MORPHOSOURCE_API_KEY: ${{ secrets.MORPHOSOURCE_API_KEY }}
  run: python .github/scripts/script_name.py
```

### Updated Workflows:
1. `daily.yml` - Daily MorphoSource Check
2. `monthly.yml` - Monthly MorphoSource Collection
3. `parse_morphosource.yml` - Parse MorphoSource Data
4. `modified_morphosource.yml` - Check Modified Records

## Data Format Compatibility

To maintain backward compatibility, the API client converts API responses to match the old scraping format:

### Legacy Format (from scraping):
```json
{
  "title": "Specimen Title",
  "url": "https://www.morphosource.org/concern/media/000123456",
  "id": "000123456",
  "metadata": {
    "Object": "specimen_id",
    "Taxonomy": "Species name",
    "Element or Part": "tooth",
    "Data Manager": "Name",
    "Date Uploaded": "01/01/2025",
    "Publication Status": "Published",
    "Rights Statement": "...",
    "CC License": "CC BY 4.0"
  },
  "scraped_date": "2025-01-01T00:00:00"
}
```

### API Response Format:
```json
{
  "id": "000123456",
  "title": "Specimen Title",
  "object_id": "specimen_id",
  "taxonomy": "Species name",
  "element": "tooth",
  "data_manager": "Name",
  "date_uploaded": "2025-01-01",
  "publication_status": "Published",
  "rights_statement": "...",
  "cc_license": "CC BY 4.0"
}
```

The `parse_record_to_legacy_format()` method handles this conversion automatically.

## Error Handling

### Old Approach:
```python
try:
    response = session.get(url)
    response.raise_for_status()
    check_for_server_error(response.text, response.status_code)
except requests.RequestException as e:
    # Handle error
```

### New Approach:
```python
try:
    result = api_client.search_media(page=1)
    # Process result
except Exception as e:
    logger.error(f"API error: {e}")
    # Handle error
```

The API client handles retries and backoff internally.

## Rate Limiting

**Old Approach**: Manual `time.sleep()` calls
```python
time.sleep(2)  # Wait between requests
```

**New Approach**: Built into API client
```python
# Automatic 0.5s delay between requests in get_all_xray_ct_records()
time.sleep(0.5)
```

## Logging

**Old Approach**: Print to stderr
```python
print(f"Fetching page {page}", file=sys.stderr)
```

**New Approach**: Proper logging
```python
logger.info(f"Fetching page {page}")
```

## Testing

A test suite has been added to verify the implementation:

```bash
python .github/scripts/test_api_client.py
```

Tests verify:
- API client can be imported
- API client can be initialized
- All required methods exist
- All scripts import the API client

## Benefits Summary

1. **Reliability**: No more bot detection or HTML parsing issues
2. **Performance**: API is faster and more efficient
3. **Maintainability**: API changes are versioned and documented
4. **Testability**: API client can be unit tested
5. **Compatibility**: Legacy format conversion ensures existing code works

## Migration Checklist

For anyone implementing similar changes:

- [x] Create API client library
- [x] Update scripts to use API client
- [x] Convert API responses to legacy format
- [x] Update workflows to pass API key
- [x] Add error handling and logging
- [x] Add rate limiting
- [x] Create tests
- [x] Document changes
- [x] Archive old code
- [ ] Configure API key in GitHub secrets
- [ ] Test with actual API

## Future Improvements

Potential enhancements:

1. **Caching**: Add response caching to reduce API calls
2. **Batch Operations**: Implement batch fetching if API supports it
3. **Webhooks**: Subscribe to real-time updates if available
4. **Pagination Optimization**: Implement concurrent page fetching
5. **Mock API**: Add mock API for testing without real credentials
6. **API Version Pinning**: Pin to specific API version for stability

## References

- [MorphoSource API Documentation](https://morphosource.stoplight.io/docs/morphosource-api)
- [API Migration Guide](API-Migration.md)
- [Pre-Bot-Era Archive](../Pre-Bot-Era/README.md)
