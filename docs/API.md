# CLI and Python API

NIRA v0.5 is local software. It exposes no HTTP server.

## Commands

| Command | Result | Default authority |
| --- | --- | --- |
| `nira` | Tk desktop | read/state only |
| `nira --console` | interactive console | read/state plus approve once |
| `nira --health` | JSON runtime status | state initialization |
| `nira --status` | Integrated JSON product snapshot | read-only state observation |
| `nira --prompt TEXT` | one planned request | policy-bound |
| `nira --inspect [PATH]` | JSON project inventory | read-only |
| `nira --read-file PATH` | JSON bounded file content | read-only |

Use `--workspace DIR` to define the path-containment root and `--state-dir DIR` to isolate local data. `--allow-write`, `--allow-execute`, and `--allow-network` are explicit process-level grants. `--enable-local-model` opts into the configured endpoint.

Successful direct actions return 0; a blocked or failed action returns 2 where applicable. Tool results contain `ok`, human-readable `output`, and structured `data`.

## Runtime API

```python
from pathlib import Path
from nira.config import NiraConfig
from nira.core.agent_runtime import AgentRuntime

runtime = AgentRuntime(NiraConfig(base_dir=Path(".nira-state")))
try:
    response = runtime.handle("Hello NIRA")
    print(response.text)
finally:
    runtime.shutdown()
```

`RuntimeResponse` includes the final text, state, planned nodes, tool results, anomalies, and the completed agent collaboration trace. `runtime.product_snapshot()` returns the same read-only agents/memory/workflows/models/tools/system contract used by `--status` and the Operations Center. Use explicit conversation and bounded-read methods rather than reaching into SQLite directly.
