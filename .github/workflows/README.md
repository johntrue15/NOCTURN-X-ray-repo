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

---

## Adding or Modifying Workflows
1. **Create a new YAML file** in this folder (e.g., `my_new_workflow.yml`).
2. **Define the workflow triggers** (e.g., push, pull_request, schedule).
3. **Add steps and jobs** as needed for your automation task.
4. **Commit and push** your changes to the repository. GitHub Actions will automatically register your new workflow.

For more information on how GitHub Actions work, see the [official documentation](https://docs.github.com/actions).
