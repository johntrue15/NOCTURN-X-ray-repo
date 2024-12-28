```plaintext
agent/
├── README.md
├── install.sh
├── requirements.txt
├── scripts/
│   ├── __init__.py
│   ├── metadata_parser.py
│   ├── fetch_github_metadata.py
│   ├── search_and_integrate.py
│   ├── metadata_parser.service
│   ├── fetch_github_metadata.service
│   ├── search_and_integrate.service
└── raspi_config_example.yaml
```

# Agent

This repository contains scripts, service files, and configuration  
for a Raspberry Pi that automatically collects and processes X-ray metadata,  
then integrates it with GitHub (and possibly iDigBio/MorphoSource).

---

## Setup Instructions

1. **Clone this repo**:
   ```bash
   git clone https://github.com/YourOrg/my-raspi-agent-repo.git
   cd my-raspi-agent-repo
   ```

2. **Run the install script**:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **Configure the Pi**:
   - Make a copy of `raspi_config_example.yaml` to `raspi_config.yaml`.
   - Edit it to match your facility info, GitHub repo, etc.

4. **Install systemd services (optional)**:
   - Copy the `.service` files from `scripts/` into `/etc/systemd/system`.
   - Enable and start them as needed:
     ```bash
     sudo systemctl enable metadata_parser.service
     sudo systemctl start metadata_parser.service
     # ...
     ```

---

## Scripts Overview

- **metadata_parser.py**: Processes local X-ray data into structured metadata.  
- **fetch_github_metadata.py**: Pulls updates/config from GitHub.  
- **search_and_integrate.py**: Searches external APIs (iDigBio, MorphoSource) and integrates new data.  

---

## Service Files

- **metadata_parser.service**  
- **fetch_github_metadata.service**  
- **search_and_integrate.service**

These allow you to run the scripts automatically in the background.  
Adjust them as needed for your environment.
