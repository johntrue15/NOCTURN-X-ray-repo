# Retrigger CT to Text Analysis Workflow - Usage Guide

## Overview

The `retrigger_ct_analysis.yml` workflow automatically fixes failed CT to Text Analysis runs that encountered API permission errors. It identifies error releases, retriggers the analysis for the corresponding MorphoSource releases, and cleans up the error releases.

## When to Use This Workflow

Use this workflow when you have CT to Text Analysis releases that failed with the error:
```
Error calling o1-mini model: Error code: 401 - {'error': {'message': 'You have insufficient permissions for this operation.', 'type': 'invalid_request_error', 'param': None, 'code': None}}
```

This typically happens when:
- OpenAI API key permissions were insufficient
- API quotas were exceeded
- Temporary API service issues occurred

## How It Works

1. **Searches** for `ct_to_text_analysis-*` releases containing the specific 401 error
2. **Identifies** the corresponding `morphosource-api-*` release that triggered each failed analysis
3. **Triggers** the `ct_to_text.yml` workflow to re-run the analysis with the correct release tag
4. **Deletes** the error release to clean up the repository
5. **Repeats** for all matching releases (or stops after one in test mode)

## Step-by-Step Instructions

### First Time Use (Test Mode)

**IMPORTANT:** Always run in test mode first to verify the workflow works correctly!

1. Navigate to the **Actions** tab in GitHub
2. Select **"Retrigger CT to Text Analysis"** from the workflow list
3. Click **"Run workflow"** button
4. Configure the options:
   - ✅ **test_mode**: Leave CHECKED (default)
   - Leave **specific_tag** empty
5. Click **"Run workflow"** to start
6. Monitor the workflow run:
   - Check the logs to see which release was processed
   - Verify the CT to Text workflow was triggered correctly
   - Confirm the error release was deleted
   - Check that a new successful CT analysis release was created

### Production Use (Batch Mode)

Once you've verified test mode works:

1. Navigate to the **Actions** tab in GitHub
2. Select **"Retrigger CT to Text Analysis"** from the workflow list
3. Click **"Run workflow"** button
4. Configure the options:
   - ❌ **test_mode**: UNCHECK this box
   - Leave **specific_tag** empty
5. Click **"Run workflow"** to start
6. The workflow will process ALL matching error releases
7. Monitor progress in the logs

### Processing a Specific Release

If you want to fix a specific error release:

1. Find the error release tag (e.g., `ct_to_text_analysis-2025-10-31_14-35-14`)
2. Navigate to the **Actions** tab in GitHub
3. Select **"Retrigger CT to Text Analysis"** from the workflow list
4. Click **"Run workflow"** button
5. Configure the options:
   - ✅ **test_mode**: Can be checked or unchecked
   - **specific_tag**: Enter the error release tag
6. Click **"Run workflow"** to start

## What to Expect

### During Execution

The workflow logs will show:
```
=========================================
Retrigger CT to Text Analysis Workflow
=========================================
Test Mode: true
Specific Tag:

Searching for error releases...

Found error release: ct_to_text_analysis-2025-10-31_14-35-14
  Timestamp: 2025-10-31_14-35-14
  Error release created at: 2025-10-31T14:13:39Z
  Found morphosource release: morphosource-api-000791512-2025-10-31_14-34-45
  → Triggering ct_to_text workflow for: morphosource-api-000791512-2025-10-31_14-34-45
  → Workflow triggered successfully
  → Deleting error release: ct_to_text_analysis-2025-10-31_14-35-14 (ID: 258827854)
  → Release deleted successfully

✓ Test mode: Processed 1 release. Exiting.
=========================================
Summary:
  Processed: 1 release(s)
=========================================
```

### After Completion

1. Error releases will be deleted from the Releases page
2. New CT to Text Analysis workflows will be triggered
3. Within a few minutes, new successful CT analysis releases should appear
4. Check the new releases to confirm they contain proper analysis (not errors)

## Troubleshooting

### No error releases found

**Problem:** Workflow reports "No error releases found to process."

**Solutions:**
- Verify error releases exist in the Releases page
- Check that the error message exactly matches the expected pattern
- Ensure releases are tagged with `ct_to_text_analysis-*` prefix

### Cannot find corresponding morphosource release

**Problem:** Log shows "⚠ Could not find corresponding morphosource release"

**Solutions:**
- Check that the morphosource release exists and wasn't deleted
- Verify the timestamp matching logic is working correctly
- The morphosource release should be created shortly before the error release

### Workflow trigger failed

**Problem:** Error when triggering ct_to_text workflow

**Solutions:**
- Verify the GitHub token has sufficient permissions
- Check that the `ct_to_text.yml` workflow file exists
- Ensure workflow_dispatch is enabled for ct_to_text.yml

### Rate limiting

**Problem:** GitHub API rate limit exceeded

**Solutions:**
- Wait for rate limit to reset (typically 1 hour)
- Run workflow in test mode to process fewer releases at once
- The workflow includes small delays between triggers to minimize this

## Safety Features

- **Test mode by default**: Prevents accidental bulk processing
- **Specific tag option**: Allows targeted fixes for individual releases
- **Detailed logging**: Every action is logged for verification
- **Rate limiting protection**: Built-in delays between API calls
- **Error validation**: Only processes releases with exact error match

## Notes

- Deleted releases cannot be recovered, but they will be regenerated from morphosource data
- The workflow requires `contents: write` and `actions: write` permissions
- Processing multiple releases may take time as each triggers a separate workflow
- Always review test mode results before running in batch mode
