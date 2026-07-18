# Troubleshooting

## Desktop does not open

Run `python -m nira --console`. Tk must be present in the Python installation. Check `python -c "import tkinter"`.

## Local model is unavailable

This is expected unless explicitly configured. Confirm the endpoint with its own health route, model name/path, and `NIRA_LOCAL_MODEL_ENABLED=true` or `--enable-local-model`. Offline mode remains functional.

## A tool is blocked

Read the access class and arguments. Approve once only if you initiated the action. For noninteractive commands, add the narrow process-level grant intentionally. Never broaden permissions to hide a planner mistake.

## A path is rejected

The target must resolve inside `--workspace`. Symlinks and `..` paths that escape are rejected. Select the correct workspace rather than bypassing containment.

## History is missing

Confirm the same `--state-dir` is used. `runtime.db` is local and not synchronized. Do not edit it while NIRA is running.

## Optional import fails

PyQt and older encrypted-memory modules require `.[legacy-qt]` or `.[legacy-security]`. They are outside the v0.5 core contract.

## Verification fails

Run `pip check`, then one failing test directly. Keep the exact command/output. If the wheel behaves differently, install it in a clean environment outside the checkout to avoid source shadowing.

## State is corrupt or disk is full

Stop NIRA and preserve the state directory before manual recovery. v0.5 has no automated migration/corruption repair; do not claim recovery succeeded without validating exported conversations and database integrity.
