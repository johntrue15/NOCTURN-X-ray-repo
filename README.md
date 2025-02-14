# NOCTURN X-ray Repository

This repository automatically tracks and analyzes X-ray CT data from MorphoSource, providing multiple layers of analysis through automated workflows.

## Documentation

- [Project Overview and Setup](docs/index.md) - Introduction, project structure, and getting started
- [Workflow Dependencies](docs/dependencies.md) - Detailed mapping of workflows and their associated scripts
- [Raspberry Pi Installation](docs/Raspi.md) - Guide for setting up NOCTURN on a Raspberry Pi

## Latest Analysis Results

### MorphoSource Updates
[View MorphoSource Updates #2025-02-13_02-04-52 on GitHub](https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/morphosource-updates-2025-02-13_02-04-52)

```
A new increase in X-ray Computed Tomography records was found on MorphoSource.

We found 1 new record(s) (old record value: 105152).

New Record #105153 Title: Reticulate Nummulites
Detail Page URL: https://www.morphosource.org/concern/media/000709702?locale=en
Object: NHMD:MP
Taxonomy: Nummulites sp.
Element or Part: Complete test
Data Manager: Ravi Kiran Koorapati
Date Uploaded: 02/13/2025
Publication Status: Restricted Download
```

### CT Analysis
[View CT to Text Analysis #2025-02-13_14-31-33 on GitHub](https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/ct_to_text_analysis-2025-02-13_14-31-33)

```
**Record #N/A:**

No information is available for Record #N/A. As a result, we are unable to provide a description of the specimen's taxonomy or morphological features at this time. Additional data or updates to this record would be necessary to offer meaningful insights into the specimen's characteristics and significance.

**Record #105153: Reticulate Nummulites**

The CT scan of Nummulites sp., cataloged under NHMD:MP, offers a detailed view of a complete test from this fascinating genus of foraminifera. Nummulites are renowned for their large, intricately patterned shells, which are composed of multiple chambers arranged in a sophisticated, often reticulate (net-like) structure. This advanced imaging technique allows researchers to explore the internal architecture of the test without physically altering the specimen, unveiling the complex septa that separate each chamber. The reticulate pattern observed in this specimen highlights the evolutionary adaptations that may have contributed to its buoyancy and structural resilience in ancient marine environments.

By examining the complete test, scientists can gain valuable insights into the growth patterns and morphological variations that characterize Nummulites species. This information is crucial for understanding their role in marine ecosystems of the past, as well as their contribution to sediment formation and biostratigraphic dating. Additionally, the high-resolution CT scans facilitate studies on the paleoecology and evolutionary biology of these microorganisms, shedding light on how they adapted to changing environmental conditions over geological time scales. Overall, the detailed morphological data obtained from this scan enhances our comprehension of Nummulites' structural complexity and their significance in the fossil record.
```

### CT Slice Analysis
[View CT Slice Analysis #2025-02-13_10-19-34 on GitHub](https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/ct_slice_analysis-2025-02-13_10-19-34)

```
Analysis for MorphoSource release: morphosource-updates-2025-02-13_02-04-52


CT Slice Analysis:
=================
The images appear to be CT slice scans revealing the internal structures of an object, possibly a fossil or a geological specimen. Each slice offers a different horizontal cross-section, showcasing details such as:

1. **Slice 1-2**: Show a fuzzy, indistinct outline with minor brightness variations, suggesting the beginning of a complex structure.
2. **Slice 3**: Begins to show more defined internal patterns, indicating layers or sections inside the object.
3. **Slice 4**: Displays circular features, possibly indicating cavities or chambers.
4. **Slices 5-7**: Reveal increasingly intricate details, showing spiral or coiled structures typically associated with shells or similar formations.
5. **Slice 8**: The complexity of the internal structure continues to build, perhaps showing further segmentation or organization within the object.
6. **Slice 9-10**: Return to less defined features but still hint at possible internal architecture, displaying holes or irregularities.

Overall, the slices capture the variability and complexity of the object's internal structure, suggesting that it may belong to a biological or geological category, such as a type of mollusk shell or mineral formation.
--------------------------------------------------------------------------------
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
Daily Check #2025-02-14_01-20-49 (2025-02-14T01:21:04Z)
CT to Text Analysis #2025-02-13_14-31-33 ()
CT Slice Analysis #2025-02-13_10-19-34 ()
MorphoSource Updates #2025-02-13_02-04-52 ()
Daily Check #2025-02-13_01-21-07 ()
```

## Contributing

Please see our [Project Overview](docs/index.md#contributing) for guidelines on contributing to this project.

---
Last updated: 2025-02-14 07:10:58 UTC
