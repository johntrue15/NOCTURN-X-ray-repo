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

# Raspberry Pi Agent Installer and Configuration

This repository contains scripts, service files, and a **single** installation/configuration script (`install_and_configure.sh`) that automates:

1. **Installing** the necessary system packages and Python libraries.  
2. **Configuring** systemd services (continuous or scheduled via timers) or cron jobs for your Raspberry Pi.  
3. **Testing** the setup to confirm it's working as expected.  

Everything is logged to `install_and_configure.log` for easy troubleshooting.

---

## Table of Contents

1. [Repository Structure](#repository-structure)  
2. [Usage Steps](#usage-steps)  
3. [Scheduling Options](#scheduling-options)  
4. [Script Details](#script-details)  
5. [Post-Installation Checks](#post-installation-checks)  
6. [Notes & Customization](#notes--customization)

---

## Repository Structure

- **`install_and_configure.sh`**: The main script that you run to set up everything (system packages, Python deps, systemd/cron configuration).  
- **`requirements.txt`**: Python dependencies.  
- **`scripts/`**: Folder containing your scripts and service files.  
  - **`.py`**: Python scripts (e.g., `metadata_parser.py`)  
  - **`.service`**: Systemd unit files (run automatically under systemd).  

---

## Usage Steps

1. **Clone this Repository**  
   ```bash
   git clone https://github.com/YourOrg/my-raspi-agent-repo.git
   cd my-raspi-agent-repo
   ```
2. **Make Script Executable**

```bash
chmod +x install_and_configure.sh
```

3. **Run the Installer**

*Use sudo because the script needs to install packages and configure systemd or cron.
```bash
sudo ./install_and_configure.sh
```

4. **Follow the Prompts**

The script will ask for the path to your repo, the user to run services, and how you’d like to schedule these services (continuous, one-shot timers, or cron).

### 5. Review the Log

- The entire setup process is logged to `install_and_configure.log` in the same directory.  
- If something fails, check the log for details.

---

## Scheduling Options

During installation, you’ll be prompted to select one of the following:

1. **Continuous** — Systemd services run in the background with `Type=simple` (or similar).  
2. **One-shot with Timers** — Systemd `.service` + `.timer` files run the scripts periodically (default daily at 2:00 AM).  
3. **Cron** — Each script is added to the `crontab` to run on a schedule (default daily at 2:00 AM).

## Continuous Services

- For scripts that you want to run **constantly** in the background.
- Example commands to manage:

```bash
systemctl status metadata_parser.service
journalctl -u metadata_parser.service -f
```

## One-shot Services + Timers
- For scripts that exit after completion, triggered on a schedule.
- You’ll see .service and .timer pairs.
- Example commands:
```bash
systemctl list-timers
systemctl status metadata_parser.timer
journalctl -u metadata_parser.service -f
```

## Cron Scheduling
- For a simpler schedule, each script is run via cron.
- Default example in the script: daily at 2:00 AM.
- Check cron entries with:
```bash
crontab -u pi -l
```
(assuming pi is the user).

## Script Details
Below is the install_and_configure.sh script you’ll find in this repo. It:

- Prompts you for the repository path, system user, and scheduling approach.
- Updates and upgrades apt packages.
- Installs Python 3, pip, and dependencies from requirements.txt.
- Copies and modifies .service files for your chosen user/path.
- Sets up either continuous systemd, systemd timers, or cron.
- Performs a basic test on metadata_parser.py.
- Logs all output to install_and_configure.log.

## Verify Services (if using systemd)
```bash
systemctl status metadata_parser.service
journalctl -u metadata_parser.service -f
```
## Verify Timers (if using one-shot)
```bash
systemctl list-timers
journalctl -u metadata_parser.service -f
```
## Verify Cron (if using cron)
```bash
crontab -u pi -l
tail -f /var/log/fetch_github_metadata.log
```
### Check the log file install_and_configure.log for any errors during the setup.

## Notes & Customization
### Service Types

If you want scripts to run indefinitely, use Type=simple. If the script exits and should only run once, use Type=oneshot.
### Timers vs. Cron

Timers are managed by systemd and are often easier to track with system logs. Cron is simpler but logs go to /var/log or must be captured manually.
User Permissions

Ensure the user you select has the necessary permissions to read/write data in the directories your scripts use.
Paths

The script uses placeholders like /home/pi/my-raspi-agent-repo in the .service files. The update_service_file function replaces them with your chosen path.
Error Handling

set -e and set -o pipefail make the script exit if a command fails. Remove or modify if partial failures are acceptable.
Testing

Currently, the script calls metadata_parser.py /tmp as a basic test. Customize it for your real test scenario.
Further Development

Integrate real logic in metadata_parser.py, fetch_github_metadata.py, search_and_integrate.py.
Use environment variables or config files (.yaml, .ini) for sensitive credentials.
Enjoy Your Automated Raspberry Pi Agent!
With this setup, your Raspberry Pi can effortlessly:

Parse local metadata.
Fetch updates from GitHub (if configured).
Integrate data with external APIs (iDigBio, MorphoSource, etc.).
All with minimal manual intervention and robust logging. Happy hacking!
