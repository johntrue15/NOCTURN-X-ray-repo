# Workflow Dependencies

This document shows the relationships between GitHub Actions workflows and their associated Python scripts.

## Workflows and Their Scripts

### daily.yml
**Required Scripts:**
- `.github/scripts/daily.py`
- `.github/scripts/collect.py`

### test_daily.yml
**Required Scripts:**
- `.github/scripts/test_daily.py`
- `.github/scripts/daily.py`

## Scripts and Their Workflows

This section shows which workflows use each script:

### daily.py
**Used in Workflows:**
- `daily.yml`
- `test_daily.yml`

### collect.py
**Used in Workflows:**
- `daily.yml`

### test_daily.py
**Used in Workflows:**
- `test_daily.yml` 