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
from telemetry_files import (  # noqa: E402
    parse_telemetry_file,
    parse_telemetry_file_with_units,
)
from telemetry_series import (  # noqa: E402
    allowed_units_for_channel,
    format_channel_meta,
    ingest_ws_telemetry_frames,
    query_batch_channels,
    query_channel_series,
    register_channel_if_missing,
)


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
            {
                "type": "telemetry",
                "seconds": 1700000000.0,
                "uptime": 1.0,
                "packet_id": 1,
                "pt1": 100.5,
            },
            {"type": "pong", "uptime": 1.1},
            {
                "seconds": 1700000002.5,
                "uptime": 3.5,
                "packet_id": 2,
                "pt1": 110.0,
                "tc1": 24.5,
            },
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

    def test_unit_rules_and_m_run_tank_defaults(self) -> None:
        channels: dict = {}
        self.assertTrue(register_channel_if_missing(channels, "M_RUN_TANK"))
        meta = format_channel_meta(channels, "M_RUN_TANK")
        self.assertEqual(meta["unit"], "kg")
        self.assertEqual(meta["allowed_units"], ["kg", "lbs"])

        self.assertEqual(allowed_units_for_channel("P_RUN_TANK"), ["kPa", "psi"])
        self.assertEqual(allowed_units_for_channel("L_THRUST"), ["N", "lbf"])
        self.assertEqual(allowed_units_for_channel("T_INJECTOR"), ["°C", "°F", "K"])
        # CSV unit overrides channel-name prefix for legacy mismatches
        self.assertEqual(
            allowed_units_for_channel("L_CUSTOM", csv_unit="psi"), ["kPa", "psi"]
        )
        self.assertEqual(
            allowed_units_for_channel("L_RUN_TANK", csv_unit="kg"), ["kg", "lbs"]
        )

    def test_unit_conversion_and_legacy_mass_alias_queries(self) -> None:
        records = [
            {
                "t": 0.0,
                "values": {
                    "P_RUN_TANK": 100.0,
                    "L_RUN_TANK": 10.0,
                    "L_THRUST": 100.0,
                    "T_RUN_TANK": 0.0,
                },
            },
            {
                "t": 1.0,
                "values": {
                    "P_RUN_TANK": 100.0,
                    "L_RUN_TANK": 10.0,
                    "L_THRUST": 100.0,
                    "T_RUN_TANK": 100.0,
                },
            },
        ]
        seconds_list = [0.0, 1.0]

        p_res = query_channel_series(
            records,
            seconds_list,
            "P_RUN_TANK",
            0.0,
            1.0,
            source_unit="psi",
            target_unit="kPa",
        )
        self.assertAlmostEqual(p_res["mean"], 689.47572932, places=4)

        m_res = query_channel_series(
            records,
            seconds_list,
            "M_RUN_TANK",
            0.0,
            1.0,
            source_unit="kg",
            target_unit="lbs",
        )
        self.assertAlmostEqual(m_res["mean"], 22.0462262, places=4)

        batch = query_batch_channels(
            records,
            seconds_list,
            [
                {
                    "index": 0,
                    "channel": "L_THRUST",
                    "tStart": 0.0,
                    "tEnd": 1.0,
                    "targetUnit": "lbf",
                },
                {
                    "index": 1,
                    "channel": "T_RUN_TANK",
                    "tStart": 0.0,
                    "tEnd": 1.0,
                    "targetUnit": "°F",
                },
                {
                    "index": 2,
                    "channel": "T_RUN_TANK",
                    "tStart": 0.0,
                    "tEnd": 1.0,
                    "targetUnit": "K",
                },
            ],
            source_units={"L_THRUST": "N", "T_RUN_TANK": "C"},
        )
        self.assertAlmostEqual(batch["0"]["mean"], 22.48089431, places=4)
        self.assertAlmostEqual(batch["1"]["min"], 32.0, places=4)
        self.assertAlmostEqual(batch["1"]["max"], 212.0, places=4)
        self.assertAlmostEqual(batch["2"]["min"], 273.15, places=4)
        self.assertAlmostEqual(batch["2"]["max"], 373.15, places=4)


class TestTelemetryFiles(unittest.TestCase):
    """Tests two-row-header telemetry CSV parsing."""

    def test_parse_telemetry_file_two_row_header_csv(self) -> None:
        csv_content = "\n".join(
            [
                ",psi,kg,N,C,,s",
                "P_RUN_TANK,L_RUN_TANK,L_THRUST,T_RUN_TANK,timestamp,seconds",
                "100.0,10.0,500.0,22.5,2026-01-01T00:00:10Z,1700000010.0",
                "110.0,10.5,510.0,23.0,2026-01-01T00:00:12Z,1700000012.5",
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "hotfire.csv"
            csv_path.write_text(csv_content, encoding="utf-8")

            records, raw_seconds, cols = parse_telemetry_file(csv_path)
            _, _, _, csv_units = parse_telemetry_file_with_units(csv_path)

        self.assertEqual(cols, ["P_RUN_TANK", "L_RUN_TANK", "L_THRUST", "T_RUN_TANK"])
        self.assertEqual(raw_seconds, [0.0, 2.5])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["t"], 0.0)
        self.assertAlmostEqual(records[0]["values"]["P_RUN_TANK"], 100.0)
        self.assertEqual(csv_units["P_RUN_TANK"], "psi")
        self.assertEqual(csv_units["L_RUN_TANK"], "kg")
        self.assertEqual(csv_units["M_RUN_TANK"], "kg")
        self.assertEqual(csv_units["L_THRUST"], "N")
        self.assertEqual(csv_units["T_RUN_TANK"], "C")


if __name__ == "__main__":
    unittest.main()
