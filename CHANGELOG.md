# Changelog

## [0.6.0] - 2026-07-23

### Added

- Connected project diagnostic from folder selection through safe inspection, bounded search, explicit permission, allowlisted execution, verification, cancellation/retry, and local session recovery.
- Native Ollama API availability, chat, and embedding support with a clear deterministic-offline fallback.

### Changed

- Process tools now accept fixed diagnostic profiles and reject arbitrary command strings.
- The desktop interface exposes project selection, diagnostic progress, cancellation, evidence, and recovery controls.
- Verification coverage increased to 57 automated tests.

## [0.5.0] - 2026-07-19

### Added

- Canonical read-only product snapshot for agents, memory, workflows, models, tools, permissions, and system health.
- Desktop Operations Center with live collaboration trace, completed-plan evidence, and scrollable product-domain tabs.
- `--status` JSON command for the same integrated runtime contract.
- Repository-grounded maturity gap matrix separating canonical features from deferred expansion.

### Changed

- Product walkthrough now includes Operations Center evidence and the complete permission-bound workflow.
- Conversation-manager layout preserves all actions at the audited desktop size.
- Visible health evidence filters private workspace and state-directory paths.

## [0.4.0] - 2026-07-18

### Added

- Canonical `AgentRuntime` entry points and structured health command.
- Persistent local conversation recovery, search, pin, rename, switch, export, and confirmed deletion.
- Bounded `--inspect` and `--read-file` commands.
- Default-deny tool access classes plus desktop approve-once flow.
- Privacy-safe permission decision evidence and UI/accessibility review.
- Clean wheel packaging and optional dependency groups.

### Changed

- Offline mode no longer probes a model endpoint.
- Ordinary chat performs no file mutation; interaction logs are opt-in.
- Permission denial stops immediately instead of entering repair.
- Project inspection excludes dependencies, caches, and build output.
- CI checks dependencies, tests, compilation, health, audit, and packaging.

### Fixed

- Entry-point mismatch, unbounded reads, path escape handling, pinned-session recovery ordering, and Windows DPI layout.

## [0.3.0] - 2026-07-17

- Portfolio baseline with 32 tests, initial docs, and terminal demo.

[0.6.0]: https://github.com/badugujashwanth-create/NIRA/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/badugujashwanth-create/NIRA/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/badugujashwanth-create/NIRA/compare/v0.3.0...v0.4.0
