# Data Compression Implementation Summary

## Problem Solved

The repository was experiencing slow GitHub Actions checkout times due to ~9.9 GB of historical data in the `data/` directory. The checkout process was:
- Enumerating 481,938 objects
- Resolving 466,189 deltas  
- Downloading ~179 MB
- Taking several minutes per workflow run

## Solution Implemented

A **hybrid compression strategy** that optimizes repository size while maintaining workflow compatibility.

### What Was Created

1. **Compression Workflow** (`.github/workflows/compress-data.yml`)
   - Manual trigger workflow to compress historical data
   - Keeps configurable number of recent directories (default: 3)
   - Compresses older directories into `data_archive.tar.gz`
   - Automatically handles special directories (`parquet/`, `reactions/`)
   - Includes configurable compression level (1-9)
   - Uses Git LFS to handle large archive files (>100 MB)

2. **Documentation** 
   - `docs/data-compression-strategy.md` - Comprehensive technical documentation
   - `DATA_ARCHIVE_README.md` - Auto-generated when workflow runs
   - Updated main `README.md` with link to compression docs

3. **Extraction Script** (`extract-data-archive.sh`)
   - Auto-generated when workflow runs
   - Simple script to restore archived data locally

## How to Use

### Running the Compression (One-Time Setup)

1. Go to **Actions** tab in GitHub
2. Select **"Compress Data Directory"** workflow  
3. Click **"Run workflow"**
4. Configure (optional):
   - **compression_level**: 1-9 (default: 6, higher = better compression)
   - **keep_recent**: Number of recent directories to keep (default: 3)
5. Click **"Run workflow"** to start

### Expected Results

The workflow will:
- Set up Git LFS for large file handling
- Keep the 3 most recent timestamped data directories uncompressed
- Keep special directories (`parquet/`, `reactions/`) uncompressed
- Compress ~250 older directories into `data_archive.tar.gz` (managed by Git LFS)
- Remove compressed directories from git tracking
- Create extraction script and documentation

**Estimated Impact:**
- Repository size: ~9.9 GB → ~1-2 GB (depends on compression)
- Checkout time: Several minutes → < 1 minute
- Objects to enumerate: 481,938 → Significantly fewer

### For Developers

**Local Development:**
If you need historical data locally:
```bash
./extract-data-archive.sh
```

**Workflow Modifications:**
No changes needed! Existing workflows will continue to work because:
- Daily workflow finds latest data from the 3 recent directories kept
- Monthly workflow creates new directories, doesn't need old ones
- Special directories are always available

## What Directories Are Affected

### Will Be Compressed (250 directories)
Timestamped directories matching pattern `YYYY-MM-DD_HH-MM-SS` older than the most recent 3:
- `data/2025-01-26_17-05-12/`
- `data/2025-01-27_01-34-38/`
- ... (247 more)

### Will Stay Uncompressed
- Most recent 3 timestamped directories
- `data/parquet/` (special directory with parquet data)
- `data/reactions/` (special directory with reaction data)

## Verification

The solution has been tested and verified:
- ✅ YAML syntax validated
- ✅ Directory filtering logic tested (correctly identifies 253 timestamped directories)
- ✅ Special directories excluded from compression
- ✅ Daily workflow compatibility verified (finds latest from recent 3)
- ✅ Monthly workflow compatibility confirmed
- ✅ Extraction script created and documented

## Files Modified/Created

### New Files
- `.github/workflows/compress-data.yml` - Main compression workflow
- `docs/data-compression-strategy.md` - Technical documentation
- `IMPLEMENTATION_SUMMARY.md` - This file
- `.gitattributes` - Configures Git LFS for large files

### Modified Files
- `README.md` - Added link to compression documentation

### Files Created When Workflow Runs
- `data_archive.tar.gz` - Compressed archive of historical data (managed by Git LFS)
- `extract-data-archive.sh` - Extraction script
- `DATA_ARCHIVE_README.md` - Archive documentation

## Next Steps

1. **Review the changes** in this PR
2. **Merge the PR** to main branch
3. **Run the compression workflow** manually from Actions tab
4. **Verify** faster checkout times in subsequent workflow runs

## Rollback Plan

If needed, the compression can be reversed:
1. Run `./extract-data-archive.sh` to restore archived data
2. Delete `data_archive.tar.gz`
3. Commit restored directories back to git

## Support

For questions or issues:
- See detailed docs: `docs/data-compression-strategy.md`
- Check workflow logs in Actions tab
- The compression is reversible and safe

## Technical Details

- **Compression**: gzip via tar
- **Default level**: 6 (balanced speed/size)
- **Pattern matching**: `YYYY-MM-DD_HH-MM-SS` format
- **Sorting**: Reverse chronological (newest first)
- **Safety**: Non-destructive, can be reversed
- **Large file handling**: Git LFS for archives >100 MB
