# This Python file uses the following encoding: utf-8
"""Thin QML facade composing the client's focused QObject controllers (`backend.py`)."""

import json
import sys
from pathlib import Path

from PySide6 import QtCore

from actuator_controller import ActuatorController
from camera_controller import CameraController
from config_manager import ensure_config_file_exists, is_dev_environment
from config_store import ConfigStore
from log_manager import LogManager
from telemetry_files import reveal_in_file_browser
from telemetry_store import TelemetryStore

ensure_config_file_exists()


class Backend(QtCore.QObject):
    """
    QObject bridge for PySide6/QML.
    Delegates configuration, camera, actuation, logs, and telemetry to focused
    controllers while preserving a stable signal/property/slot surface for QML.
    """

    config_changed = QtCore.Signal()
    server_url_changed = QtCore.Signal(str)
    auto_reconnect_changed = QtCore.Signal(bool)
    reconnect_interval_ms_changed = QtCore.Signal(int)
    connect_requested = QtCore.Signal()
    log_sent = QtCore.Signal(str, str)
    data_loaded = QtCore.Signal(str, str, "QVariant")
    local_data_changed = QtCore.Signal()
    remote_data_changed = QtCore.Signal()
    external_data_changed = QtCore.Signal()
    telemetry_changed = QtCore.Signal()
    channels_changed = QtCore.Signal()
    armed_changed = QtCore.Signal(bool)
    valves_changed = QtCore.Signal()
    valve_state_updated = QtCore.Signal(str, str)
    ws_send_requested = QtCore.Signal(str)
    disconnected = QtCore.Signal()
    recording_changed = QtCore.Signal(bool)
    server_recording_active_on_connect = QtCore.Signal(str)
    view_refresh_hz_changed = QtCore.Signal(int)
    min_log_level_changed = QtCore.Signal(str)
    camera_config_changed = QtCore.Signal()
    camera_active_changed = QtCore.Signal(bool)
    camera_toggle_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ws_connected = False
        self._prompted_server_recording = False

        self.log_manager = LogManager(self)
        self.config_store = ConfigStore(self.log_manager, self)
        self.camera_controller = CameraController(self.config_store, self)
        self.actuator_controller = ActuatorController(self)
        self.telemetry_store = TelemetryStore(self.config_store, self.log_manager, self)

        self._wire_controller_signals()
        self.load_config()
        self.refresh_local_data()

        env_type = (
            "Development (/contents/config/)"
            if is_dev_environment()
            else f"Standalone ({sys.platform})"
        )
        print(
            "[CONFIG] Environment: ",
            f"{env_type} | Config directory: {self.config_dir}",
        )

    def _wire_controller_signals(self) -> None:
        self.log_manager.log_sent.connect(self.log_sent)
        self.log_manager.local_data_changed.connect(self.local_data_changed)
        self.log_manager.remote_data_changed.connect(self.remote_data_changed)

        self.config_store.config_changed.connect(self.config_changed)
        self.config_store.server_url_changed.connect(self.server_url_changed)
        self.config_store.auto_reconnect_changed.connect(self.auto_reconnect_changed)
        self.config_store.reconnect_interval_ms_changed.connect(
            self.reconnect_interval_ms_changed
        )
        self.config_store.view_refresh_hz_changed.connect(
            self.telemetry_store.reschedule_ui_timer
        )
        self.config_store.view_refresh_hz_changed.connect(self.view_refresh_hz_changed)
        self.config_store.min_log_level_changed.connect(self.min_log_level_changed)
        self.config_store.external_data_changed.connect(self.external_data_changed)

        self.camera_controller.camera_config_changed.connect(self.camera_config_changed)
        self.camera_controller.camera_active_changed.connect(self.camera_active_changed)
        self.camera_controller.camera_toggle_requested.connect(
            self.camera_toggle_requested
        )

        self.actuator_controller.config_changed.connect(self.config_changed)
        self.actuator_controller.armed_changed.connect(self.armed_changed)
        self.actuator_controller.valves_changed.connect(self.valves_changed)
        self.actuator_controller.valve_state_updated.connect(self.valve_state_updated)

        self.telemetry_store.telemetry_changed.connect(self.telemetry_changed)
        self.telemetry_store.channels_changed.connect(self.channels_changed)
        self.telemetry_store.recording_changed.connect(self.recording_changed)
        self.telemetry_store.data_loaded.connect(self.data_loaded)

    # ------------------------------------------------------------------
    # Logging Slots
    # ------------------------------------------------------------------
    @QtCore.Slot(str)
    def log_info(self, msg: str) -> None:
        self.log_manager.log_info(msg)

    @QtCore.Slot(str, str)
    def log(self, level: str, msg: str) -> None:
        self.log_manager.log(level, msg)

    @QtCore.Slot(str)
    def info(self, msg: str) -> None:
        self.log_manager.log_info(msg)

    @QtCore.Slot(str)
    def warn(self, msg: str) -> None:
        self.log_manager.log_warn(msg)

    @QtCore.Slot(str)
    def err(self, msg: str) -> None:
        self.log_manager.log_error(msg)

    # ------------------------------------------------------------------
    # Config & UI Settings
    # ------------------------------------------------------------------
    @QtCore.Property(str, notify=config_changed)
    def config_dir(self) -> str:
        return self.config_store.config_dir

    @QtCore.Property(str, notify=server_url_changed)
    def server_url(self) -> str:
        return self.config_store.server_url

    @server_url.setter
    def server_url(self, url: str) -> None:
        self.config_store.server_url = url

    @QtCore.Property(bool, notify=auto_reconnect_changed)
    def auto_reconnect(self) -> bool:
        return self.config_store.auto_reconnect

    @auto_reconnect.setter
    def auto_reconnect(self, enabled: bool) -> None:
        self.config_store.auto_reconnect = enabled

    @QtCore.Property(int, notify=reconnect_interval_ms_changed)
    def reconnect_interval_ms(self) -> int:
        return self.config_store.reconnect_interval_ms

    @reconnect_interval_ms.setter
    def reconnect_interval_ms(self, interval: int) -> None:
        self.config_store.reconnect_interval_ms = interval

    @QtCore.Property(int, notify=view_refresh_hz_changed)
    def view_refresh_hz(self) -> int:
        return self.config_store.view_refresh_hz

    @view_refresh_hz.setter
    def view_refresh_hz(self, hz: int) -> None:
        self.config_store.view_refresh_hz = hz

    @QtCore.Property(str, notify=min_log_level_changed)
    def min_log_level(self) -> str:
        return self.config_store.min_log_level

    @min_log_level.setter
    def min_log_level(self, level: str) -> None:
        self.config_store.min_log_level = level

    @QtCore.Slot(result="QVariantMap")
    def load_config(self) -> dict:
        data = self.config_store.load_config()
        self.actuator_controller.seed_valves_from_config(data)
        self.camera_controller.apply_camera_transport()
        return data

    @QtCore.Slot(str)
    def set_min_log_level(self, level: str) -> None:
        self.min_log_level = level

    @QtCore.Slot(result="QVariantMap")
    def get_split_config(self) -> dict:
        return self.config_store.get_split_config()

    @QtCore.Slot(bool, str, str, str, str, float)
    def save_split_config(
        self,
        split_active: bool,
        left_page: str,
        right_page: str,
        last_right_page: str,
        focused_pane: str,
        split_ratio: float,
    ) -> None:
        self.config_store.save_split_config(
            split_active,
            left_page,
            right_page,
            last_right_page,
            focused_pane,
            split_ratio,
        )

    @QtCore.Slot()
    def connect(self) -> None:
        self.connect_requested.emit()

    @QtCore.Slot(str)
    def show_in_file_browser(self, url: str) -> None:
        reveal_in_file_browser(url, self.log_info, self.warn)

    # ------------------------------------------------------------------
    # Camera Controls
    # ------------------------------------------------------------------
    @QtCore.Property(str, notify=camera_config_changed)
    def camera_mode(self) -> str:
        return self.camera_controller.camera_mode

    @QtCore.Property(str, notify=camera_config_changed)
    def camera_profile(self) -> str:
        return self.camera_controller.camera_profile

    @QtCore.Property(str, notify=camera_config_changed)
    def camera_manual_target(self) -> str:
        return self.camera_controller.camera_manual_target

    @QtCore.Property(str, notify=camera_config_changed)
    def camera_username(self) -> str:
        return self.camera_controller.camera_username

    @QtCore.Property(str, notify=camera_config_changed)
    def camera_password(self) -> str:
        return self.camera_controller.camera_password

    @QtCore.Property(str, notify=camera_config_changed)
    def camera_rtsp_url(self) -> str:
        return self.camera_controller.camera_rtsp_url

    @QtCore.Slot(str, str, str)
    def set_camera_settings(self, mode: str, profile: str, manual_target: str) -> None:
        self.camera_controller.set_camera_settings(mode, profile, manual_target)

    @QtCore.Property(bool, notify=camera_active_changed)
    def camera_active(self) -> bool:
        return self.camera_controller.camera_active

    @QtCore.Slot(bool)
    def set_camera_active(self, active: bool) -> None:
        self.camera_controller.set_camera_active(active)

    @QtCore.Slot(QtCore.QObject)
    def configure_camera_player(self, player: QtCore.QObject) -> None:
        self.camera_controller.configure_camera_player(player)

    @QtCore.Slot()
    def toggle_camera(self) -> None:
        self.camera_controller.toggle_camera()

    @QtCore.Slot(str, str)
    def set_camera_credentials(self, username: str, password: str) -> None:
        self.camera_controller.set_camera_credentials(username, password)

    @QtCore.Slot(str)
    def set_camera_manual_target(self, target: str) -> None:
        self.camera_controller.set_camera_manual_target(target)

    # ------------------------------------------------------------------
    # Telemetry Config, Recording & Queries
    # ------------------------------------------------------------------
    @QtCore.Slot("QVariantList", result=bool)
    def save_graphs_config(self, cards: list) -> bool:
        return self.telemetry_store.save_graphs_config(cards)

    @QtCore.Property("QVariantMap", notify=telemetry_changed)
    def telemetry(self) -> dict:
        return self.telemetry_store.telemetry

    @QtCore.Property("QVariantMap", notify=telemetry_changed)
    def loaded_meta(self) -> dict:
        return self.telemetry_store.loaded_meta

    @QtCore.Property("QVariantList", notify=channels_changed)
    def default_graph_cards(self) -> list:
        return self.telemetry_store.default_graph_cards

    @QtCore.Property("QVariantList", notify=channels_changed)
    def available_channels(self) -> list:
        return self.telemetry_store.available_channels

    @QtCore.Slot(str, result="QVariantMap")
    def get_channel_meta(self, channel: str) -> dict:
        return self.telemetry_store.get_channel_meta(channel)

    @QtCore.Property(bool, notify=recording_changed)
    def recording(self) -> bool:
        return self.telemetry_store.recording

    @recording.setter
    def recording(self, active: bool) -> None:
        self.set_recording(active)

    @QtCore.Slot(bool)
    def set_recording(self, active: bool) -> None:
        self.telemetry_store.set_recording(
            active, self._ws_connected, self.ws_send_requested.emit
        )

    @QtCore.Slot(result=bool)
    def toggle_recording(self) -> bool:
        self.set_recording(not self.recording)
        return self.recording

    @QtCore.Slot(str)
    def pull_server_recording_state(self, filename: str = "") -> None:
        if not self._ws_connected:
            self.warn("Cannot pull server recording while disconnected.")
            return
        self.log_info("Pulling current recorded state from server...")
        self.log_manager.fetch_remote_file(
            self.server_url,
            filename,
            mode="pull_recording",
            on_saved_cb=lambda fname, dest, ow, _mode: (
                self.telemetry_store.apply_pulled_recording_file(
                    fname, dest, overwrote=ow
                )
            ),
        )

    # ------------------------------------------------------------------
    # Actuator & Connection State
    # ------------------------------------------------------------------
    @QtCore.Property(bool, notify=armed_changed)
    def armed(self) -> bool:
        return self.actuator_controller.armed

    @armed.setter
    def armed(self, value: bool) -> None:
        self.actuator_controller.armed = value

    @QtCore.Property("QVariantList", notify=config_changed)
    def valve_definitions(self) -> list:
        return self.actuator_controller.valve_definitions

    @QtCore.Property("QVariantMap", notify=valves_changed)
    def valves(self) -> dict:
        return self.actuator_controller.valves

    @QtCore.Slot(bool)
    def on_ws_connected_changed(self, connected: bool) -> None:
        connected = bool(connected)
        was_connected = self._ws_connected
        self._ws_connected = connected
        if connected and not was_connected:
            self._prompted_server_recording = False
            self.refresh_remote_data()
            rec_path = self.telemetry_store.record_file_path
            if self.recording and rec_path is not None:
                payload = {
                    "type": "record",
                    "command": "RECORD",
                    "active": True,
                    "filename": rec_path.name,
                }
                self.ws_send_requested.emit(json.dumps(payload))
        elif not connected:
            self._prompted_server_recording = False
            self.armed = False
            if self.recording:
                self.set_recording(False)
                self.warn("Server went offline; telemetry recording stopped.")
            if was_connected:
                self.disconnected.emit()

    @QtCore.Slot(str, str)
    def actuate_valve(self, valve_id: str, action: str) -> None:
        self.actuator_controller.actuate_valve(
            valve_id, action, self.ws_send_requested.emit, self.warn
        )

    @QtCore.Slot()
    def abort(self) -> None:
        self.actuator_controller.abort(self.ws_send_requested.emit, self.warn)

    # ------------------------------------------------------------------
    # Local, External & HTTP Remote Data Management
    # ------------------------------------------------------------------
    @QtCore.Property("QVariantList", notify=local_data_changed)
    def local_data(self) -> list:
        return self.log_manager.local_data

    @QtCore.Property("QVariantList", notify=remote_data_changed)
    def remote_data(self) -> list:
        return self.log_manager.remote_data

    @QtCore.Property("QVariantList", notify=external_data_changed)
    def external_data(self) -> list:
        return self.config_store.external_data

    @QtCore.Slot(str)
    def add_external_data(self, file_path: str) -> None:
        self.config_store.add_external_data(file_path)

    @QtCore.Slot(str)
    def hide_external_data(self, file_path: str) -> None:
        self.config_store.hide_external_data(file_path)

    @QtCore.Slot(result="QVariantList")
    def refresh_local_data(self) -> list:
        return self.log_manager.refresh_local_data()

    @QtCore.Slot()
    def refresh_remote_data(self) -> None:
        self.log_manager.refresh_remote_data(self.server_url)

    @QtCore.Slot(str)
    def download_remote_data(self, filename: str) -> None:
        self.log_manager.fetch_remote_file(
            self.server_url,
            filename,
            mode="download",
        )

    @QtCore.Slot(str, str)
    @QtCore.Slot(str)
    def push_data_to_remote(self, mode_or_path: str, filename: str = "") -> None:
        if not self._ws_connected:
            self.warn("Cannot push data: not connected to the valve cart server.")
            return
        target = filename if filename else mode_or_path
        self.log_manager.push_data_to_remote(
            self.server_url,
            target,
            self.telemetry_store.known_channels,
        )

    @QtCore.Slot(str, str, str, result=bool)
    def rename_data(self, mode: str, old_name: str, new_name: str) -> bool:
        return self.log_manager.rename_data(
            mode,
            old_name,
            new_name,
            self.config_store,
            self.server_url,
        )

    @QtCore.Slot(str, str, result=bool)
    def delete_data(self, mode: str, filename: str) -> bool:
        return self.log_manager.delete_data(
            mode,
            filename,
            self.config_store,
            self.server_url,
        )

    # ------------------------------------------------------------------
    # WebSocket Dispatch & Telemetry Queries
    # ------------------------------------------------------------------
    def _handle_init_or_config_msg(self, msg: dict) -> None:
        if "armed" in msg:
            self.armed = bool(msg["armed"])
        valves_payload = msg.get("valves")
        if isinstance(valves_payload, list):
            self.actuator_controller.apply_actuator_definitions(valves_payload)
        elif isinstance(valves_payload, dict):
            self.actuator_controller.apply_valves_map(valves_payload)
        channels_payload = msg.get("channels")
        if isinstance(channels_payload, dict):
            self.telemetry_store.apply_live_channels_metadata(channels_payload)
        if (
            bool(msg.get("recording", False))
            and not self.recording
            and not self._prompted_server_recording
        ):
            self._prompted_server_recording = True
            rec_name = str(msg.get("recording_filename") or msg.get("active_log") or "")
            self.server_recording_active_on_connect.emit(rec_name)

    def _handle_valve_state_msg(self, msg: dict) -> None:
        if "valve" in msg and "state" in msg:
            self.actuator_controller.apply_valve_state(msg["valve"], msg["state"])
        valves_map = msg.get("valves")
        if isinstance(valves_map, dict):
            self.actuator_controller.apply_valves_map(valves_map)

    def _handle_control_message(self, msg: dict) -> None:
        actuators_list = msg.get("actuators") or msg.get("valve_definitions")
        if isinstance(actuators_list, list):
            self.actuator_controller.apply_actuator_definitions(actuators_list)

        msg_type = msg.get("type")
        handlers = {
            "init": self._handle_init_or_config_msg,
            "actuators": self._handle_init_or_config_msg,
            "config": self._handle_init_or_config_msg,
            "valve_state": self._handle_valve_state_msg,
            "summary": self._handle_valve_state_msg,
            "armed": lambda m: setattr(self, "armed", bool(m.get("armed", False))),
            "remote_data_list": self.log_manager.handle_remote_data_list_msg,
            "alert": lambda m: self.log(m.get("level", "WARN"), m.get("message", "")),
        }
        handler = handlers.get(msg_type)
        if handler is not None:
            handler(msg)
        elif msg.get("identifier") == "FEEDBACK":
            data = msg.get("data", {})
            if isinstance(data, dict) and "valve" in data and "action" in data:
                self.actuator_controller.apply_valve_state(
                    data["valve"], data["action"]
                )

    @QtCore.Slot(str)
    def ingest_ws_message(self, raw_message: str) -> None:
        """Ingests incoming WebSocket frames into control and telemetry."""
        parsed_frames: list[dict] = []
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
                parsed_frames.append(parsed)

        self.telemetry_store.ingest_telemetry_frames(
            parsed_frames, self._ws_connected, self.ws_send_requested.emit
        )

    @QtCore.Slot(str, str, result="QVariant")
    @QtCore.Slot(str, result="QVariant")
    def load_data(self, mode_or_path: str, file_path: str = "") -> dict:
        if file_path:
            mode, target = mode_or_path, file_path
        else:
            mode, target = "external", mode_or_path
        return self.telemetry_store.load_data(mode, target)

    @QtCore.Slot(str, str, float, float, int, bool, int, str, result="QVariantMap")
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
        target_unit: str = "",
    ) -> dict:
        return self.telemetry_store.get_channel_data(
            source_mode,
            channel,
            t_start,
            t_end,
            max_buckets,
            filter_outliers_3std,
            smoothing_window,
            target_unit,
        )

    @QtCore.Slot(str, "QVariantList", result="QVariantMap")
    def get_batch_channel_data(self, source_mode: str, requests: list) -> dict:
        return self.telemetry_store.get_batch_channel_data(source_mode, requests)

    @QtCore.Slot(str, result=str)
    @QtCore.Slot(result=str)
    def open_data(self, open_where: str = "") -> str:
        from PySide6.QtWidgets import QFileDialog

        open_dir = open_where if open_where else str(Path.home())
        file_filter = (
            "Telemetry Files (*.csv *.jsonl);;"
            "CSV Files (*.csv);;"
            "JSONL Files (*.jsonl);;"
            "All Files (*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Open data", open_dir, file_filter
        )
        if file_path:
            self.log_info(f'User opened data "{file_path}"')
            self.add_external_data(file_path)
            self.load_data("external", file_path)
            return file_path
        self.log_info("Nothing picked.")
        return ""
