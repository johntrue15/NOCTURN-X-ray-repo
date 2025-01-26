# Workflow Dependencies

This document shows the relationships between GitHub Actions workflows and their associated Python scripts.

## Workflows and Their Scripts

### test-run-run.yml
**Required Scripts:**
- `.github/scripts/2D3D_check.py`
- `.github/scripts/ct_image_to_text.py`
- `.github/scripts/ct_slices_to_text.py`
- `.github/scripts/url_screenshot_check.py`

### code_review_workflow.yml
**Required Scripts:**
- `.github/scripts/analyze_code.py`

### ct_images_to_text.yml
**Required Scripts:**
- `.github/scripts/ct_image_to_text.py`
- `.github/scripts/extract_url.py`
- `.github/scripts/get_morphosource_release.py`

### test_daily.yml
**Required Scripts:**
- `.github/scripts/daily.py`
- `.github/scripts/test_daily.py`

### automated_slices_to_text.yml
**Required Scripts:**
- `.github/scripts/automated_slices_to_text.py`
- `.github/scripts/move_slices_and_screenshots.py`

### test_3d_screenshot.yml
**Required Scripts:**
- `.github/scripts/test_3D_screenshot.py`

### test_3d_screenshots_prompt.yml
**Required Scripts:**
- `.github/scripts/ct_image_to_text.py`

### monthly.yml
**Required Scripts:**
- `.github/scripts/monthly.py`

### dimension_test.yml
**Required Scripts:**
- `.github/scripts/selenium_fullscreen_test2D.py`
- `.github/scripts/selenium_fullscreen_test3D.py`

### analyze_dependencies.yml
**Required Scripts:**
- `.github/scripts/analyze_dependencies.py`

### release_analysis.yml
**Required Scripts:**
- `.github/scripts/release_analysis.py`
- `.github/scripts/release_analyzer.py`

### wiki-generation.yml
**Required Scripts:**
- `.github/scripts/release_analysis.py`

### combined_url_check_screenshot.yml
**Required Scripts:**
- `.github/scripts/2D3D_check.py`
- `.github/scripts/2D_screenshot.py`
- `.github/scripts/3D_screenshot.py`
- `.github/scripts/url_screenshot_check.py`

### combined_ct_images_to_text.yml
**Required Scripts:**
- `.github/scripts/2D3D_check.py`
- `.github/scripts/ct_image_to_text.py`
- `.github/scripts/ct_slices_to_text.py`
- `.github/scripts/url_screenshot_check.py`

### test_monthly.yml
**Required Scripts:**
- `.github/scripts/test_monthly.py`

### move_slices.yml
**Required Scripts:**
- `.github/scripts/move_slices_and_screenshots.py`

### Claude_issue_automation.yml
**Required Scripts:**
- `.github/scripts/generate_code.py`

### metadata_record_extract.yml
**Required Scripts:**
- `.github/scripts/metadata_record_extract.py`

### combined_ct_images_to_text_old.yml
**Required Scripts:**
- `.github/scripts/2D3D_check.py`
- `.github/scripts/2D_screenshot.py`
- `.github/scripts/ct_image_to_text.py`
- `.github/scripts/url_screenshot_check.py`

### ct_to_text.yml
**Required Scripts:**
- `.github/scripts/ct_to_text.py`

### selenium_screenshot_new.yml
**Required Scripts:**
- `.github/scripts/selenium_screenshot_new.py`

### test_3d_screenshot_prompt.yml
**Required Scripts:**
- `.github/scripts/analyze_ct_images.py`
- `.github/scripts/test_3D_screenshot.py`

### selenium_test.yml
**Required Scripts:**
- `.github/scripts/selenium_fullscreen_test.py`

### url_screenshot_check.yml
**Required Scripts:**
- `.github/scripts/url_screenshot_check.py`

### parse_morphosource.yml
**Required Scripts:**
- `.github/scripts/scrape_morphosource.py`

### OpenAI-release-analysis.yml
**Required Scripts:**
- `.github/scripts/OpenAI-release-analysis.py`

### selenium_screenshot.yml
**Required Scripts:**
- `.github/scripts/selenium_screenshot.py`

### daily.yml
**Required Scripts:**
- `.github/scripts/collect.py`
- `.github/scripts/daily.py`

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
