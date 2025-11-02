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

---

## Adding or Modifying Workflows
1. **Create a new YAML file** in this folder (e.g., `my_new_workflow.yml`).
2. **Define the workflow triggers** (e.g., push, pull_request, schedule).
3. **Add steps and jobs** as needed for your automation task.
4. **Commit and push** your changes to the repository. GitHub Actions will automatically register your new workflow.

For more information on how GitHub Actions work, see the [official documentation](https://docs.github.com/actions).
