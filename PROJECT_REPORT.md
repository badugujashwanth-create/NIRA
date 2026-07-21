# NIRA project report

## Current status

NIRA v0.5.0 is the current public release. The canonical product entry point is the installable `nira` package:

```powershell
python -m nira
python -m nira --console
```

The root `main.py` and root-level `config/`, `core/`, and `plugins/` tree are retained legacy Stage 3 surfaces. They are not the evidence source for the v0.5 desktop, permission, tool, memory, packaging, or release claims. `nira_agent` is a compatibility namespace for historical imports.

## Product thesis

NIRA is a local-first assistant runtime that separates user intent, planning, model output, and privileged tool execution. Read and NIRA-state operations are bounded; workspace writes, processes, and network access require an explicit user grant. A denial fails closed and is never automatically repaired or retried.

## Verified end-to-end workflow

1. Start immediately in deterministic offline mode with no credential.
2. Create and persist a local conversation.
3. Plan a bounded task and inspect progress.
4. Use contained read tools for project/file inspection.
5. Deny a side-effecting action by default or approve it once.
6. Inspect permission evidence, local memory, workflows, model state, tools, agents, and health in the Operations Center.
7. Search, pin, rename, export, or delete the local session.

The 5:40 narrated walkthrough records this current-build workflow at 1280×720. Twelve milestone frames, captions, and machine-readable verification metadata are retained under `docs/demo/verification/`.

## Architecture and safety boundaries

- `nira/core/` owns the canonical runtime and path controls.
- `nira/task_graph/` plans and executes dependency-bound work.
- `nira/tools/` registers bounded tools and access classes.
- `nira/security/` enforces default-deny side-effect policy.
- `nira/memory/` stores local SQLite conversations and retrieval state.
- `nira/interface/` provides desktop, console, progress, approval, and Operations Center surfaces.
- `nira/models/` routes deterministic and optional llama.cpp-compatible model paths.

The canonical SQLite store is local but not encrypted. A real local-model/hardware profile, cloud fallback, hosted multi-user operation, unrestricted autonomy, and production security certification are not claimed.

## Verification evidence

| Gate | Result |
|---|---|
| Automated tests | 51 passed |
| Dependency consistency | `pip check` passed |
| Dependency audit | `pip-audit --skip-editable` passed for the audited environment |
| Bytecode compilation | Canonical, compatibility, and local-model packages passed |
| Packaging | sdist and wheel built; clean-environment wheel smoke passed |
| Secret scan | Tracked tree and full history passed the recorded Gitleaks gate |
| Desktop evidence | Eight accepted UI states plus twelve walkthrough milestones |
| Demo | 340.008 seconds, 1280×720 VP9/Opus, narrated and captioned |

## Recruiter-facing interpretation

NIRA is strongest as an engineering case study in permission architecture, local-first state, deterministic fallback, bounded tools, packaging, and honest product evidence. It should not be presented as a verified foundation-model achievement or a production autonomous agent.

## Highest-value remaining work

- Measure one supported local model and hardware profile.
- Add memory retention, backup/restore, and corruption-recovery exercises.
- Evaluate retrieval quality and source citations.
- Add rich messages/attachments and broader accessibility evidence.
- Validate desktop behavior beyond the visually audited Windows profile.

See [README.md](README.md), [docs/CASE_STUDY.md](docs/CASE_STUDY.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md), and [docs/TEST_REPORT.md](docs/TEST_REPORT.md).
