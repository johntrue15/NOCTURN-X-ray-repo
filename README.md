# NOCTURN X-ray Repository

This repository automatically tracks and analyzes X-ray CT data from MorphoSource, providing multiple layers of analysis through automated workflows.

## GitHub Pages

📊 [View Release Dashboard](https://johntrue15.github.io/NOCTURN-X-ray-repo/) - Interactive dashboard showing the latest release information, updated hourly.

## Documentation

- [Project Overview and Setup](docs/index.md) - Introduction, project structure, and getting started
- [Workflow Dependencies](docs/dependencies.md) - Detailed mapping of workflows and their associated scripts
- [Raspberry Pi Installation](docs/Raspi.md) - Guide for setting up NOCTURN on a Raspberry Pi
- [API Migration Guide](docs/API-Migration.md) - Information about the transition from web scraping to MorphoSource API

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
[View CT to Text Analysis #2025-02-26_18-22-13 on GitHub](https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/ct_to_text_analysis-2025-02-26_18-22-13)

```
The recently released CT scan of a Crocodilia indeterminate (Crocodilia indet.) tooth offers a fascinating glimpse into the intricate anatomy of these ancient reptiles. Crocodilians, encompassing modern alligators, crocodiles, and their relatives, are renowned for their powerful jaws and sharp teeth, essential for their predatory lifestyle. This high-resolution scan allows scientists to examine the tooth's internal structure without damaging the specimen, revealing details such as enamel thickness, dentine composition, and the presence of any microscopic wear patterns.

One of the notable morphological features visible through the CT scanning process is the complexity of the tooth's root structure. Understanding the root morphology can provide insights into the attachment strength and longevity of the tooth, shedding light on how these animals efficiently capture and process their prey. Additionally, the scan may reveal growth patterns or incremental lines within the tooth, which can be analyzed to infer the age, growth rates, and even the environmental conditions the individual experienced during its lifetime.

This non-destructive imaging technique not only preserves the integrity of the fossil but also opens doors to comparative studies with both extinct and extant crocodilian species. By comparing the morphological features revealed in the CT scan, researchers can trace evolutionary adaptations that have allowed crocodilians to thrive in diverse habitats for millions of years. Ultimately, such detailed internal views enhance our understanding of crocodilian biology and evolution, contributing to the broader knowledge of reptilian development and ecological success.
```

### CT Slice Analysis
[View CT Slice Analysis #2025-02-26_18-45-11 on GitHub](https://github.com/johntrue15/NOCTURN-X-ray-repo/releases/tag/ct_slice_analysis-2025-02-26_18-45-11)

```
Analysis for MorphoSource release: morphosource-updates-2025-02-26_18-21-42


CT Slice Analysis:
=================
The CT slice images you provided appear to depict specific specimens, possibly teeth or tooth-like structures, as suggested by their shape and outlines. Each slice shows varying levels of detail, with the object prominently displayed in the center against a black background, which aids in visualization.

1. **First Image**: The object at the center is somewhat pointed, indicating it may be a tooth's crown. There is a smooth contour toward the tip.

2. **Subsequent Images**: As you progress through the images, the shape and position of the object gradually change, possibly illustrating the three-dimensional structure of the specimen from different angles. The consistency in color and textural details hints at a solid material, likely indicative of dental anatomy.

3. **Overall Characteristics**: The grading of transparency and shading across the slices illustrates the internal composition, possibly displaying density differences within the material.

These slices can be valuable for scientific studies, such as anatomical research or for identifying species based on dental morphology.
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

**Important**: This repository now uses the MorphoSource API. You'll need to obtain an API key from MorphoSource.org and configure it as a GitHub secret named `MORPHOSOURCE_API_KEY`. See our [API Migration Guide](docs/API-Migration.md) for detailed instructions.

For detailed installation instructions:
- Standard setup: See our [Project Overview](docs/index.md#installation)
- Raspberry Pi setup: Follow our [Raspberry Pi Guide](docs/Raspi.md#installation)
- API Configuration: Follow our [API Migration Guide](docs/API-Migration.md#setup-requirements)

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
Last updated: 2025-02-26 19:02:14 UTC
