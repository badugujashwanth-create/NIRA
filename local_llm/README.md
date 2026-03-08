# local_llm (Windows only)

Local `llama.cpp` inference setup for Windows 10/11 with Python 3.10+.

This setup:
- Downloads official prebuilt Windows binaries from `https://github.com/ggerganov/llama.cpp/releases`
- Downloads a 7B GGUF model (default quant `Q4_K_M`)
- Starts `llama-server.exe` on `127.0.0.1:8080`
- Sends test requests to `http://127.0.0.1:8080/completion`

No manual C++ build, no `make`, no paid APIs.

## Folder Layout

```text
NIRAMini\
  local_llm\
    scripts\
      download_llama_cpp.ps1
      fetch_7b_model.py
    llama_cpp_server.py
    query_example.py
    requirements.txt
```

## 1) Install Python Dependencies

```powershell
cd C:\Users\JASHWANTH\NIRAMini\local_llm
python -m pip install -r .\requirements.txt
```

## 2) Download Official llama.cpp Windows Binaries

```powershell
cd C:\Users\JASHWANTH\NIRAMini\local_llm
powershell -ExecutionPolicy Bypass -File .\scripts\download_llama_cpp.ps1 -Force
```

What this script does:
- Calls GitHub release API for official `ggerganov/llama.cpp` (with redirect-safe fallback).
- Downloads Windows CPU x64 prebuilt zip.
- Extracts into:
  - `C:\Users\JASHWANTH\NIRAMini\local_llm\runtime\`
- Validates:
  - `llama-server.exe`
  - `llama-cli.exe`

Verify binaries:

```powershell
Get-ChildItem .\runtime -Recurse -Filter llama-server.exe
Get-ChildItem .\runtime -Recurse -Filter llama-cli.exe
```

Expected output example:

```text
Directory: C:\Users\JASHWANTH\NIRAMini\local_llm\runtime
Mode   LastWriteTime   Length Name
----   -------------   ------ ----
-a---  ...             ...    llama-server.exe
-a---  ...             ...    llama-cli.exe
```

## 3) Download 7B Q4_K_M GGUF Model

Default model source:
- Repo: `Qwen/Qwen2.5-7B-Instruct-GGUF`
- Quant: `q4_k_m`

```powershell
cd C:\Users\JASHWANTH\NIRAMini\local_llm
python .\scripts\fetch_7b_model.py --quant q4_k_m --out-dir .\models
```

The script validates:
- Extension is `.gguf`
- File exists and is non-empty
- File size passes minimum threshold (default `100 MB` per part)

Find downloaded model path:

```powershell
Get-ChildItem .\models\*.gguf
```

## 4) Start llama.cpp Local Server

```powershell
cd C:\Users\JASHWANTH\NIRAMini\local_llm
$MODEL = (Get-ChildItem .\models\*q4_k_m*.gguf | Sort-Object Name | Select-Object -First 1).FullName
if (-not $MODEL) { throw "No q4_k_m GGUF model found in .\models" }
python .\llama_cpp_server.py --llama-dir .\runtime --model "$MODEL"
```

Server defaults used by `llama_cpp_server.py`:
- `--ctx-size 2048`
- `--host 127.0.0.1`
- `--port 8080`
- `--n-gpu-layers 0`
- `--threads` auto-detected (`CPU count - 2`, min 1)

Expected startup output example:

```text
[info] Starting llama.cpp server with:
       executable : C:\...\local_llm\runtime\llama-server.exe
       model      : C:\...\local_llm\models\...\q4_k_m....gguf
       host       : 127.0.0.1
       port       : 8080
       ctx-size   : 2048
       n-gpu-layers: 0
       threads    : 10
[ok] llama.cpp server is ready at http://127.0.0.1:8080
```

## 5) Test Inference via `/completion`

Open a second Windows terminal:

```powershell
cd C:\Users\JASHWANTH\NIRAMini\local_llm
python .\query_example.py --base-url http://127.0.0.1:8080 --prompt "Explain local LLM inference in 3 lines."
```

Expected output example:

```text
[info] Endpoint: http://127.0.0.1:8080/completion
[info] Prompt: Explain local LLM inference in 3 lines.
[response]
1) ...
2) ...
3) ...
```

## Troubleshooting (Windows)

- Error: `Could not find 'llama-server.exe' under ...`
  - Re-run:
    - `powershell -ExecutionPolicy Bypass -File .\scripts\download_llama_cpp.ps1 -Force`
  - Confirm file:
    - `Get-ChildItem .\runtime -Recurse -Filter llama-server.exe`

- Error: `Model file does not exist: ...`
  - Verify:
    - `Get-ChildItem .\models\*.gguf`
  - Re-run model download:
    - `python .\scripts\fetch_7b_model.py --quant q4_k_m --out-dir .\models`

- Error: `Port 8080 is already in use`
  - Find process:
    - `netstat -ano | findstr :8080`
  - Stop it or use a different port:
    - `python .\llama_cpp_server.py --llama-dir .\runtime --model "$MODEL" --port 8081`

- Slow responses on 16GB RAM
  - Keep `q4_k_m`
  - Keep `ctx-size` at `2048`
  - Do not enable GPU layers on integrated GPU (`--n-gpu-layers 0`)

