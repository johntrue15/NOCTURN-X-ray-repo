# Quick Start: Data Compression

## Problem
Repository checkout in GitHub Actions is slow (~480k objects, ~180MB download, several minutes)

## Solution  
A workflow to compress old data while keeping recent data accessible for workflows.

## How to Run (One-Time Setup)

### Step 1: Merge this PR
Merge this pull request to the main branch.

### Step 2: Run the Compression Workflow

1. Go to: https://github.com/johntrue15/NOCTURN-X-ray-repo/actions
2. Click on **"Compress Data Directory"** in the left sidebar
3. Click **"Run workflow"** button (top right)
4. Use defaults or customize:
   - **compression_level**: `6` (recommended) - Higher = better compression but slower
   - **keep_recent**: `3` (recommended) - Number of recent directories to keep
5. Click green **"Run workflow"** button

### Step 3: Wait for Completion
The workflow will:
- Identify ~250 old data directories to compress
- Create `data_archive.tar.gz` (~1-2GB estimated)
- Keep 3 most recent directories + special directories uncompressed
- Push changes to main branch
- Takes ~5-15 minutes depending on compression level

### Step 4: Verify Results
After the workflow completes:
- Check repository size decreased
- Run any existing workflow to verify faster checkout
- See `DATA_ARCHIVE_README.md` for details

## Expected Improvement

| Metric | Before | After (Estimated) |
|--------|--------|-------------------|
| Repo Size | ~9.9 GB | ~1-2 GB |
| Checkout Time | Several minutes | < 1 minute |
| Objects | 481,938 | Significantly fewer |
| Network Transfer | ~179 MB | Much smaller |

## If You Need Old Data Locally

```bash
./extract-data-archive.sh
```

## No Workflow Changes Needed!

Your existing workflows will continue to work without any modifications because:
- Daily workflow uses the 3 recent directories (kept uncompressed)
- Monthly workflow creates new directories (independent)
- Special directories (parquet, reactions) always available

## More Information

- Full documentation: `docs/data-compression-strategy.md`
- Implementation details: `IMPLEMENTATION_SUMMARY.md`
- After running: `DATA_ARCHIVE_README.md`

## Questions?

See the documentation files or check the workflow run logs in the Actions tab.
