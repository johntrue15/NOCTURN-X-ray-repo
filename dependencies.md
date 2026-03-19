# Workflow Dependencies

This document shows the relationships between GitHub Actions workflows and their associated Python scripts.

## Scheduled Workflows

### Parse MorphoSource API (total_count + latest record) (`parse-morphosource-api.yml`)

**Schedule:** Every 5 minutes

**Required Scripts:**
- `.github/scripts/parse_morphosource_api.py`

**Triggers Workflows:**

- `ct_to_text.yml`
  Scripts:
  - `.github/scripts/ct_to_text.py`

- `modified_morphosource.yml`
  Scripts:
  - `.github/scripts/check_modified_morphosource.py`

- `update_readme.yml`

---

### Daily MorphoSource Check (`daily.yml`)

**Schedule:** Daily at midnight

**Required Scripts:**
- `.github/scripts/daily.py`


---

### Release Reactions Collector (`release-reactions.yml`)

**Schedule:** Daily at midnight

**Required Scripts:**
- `.github/scripts/collect_reactions.py`


---

### Monthly MorphoSource Collection (`monthly.yml`)

**Schedule:** Monthly on day 1 at 0:0

**Required Scripts:**
- `.github/scripts/monthly.py`


---

### Wiki Generation (`wiki-generation.yml`)

**Schedule:** Monthly on day 1 at 0:0

**Required Scripts:**
- `.github/scripts/release_analysis.py`


---

### Cleanup CT Error Releases (`cleanup_ct_error_releases.yml`)

**Schedule:** Cron: 0 */6 * * *


---

### GitHub Pages Content Generation (`github-pages.yml`)

**Schedule:** Cron: 0 */6 * * *

**Required Scripts:**
- `.github/scripts/generate_taxonomy_explorer.py`


---

### Dataset Quality Metrics (`quality-metrics.yml`)

**Schedule:** Cron: 0 10 * * 0

**Required Scripts:**
- `.github/scripts/quality_metrics.py`


---

### Daily Deep Analysis Orchestrator (`daily-analysis-orchestrator.yml`)

**Schedule:** Cron: 0 6 * * *

**Required Scripts:**
- `.github/scripts/score_records.py`

**Triggers Workflows:**

- `cross-specimen-analysis.yml`
  Scripts:
  - `.github/scripts/cross_specimen_compare.py`

---

### Weekly Trend Report (`weekly-trend-report.yml`)

**Schedule:** Cron: 0 8 * * 0

**Required Scripts:**
- `.github/scripts/weekly_trends.py`


---

### MorphoSource Blockchain Snapshot (`morphosource_blockchain.yml`)

**Schedule:** Cron: 30 2 * * *

**Required Scripts:**
- `.github/scripts/morphosource_blockchain.py`


---

### Fine-tune Model from Reactions (`finetune-model.yml`)

**Schedule:** Weekly on Sunday at midnight

**Required Scripts:**
- `.github/scripts/finetune_model.py`
- `.github/scripts/prepare_finetune_data.py`


---

## Other Workflows

### Analyze Workflow Dependencies (`analyze_dependencies.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/analyze_dependencies.py`

### Audit CT Text Releases (`audit_ct_releases.yml`)
**Manual trigger available**

### MorphoSource CT API Pipeline (`combined_ct_images_to_text.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/process_morphosource_records.py`

### Compress Data Directory (`compress-data.yml`)
**Manual trigger available**

### Cross-Specimen Comparison (`cross-specimen-analysis.yml`)
**Triggered by:**
- `Daily Deep Analysis Orchestrator`
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/cross_specimen_compare.py`

### CT to Text Analysis (`ct_to_text.yml`)
**Triggered by:**
- `Parse MorphoSource API (total_count + latest record)`
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/ct_to_text.py`

### Deploy GitHub Pages (`deploy-pages.yml`)

### Fetch MorphoSource media (by ID) (`fetch_morphosource_media.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/fetch_morphosource_media.py`

### Check Modified MorphoSource Records (`modified_morphosource.yml`)
**Triggered by:**
- `Parse MorphoSource API (total_count + latest record)`
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/check_modified_morphosource.py`

### MorphoSource API Download (`morphosource_api_download.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/analyze_downloaded_mesh.py`
- `.github/scripts/morphosource_api_download.py`

### Parquet Data Grapher (`parquet_grapher.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/parquet_grapher.py`

### Parquet Data Processor (`parquet_processor.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/parquet_processor.py`

### Retrigger CT to Text Analysis (`retrigger_ct_analysis.yml`)
**Manual trigger available**

### Save User Ratings (`save-ratings.yml`)

### SlicerMorph Analysis (`slicer_morph_analysis.yml`)
**Manual trigger available**
**Required Scripts:**
- `.github/scripts/slicer_morph_analysis.py`

### Update README (`update_readme.yml`)
**Triggered by:**
- `Parse MorphoSource API (total_count + latest record)`
**Manual trigger available**

### Workflow Monitor (`workflow-monitor.yml`)
**Triggered by:**
- `*`

## Scripts and Their Workflows

This section shows which workflows use each script:

### analyze_dependencies.py
**Used in Workflows:**
- `analyze_dependencies.yml`

### analyze_downloaded_mesh.py
**Used in Workflows:**
- `morphosource_api_download.yml`

### check_modified_morphosource.py
**Used in Workflows:**
- `modified_morphosource.yml`

### collect_reactions.py
**Used in Workflows:**
- `release-reactions.yml`

### cross_specimen_compare.py
**Used in Workflows:**
- `cross-specimen-analysis.yml`

### ct_to_text.py
**Used in Workflows:**
- `ct_to_text.yml`

### daily.py
**Used in Workflows:**
- `daily.yml`

### fetch_morphosource_media.py
**Used in Workflows:**
- `fetch_morphosource_media.yml`

### finetune_model.py
**Used in Workflows:**
- `finetune-model.yml`

### generate_taxonomy_explorer.py
**Used in Workflows:**
- `github-pages.yml`

### monthly.py
**Used in Workflows:**
- `monthly.yml`

### morphosource_api_download.py
**Used in Workflows:**
- `morphosource_api_download.yml`

### morphosource_blockchain.py
**Used in Workflows:**
- `morphosource_blockchain.yml`

### parquet_grapher.py
**Used in Workflows:**
- `parquet_grapher.yml`

### parquet_processor.py
**Used in Workflows:**
- `parquet_processor.yml`

### parse_morphosource_api.py
**Used in Workflows:**
- `parse-morphosource-api.yml`

### prepare_finetune_data.py
**Used in Workflows:**
- `finetune-model.yml`

### process_morphosource_records.py
**Used in Workflows:**
- `combined_ct_images_to_text.yml`

### quality_metrics.py
**Used in Workflows:**
- `quality-metrics.yml`

### release_analysis.py
**Used in Workflows:**
- `wiki-generation.yml`

### score_records.py
**Used in Workflows:**
- `daily-analysis-orchestrator.yml`

### slicer_morph_analysis.py
**Used in Workflows:**
- `slicer_morph_analysis.yml`

### weekly_trends.py
**Used in Workflows:**
- `weekly-trend-report.yml`
