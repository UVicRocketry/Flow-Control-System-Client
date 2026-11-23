"""End-to-end smoke test exercising the live Server <-> Client protocol.

Spawns the real `Flow-Control-System-Server` (`contents/code/main.py --mock`)
as a subprocess and connects the real `Flow-Control-System-Client` `Backend`
over a real `QWebSocket` + `QNetworkAccessManager` HTTP `/api/data` transport.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    _prefix_bin = Path(sys.prefix) / "bin"
    if _prefix_bin.exists():
        os.add_dll_directory(str(_prefix_bin))

CLIENT_REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = str(CLIENT_REPO_ROOT / "contents" / "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from PySide6 import QtCore  # noqa: E402

import backend as backend_mod  # noqa: E402
import config_manager  # noqa: E402
import config_store  # noqa: E402
import log_manager  # noqa: E402
import telemetry_files  # noqa: E402
import telemetry_store  # noqa: E402


def _resolve_server_repo() -> Path | None:
    env_override = os.environ.get("FCS_SERVER_REPO", "").strip()
    candidates = [
        Path(env_override) if env_override else None,
        CLIENT_REPO_ROOT.parent / "Flow-Control-System-Server",
    ]
    for candidate in candidates:
        if candidate and (candidate / "contents" / "code" / "main.py").is_file():
            return candidate
    return None


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _temp_config_patch_stack(tmp_path: Path) -> ExitStack:
    cfg_dir = tmp_path / "config"
    graphs_dir = cfg_dir / "graphs"
    data_dir = cfg_dir / "data"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    graphs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    src_cfg = CLIENT_REPO_ROOT / "contents" / "config" / "config.json"
    src_graphs = CLIENT_REPO_ROOT / "contents" / "config" / "graphs" / "graphs.json"
    cfg_file = cfg_dir / "config.json"
    graphs_file = graphs_dir / "graphs.json"
    if src_cfg.exists():
        shutil.copy2(src_cfg, cfg_file)
    if src_graphs.exists():
        shutil.copy2(src_graphs, graphs_file)

    stack = ExitStack()
    for mod in (
        config_manager,
        config_store,
        log_manager,
        telemetry_files,
        telemetry_store,
    ):
        if hasattr(mod, "CONFIG_DIR"):
            stack.enter_context(mock.patch.object(mod, "CONFIG_DIR", cfg_dir))
        if hasattr(mod, "CONFIG_FILE"):
            stack.enter_context(mock.patch.object(mod, "CONFIG_FILE", cfg_file))
        if hasattr(mod, "GRAPHS_CONFIG_DIR"):
            stack.enter_context(mock.patch.object(mod, "GRAPHS_CONFIG_DIR", graphs_dir))
        if hasattr(mod, "GRAPHS_CONFIG_FILE"):
            stack.enter_context(
                mock.patch.object(mod, "GRAPHS_CONFIG_FILE", graphs_file)
            )
    return stack


def _wait_until(
    app: QtCore.QCoreApplication,
    predicate,
    timeout_s: float = 5.0,
    description: str = "condition",
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(f"Timed out after {timeout_s:.1f}s waiting for {description}")


class _MockServerProcess:
    """Starts and cleanly tears down the real Flow-Control-System-Server."""

    def __init__(self, server_repo: Path, port: int, data_dir: Path) -> None:
        self.server_repo = server_repo
        self.port = port
        self.data_dir = data_dir
        self.proc: subprocess.Popen[str] | None = None

    @property
    def ws_url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/ws"

    @property
    def http_health_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/data"

    def __enter__(self) -> _MockServerProcess:
        cmd = [
            sys.executable,
            str(self.server_repo / "contents" / "code" / "main.py"),
            "--mock",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--rate",
            "50",
            "--transit-delay",
            "0.05",
            "--data-dir",
            str(self.data_dir),
            "--log-level",
            "WARNING",
        ]
        self.proc = subprocess.Popen(
            cmd,
            cwd=str(self.server_repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._wait_ready()
        return self

    def _wait_ready(self, timeout_s: float = 10.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            assert self.proc is not None
            if self.proc.poll() is not None:
                output = self.proc.stdout.read() if self.proc.stdout else ""
                raise RuntimeError(
                    f"Server exited prematurely (code {self.proc.returncode}):\n{output}"
                )
            try:
                with urllib.request.urlopen(self.http_health_url, timeout=0.5) as resp:
                    if resp.status == 200:
                        return
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.05)
        raise TimeoutError(
            f"Server did not become ready at {self.http_health_url} within {timeout_s}s"
        )

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2.0)
        if self.proc.stdout is not None:
            self.proc.stdout.close()


class TestServerClientE2ESmoke(unittest.TestCase):
    """End-to-end smoke test verifying real Server <-> Client interaction."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server_repo = _resolve_server_repo()
        if cls.server_repo is None:
            raise unittest.SkipTest(
                "Sibling Flow-Control-System-Server repo not found "
                "(set FCS_SERVER_REPO to enable E2E smoke tests)."
            )
        missing = [
            mod
            for mod in ("fastapi", "uvicorn", "PySide6.QtWebSockets")
            if importlib.util.find_spec(mod) is None
        ]
        if missing:
            raise unittest.SkipTest(
                f"Missing dependencies for E2E smoke test: {', '.join(missing)}"
            )
        cls.app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])

    def _assert_handshake_and_telemetry(
        self, client: backend_mod.Backend, logs: list[tuple[str, str]]
    ) -> None:
        _wait_until(
            self.app,
            lambda: (
                client.armed
                and bool(client.valve_definitions)
                and any(
                    ch.get("key") == "P_RUN_TANK" for ch in client.available_channels
                )
            ),
            description="server init handshake",
        )
        valve_ids = {v["id"] for v in client.valve_definitions}
        self.assertTrue({"N2OV", "DUMP", "RTV", "QD", "MEV", "MRV"}.issubset(valve_ids))
        self.assertEqual(client.get_channel_meta("P_RUN_TANK").get("unit"), "kPa")
        self.assertEqual(client.get_channel_meta("M_RUN_TANK").get("unit"), "kg")
        self.assertEqual(client.get_channel_meta("T_RUN_TANK").get("unit"), "°C")
        _wait_until(
            self.app,
            lambda: any("MOCK SIMULATION" in msg for _lvl, msg in logs),
            description="mock mode connect alert",
        )

        _wait_until(
            self.app,
            lambda: int(client.telemetry.get("packet_id", 0)) >= 3,
            description="live telemetry frames",
        )
        series = client.get_channel_data("live", "P_RUN_TANK", 0.0, 60.0)
        self.assertGreaterEqual(len(series.get("vs", [])), 1)
        self.assertGreaterEqual(int(series.get("rawCount", 0)), 1)

    def _assert_actuation_abort_and_interlocks(
        self, client: backend_mod.Backend, ws, logs: list[tuple[str, str]]
    ) -> None:
        seen_states: list[tuple[str, str]] = []
        client.valve_state_updated.connect(
            lambda vid, st: seen_states.append((vid, st))
        )

        client.actuate_valve("N2OV", "OPEN")
        _wait_until(
            self.app,
            lambda: client.valves.get("N2OV") == "OPEN",
            description="N2OV open transit completion",
        )
        self.assertIn(("N2OV", "ACTUATING"), seen_states)

        client.abort()
        _wait_until(
            self.app,
            lambda: (
                client.valves.get("N2OV") == "CLOSED"
                and client.valves.get("DUMP") == "OPEN"
                and client.valves.get("RTV") == "VENT"
                and any("EMERGENCY ABORT executed" in msg for _lvl, msg in logs)
            ),
            description="emergency abort valve states and alert",
        )

        ws.sendTextMessage(json.dumps({"type": "safe"}))
        _wait_until(self.app, lambda: not client.armed, description="SAFE interlock sync")
        client.actuate_valve("N2OV", "OPEN")
        self.assertEqual(client.valves.get("N2OV"), "CLOSED")

        ws.sendTextMessage(json.dumps({"type": "arm"}))
        _wait_until(self.app, lambda: client.armed, description="ARM interlock sync")

    def _assert_recording_and_http_crud(
        self,
        client: backend_mod.Backend,
        server_data_dir: Path,
        client_data_dir: Path,
    ) -> None:
        client.set_recording(True)
        start_pkt = int(client.telemetry.get("packet_id", 0))
        _wait_until(
            self.app,
            lambda: int(client.telemetry.get("packet_id", 0)) >= start_pkt + 3,
            description="samples recorded on server",
        )
        client.set_recording(False)

        _wait_until(
            self.app,
            lambda: len(client.remote_data) >= 1,
            description="recorded file in remote_data",
        )
        recorded_name = client.remote_data[0]
        server_csv = server_data_dir / recorded_name
        self.assertTrue(server_csv.is_file())
        lines = server_csv.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 3)
        self.assertIn("P_RUN_TANK", lines[1])

        local_copy = client_data_dir / recorded_name
        if local_copy.exists():
            local_copy.unlink()
        client.refresh_local_data()
        self.assertNotIn(recorded_name, client.local_data)

        client.download_remote_data(recorded_name)
        _wait_until(
            self.app,
            lambda: recorded_name in client.local_data,
            description="HTTP download of recorded CSV",
        )
        self.assertEqual(local_copy.read_bytes(), server_csv.read_bytes())

        renamed = "e2e_smoke_renamed.csv"
        self.assertTrue(client.rename_data("remote", recorded_name, renamed))
        _wait_until(
            self.app,
            lambda: (
                (server_data_dir / renamed).is_file()
                and not (server_data_dir / recorded_name).exists()
                and renamed in client.remote_data
            ),
            description="HTTP rename of remote CSV",
        )

        self.assertTrue(client.delete_data("remote", renamed))
        _wait_until(
            self.app,
            lambda: (
                not (server_data_dir / renamed).exists()
                and renamed not in client.remote_data
            ),
            description="HTTP delete of remote CSV",
        )

    def test_full_session_handshake_telemetry_actuation_abort_and_http_crud(
        self,
    ) -> None:
        from PySide6 import QtWebSockets

        port = _find_free_port()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            server_data_dir = tmp_path / "server_data"
            server_data_dir.mkdir(parents=True, exist_ok=True)
            client_data_dir = tmp_path / "config" / "data"

            with (
                _MockServerProcess(self.server_repo, port, server_data_dir) as srv,
                _temp_config_patch_stack(tmp_path),
            ):
                client = backend_mod.Backend()
                client.server_url = srv.ws_url

                logs: list[tuple[str, str]] = []
                disconnected_flag: list[bool] = []
                client.log_sent.connect(lambda lvl, msg: logs.append((lvl, msg)))
                client.disconnected.connect(lambda: disconnected_flag.append(True))

                ws = QtWebSockets.QWebSocket()
                ws.connected.connect(lambda: client.on_ws_connected_changed(True))
                ws.disconnected.connect(lambda: client.on_ws_connected_changed(False))
                ws.textMessageReceived.connect(client.ingest_ws_message)
                client.ws_send_requested.connect(ws.sendTextMessage)

                ws.open(QtCore.QUrl(srv.ws_url))
                try:
                    self._assert_handshake_and_telemetry(client, logs)
                    self._assert_actuation_abort_and_interlocks(client, ws, logs)
                    self._assert_recording_and_http_crud(
                        client, server_data_dir, client_data_dir
                    )
                finally:
                    ws.close()
                    _wait_until(
                        self.app,
                        lambda: bool(disconnected_flag) and not client.armed,
                        description="graceful WebSocket disconnect",
                    )


if __name__ == "__main__":
    unittest.main()
