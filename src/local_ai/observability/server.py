"""Start and stop the local Arize Phoenix server (UI on http://localhost:6006).

Phoenix is launched with uvx and is not a project dependency. The server runs detached; the
PID of the uvx process (the root of the process tree) is kept in a PID file in the data
directory, so that phoenix-stop can find and terminate it.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

HOST = "127.0.0.1"
DEFAULT_PORT = 6006
DEFAULT_TIMEOUT = 120.0
IS_WINDOWS = sys.platform == "win32"
# Process images that phoenix-start may have created; guards against PID reuse.
LAUNCHER_IMAGES = frozenset({"uvx.exe", "uv.exe", "uvx", "uv"})


class PhoenixError(RuntimeError):
    """Operational failure with a message meant for the user."""


class Paths(NamedTuple):
    data_dir: Path
    pid_file: Path
    log_file: Path


class PidState(NamedTuple):
    pid: int
    port: int


def get_paths() -> Paths:
    raw = os.environ.get("PHOENIX_DATA_DIR", "").strip()
    data_dir = Path(raw) if raw else Path.home() / ".local" / "share" / "finances-ai" / "phoenix"
    return Paths(data_dir, data_dir / "phoenix.pid", data_dir / "phoenix.log")


def get_port() -> int:
    raw = os.environ.get("PHOENIX_PORT", "").strip() or str(DEFAULT_PORT)
    try:
        port = int(raw)
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        raise PhoenixError(f"PHOENIX_PORT must be a port number from 1 to 65535, got {raw!r}.")
    return port


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((HOST, port)) == 0


def _run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=False).stdout


def process_image(pid: int) -> str | None:
    """Lower-case image name of a live process, or None if no such process exists."""
    if IS_WINDOWS:
        out = _run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"])
        rows = list(csv.reader(out.splitlines()))
        # A "no tasks" message has a single column, so check the PID column explicitly.
        if rows and len(rows[0]) > 1 and rows[0][1] == str(pid):
            return rows[0][0].lower()
        return None
    out = _run(["ps", "-p", str(pid), "-o", "comm="]).strip()
    return Path(out).name.lower() if out else None


def is_ours(pid: int) -> bool:
    return process_image(pid) in LAUNCHER_IMAGES


def kill_tree(pid: int) -> None:
    """Terminate a process and all of its children."""
    if IS_WINDOWS:
        # /T kills the child processes (uvx starts Phoenix); /F forces it, since the
        # detached process has no console window to receive a graceful signal.
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)  # started with start_new_session=True
    except ProcessLookupError:
        pass


def listening_pid(port: int) -> int | None:
    """PID that owns the listening socket on the port, for diagnostics only."""
    if not IS_WINDOWS:
        return None
    for line in _run(["netstat", "-ano", "-p", "TCP"]).splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(f":{port}"):
            return int(parts[4])
    return None


def read_pid_file(paths: Paths) -> PidState | None:
    try:
        data = json.loads(paths.pid_file.read_text(encoding="utf-8"))
        return PidState(int(data["pid"]), int(data["port"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_pid_file(paths: Paths, pid: int, port: int) -> None:
    paths.pid_file.write_text(json.dumps({"pid": pid, "port": port}), encoding="utf-8")


def port_conflict(port: int, reason: str) -> PhoenixError:
    owner = listening_pid(port)
    who = f" (PID {owner})" if owner else ""
    return PhoenixError(f"Port {port} is {reason}{who}. Free it or set PHOENIX_PORT.")


def build_env(paths: Paths, port: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        PHOENIX_WORKING_DIR=str(paths.data_dir),
        PHOENIX_HOST=HOST,
        PHOENIX_PORT=str(port),
        PHOENIX_TELEMETRY_ENABLED="false",
    )
    return env


def wait_ready(proc: subprocess.Popen[bytes], port: int, timeout: float) -> bool:
    """Poll the server until it answers, returns False on timeout, raises if it exits."""
    deadline = time.monotonic() + timeout
    url = f"http://{HOST}:{port}/healthz"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise PhoenixError(f"Phoenix exited with code {proc.returncode}. See the log.")
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    return False


def start(foreground: bool, timeout: float) -> int:
    port, paths = get_port(), get_paths()
    uvx = shutil.which("uvx")
    if uvx is None:
        raise PhoenixError("'uvx' was not found. Install uv: https://docs.astral.sh/uv/")
    paths.data_dir.mkdir(parents=True, exist_ok=True)

    state = read_pid_file(paths)
    if state is not None:
        if is_ours(state.pid):
            print(f"Phoenix is already running (PID {state.pid}): http://localhost:{state.port}")
            return 0
        paths.pid_file.unlink(missing_ok=True)  # stale PID file

    if port_in_use(port):
        raise port_conflict(port, "in use by a process not started by phoenix-start")

    cmd = [uvx, "arize-phoenix", "serve"]
    env = build_env(paths, port)

    if foreground:
        proc = subprocess.Popen(cmd, env=env)
        write_pid_file(paths, proc.pid, port)
        try:
            return proc.wait()
        except KeyboardInterrupt:
            kill_tree(proc.pid)
            return 130
        finally:
            paths.pid_file.unlink(missing_ok=True)

    kwargs: dict[str, object] = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    with paths.log_file.open("ab") as log:
        proc = subprocess.Popen(
            cmd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **kwargs
        )
    write_pid_file(paths, proc.pid, port)

    try:
        ready = wait_ready(proc, port, timeout)
    except PhoenixError:
        paths.pid_file.unlink(missing_ok=True)
        raise
    if ready:
        print(f"Phoenix started (PID {proc.pid}): http://localhost:{port}")
        print(f"Data: {paths.data_dir}")
    else:
        # The first uvx run downloads Phoenix, which can take minutes. The PID file is kept,
        # so phoenix-stop still works.
        print(f"Phoenix is still starting (PID {proc.pid}). Log: {paths.log_file}")
    return 0


def _wait_port_free(port: int, timeout: float = 10.0) -> bool:
    """Wait for the socket to close after a kill; False if it is still busy at the deadline."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not port_in_use(port):
            return True
        time.sleep(0.5)
    return not port_in_use(port)


