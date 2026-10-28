# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Configuration & Path Management
handles environment detection, config directory resolution, template seeding,
and reading/writing application and graph configuration files.
"""

import json
import os
import shutil
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent


def get_default_config_dir() -> Path:
    """
    returns the bundled/source default configuration directory (/contents/config/).
    used directly in development, and bundled as default template for standalone packages.
    """
    # 1. PyInstaller single-file temporary bundle (sys._MEIPASS)
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

    # 3. source repository tree (/contents/config/)
    return CURRENT_DIR.parent / "config"


def get_user_config_dir() -> Path:
    """
    returns the standard OS-specific user configuration directory:
    - linux / unix: $XDG_CONFIG_HOME/flow-control (default ~/.config/flow-control)
    - windows: %APPDATA%/FlowControl (default ~/AppData/Roaming/FlowControl)
    - macos: ~/Library/Application Support/FlowControl
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
    determines whether the application is running in a development environment.
    - forced dev mode: FLOW_CONTROL_DEV=1
    - forced user mode: FLOW_CONTROL_DEV=0 or FLOW_CONTROL_USE_USER_CONFIG=1
    - standalone package (PyInstaller / frozen): False
    - running from source tree: True
    """
    env_force = os.environ.get("FLOW_CONTROL_DEV")
    if env_force is not None:
        return env_force.strip() in ("1", "true", "True", "yes")

    if os.environ.get("FLOW_CONTROL_USE_USER_CONFIG") == "1":
        return False

    return not getattr(sys, "frozen", False)


def get_config_dir() -> Path:
    """
    resolves the active configuration directory:
    - in dev mode: pulls directly from /contents/config/
    - in standalone packages: uses the OS-specific user config directory,
      initializing missing files (including subdirectories) from /contents/config/
    """
    if is_dev_environment():
        dev_dir = get_default_config_dir()
        try:
            dev_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return dev_dir

    # standalone packaged distribution
    user_dir = get_user_config_dir()
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        print(
            f"[CONFIG] Notice: Cannot write to {user_dir} ({err}). "
            "Falling back to temp directory.",
            file=sys.stderr,
        )
        tmp_base = os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
        fallback_dir = Path(tmp_base) / "flow-control"
        try:
            fallback_dir.mkdir(parents=True, exist_ok=True)
            user_dir = fallback_dir
        except OSError:
            user_dir = get_default_config_dir()

    # seed default configuration files and subdirectories from bundled template if absent
    default_dir = get_default_config_dir()
    if default_dir.exists() and default_dir.is_dir():
        for src_file in default_dir.rglob("*.json"):
            rel_path = src_file.relative_to(default_dir)
            dest_file = user_dir / rel_path
            if not dest_file.exists():
                try:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_file)
                    print("[CONFIG] Init: ", f"default user config: {dest_file}")
                except Exception as err:
                    print(
                        "[CONFIG] Warning: ",
                        f"Could not copy template {rel_path}: {err}",
                        file=sys.stderr,
                    )

    return user_dir


# active configuration locations
CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"
GRAPHS_CONFIG_DIR = CONFIG_DIR / "graphs"
GRAPHS_CONFIG_FILE = GRAPHS_CONFIG_DIR / "graphs.json"


def get_default_config_file() -> Path:
    """returns the path to the template config/config.json."""
    return get_default_config_dir() / "config.json"


def get_default_graphs_config_file() -> Path:
    """returns the path to the template config/graphs/graphs.json."""
    return get_default_config_dir() / "graphs" / "graphs.json"


def ensure_config_file_exists() -> None:
    """populates CONFIG_FILE and GRAPHS_CONFIG_FILE from templates if absent."""
    for dest_path, template_path in (
        (CONFIG_FILE, get_default_config_file()),
        (GRAPHS_CONFIG_FILE, get_default_graphs_config_file()),
    ):
        if not dest_path.exists():
            if template_path.exists():
                try:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_path, dest_path)
                    print(
                        "[CONFIG] Init: ",
                        f"conf file from {template_path} -> {dest_path}",
                    )
                except Exception as err:
                    print(
                        "[CONFIG] Notice: ",
                        f"Could not copy template conf to {dest_path}: {err}",
                        file=sys.stderr,
                    )
            else:
                print(
                    "[CONFIG] Warning: ",
                    f"Template conf file not found at {template_path}",
                    file=sys.stderr,
                )


def read_app_config(log_error_fn=None) -> dict:
    """
    loads application configuration from CONFIG_FILE (or template fallback),
    applying environment overrides such as FLOW_CONTROL_WS_URL.
    """
    target_path = CONFIG_FILE if CONFIG_FILE.exists() else get_default_config_file()
    config_data = {}

    if target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as err:
            if log_error_fn:
                log_error_fn(f"Error reading {target_path}: {err}.")
            config_data = {}
    else:
        if log_error_fn:
            log_error_fn(f"No configuration file found at {target_path}.")

    ensure_config_file_exists()

    # environment variable override takes highest precedence for server URL
    env_url = os.environ.get("FLOW_CONTROL_WS_URL")
    if env_url:
        if "server" not in config_data:
            config_data["server"] = {}
        config_data["server"]["default_url"] = env_url

    return config_data


def write_app_config(data: dict, log_error_fn=None) -> bool:
    """writes dictionary data to CONFIG_FILE."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as err:
        if log_error_fn:
            log_error_fn(f"Couldnt save config to {CONFIG_FILE}: {err}")
        return False


def read_graphs_config(log_error_fn=None) -> tuple[dict, list]:
    """
    loads known channel definitions and default graph card configs from
    GRAPHS_CONFIG_FILE (or template fallback).
    """
    target = (
        GRAPHS_CONFIG_FILE
        if GRAPHS_CONFIG_FILE.exists()
        else get_default_graphs_config_file()
    )
    known_channels = {}
    default_cards = []

    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        channels_map = data.get("channels", {})
        if isinstance(channels_map, dict):
            known_channels = {
                str(k): dict(v) for k, v in channels_map.items() if isinstance(v, dict)
            }
        cards_list = data.get("default_cards", [])
        if isinstance(cards_list, list):
            default_cards = [dict(c) for c in cards_list if isinstance(c, dict)]
    except Exception as err:
        if log_error_fn:
            log_error_fn(f'Failed to load graphs configuration from "{target}": {err}')

    return known_channels, default_cards
