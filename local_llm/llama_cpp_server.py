from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import requests


class ServerStartError(RuntimeError):
    pass


def detect_cpu_threads() -> int:
    total = os.cpu_count() or 4
    # Keep 1-2 threads free for system responsiveness on integrated-GPU laptops.
    return max(1, total - 2)


@dataclass
class LlamaServerConfig:
    llama_dir: Path
    model_path: Path
    host: str = "127.0.0.1"
    port: int = 8080
    ctx_size: int = 2048
    n_threads: int = field(default_factory=detect_cpu_threads)
    n_gpu_layers: int = 0
    batch_size: int = 512
    startup_timeout_sec: int = 120
    extra_args: list[str] = field(default_factory=list)


class LlamaCppServer:
    def __init__(self, config: LlamaServerConfig) -> None:
        self.config = config
        self.process: Optional[subprocess.Popen[str]] = None
        self._log_lines: deque[str] = deque(maxlen=60)
        self._log_thread: Optional[threading.Thread] = None
        self._stop_logs = threading.Event()

    def start(self) -> None:
        self._validate()
        if self._is_port_open(self.config.host, self.config.port):
            raise ServerStartError(
                f"Port {self.config.port} is already in use on {self.config.host}. "
                "Stop the existing process or choose another port."
            )

        exe_path = self._find_server_executable(self.config.llama_dir)
        cmd = self._build_command(exe_path)
        print("[info] Starting llama.cpp server with:")
        print(f"       executable : {exe_path}")
        print(f"       model      : {self.config.model_path}")
        print(f"       host       : {self.config.host}")
        print(f"       port       : {self.config.port}")
        print(f"       ctx-size   : {self.config.ctx_size}")
        print(f"       n-gpu-layers: {self.config.n_gpu_layers}")
        print(f"       threads    : {self.config.n_threads}")

        self.process = subprocess.Popen(
            cmd,
            cwd=str(self.config.llama_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self._stop_logs.clear()
        self._log_thread = threading.Thread(target=self._consume_logs, daemon=True)
        self._log_thread.start()

        self._wait_until_ready()

    def stop(self) -> None:
        if not self.process:
            return
        if self.process.poll() is not None:
            return

        self.process.terminate()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        finally:
            self._stop_logs.set()

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def base_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    def _validate(self) -> None:
        if not self.config.llama_dir.exists():
            raise ServerStartError(f"llama.cpp directory does not exist: {self.config.llama_dir}")
        if not self.config.model_path.exists():
            raise ServerStartError(f"Model file does not exist: {self.config.model_path}")
        if self.config.model_path.suffix.lower() != ".gguf":
            raise ServerStartError(f"Model file must be .gguf: {self.config.model_path}")

    def _consume_logs(self) -> None:
        if not self.process or not self.process.stdout:
            return
        while not self._stop_logs.is_set():
            line = self.process.stdout.readline()
            if not line:
                break
            line = line.rstrip()
            if line:
                self._log_lines.append(line)

    def _wait_until_ready(self) -> None:
        started_at = time.time()
        health_url = f"{self.base_url}/health"
        models_url = f"{self.base_url}/v1/models"
        session = requests.Session()

        while time.time() - started_at < self.config.startup_timeout_sec:
            if not self.process:
                break
            if self.process.poll() is not None:
                raise ServerStartError(self._format_start_failure("llama-server exited during startup."))

            if self._endpoint_ok(session, health_url) or self._endpoint_ok(session, models_url):
                return
            time.sleep(0.5)

        raise ServerStartError(self._format_start_failure("Timed out waiting for llama-server readiness."))

    @staticmethod
    def _endpoint_ok(session: requests.Session, url: str) -> bool:
        try:
            response = session.get(url, timeout=2)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def _build_command(self, exe_path: Path) -> list[str]:
        c = self.config
        cmd = [
            str(exe_path),
            "--model",
            str(c.model_path),
            "--host",
            c.host,
            "--port",
            str(c.port),
            "--ctx-size",
            str(c.ctx_size),
            "--threads",
            str(c.n_threads),
            "--batch-size",
            str(c.batch_size),
            "--n-gpu-layers",
            str(c.n_gpu_layers),
        ]
        cmd.extend(c.extra_args)
        return cmd

    @staticmethod
    def _find_server_executable(llama_dir: Path) -> Path:
        candidates = list(llama_dir.rglob("llama-server.exe"))
        if not candidates:
            raise ServerStartError(
                f"Could not find 'llama-server.exe' under: {llama_dir}"
            )
        return candidates[0]

    @staticmethod
    def _is_port_open(host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            return sock.connect_ex((host, port)) == 0

    def _format_start_failure(self, msg: str) -> str:
        log_tail = "\n".join(self._log_lines) if self._log_lines else "(no output captured)"
        return f"{msg}\nRecent llama-server output:\n{log_tail}"


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a local llama.cpp HTTP server.")
    parser.add_argument("--llama-dir", required=True, help="Path to extracted llama.cpp binaries.")
    parser.add_argument("--model", required=True, help="Path to GGUF model file.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--ctx-size", type=int, default=2048, help="Context size (default: 2048)")
    parser.add_argument("--threads", type=int, default=detect_cpu_threads(), help="CPU threads")
    parser.add_argument("--n-gpu-layers", type=int, default=0, help="GPU layers (default: 0 for CPU)")
    parser.add_argument("--batch-size", type=int, default=512, help="Batch size")
    parser.add_argument("--startup-timeout", type=int, default=120, help="Startup timeout in seconds")
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Additional argument passed to llama-server (repeatable).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    config = LlamaServerConfig(
        llama_dir=Path(args.llama_dir).expanduser().resolve(),
        model_path=Path(args.model).expanduser().resolve(),
        host=args.host,
        port=args.port,
        ctx_size=args.ctx_size,
        n_threads=args.threads,
        n_gpu_layers=args.n_gpu_layers,
        batch_size=args.batch_size,
        startup_timeout_sec=args.startup_timeout,
        extra_args=list(args.extra_arg),
    )

    server = LlamaCppServer(config)

    def handle_signal(_signum, _frame) -> None:
        print("\n[info] Stopping server...")
        server.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    try:
        server.start()
    except ServerStartError as exc:
        print(f"[error] {exc}")
        return 1
    except Exception as exc:
        print(f"[error] Unexpected failure: {exc}")
        return 1

    print(f"[ok] llama.cpp server is ready at {server.base_url}")
    print("[info] Press Ctrl+C to stop.")
    try:
        while server.is_running():
            time.sleep(1)
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
