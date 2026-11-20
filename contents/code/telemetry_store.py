# This Python file uses the following encoding: utf-8
"""Live/loaded telemetry buffering, graphing queries, and recording (`telemetry_store.py`)."""

import json
import time
from pathlib import Path

from PySide6 import QtCore

from config_manager import (
    CONFIG_DIR,
    read_graphs_config,
    write_graphs_config,
)
from telemetry_files import (
    append_recording_rows,
    init_recording_csv,
    parse_telemetry_file_with_units,
    resolve_data_file,
)
from telemetry_series import (
    ColumnarTelemetryBuffer,
    coerce_allowed_unit,
    format_channel_meta,
    ingest_ws_telemetry_frames,
    list_available_channels,
    register_channel_if_missing,
)

LARGE_FILE_BYTES = 10 * 1024 * 1024


class _FileParseSignals(QtCore.QObject):
    finished = QtCore.Signal(str, str, str, object, object, object, object)
    failed = QtCore.Signal(str, str)


class _FileParseWorker(QtCore.QRunnable):
    """Background QRunnable for parsing large (>10 MB) telemetry files."""

    def __init__(self, mode: str, target: str, resolved_path: Path):
        super().__init__()
        self.mode = mode
        self.target = target
        self.resolved_path = resolved_path
        self.signals = _FileParseSignals()

    def run(self) -> None:
        try:
            records, seconds_list, cols, csv_units = parse_telemetry_file_with_units(
                self.resolved_path
            )
            self.signals.finished.emit(
                self.mode,
                self.target,
                str(self.resolved_path),
                records,
                seconds_list,
                cols,
                csv_units,
            )
        except Exception as err:
            self.signals.failed.emit(self.target, str(err))


