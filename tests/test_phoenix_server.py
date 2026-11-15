import socket
import subprocess
import sys
from pathlib import Path

import pytest

from local_ai.observability import server
from local_ai.observability.server import PhoenixError, PidState


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PHOENIX_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PHOENIX_PORT", raising=False)
    monkeypatch.setattr(server, "listening_pid", lambda port: None)


def test_default_port_is_6006(monkeypatch: pytest.MonkeyPatch) -> None:
    assert server.get_port() == 6006


@pytest.mark.parametrize("value", ["abc", "0", "70000"])
def test_invalid_port_raises(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("PHOENIX_PORT", value)
    with pytest.raises(PhoenixError, match="PHOENIX_PORT"):
        server.get_port()


def test_port_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOENIX_PORT", "6100")
    assert server.get_port() == 6100


def test_pid_file_round_trip(tmp_path: Path) -> None:
    paths = server.get_paths()
    assert server.read_pid_file(paths) is None
    server.write_pid_file(paths, 1234, 6006)
    assert server.read_pid_file(paths) == PidState(1234, 6006)
    paths.pid_file.write_text("garbage", encoding="utf-8")
    assert server.read_pid_file(paths) is None


def test_port_in_use_detects_listener() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        assert server.port_in_use(port) is True
    assert server.port_in_use(port) is False


def test_start_fails_without_uvx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server.shutil, "which", lambda name: None)
    assert server.start_main([]) == 1


def test_start_reports_already_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(server.shutil, "which", lambda name: "uvx")
    paths = server.get_paths()
    server.write_pid_file(paths, 999, 6006)
    monkeypatch.setattr(server, "is_ours", lambda pid: True)
    launched: list[object] = []
    monkeypatch.setattr(server.subprocess, "Popen", lambda *a, **k: launched.append(a))
    assert server.start_main([]) == 0
    assert launched == []
    assert "already running" in capsys.readouterr().out


def test_start_removes_stale_pid_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server.shutil, "which", lambda name: "uvx")
    paths = server.get_paths()
    server.write_pid_file(paths, 999, 6006)
    monkeypatch.setattr(server, "is_ours", lambda pid: False)
    monkeypatch.setattr(server, "port_in_use", lambda port: True)
    assert server.start_main([]) == 1
    assert not paths.pid_file.exists()


def test_start_refuses_busy_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server.shutil, "which", lambda name: "uvx")
    monkeypatch.setattr(server, "port_in_use", lambda port: True)
    launched: list[object] = []
    monkeypatch.setattr(server.subprocess, "Popen", lambda *a, **k: launched.append(a))
    assert server.start_main([]) == 1
    assert launched == []


def test_start_launches_detached_and_writes_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server.shutil, "which", lambda name: "uvx")
    monkeypatch.setattr(server, "port_in_use", lambda port: False)
    monkeypatch.setattr(server, "wait_ready", lambda proc, port, timeout: True)
    captured: dict[str, object] = {}

    class FakeProc:
        pid = 4321

    def fake_popen(cmd: list[str], **kwargs: object) -> FakeProc:
        captured["cmd"] = cmd
        captured.update(kwargs)
        return FakeProc()

    monkeypatch.setattr(server.subprocess, "Popen", fake_popen)
    assert server.start_main([]) == 0
    assert captured["cmd"] == ["uvx", "arize-phoenix", "serve"]
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["PHOENIX_HOST"] == "127.0.0.1"
    assert env["PHOENIX_PORT"] == "6006"
    assert env["PHOENIX_TELEMETRY_ENABLED"] == "false"
    assert server.read_pid_file(server.get_paths()) == PidState(4321, 6006)


def test_start_cleans_pid_file_when_phoenix_exits_early(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server.shutil, "which", lambda name: "uvx")
    monkeypatch.setattr(server, "port_in_use", lambda port: False)

    class FakeProc:
        pid = 4321
        returncode = 1

        def poll(self) -> int:
            return 1

    monkeypatch.setattr(server.subprocess, "Popen", lambda *a, **k: FakeProc())
    assert server.start_main([]) == 1
    assert not server.get_paths().pid_file.exists()


def test_stop_when_not_running(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(server, "port_in_use", lambda port: False)
    assert server.stop_main([]) == 0
    assert "not running" in capsys.readouterr().out


def test_stop_warns_and_kills_foreign_listener(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    killed: list[int] = []
    monkeypatch.setattr(server, "port_in_use", lambda port: not killed)
    monkeypatch.setattr(server, "listening_pid", lambda port: 555)
    monkeypatch.setattr(server, "kill_tree", lambda pid: killed.append(pid))
    assert server.stop_main([]) == 0
    assert killed == [555]
    assert "Warning" in capsys.readouterr().err


def test_stop_reports_foreign_listener_it_cannot_identify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "port_in_use", lambda port: True)
    killed: list[int] = []
    monkeypatch.setattr(server, "kill_tree", lambda pid: killed.append(pid))
    assert server.stop_main([]) == 1
    assert killed == []


def test_stop_ignores_pid_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = server.get_paths()
    server.write_pid_file(paths, 999, 6006)
    monkeypatch.setattr(server, "is_ours", lambda pid: False)
    monkeypatch.setattr(server, "port_in_use", lambda port: False)
    killed: list[int] = []
    monkeypatch.setattr(server, "kill_tree", lambda pid: killed.append(pid))
    assert server.stop_main([]) == 0
    assert killed == []
    assert not paths.pid_file.exists()


def test_stop_kills_tree_of_our_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = server.get_paths()
    server.write_pid_file(paths, 999, 6006)
    monkeypatch.setattr(server, "is_ours", lambda pid: True)
    monkeypatch.setattr(server, "port_in_use", lambda port: False)
    killed: list[int] = []
    monkeypatch.setattr(server, "kill_tree", lambda pid: killed.append(pid))
    assert server.stop_main([]) == 0
    assert killed == [999]
    assert not paths.pid_file.exists()
    assert "stopped" in capsys.readouterr().out


def test_process_image_parses_tasklist_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    out = '"uvx.exe","999","Console","1","12,000 K"\n'
    monkeypatch.setattr(server, "IS_WINDOWS", True)
    monkeypatch.setattr(server, "_run", lambda args: out)
    assert server.process_image(999) == "uvx.exe"


def test_process_image_handles_no_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "IS_WINDOWS", True)
    monkeypatch.setattr(server, "_run", lambda args: "INFO: No tasks are running.\n")
    assert server.process_image(999) is None


def test_build_env_forces_localhost_and_no_telemetry(tmp_path: Path) -> None:
    env = server.build_env(server.get_paths(), 6006)
    assert env["PHOENIX_HOST"] == "127.0.0.1"
    assert env["PHOENIX_WORKING_DIR"] == str(tmp_path)
    assert env["PHOENIX_TELEMETRY_ENABLED"] == "false"


def test_kill_tree_terminates_children(tmp_path: Path) -> None:
    if not server.IS_WINDOWS:
        pytest.skip("taskkill-based tree kill is Windows-only")
    child = "import time; time.sleep(60)"
    parent_code = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {child!r}])\n"
        "time.sleep(60)\n"
    )
    parent = subprocess.Popen([sys.executable, "-c", parent_code])
    try:
        server.kill_tree(parent.pid)
        assert parent.wait(timeout=10) != 0
    finally:
        if parent.poll() is None:
            parent.kill()
