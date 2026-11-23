"""Phase 4 unit tests for split client controllers, ring buffer, and HTTP log URLs."""

import ast
import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    _prefix_bin = Path(sys.prefix) / "bin"
    if _prefix_bin.exists():
        os.add_dll_directory(str(_prefix_bin))

CODE_DIR = str(Path(__file__).resolve().parents[1] / "contents" / "code")
REPO_ROOT = Path(__file__).resolve().parents[1]
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from PySide6 import QtCore  # noqa: E402

import backend as backend_mod  # noqa: E402
import camera_controller  # noqa: E402
import config_manager  # noqa: E402
import config_store  # noqa: E402
import connection_finder  # noqa: E402
import log_manager  # noqa: E402
import telemetry_files  # noqa: E402
import telemetry_store  # noqa: E402
from actuator_controller import ActuatorController  # noqa: E402
from camera_controller import CameraController  # noqa: E402
from config_store import ConfigStore  # noqa: E402
from log_manager import LogManager, build_api_data_url, ws_url_to_http_base  # noqa: E402
from telemetry_series import (  # noqa: E402
    ColumnarTelemetryBuffer,
    ingest_ws_telemetry_frames,
)


def _temp_config_patch_stack(tmp_path: Path) -> ExitStack:
    cfg_dir = tmp_path / "config"
    graphs_dir = cfg_dir / "graphs"
    data_dir = cfg_dir / "data"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    graphs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    src_cfg = REPO_ROOT / "contents" / "config" / "config.json"
    src_graphs = REPO_ROOT / "contents" / "config" / "graphs" / "graphs.json"
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


class TestHttpUrlAndConfigStore(unittest.TestCase):
    """Tests /api/data URL building, ConfigStore min_log_level, and path cleanup."""

    def test_ws_url_to_http_and_api_data_url(self) -> None:
        self.assertEqual(
            ws_url_to_http_base("ws://192.168.0.1:8080/ws"),
            "http://192.168.0.1:8080",
        )
        self.assertEqual(
            ws_url_to_http_base("wss://cart.local/ws"),
            "https://cart.local",
        )
        self.assertEqual(
            build_api_data_url("ws://127.0.0.1:8080/ws"),
            "http://127.0.0.1:8080/api/data",
        )
        self.assertEqual(
            build_api_data_url("ws://127.0.0.1:8080/ws", "run 1.csv"),
            "http://127.0.0.1:8080/api/data/run%201.csv",
        )
        self.assertEqual(
            build_api_data_url("ws://127.0.0.1:8080/ws", "run_1.csv", action="rename"),
            "http://127.0.0.1:8080/api/data/run_1.csv/rename",
        )

    def test_config_store_min_log_level_persistence_and_legacy_cleanup(self) -> None:
        src = inspect.getsource(telemetry_files.resolve_data_file)
        self.assertNotIn("PDP-Ground-Support-Rewrite", src)

        with tempfile.TemporaryDirectory() as tmpdir:
            with _temp_config_patch_stack(Path(tmpdir)):
                store = ConfigStore(LogManager())
                store.load_config()
                self.assertEqual(store.min_log_level, "INFO")

                store.min_log_level = "warn"
                self.assertEqual(store.min_log_level, "WARN")
                store.min_log_level = "BOGUS"
                self.assertEqual(store.min_log_level, "WARN")

                reloaded = ConfigStore(LogManager())
                reloaded.load_config()
                self.assertEqual(reloaded.min_log_level, "WARN")


class TestRingBufferAndColumnarSeries(unittest.TestCase):
    """Tests bounded live ring buffer eviction and columnar series math."""

    def test_ingest_ring_buffer_trim_and_columnar_filtering(self) -> None:
        known: dict = {}
        recs: list = []
        secs: list = []
        frames = [
            {"type": "telemetry", "seconds": float(i), "PT1": float(i)}
            for i in range(15)
        ]
        _, ingested, _, latest = ingest_ws_telemetry_frames(
            frames, known, recs, secs, None, {}, max_live_samples=10
        )
        self.assertEqual(len(ingested), 15)
        self.assertEqual(len(recs), 10)
        self.assertEqual(len(secs), 10)
        self.assertEqual(secs[0], 5.0)
        self.assertEqual(recs[0]["values"]["PT1"], 5.0)
        self.assertEqual(latest["values"]["PT1"], 14.0)

        buf = ColumnarTelemetryBuffer(max_samples=12)
        samples = [
            {"t": float(i), "values": {"P_RUN_TANK": 100.0 if i != 5 else 9999.0}}
            for i in range(11)
        ]
        buf.append_records(samples)
        series = buf.query_series(
            "P_RUN_TANK",
            t_start=0.0,
            t_end=10.0,
            max_buckets=15,
            filter_outliers_3std=True,
            smoothing_window=3,
        )
        self.assertEqual(series["rawCount"], 11)
        self.assertEqual(series["filteredCount"], 10)
        self.assertAlmostEqual(series["mean"], 100.0, places=4)


