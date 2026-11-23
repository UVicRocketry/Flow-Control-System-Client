# This Python file uses the following encoding: utf-8
"""Generic subnet and localhost connection autodiscovery (`connection_finder.py`)."""

import errno
import selectors
import socket
import time
from urllib.parse import urlparse

from PySide6.QtNetwork import QNetworkInterface

_TARGET_SUBNETS = ("192.168.0.", "192.168.1.")
_ROUTER_IPS = frozenset(
    {
        "192.168.0.253",
        "192.168.0.254",
        "192.168.1.253",
        "192.168.1.254",
    }
)
_GATEWAY_IPS = frozenset({"192.168.0.1", "192.168.1.1"})
_PRIORITY_WS_IPS = ("192.168.0.1", "192.168.1.1")
_PRIORITY_RTSP_IPS = (
    "192.168.0.103",
    "192.168.1.108",
    "192.168.0.108",
    "192.168.1.103",
)
_LOCALHOST_IP = "127.0.0.1"
_WS_PORT = 8080
_RTSP_PORT = 554
_RTSP_LOCAL_ALT_PORTS = (8554,)
_DEFAULT_DISCOVER_TIMEOUT = 5.0


def _open_nonblocking_socket(
    ip: str,
    port: int,
    sel: selectors.BaseSelector,
    sockets: list[socket.socket],
) -> str | None:
    """Opens a non-blocking IPv4 TCP socket and registers pending connects."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setblocking(False)
        err = sock.connect_ex((ip, port))
        if err == 0:
            sock.close()
            return ip
        if err in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
            sel.register(sock, selectors.EVENT_WRITE, ip)
            sockets.append(sock)
            return None
    except OSError:
        pass
    sock.close()
    return None


def _await_ready_socket(
    sel: selectors.BaseSelector,
    sockets: list[socket.socket],
    timeout: float,
) -> str | None:
    """Waits up to timeout seconds and returns the first connected host IP."""
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
    return None


def _probe_hosts(
    candidates: list[str],
    port: int,
    timeout: float = 0.15,
    deadline: float | None = None,
) -> str | None:
    """Probes candidate IPv4 hosts in batches and returns the first with open TCP port."""
    for i in range(0, len(candidates), 64):
        batch_timeout = timeout
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            batch_timeout = min(timeout, remaining)
        batch = candidates[i : i + 64]
        sel = selectors.DefaultSelector()
        sockets: list[socket.socket] = []
        try:
            for ip in batch:
                hit = _open_nonblocking_socket(ip, port, sel, sockets)
                if hit is not None:
                    return hit
            hit = _await_ready_socket(sel, sockets, batch_timeout)
            if hit is not None:
                return hit
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


def _is_usable_interface(iface: QNetworkInterface) -> bool:
    """Returns True when an interface is up, running, and non-loopback."""
    Flag = QNetworkInterface.InterfaceFlag
    flags = iface.flags()
    return (
        bool(flags & Flag.IsUp)
        and bool(flags & Flag.IsRunning)
        and not bool(flags & Flag.IsLoopBack)
    )


def _record_iface_prefixes(
    ips: list[str], local_ips: set[str], target_prefixes: list[str]
) -> None:
    """Adds interface IPv4 addresses to local_ips and unique /24 prefixes to target."""
    for ip in ips:
        local_ips.add(ip)
        parts = ip.split(".")
        if len(parts) == 4:
            pfx = f"{parts[0]}.{parts[1]}.{parts[2]}."
            if pfx not in target_prefixes:
                target_prefixes.append(pfx)


def _collect_network_state() -> tuple[list[str], set[str], bool]:
    """Collects active 192.168.0/1.* prefixes, local IPs, and Ethernet presence."""
    IType = QNetworkInterface.InterfaceType
    is_eth = False
    local_ips: set[str] = set()
    eth_prefixes: list[str] = []
    other_prefixes: list[str] = []

    for iface in QNetworkInterface.allInterfaces():
        if not _is_usable_interface(iface):
            continue
        ips = [
            e.ip().toString()
            for e in iface.addressEntries()
            if "." in e.ip().toString()
        ]
        if not ips:
            continue
        iface_is_eth = iface.type() == IType.Ethernet
        is_eth = is_eth or iface_is_eth
        _record_iface_prefixes(
            ips, local_ips, eth_prefixes if iface_is_eth else other_prefixes
        )

    prefixes = [pfx for pfx in _TARGET_SUBNETS if pfx in eth_prefixes]
    for pfx in _TARGET_SUBNETS:
        if pfx in other_prefixes and pfx not in prefixes:
            prefixes.append(pfx)
    return prefixes, local_ips, is_eth


def has_active_ethernet() -> bool:
    """Returns True when a non-loopback Ethernet interface is up with an IPv4 address."""
    return _collect_network_state()[2]


def _build_fast_candidates(
    priority_ips: tuple[str, ...], prefixes: list[str], excluded: set[str]
) -> list[str]:
    """Builds prioritized candidate IPs from known hosts and ARP neighbors."""
    candidates: list[str] = []
    for ip in priority_ips:
        if ip not in excluded and (
            not prefixes or any(ip.startswith(pfx) for pfx in prefixes)
        ):
            candidates.append(ip)
    for ip in _read_arp_neighbors(prefixes, excluded):
        if ip not in candidates:
            candidates.append(ip)
    return candidates


def _probe_localhost(
    port: int,
    extra_ports: tuple[int, ...] = (),
    deadline: float | None = None,
) -> str | None:
    """Probes localhost on primary and optional alternate ports."""
    if _probe_hosts([_LOCALHOST_IP], port=port, timeout=0.15, deadline=deadline):
        return _LOCALHOST_IP
    for alt_port in extra_ports:
        if _probe_hosts(
            [_LOCALHOST_IP], port=alt_port, timeout=0.15, deadline=deadline
        ):
            return f"{_LOCALHOST_IP}:{alt_port}"
    return None


def _discover_host(
    port: int,
    priority_ips: tuple[str, ...],
    infra_ips: frozenset[str],
    fallback_hosts: tuple[str, str],
    localhost_alt_ports: tuple[int, ...] = (),
    total_timeout: float = _DEFAULT_DISCOVER_TIMEOUT,
) -> str:
    """Discovers a reachable host on 192.168.0/1.*, then localhost, else fallback."""
    deadline = time.monotonic() + max(0.0, total_timeout)
    prefixes, local_ips, _ = _collect_network_state()
    excluded = local_ips | infra_ips

    fast_candidates = _build_fast_candidates(priority_ips, prefixes, excluded)
    if fast_candidates:
        found = _probe_hosts(
            fast_candidates, port=port, timeout=0.15, deadline=deadline
        )
        if found:
            return found

    seen = set(fast_candidates) | excluded
    sweep_candidates = [
        f"{pfx}{host}"
        for pfx in prefixes
        for host in range(1, 253)
        if f"{pfx}{host}" not in seen
    ]
    if sweep_candidates and time.monotonic() < deadline:
        found = _probe_hosts(
            sweep_candidates, port=port, timeout=0.12, deadline=deadline
        )
        if found:
            return found

    if time.monotonic() < deadline:
        local_hit = _probe_localhost(port, localhost_alt_ports, deadline=deadline)
        if local_hit:
            return local_hit

    if "192.168.1." in prefixes and "192.168.0." not in prefixes:
        return fallback_hosts[1]
    return fallback_hosts[0]


def autodiscover(
    conn_type: str = "ws", timeout: float = _DEFAULT_DISCOVER_TIMEOUT
) -> str:
    """Auto-discovers a connection link across 192.168.0(1).* and localhost."""
    kind = (conn_type or "").strip().lower()
    if kind == "ws":
        host = _discover_host(
            port=_WS_PORT,
            priority_ips=_PRIORITY_WS_IPS,
            infra_ips=_ROUTER_IPS,
            fallback_hosts=("192.168.0.1", "192.168.1.1"),
            total_timeout=timeout,
        )
        return f"ws://{host}:{_WS_PORT}/ws"
    if kind == "rtsp":
        return _discover_host(
            port=_RTSP_PORT,
            priority_ips=_PRIORITY_RTSP_IPS,
            infra_ips=_ROUTER_IPS | _GATEWAY_IPS,
            fallback_hosts=("192.168.0.108", "192.168.1.108"),
            localhost_alt_ports=_RTSP_LOCAL_ALT_PORTS,
            total_timeout=timeout,
        )
    raise ValueError(f"Unsupported connection type: {conn_type!r}")


def is_ws_reachable(url: str, timeout: float = 0.15) -> bool:
    """Returns True when the TCP host:port of a WebSocket URL accepts connections."""
    parsed = urlparse((url or "").strip())
    host = parsed.hostname
    if not host:
        return False
    default_port = 443 if parsed.scheme == "wss" else _WS_PORT
    port = parsed.port or default_port
    return _probe_hosts([host], port=port, timeout=timeout) is not None
