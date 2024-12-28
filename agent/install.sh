#!/usr/bin/env bash
#
# install.sh
#
# Installs necessary system packages and Python libraries on the Raspberry Pi.
# Usage: chmod +x install.sh && ./install.sh
#

set -e

echo "Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

echo "Installing Python3 and pip..."
sudo apt-get install -y python3 python3-pip

echo "Installing any additional dependencies if needed..."
# e.g., git, yq, etc.
# sudo apt-get install -y git jq

echo "Installing Python libraries from requirements.txt..."
pip3 install --upgrade pip
pip3 install -r requirements.txt

echo "Installation complete!"
