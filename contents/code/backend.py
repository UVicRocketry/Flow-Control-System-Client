# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Backend Controller
provides QObject bridge between PySide6/QML and config/telemetry helpers.
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
    ensure_config_file_exists,
    is_dev_environment,
    read_app_config,
    read_graphs_config,
    write_app_config,
)
from telemetry_files import (
    delete_data_file,
    list_local_data_files,
    parse_telemetry_file,
    rename_data_file,
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
    exposes configuration properties, file loading, and telemetry queries.
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
    local_data_changed = QtCore.Signal()
    remote_data_changed = QtCore.Signal()
    external_data_changed = QtCore.Signal()
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
        self._local_data = []
        self._remote_data = []
        self._pending_deletions = set()
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
        self.refresh_local_data()

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
        curr = self._config_data["server"].get("reconnect_interval_ms")
        if curr != interval:
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
        self.external_data_changed.emit()
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
        """loads default channels and cards from config/graphs/graphs.json."""
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
        defs = self._config_data.get("actuators") or self._config_data.get(
            "valves"
        )
        if isinstance(defs, list) and defs:
            self._apply_actuator_definitions(defs)

    def _apply_actuator_definitions(self, definitions: list):
        valid_defs = [
            dict(item)
            for item in definitions
            if isinstance(item, dict) and item.get("id")
        ]
        self._valve_definitions = valid_defs
        seeded = {}
        for item in valid_defs:
            vid = item["id"]
            default_st = self._normalize_valve_state(
                item.get("normal_state", "CLOSED")
            )
            seeded[vid] = self._valves.get(vid, default_st)
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
        """Disarms system and emits disconnect signals on True -> False."""
        connected = bool(connected)
        was_connected = self._ws_connected
        self._ws_connected = connected
        if connected and not was_connected:
            self.refresh_remote_data()
        elif not connected:
            self.set_armed(False)
            if was_connected:
                self.disconnected.emit()
                self.websocket_closed.emit()

    # local & remote data management

    @QtCore.Property("QVariantList", notify=local_data_changed)
    def local_data(self) -> list:
        return list(self._local_data)

    @QtCore.Property("QVariantList", notify=remote_data_changed)
    def remote_data(self) -> list:
        return list(self._remote_data)

    @QtCore.Property("QVariantList", notify=external_data_changed)
    def external_data(self) -> list:
        raw = self._config_data.get("external_data", [])
        if not isinstance(raw, list):
            return []
        return [str(p) for p in raw if str(p).strip()]

    def _set_external_data_list(self, paths: list[str]):
        self._config_data["external_data"] = paths
        self.save_config(self._config_data)
        self.external_data_changed.emit()

    @QtCore.Slot(str)
    def add_external_data(self, file_path: str):
        """Persists an externally opened telemetry file path in config.json."""
        clean = file_path.strip()
        if not clean:
            return
        current = self.external_data
        updated = [clean] + [p for p in current if p != clean]
        if updated != current:
            self._set_external_data_list(updated)

    @QtCore.Slot(str)
    def hide_external_data(self, file_path: str):
        """Removes an external telemetry file from the persisted list."""
        clean = file_path.strip()
        current = self.external_data
        updated = [p for p in current if p != clean]
        if updated != current:
            self._set_external_data_list(updated)
            self.log_info(f'Hidden external log "{Path(clean).name}".')

    @QtCore.Slot(result="QVariantList")
    def refresh_local_data(self) -> list:
        """Scans CONFIG_DIR / 'data' for telemetry files."""
        self._local_data = list_local_data_files()
        self.local_data_changed.emit()
        return self._local_data

    @QtCore.Slot()
    def refresh_remote_data(self):
        """Requests the remote telemetry file list from the server."""
        payload = {"type": "remote_data_req", "operation": "list"}
        self.ws_send_requested.emit(json.dumps(payload))

    @QtCore.Slot(str)
    def download_remote_data(self, filename: str):
        """Requests a remote telemetry file to save into local data."""
        clean_name = Path(filename.strip()).name
        if not clean_name:
            self.log_warn("No remote file selected to download.")
            return
        payload = {
            "type": "remote_data_req",
            "operation": "get",
            "filename": clean_name,
            "mode": "download",
        }
        self.ws_send_requested.emit(json.dumps(payload))

    @QtCore.Slot(str, str)
    def mark_data_for_deletion(self, mode: str, filename: str):
        self._pending_deletions.add((mode, filename))

    @QtCore.Slot(str, str)
    def unmark_data_for_deletion(self, mode: str, filename: str):
        self._pending_deletions.discard((mode, filename))

    @QtCore.Slot(str, str, str, result=bool)
    def rename_data(self, mode: str, old_name: str, new_name: str) -> bool:
        """Renames a local, external, or remote telemetry file."""
        new_clean = Path(new_name.strip()).name
        if not new_clean:
            self.log_warn("New filename cannot be empty.")
            return False

        if mode == "remote":
            if Path(new_clean).suffix == "" and Path(old_name).suffix:
                new_clean = new_clean + Path(old_name).suffix
            payload = {
                "type": "remote_data_req",
                "operation": "rename",
                "old_name": old_name,
                "new_name": new_clean,
            }
            self.ws_send_requested.emit(json.dumps(payload))
            self._remote_data = [
                new_clean if item == old_name else item
                for item in self._remote_data
            ]
            self.remote_data_changed.emit()
            self.log_info(
                f'Requested remote rename "{old_name}" -> "{new_clean}".'
            )
            return True

        try:
            dst = rename_data_file(mode, old_name, new_clean)
            if mode == "local":
                self.refresh_local_data()
            elif mode == "external":
                updated = [
                    str(dst) if p == old_name else p
                    for p in self.external_data
                ]
                self._set_external_data_list(updated)
            self.log_info(f'Renamed "{Path(old_name).name}" to "{dst.name}".')
            return True
        except Exception as err:
            self.log_error(f'Failed to rename "{old_name}": {err}')
            return False

    @QtCore.Slot(str, str, result=bool)
    def delete_data(self, mode: str, filename: str) -> bool:
        """Deletes a local, external, or remote telemetry file."""
        self._pending_deletions.discard((mode, filename))
        if mode == "remote":
            payload = {
                "type": "remote_data_req",
                "operation": "delete",
                "filename": filename,
            }
            self.ws_send_requested.emit(json.dumps(payload))
            if filename in self._remote_data:
                self._remote_data.remove(filename)
                self.remote_data_changed.emit()
            self.log_info(f'Deleted remote file "{filename}".')
            return True

        try:
            deleted = delete_data_file(mode, filename)
            if mode == "local":
                self.refresh_local_data()
            elif mode == "external":
                updated = [p for p in self.external_data if p != filename]
                self._set_external_data_list(updated)
            self.log_info(f'Deleted "{deleted.name}".')
            return True
        except FileNotFoundError:
            if mode == "local":
                self.refresh_local_data()
            elif mode == "external":
                updated = [p for p in self.external_data if p != filename]
                self._set_external_data_list(updated)
            return False
        except Exception as err:
            self.log_error(f'Failed to delete "{filename}": {err}')
            return False

    @QtCore.Slot(str, str)
    def actuate_valve(self, valve_id: str, action: str):
        """Validates armed/interlock state and emits an outbound command."""
        if not self._armed:
            self.log_warn(
                f"Cannot actuate {valve_id}: system is SAFE (disarmed)."
            )
            return

        vdef = self._get_valve_def(valve_id)
        if vdef.get("external", False):
            self.log_warn(f"{valve_id} is externally controlled.")
            return

        current = self._valves.get(valve_id, "")
        if vdef.get("single_use", False) and current in (
            "FIRED",
            "DISCONNECTED",
        ):
            self.log_warn(
                f"{valve_id} is single-use and already {current}."
            )
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
        """Sends emergency abort command regardless of armed state."""
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

    def _apply_valves_map(self, valves_map: dict):
        for vid, st in valves_map.items():
            self._valves[vid] = self._normalize_valve_state(st)
        self.valves_changed.emit()

    def _handle_init_or_config_msg(self, msg: dict):
        if "armed" in msg:
            self.set_armed(bool(msg["armed"]))
        valves_payload = msg.get("valves")
        if isinstance(valves_payload, list):
            self._apply_actuator_definitions(valves_payload)
        elif isinstance(valves_payload, dict):
            self._apply_valves_map(valves_payload)

    def _handle_valve_state_msg(self, msg: dict):
        if "valve" in msg and "state" in msg:
            self._apply_valve_state(msg["valve"], msg["state"])
        valves_map = msg.get("valves")
        if isinstance(valves_map, dict):
            self._apply_valves_map(valves_map)

    def _handle_remote_data_list_msg(self, msg: dict):
        raw_files = msg.get("files", [])
        parsed_names = []
        if isinstance(raw_files, list):
            for entry in raw_files:
                if isinstance(entry, dict) and entry.get("name"):
                    parsed_names.append(str(entry["name"]))
                elif isinstance(entry, str) and entry.strip():
                    parsed_names.append(entry.strip())
        self._remote_data = parsed_names
        self.remote_data_changed.emit()

    def _handle_remote_data_content_msg(self, msg: dict):
        fname = Path(str(msg.get("filename", ""))).name
        content = msg.get("content", "")
        req_mode = str(msg.get("mode", "download")).lower()
        if not fname:
            return
        dest_dir = CONFIG_DIR / "data"
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / fname
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(str(content))
            self.refresh_local_data()
            if req_mode == "load":
                self._load_resolved_file("remote", fname, dest_path)
            else:
                self.log_info(f'Downloaded "{fname}" to local data.')
        except Exception as err:
            self.log_error(f'Failed to save remote file "{fname}": {err}')

    def _handle_control_message(self, msg: dict):
        msg_type = msg.get("type")
        ident = msg.get("identifier")

        actuators_list = msg.get("actuators") or msg.get("valve_definitions")
        if isinstance(actuators_list, list):
            self._apply_actuator_definitions(actuators_list)

        if msg_type in ("init", "actuators", "config"):
            self._handle_init_or_config_msg(msg)
        elif msg_type in ("valve_state", "summary"):
            self._handle_valve_state_msg(msg)
        elif ident == "FEEDBACK":
            data = msg.get("data", {})
            if isinstance(data, dict) and "valve" in data and "action" in data:
                self._apply_valve_state(data["valve"], data["action"])
        elif msg_type == "armed":
            self.set_armed(bool(msg.get("armed", False)))
        elif msg_type == "remote_data_list":
            self._handle_remote_data_list_msg(msg)
        elif msg_type == "remote_data_content":
            self._handle_remote_data_content_msg(msg)
        elif msg_type == "alert":
            self.log(msg.get("level", "WARN"), msg.get("message", ""))

    # live WebSocket telemetry ingestion & file loading

    @QtCore.Slot(str)
    def ingest_ws_message(self, raw_message: str):
        """ingests incoming WebSocket frames into control and telemetry."""
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

        res = ingest_ws_telemetry_frames(
            raw_message,
            self._known_channels,
            self._live_records,
            self._live_seconds,
            self._live_t0,
            self._latest_telemetry,
        )
        new_channels, ingested, self._live_t0, self._latest_telemetry = res
        for rec in ingested:
            self.telemetry_point_received.emit(rec)
        if new_channels:
            self.channels_changed.emit()
        if ingested:
            self.telemetry_changed.emit()

    def _load_resolved_file(
        self, mode: str, target: str, resolved_path: Path
    ) -> dict:
        try:
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

        name = Path(target).name
        self.log_info(f'Loaded data "{name}" ({mode}, {len(records)} samples)')
        self.data_loaded.emit(mode, target, self._loaded_meta)
        self.telemetry_changed.emit()
        return self._loaded_meta

    @QtCore.Slot(str, str, result="QVariant")
    @QtCore.Slot(str, result="QVariant")
    def load_data(self, mode_or_path: str, file_path: str = "") -> dict:
        """loads telemetry data (.csv or .jsonl) from the target file."""
        if file_path:
            mode = mode_or_path
            target = file_path
        else:
            mode = "external"
            target = mode_or_path

        if not target:
            self.log_warn("No data file specified to load.")
            return {}

        if mode == "remote" and self._ws_connected:
            clean_name = Path(target.strip()).name
            local_cand = CONFIG_DIR / "data" / clean_name
            if not local_cand.exists():
                payload = {
                    "type": "remote_data_req",
                    "operation": "get",
                    "filename": clean_name,
                    "mode": "load",
                }
                self.ws_send_requested.emit(json.dumps(payload))
                return {}

        try:
            resolved_path = resolve_data_file(target, self._known_channels)
        except Exception as err:
            self.log_error(f'Failed to resolve data file "{target}": {err}')
            return {}

        return self._load_resolved_file(mode, target, resolved_path)

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
        returns windowed, optionally 3-std outlier-filtered, bucket-downsampled
        and smoothed time-series points for a given channel.
        """
        # use loaded file records in history mode, and live records in live
        use_loaded = source_mode != "live"
        records = self._loaded_records if use_loaded else self._live_records
        seconds_list = (
            self._loaded_seconds if use_loaded else self._live_seconds
        )

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
        file_filter = (
            "Telemetry Files (*.csv *.jsonl);;"
            "CSV Files (*.csv);;"
            "JSONL Files (*.jsonl);;"
            "All Files (*)"
        )

        file = QFileDialog.get_open_file_name(
            None,
            "Open data",
            f"{open_dir}",
            file_filter,
        )

        if file[0]:
            msg = f'User opened data "{file[0]}"'
            self.log_info(msg)
            self.add_external_data(file[0])
            self.data_opened.emit(file[0])
            self.load_data("external", file[0])
            return file[0]
        else:
            self.log_info("Nothing picked.")
            return ""
