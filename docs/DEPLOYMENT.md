# Deployment and distribution

NIRA is a local application, not a hosted service.

## Supported release path

1. Create a Python 3.11+ virtual environment.
2. Install the v0.5 wheel and its three runtime dependencies.
3. Run `python -m nira --health --state-dir <local-path>` and `python -m nira --status --state-dir <local-path>`.
4. Launch the desktop or console.
5. Enable a local model only after its endpoint is configured and verified.

The wheel has been installed into a clean virtual environment outside the source tree and returned healthy offline JSON.

## Not yet supported

PyPI publication, signed Windows installer, auto-update, system service, container deployment, hosted multi-user API, and production cloud deployment. These require explicit owner approval, licensing, signed artifacts, platform testing, migrations/backups, and a vulnerability-response plan.

Rollback uses a prior verified tag or a normal revert commit. Never rewrite public history to roll back a release.
