# Daily Collection Script - Usage Guide

## Overview

The `daily.py` script collects MorphoSource X-ray CT data with two operational modes:

1. **Incremental Mode** (default): Fetches only new records since last collection
2. **Full Collection Mode** (`--fetch-all`): Paginates through ALL records and saves to parquet

## Command-Line Usage

### Basic Usage (Incremental)

```bash
python daily.py --data-dir /path/to/data --output-dir /path/to/output
```

This mode:
- Fetches new records until it finds the latest stored record ID
- Combines new records with existing records
- Saves only to JSON format
- Efficient for frequent checks (e.g., hourly)

### Full Collection Mode (with Parquet)

```bash
python daily.py --data-dir /path/to/data --output-dir /path/to/output --fetch-all
```

This mode:
- Paginates through ALL pages of MorphoSource results
- Fetches complete dataset regardless of previous state
- Saves to both JSON and Parquet formats
- Suitable for daily snapshots (scheduled once per day)

### Create Notes Only

```bash
python daily.py --data-dir /path/to/data --output-dir /path/to/output --create-notes
```

Creates release notes without fetching data (used for "no changes" scenarios).

## Output Files

### JSON Format
- **File**: `morphosource_data_complete.json`
- **Structure**: Array of record objects with nested metadata
- **Use Case**: Human-readable, API integration, backward compatibility

### Parquet Format (with `--fetch-all`)
- **File**: `morphosource_data_complete.parquet`
- **Structure**: Flattened table with metadata columns prefixed by `metadata_`
- **Use Case**: Data analysis, machine learning, efficient storage
- **Compression**: Snappy compression for optimal performance

### Supporting Files
- `release_notes.txt`: Human-readable summary of the collection
- `daily_info.json`: Metadata about the collection run
- `daily_extractor.log`: Detailed execution log

## Parquet Schema

The parquet file has the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `id` | string | MorphoSource record ID |
| `title` | string | Record title |
| `url` | string | Direct link to record |
| `scraped_date` | string | ISO timestamp of collection |
| `metadata_Taxonomy` | string | Taxonomic classification |
| `metadata_Element_or_Part` | string | Anatomical element |
| `metadata_Institution` | string | Source institution |
| `metadata_CC_License` | string | Creative Commons license |
| `metadata_*` | string | Other metadata fields (flattened) |

**Note**: Metadata column names are sanitized (spaces → underscores, slashes → underscores).

## Workflow Integration

### GitHub Actions (Daily)

```yaml
- name: Run Daily Check
  run: |
    python .github/scripts/daily.py \
      --data-dir data/${{ steps.timestamp.outputs.timestamp }} \
      --output-dir data/${{ steps.timestamp.outputs.timestamp }} \
      --fetch-all
```

### Dependencies

```bash
pip install requests beautifulsoup4 pandas pyarrow
```

## Error Handling

The script includes robust error handling:

- **API Errors**: Retries up to 5 times with exponential backoff
- **Rate Limiting**: 2-second delay between page requests
- **Progress Logging**: Status logged every 5 pages
- **Graceful Degradation**: If parquet dependencies unavailable, continues with JSON only

## Performance

### Typical Collection Times

| Mode | Records | Pages | Time |
|------|---------|-------|------|
| Incremental | 10-50 | 1-2 | ~10 sec |
| Full Collection | 5000+ | 50+ | ~3-5 min |

### Resource Usage

- **Memory**: ~100-200 MB for full collection
- **Disk**: Parquet files are ~30-40% of JSON size
- **Network**: ~1-2 MB per 100 records

## Troubleshooting

### Parquet Not Created

**Issue**: Parquet file missing in output

**Solutions**:
1. Check if pandas/pyarrow are installed: `pip list | grep -E "(pandas|pyarrow)"`
2. Look for "Parquet support not available" in logs
3. Install: `pip install pandas pyarrow`

### Missing Records

**Issue**: Some records not collected

**Solutions**:
1. Check `daily_extractor.log` for API errors
2. Verify network connectivity to morphosource.org
3. Check if API rate limits are being hit
4. Increase retry count in error handling

### Duplicate Records

**Issue**: Same record appearing multiple times

**Solutions**:
1. Use full collection mode (`--fetch-all`) to rebuild dataset
2. Check that record IDs are unique in source data
3. Verify sorting is consistent (`system_create_dtsi desc`)

## Advanced Usage

### Custom Query

Modify the query in `morphosource_api.py`:

```python
result = self.api.search_media(
    query="X-Ray Computed Tomography",  # Change this
    sort="system_create_dtsi desc",
    page=page,
    per_page=per_page
)
```

### Data Analysis with Parquet

```python
import pandas as pd

# Read the parquet file
df = pd.read_parquet('morphosource_data_complete.parquet')

# Analyze by taxonomy
taxonomy_counts = df['metadata_Taxonomy'].value_counts()

# Filter by institution
duke_records = df[df['metadata_Institution'].str.contains('Duke', na=False)]

# Export to CSV
df.to_csv('morphosource_export.csv', index=False)
```

## See Also

- `parse_morphosource_api.py`: Tracks total count changes and latest record
- `monthly.py`: Full monthly collection with change tracking
- `morphosource_api.py`: API client library
