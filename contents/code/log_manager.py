# This Python file uses the following encoding: utf-8
"""Diagnostic logging and HTTP `/api/data` + local log management (`log_manager.py`)."""

import json
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

from PySide6 import QtCore, QtNetwork

from config_manager import CONFIG_DIR
from telemetry_files import (
    delete_data_file,
    list_local_data_files,
    rename_data_file,
    resolve_data_file,
)


def ws_url_to_http_base(ws_url: str) -> str:
    """Converts a WebSocket URL (`ws://host:port/ws`) to an HTTP base URL."""
    raw = str(ws_url or "").strip()
    if not raw:
        return "http://127.0.0.1:8080"
    parsed = urlparse(raw)
    scheme_map = {"ws": "http", "wss": "https", "http": "http", "https": "https"}
    scheme = scheme_map.get(parsed.scheme.lower(), "http")
    netloc = parsed.netloc or "127.0.0.1:8080"
    return urlunparse((scheme, netloc, "", "", "", ""))


def build_api_data_url(
    ws_url: str, filename: str | None = None, action: str | None = None
) -> str:
    """Builds a server `/api/data/...` URL from the configured WebSocket URL."""
    base = ws_url_to_http_base(ws_url).rstrip("/")
    if not filename:
        return f"{base}/api/data"
    encoded = quote(Path(filename).name, safe="")
    if action:
        return f"{base}/api/data/{encoded}/{action}"
    return f"{base}/api/data/{encoded}"


