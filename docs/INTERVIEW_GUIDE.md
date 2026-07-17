# NIRA interview guide

## Tell me about this project.

NIRA is a local-first Python assistant runtime with planning, specialist capabilities, memory, permission checks, and optional llama.cpp inference.

## Why did you build it?

It explores how assistant tools can remain understandable and permissioned without requiring a cloud model for the core runtime.

## What was your contribution?

Discuss the repository's orchestration, permission/risk boundary, local-first packaging, optional integrations, tests, and portable documentation. Do not imply that every optional voice, OCR, browser, or model feature was verified.

## What was the hardest technical problem?

Designing graceful behavior when models or system integrations are unavailable while preventing tool execution from becoming implicitly authorized.

## How does the architecture work?

The Python package separates orchestration, specialists, tools, memory, research/document helpers, risk decisions, and model adapters. The core test path does not require loading a local model.

## What would you improve?

Add integration tests for optional adapters, structured execution traces, interactive permission prompts, supported-platform packaging, and adversarial prompt-injection coverage.

## How did you test it?

The editable install and 32 pytest tests pass in CI. Optional environment-dependent integrations require separate tests and are documented as unverified.

## What are its security limitations?

Local tools can still access sensitive files or networks. Permissions, prompt data, model provenance, and browser/system actions need explicit user control and audit evidence.

## How would you scale it?

Keep orchestration stateless where possible, isolate model workers, persist scoped memory explicitly, queue long tools, and enforce per-tool permissions and resource limits.

## What did you learn?

A useful agent architecture separates interpretation, planning, authorization, execution, and evidence rather than collapsing them into one model response.
