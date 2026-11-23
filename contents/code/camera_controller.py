# This Python file uses the following encoding: utf-8
"""IP camera RTSP configuration, link detection, and FFmpeg tuning (`camera_controller.py`)."""

import os
import threading
from urllib.parse import quote
from urllib.request import (
    HTTPDigestAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    ProxyHandler,
    build_opener,
)

from PySide6 import QtCore, QtMultimedia

from connection_finder import autodiscover, has_active_ethernet


class CameraController(QtCore.QObject):
    """Manages RTSP camera settings, subnet autodetection, and playback options."""

    camera_config_changed = QtCore.Signal()
    camera_active_changed = QtCore.Signal(bool)
    camera_toggle_requested = QtCore.Signal()

    def __init__(self, config_store, parent=None):
        super().__init__(parent)
        self._config_store = config_store
        self._camera_active = False

    def _cam_cfg(self) -> dict:
        cam = self._config_store.config_data.get("camera")
        return cam if isinstance(cam, dict) else {}

    def _save_cam_cfg(self, cam: dict) -> None:
        data = self._config_store.config_data
        data["camera"] = cam
        self._config_store.save_config(data)
        self.camera_config_changed.emit()

    @staticmethod
    def _detect_camera_link() -> tuple[str, bool]:
        """Auto-discovers an RTSP camera and checks Ethernet link presence."""
        return autodiscover("rtsp"), has_active_ethernet()

    def apply_camera_transport(self) -> None:
        os.environ["QT_FFMPEG_RTSP_TRANSPORT"] = (
            "udp" if self.camera_profile == "udp_high" else "tcp"
        )

    def _enforce_camera_h264(self, host: str) -> None:
        """Configures Amcrest streams for low-latency H.264 in background."""
        user, pwd = self.camera_username, self.camera_password
        if not host or not user:
            return
        params = (
            "Encode[0].MainFormat[0].Video.Compression=H.264",
            "Encode[0].MainFormat[0].Video.Profile=Main",
            "Encode[0].MainFormat[0].Video.GOP=5",
            "Encode[0].MainFormat[0].Video.BitRateControl=CBR",
            "Encode[0].MainFormat[0].AudioEnable=false",
            "Encode[0].ExtraFormat[0].Video.Compression=H.264",
            "Encode[0].ExtraFormat[0].Video.Profile=Main",
            "Encode[0].ExtraFormat[0].Video.GOP=5",
            "Encode[0].ExtraFormat[0].Video.BitRateControl=CBR",
            "Encode[0].ExtraFormat[0].AudioEnable=false",
        )

        def _worker() -> None:
            try:
                base = f"http://{host}/cgi-bin/configManager.cgi"
                mgr = HTTPPasswordMgrWithDefaultRealm()
                mgr.add_password(None, base, user, pwd)
                opener = build_opener(ProxyHandler({}), HTTPDigestAuthHandler(mgr))
                cfg = (
                    opener.open(f"{base}?action=getConfig&name=Encode", timeout=2.0)
                    .read()
                    .decode("utf-8", "replace")
                )
                current = {ln.strip() for ln in cfg.splitlines()}
                if all(f"table.{p}" in current for p in params):
                    return
                opener.open(
                    f"{base}?action=setConfig&" + "&".join(params), timeout=2.0
                ).read()
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    @property
    def camera_mode(self) -> str:
        return "manual" if self._cam_cfg().get("mode") == "manual" else "auto"

    @property
    def camera_profile(self) -> str:
        return "udp_high" if self._cam_cfg().get("profile") == "udp_high" else "tcp_low"

    @property
    def camera_manual_target(self) -> str:
        return str(self._cam_cfg().get("manual_target", "192.168.0.108")).strip()

    @property
    def camera_username(self) -> str:
        return str(self._cam_cfg().get("username", "admin")).strip()

    @property
    def camera_password(self) -> str:
        return str(self._cam_cfg().get("password", "admin"))

    @property
    def camera_rtsp_url(self) -> str:
        self.apply_camera_transport()
        target = (
            self.camera_manual_target
            if self.camera_mode == "manual"
            else autodiscover("rtsp")
        )
        if target.startswith(("rtsp://", "http://", "https://", "file://")):
            return target
        host = target or "192.168.0.108"
        self._enforce_camera_h264(host.split(":")[0])
        port = 554
        if ":" in host:
            host, port_s = host.rsplit(":", 1)
            port = int(port_s) if port_s.isdigit() else 554
        subtype = 0 if self.camera_profile == "udp_high" else 1
        user, pwd = self.camera_username, self.camera_password
        auth = (
            f"{quote(user, safe='')}:{quote(pwd, safe='')}@"
            if (user and pwd)
            else (f"{quote(user, safe='')}@" if user else "")
        )
        return f"rtsp://{auth}{host}:{port}/cam/realmonitor?channel=1&subtype={subtype}"

    def set_camera_settings(self, mode: str, profile: str, manual_target: str) -> None:
        cam = dict(self._cam_cfg())
        new_mode = "manual" if mode == "manual" else "auto"
        new_prof = "udp_high" if profile == "udp_high" else "tcp_low"
        if (
            new_mode == "auto"
            and cam.get("mode") != "auto"
            and profile == cam.get("profile")
        ):
            is_eth = has_active_ethernet()
            new_prof = "udp_high" if is_eth else "tcp_low"
        cam.update(
            {
                "mode": new_mode,
                "profile": new_prof,
                "manual_target": manual_target.strip() or "192.168.0.108",
            }
        )
        self.apply_camera_transport()
        self._save_cam_cfg(cam)

    @property
    def camera_active(self) -> bool:
        return self._camera_active

    def set_camera_active(self, active: bool) -> None:
        val = bool(active)
        if self._camera_active != val:
            self._camera_active = val
            self.camera_active_changed.emit(val)

    @staticmethod
    def configure_camera_player(player: QtCore.QObject) -> None:
        """Configures QML MediaPlayer for low-latency live RTSP playback."""
        opts = player.playbackOptions()
        opts.setPlaybackIntent(
            QtMultimedia.QPlaybackOptions.PlaybackIntent.LowLatencyStreaming
        )
        opts.setProbeSize(4096)
        opts.setNetworkTimeout(5000)
        player.setPlaybackOptions(opts)
        player.setPlaybackRate(2.0)

    def toggle_camera(self) -> None:
        self.camera_toggle_requested.emit()

    def set_camera_credentials(self, username: str, password: str) -> None:
        cam = dict(self._cam_cfg())
        cam["username"] = username.strip()
        cam["password"] = password
        self._save_cam_cfg(cam)

    def set_camera_manual_target(self, target: str) -> None:
        cam = dict(self._cam_cfg())
        cam["manual_target"] = target.strip() or "192.168.0.108"
        self._save_cam_cfg(cam)