def stop() -> int:
    port, paths = get_port(), get_paths()
    state = read_pid_file(paths)
    if state is not None and is_ours(state.pid):
        kill_tree(state.pid)
        paths.pid_file.unlink(missing_ok=True)
        if not _wait_port_free(state.port):
            raise PhoenixError(f"Port {state.port} is still in use after stopping Phoenix.")
        print("Phoenix stopped.")
        return 0

    paths.pid_file.unlink(missing_ok=True)  # absent or stale
    if not port_in_use(port):
        print("Phoenix is not running.")
        return 0

    # The port is held by a process this session did not start (for example a server left
    # over from an earlier session). Warn, then stop that process and its children.
    owner = listening_pid(port)
    if owner is None:
        raise port_conflict(port, "in use by a process not started by phoenix-start")
    print(
        f"Warning: port {port} is held by PID {owner}, which was not started by "
        "phoenix-start in this session. Stopping it.",
        file=sys.stderr,
    )
    kill_tree(owner)
    if not _wait_port_free(port):
        raise PhoenixError(f"Port {port} is still in use after stopping PID {owner}.")
    print("Stopped the process that was holding the port.")
    return 0


def _run_command(action: Callable[[], int]) -> int:
    try:
        return action()
    except PhoenixError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def start_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="phoenix-start", description="Start the local Phoenix server."
    )
    parser.add_argument(
        "--foreground", action="store_true", help="run in this terminal (Ctrl+C stops it)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="seconds to wait until the server answers (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    return _run_command(lambda: start(args.foreground, args.timeout))


def stop_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="phoenix-stop", description="Stop the Phoenix server started by phoenix-start."
    )
    parser.parse_args(argv)
    return _run_command(stop)
