# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Backend Controller
Provides QObject bridge between PySide6/QML and native QWebSocket.
Manages application configuration across platforms and environments.
"""

import sys
import os
import json
import shutil
from pathlib import Path
from PySide6 import QtCore

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
                    print(f"[CONFIG] Initialized default user config: {dest_file}")
                except Exception as err:
                    print(
                        f"[CONFIG] Warning: Could not copy template {src_file.name}: {err}",
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
    """Ensures CONFIG_FILE exists by copying from template config/config.json if absent."""
    if not CONFIG_FILE.exists():
        template_file = get_default_config_file()
        if template_file.exists():
            try:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_file, CONFIG_FILE)
                print(
                    f"[CONFIG] Initialized config file from {template_file} -> {CONFIG_FILE}"
                )
            except Exception as err:
                print(
                    f"[CONFIG] Notice: Could not copy template config to {CONFIG_FILE}: {err}",
                    file=sys.stderr,
                )
        else:
            print(
                f"[CONFIG] Warning: Template config file not found at {template_file}",
                file=sys.stderr,
            )


ensure_config_file_exists()


class Backend(QtCore.QObject):
    """
    QObject bridge for PySide6/QML.
    Exposes configuration properties and settings accessors.
    """

    config_changed = QtCore.Signal()
    server_url_changed = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_data = {}
        self.load_config()

        env_type = (
            "Development (/contents/config/)"
            if is_dev_environment()
            else f"Standalone ({sys.platform})"
        )
        print(f"[CONFIG] Environment: {env_type} | Config directory: {CONFIG_DIR}")

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

    @QtCore.Slot(result="QVariantMap")
    def load_config(self) -> dict:
        """Loads configuration from CONFIG_FILE, falling back to template config/config.json."""
        target_path = CONFIG_FILE if CONFIG_FILE.exists() else get_default_config_file()
        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    self._config_data = json.load(f)
            except Exception as err:
                print(f"[CONFIG] Error reading {target_path}: {err}.", file=sys.stderr)
                self._config_data = {}
        else:
            print(
                f"[CONFIG] Error: No configuration file found at {target_path}.",
                file=sys.stderr,
            )
            self._config_data = {}

        ensure_config_file_exists()
        self.config_changed.emit()
        self.server_url_changed.emit(self.server_url)
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
            self.server_url_changed.emit(self.server_url)
            return True
        except Exception as err:
            print(
                f"[CONFIG] Error saving config to {CONFIG_FILE}: {err}", file=sys.stderr
            )
            return False

    # duplicate slot for default overload
    @QtCore.Slot(str, result="QVariant")
    @QtCore.Slot(str, "QVariant", result="QVariant")
    def get_setting(self, key: str, default=None):
        return self._config_data.get(key, default)

    @QtCore.Slot(str, "QVariant")
    def set_setting(self, key: str, value):
        self._config_data[key] = value
        self.save_config(self._config_data)

    @QtCore.Slot()
    def connect(self):
        """Connection entrypoint."""
        pass
