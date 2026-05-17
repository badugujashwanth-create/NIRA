#!/usr/bin/env bash
set -euo pipefail

ollama pull phi:3
ollama pull qwen2.5-coder:7b-gguf-q4_k_m
# Pull only when you have enough RAM headroom.
# ollama pull qwen2.5:14b-gguf-q4_k_m
