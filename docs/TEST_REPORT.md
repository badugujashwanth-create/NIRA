# Test report

Last local verification: 18 July 2026, Windows, Python 3.13, branch `product-completion-2026`.

| Check | Result | Scope |
| --- | --- | --- |
| `pip check` | Pass | installed dependencies consistent |
| `pytest -q` | **48 passed** | CLI, runtime, memory, task graph, policy, tools, models, interface |
| `compileall` | Pass | canonical, compatibility, local-model packages |
| `pip-audit --skip-editable` | Pass | no known dependency vulnerabilities; editable app skipped |
| `python -m build` | Pass | sdist and v0.4 wheel |
| clean-venv wheel install | Pass | installed outside source tree with runtime dependencies |
| installed `python -m nira --health` | Pass | deterministic offline, read/state authority |
| desktop capture flow | Pass | five accepted current-build screenshots |

## Important regressions covered

No chat file mutation; path escape blocked; file output bounded; pinned session does not replace latest; callback failures deny; permission evidence excludes arguments; process denial is prompted once and never repaired; project inspection excludes dependencies.

## Not covered

Real local model, voice/OCR/PyQt, Narrator/NVDA, database corruption/disk full, Linux/macOS desktop, retrieval quality, and adversarial DNS/path races. Green tests do not validate those claims.
