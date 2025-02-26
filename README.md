# NOCTURN X-ray Repository

This repository automatically tracks and analyzes X-ray CT data from MorphoSource, providing multiple layers of analysis through automated workflows.

## Documentation

- [Project Overview and Setup](docs/index.md) - Introduction, project structure, and getting started
- [Workflow Dependencies](docs/dependencies.md) - Detailed mapping of workflows and their associated scripts
- [Raspberry Pi Installation](docs/Raspi.md) - Guide for setting up NOCTURN on a Raspberry Pi

## Latest Analysis Results

### MorphoSource Updates
[View MorphoSource Updates #2025-02-26_17-45-06 on GitHub](https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/morphosource-updates-2025-02-26_17-45-06)

```
A new increase in X-ray Computed Tomography records was found on MorphoSource.

We found 1 new record(s) (old record value: 105254).

New Record #105255 Title: P3035
Detail Page URL: https://www.morphosource.org/concern/media/000713515?locale=en
Object: uf:uf/tro
Taxonomy: Crocodilia indet.
Element or Part: tooth
Data Manager: Mitchell Riegler
Date Uploaded: 02/26/2025
Publication Status: Restricted Download
```

### CT Analysis
```
Waiting for CT analysis to complete...
```

### CT Slice Analysis
```
Waiting for CT slice analysis to complete...
```

## Workflow Overview

This repository uses several automated workflows to analyze X-ray CT data. For a complete list of workflows and their dependencies, see our [Workflow Dependencies](docs/dependencies.md) documentation.

### Main Workflows

1. **Parse MorphoSource Data** (`parse_morphosource.yml`)
   - Runs every 5 minutes
   - Scrapes MorphoSource for new X-ray CT records
   - Creates releases with new record details
   - Triggers subsequent analysis workflows

2. **CT to Text Analysis** (`ct_to_text.yml`)
   - Triggered by MorphoSource updates
   - Analyzes CT metadata using AI
   - Generates detailed descriptions of specimens

3. **CT Slice Analysis** (`combined_ct_images_to_text.yml`)
   - Analyzes 2D slices and 3D reconstructions
   - Checks image URLs and captures screenshots
   - Provides comprehensive visual analysis

### Supporting Workflows

- **Daily Check** (`daily.yml`): Daily verification of data consistency
- **Monthly Collection** (`monthly.yml`): Monthly data aggregation
- **Error Cleanup** (`cleanup_ct_error_releases.yml`): Maintains release quality
- **Wiki Generation** (`wiki-generation.yml`): Updates documentation

## Installation

For detailed installation instructions:
- Standard setup: See our [Project Overview](docs/index.md#installation)
- Raspberry Pi setup: Follow our [Raspberry Pi Guide](docs/Raspi.md#installation)

## Recent Activity

```
CT Analysis Error #13550093604 (2025-02-26T17:46:52Z)
CT to Text Analysis #2025-02-26_17-45-30 ()
MorphoSource Updates #2025-02-26_17-45-06 ()
CT Slice Analysis #2025-02-26_17-32-15 ()
CT to Text Analysis #2025-02-26_17-29-12 ()
```

## Contributing

Please see our [Project Overview](docs/index.md#contributing) for guidelines on contributing to this project.

---
Last updated: 2025-02-26 18:07:19 UTC
