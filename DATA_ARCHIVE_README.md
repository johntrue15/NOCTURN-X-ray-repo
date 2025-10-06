# Data Directory Archive

This repository uses a hybrid approach to manage historical data efficiently while maintaining workflow compatibility.

## Data Organization Strategy

To optimize GitHub Actions checkout performance while keeping workflows functional:

- **Recent data**: The most recent data directories are kept uncompressed in the `data/` directory
- **Historical data**: Older data directories are compressed in `data_archive.tar.gz`

This approach:
- Reduces repository size significantly (from ~10GB to a fraction of that)
- Keeps checkout times fast for GitHub Actions
- Maintains workflow compatibility (daily/monthly workflows can access recent data)
- Preserves all historical data in the archive

## Current State

- **Uncompressed**: The most recent data directories in `data/`
- **Archived**: Historical data in `data_archive.tar.gz`

## Extracting Historical Data

If you need to work with historical data locally, run:

```bash
./extract-data-archive.sh
```

Or manually extract:

```bash
tar -xzf data_archive.tar.gz -C /tmp/
mv /tmp/old_data/* data/
```

## For Workflow Maintainers

Most workflows don't need historical data. They work with the recent data that's already uncompressed. However, if a workflow needs access to archived data, add:

```yaml
- name: Extract historical data archive
  if: hashFiles('data_archive.tar.gz') != ''
  run: |
    echo "Extracting historical data..."
    tar -xzf data_archive.tar.gz -C /tmp/
    mv /tmp/old_data/* data/ 2>/dev/null || true
```

## Archive Information

- **Archive file**: `data_archive.tar.gz`
- **Last updated**: See git commit history

## Updating the Archive

To re-compress and update the archive:

1. Go to Actions tab in GitHub
2. Select "Compress Data Directory" workflow
3. Click "Run workflow"
4. Optionally adjust compression level and number of recent directories to keep

The workflow will:
- Keep the N most recent data directories uncompressed
- Compress older directories into `data_archive.tar.gz`
- Remove compressed directories from git to save space
