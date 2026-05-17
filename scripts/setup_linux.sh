#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
mkdir -p .nira_data .nira_sandbox
echo "NIRA Mini local-first environment is ready."
