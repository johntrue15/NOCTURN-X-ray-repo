# Raspi Device Automated Install/Config for Script/Agent functions

This repository contains scripts and configuration files for the Raspberry Pi 
that automatically collects X-ray metadata and integrates it with GitHub 
(and potentially iDigBio/MorphoSource).

## Setup Instructions

1. **Clone this repo** onto your Raspberry Pi:
   ```bash
   git clone https://github.com/YourOrg/my-raspi-agent-repo.git
   cd my-raspi-agent-repo
   ```
2. **Run the install script** to set up the dependencies
   ```bash
   ./install.sh
   ```
3. **Edit the config file** to match your facility details:
   ```bash
    cp raspi_config_example.yaml raspi_config.yaml
    nano raspi_config.yaml
   ```
