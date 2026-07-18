# Performance report

No universal model-performance claim is made because no real model/hardware profile has been verified.

## Verified performance-oriented behavior

- Offline mode avoids local endpoint probes.
- Model cache count and idle lifetime are bounded.
- Context, vector hits, research sources, project previews, and file output are capped.
- Dependency/build/cache directories are pruned from project analysis.
- Runtime and model durations are recorded locally through `PerformanceAnalyzer`.

## Required benchmark evidence

Measure cold offline startup, 10k-file inspection, 1k-message search, large local-source collection, and one approved model profile. Record hardware, command, dataset, warm/cold state, sample count, p50/p95, peak memory, and raw output before publishing numbers.

Current conclusion: deterministic offline operations are deliberately bounded, but the repository does not yet support a recruiter-facing latency or tokens-per-second claim.
