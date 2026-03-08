from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import HfHubHTTPError


DEFAULT_REPO_ID = "Qwen/Qwen2.5-7B-Instruct-GGUF"
DEFAULT_QUANT = "q4_k_m"
DEFAULT_MIN_SIZE_MB = 100


def normalize_quant(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def choose_files(repo_id: str, quant: str) -> list[str]:
    api = HfApi()
    info = api.model_info(repo_id)
    gguf_files = sorted(
        sibling.rfilename for sibling in info.siblings if sibling.rfilename.lower().endswith(".gguf")
    )
    if not gguf_files:
        raise RuntimeError(f"No GGUF files found in repo: {repo_id}")

    quant_norm = normalize_quant(quant)
    matches = [name for name in gguf_files if quant_norm in name.lower().replace("-", "_")]
    if not matches:
        raise RuntimeError(
            f"No GGUF file matched quant '{quant}' in {repo_id}. "
            f"Available GGUF files: {', '.join(gguf_files)}"
        )

    # For 16GB RAM target, strongly prefer 7B variants when multiple files match quant.
    seven_b_matches = [name for name in matches if "7b" in name.lower()]
    if seven_b_matches:
        matches = seven_b_matches

    first = matches[0]
    split_marker = re.search(r"^(.*)-\d{5}-of-\d{5}\.gguf$", first, flags=re.IGNORECASE)
    if split_marker:
        prefix = split_marker.group(1)
        part_re = re.compile(rf"^{re.escape(prefix)}-\d{{5}}-of-\d{{5}}\.gguf$", flags=re.IGNORECASE)
        parts = [name for name in matches if part_re.match(name)]
        if not parts:
            raise RuntimeError(f"Detected split GGUF naming but no matching parts found for prefix '{prefix}'.")
        return sorted(parts)

    return [first]


def download_files(repo_id: str, files: list[str], out_dir: Path, min_size_mb: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    min_size_bytes = max(1, min_size_mb) * 1024 * 1024
    for filename in files:
        local_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(out_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        path_obj = Path(local_path)
        if path_obj.suffix.lower() != ".gguf":
            raise RuntimeError(f"Downloaded file has invalid extension (expected .gguf): {path_obj}")
        if not path_obj.exists() or path_obj.stat().st_size <= 0:
            raise RuntimeError(f"Downloaded file is missing or empty: {path_obj}")
        if path_obj.stat().st_size < min_size_bytes:
            raise RuntimeError(
                f"Downloaded file appears too small ({path_obj.stat().st_size} bytes): {path_obj}. "
                f"Expected at least {min_size_mb} MB."
            )
        downloaded.append(path_obj)
    return downloaded


def main() -> int:
    if os.name != "nt":
        print("[error] This script is intended for Windows usage only.", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="Fetch a 7B quantized GGUF model from Hugging Face.")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID, help=f"Model repo (default: {DEFAULT_REPO_ID})")
    parser.add_argument("--quant", default=DEFAULT_QUANT, help=f"Quant selector (default: {DEFAULT_QUANT})")
    parser.add_argument(
        "--min-size-mb",
        type=int,
        default=DEFAULT_MIN_SIZE_MB,
        help=f"Minimum expected file size per GGUF part in MB (default: {DEFAULT_MIN_SIZE_MB}).",
    )
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parents[1] / "models"),
        help="Directory where GGUF file(s) will be saved.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()

    try:
        if "7b" not in args.repo_id.lower():
            print(
                f"[warn] Repo '{args.repo_id}' does not explicitly include '7B' in name. "
                "Proceeding anyway."
            )
        files = choose_files(args.repo_id, args.quant)
        downloaded = download_files(args.repo_id, files, out_dir, args.min_size_mb)
    except HfHubHTTPError as exc:
        print(f"[error] Hugging Face request failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print("[ok] Downloaded model files:")
    for path in downloaded:
        print(f" - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
