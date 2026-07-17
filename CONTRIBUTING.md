# Contributing to NIRA Local AI Assistant

Thank you for improving this project. Keep changes focused, explain user-visible behavior, and avoid committing credentials, generated dependencies, local databases, or build output.

## Development flow

1. Fork or branch from the current default branch.
2. Install dependencies with `python -m venv .venv; .\.venv\Scripts\python -m pip install -e .`.
3. Make the smallest coherent change.
4. Run the relevant checks from [docs/TEST_REPORT.md](docs/TEST_REPORT.md).
5. Update documentation when commands, configuration, or behavior change.
6. Open a pull request with the problem, solution, verification evidence, and any limitations.

Use Conventional Commit-style subjects where practical, such as `fix: validate empty requests` or `docs: clarify local setup`.

## Security

Do not open a public issue containing a credential or private user data. Follow [SECURITY.md](SECURITY.md).

