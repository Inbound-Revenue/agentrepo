#! /bin/bash
# Minimal setup - heavy lifting is done by autostart.yaml
# This script runs BEFORE autostart, so keep it fast!

echo "Setting up the environment..."

# Skip heavy operations - autostart.yaml handles poetry install, npm install, etc.
# Just do quick git config if needed

echo "Setup complete (dependencies handled by autostart.yaml)"
