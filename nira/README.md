# Nira Agent (Advanced Hybrid Desktop Architecture)

Windows-first, modular, production-oriented scaffolding for an agent-level desktop AI assistant.

## 1) Full Folder Structure

```text
nira_agent\
  __init__.py
  __main__.py
  main.py
  config.py
  logging_setup.py
  performance.py
  requirements.txt
  workflows.dsl
  README.md
  scripts\
    run.ps1
  ui\
    __init__.py
    app_state.py
  ai\
    __init__.py
    llm_client.py
    prompting.py
    structured_output.py
    confidence.py
    personality.py
  routing\
    __init__.py
    cache.py
    response_parser.py
    hybrid_router.py
  automation\
    __init__.py
    models.py
    permissions.py
    tool_registry.py
    undo.py
    builtins.py
    workflow_dsl.py
    skill_loader.py
    executor.py
    manager.py
    example_registry.py
  monitoring\
    __init__.py
    activity.py
    triggers.py
    proactive.py
  memory\
    __init__.py
    short_term.py
    compressor.py
    long_term.py
    context_builder.py
    preferences.py
    manager.py
  security\
    __init__.py
    encryption.py
    auth.py
    audit.py
    tier_policy.py
  storage\
    __init__.py
    sql_store.py
  skills\
    __init__.py
    base.py
    app_skill.py
    file_skill.py
    workflow_skill.py
    browser_skill.py
    ocr_skill.py
```

## 2) Architecture Highlights

- Hybrid routing:
  - local llama.cpp primary
  - optional cloud fallback
  - confidence scoring + escalation threshold
  - TTL response cache
- Tool calling:
  - strict JSON tool calls
  - whitelist registry + arg validation
  - permission/tier checks
  - destructive confirmation + passphrase fallback
  - feedback loop back into model
- Automation:
  - skill auto-loader from `skills\`
  - app/file/browser/workflow/screenshot/OCR tools
  - DSL workflow parser
  - undo stack
- Memory:
  - short-term rolling memory
  - compression every N turns
  - encrypted long-term storage (SQL-backed when DB is available)
  - context injection builder
- Monitoring:
  - active window + process + idle + CPU
  - trigger engine + intervention cooldown
  - proactive system-state prompt injection
- Security:
  - encrypted logs/memory (stored in SQL by default, file fallback on DB failure)
  - permission tiers
  - voice verification interface + passphrase fallback
  - mandatory confirmation for tier-3/destructive actions
  - automatic safe mode on security errors

## 3) JSON Tool Call Contract

Model is instructed to return strict JSON:

```json
{
  "message": "User-facing text",
  "tool_calls": [
    {
      "tool": "open_app",
      "args": { "target": "notepad.exe" }
    }
  ],
  "confidence": 0.84
}
```

## 4) Windows Setup & Run

### A) Start local llama.cpp first

Use your existing `local_llm` folder tooling:

```powershell
cd C:\Users\JASHWANTH\NIRAMini\local_llm
powershell -ExecutionPolicy Bypass -File .\scripts\download_llama_cpp.ps1 -Force
python .\scripts\fetch_7b_model.py --quant q4_k_m --out-dir .\models
$MODEL = (Get-ChildItem .\models\*q4_k_m*.gguf | Sort-Object Name | Select-Object -First 1).FullName
python .\llama_cpp_server.py --llama-dir .\runtime --model "$MODEL"
```

### B) Run Nira Agent

Open a second terminal:

```powershell
cd C:\Users\JASHWANTH\NIRAMini\nira_agent
python -m pip install -r .\requirements.txt
$env:DB_HOST = "localhost"
$env:DB_PORT = "3306"
$env:DB_USER = "root"
$env:DB_PASSWORD = "<your-mysql-password>"
$env:DB_NAME = "nira_agent"
python -m nira_agent
```

Or:

```powershell
cd C:\Users\JASHWANTH\NIRAMini
powershell -ExecutionPolicy Bypass -File .\nira_agent\scripts\run.ps1
```

## 5) Runtime Commands

- `/mode Focus`
- `/mode Calm`
- `/mode Strategy`
- `/mode Night`
- `/undo`
- `/dnd on`
- `/dnd off`
- `/cloud <prompt>` (manual cloud escalation if configured)
- `/health`
- `/exit`

## 6) Example Workflow DSL

`workflows.dsl`

```text
workflow morning_boot permission=standard:
  open_app target="notepad.exe"
  open_url url="https://www.bing.com"
```

Model can call:

```json
{
  "message": "Starting your routine.",
  "tool_calls": [
    { "tool": "run_workflow", "args": { "name": "morning_boot" } }
  ],
  "confidence": 0.91
}
```

## 7) Common Troubleshooting

- `Could not find 'llama-server.exe'`:
  - Re-run local llama download script.
- `Model file does not exist`:
  - Verify GGUF path in `local_llm\models`.
- `Port 8080 already in use`:
  - Stop old process or run server on another port and set `NIRA_LOCAL_LLM_BASE_URL`.
- `SQL storage unavailable`:
  - Verify MySQL is running on configured host/port.
  - Verify `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`.
  - Install connector: `python -m pip install mysql-connector-python`.
- `OCR failed`:
  - Install Tesseract OCR on Windows and ensure it is in `PATH`.
- `Destructive tool blocked`:
  - Check permission tier and passphrase config.

## 8) Config via Environment Variables

Examples:

```powershell
$env:NIRA_LOCAL_LLM_BASE_URL = "http://127.0.0.1:8080"
$env:NIRA_PERMISSION_DEFAULT = "destructive"
$env:NIRA_PASSPHRASE = "YourStrongPassphrase"
$env:DB_HOST = "localhost"
$env:DB_PORT = "3306"
$env:DB_USER = "root"
$env:DB_PASSWORD = "<your-mysql-password>"
$env:DB_NAME = "nira_agent"
python -m nira_agent
```

SQL defaults in code (if env vars are missing):

```python
{
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
}
```
