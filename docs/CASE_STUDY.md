# Case study: making a local assistant permission-bound

## Starting problem

NIRA contained substantial planning, memory, model, and automation code, but the public module entry launched a shallower runtime. Ordinary chat could create a notes file, and the richer task path had no single integrated authorization decision before side effects.

## Engineering response

The v0.4 pass selected `AgentRuntime` as canonical and inserted access enforcement at the tool registry. Read and NIRA-state actions are allowed; workspace writes, processes, and network calls require an explicit grant or approve-once decision. Callback errors fail closed, and a denial never enters repair.

Offline startup became honest and immediate. Sessions gained recovery, search, pin, rename, export, and deletion. Project inspection and file reading became direct bounded tools. A screenshot-first desktop audit then drove DPI, composer, empty-state, conversation, privacy, and permission UI repairs.

The v0.5 pass integrated a read-only Operations Center instead of adding presentation-only agent names. One canonical snapshot now exposes real sequential role activity, local memory counts, workflow templates and the completed plan, model routing/cache state, the registered tool authority, and live health evidence. The desktop filters private paths and identifiers while the local `--status` command retains the complete diagnostic contract.

## Evidence

- Tests increased from 32 to 51.
- Wheel builds and runs in a clean environment outside the repository.
- Dependency audit is clean for the audited environment.
- Eight accepted screenshots show empty, offline response, approval, denial, session management, Operations Center overview, agent activity, and privacy-safe health states.

## Result and limitation

NIRA is now a defensible local assistant prototype with a structural safety thesis. It is not a production autonomous agent. The llama.cpp adapter is real and mock-tested, but no real model/hardware profile is verified; accessibility and retrieval quality also need manual/repeatable evidence.
