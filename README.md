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
[View CT to Text Analysis #2025-02-26_17-45-30 on GitHub](https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/ct_to_text_analysis-2025-02-26_17-45-30)

```
**Detailed CT Scan Reveals Insights into an Indeterminate Crocodilian Tooth**

The recent X-ray computed tomography (CT) scan of a crocodilian tooth, cataloged as record #105255, offers a fascinating glimpse into the intricate anatomy of these ancient reptiles. Although the exact species remains unidentified within the Crocodilia order, the high-resolution imaging provides valuable information about its morphological features. The CT scan meticulously captures the tooth's structure, revealing layers of enamel and dentine that highlight the tooth's durability and adaptation for a carnivorous diet.

One of the standout features observed is the complexity of the tooth's internal architecture. The scan exposes the pulp cavity, which houses nerves and blood vessels, indicating the tooth's vitality and growth patterns. Additionally, the enamel shows subtle variations in thickness, suggesting specialized functions such as enhanced grip or slicing capabilities for capturing and processing prey. These details shed light not only on the feeding mechanisms of this crocodilian but also on its ecological role during its time.

Moreover, the scan allows scientists to compare this tooth with those of both modern and extinct crocodilians, providing insights into evolutionary trends within the group. Understanding these morphological traits helps reconstruct the evolutionary history and adaptive strategies that have enabled crocodilians to thrive for millions of years. Overall, the CT scan serves as a powerful tool in unraveling the biological and evolutionary narratives embedded within a single tooth of an indeterminate crocodilian species.
```

### CT Slice Analysis
[View CT Slice Analysis #2025-02-26_17-32-15 on GitHub](https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/ct_slice_analysis-2025-02-26_17-32-15)

```
Analysis for MorphoSource release: morphosource-updates-2025-02-26_17-29-09


CT Slice Analysis:
=================
The provided sequence of CT slice images showcases several views of a structure, possibly a fossil or a specimen, as observed in a 3D format. 

1. **Initial Slices**: The first few images depict a solid mass with irregular shapes, suggesting contours of an object with varying density and texture, indicative of organic structures.

2. **Middle Sections**: As you progress through the slices, the shapes become more defined, possibly illustrating distinctive features or appendages of the specimen, with a notable increase in detail in areas of interest.

3. **Final Slices**: The latter images display a more fragmented appearance, with clear separations between parts of the structure, reflecting unique morphological traits. The variations in the intensity of gray scales emphasize differences in materials or densities.

Overall, the slices provide valuable insight into the 3D composition and intricate details of the specimen, which may be used for further analysis or study.
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
CT Analysis Error #13550093604 (2025-02-26T17:46:52Z)
CT to Text Analysis #2025-02-26_17-45-30 ()
MorphoSource Updates #2025-02-26_17-45-06 ()
CT Slice Analysis #2025-02-26_17-32-15 ()
CT to Text Analysis #2025-02-26_17-29-12 ()
```

## Contributing

Please see our [Project Overview](docs/index.md#contributing) for guidelines on contributing to this project.

---
Last updated: 2025-02-26 18:08:20 UTC
