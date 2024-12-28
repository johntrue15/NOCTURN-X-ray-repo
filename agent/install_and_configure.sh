#!/usr/bin/env bash
#
# install_and_configure.sh
# 
# A single script to:
# 1. Prompt for configuration details (paths, user, scheduling).
# 2. Install required packages (system & Python).
# 3. Modify systemd .service files or set up timers/cron.
# 4. Enable, start, and test the services.
# 5. Log everything to install_and_configure.log.
#
# Usage:
#   1) git clone https://github.com/YourOrg/my-raspi-agent-repo.git
#   2) cd my-raspi-agent-repo
#   3) chmod +x install_and_configure.sh
#   4) sudo ./install_and_configure.sh

# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables and parameters as an error.
set -u
# Pipefail ensures script fails if any command in a pipeline fails (non-zero).
set -o pipefail

# Capture script directory (assuming this script is in the repo root)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Log file
LOGFILE="${SCRIPT_DIR}/install_and_configure.log"
# Redirect all stdout/stderr to tee, which appends to LOGFILE
exec > >(tee -a "$LOGFILE") 2>&1

echo "===================================================="
echo "   Welcome to the Raspberry Pi Agent Installer      "
echo "===================================================="
echo "All output is being logged to: $LOGFILE"
echo

# ------------------------------------------------------------------------------
# 1. Interactive prompts (you can hardcode or remove if you prefer non-interactive)
# ------------------------------------------------------------------------------

DEFAULT_INSTALL_PATH="/home/pi/my-raspi-agent-repo"
read -rp "Path to the cloned repository [${DEFAULT_INSTALL_PATH}]: " REPO_PATH
REPO_PATH="${REPO_PATH:-${DEFAULT_INSTALL_PATH}}"
echo "Using repository path: ${REPO_PATH}"

DEFAULT_USER="pi"
read -rp "System user to run services [${DEFAULT_USER}]: " INSTALL_USER
INSTALL_USER="${INSTALL_USER:-${DEFAULT_USER}}"
echo "Using system user: ${INSTALL_USER}"

echo
echo "How do you want these services to run?"
echo "  1) Continuous (Type=simple) systemd services"
echo "  2) One-shot with systemd timers"
echo "  3) Cron-based scheduling"
read -rp "Choose an option [1, 2, or 3]: " SCHED_OPTION
echo

case "$SCHED_OPTION" in
  1)  echo "Option 1 selected: Continuous systemd services." ;;
  2)  echo "Option 2 selected: One-shot with systemd timers." ;;
  3)  echo "Option 3 selected: Cron-based scheduling." ;;
  *)  echo "Invalid option. Defaulting to continuous services."
      SCHED_OPTION=1
      ;;
esac

# ------------------------------------------------------------------------------
# 2. Install system packages and Python requirements
# ------------------------------------------------------------------------------

echo "=== Updating and upgrading system packages... ==="
apt-get update -y
apt-get upgrade -y

echo "=== Installing Python 3, pip, and other dependencies... ==="
apt-get install -y python3 python3-pip

# If you need other packages, uncomment or add them here:
# apt-get install -y git jq

echo "=== Installing Python libraries from requirements.txt ==="
if [ -f "${REPO_PATH}/requirements.txt" ]; then
    pip3 install --upgrade pip
    pip3 install -r "${REPO_PATH}/requirements.txt"
else
    echo "No requirements.txt found at ${REPO_PATH}/requirements.txt"
fi

# ------------------------------------------------------------------------------
# 3. Adjust systemd .service files or create .timer/.cron if needed
# ------------------------------------------------------------------------------

# Services we expect in the scripts folder
SERVICES=("metadata_parser" "fetch_github_metadata" "search_and_integrate")

cd "${REPO_PATH}"

# Function to replace placeholders in .service files
function update_service_file() {
  local SERVICE_FILE="$1"
  local PATH_PLACEHOLDER="/home/pi/my-raspi-agent-repo"
  local USER_PLACEHOLDER="User=pi"

  # Replace the path in ExecStart and the user if needed
  sed -i "s|ExecStart=/usr/bin/python3 ${PATH_PLACEHOLDER}|ExecStart=/usr/bin/python3 ${REPO_PATH}|g" "${SERVICE_FILE}"
  sed -i "s|${USER_PLACEHOLDER}|User=${INSTALL_USER}|g" "${SERVICE_FILE}"
}

# Make sure we have a systemd directory
SYSTEMD_DIR="/etc/systemd/system"

if [ "$SCHED_OPTION" = "1" ]; then
  echo "=== Configuring continuous systemd services... ==="
  
  # Copy each .service to /etc/systemd/system and update placeholders
  for service in "${SERVICES[@]}"; do
    SERVICE_SRC="${REPO_PATH}/scripts/${service}.service"
    if [ -f "${SERVICE_SRC}" ]; then
      echo "Copying ${service}.service to ${SYSTEMD_DIR}"
      cp "${SERVICE_SRC}" "${SYSTEMD_DIR}/"
      update_service_file "${SYSTEMD_DIR}/${service}.service"
      # Make sure service is Type=simple or default if you desire
      # If it's set differently, you can sed that here as well
      # sed -i "s|Type=oneshot|Type=simple|g" "${SYSTEMD_DIR}/${service}.service"
      systemctl enable "${service}.service"
      systemctl start "${service}.service"
    else
      echo "WARNING: ${SERVICE_SRC} not found."
    fi
  done

