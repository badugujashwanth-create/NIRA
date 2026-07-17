# Development guide

## Purpose

Modular local-first assistant runtime with planning, automation permissions, specialist agents, memory, and optional local LLM support.

## Prerequisites

Python 3.11+, pytest, requests, psutil, optional llama.cpp and desktop integrations.

## Install

```powershell
python -m venv .venv; .\.venv\Scripts\python -m pip install -e .
```

## Run

```powershell
.\.venv\Scripts\python -m nira
```

## Verify

- Tests: `.\.venv\Scripts\python -m pytest -q`
- Build: `Optional executable build is documented under `nira/scripts``

See [TEST_REPORT.md](TEST_REPORT.md) for the latest audited results. Copy example environment files instead of committing real values. Generated dependencies, caches, logs, databases, and build output must remain untracked.