class TestSplitControllersAndBackendFacade(unittest.TestCase):
    """Tests __feature__ removal, ActuatorController, TelemetryStore, and Backend."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])

    def test_actuator_controller_interlocks_and_abort(self) -> None:
        ctrl = ActuatorController()
        ctrl.apply_actuator_definitions(
            [
                {"id": "N2OV", "normal_state": "CLOSED"},
                {"id": "MRV", "normal_state": "READY", "external": True},
                {"id": "QD", "normal_state": "CONNECTED", "single_use": True},
            ]
        )
        sent: list[dict] = []
        warns: list[str] = []

        def send_ws(raw: str) -> None:
            sent.append(json.loads(raw))

        self.assertFalse(ctrl.actuate_valve("N2OV", "OPEN", send_ws, warns.append))
        ctrl.abort(send_ws, warns.append)
        self.assertEqual(sent[-1]["type"], "abort")

        ctrl.armed = True
        self.assertFalse(ctrl.actuate_valve("MRV", "FIRE", send_ws, warns.append))
        self.assertTrue(ctrl.actuate_valve("QD", "DISCONNECT", send_ws, warns.append))
        ctrl.apply_valve_state("QD", "DISCONNECTED")
        self.assertFalse(ctrl.actuate_valve("QD", "CONNECT", send_ws, warns.append))

    def test_backend_facade_no_feature_and_init_channels(self) -> None:
        self.assertNotIn("PySide6.QtWidgets", sys.modules)
        self.assertTrue(hasattr(QtCore.QObject, "setObjectName"))
        self.assertFalse(hasattr(QtCore.QObject, "set_object_name"))
        for py_path in Path(CODE_DIR).glob("*.py"):
            tree = ast.parse(py_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "__feature__", str(py_path))
                elif isinstance(node, ast.Import):
                    self.assertNotIn(
                        "__feature__",
                        [alias.name for alias in node.names],
                        str(py_path),
                    )

        with tempfile.TemporaryDirectory() as tmpdir:
            with _temp_config_patch_stack(Path(tmpdir)):
                be = backend_mod.Backend()
                self.assertEqual(be.min_log_level, "INFO")
                be.set_min_log_level("ERR")
                self.assertEqual(be.min_log_level, "ERR")

                be.ingest_ws_message(
                    json.dumps(
                        {
                            "type": "init",
                            "armed": True,
                            "valves": {"N2OV": "OPEN"},
                            "channels": {"P_CUSTOM": {"unit": "psi", "pin": "AIN90"}},
                        }
                    )
                )
                self.assertTrue(be.armed)
                self.assertEqual(be.valves["N2OV"], "OPEN")
                meta = be.get_channel_meta("P_CUSTOM")
                self.assertEqual(meta["allowed_units"], ["kPa", "psi"])

                be.ingest_ws_message(
                    json.dumps(
                        {
                            "type": "telemetry",
                            "seconds": 1.0,
                            "P_CUSTOM": 100.0,
                        }
                    )
                )
                res = be.get_channel_data(
                    "live", "P_CUSTOM", 0.0, 2.0, 50, False, 1, "kPa"
                )
                self.assertAlmostEqual(res["mean"], 689.47572932, places=3)

    def test_telemetry_store_parsed_dataclass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            csv_path = tmp_path / "sample.csv"
            csv_path.write_text(
                "kPa,s\nP_RUN_TANK,seconds\n100.0,0.0\n200.0,1.0\n",
                encoding="utf-8",
            )
            with _temp_config_patch_stack(tmp_path):
                logs = LogManager()
                cfg = ConfigStore(logs)
                cfg.load_config()
                store = telemetry_store.TelemetryStore(cfg, logs)

                meta = store.load_resolved_file("local", "sample.csv", csv_path)
                self.assertEqual(meta["name"], "sample.csv")
                self.assertEqual(meta["source"], "local")
                self.assertEqual(meta["count"], 2)
                self.assertEqual(store.loaded_meta, meta)
                self.assertEqual(store.loaded_meta["units"], {"P_RUN_TANK": "kPa"})

                parsed = telemetry_store._ParsedTelemetryFile(
                    mode="external",
                    target=str(csv_path),
                    resolved_path=str(csv_path),
                    records=[{"t": 0.0, "values": {"P_RUN_TANK": 100.0}}],
                    seconds=[0.0],
                    columns=["P_RUN_TANK"],
                    csv_units={"P_RUN_TANK": "kPa"},
                )
                store._apply_parsed_telemetry(parsed)
                self.assertEqual(store.loaded_meta["source"], "external")
                self.assertEqual(store.loaded_meta["count"], 1)


class TestConnectionFinderAndAutoManualModes(unittest.TestCase):
    """Tests connection_finder.autodiscover, WS auto/manual mode, and camera integration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])

    def test_autodiscover_ws_and_rtsp_subnet_localhost_and_fallback(self) -> None:
        with (
            mock.patch.object(
                connection_finder,
                "_collect_network_state",
                return_value=(["192.168.0.", "192.168.1."], {"192.168.0.10"}, True),
            ),
            mock.patch.object(
                connection_finder, "_read_arp_neighbors", return_value=[]
            ),
        ):
            # 1. Discovered on 192.168.0/1.* fast pass
            with mock.patch.object(
                connection_finder,
                "_probe_hosts",
                side_effect=lambda cands, port, timeout=0.15, deadline=None: (
                    "192.168.1.1" if port == 8080 and "192.168.1.1" in cands else None
                ),
            ):
                self.assertEqual(
                    connection_finder.autodiscover("ws"), "ws://192.168.1.1:8080/ws"
                )

            # 2. Subnet sweep finds camera on 192.168.0.55 after fast pass misses
            def _sweep_rtsp(cands, port, timeout=0.15, deadline=None):
                if port == 554 and "192.168.0.55" in cands and len(cands) > 10:
                    return "192.168.0.55"
                return None

            with mock.patch.object(
                connection_finder, "_probe_hosts", side_effect=_sweep_rtsp
            ):
                self.assertEqual(connection_finder.autodiscover("rtsp"), "192.168.0.55")

            # 3. Localhost fallback when 192.168.0/1.* has no open port
            def _localhost_ws(cands, port, timeout=0.15, deadline=None):
                return "127.0.0.1" if port == 8080 and cands == ["127.0.0.1"] else None

            with mock.patch.object(
                connection_finder, "_probe_hosts", side_effect=_localhost_ws
            ):
                self.assertEqual(
                    connection_finder.autodiscover("ws"), "ws://127.0.0.1:8080/ws"
                )

            def _localhost_rtsp_alt(cands, port, timeout=0.15, deadline=None):
                return "127.0.0.1" if port == 8554 and cands == ["127.0.0.1"] else None

            with mock.patch.object(
                connection_finder, "_probe_hosts", side_effect=_localhost_rtsp_alt
            ):
                self.assertEqual(
                    connection_finder.autodiscover("rtsp"), "127.0.0.1:8554"
                )

            # 4. Offline fallback when neither subnet nor localhost responds
            with mock.patch.object(
                connection_finder, "_probe_hosts", return_value=None
            ):
                self.assertEqual(
                    connection_finder.autodiscover("ws"), "ws://192.168.0.1:8080/ws"
                )
                self.assertEqual(
                    connection_finder.autodiscover("rtsp"), "192.168.0.108"
                )

            # 5. Zero timeout budget aborts scan immediately and returns fallback
            with mock.patch.object(
                connection_finder, "_open_nonblocking_socket"
            ) as mock_open:
                self.assertEqual(
                    connection_finder.autodiscover("ws", timeout=0.0),
                    "ws://192.168.0.1:8080/ws",
                )
                mock_open.assert_not_called()

        with (
            mock.patch.object(
                connection_finder,
                "_collect_network_state",
                return_value=(["192.168.1."], {"192.168.1.10"}, True),
            ),
            mock.patch.object(
                connection_finder, "_read_arp_neighbors", return_value=[]
            ),
            mock.patch.object(connection_finder, "_probe_hosts", return_value=None),
        ):
            self.assertEqual(
                connection_finder.autodiscover("ws"), "ws://192.168.1.1:8080/ws"
            )
            self.assertEqual(connection_finder.autodiscover("rtsp"), "192.168.1.108")

        with self.assertRaises(ValueError):
            connection_finder.autodiscover("http")

        with mock.patch.object(
            connection_finder, "_probe_hosts", return_value="127.0.0.1"
        ) as mock_probe:
            self.assertTrue(connection_finder.is_ws_reachable("ws://127.0.0.1:8080/ws"))
            mock_probe.assert_called_with(["127.0.0.1"], port=8080, timeout=0.15)
        self.assertFalse(connection_finder.is_ws_reachable("not-a-url"))

    def test_ws_auto_manual_mode_and_camera_controller_integration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                _temp_config_patch_stack(Path(tmpdir)),
                mock.patch.object(
                    config_store,
                    "autodiscover",
                    return_value="ws://127.0.0.1:8080/ws",
                ) as mock_ws_discover,
                mock.patch.object(
                    camera_controller,
                    "autodiscover",
                    return_value="127.0.0.1:8554",
                ) as mock_rtsp_discover,
                mock.patch.object(
                    camera_controller,
                    "has_active_ethernet",
                    return_value=False,
                ),
            ):
                be = backend_mod.Backend()
                self.assertEqual(be.server_mode, "auto")
                self.assertEqual(be.server_manual_url, "ws://192.168.0.1:8080/ws")
                self.assertEqual(be.server_url, "ws://127.0.0.1:8080/ws")
                self.assertGreaterEqual(mock_ws_discover.call_count, 1)

                mode_events: list[str] = []
                url_events: list[str] = []
                be.server_mode_changed.connect(mode_events.append)
                be.server_url_changed.connect(url_events.append)

                # Updating manual URL while in auto mode keeps auto mode active
                be.set_server_manual_url("ws://10.0.0.25:8080/ws")
                self.assertEqual(be.server_mode, "auto")
                self.assertEqual(be.server_manual_url, "ws://10.0.0.25:8080/ws")
                self.assertEqual(be.server_url, "ws://127.0.0.1:8080/ws")

                # Switching to manual mode uses and persists manual URL
                be.set_server_mode("manual")
                self.assertEqual(be.server_mode, "manual")
                self.assertEqual(be.server_url, "ws://10.0.0.25:8080/ws")
                self.assertEqual(mode_events[-1], "manual")
                self.assertEqual(url_events[-1], "ws://10.0.0.25:8080/ws")

                # Reloading verifies persisted mode and manual URL
                reloaded = ConfigStore(LogManager())
                reloaded.load_config()
                self.assertEqual(reloaded.server_mode, "manual")
                self.assertEqual(reloaded.server_manual_url, "ws://10.0.0.25:8080/ws")
                self.assertEqual(reloaded.server_url, "ws://10.0.0.25:8080/ws")

                # Switching back to auto mode preserves saved manual URL
                be.set_server_mode("auto")
                self.assertEqual(be.server_mode, "auto")
                self.assertEqual(be.server_manual_url, "ws://10.0.0.25:8080/ws")
                self.assertEqual(be.server_url, "ws://127.0.0.1:8080/ws")

                # CameraController delegates discovery and link detection to connection_finder
                be.set_camera_settings("auto", "udp_high", "192.168.1.108")
                with mock.patch.object(be.camera_controller, "_enforce_camera_h264"):
                    rtsp_url = be.camera_rtsp_url
                mock_rtsp_discover.assert_called_with("rtsp")
                self.assertTrue(
                    rtsp_url.endswith(
                        "@127.0.0.1:8554/cam/realmonitor?channel=1&subtype=0"
                    )
                )
                self.assertEqual(
                    CameraController._detect_camera_link(), ("127.0.0.1:8554", False)
                )


if __name__ == "__main__":
    unittest.main()