class TelemetryStore(QtCore.QObject):
    """Owns live/loaded telemetry buffers, graph configs, and CSV recording."""

    telemetry_changed = QtCore.Signal()
    channels_changed = QtCore.Signal()
    recording_changed = QtCore.Signal(bool)
    data_loaded = QtCore.Signal(str, str, "QVariant")

    def __init__(self, config_store, log_manager, parent=None):
        super().__init__(parent)
        self._config_store = config_store
        self._log_manager = log_manager
        self._recording = False
        self._record_file_path: Path | None = None
        self._record_columns: list[str] = []
        self._record_sample_count = 0
        self._active_workers: list[_FileParseWorker] = []

        self._known_channels: dict = {}
        self._default_graph_cards: list[dict] = []
        self._live_records: list[dict] = []
        self._live_seconds: list[float] = []
        self._live_buffer = ColumnarTelemetryBuffer()
        self._live_t0: float | None = None
        self._telemetry_ui_dirty = False
        self._last_telemetry_emit_ts = 0.0
        self._telemetry_ui_timer = QtCore.QTimer(self)
        self._telemetry_ui_timer.setSingleShot(True)
        self._telemetry_ui_timer.timeout.connect(self._flush_telemetry_ui_update)

        self.load_graphs_config()
        self._latest_telemetry: dict = {
            "seconds": 0.0,
            "uptime": 0.0,
            "packet_id": 0,
            "values": {k: 0.0 for k in self._known_channels},
        }
        self._loaded_records: list[dict] = []
        self._loaded_seconds: list[float] = []
        self._loaded_buffer = ColumnarTelemetryBuffer(max_samples=0)
        self._loaded_channel_units: dict[str, str] = {}
        self._live_channel_units: dict[str, str] = {}
        self._loaded_meta: dict = {
            "name": "",
            "path": "",
            "source": "",
            "minTime": 0.0,
            "maxTime": 0.0,
            "duration": 0.0,
            "count": 0,
            "columns": list(self._known_channels.keys()),
        }

    # ------------------------------------------------------------------
    # Graphs & Channel Metadata
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_graph_card(card: dict) -> dict:
        raw_title = card.get("title") or card.get("channelKey") or "Graph"
        channel_key = str(card.get("channelKey") or "")
        if channel_key == "L_RUN_TANK" and "mass" in str(raw_title).lower():
            channel_key = "M_RUN_TANK"
        y_unit = coerce_allowed_unit(channel_key, card.get("yAxisLabel"))
        return {
            "title": str(raw_title),
            "channelKey": channel_key,
            "xAxisLabel": str(card.get("xAxisLabel") or "Time (s)"),
            "yAxisLabel": y_unit,
            "accentColor": str(card.get("accentColor") or "theme:highlight"),
            "autoScale": bool(card.get("autoScale", True)),
            "manualMinY": float(card.get("manualMinY", 0.0)),
            "manualMaxY": float(card.get("manualMaxY", 1000.0)),
            "minYRange": float(card.get("minYRange", 10.0)),
            "filterOutliers3Std": bool(card.get("filterOutliers3Std", False)),
            "smoothingWindow": int(card.get("smoothingWindow", 1)),
            "maxBuckets": int(card.get("maxBuckets", 300)),
            "showGrid": bool(card.get("showGrid", True)),
            "showFill": bool(card.get("showFill", True)),
            "colSpan": int(card.get("colSpan", 1)),
            "cardHeight": max(210, int(card.get("cardHeight", 230))),
        }

    def load_graphs_config(self) -> None:
        known_channels, default_cards = read_graphs_config(
            self._log_manager.log_error
        )
        if known_channels:
            self._known_channels = known_channels
        if default_cards:
            self._default_graph_cards = [
                self._normalize_graph_card(dict(c))
                for c in default_cards
                if isinstance(c, dict)
            ]
        self.channels_changed.emit()

    def save_graphs_config(self, cards: list) -> bool:
        if not isinstance(cards, list):
            return False
        self._default_graph_cards = [
            self._normalize_graph_card(dict(c)) for c in cards if isinstance(c, dict)
        ]
        return write_graphs_config(
            self._known_channels,
            self._default_graph_cards,
            self._log_manager.log_error,
        )

    @property
    def known_channels(self) -> dict:
        return self._known_channels

    @property
    def telemetry(self) -> dict:
        return self._latest_telemetry

    @property
    def loaded_meta(self) -> dict:
        return self._loaded_meta

    @property
    def default_graph_cards(self) -> list[dict]:
        return self._default_graph_cards

    @property
    def available_channels(self) -> list[dict]:
        return list_available_channels(self._known_channels, self._loaded_channel_units)

    def get_channel_meta(self, channel: str) -> dict:
        return format_channel_meta(
            self._known_channels, channel, self._loaded_channel_units
        )

    def apply_live_channels_metadata(self, channels_payload: dict) -> None:
        new_ch = False
        for ch_key, ch_info in channels_payload.items():
            if not isinstance(ch_info, dict):
                continue
            key_str = str(ch_key)
            unit_str = str(ch_info.get("unit") or "").strip()
            if unit_str:
                self._live_channel_units[key_str] = unit_str
            if register_channel_if_missing(
                self._known_channels, key_str, unit_str or None
            ):
                new_ch = True
        if new_ch:
            self.channels_changed.emit()

    # ------------------------------------------------------------------
    # Telemetry Recording
    # ------------------------------------------------------------------
    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def record_file_path(self) -> Path | None:
        return self._record_file_path

    def set_recording(
        self, active: bool, ws_connected: bool, ws_send_fn
    ) -> None:
        val = bool(active)
        if self._recording == val:
            return
        if val:
            self._start_recording(ws_connected, ws_send_fn)
        else:
            self._stop_recording(ws_connected, ws_send_fn)

    def _start_recording(self, ws_connected: bool, ws_send_fn) -> None:
        if not ws_connected:
            self._log_manager.log_warn(
                "Cannot record telemetry while server is offline."
            )
            self.recording_changed.emit(self._recording)
            return
        ts = time.strftime("%Y_%m_%d_%H%M%S")
        dest_path = CONFIG_DIR / "data" / f"telemetry_{ts}.csv"
        try:
            self._record_columns = init_recording_csv(dest_path, self._known_channels)
        except Exception as err:
            self._log_manager.log_error(
                f"Failed to start local telemetry recording: {err}"
            )
            return

        self._record_file_path = dest_path
        self._record_sample_count = 0
        self._recording = True
        self.recording_changed.emit(True)
        self._log_manager.refresh_local_data()
        ws_send_fn(
            json.dumps(
                {
                    "type": "record",
                    "command": "RECORD",
                    "active": True,
                    "filename": dest_path.name,
                }
            )
        )
        self._log_manager.log_info(
            f'Recording telemetry to "{dest_path.name}" locally and on server.'
        )

    def _stop_recording(self, ws_connected: bool, ws_send_fn) -> None:
        fname = (
            self._record_file_path.name if self._record_file_path else "telemetry.csv"
        )
        count = self._record_sample_count
        self._recording = False
        self._record_file_path = None
        self.recording_changed.emit(False)
        ws_send_fn(json.dumps({"type": "record", "command": "RECORD", "active": False}))
        self._log_manager.refresh_local_data()
        if ws_connected:
            self._log_manager.refresh_remote_data(
                self._config_store.server_url, ws_connected, ws_send_fn
            )
        self._log_manager.log_info(
            f'Stopped recording "{fname}" ({count} samples saved).'
        )

    def _append_to_active_recording(
        self, ingested: list, ws_connected: bool, ws_send_fn
    ) -> None:
        if not (self._recording and self._record_file_path and ingested):
            return
        try:
            append_recording_rows(
                self._record_file_path, self._record_columns, ingested
            )
            self._record_sample_count += len(ingested)
        except Exception as err:
            self._log_manager.log_error(f"Failed writing to recording CSV: {err}")
            self.set_recording(False, ws_connected, ws_send_fn)

    # ------------------------------------------------------------------
    # Live Ingestion & File Loading
    # ------------------------------------------------------------------
    def _flush_telemetry_ui_update(self) -> None:
        if self._telemetry_ui_dirty:
            self._telemetry_ui_dirty = False
            self._last_telemetry_emit_ts = time.monotonic()
            self.telemetry_changed.emit()

    def reschedule_ui_timer(self) -> None:
        if self._telemetry_ui_timer.isActive():
            self._telemetry_ui_timer.stop()
            self._schedule_telemetry_ui_update()

    def _schedule_telemetry_ui_update(self) -> None:
        self._telemetry_ui_dirty = True
        interval_s = 1.0 / float(max(1, self._config_store.view_refresh_hz))
        now = time.monotonic()
        elapsed = now - self._last_telemetry_emit_ts
        if elapsed >= interval_s and not self._telemetry_ui_timer.isActive():
            self._flush_telemetry_ui_update()
        elif not self._telemetry_ui_timer.isActive():
            wait_ms = max(8, int((interval_s - elapsed) * 1000.0))
            self._telemetry_ui_timer.start(wait_ms)

    def ingest_telemetry_frames(
        self, parsed_frames: list[dict], ws_connected: bool, ws_send_fn
    ) -> None:
        res = ingest_ws_telemetry_frames(
            parsed_frames,
            self._known_channels,
            self._live_records,
            self._live_seconds,
            self._live_t0,
            self._latest_telemetry,
        )
        new_channels, ingested, self._live_t0, self._latest_telemetry = res
        if ingested:
            self._live_buffer.append_records(ingested)
        self._append_to_active_recording(ingested, ws_connected, ws_send_fn)
        if new_channels:
            self.channels_changed.emit()
        if ingested:
            self._schedule_telemetry_ui_update()

    def apply_pulled_recording_file(
        self, fname: str, dest_path: Path, overwrote: bool = False
    ) -> None:
        records, seconds_list, cols, csv_units = parse_telemetry_file_with_units(
            dest_path
        )
        self._live_channel_units.update(csv_units)
        new_ch = False
        for c in cols:
            if register_channel_if_missing(
                self._known_channels, c, csv_unit=csv_units.get(c)
            ):
                new_ch = True
        self._live_records = list(records)
        self._live_seconds = list(seconds_list)
        self._live_buffer.load_records(self._live_records, self._live_seconds)
        if records:
            self._latest_telemetry = dict(records[-1])
        if new_ch:
            self.channels_changed.emit()
        self.telemetry_changed.emit()
        suffix = ", overwrote existing local log" if overwrote else ""
        self._log_manager.log_info(
            f'Pulled current recorded state from "{fname}" '
            f"({len(records)} samples{suffix})."
        )

    def _apply_parsed_telemetry(
        self,
        mode: str,
        target: str,
        resolved_str: str,
        records: list,
        seconds_list: list,
        cols: list,
        csv_units: dict | None = None,
    ) -> dict:
        self._loaded_channel_units = dict(csv_units or {})
        new_ch = False
        for c in cols:
            if register_channel_if_missing(
                self._known_channels, c, csv_unit=self._loaded_channel_units.get(c)
            ):
                new_ch = True
        if new_ch or self._loaded_channel_units:
            self.channels_changed.emit()

        self._loaded_records = records
        self._loaded_seconds = seconds_list
        self._loaded_buffer.load_records(records, seconds_list)
        min_t = seconds_list[0] if seconds_list else 0.0
        max_t = seconds_list[-1] if seconds_list else 0.0

        self._loaded_meta = {
            "source": mode,
            "path": target,
            "resolvedPath": resolved_str,
            "name": Path(target).name,
            "columns": list(cols),
            "units": dict(self._loaded_channel_units),
            "count": len(records),
            "minTime": min_t,
            "maxTime": max_t,
            "duration": max(0.0, max_t - min_t),
        }

        name = Path(target).name
        self._log_manager.log_info(
            f'Loaded data "{name}" ({mode}, {len(records)} samples)'
        )
        self.data_loaded.emit(mode, target, self._loaded_meta)
        self.telemetry_changed.emit()
        return self._loaded_meta

    def _on_worker_finished(
        self,
        worker: _FileParseWorker,
        mode: str,
        target: str,
        resolved_str: str,
        records: list,
        seconds_list: list,
        cols: list,
        csv_units: dict,
    ) -> None:
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        self._apply_parsed_telemetry(
            mode, target, resolved_str, records, seconds_list, cols, csv_units
        )

    def _on_worker_failed(
        self, worker: _FileParseWorker, target: str, err_msg: str
    ) -> None:
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        self._log_manager.log_error(f'Failed to parse data file "{target}": {err_msg}')

    def load_resolved_file(
        self, mode: str, target: str, resolved_path: Path
    ) -> dict:
        try:
            file_size = resolved_path.stat().st_size
        except OSError:
            file_size = 0

        if file_size > LARGE_FILE_BYTES:
            name = Path(target).name
            self._log_manager.log_info(f'Loading large log "{name}" in background...')
            worker = _FileParseWorker(mode, target, resolved_path)
            self._active_workers.append(worker)
            worker.signals.finished.connect(
                lambda m, t, r, rec, sec, cols, units, w=worker: (
                    self._on_worker_finished(w, m, t, r, rec, sec, cols, units)
                )
            )
            worker.signals.failed.connect(
                lambda t, err, w=worker: self._on_worker_failed(w, t, err)
            )
            QtCore.QThreadPool.globalInstance().start(worker)
            return {}

        try:
            records, seconds_list, cols, csv_units = parse_telemetry_file_with_units(
                resolved_path
            )
        except Exception as err:
            self._log_manager.log_error(f'Failed to parse data file "{target}": {err}')
            return {}

        return self._apply_parsed_telemetry(
            mode, target, str(resolved_path), records, seconds_list, cols, csv_units
        )

    def load_data(
        self,
        mode: str,
        target: str,
        ws_connected: bool,
        ws_send_fn,
    ) -> dict:
        if not target:
            self._log_manager.log_warn("No data file specified to load.")
            return {}

        if mode == "remote":
            clean_name = Path(target.strip()).name
            local_cand = CONFIG_DIR / "data" / clean_name
            if not local_cand.exists():
                self._log_manager.fetch_remote_file(
                    self._config_store.server_url,
                    clean_name,
                    mode="load",
                    on_saved_cb=self._on_remote_saved,
                    ws_connected=ws_connected,
                    ws_send_fn=ws_send_fn,
                )
                return {}

        try:
            resolved_path = resolve_data_file(target, self._known_channels)
        except Exception as err:
            self._log_manager.log_error(f'Failed to resolve data file "{target}": {err}')
            return {}

        return self.load_resolved_file(mode, target, resolved_path)

    def _on_remote_saved(
        self, fname: str, dest_path: Path, overwrote: bool, mode: str
    ) -> None:
        if mode == "load":
            self.load_resolved_file("remote", fname, dest_path)
        elif mode == "pull_recording":
            self.apply_pulled_recording_file(fname, dest_path, overwrote=overwrote)

    # ------------------------------------------------------------------
    # Windowed Time-Series Queries
    # ------------------------------------------------------------------
    def _active_source_units(self, source_mode: str) -> dict[str, str]:
        units = {
            k: str(v.get("unit", ""))
            for k, v in self._known_channels.items()
            if isinstance(v, dict) and v.get("unit")
        }
        overlay = (
            self._live_channel_units
            if source_mode == "live"
            else self._loaded_channel_units
        )
        units.update(overlay)
        if "M_RUN_TANK" in units and "L_RUN_TANK" not in units:
            units["L_RUN_TANK"] = units["M_RUN_TANK"]
        elif "L_RUN_TANK" in units and "M_RUN_TANK" not in units:
            units["M_RUN_TANK"] = units["L_RUN_TANK"]
        return units

    def get_channel_data(
        self,
        source_mode: str,
        channel: str,
        t_start: float,
        t_end: float,
        max_buckets: int = 300,
        filter_outliers_3std: bool = False,
        smoothing_window: int = 1,
        target_unit: str = "",
    ) -> dict:
        buf = self._loaded_buffer if source_mode != "live" else self._live_buffer
        src_units = self._active_source_units(source_mode)
        return buf.query_series(
            channel=channel,
            t_start=t_start,
            t_end=t_end,
            max_buckets=max_buckets,
            filter_outliers_3std=filter_outliers_3std,
            smoothing_window=smoothing_window,
            source_unit=src_units.get(channel),
            target_unit=target_unit or None,
        )

    def get_batch_channel_data(self, source_mode: str, requests: list) -> dict:
        buf = self._loaded_buffer if source_mode != "live" else self._live_buffer
        src_units = self._active_source_units(source_mode)
        return buf.query_batch(requests, src_units)
