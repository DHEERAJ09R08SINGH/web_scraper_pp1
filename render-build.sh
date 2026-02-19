#!/usr/bin/env bash
# Install Chromium
apt-get update
apt-get install -y chromium-browser chromium-chromedriver

# Install Python dependencies
pip install -r requirements.txt