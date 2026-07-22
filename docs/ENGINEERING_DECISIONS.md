# NIRA engineering decisions

NIRA's strongest evidence is in the boundaries added after failure modes were reproduced. These incidents are limited to changes visible in code, tests, and merged pull requests.

## Tools could advertise risk without enforcing one policy

**Problem.** Tool implementations carried their own behavior, while the runtime did not have one canonical, default-deny authorization point for workspace writes, processes, and network access.

**User impact.** A plan could select a capable tool without giving the desktop and console interfaces a consistent opportunity to deny or approve the side effect. Permission language in the UI would not have been a reliable execution boundary.

**Reproduction.** On the pre-v0.4 tree, register a write or process tool and execute it through the runtime. There was no registry-level `ToolAccess` decision shared across tools and interfaces.

**Investigation.** Access implications were distributed across tool names and implementations. The runtime, planner, and UI could not query a common policy or retain a bounded decision history.

**Root cause.** The original architecture treated tools primarily as capabilities, not as privileged operations requiring a policy decision before dispatch.

**Fix.** `ToolAccess` classifies reads, NIRA state, workspace writes, processes, and network actions. `ToolRegistry` consults `ToolPermissionPolicy` before calling a tool. Writes/process/network default to denial, can receive one-time approval, and fail closed if the approval callback raises.

**Regression test.** `tests/test_permission_policy.py` covers default denial, one-time approval, runtime integration, failed approval callbacks, and a bounded history that excludes tool arguments. CLI tests confirm the same boundary outside the desktop UI.

**Trade-off.** Legitimate automation requires an extra user decision and approvals are not durable grants. That friction is intentional; v0.5 favors reviewability over unattended execution.

**Relevant files.** `nira/security/tool_policy.py`, `nira/tools/base.py`, `nira/tools/registry.py`, `nira/core/agent_runtime.py`, `tests/test_permission_policy.py`, `tests/test_cli.py`.

**Reference.** Commit [`e4c91fd`](https://github.com/badugujashwanth-create/NIRA/commit/e4c91fd), included in [PR #2](https://github.com/badugujashwanth-create/NIRA/pull/2).

## Read-only tools could still consume unbounded local data

**Problem.** `FileManager` read an entire file into memory, and `ProjectAnalyzer` recursively counted Python files without excluding virtual environments, dependencies, caches, or build output.

**User impact.** A nominally safe repository inspection could return a huge file, expose irrelevant dependency content to the conversation, run slowly, or report misleading project composition.

**Reproduction.** Before the fix, call the file read action on a large file: `path.read_text` had no byte limit. Create `.venv/dependency.py` under a workspace and run the analyzer: `rglob("*.py")` counted it as project source.

**Investigation.** Path containment was working, but containment alone did not bound the amount or relevance of data read inside the allowed root.

**Root cause.** The first safety model distinguished inside/outside paths but did not treat volume and generated directories as part of the read boundary.

**Fix.** File reads now cap requested output between 1 byte and 256 KiB and report truncation metadata. Project inspection uses a non-following directory walk, excludes known VCS/dependency/cache/build directories, and reports language counts plus bounded preview and scan errors.

**Regression test.** `test_file_manager_bounds_large_read_output` verifies truncation at a requested 32-byte limit. `test_project_analyzer_excludes_dependency_directories` places source files under `.venv` and `node_modules` and confirms that only application source is counted.

**Trade-off.** A truncated file or excluded generated tree may omit information needed for a specialized investigation. Callers must request a deliberate smaller target instead of using one unbounded read.

**Relevant files.** `nira/tools/file_manager.py`, `nira/tools/project_analyzer.py`, `tests/test_tools.py`.

**Reference.** Commit [`69dd28b`](https://github.com/badugujashwanth-create/NIRA/commit/69dd28b77ebc1d47b8f441d383dfb8fc23f0e94b), included in [PR #2](https://github.com/badugujashwanth-create/NIRA/pull/2).
