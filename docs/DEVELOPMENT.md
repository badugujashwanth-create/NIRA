# Development guide

## Environment

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

No model, key, or network service is needed for the core suite.

## Run safely

```powershell
.\.venv\Scripts\python -m nira --health --state-dir .\.local-state
.\.venv\Scripts\python -m nira --console --workspace . --state-dir .\.local-state
```

Use a disposable `--state-dir` and workspace for side-effect tests. Do not grant write, process, or network access merely to make a test pass.

## Verification

```powershell
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m compileall -q nira nira_agent local_llm main.py
.\.venv\Scripts\pip-audit --skip-editable
.\.venv\Scripts\python -m build
```

## Change rules

- Add every canonical tool through `ToolRegistry` with an explicit access class.
- Test denied, callback-failure, invalid-path, and oversized-input cases.
- Treat permission denial as final user intent, not a repairable failure.
- Keep user content out of default logs and security evidence.
- Update README, API, security, tests, changelog, demo, and version claims together.
- Optional integrations must fail honestly when their dependency/service is absent.
