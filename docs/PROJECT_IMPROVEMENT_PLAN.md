# Project Improvement Plan

## Current state

NIRA is a tested local-assistant runtime with tool orchestration, permission boundaries, fallback behavior, and 32 passing tests. It is stronger than a chat wrapper, but the operator experience and environment-dependent integrations are not uniformly verified.

## Findings

- **Works:** core orchestration, local-first configuration, confirmation gates, error paths, tests, and documented CLI workflow.
- **Does not / missing:** no polished desktop UI; local-model availability, OS tools, offline behavior, and resource use vary by machine.
- **UX / architecture:** module boundaries are good; onboarding should make model/tool prerequisites and recovery clearer.
- **Testing / security:** provider and OS integration smoke tests remain manual. Permissions are explicit, but an exhaustive tool abuse review is out of scope.
- **Performance / docs / demo:** model startup and memory are not benchmarked. Documentation and video are strong; hardware-dependent behavior is the main demo blocker.

## Recommendations

### Critical

- Keep all external actions behind explicit confirmation and keep unsupported providers fail-closed.
- Verify the documented primary CLI workflow and one unavailable-model recovery path.

### High value

- Add repeatable resource measurements for one supported local model.
- Add contract tests for another failure-prone tool adapter.

### Optional

- Add a thin desktop shell only if it preserves the tested core instead of duplicating it.

## Delivery constraints

- **Priority:** critical checks first; **complexity:** small to medium; **dependencies:** supported Python/runtime and an optional local model.
- **Acceptance:** tests pass, startup is reproducible, a permission gate and recovery path are demonstrated, and limitations remain explicit.
- **Excluded:** cloud accounts, autonomous unrestricted actions, paid APIs, and a broad UI rewrite.
