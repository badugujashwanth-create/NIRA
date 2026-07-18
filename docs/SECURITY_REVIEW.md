# Security review

Reviewed: 18 July 2026. Scope: canonical v0.4 runtime, not optional legacy integrations.

## Controls verified

- Registry-level access classes: read, NIRA state, workspace write, process, network.
- Default allow only read and NIRA-owned state.
- Approve-once desktop/console paths and fail-closed callback handling.
- No automatic repair after permission denial.
- Resolved workspace paths must remain inside the selected root.
- File read output is bounded; project scan excludes dependency/build trees.
- URL validator rejects credentials and direct local/private hosts.
- Interaction-training log is opt-in.
- Permission evidence omits raw arguments.
- Dependency audit reported no known vulnerabilities in the audited environment.
- Gitleaks v8.30.1 reported no leaks in the tracked current tree and no leaks across all 17 commits.

## Residual risks

- SQLite transcript content is unencrypted.
- DNS rebinding and hostile local-filesystem races need deeper testing.
- A future tool could be misclassified if review/tests are skipped.
- Real model prompt-injection and hallucination behavior is unmeasured.
- Optional PyQt/cryptography/voice modules are outside the core contract.

The raw working-directory scan found 206 generic-key patterns only inside ignored third-party `.venv` fixtures; the scan was repeated against a `git archive` of tracked `HEAD` and returned clean. Do not store tokens in environment examples, conversations used for demos, model files, or repository artifacts.
