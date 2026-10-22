# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Backend Controller
Provides QObject bridge between PySide6/QML and configuration management.
Manages application configuration, server connection settings, and persistence.
"""

import sys
import os
import json
import shutil
import subprocess
import time
from pathlib import Path

from PySide6 import QtCore
from PySide6.QtWidgets import QFileDialog
from __feature__ import snake_case, true_property

assert snake_case, true_property

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent


def get_default_config_dir() -> Path:
    """
    Returns the bundled/source default configuration directory
    (/contents/config/).
    Used directly in development, and bundled as default template for
    standalone packages.
    """
    # 1. PyInstaller single-file temporary bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_cfg = Path(sys._MEIPASS) / "contents" / "config"
        if meipass_cfg.exists():
            return meipass_cfg
        return Path(sys._MEIPASS) / "config"

    # 2. PyInstaller onedir distribution
    exe_dir = Path(sys.executable).resolve().parent
    for sub in [
        exe_dir / "_internal" / "contents" / "config",
        exe_dir / "contents" / "config",
        exe_dir / "config",
    ]:
        if sub.exists():
            return sub

    # 3. Source repository tree (/contents/config/)
    src_cfg = CURRENT_DIR.parent / "config"
    return src_cfg


def get_user_config_dir() -> Path:
    """
    Returns the standard OS-specific user configuration directory:
    - Linux / Unix: $XDG_CONFIG_HOME/flow-control
      (default ~/.config/flow-control)
    - Windows: %APPDATA%/FlowControl (default ~/AppData/Roaming/FlowControl)
    - macOS: ~/Library/Application Support/FlowControl
    """
    if sys.platform.startswith("win32"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "FlowControl"
        return Path.home() / "AppData" / "Roaming" / "FlowControl"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FlowControl"
    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / "flow-control"
        return Path.home() / ".config" / "flow-control"


def is_dev_environment() -> bool:
    """
    Determines whether the application is running in a development environment.
    - Forced dev mode: FLOW_CONTROL_DEV=1
    - Forced user mode: FLOW_CONTROL_DEV=0 or FLOW_CONTROL_USE_USER_CONFIG=1
    - Standalone package (PyInstaller / frozen): False
    - Running from source tree: True
    """
    env_force = os.environ.get("FLOW_CONTROL_DEV")
    if env_force is not None:
        return env_force.strip() in ("1", "true", "True", "yes")

    if os.environ.get("FLOW_CONTROL_USE_USER_CONFIG") == "1":
        return False

    return not getattr(sys, "frozen", False)


def get_config_dir() -> Path:
    """
    Resolves the active configuration directory:
    - In dev mode: pulls directly from /contents/config/
    - In standalone packages: uses the OS-specific user config directory,
      initializing missing files from /contents/config/ as defaults.
    """
    if is_dev_environment():
        dev_dir = get_default_config_dir()
        try:
            dev_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return dev_dir

    # Standalone packaged distribution
    user_dir = get_user_config_dir()
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        print(
            f"""
        [CONFIG] Notice: Cannot write to {user_dir} ({err}).
         Falling back to temp directory.
        """,
            file=sys.stderr,
        )
        tmp_base = os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
        fallback_dir = Path(tmp_base) / "flow-control"
        try:
            fallback_dir.mkdir(parents=True, exist_ok=True)
            user_dir = fallback_dir
        except OSError:
            user_dir = get_default_config_dir()

    # Seed default configuration files from bundled template if not yet present
    default_dir = get_default_config_dir()
    if default_dir.exists() and default_dir.is_dir():
        for src_file in default_dir.glob("*.json"):
            dest_file = user_dir / src_file.name
            if not dest_file.exists():
                try:
                    shutil.copy2(src_file, dest_file)
                    print(
                        "[CONFIG] Init: ",
                        f"default user config: {dest_file}"
                    )
                except Exception as err:
                    print(
                        "[CONFIG] Warning: ",
                        f"Could not copy template {src_file.name}: {err}",
                        file=sys.stderr,
                    )

    return user_dir


# Active configuration locations
CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_default_config_file() -> Path:
    """Returns the path to the template config/config.json."""
    return get_default_config_dir() / "config.json"


def ensure_config_file_exists():
    """
    populates CONFIG_FILE if absent
    """
    if not CONFIG_FILE.exists():
        template_file = get_default_config_file()
        if template_file.exists():
            try:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_file, CONFIG_FILE)
                print(
                    "[CONFIG] Init: ",
                    f"config file from {template_file} -> {CONFIG_FILE}",
                )
            except Exception as err:
                print(
                    "[CONFIG] Notice: ",
                    f"Could not copy template config to {CONFIG_FILE}: {err}",
                    file=sys.stderr,
                )
        else:
            print(
                "[CONFIG] Warning: ",
                f"Template config file not found at {template_file}",
                file=sys.stderr,
            )


ensure_config_file_exists()


class Backend(QtCore.QObject):
    """
    QObject bridge for PySide6/QML.
    exposes configuration properties and settings
    """

    # Signals
    config_changed = QtCore.Signal()
    server_url_changed = QtCore.Signal(str)
    auto_reconnect_changed = QtCore.Signal(bool)
    reconnect_interval_ms_changed = QtCore.Signal(int)
    connect_requested = QtCore.Signal()
    log_sent = QtCore.Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_data = {}
        self.load_config()

        env_type = (
            "Development (/contents/config/)"
            if is_dev_environment()
            else f"Standalone ({sys.platform})"
        )
        print(
            "[CONFIG] Environment: ",
            f"{env_type} | Config directory: {CONFIG_DIR}"
        )

        # logs push to UI and stdout

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
        """Logger for QML"""
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
        """Loads configuration from CONFIG_FILE"""
        if CONFIG_FILE.exists():
            target_path = CONFIG_FILE
        else:
            get_default_config_file()

        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    self._config_data = json.load(f)
            except Exception as err:
                self.log_error(f"Error reading {target_path}: {err}.")
                self._config_data = {}
        else:
            self.log_error(f"No configuration file found at {target_path}.")
            self._config_data = {}

        ensure_config_file_exists()

        # Environment variable override takes highest precedence for server URL
        env_url = os.environ.get("FLOW_CONTROL_WS_URL")
        if env_url:
            if "server" not in self._config_data:
                self._config_data["server"] = {}
            self._config_data["server"]["default_url"] = env_url

        self.config_changed.emit()
        self.server_url_changed.emit(self.server_url)
        self.auto_reconnect_changed.emit(self.auto_reconnect)
        self.reconnect_interval_ms_changed.emit(self.reconnect_interval_ms)
        return self._config_data

    @QtCore.Slot("QVariantMap", result=bool)
    def save_config(self, data: dict) -> bool:
        """Saves dictionary data to CONFIG_FILE."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self._config_data = data
            self.config_changed.emit()
            return True

        except Exception as err:
            self.log_error(f"Couldnt save config to {CONFIG_FILE}: {err}")
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
        """Signals QML/listeners to initiate WebSocket connection."""
        self.connect_requested.emit()

    @QtCore.Slot()
    def connect(self):
        """Connection entrypoint called on startup."""
        self.connect_to_server()

    @QtCore.Slot(str)
    def show_in_file_browser(self, url: str):
        target_file = Path(url).resolve()
        target_dir = target_file.parent
        try:
            if sys.platform.startswith("linux"):
                cmd = [
                    "dbus-send",
                    "--session",
                    "--dest=org.freedesktop.FileManager1",
                    "--type=method_call",
                    "/org/freedesktop/FileManager1",
                    "org.freedesktop.FileManager1.ShowItems",
                    f"array:string:file://{target_file}",
                    "string:",
                ]
                res = subprocess.run(cmd, capture_output=True, timeout=1)
                if res.returncode == 0:
                    self.log_info(f"Showing in file manager: {target_file.name}")
                    return

                # Fallback to xdg-open on directory
                if shutil.which("xdg-open"):
                    subprocess.Popen(["xdg-open", str(target_dir)])
                    self.log_info(f"Showing in data folder: {target_dir}")
                    return

            elif sys.platform == "win32":  # windows
                subprocess.Popen(f'explorer /select,"{target_file}"')
                self.log_info(f"Showing file in Explorer: {target_file.name}")
                return

            elif sys.platform == "darwin":  # macos
                subprocess.Popen(["open", "-R", str(target_file)])
                self.log_info(f"Showing file in Finder: {target_file.name}")
                return

        except Exception as e:
            self.log_warn(f"Failed to open data file location: {e}")

    @QtCore.Slot(str)
    def open_data(self, open_where: str = "") -> str:
        open_dir = open_where if not open_where else Path.home()

        file = QFileDialog.get_open_file_name(
            None, "Open data", f"{open_dir}", ".csv"
        )

        if file[0]:
            msg = f'User opened data "{file[0]}"'
            self.data_opened.emit(file[0])
        else:
            msg = "Nothing picked."

        self.log_info(msg)
        return
