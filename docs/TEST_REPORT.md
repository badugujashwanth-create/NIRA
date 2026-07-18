# Test report

Last local verification: 19 July 2026, Windows, Python 3.13, branch `product-integration-v0.5`.

| Check | Result | Scope |
| --- | --- | --- |
| `pip check` | Pass | installed dependencies consistent |
| `pytest -q` | **51 passed** | CLI, runtime, memory, task graph, policy, tools, models, interface, Operations Center |
| `compileall` | Pass | canonical, compatibility, local-model packages |
| `pip-audit --skip-editable` | Pass | no known dependency vulnerabilities; editable app skipped |
| Gitleaks 8.30.1 tracked `HEAD` | Pass | no leaks in 1.94 MB tracked archive |
| Gitleaks 8.30.1 full history | Pass | no leaks across the complete repository history |
| `python -m build` | Pass | v0.5 sdist and wheel |
| clean-venv wheel install | Pass | deterministic-offline health/status smoke outside source tree; 9 roles, 14 tools, 1 workflow |
| installed `python -m nira --health` | Pass | deterministic offline, read/state authority |
| desktop capture flow | Pass | eight current-build audit screenshots and all 12 frames from the 5:40 v0.5 walkthrough inspected |
| demo artifact integrity | Pass | 340.008 s, 1280x720 VP9/Opus, SHA-256 `cd6e57141667487f0f99d43107b68a0852da2eb7aa905dfc643b8cb34cdade88` |

## Important regressions covered

No chat file mutation; path escape blocked; file output bounded; pinned session does not replace latest; callback failures deny; permission evidence excludes arguments; process denial is prompted once and never repaired; project inspection excludes dependencies; Operations Center omits private paths and reports the completed task plan.

## Not covered

Real local model, voice/OCR/PyQt, Narrator/NVDA, database corruption/disk full, Linux/macOS desktop, retrieval quality, and adversarial DNS/path races. Green tests do not validate those claims.
