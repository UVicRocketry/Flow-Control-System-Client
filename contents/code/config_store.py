# This Python file uses the following encoding: utf-8
"""Application and UI configuration store (`config_store.py`)."""

from PySide6 import QtCore

from config_manager import (
    CONFIG_DIR,
    CONFIG_FILE,
    is_dev_environment,
    read_app_config,
    write_app_config,
)

VALID_LOG_LEVELS = frozenset({"INFO", "WARN", "ERR"})


class ConfigStore(QtCore.QObject):
    """Manages reading, mutating, and persisting `config.json` settings."""

    config_changed = QtCore.Signal()
    server_url_changed = QtCore.Signal(str)
    auto_reconnect_changed = QtCore.Signal(bool)
    reconnect_interval_ms_changed = QtCore.Signal(int)
    view_refresh_hz_changed = QtCore.Signal(int)
    min_log_level_changed = QtCore.Signal(str)
    external_data_changed = QtCore.Signal()

    def __init__(self, log_manager=None, parent=None):
        super().__init__(parent)
        self._log_manager = log_manager
        self._config_data: dict = {}

    def _log_error(self, msg: str) -> None:
        if self._log_manager is not None:
            self._log_manager.log_error(msg)

    def _log_info(self, msg: str) -> None:
        if self._log_manager is not None:
            self._log_manager.log_info(msg)

    @property
    def config_data(self) -> dict:
        return self._config_data

    @property
    def config_dir(self) -> str:
        return str(CONFIG_DIR)

    @property
    def config_file(self) -> str:
        return str(CONFIG_FILE)

    @property
    def is_dev_mode(self) -> bool:
        return is_dev_environment()

    def _ui_section(self) -> dict:
        ui = self._config_data.get("ui")
        return ui if isinstance(ui, dict) else {}

    def _ensure_section(self, name: str) -> dict:
        sec = self._config_data.get(name)
        if not isinstance(sec, dict):
            sec = {}
            self._config_data[name] = sec
        return sec

    @property
    def server_url(self) -> str:
        server_sec = self._config_data.get("server", {})
        if not isinstance(server_sec, dict):
            return "ws://127.0.0.1:8080/ws"
        return str(server_sec.get("default_url", "ws://127.0.0.1:8080/ws"))

    @server_url.setter
    def server_url(self, url: str) -> None:
        clean = url.strip()
        if not clean:
            return
        server_sec = self._ensure_section("server")
        if server_sec.get("default_url") != clean:
            server_sec["default_url"] = clean
            self.save_config(self._config_data)
            self.server_url_changed.emit(clean)

    @property
    def auto_reconnect(self) -> bool:
        server_sec = self._config_data.get("server", {})
        if not isinstance(server_sec, dict):
            return True
        return bool(server_sec.get("auto_reconnect", True))

    @auto_reconnect.setter
    def auto_reconnect(self, enabled: bool) -> None:
        val = bool(enabled)
        server_sec = self._ensure_section("server")
        if server_sec.get("auto_reconnect") != val:
            server_sec["auto_reconnect"] = val
            self.save_config(self._config_data)
            self.auto_reconnect_changed.emit(val)

    @property
    def reconnect_interval_ms(self) -> int:
        server_sec = self._config_data.get("server", {})
        if not isinstance(server_sec, dict):
            return 2000
        return int(server_sec.get("reconnect_interval_ms", 2000))

    @reconnect_interval_ms.setter
    def reconnect_interval_ms(self, interval: int) -> None:
        val = int(interval)
        server_sec = self._ensure_section("server")
        if server_sec.get("reconnect_interval_ms") != val:
            server_sec["reconnect_interval_ms"] = val
            self.save_config(self._config_data)
            self.reconnect_interval_ms_changed.emit(val)

    @property
    def view_refresh_hz(self) -> int:
        return max(1, min(120, int(self._ui_section().get("view_refresh_hz", 20))))

    @view_refresh_hz.setter
    def view_refresh_hz(self, hz: int) -> None:
        clamped = max(1, min(120, int(hz)))
        ui_sec = self._ensure_section("ui")
        if ui_sec.get("view_refresh_hz") != clamped:
            ui_sec["view_refresh_hz"] = clamped
            self.save_config(self._config_data)
            self.view_refresh_hz_changed.emit(clamped)

    @property
    def min_log_level(self) -> str:
        raw = str(self._ui_section().get("min_log_level", "INFO")).strip().upper()
        return raw if raw in VALID_LOG_LEVELS else "INFO"

    @min_log_level.setter
    def min_log_level(self, level: str) -> None:
        norm = str(level or "").strip().upper()
        if norm not in VALID_LOG_LEVELS:
            return
        ui_sec = self._ensure_section("ui")
        if ui_sec.get("min_log_level") != norm:
            ui_sec["min_log_level"] = norm
            self.save_config(self._config_data)
            self.min_log_level_changed.emit(norm)

    def load_config(self) -> dict:
        """Loads configuration from CONFIG_FILE via config_manager."""
        self._config_data = read_app_config(self._log_error)
        self.config_changed.emit()
        self.server_url_changed.emit(self.server_url)
        self.auto_reconnect_changed.emit(self.auto_reconnect)
        self.reconnect_interval_ms_changed.emit(self.reconnect_interval_ms)
        self.view_refresh_hz_changed.emit(self.view_refresh_hz)
        self.min_log_level_changed.emit(self.min_log_level)
        self.external_data_changed.emit()
        return self._config_data

    def save_config(self, data: dict) -> bool:
        """Persists dictionary data to CONFIG_FILE via config_manager."""
        if write_app_config(data, self._log_error):
            self._config_data = data
            self.config_changed.emit()
            return True
        return False

    def get_setting(self, key: str, default=None):
        return self._config_data.get(key, default)

    def set_setting(self, key: str, value) -> None:
        self._config_data[key] = value
        self.save_config(self._config_data)

    def get_split_config(self) -> dict:
        """Returns saved split view state, pane positions, and ratio."""
        ui_sec = self._ui_section()
        try:
            ratio = float(ui_sec.get("split_ratio", 0.5))
        except (TypeError, ValueError):
            ratio = 0.5
        return {
            "split_active": bool(ui_sec.get("split_active", False)),
            "left_page": str(ui_sec.get("left_page", "dashboard") or "dashboard"),
            "right_page": str(ui_sec.get("right_page", "") or ""),
            "last_right_page": str(ui_sec.get("last_right_page", "") or ""),
            "focused_pane": str(ui_sec.get("focused_pane", "left") or "left"),
            "split_ratio": max(0.05, min(0.95, ratio)),
        }

    def save_split_config(
        self,
        split_active: bool,
        left_page: str,
        right_page: str,
        last_right_page: str,
        focused_pane: str,
        split_ratio: float,
    ) -> None:
        """Persists split view state, pane positions, and sizing ratio."""
        ui_sec = self._ensure_section("ui")
        ratio = round(max(0.05, min(0.95, float(split_ratio))), 4)
        updated = {
            "split_active": bool(split_active),
            "left_page": str(left_page or "dashboard"),
            "right_page": str(right_page or ""),
            "last_right_page": str(last_right_page or ""),
            "focused_pane": "right" if focused_pane == "right" else "left",
            "split_ratio": ratio,
        }
        if any(ui_sec.get(k) != v for k, v in updated.items()):
            ui_sec.update(updated)
            self.save_config(self._config_data)

    @property
    def external_data(self) -> list[str]:
        raw = self._config_data.get("external_data", [])
        if not isinstance(raw, list):
            return []
        return [str(p) for p in raw if str(p).strip()]

    def set_external_data_list(self, paths: list[str]) -> None:
        self._config_data["external_data"] = paths
        self.save_config(self._config_data)
        self.external_data_changed.emit()

    def add_external_data(self, file_path: str) -> None:
        """Persists an externally opened telemetry file path in config.json."""
        clean = file_path.strip()
        if not clean:
            return
        current = self.external_data
        updated = [clean] + [p for p in current if p != clean]
        if updated != current:
            self.set_external_data_list(updated)

    def hide_external_data(self, file_path: str) -> None:
        """Removes an external telemetry file from the persisted list."""
        from pathlib import Path

        clean = file_path.strip()
        current = self.external_data
        updated = [p for p in current if p != clean]
        if updated != current:
            self.set_external_data_list(updated)
            self._log_info(f'Hidden external log "{Path(clean).name}".')
