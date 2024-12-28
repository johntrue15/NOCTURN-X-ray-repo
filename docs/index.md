# NSF NOCTURN Metadata Project Documentation

Welcome to the **NOCTURN Xray** documentation! This overview will help you get started with the repository and understand the core components.

## Table of Contents

1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Branch Strategy](#branch-strategy)
6. [Contributing](#contributing)
7. [License](#license)

---

## Introduction

**NOCTURN** is a project designed to streamline non-clinical tomographic imaging workflows across various facilities. Each facility may require its own custom scripts or configuration, which is why we have multiple branches for separate facility requirements.

---

## Project Structure

```plaintext
my-nocturn-xray-repo/
├─ README.md                 # High-level project overview
├─ docs/                     # Documentation files (you are here!)
├─ agent/                    # Core agent code
│   └─ main_agent.py
├─ .github/workflows/        # GitHub Actions workflows
│   └─ agent_actions.yml
├─ facility-1-branch         # (Branch in GitHub, not a folder in main)
├─ facility-2-branch         # (Branch in GitHub, not a folder in main)
└─ facility-n-branch         # (Branch in GitHub, not a folder in main)
