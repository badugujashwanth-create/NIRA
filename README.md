# NIRA — Local-First Permissioned Assistant

NIRA is a Python desktop and console assistant for work that should remain inspectable on the user's machine. It separates a request, a plan, a model response, and a privileged tool action so that “the assistant suggested it” never silently becomes “the computer executed it.”

**Current release:** v0.5.0. Deterministic offline behavior, local session persistence, permission-gated tools, path containment, the Operations Center, and packaging are verified. Ollama and llama.cpp-compatible local APIs can be configured, but no real model/hardware performance profile is claimed.

[Watch the 5:40 desktop walkthrough](https://jashwanth-portfolio-ten.vercel.app/work/nira/) · [MP4](https://jashwanth-portfolio-ten.vercel.app/media/nira/demo.mp4) · [Captions](https://jashwanth-portfolio-ten.vercel.app/media/nira/demo-captions.vtt)

## A practical workflow

The published walkthrough uses one bounded repository-inspection task:

1. open NIRA in deterministic offline mode;
2. create and retain a local conversation;
3. ask it to inspect a selected workspace;
4. let the read-only analyzer enumerate manifests and source types while excluding dependency/build directories;
5. run a bounded text search for real diagnostic evidence;
6. review the requested action, reason, target, expected effect, and risk;
7. approve one fixed diagnostic profile, or reject it and retry later;
8. verify the captured exit code and evidence; and
9. restore, rename, export, or delete the locally preserved session.

This is useful even without a model: the orchestration, permission, containment, memory, and failure states are real runtime behavior rather than a simulated chat transcript.

## Privacy model

- Conversations are stored in a local SQLite database and are not cloud-synced.
- Interaction-training logs are off by default.
- File operations resolve against the selected workspace root.
- Read output is capped; project inspection skips dependency, cache, VCS, and build directories.
- Public URL validation rejects embedded credentials and direct private/local hosts.
- The database is not encrypted; the operating-system account and state-directory permissions remain part of the trust boundary.

## Permission boundary

| Action | Default | What happens |
| --- | --- | --- |
| Read contained workspace data | Allow | Tool runs with bounded output |
| Read/write NIRA's own state | Allow | Conversation and proposal state remains local |
| Write workspace files | Deny | Requires an explicit one-time approval |
| Start a process or build | Deny | Requires an explicit one-time approval |
| Use the network | Deny | Requires an explicit one-time approval |

Authorization happens in the tool registry before tool code runs. A denied action is returned as a user decision; the planner does not retry around it. If the approval callback itself fails, the result is denial.

## Runtime map

```text
request
  -> intent and task graph
  -> specialist/runtime step
  -> tool registry
  -> permission policy
  -> bounded tool or explicit denial
  -> local conversation/evidence

optional model path
  -> llama.cpp-compatible endpoint
  -> health check and model routing
  -> deterministic fallback when unavailable
```

The read-only Operations Center reports agents, memory, workflows, models, tools, permissions, and system health; it is an observability surface, not a second execution engine.

## Install and run

Python 3.11+ is required. Offline mode needs no credentials.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"

# Desktop or console
.\.venv\Scripts\python -m nira
.\.venv\Scripts\python -m nira --console

# Bounded read-only checks
.\.venv\Scripts\python -m nira --health --state-dir .\.local-state
.\.venv\Scripts\python -m nira --inspect . --workspace .
.\.venv\Scripts\python -m nira --read-file README.md --workspace .
.\.venv\Scripts\python -m nira --search TODO --workspace .
.\.venv\Scripts\python -m nira --diagnose TODO --workspace . --allow-execute
```

Enable a model only after a compatible endpoint is actually running:

```powershell
.\.venv\Scripts\python -m nira --enable-local-model

# Or use the local Ollama API. Override NIRA_OLLAMA_MODEL when needed.
.\.venv\Scripts\python -m nira --enable-ollama
```

Configuration is documented in [.env.example](.env.example); model files, tokens, databases, and state directories must remain untracked.

## Failure recovery

NIRA treats unavailable models, invalid paths, oversized reads, missing tool approval, and failed approval UI callbacks as explicit results. It preserves the conversation and exposes the reason instead of claiming success. Process output is captured by the build tool when the user authorizes it; a timeout or non-zero exit remains visible evidence.

## Verify the release boundary

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m compileall -q nira nira_agent local_llm main.py
.\.venv\Scripts\pip-audit --skip-editable
.\.venv\Scripts\python -m build
```

See [engineering decisions](docs/ENGINEERING_DECISIONS.md) for the incidents behind the permission and tool boundaries.

## Hardware and product limits

- No real local-model latency, memory, quality, or hardware compatibility profile is verified for the current release.
- Transcript rendering is plain text; attachments and rich Markdown are incomplete.
- Voice, OCR, the PyQt overlay, and older encrypted-memory modules are outside the core contract.
- Windows is the only visually audited desktop platform; Narrator/NVDA and a full scaling matrix remain untested.
- NIRA is not a hosted service or an unrestricted autonomous agent.

## Reference

[Architecture](docs/ARCHITECTURE.md) · [Security review](docs/SECURITY_REVIEW.md) · [CLI/API](docs/API.md) · [Test report](docs/TEST_REPORT.md) · [Case study](docs/CASE_STUDY.md) · [Version roadmap](docs/VERSION_ROADMAP.md) · [Contributing](CONTRIBUTING.md)

## License status

No license file is present. All rights remain with the copyright holder until an explicit licensing decision is approved.
