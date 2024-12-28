# NSF NOCTURN Metadata

Welcome to the **NOCTURN Metadata** project! This repository is dedicated to streamlining non-clinical tomographic imaging workflows across various facilities, while keeping each facility’s code and configurations separated into their own Git branches.

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Getting Started](#getting-started)
4. [Usage](#usage)
5. [Branch Strategy](#branch-strategy)
6. [Contributing](#contributing)
7. [License](#license)

---

## Overview

The **NOCTURN Metadata** project aims to:
- Automate the collection and processing of X-ray Computed Tomography (CT) imaging data.
- Provide facility-specific configurations in separate branches.
- Centralize shared code and actions in the main branch, making collaboration seamless.

---

## Project Structure

```plaintext
my-nocturn-xray-repo/
├─ README.md                   # General project overview
├─ docs/                       # Documentation files
│   └─ index.md
├─ agent/                      # Core agent code for processing
│   └─ main_agent.py
├─ .github/
│   └─ workflows/
│       └─ agent_actions.yml   # GitHub Actions workflow
├─ facility-1-branch           # Branch in GitHub (not a folder)
├─ facility-2-branch           # Branch in GitHub (not a folder)
└─ facility-n-branch           # Branch in GitHub (not a folder)

