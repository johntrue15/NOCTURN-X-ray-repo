# NOCTURN X-ray Repository

This repository automatically tracks and analyzes X-ray CT data from MorphoSource, providing multiple layers of analysis through automated workflows.

## Documentation

- [Project Overview and Setup](docs/index.md) - Introduction, project structure, and getting started
- [Workflow Dependencies](docs/dependencies.md) - Detailed mapping of workflows and their associated scripts
- [Raspberry Pi Installation](docs/Raspi.md) - Guide for setting up NOCTURN on a Raspberry Pi

## Latest Analysis Results

### MorphoSource Updates
[View MorphoSource Updates #2025-02-26_18-21-42 on GitHub](https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/morphosource-updates-2025-02-26_18-21-42)

```
A new increase in X-ray Computed Tomography records was found on MorphoSource.

We found 1 new record(s) (old record value: 105255).

New Record #105256 Title: P3115
Detail Page URL: https://www.morphosource.org/concern/media/000713521?locale=en
Object: uf:uf
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
MorphoSource Modified Record #2025-02-26_18-49-39 ()
CT Slice Analysis #2025-02-26_18-45-11 (2025-02-26T18:50:43Z)
CT Slice Analysis #2025-02-26_18-24-28 ()
CT to Text Analysis #2025-02-26_18-22-13 ()
MorphoSource Updates #2025-02-26_18-21-42 ()
```

## Contributing

Please see our [Project Overview](docs/index.md#contributing) for guidelines on contributing to this project.

---
Last updated: 2025-02-26 19:01:22 UTC
