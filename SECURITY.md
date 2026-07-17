# Security policy

## Supported status

NIRA Local AI Assistant is maintained as a portfolio project and Voice, OCR, browser, and local-model features require optional system dependencies and are not validated by the core test suite.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature when it is enabled. Otherwise, contact the repository owner through an existing verified GitHub contact channel. Do not include secrets, access tokens, private URLs, or personal data in a public issue.

## Configuration rules

- Keep real credentials in local environment files or an external secret manager.
- Commit only placeholder values in `.env.example` files.
- Rotate any credential that was previously committed; deleting it from the current branch does not remove Git history.
- Use synthetic or public sample data for tests, screenshots, and recordings.

No response-time or production support commitment is implied.

