from __future__ import annotations

import argparse
import requests


def query_completion(base_url: str, prompt: str, timeout_sec: int = 60) -> str:
    url = f"{base_url.rstrip('/')}/completion"
    payload = {
        "prompt": f"User: {prompt}\nAssistant:",
        "temperature": 0.2,
        "n_predict": 256,
    }
    response = requests.post(url, json=payload, timeout=timeout_sec)
    response.raise_for_status()
    data = response.json()
    text = data.get("content") or data.get("choices", [{}])[0].get("text", "")
    text = str(text).strip()
    if not text:
        raise RuntimeError("Empty response from /completion")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Query local llama.cpp server.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--prompt",
        default="Give me 3 bullet points on why local LLM inference is useful.",
        help="Prompt text sent to /completion.",
    )
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    print(f"[info] Endpoint: {args.base_url.rstrip('/')}/completion")
    print(f"[info] Prompt: {args.prompt}")

    try:
        reply = query_completion(base_url=args.base_url, prompt=args.prompt, timeout_sec=args.timeout)
    except requests.RequestException as exc:
        print(f"[error] Could not reach local server: {exc}")
        return 1
    except Exception as exc:
        print(f"[error] {exc}")
        return 1

    print("[response]")
    print(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
