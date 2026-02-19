#!/usr/bin/env bash
set -e

echo "==== Installing Chromium and ChromeDriver ===="

# Update package lists
apt-get update

# Install Chromium browser
apt-get install -y chromium-browser

# Install ChromeDriver manually (matching Chromium version)
CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
wget -q "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"
unzip -o chromedriver_linux64.zip
chmod +x chromedriver
mv chromedriver /usr/local/bin/
rm chromedriver_linux64.zip

# Verify installations
which chromium-browser
which chromedriver
chromium-browser --version
chromedriver --version

echo "==== Installing Python dependencies ===="
pip install --upgrade pip
pip install -r requirements.txt

echo "==== Build completed successfully ===="
