# GitHub Actions Workflows

This folder (`.github/workflows`) contains the GitHub Actions workflows used by this repository. Each workflow automates a specific process—such as scraping MorphoSource data or deploying code changes.

---

## Available Workflows

### 1. `parse_morphosource.yml`
- **Purpose**: Scrapes MorphoSource for new “X-Ray Computed Tomography” records, then updates a GitHub Release if new records are found.
- **Triggers**:
  - **Scheduled** (Cron): Runs every 12 hours.
  - **Manual**: Can be triggered on demand from the GitHub Actions tab.
- **Key Steps**:
  1. Checks out the repository.
  2. Installs Python and dependencies.
  3. Runs the `scrape_morphosource.py` script.
  4. If new records exist, creates or updates a “MorphoSource Updates” release.

### 2. `ct_to_text.yml`
- **Purpose**: Analyzes MorphoSource releases using OpenAI's GPT-4o-mini to generate scientific descriptions of CT scan records.
- **Triggers**:
  - **Automatic**: Runs when a new release is published.
  - **Manual**: Can be triggered on demand to re-analyze a specific morphosource release.
- **Manual Trigger Instructions**:
  1. Go to the Actions tab in GitHub
  2. Select "CT to Text Analysis" workflow
  3. Click "Run workflow"
  4. Enter the release tag to analyze (e.g., `morphosource-api-000791519-2025-10-31_20-35-16`)
  5. Click "Run workflow"
- **Use Cases**:
  - Re-run analysis for releases that failed due to API errors
  - Update analysis with improved prompts or models
  - Generate new descriptions for existing releases

### 3. `retrigger_ct_analysis.yml`
- **Purpose**: Automatically finds CT to Text Analysis releases that failed with permission errors, retriggers the analysis for the corresponding MorphoSource releases, and cleans up the error releases.
- **Triggers**:
  - **Manual only**: Must be triggered via workflow_dispatch with configuration options.
- **Manual Trigger Instructions**:
  1. Go to the Actions tab in GitHub
  2. Select "Retrigger CT to Text Analysis" workflow
  3. Click "Run workflow"
  4. Configure options:
     - **test_mode**: Check this box to process only ONE release (recommended for first run)
     - **specific_tag**: (Optional) Enter a specific error release tag to process (e.g., `ct_to_text_analysis-2025-10-31_14-35-14`)
  5. Click "Run workflow"
- **What it does**:
  1. Searches for `ct_to_text_analysis-*` releases containing the error: "Error calling o1-mini model: Error code: 401 - {'error': {'message': 'You have insufficient permissions for this operation.'"
  2. For each error release found:
     - Identifies the corresponding `morphosource-api-*` release that triggered it
     - Triggers the `ct_to_text.yml` workflow to re-run the analysis
     - Deletes the error release to clean up
  3. In test mode, processes only one release and exits
  4. With test mode off, processes all matching error releases
- **Use Cases**:
  - Bulk fix multiple days of failed CT to Text Analysis runs
  - Clean up error releases after fixing the underlying API permission issue
  - Test the retrigger process on a single release before processing all errors
- **Important Notes**:
  - Always run in test mode first to verify behavior
  - The workflow will wait briefly between triggering workflows to avoid rate limiting
  - Deleted releases cannot be recovered, but they can be regenerated from the morphosource data

---

## Adding or Modifying Workflows
1. **Create a new YAML file** in this folder (e.g., `my_new_workflow.yml`).
2. **Define the workflow triggers** (e.g., push, pull_request, schedule).
3. **Add steps and jobs** as needed for your automation task.
4. **Commit and push** your changes to the repository. GitHub Actions will automatically register your new workflow.

For more information on how GitHub Actions work, see the [official documentation](https://docs.github.com/actions).
