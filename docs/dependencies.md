# Workflow Dependencies

This document shows the relationships between GitHub Actions workflows and their associated Python scripts.

## Scheduled Workflows

### Monthly MorphoSource Collection (`monthly.yml`)

**Schedule:** Cron: 0 0 1 * *

**Required Scripts:**
- `.github/scripts/monthly.py`


---

### Daily MorphoSource Check (`daily.yml`)

**Schedule:** Daily at midnight

**Required Scripts:**
- `.github/scripts/collect.py`
- `.github/scripts/daily.py`


---

### Wiki Generation (`wiki-generation.yml`)

**Schedule:** Daily at midnight

**Required Scripts:**
- `.github/scripts/release_analysis.py`


---

### Parse MorphoSource Data (`parse_morphosource.yml`)

**Schedule:** Every 5 minutes

**Required Scripts:**
- `.github/scripts/scrape_morphosource.py`

**Triggers Workflows:**

- `combined_ct_images_to_text.yml`
  Scripts:
  - `.github/scripts/2D3D_check.py`
  - `.github/scripts/ct_image_to_text.py`
  - `.github/scripts/ct_slices_to_text.py`
  - `.github/scripts/url_screenshot_check.py`

- `ct_to_text.yml`
  Scripts:
  - `.github/scripts/ct_to_text.py`

---

## Other Workflows

### Auto Code Generation with Claude on Issue (`Claude_issue_automation.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/generate_code.py`

### OpenAI Release Analysis (`OpenAI-release-analysis.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/OpenAI-release-analysis.py`

### Analyze Workflow Dependencies (`analyze_dependencies.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/analyze_dependencies.py`

### Automated Slices to Text (`automated_slices_to_text.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/automated_slices_to_text.py`
- `.github/scripts/move_slices_and_screenshots.py`

### Code Review and Analysis (`code_review_workflow.yml`)
**Triggered by:**
- `Auto Code Generation with Claude on Issue`
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/analyze_code.py`

### MorphoSource Analysis Workflow (`combined_ct_images_to_text.yml`)
**Triggered by:**
- `Parse MorphoSource Data`
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/2D3D_check.py`
- `.github/scripts/ct_image_to_text.py`
- `.github/scripts/ct_slices_to_text.py`
- `.github/scripts/url_screenshot_check.py`

### MorphoSource Analysis Workflow (`combined_ct_images_to_text_old.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/2D3D_check.py`
- `.github/scripts/2D_screenshot.py`
- `.github/scripts/ct_image_to_text.py`
- `.github/scripts/url_screenshot_check.py`

### MorphoSource URL and Screenshot Check (`combined_url_check_screenshot.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/2D3D_check.py`
- `.github/scripts/2D_screenshot.py`
- `.github/scripts/3D_screenshot.py`
- `.github/scripts/url_screenshot_check.py`

### CT Images to Text (`ct_images_to_text.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/ct_image_to_text.py`
- `.github/scripts/extract_url.py`
- `.github/scripts/get_morphosource_release.py`

### CT to Text (`ct_to_text.yml`)
**Triggered by:**
- `Parse MorphoSource Data`
**Required Scripts:**
- `.github/scripts/ct_to_text.py`

### 2D or 3D Selenium Fullscreen Test (`dimension_test.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/selenium_fullscreen_test2D.py`
- `.github/scripts/selenium_fullscreen_test3D.py`

### Metadata Record Extractor (`metadata_record_extract.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/metadata_record_extract.py`

### Move Slices with Selenium (`move_slices.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/move_slices_and_screenshots.py`

### Release Analysis and Wiki Generation (`release_analysis.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/release_analysis.py`
- `.github/scripts/release_analyzer.py`

### Test New Morphosource Release URL Screenshot (`selenium_screenshot.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/selenium_screenshot.py`

### Selenium Screenshot New Workflow (`selenium_screenshot_new.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/selenium_screenshot_new.py`

### Run Selenium Fullscreen Test (`selenium_test.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/selenium_fullscreen_test.py`

### Test URL Processing Workflow (`test-run-run.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/2D3D_check.py`
- `.github/scripts/ct_image_to_text.py`
- `.github/scripts/ct_slices_to_text.py`
- `.github/scripts/url_screenshot_check.py`

### 3D Screenshot Tests (`test_3d_screenshot.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/test_3D_screenshot.py`

