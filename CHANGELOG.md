# Changelog

## [0.4.0] - Unreleased

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

[0.4.0]: https://github.com/badugujashwanth-create/NIRA/compare/v0.3.0...HEAD
