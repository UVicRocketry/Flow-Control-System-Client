# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Backend Controller
provides QObject bridge between PySide6/QML and configuration/telemetry helpers.
"""

import json
import sys
import time
from pathlib import Path

from PySide6 import QtCore
from PySide6.QtWidgets import QFileDialog
from __feature__ import snake_case, true_property

from config_manager import (
    CONFIG_DIR,
    CONFIG_FILE,
    CURRENT_DIR,
    GRAPHS_CONFIG_DIR,
    GRAPHS_CONFIG_FILE,
    REPO_ROOT,
    ensure_config_file_exists,
    get_config_dir,
    get_default_config_dir,
    get_default_config_file,
    get_default_graphs_config_file,
    get_user_config_dir,
    is_dev_environment,
    read_app_config,
    read_graphs_config,
    write_app_config,
)
from telemetry_files import (
    parse_telemetry_file,
    resolve_data_file,
    reveal_in_file_browser,
)
from telemetry_series import (
    format_channel_meta,
    ingest_ws_telemetry_frames,
    list_available_channels,
    query_channel_series,
    register_channel_if_missing,
)

assert snake_case, true_property

ensure_config_file_exists()


class Backend(QtCore.QObject):
    """
    QObject bridge for PySide6/QML.
    exposes configuration properties, file loading, and telemetry series queries.
    """

    # signals
    config_changed = QtCore.Signal()
    server_url_changed = QtCore.Signal(str)
    auto_reconnect_changed = QtCore.Signal(bool)
    reconnect_interval_ms_changed = QtCore.Signal(int)
    connect_requested = QtCore.Signal()
    log_sent = QtCore.Signal(str, str)
    data_opened = QtCore.Signal(str)
    data_loaded = QtCore.Signal(str, str, "QVariant")
    telemetry_changed = QtCore.Signal()
    telemetry_point_received = QtCore.Signal("QVariantMap")
    channels_changed = QtCore.Signal()
    armed_changed = QtCore.Signal(bool)
    valves_changed = QtCore.Signal()
    valve_state_updated = QtCore.Signal(str, str)
    ws_send_requested = QtCore.Signal(str)
    disconnected = QtCore.Signal()
    websocket_closed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_data = {}
        self._armed = False
        self._ws_connected = False
        self._valve_definitions = []
        self._valves = {}
        self._known_channels = {}
        self._default_graph_cards = []
        self._live_records = []
        self._live_seconds = []
        self._live_t0 = None
        self.load_graphs_config()
        self._latest_telemetry = {
            "seconds": 0.0,
            "uptime": 0.0,
            "packet_id": 0,
            "values": {k: 0.0 for k in self._known_channels},
        }
        self._loaded_records = []
        self._loaded_seconds = []
        self._loaded_meta = {
            "name": "",
            "path": "",
            "source": "",
            "minTime": 0.0,
            "maxTime": 0.0,
            "duration": 0.0,
            "count": 0,
            "columns": list(self._known_channels.keys()),
        }
        self.load_config()

        env_type = (
            "Development (/contents/config/)"
            if is_dev_environment()
            else f"Standalone ({sys.platform})"
        )
        print(
            "[CONFIG] Environment: ",
            f"{env_type} | Config directory: {CONFIG_DIR}",
        )

    # logging helpers (push to UI toaster/notification tray and stdout/stderr)

    def log_info(self, msg: str):
        self._send_log("INFO", msg)

    def log_warn(self, msg: str):
        self._send_log("WARN", msg)

    def log_error(self, msg: str):
        self._send_log("ERR", msg, sys.stderr)

    def _send_log(self, level: str, msg: str, file=sys.stdout):
        t_str = time.strftime("%H:%M:%S")
        entry = f"[{t_str}] [{level}] {msg}"
        print(f"[FLOW-CTRL] {entry}", flush=True, file=file)
        self.log_sent.emit(level, msg)

    @QtCore.Slot(str, str)
    def log(self, level: str, msg: str):
        """logger slot for QML."""
        lvl = level.upper()
        out_stream = sys.stderr if lvl == "ERR" else sys.stdout
        self._send_log(lvl, msg, file=out_stream)

    @QtCore.Slot(str)
    def info(self, msg: str):
        self.log_info(msg)

    @QtCore.Slot(str)
    def warn(self, msg: str):
        self.log_warn(msg)

    @QtCore.Slot(str)
    def err(self, msg: str):
        self.log_error(msg)

    # configuration properties & slots

    @QtCore.Property(str, notify=config_changed)
    def config_dir(self) -> str:
        return str(CONFIG_DIR)

    @QtCore.Property(str, notify=config_changed)
    def config_file(self) -> str:
        return str(CONFIG_FILE)

    @QtCore.Property(bool, constant=True)
    def is_dev_mode(self) -> bool:
        return is_dev_environment()

    @QtCore.Property(str, notify=server_url_changed)
    def server_url(self) -> str:
        server_sec = self._config_data.get("server", {})
        return server_sec.get("default_url", "ws://127.0.0.1:8080/ws")

    @server_url.setter
    def server_url(self, url: str):
        url = url.strip()
        if not url:
            return
        if "server" not in self._config_data:
            self._config_data["server"] = {}
        if self._config_data["server"].get("default_url") != url:
            self._config_data["server"]["default_url"] = url
            self.save_config(self._config_data)
            self.server_url_changed.emit(url)

    @QtCore.Property(bool, notify=auto_reconnect_changed)
    def auto_reconnect(self) -> bool:
        server_sec = self._config_data.get("server", {})
        return bool(server_sec.get("auto_reconnect", True))

    @auto_reconnect.setter
    def auto_reconnect(self, enabled: bool):
        if "server" not in self._config_data:
            self._config_data["server"] = {}
        if self._config_data["server"].get("auto_reconnect") != enabled:
            self._config_data["server"]["auto_reconnect"] = enabled
            self.save_config(self._config_data)
            self.auto_reconnect_changed.emit(enabled)

    @QtCore.Property(int, notify=reconnect_interval_ms_changed)
    def reconnect_interval_ms(self) -> int:
        server_sec = self._config_data.get("server", {})
        return int(server_sec.get("reconnect_interval_ms", 2000))

    @reconnect_interval_ms.setter
    def reconnect_interval_ms(self, interval: int):
        if "server" not in self._config_data:
            self._config_data["server"] = {}
        if self._config_data["server"].get("reconnect_interval_ms") != interval:
            self._config_data["server"]["reconnect_interval_ms"] = interval
            self.save_config(self._config_data)
            self.reconnect_interval_ms_changed.emit(interval)

    @QtCore.Slot(result="QVariantMap")
    def load_config(self) -> dict:
        """loads configuration from CONFIG_FILE via config_manager."""
        self._config_data = read_app_config(self.log_error)
        self._seed_valves_from_config()
        self.config_changed.emit()
        self.server_url_changed.emit(self.server_url)
        self.auto_reconnect_changed.emit(self.auto_reconnect)
        self.reconnect_interval_ms_changed.emit(self.reconnect_interval_ms)
        return self._config_data

    @QtCore.Slot("QVariantMap", result=bool)
    def save_config(self, data: dict) -> bool:
        """saves dictionary data to CONFIG_FILE via config_manager."""
        if write_app_config(data, self.log_error):
            self._config_data = data
            self.config_changed.emit()
            return True
        return False

    @QtCore.Slot(str, result="QVariant")
    @QtCore.Slot(str, "QVariant", result="QVariant")
    def get_setting(self, key: str, default=None):
        return self._config_data.get(key, default)

    @QtCore.Slot(str, "QVariant")
    def set_setting(self, key: str, value):
        self._config_data[key] = value
        self.save_config(self._config_data)

    @QtCore.Slot(str)
    def set_server_url(self, url: str):
        self.server_url = url

    @QtCore.Slot(bool)
    def set_auto_reconnect(self, enabled: bool):
        self.auto_reconnect = enabled

    @QtCore.Slot(int)
    def set_reconnect_interval_ms(self, interval: int):
        self.reconnect_interval_ms = interval

    @QtCore.Slot()
    def connect_to_server(self):
        """signals QML/listeners to initiate WebSocket connection."""
        self.connect_requested.emit()

    @QtCore.Slot()
    def connect(self):
        """connection entrypoint called on startup."""
        self.connect_to_server()

    @QtCore.Slot(str)
    def show_in_file_browser(self, url: str):
        reveal_in_file_browser(url, self.log_info, self.log_warn)

    # telemetry & graphs configuration

    @QtCore.Slot()
    def load_graphs_config(self):
        """loads default channels and default graph cards from config/graphs/graphs.json."""
        known_channels, default_cards = read_graphs_config(self.log_error)
        if known_channels:
            self._known_channels = known_channels
        if default_cards:
            self._default_graph_cards = default_cards
        self.channels_changed.emit()

    @QtCore.Property("QVariantMap", notify=telemetry_changed)
    def telemetry(self) -> dict:
        return self._latest_telemetry

    @QtCore.Property("QVariantMap", notify=telemetry_changed)
    def loaded_meta(self) -> dict:
        return self._loaded_meta

    @QtCore.Property("QVariantList", notify=channels_changed)
    def default_graph_cards(self) -> list:
        return self._default_graph_cards

    @QtCore.Property("QVariantList", notify=channels_changed)
    def available_channels(self) -> list:
        return list_available_channels(self._known_channels)

    @QtCore.Slot(str, result="QVariantMap")
    def get_channel_meta(self, channel: str) -> dict:
        return format_channel_meta(self._known_channels, channel)

    # actuator & safety state

    @staticmethod
    def _normalize_valve_state(state: str) -> str:
        s = str(state).strip().upper()
        aliases = {
            "CLOSE": "CLOSED",
            "TRANSIT": "ACTUATING",
            "FILLING": "FILL",
            "VENTING": "VENT",
        }
        return aliases.get(s, s)

    def _seed_valves_from_config(self):
        defs = self._config_data.get("actuators") or self._config_data.get("valves")
        if isinstance(defs, list) and defs:
            self._apply_actuator_definitions(defs)

    def _apply_actuator_definitions(self, definitions: list):
        valid_defs = [dict(item) for item in definitions if isinstance(item, dict) and item.get("id")]
        self._valve_definitions = valid_defs
        seeded = {}
        for item in valid_defs:
            vid = item["id"]
            seeded[vid] = self._valves.get(
                vid,
                self._normalize_valve_state(item.get("normal_state", "CLOSED")),
            )
        self._valves = seeded
        self.config_changed.emit()
        self.valves_changed.emit()

    def _get_valve_def(self, valve_id: str) -> dict:
        for item in self._valve_definitions:
            if item.get("id") == valve_id:
                return item
        return {}

    @QtCore.Property(bool, notify=armed_changed)
    def armed(self) -> bool:
        return self._armed

    @armed.setter
    def armed(self, value: bool):
        value = bool(value)
        if self._armed != value:
            self._armed = value
            self.armed_changed.emit(value)

    @QtCore.Slot(bool)
    def set_armed(self, value: bool):
        self.armed = value

    @QtCore.Property("QVariantList", notify=config_changed)
    def valve_definitions(self) -> list:
        return list(self._valve_definitions)

    @QtCore.Property("QVariantMap", notify=valves_changed)
    def valves(self) -> dict:
        return dict(self._valves)

    @QtCore.Slot(bool)
    def on_ws_connected_changed(self, connected: bool):
        """Disarms system and emits disconnect signals on True -> False transitions."""
        connected = bool(connected)
        was_connected = self._ws_connected
        self._ws_connected = connected
        if not connected:
            self.set_armed(False)
            if was_connected:
                self.disconnected.emit()
                self.websocket_closed.emit()

    @QtCore.Slot(str, str)
    def actuate_valve(self, valve_id: str, action: str):
        """Validates armed/interlock state and emits an outbound valve command."""
        if not self._armed:
            self.log_warn(f"Cannot actuate {valve_id}: system is SAFE (disarmed).")
            return

        vdef = self._get_valve_def(valve_id)
        if vdef.get("external", False):
            self.log_warn(f"{valve_id} is externally controlled.")
            return

        current = self._valves.get(valve_id, "")
        if vdef.get("single_use", False) and current in ("FIRED", "DISCONNECTED"):
            self.log_warn(f"{valve_id} is single-use and already {current}.")
            return

        act = str(action).strip().upper()
        payload = {
            "type": "command",
            "command": "CTRL",
            "valve": valve_id,
            "action": act,
        }
        self.ws_send_requested.emit(json.dumps(payload))

    @QtCore.Slot()
    def abort(self):
        """Sends immediate emergency abort command regardless of armed state."""
        payload = {"type": "abort", "command": "ABORT"}
        self.ws_send_requested.emit(json.dumps(payload))
        self.log_warn("EMERGENCY ABORT command sent.")

    def _apply_valve_state(self, valve_id: str, state: str):
        norm = self._normalize_valve_state(state)
        if not valve_id or not norm:
            return
        if self._valves.get(valve_id) != norm:
            self._valves[valve_id] = norm
            self.valve_state_updated.emit(valve_id, norm)
            self.valves_changed.emit()

    def _handle_control_message(self, msg: dict):
        msg_type = msg.get("type")
        ident = msg.get("identifier")

        # Accept actuator definitions pushed from Flow-Control-System-Server/config/actuators.json
        actuators_list = msg.get("actuators") or msg.get("valve_definitions")
        if isinstance(actuators_list, list):
            self._apply_actuator_definitions(actuators_list)

        if msg_type in ("init", "actuators", "config"):
            if "armed" in msg:
                self.set_armed(bool(msg["armed"]))
            valves_payload = msg.get("valves")
            if isinstance(valves_payload, list):
                self._apply_actuator_definitions(valves_payload)
            elif isinstance(valves_payload, dict):
                for vid, st in valves_payload.items():
                    self._valves[vid] = self._normalize_valve_state(st)
                self.valves_changed.emit()
            return

        if msg_type in ("valve_state", "summary"):
            if "valve" in msg and "state" in msg:
                self._apply_valve_state(msg["valve"], msg["state"])
            valves_map = msg.get("valves")
            if isinstance(valves_map, dict):
                for vid, st in valves_map.items():
                    self._valves[vid] = self._normalize_valve_state(st)
                self.valves_changed.emit()
            return

        if ident == "FEEDBACK":
            data = msg.get("data", {})
            if isinstance(data, dict) and "valve" in data and "action" in data:
                self._apply_valve_state(data["valve"], data["action"])
            return

        if msg_type == "armed":
            self.set_armed(bool(msg.get("armed", False)))
            return

        if msg_type == "alert":
            self.log(msg.get("level", "WARN"), msg.get("message", ""))

    # live WebSocket telemetry ingestion & file loading

    @QtCore.Slot(str)
    def ingest_ws_message(self, raw_message: str):
        """ingests incoming WebSocket JSON / JSONL frames into control state and live telemetry."""
        for line in raw_message.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                self._handle_control_message(parsed)

        new_channels, ingested_records, self._live_t0, self._latest_telemetry = (
            ingest_ws_telemetry_frames(
                raw_message,
                self._known_channels,
                self._live_records,
                self._live_seconds,
                self._live_t0,
                self._latest_telemetry,
            )
        )
        for rec in ingested_records:
            self.telemetry_point_received.emit(rec)
        if new_channels:
            self.channels_changed.emit()
        if ingested_records:
            self.telemetry_changed.emit()

    @QtCore.Slot(str, str, result="QVariant")
    @QtCore.Slot(str, result="QVariant")
    def load_data(self, mode_or_path: str, file_path: str = "") -> dict:
        """loads telemetry data (.csv or .jsonl) from the target file and emits data_loaded."""
        if file_path:
            mode = mode_or_path
            target = file_path
        else:
            mode = "external"
            target = mode_or_path

        if not target:
            self.log_warn("No data file specified to load.")
            return {}

        try:
            resolved_path = resolve_data_file(target, self._known_channels)
            records, seconds_list, cols = parse_telemetry_file(resolved_path)
        except Exception as err:
            self.log_error(f'Failed to parse data file "{target}": {err}')
            return {}

        new_ch = False
        for c in cols:
            if register_channel_if_missing(self._known_channels, c):
                new_ch = True
        if new_ch:
            self.channels_changed.emit()

        self._loaded_records = records
        self._loaded_seconds = seconds_list
        min_t = seconds_list[0] if seconds_list else 0.0
        max_t = seconds_list[-1] if seconds_list else 0.0

        self._loaded_meta = {
            "source": mode,
            "path": target,
            "resolvedPath": str(resolved_path),
            "name": Path(target).name,
            "columns": list(cols),
            "count": len(records),
            "minTime": min_t,
            "maxTime": max_t,
            "duration": max(0.0, max_t - min_t),
        }

        self.log_info(
            f'Loaded data "{Path(target).name}" ({mode}, {len(records)} samples)'
        )
        self.data_loaded.emit(mode, target, self._loaded_meta)
        self.telemetry_changed.emit()
        return self._loaded_meta

    @QtCore.Slot(str, str, float, float, int, bool, int, result="QVariantMap")
    def get_channel_data(
        self,
        source_mode: str,
        channel: str,
        t_start: float,
        t_end: float,
        max_buckets: int = 300,
        filter_outliers_3std: bool = False,
        smoothing_window: int = 1,
    ) -> dict:
        """
        returns windowed, optionally 3-std outlier-filtered, bucket-downsampled,
        and smoothed time-series points for a given channel.
        """
        # use loaded file records when in local/remote/external mode, and live stream records in live mode
        use_loaded = source_mode != "live"
        records = self._loaded_records if use_loaded else self._live_records
        seconds_list = self._loaded_seconds if use_loaded else self._live_seconds

        return query_channel_series(
            records=records,
            seconds_list=seconds_list,
            channel=channel,
            t_start=t_start,
            t_end=t_end,
            max_buckets=max_buckets,
            filter_outliers_3std=filter_outliers_3std,
            smoothing_window=smoothing_window,
        )

    @QtCore.Slot(str, result=str)
    @QtCore.Slot(result=str)
    def open_data(self, open_where: str = "") -> str:
        open_dir = open_where if open_where else Path.home()

        file = QFileDialog.get_open_file_name(
            None,
            "Open data",
            f"{open_dir}",
            "Telemetry Files (*.csv *.jsonl);;CSV Files (*.csv);;JSONL Files (*.jsonl);;All Files (*)",
        )

        if file[0]:
            msg = f'User opened data "{file[0]}"'
            self.log_info(msg)
            self.data_opened.emit(file[0])
            self.load_data("external", file[0])
            return file[0]
        else:
            self.log_info("Nothing picked.")
            return ""