### Test 3D Screenshot with Prompt (`test_3d_screenshot_prompt.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/analyze_ct_images.py`
- `.github/scripts/test_3D_screenshot.py`

### Test MorphoSource Screenshots Analysis (`test_3d_screenshots_prompt.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/ct_image_to_text.py`

### Test Workflow (`test_commit_workflow.yml`)
**Manual trigger available**

### Test Daily Check (`test_daily.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/daily.py`
- `.github/scripts/test_daily.py`

### Test Monthly Collection (`test_monthly.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/test_monthly.py`

### URL Screenshot Check for 2D/3D (`url_screenshot_check.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/url_screenshot_check.py`

## Scripts and Their Workflows

This section shows which workflows use each script:

### 2D3D_check.py
**Used in Workflows:**
- `combined_ct_images_to_text.yml`
- `combined_ct_images_to_text_old.yml`
- `combined_url_check_screenshot.yml`
- `test-run-run.yml`

### 2D_screenshot.py
**Used in Workflows:**
- `combined_ct_images_to_text_old.yml`
- `combined_url_check_screenshot.yml`

### 3D_screenshot.py
**Used in Workflows:**
- `combined_url_check_screenshot.yml`

### OpenAI-release-analysis.py
**Used in Workflows:**
- `OpenAI-release-analysis.yml`

### analyze_code.py
**Used in Workflows:**
- `code_review_workflow.yml`

### analyze_ct_images.py
**Used in Workflows:**
- `test_3d_screenshot_prompt.yml`

### analyze_dependencies.py
**Used in Workflows:**
- `analyze_dependencies.yml`

### automated_slices_to_text.py
**Used in Workflows:**
- `automated_slices_to_text.yml`

### collect.py
**Used in Workflows:**
- `daily.yml`

### ct_image_to_text.py
**Used in Workflows:**
- `combined_ct_images_to_text.yml`
- `combined_ct_images_to_text_old.yml`
- `ct_images_to_text.yml`
- `test-run-run.yml`
- `test_3d_screenshots_prompt.yml`

### ct_slices_to_text.py
**Used in Workflows:**
- `combined_ct_images_to_text.yml`
- `test-run-run.yml`

### ct_to_text.py
**Used in Workflows:**
- `ct_to_text.yml`

### daily.py
**Used in Workflows:**
- `daily.yml`
- `test_daily.yml`

### extract_url.py
**Used in Workflows:**
- `ct_images_to_text.yml`

### generate_code.py
**Used in Workflows:**
- `Claude_issue_automation.yml`

### get_morphosource_release.py
**Used in Workflows:**
- `ct_images_to_text.yml`

### metadata_record_extract.py
**Used in Workflows:**
- `metadata_record_extract.yml`

### monthly.py
**Used in Workflows:**
- `monthly.yml`

### move_slices_and_screenshots.py
**Used in Workflows:**
- `automated_slices_to_text.yml`
- `move_slices.yml`

### release_analysis.py
**Used in Workflows:**
- `release_analysis.yml`
- `wiki-generation.yml`

### release_analyzer.py
**Used in Workflows:**
- `release_analysis.yml`

### scrape_morphosource.py
**Used in Workflows:**
- `parse_morphosource.yml`

### selenium_fullscreen_test.py
**Used in Workflows:**
- `selenium_test.yml`

### selenium_fullscreen_test2D.py
**Used in Workflows:**
- `dimension_test.yml`

### selenium_fullscreen_test3D.py
**Used in Workflows:**
- `dimension_test.yml`

### selenium_screenshot.py
**Used in Workflows:**
- `selenium_screenshot.yml`

### selenium_screenshot_new.py
**Used in Workflows:**
- `selenium_screenshot_new.yml`

### test_3D_screenshot.py
**Used in Workflows:**
- `test_3d_screenshot.yml`
- `test_3d_screenshot_prompt.yml`

### test_daily.py
**Used in Workflows:**
- `test_daily.yml`

### test_monthly.py
**Used in Workflows:**
- `test_monthly.yml`

### url_screenshot_check.py
**Used in Workflows:**
- `combined_ct_images_to_text.yml`
- `combined_ct_images_to_text_old.yml`
- `combined_url_check_screenshot.yml`
- `test-run-run.yml`
- `url_screenshot_check.yml`
