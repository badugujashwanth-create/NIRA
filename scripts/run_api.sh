#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate
python main.py serve --host 127.0.0.1 --port "${PORT:-8787}"
