# Security policy

## Supported status

The supported v0.4 security boundary is the canonical `AgentRuntime`, `nira.tools` registry, deterministic offline mode, local conversations, and optional llama.cpp HTTP adapter. Voice, OCR, PyQt, older encrypted-memory modules, and real-model behavior are outside the 48-test core contract.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature when it is enabled. Otherwise, contact the repository owner through an existing verified GitHub contact channel. Do not include secrets, access tokens, private URLs, or personal data in a public issue.

## Configuration rules

- Keep real credentials in local environment files or an external secret manager.
- Commit only placeholder values in `.env.example` files.
- Rotate any credential that was previously committed; deleting it from the current branch does not remove Git history.
- Use synthetic or public sample data for tests, screenshots, and recordings.

## Tool authority

- Read and NIRA-owned state are the only default access classes.
- Workspace writes, process execution, and network access require a grant or approve-once decision.
- Treat a denied permission as final user intent; do not automatically retry it.
- New tools must declare their access class and include denied/failure-path tests.
- Protect the local state directory; the canonical SQLite conversation store is not encrypted.

See [the current security review](docs/SECURITY_REVIEW.md) for threats, controls, and residual risks.

No response-time or production support commitment is implied.

