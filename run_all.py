"""Run the OpsPilot/ashboard stack with one command: backend (uvicorn + SQLite) and frontend (vite).

Usage:
    python run_all.py            # run both servers (Ctrl+C stops both)
    python run_all.py --smoke    # start both, verify they are healthy, then exit
    BACKEND_PORT=8000-ish        # env BACKEND_PORT / FRONTEND_PORT override the defaults
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

BACKEND_PORT = os.environ.get("BACKEND_PORT", "8000")
FRONTEND_PORT = os.environ.get("FRONTEND_PORT", "8080")
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"
SMOKE = "--smoke" in sys.argv

_info: dict[str, str] = {"frontend_url": FRONTEND_URL}
_stop = threading.Event()


def find_backend_python() -> str:
    """Prefer the project venv so all backend deps resolve."""
    candidate = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def port_open(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def backend_healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def spawn(label: str, cmd: list[str], cwd: Path) -> subprocess.Popen:
    """Start a server process in its own process group so Ctrl+C cleanup can kill the whole tree."""
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )

    def pump() -> None:
        stream = proc.stdout
        while stream and not _stop.is_set():
            raw = stream.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").rstrip()
            if label == "frontend":
                match = re.search(r"Local:\s*https?://[^\s\x1b]+", line)
                if match:
                    _info["frontend_url"] = match.group(0).split()[-1]
            print(f"[{label}] {line}", flush=True)
        print(f"[{label}] stopped", flush=True)

    threading.Thread(target=pump, daemon=True).start()
    return proc


def kill_tree(proc: subprocess.Popen) -> None:
    """Kill a process and all of its children (Windows-safe)."""
    if proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.terminate()
        proc.wait(timeout=10)


def wait_healthy(label: str, probe, timeout: float, process: subprocess.Popen) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            print(f"[{label}] exited early with code {process.returncode}", flush=True)
            return False
        if probe():
            return True
        time.sleep(1.0)
    return False


def cleanup(procs: list[subprocess.Popen]) -> None:
    _stop.set()
    for proc in reversed(procs):
        kill_tree(proc)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        print("Node/npm not found on PATH; npm run dev cannot start.", file=sys.stderr)
        return 2
    os.environ["BROWSER"] = "none"

    print(f"Starting OpsPilot stack  (SQL database: {BACKEND_DIR / 'opspilot.db'})\n", flush=True)

    backend = spawn(
        "backend",
        [find_backend_python(), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", BACKEND_PORT],
        BACKEND_DIR,
    )
    frontend = spawn(
        "frontend",
        [npm, "run", "dev", "--", "--port", FRONTEND_PORT, "--strictPort"],
        FRONTEND_DIR,
    )
    procs = [frontend, backend]

    ok_backend = wait_healthy("backend", backend_healthy, timeout=60.0, process=backend)
    ok_frontend = wait_healthy(
        "frontend",
        lambda: port_open(_info["frontend_url"]),
        timeout=90.0,
        process=frontend,
    )

    print("", flush=True)
    if ok_backend and ok_frontend:
        print(f"  backend  ready  ->  {BACKEND_URL}      (API docs: {BACKEND_URL}/docs)", flush=True)
        print(f"  frontend ready  ->  {_info['frontend_url']}", flush=True)
        if SMOKE:
            print("  smoke check passed; shutting down.", flush=True)
            cleanup(procs)
            return 0
        print("  Press Ctrl+C here to stop both servers.\n", flush=True)
    else:
        print("A server failed to start; see logs above. Shutting down both.", file=sys.stderr)
        cleanup(procs)
        return 1

    try:
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping servers...", flush=True)
    finally:
        cleanup(procs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