elif [ "$SCHED_OPTION" = "2" ]; then
  echo "=== Configuring one-shot services with systemd timers... ==="
  echo "We'll assume each .service is Type=oneshot, and create a matching .timer."
  
  for service in "${SERVICES[@]}"; do
    SERVICE_SRC="${REPO_PATH}/scripts/${service}.service"
    if [ -f "${SERVICE_SRC}" ]; then
      cp "${SERVICE_SRC}" "${SYSTEMD_DIR}/"
      update_service_file "${SYSTEMD_DIR}/${service}.service"
      
      # Force to oneshot (if you want to be sure):
      sed -i "s|^Type=.*|Type=oneshot|g" "${SYSTEMD_DIR}/${service}.service"
      sed -i "s|^Restart=.*|Restart=no|g" "${SYSTEMD_DIR}/${service}.service"

      # Create a .timer file
      TIMER_FILE="${SYSTEMD_DIR}/${service}.timer"
      echo "[Unit]"                 >  "${TIMER_FILE}"
      echo "Description=Timer for ${service}.service" >> "${TIMER_FILE}"
      echo "[Timer]"               >> "${TIMER_FILE}"
      echo "# Run daily at 2:00 AM, adjust as needed" >> "${TIMER_FILE}"
      echo "OnCalendar=*-*-* 02:00:00"               >> "${TIMER_FILE}"
      echo "[Install]"             >> "${TIMER_FILE}"
      echo "WantedBy=timers.target" >> "${TIMER_FILE}"

      systemctl enable "${service}.timer"
      systemctl start "${service}.timer"
    else
      echo "WARNING: ${SERVICE_SRC} not found."
    fi
  done

  # Enable the timers target
  systemctl enable timers.target
  systemctl start timers.target

elif [ "$SCHED_OPTION" = "3" ]; then
  echo "=== Configuring cron-based scheduling... ==="
  echo "We will assume each script is run daily at 2:00 AM (example)."
  echo "Adjust cron entries to your liking."
  CRON_FILE="/tmp/raspi_agent_cron"

  # We'll create cron entries for each script
  # This example runs daily at 2:00 AM
  # You can modify the path to the Python scripts as needed.
  (
    crontab -l 2>/dev/null || true
    echo "# Raspi Agent Scripts (added by install_and_configure.sh)"
    for service in "${SERVICES[@]}"; do
      SCRIPT_PATH="${REPO_PATH}/scripts/${service}.py"
      if [ -f "${SCRIPT_PATH}" ]; then
        # Example: Run at 2:00 AM daily
        echo "0 2 * * * /usr/bin/python3 ${SCRIPT_PATH} >> /var/log/${service}.log 2>&1"
      else
        echo "# WARNING: ${SCRIPT_PATH} not found."
      fi
    done
  ) > "${CRON_FILE}"

  # Install the new crontab for INSTALL_USER
  crontab -u "${INSTALL_USER}" "${CRON_FILE}"
  rm -f "${CRON_FILE}"

  echo "Cron scheduling set. You can verify with: crontab -u ${INSTALL_USER} -l"

else
  echo "=== No valid scheduling option chosen, skipping service setup. ==="
fi

# ------------------------------------------------------------------------------
# 4. Basic Post-Installation Testing
# ------------------------------------------------------------------------------

echo
echo "=== Performing basic post-install checks... ==="
echo

# Check Python installation
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found after installation!" >&2
  exit 1
fi

# Check pip installation
if ! command -v pip3 &>/dev/null; then
  echo "ERROR: pip3 not found after installation!" >&2
  exit 1
fi

# Optional: test the scripts directly
TEST_SCRIPT="${REPO_PATH}/scripts/metadata_parser.py"
if [ -f "${TEST_SCRIPT}" ]; then
  echo "Testing metadata_parser.py..."
  python3 "${TEST_SCRIPT}" "/tmp" || echo "WARNING: metadata_parser test failed or is incomplete (placeholder)."
else
  echo "WARNING: ${TEST_SCRIPT} not found."
fi

echo
echo "=== Installation and configuration complete! ==="
echo "Log file: ${LOGFILE}"
echo

if [ "$SCHED_OPTION" = "1" ]; then
  echo "Check status of services with:"
  for service in "${SERVICES[@]}"; do
    echo "  systemctl status ${service}.service"
  done
  echo
  echo "View logs with, e.g.:  journalctl -u metadata_parser.service -f"
elif [ "$SCHED_OPTION" = "2" ]; then
  echo "Check status of timers with: systemctl list-timers"
  echo "View logs with: journalctl -u <service>.service"
elif [ "$SCHED_OPTION" = "3" ]; then
  echo "Check cron with: crontab -u ${INSTALL_USER} -l"
  echo "Logs can be found in /var/log/<service>.log if you used the example entries."
fi

echo "Done!"
exit 0