class LogManager(QtCore.QObject):
    """Handles diagnostic logs and local/external/HTTP `/api/data` telemetry files."""

    log_sent = QtCore.Signal(str, str)
    local_data_changed = QtCore.Signal()
    remote_data_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._local_data: list[str] = []
        self._remote_data: list[str] = []
        self._pending_deletions: set[tuple[str, str]] = set()
        self._net_mgr: QtNetwork.QNetworkAccessManager | None = None
        self._active_replies: set[QtNetwork.QNetworkReply] = set()

    def _network_manager(self) -> QtNetwork.QNetworkAccessManager:
        if self._net_mgr is None:
            self._net_mgr = QtNetwork.QNetworkAccessManager(self)
        return self._net_mgr

    # ------------------------------------------------------------------
    # Diagnostic Logging
    # ------------------------------------------------------------------
    def _send_log(self, level: str, msg: str, stream=sys.stdout) -> None:
        t_str = time.strftime("%H:%M:%S")
        entry = f"[{t_str}] [{level}] {msg}"
        print(f"[FLOW-CTRL] {entry}", flush=True, file=stream)
        self.log_sent.emit(level, msg)

    def log(self, level: str, msg: str) -> None:
        lvl = str(level).upper()
        stream = sys.stderr if lvl == "ERR" else sys.stdout
        self._send_log(lvl, msg, stream=stream)

    def log_info(self, msg: str) -> None:
        self._send_log("INFO", msg)

    def log_warn(self, msg: str) -> None:
        self._send_log("WARN", msg)

    def log_error(self, msg: str) -> None:
        self._send_log("ERR", msg, stream=sys.stderr)

    # ------------------------------------------------------------------
    # Local / Remote File Lists
    # ------------------------------------------------------------------
    @property
    def local_data(self) -> list[str]:
        return list(self._local_data)

    @property
    def remote_data(self) -> list[str]:
        return list(self._remote_data)

    def refresh_local_data(self) -> list[str]:
        """Scans CONFIG_DIR / 'data' for local telemetry files."""
        self._local_data = list_local_data_files()
        self.local_data_changed.emit()
        return self._local_data

    def mark_data_for_deletion(self, mode: str, filename: str) -> None:
        self._pending_deletions.add((mode, filename))

    def unmark_data_for_deletion(self, mode: str, filename: str) -> None:
        self._pending_deletions.discard((mode, filename))

    def handle_remote_data_list_msg(self, msg: dict) -> None:
        raw_files = msg.get("files", [])
        parsed_names: list[str] = []
        if isinstance(raw_files, list):
            for entry in raw_files:
                if isinstance(entry, dict) and entry.get("name"):
                    parsed_names.append(str(entry["name"]))
                elif isinstance(entry, str) and entry.strip():
                    parsed_names.append(entry.strip())
        self._remote_data = parsed_names
        self.remote_data_changed.emit()

    def _save_remote_bytes(
        self, fname: str, raw_bytes: bytes, req_mode: str, on_saved_cb=None
    ) -> None:
        dest_dir = CONFIG_DIR / "data"
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / fname
            overwrote = dest_path.exists()
            dest_path.write_bytes(raw_bytes)
            self.refresh_local_data()
            if on_saved_cb is not None and req_mode in ("load", "pull_recording"):
                on_saved_cb(fname, dest_path, overwrote, req_mode)
            else:
                self.log_info(f'Downloaded "{fname}" to local data.')
        except Exception as err:
            self.log_error(f'Failed to save remote file "{fname}": {err}')

    def handle_remote_data_content_msg(self, msg: dict, on_saved_cb=None) -> None:
        fname = Path(str(msg.get("filename", ""))).name
        content = msg.get("content", "")
        req_mode = str(msg.get("mode", "download")).lower()
        if not fname and req_mode == "pull_recording":
            fname = f"telemetry_pull_{time.strftime('%Y_%m_%d_%H%M%S')}.csv"
        if not fname:
            return
        self._save_remote_bytes(
            fname, str(content).encode("utf-8"), req_mode, on_saved_cb
        )

    # ------------------------------------------------------------------
    # HTTP /api/data Operations via QNetworkAccessManager (with WS fallback)
    # ------------------------------------------------------------------
    def _track_reply(self, reply: QtNetwork.QNetworkReply, callback) -> None:
        self._active_replies.add(reply)

        def _done() -> None:
            self._active_replies.discard(reply)
            try:
                callback(reply)
            finally:
                reply.deleteLater()

        reply.finished.connect(_done)

    @staticmethod
    def _make_request(url_str: str, content_type: str | None = None):
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(url_str))
        if content_type:
            req.setHeader(
                QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader,
                content_type,
            )
        return req

    def refresh_remote_data(
        self, server_url: str, ws_connected: bool = False, ws_send_fn=None
    ) -> None:
        """Fetches remote data file list via GET /api/data."""
        req = self._make_request(build_api_data_url(server_url))
        reply = self._network_manager().get(req)

        def _on_done(r: QtNetwork.QNetworkReply) -> None:
            if r.error() == QtNetwork.QNetworkReply.NetworkError.NoError:
                try:
                    payload = json.loads(bytes(r.readAll().data()).decode("utf-8"))
                    if isinstance(payload, dict):
                        self.handle_remote_data_list_msg(payload)
                        return
                except Exception as err:
                    self.log_warn(f"Failed parsing /api/data list: {err}")
            elif ws_connected and ws_send_fn is not None:
                ws_send_fn(
                    json.dumps({"type": "remote_data_req", "operation": "list"})
                )

        self._track_reply(reply, _on_done)

    def fetch_remote_file(
        self,
        server_url: str,
        filename: str,
        mode: str = "download",
        on_saved_cb=None,
        ws_connected: bool = False,
        ws_send_fn=None,
    ) -> None:
        """Downloads a remote log via GET /api/data/{filename}."""
        clean_name = Path(filename.strip()).name if filename else ""
        if not clean_name and mode != "pull_recording":
            self.log_warn("No remote file selected to download.")
            return
        if not clean_name and mode == "pull_recording":
            if ws_connected and ws_send_fn is not None:
                ws_send_fn(
                    json.dumps(
                        {
                            "type": "remote_data_req",
                            "operation": "get",
                            "filename": "",
                            "mode": mode,
                        }
                    )
                )
            return

        req = self._make_request(build_api_data_url(server_url, clean_name))
        reply = self._network_manager().get(req)

        def _on_done(r: QtNetwork.QNetworkReply) -> None:
            if r.error() == QtNetwork.QNetworkReply.NetworkError.NoError:
                raw_bytes = bytes(r.readAll().data())
                self._save_remote_bytes(clean_name, raw_bytes, mode, on_saved_cb)
                return
            if ws_connected and ws_send_fn is not None:
                ws_send_fn(
                    json.dumps(
                        {
                            "type": "remote_data_req",
                            "operation": "get",
                            "filename": clean_name,
                            "mode": mode,
                        }
                    )
                )
            else:
                self.log_error(
                    f'Failed downloading "{clean_name}": {r.errorString()}'
                )

        self._track_reply(reply, _on_done)

    def push_data_to_remote(
        self,
        server_url: str,
        target: str,
        known_channels: dict,
        ws_connected: bool = False,
        ws_send_fn=None,
    ) -> None:
        """Uploads a local/external CSV or JSONL log via PUT /api/data/{filename}."""
        clean_target = target.strip()
        if not clean_target:
            self.log_warn("No local file selected to push.")
            return
        try:
            resolved_path = resolve_data_file(clean_target, known_channels)
        except Exception as err:
            self.log_error(f'Failed to resolve data file "{clean_target}": {err}')
            return

        if resolved_path.suffix.lower() not in (".csv", ".jsonl"):
            self.log_warn(
                f'Cannot push "{resolved_path.name}": only .csv or .jsonl files supported.'
            )
            return

        try:
            raw_bytes = resolved_path.read_bytes()
        except Exception as err:
            self.log_error(f'Failed reading "{resolved_path.name}" for upload: {err}')
            return

        req = self._make_request(
            build_api_data_url(server_url, resolved_path.name),
            content_type="text/csv",
        )
        reply = self._network_manager().put(req, QtCore.QByteArray(raw_bytes))
        self.log_info(f'Pushing "{resolved_path.name}" to valve cart...')

        def _on_done(r: QtNetwork.QNetworkReply) -> None:
            if r.error() == QtNetwork.QNetworkReply.NetworkError.NoError:
                self.log_info(f'Uploaded "{resolved_path.name}" to valve cart.')
                self.refresh_remote_data(server_url, ws_connected, ws_send_fn)
                return
            if ws_connected and ws_send_fn is not None:
                ws_send_fn(
                    json.dumps(
                        {
                            "type": "remote_data_req",
                            "operation": "put",
                            "filename": resolved_path.name,
                            "content": raw_bytes.decode("utf-8", errors="replace"),
                        }
                    )
                )
            else:
                self.log_error(
                    f'Failed uploading "{resolved_path.name}": {r.errorString()}'
                )

        self._track_reply(reply, _on_done)

    def _rename_remote_data(
        self,
        server_url: str,
        old_name: str,
        new_clean: str,
        ws_connected: bool,
        ws_send_fn,
    ) -> bool:
        if Path(new_clean).suffix == "" and Path(old_name).suffix:
            new_clean = new_clean + Path(old_name).suffix
        url = build_api_data_url(server_url, old_name, action="rename")
        req = self._make_request(url, content_type="application/json")
        body = json.dumps({"new_name": new_clean}).encode("utf-8")
        reply = self._network_manager().post(req, QtCore.QByteArray(body))

        def _on_done(r: QtNetwork.QNetworkReply) -> None:
            if r.error() == QtNetwork.QNetworkReply.NetworkError.NoError:
                self.refresh_remote_data(server_url, ws_connected, ws_send_fn)
                return
            if ws_connected and ws_send_fn is not None:
                ws_send_fn(
                    json.dumps(
                        {
                            "type": "remote_data_req",
                            "operation": "rename",
                            "old_name": old_name,
                            "new_name": new_clean,
                        }
                    )
                )
            else:
                self.log_error(f'Failed renaming "{old_name}": {r.errorString()}')

        self._track_reply(reply, _on_done)
        self._remote_data = [
            new_clean if item == old_name else item for item in self._remote_data
        ]
        self.remote_data_changed.emit()
        self.log_info(f'Requested remote rename "{old_name}" -> "{new_clean}".')
        return True

    def rename_data(
        self,
        mode: str,
        old_name: str,
        new_name: str,
        config_store,
        server_url: str,
        ws_connected: bool = False,
        ws_send_fn=None,
    ) -> bool:
        """Renames a local, external, or remote telemetry file."""
        new_clean = Path(new_name.strip()).name
        if not new_clean:
            self.log_warn("New filename cannot be empty.")
            return False

        if mode == "remote":
            return self._rename_remote_data(
                server_url, old_name, new_clean, ws_connected, ws_send_fn
            )

        try:
            dst = rename_data_file(mode, old_name, new_clean)
            if mode == "local":
                self.refresh_local_data()
            elif mode == "external":
                updated = [
                    str(dst) if p == old_name else p
                    for p in config_store.external_data
                ]
                config_store.set_external_data_list(updated)
            self.log_info(f'Renamed "{Path(old_name).name}" to "{dst.name}".')
            return True
        except Exception as err:
            self.log_error(f'Failed to rename "{old_name}": {err}')
            return False

    def _delete_remote_data(
        self, server_url: str, filename: str, ws_connected: bool, ws_send_fn
    ) -> bool:
        req = self._make_request(build_api_data_url(server_url, filename))
        reply = self._network_manager().deleteResource(req)

        def _on_done(r: QtNetwork.QNetworkReply) -> None:
            if r.error() == QtNetwork.QNetworkReply.NetworkError.NoError:
                self.refresh_remote_data(server_url, ws_connected, ws_send_fn)
                return
            if ws_connected and ws_send_fn is not None:
                ws_send_fn(
                    json.dumps(
                        {
                            "type": "remote_data_req",
                            "operation": "delete",
                            "filename": filename,
                        }
                    )
                )
            else:
                self.log_error(f'Failed deleting "{filename}": {r.errorString()}')

        self._track_reply(reply, _on_done)
        if filename in self._remote_data:
            self._remote_data.remove(filename)
            self.remote_data_changed.emit()
        self.log_info(f'Deleted remote file "{filename}".')
        return True

    @staticmethod
    def _prune_deleted_file_entry(mode: str, filename: str, config_store, mgr) -> None:
        if mode == "local":
            mgr.refresh_local_data()
        elif mode == "external":
            updated = [p for p in config_store.external_data if p != filename]
            config_store.set_external_data_list(updated)

    def delete_data(
        self,
        mode: str,
        filename: str,
        config_store,
        server_url: str,
        ws_connected: bool = False,
        ws_send_fn=None,
    ) -> bool:
        """Deletes a local, external, or remote telemetry file."""
        self._pending_deletions.discard((mode, filename))
        if mode == "remote":
            return self._delete_remote_data(
                server_url, filename, ws_connected, ws_send_fn
            )

        try:
            deleted = delete_data_file(mode, filename)
            self._prune_deleted_file_entry(mode, filename, config_store, self)
            self.log_info(f'Deleted "{deleted.name}".')
            return True
        except FileNotFoundError:
            self._prune_deleted_file_entry(mode, filename, config_store, self)
            return False
        except Exception as err:
            self.log_error(f'Failed to delete "{filename}": {err}')
            return False
