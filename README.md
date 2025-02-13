# NOCTURN X-ray Repository

This repository automatically tracks and analyzes X-ray CT data from MorphoSource, providing multiple layers of analysis through automated workflows.

## Documentation

- [Project Overview and Setup](docs/index.md) - Introduction, project structure, and getting started
- [Workflow Dependencies](docs/dependencies.md) - Detailed mapping of workflows and their associated scripts
- [Raspberry Pi Installation](docs/Raspi.md) - Guide for setting up NOCTURN on a Raspberry Pi

## Latest Analysis Results

### MorphoSource Updates
```
No updates found
```

### CT Analysis
```
CT to Text Analysis #2025-02-13_14-31-33	Latest	ct_to_text_analysis-2025-02-13_14-31-33	2025-02-13T14:31:44Z
```

### CT Image Analysis
```

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

3. **Combined CT Image Analysis** (`combined_ct_images_to_text.yml`)
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
CT to Text Analysis #2025-02-13_14-31-33	Latest	ct_to_text_analysis-2025-02-13_14-31-33	2025-02-13T14:31:44Z
CT Slice Analysis #2025-02-13_10-19-34		ct_slice_analysis-2025-02-13_10-19-34	2025-02-13T10:25:44Z
CT Analysis Error #13298852187		ct_analysis_error-13298852187	2025-02-13T02:06:32Z
MorphoSource Updates #2025-02-13_02-04-52		morphosource-updates-2025-02-13_02-04-52	2025-02-13T02:04:53Z
Daily Check #2025-02-13_01-21-07		daily-2025-02-13_01-21-07	2025-02-13T01:21:19Z
```

## Contributing

Please see our [Project Overview](docs/index.md#contributing) for guidelines on contributing to this project.

---
Last updated: 2025-02-13 21:48:12 UTC
