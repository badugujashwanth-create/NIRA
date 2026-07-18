# NIRA maturity gap matrix

This matrix reconciles the July 2026 product-maturity review with the canonical runtime. A file or legacy module is not counted as a finished capability unless it is on the tested request path or clearly labelled optional. The goal is an accurate portfolio, not a large feature count.

Status meanings:

- **Verified** — exercised by the canonical runtime and automated tests.
- **Integrated** — visible through the Operations Center or primary desktop flow.
- **Partial** — real implementation exists, but the production contract is incomplete.
- **Deferred** — deliberately outside the local single-user product scope.

| Review area | What is already real | Genuine remaining gap | Status after v0.5 |
| --- | --- | --- | --- |
| Agent ecosystem | Planner, coding, research, document, safety, intent-routing, execution/repair, critic, and response roles | Email, meetings, project management, database, GitHub/DevOps, testing, presentation, spreadsheet, and UI-design specialists need bounded connectors and their own tests. Finance, shopping, recruiter, and health agents require separate safety/product definitions. | Integrated core; expansion deferred |
| Multi-agent collaboration | Shared `AgentState`, specialist routing, planner-to-executor handoff, safety review, critic reflection, and a live collaboration trace | No voting, debate, learned specialization, dynamic spawning, or parallel executor | Integrated sequential pipeline; partial society model |
| Workflow intelligence | Built-in templates, dependency graphs, conditional readiness, learned trace matching, one bounded repair retry, and visible progress | No drag-and-drop editor, arbitrary loops, schedules/events, approvals as workflow nodes, version history, or marketplace | Verified engine; visual authoring deferred |
| Memory evolution | Bounded short-term context, vector retrieval, knowledge graph, error/workflow/research memory, and searchable/pinnable/exportable/deletable sessions | Compression summaries, importance/aging/forgetting, canonical deduplication and contradiction checks, retention settings, relationship timeline, and record-level editing | Integrated explorer; lifecycle partial |
| Knowledge system | PDF/text extraction, local research ingestion, web source analysis behind explicit network permission, OCR in the optional automation layer, vector store, and knowledge graph | GitHub/YouTube ingestion and Notion/Drive/OneDrive/SharePoint/email connectors are not implemented | Local ingestion partial; cloud connectors deferred |
| Desktop AI OS | Main desktop window, floating overlay, notifications, voice adapter, global app state, and desktop JSON bridge | Spotlight launcher, global command palette/hotkeys, clipboard/screen understanding, screenshot reasoning, window management, and background suggestions | Desktop shell partial |
| Planning engine | Goal decomposition, dependencies, risk classification, bounded retry/repair, progress events, and adaptive guidance from reflection | Durable long-running tasks, resource/time estimates, parallel scheduling, benchmark suite, and resume-after-restart | Verified local graph; durable planner deferred |
| Tool ecosystem | Registry, access classes, default-deny policy, approve-once UI, recent decision history, path containment, bounded output, and tool list/health view | Marketplace, automatic installation, community SDK, signed/versioned tools, dependency graph, and usage analytics | Integrated and permission-bound; marketplace deferred |
| Developer experience | Installable CLI, wheel, health/status JSON contracts, desktop JSON-lines bridge, documented architecture and commands | Stable REST/WebSocket services, Python/JavaScript/plugin SDKs, OpenAPI, developer portal, and extension templates | CLI/bridge verified; public API deferred |
| User interface | Desktop chat, task graph progress, project context, conversation manager, privacy/approval dialogs, plus Operations Center tabs for agents, memory, workflows, models, tools, permissions, and health | Direct workflow editing, knowledge-relationship graph, deeper analytics, rich Markdown/attachments, and full accessibility matrix | Cohesive core integrated |
| AI intelligence | Post-execution reflection, critic repair hints, confidence scoring, model routing/cache, anomaly detection, and deterministic offline fallback | Calibrated hallucination evaluation, automatic prompt optimization, safe continuous-learning loop, and formal agent benchmark/evaluator | Runtime intelligence verified; evaluation partial |
| Enterprise | Local audit evidence and access policy only | Multi-user workspaces, RBAC, SSO, organizations, billing, API keys, hosted admin, and tenant isolation | Deferred; NIRA is explicitly single-user/local |
| Mobile companion | None in the canonical product | Android/iOS app, remote execution/notifications, voice, approvals, and dashboard | Deferred |
| AI models | Configurable model roles, multiple aliases, selection by task, bounded cache, idle unload, embedding route, and optional cloud-routing legacy code | A measured model/hardware profile, verified cloud fallback, cost policy, benchmarks, LoRA/fine-tuning UI, quantization management | Routing verified; model profile still required |
| Production readiness | PowerShell installer, wheel, PyInstaller build script, CI/security gates, config corruption backup, monitoring, troubleshooting, release evidence, and end-user docs | Signed installer, auto-update, crash recovery exercises, database migrations/backup/restore, release channels, plugin signing, opt-in telemetry policy, and broader platform/accessibility tests | Packaged prototype; signed production distribution deferred |

## Product boundary

NIRA v0.5 remains a local, single-user assistant. It does not claim medical, financial, commerce, recruiting, enterprise tenancy, mobile, or unattended autonomy. New connectors and side-effecting agents must enter through the existing default-deny tool policy and ship with failure-path tests before being advertised.

## Next release gate

The highest-value v0.6 work is memory lifecycle control, one measured local-model profile, retrieval/citation evaluation, safe resume/recovery, and accessibility evidence. These improve trust and daily usability more than adding unverified agent names.
