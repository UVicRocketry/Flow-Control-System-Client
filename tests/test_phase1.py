"""Phase 1 unit tests for non-GUI client core modules."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CODE_DIR = str(Path(__file__).resolve().parents[1] / "contents" / "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

import config_manager  # noqa: E402
from telemetry_files import parse_telemetry_file  # noqa: E402
from telemetry_series import ingest_ws_telemetry_frames  # noqa: E402


class TestConfigManager(unittest.TestCase):
    """Tests environment mode detection in config_manager."""

    def test_is_dev_environment_flags(self) -> None:
        base_env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in (
                "FLOW_CONTROL_DEV",
                "FLOW_CONTROL_USE_USER_CONFIG",
                "APPIMAGE",
                "SHARUN_DIR",
                "APPDIR",
            )
        }
        with mock.patch.dict(os.environ, base_env, clear=True):
            with mock.patch.object(sys, "frozen", False, create=True):
                self.assertTrue(config_manager.is_dev_environment())

            with mock.patch.dict(os.environ, {"FLOW_CONTROL_DEV": "1"}):
                self.assertTrue(config_manager.is_dev_environment())

            with mock.patch.dict(os.environ, {"FLOW_CONTROL_DEV": "0"}):
                self.assertFalse(config_manager.is_dev_environment())

            with mock.patch.dict(os.environ, {"FLOW_CONTROL_USE_USER_CONFIG": "1"}):
                self.assertFalse(config_manager.is_dev_environment())

            with mock.patch.dict(os.environ, {"APPIMAGE": "/tmp/FlowControl.AppImage"}):
                self.assertFalse(config_manager.is_dev_environment())


class TestTelemetrySeries(unittest.TestCase):
    """Tests WebSocket telemetry frame ingestion for text and pre-parsed dicts."""

    def test_ingest_ws_telemetry_frames_str_and_preparsed(self) -> None:
        frames = [
            {"type": "telemetry", "seconds": 1700000000.0, "uptime": 1.0, "packet_id": 1, "pt1": 100.5},
            {"type": "pong", "uptime": 1.1},
            {"seconds": 1700000002.5, "uptime": 3.5, "packet_id": 2, "pt1": 110.0, "tc1": 24.5},
        ]
        raw_message = "\n".join(json.dumps(f) for f in frames)

        channels_str: dict = {}
        recs_str: list = []
        secs_str: list = []
        new_str, ingested_str, t0_str, latest_str = ingest_ws_telemetry_frames(
            raw_message, channels_str, recs_str, secs_str, None, {}
        )

        channels_list: dict = {}
        recs_list: list = []
        secs_list: list = []
        new_list, ingested_list, t0_list, latest_list = ingest_ws_telemetry_frames(
            frames, channels_list, recs_list, secs_list, None, {}
        )

        self.assertTrue(new_str)
        self.assertEqual(new_str, new_list)
        self.assertEqual(t0_str, 1700000000.0)
        self.assertEqual(t0_str, t0_list)
        self.assertEqual(secs_str, [0.0, 2.5])
        self.assertEqual(secs_str, secs_list)
        self.assertEqual(ingested_str, ingested_list)
        self.assertEqual(recs_str, recs_list)
        self.assertEqual(latest_str, latest_list)
        self.assertEqual(set(channels_str), {"pt1", "tc1"})

    def test_ingest_ws_telemetry_frames_empty_inputs(self) -> None:
        self.assertEqual(
            ingest_ws_telemetry_frames("", {}, [], [], None, {}),
            (False, [], None, {}),
        )
        self.assertEqual(
            ingest_ws_telemetry_frames([], {}, [], [], 1.0, {"uptime": 1.0}),
            (False, [], 1.0, {"uptime": 1.0}),
        )


class TestTelemetryFiles(unittest.TestCase):
    """Tests two-row-header telemetry CSV parsing."""

    def test_parse_telemetry_file_two_row_header_csv(self) -> None:
        csv_content = "\n".join(
            [
                "s,psi,degC,iso",
                "seconds,PT-101,TC-201,timestamp",
                "1700000010.0,150.25,22.5,2026-01-01T00:00:10Z",
                "1700000012.5,155.75,23.0,2026-01-01T00:00:12Z",
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "hotfire.csv"
            csv_path.write_text(csv_content, encoding="utf-8")

            records, raw_seconds, cols = parse_telemetry_file(csv_path)

        self.assertEqual(cols, ["PT-101", "TC-201"])
        self.assertEqual(raw_seconds, [0.0, 2.5])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["t"], 0.0)
        self.assertEqual(records[0]["values"], {"PT-101": 150.25, "TC-201": 22.5})
        self.assertEqual(records[1]["t"], 2.5)
        self.assertEqual(records[1]["values"], {"PT-101": 155.75, "TC-201": 23.0})


if __name__ == "__main__":
    unittest.main()
