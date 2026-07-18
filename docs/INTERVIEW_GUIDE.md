# Interview guide

## Short pitch

NIRA is a local-first Python assistant where planning and capability are separate from authorization. It works in honest offline mode, stores controlled sessions locally, exposes bounded read tools, and asks before writes, processes, or network calls.

## Defensible deep dives

**Why enforce in the registry?** Every canonical task tool crosses that boundary, so permission is structural rather than prompt-based.

**Why permit NIRA state?** Sessions and proposal artifacts are core product state. The user workspace has a larger blast radius and remains separately gated.

**Why no retry after denial?** A refusal is user intent, not a technical error.

**Why an offline fallback?** Health, sessions, inspection, planning, and safety remain demonstrable without inventing model output.

**What would make it a finished flagship?** One measured model profile, memory lifecycle UI, retrieval evaluation/citations, safe revise/retry, and manual accessibility evidence.

## Claims to avoid

Do not call it production-ready, fully autonomous, fully accessible, encrypted by default, cross-platform, or a verified local LLM product.

## Demo order

Health and architecture → Operations Center evidence → session recovery → bounded inspection/read → process approval and denial → decision evidence → tests/package smoke → limitations.
