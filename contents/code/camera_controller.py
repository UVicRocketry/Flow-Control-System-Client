# This Python file uses the following encoding: utf-8
"""IP camera RTSP configuration, link detection, and FFmpeg tuning (`camera_controller.py`)."""

import errno
import os
import selectors
import socket
import threading
import time
from urllib.parse import quote
from urllib.request import (
    HTTPDigestAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    ProxyHandler,
    build_opener,
)

from PySide6 import QtCore, QtMultimedia
from PySide6.QtNetwork import QNetworkInterface

_PRIORITY_CAMERA_IPS = (
    "192.168.0.103",
    "192.168.1.108",
    "192.168.0.108",
    "192.168.1.103",
)
_INFRASTRUCTURE_IPS = frozenset(
    {
        "192.168.0.1",
        "192.168.0.253",
        "192.168.0.254",
        "192.168.1.1",
        "192.168.1.253",
        "192.168.1.254",
    }
)


def _probe_rtsp_hosts(
    candidates: list[str], port: int = 554, timeout: float = 0.15
) -> str | None:
    """Probes candidate IPv4 hosts in batches and returns the first with open TCP port."""
    for i in range(0, len(candidates), 64):
        batch = candidates[i : i + 64]
        sel = selectors.DefaultSelector()
        sockets: list[socket.socket] = []
        try:
            for ip in batch:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setblocking(False)
                err = sock.connect_ex((ip, port))
                if err == 0:
                    sock.close()
                    return ip
                if err in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
                    sel.register(sock, selectors.EVENT_WRITE, ip)
                    sockets.append(sock)
                else:
                    sock.close()

            deadline = time.monotonic() + timeout
            while sockets and sel.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                for key, _ in sel.select(timeout=remaining):
                    sock = key.fileobj
                    ip = key.data
                    sel.unregister(sock)
                    if sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
                        return ip
        finally:
            sel.close()
            for sock in sockets:
                try:
                    sock.close()
                except OSError:
                    pass
    return None


def _read_arp_neighbors(prefixes: list[str], excluded: set[str]) -> list[str]:
    """Returns ARP neighbor IPv4s matching active subnet prefixes."""
    neighbors: list[str] = []
    try:
        with open("/proc/net/arp", encoding="utf-8") as f:
            lines = f.read().splitlines()[1:]
    except OSError:
        return neighbors

    for line in lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        ip, flags = parts[0], parts[2]
        if flags == "0x0" or ip in excluded:
            continue
        if any(ip.startswith(pfx) for pfx in prefixes):
            neighbors.append(ip)
    return neighbors


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
        """Auto-discovers an RTSP camera on active subnets and checks Ethernet link."""
        Flag = QNetworkInterface.InterfaceFlag
        IType = QNetworkInterface.InterfaceType

        is_eth = False
        local_ips: set[str] = set()
        eth_prefixes: list[str] = []
        other_prefixes: list[str] = []

        for iface in QNetworkInterface.allInterfaces():
            flags = iface.flags()
            if (
                not (flags & Flag.IsUp)
                or not (flags & Flag.IsRunning)
                or (flags & Flag.IsLoopBack)
            ):
                continue
            ips = [
                e.ip().toString()
                for e in iface.addressEntries()
                if "." in e.ip().toString()
            ]
            if not ips:
                continue
            iface_is_eth = iface.type() == IType.Ethernet
            if iface_is_eth:
                is_eth = True
            for ip in ips:
                local_ips.add(ip)
                parts = ip.split(".")
                if len(parts) != 4:
                    continue
                pfx = f"{parts[0]}.{parts[1]}.{parts[2]}."
                target_list = eth_prefixes if iface_is_eth else other_prefixes
                if pfx not in target_list:
                    target_list.append(pfx)

        prefixes: list[str] = []
        for pfx in ("192.168.0.", "192.168.1."):
            if pfx in eth_prefixes or pfx in other_prefixes:
                prefixes.append(pfx)
        for pfx in eth_prefixes + other_prefixes:
            if pfx not in prefixes:
                prefixes.append(pfx)

        excluded = local_ips | _INFRASTRUCTURE_IPS

        # 1. Fast pass: known camera IPs on active subnets + ARP neighbors
        fast_candidates: list[str] = []
        for ip in _PRIORITY_CAMERA_IPS:
            if ip not in excluded and (
                not prefixes or any(ip.startswith(pfx) for pfx in prefixes)
            ):
                fast_candidates.append(ip)
        for ip in _read_arp_neighbors(prefixes, excluded):
            if ip not in fast_candidates:
                fast_candidates.append(ip)

        if fast_candidates:
            found = _probe_rtsp_hosts(fast_candidates, port=554, timeout=0.15)
            if found:
                return found, is_eth

        # 2. Subnet sweep fallback across active /24 prefixes
        seen = set(fast_candidates) | excluded
        sweep_candidates = [
            f"{pfx}{host}"
            for pfx in prefixes
            for host in range(2, 253)
            if f"{pfx}{host}" not in seen
        ]
        if sweep_candidates:
            found = _probe_rtsp_hosts(sweep_candidates, port=554, timeout=0.12)
            if found:
                return found, is_eth

        # 3. Fallback when camera is offline
        fallback = (
            "192.168.1.108"
            if "192.168.1." in prefixes and "192.168.0." not in prefixes
            else "192.168.0.108"
        )
        return fallback, is_eth

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
                opener.open(f"{base}?action=setConfig&" + "&".join(params), timeout=2.0).read()
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
            else self._detect_camera_link()[0]
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

    def set_camera_settings(
        self, mode: str, profile: str, manual_target: str
    ) -> None:
        cam = dict(self._cam_cfg())
        new_mode = "manual" if mode == "manual" else "auto"
        new_prof = "udp_high" if profile == "udp_high" else "tcp_low"
        if (
            new_mode == "auto"
            and cam.get("mode") != "auto"
            and profile == cam.get("profile")
        ):
            _, is_eth = self._detect_camera_link()
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
