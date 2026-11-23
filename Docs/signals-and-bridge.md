# Internally Exposed Signals & Python–QML Bridge

This document catalogs every signal, `@QtCore.Property`, and `@QtCore.Slot` exposed between the **Python `Backend` QML facade** ([`contents/code/backend.py`](../contents/code/backend.py)), its five composed `QObject` controllers, and the **QML user interface** ([`contents/qml/`](../contents/qml/main.qml)).

---

## 1. Architectural Reasoning: How the QML–Python Bridge Works

### 1.1 Context Injection (`backend` Singleton)
In [`contents/code/main.py`](../contents/code/main.py), `Backend` (`PySide6.QtCore.QObject`) is instantiated before loading `main.qml` and exposed on the root QML context using standard PySide6 camelCase APIs:

```python
from backend import Backend

backend = Backend()
engine.rootContext().setContextProperty("backend", backend)
```

**Why this approach was chosen:**
- **Global availability without import boilerplate:** Every QML file (`main.qml`, `Websocket.qml`, `Dashboard.qml`, `Actuators.qml`, `Graphs.qml`, `GraphCard.qml`, `Video.qml`, `Settings.qml`) references `backend` directly without threading props across multiple layout layers or popout loaders.
- **Headless / standalone safety:** In [`contents/code/backend.py`](../contents/code/backend.py), `PySide6.QtWidgets.QFileDialog` is imported lazily inside `open_data()`, and `QtMultimedia` is imported lazily inside `CameraController.configure_camera_player()`. Headless CI runners (without `libEGL.so.1`) and test suites can instantiate `Backend()` using only `QtCore` and `QtNetwork`.
- **Defensive QML bindings:** QML views guard bindings with `backend ? ... : ...` and `typeof backend !== "undefined"`, allowing standalone component inspection in `qmllint` or `qmlscene`.

### 1.2 Standard PySide6 CamelCase & Split Controller Composition
As of Phase 4, **`from __feature__ import snake_case, true_property` has been completely removed** from all Python modules (`main.py`, `splash.py`, `backend.py`, and controllers):

1. **Standard Qt API calls in Python:** Qt methods and getters/setters use upstream PySide6 camelCase (`setObjectName()`, `rootContext()`, `addImportPath()`, `QDesktopServices.openUrl()`, `QNetworkAccessManager.deleteResource()`). This avoids PySide6 import-order hook hazards and eliminates dual-casing workarounds.
2. **Stable `snake_case` QML Interface:** Custom `@QtCore.Signal`, `@QtCore.Property`, and `@QtCore.Slot` attributes defined on `Backend` intentionally remain in `snake_case` (`server_url`, `log_sent`, `telemetry_changed`, `get_channel_data`, `actuate_valve`, etc.) so existing QML bindings across all 42 `.qml` files remain intact.
   - **QML Signal Handler Rule:** Qt converts a Python signal `<name>` into an on-handler named `on` + `<Name with only the first character capitalized>`:
     - `log_sent` → `function onLog_sent(level, msg)`
     - `data_loaded` → `function onData_loaded(mode, filePath, meta)`
     - `telemetry_changed` → `function onTelemetry_changed()`
     - `channels_changed` → `function onChannels_changed()`
     - `connect_requested` → `function onConnect_requested()`
     - `valve_state_updated` → `function onValve_state_updated(valveId, state)`
3. **Controller Composition Behind `Backend`:** Rather than keeping a 1,500-line monolith, [`Backend`](../contents/code/backend.py) delegates state and I/O to five focused helper classes:
   - [`ConfigStore`](../contents/code/config_store.py): Reads/writes `config.json` (`server`, `ui.view_refresh_hz`, `ui.min_log_level`, split-view layout, `external_data`).
   - [`CameraController`](../contents/code/camera_controller.py): Manages Amcrest RTSP settings (`auto`/`manual`, `udp_high`/`tcp_low`), active Ethernet/Wi-Fi IP detection via `QNetworkInterface`, background HTTP Digest H.264 configuration, and lazy `QtMultimedia` playback tuning.
   - [`ActuatorController`](../contents/code/actuator_controller.py): Tracks `armed` interlock state, canonical actuator definitions, normalized valve states, safety interlocks (`SAFE` / `external` / expended `single_use`), and `ABORT`.
   - [`LogManager`](../contents/code/log_manager.py): Emits structured diagnostic logs (`INFO`/`WARN`/`ERR`), manages local/remote file lists, and performs async HTTP `/api/data/...` file CRUD via `QNetworkAccessManager` (with automatic WebSocket fallback).
   - [`TelemetryStore`](../contents/code/telemetry_store.py): Owns live/loaded `ColumnarTelemetryBuffer` storage, consumes server `init` `channels` metadata, runs `QThreadPool` workers (`_FileParseWorker`) for logs > 10 MB, throttles UI telemetry refreshes at `view_refresh_hz`, and executes synchronized CSV recording.

### 1.3 Pull-Based NumPy Columnar Telemetry & Safe Unit Conversion
When live WebSocket frames arrive or a large CSV/JSONL dataset is loaded, Python **never** pushes raw telemetry arrays through QML signals:

1. **Bounded Columnar Storage (`ColumnarTelemetryBuffer`):** [`telemetry_series.py`](../contents/code/telemetry_series.py) stores live samples in a bounded ring buffer (`DEFAULT_MAX_LIVE_SAMPLES = 50_000`) and column-oriented `float64` arrays (cached as NumPy arrays when `numpy` is installed, with automatic stdlib `bisect` / pure-Python fallback).
2. **Throttled UI Notification:** `TelemetryStore._schedule_telemetry_ui_update()` coalesces incoming frames and emits `telemetry_changed` at most `view_refresh_hz` times per second (configurable 1–120 Hz in [`Settings.qml`](../contents/qml/Settings.qml)).
3. **Single & Batch Windowed Queries:** Visible graph cards pull downsampled data via `get_channel_data(...)` or a single batched `get_batch_channel_data(source_mode, requests)` call from [`Graphs.qml`](../contents/qml/pages/Graphs.qml):
   - Slices `[win_start, win_end]` in $O(\log N)$ via `np.searchsorted` / `bisect`.
   - Optionally applies $3\sigma$ outlier rejection, time-bucket min/max envelope reduction (`np.add.reduceat` / `minimum.reduceat` / `maximum.reduceat`), and moving-average smoothing.
   - Converts units linearly at query time using the active source unit (priority: loaded CSV header unit → server `init` `channels` unit → `graphs.json` metadata → prefix default) to the card's chosen `target_unit`.
   - Valid target units are constrained per physical category in [`GraphEditDialog.qml`](../contents/qml/pages/graphs/GraphEditDialog.qml) via `format_channel_meta()` (`allowed_units`): Pressure (`kPa`, `psi`), Mass (`kg`, `lbs`), Force (`N`, `lbf`), Temperature (`°C`, `°F`, `K`). Legacy `L_RUN_TANK` columns map transparently to `M_RUN_TANK`.

---

## 2. Python `Backend` Exposed Signals (`contents/code/backend.py`)

| Signal Name | Signature | QML Handler Name | Emitted When | Primary Consumers |
| :--- | :--- | :--- | :--- | :--- |
| `config_changed` | `Signal()` | `onConfig_changed` | `load_config()`, `save_config()`, or `apply_actuator_definitions()` completes | `config_dir`, `config_file`, `valve_definitions` bindings |
| `server_url_changed` | `Signal(str)` | `onServer_url_changed` | `server_url` changes or `load_config()` runs | `main.qml`, `Websocket.qml` |
| `auto_reconnect_changed` | `Signal(bool)` | `onAuto_reconnect_changed` | `auto_reconnect` changes or `load_config()` runs | `Settings.qml`, `Websocket.qml` |
| `reconnect_interval_ms_changed` | `Signal(int)` | `onReconnect_interval_ms_changed` | `reconnect_interval_ms` changes or `load_config()` runs | `Websocket.qml` (`autoReconnectTimer`) |
| `view_refresh_hz_changed` | `Signal(int)` | `onView_refresh_hz_changed` | `view_refresh_hz` changes or `load_config()` runs | `Settings.qml`, `TelemetryStore.reschedule_ui_timer()` |
| `min_log_level_changed` | `Signal(str)` | `onMin_log_level_changed` | `min_log_level` changes or `load_config()` runs | `main.qml` (`logToaster.minSeverity`, `settingsDialog.minLogLevel`) |
| `connect_requested` | `Signal()` | `onConnect_requested` | `backend.connect()` / `connect_to_server()` is called | `Websocket.qml` |
| `log_sent` | `Signal(str, str)` | `onLog_sent(level, msg)` | Any `log`, `info`, `warn`, `err`, `log_info`, `log_warn`, `log_error` call | `main.qml` (`notificationModel` + `logToaster.showToast`) |
| `data_opened` | `Signal(str)` | `onData_opened(filePath)` | Native `QFileDialog` in `open_data()` picks a file | Available to QML extensions |
| `data_loaded` | `Signal(str, str, "QVariant")` | `onData_loaded(mode, filePath, meta)` | `load_data()` or `_FileParseWorker` finishes parsing a dataset | `Dashboard.qml`, `Graphs.qml` |
| `local_data_changed` | `Signal()` | `onLocal_data_changed` | `refresh_local_data()` or download/recording/rename/delete updates `CONFIG_DIR / "data"` | `Dashboard.qml` (`local_data` list) |
| `remote_data_changed` | `Signal()` | `onRemote_data_changed` | HTTP `/api/data` response or WS `remote_data_list` updates server file list | `Dashboard.qml` (`remote_data` list) |
| `external_data_changed` | `Signal()` | `onExternal_data_changed` | `add_external_data()`, `hide_external_data()`, rename, or delete updates `config.json` | `Dashboard.qml` (`external_data` list) |
| `telemetry_changed` | `Signal()` | `onTelemetry_changed` | Throttled live WS ingestion, file load, or recording pull completes | `Graphs.qml`, `GraphCard.qml`, `telemetry`/`loaded_meta` bindings |
| `telemetry_point_received` | `Signal("QVariantMap")` | `onTelemetry_point_received(rec)` | Declared signal for per-point listeners (`Graphs.qml` pulls via `telemetry_changed`) | Optional per-point consumers |
| `channels_changed` | `Signal()` | `onChannels_changed` | `load_graphs_config()`, WS `init` `channels` metadata, or new channel discovery | `Graphs.qml` (`available_channels`, `default_graph_cards`) |
| `armed_changed` | `Signal(bool)` | `onArmed_changed(armed)` | Server `init`/`armed` message or disconnect auto-disarm changes `armed` | `main.qml` topbar badge, `Actuators.qml` |
| `valves_changed` | `Signal()` | `onValves_changed` | Initial valve seeding, `valve_state`, or `summary` update arrives | `Actuators.qml`, `ActuatorCard.qml` |
| `valve_state_updated` | `Signal(str, str)` | `onValve_state_updated(valveId, state)` | Single actuator transitions state in `apply_valve_state()` | `Actuators.qml` |
| `ws_send_requested` | `Signal(str)` | `onWs_send_requested(payload)` | Outbound `command`, `abort`, `record`, or WS fallback `remote_data_req` JSON frame | `main.qml` → `root.sendTextMessage(payload)` |
| `disconnected` | `Signal()` | `onDisconnected` | `on_ws_connected_changed(False)` after an open session | `Dashboard.qml` (`commitPendingDeletions()`, banner reset) |
| `websocket_closed` | `Signal()` | `onWebsocket_closed` | Same disconnect transition as `disconnected` | `Dashboard.qml` |
| `recording_changed` | `Signal(bool)` | `onRecording_changed(active)` | `set_recording()` / `toggle_recording()` starts or stops CSV logging | `main.qml` topbar `recordBtn` |
| `server_recording_active_on_connect` | `Signal(str)` | `onServer_recording_active_on_connect(filename)` | Server `init` reports `recording: true` while client is not recording | `main.qml` (`serverRecordingDialog`) |
| `camera_config_changed` | `Signal()` | `onCamera_config_changed` | Camera mode, profile, manual target, or credentials updated | `Video.qml`, `Settings.qml` |
| `camera_active_changed` | `Signal(bool)` | `onCamera_active_changed(active)` | `set_camera_active()` or `toggle_camera()` changes camera state | `Video.qml` |
| `camera_toggle_requested` | `Signal()` | `onCamera_toggle_requested` | `toggle_camera()` invoked cleanly | `Video.qml` |

---

## 3. Python `Backend` Exposed Properties (`@QtCore.Property`)

| Property Name | Type | Notify Signal | Access | Purpose & Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `config_dir` | `str` | `config_changed` | Read-only | Active config root (`contents/config/` in dev mode; OS `platformdirs` config dir when packaged). |
| `config_file` | `str` | `config_changed` | Read-only | Full path to active `config.json`. |
| `is_dev_mode` | `bool` | `constant=True` | Read-only | `True` when running from source or `FLOW_CONTROL_DEV=1`; `False` in PyInstaller/AppImage builds. |
| `server_url` | `str` | `server_url_changed` | Read / Write | WebSocket URL (default `ws://127.0.0.1:8080/ws`, overridden by `FLOW_CONTROL_WS_URL`). Persists to `config.json`. |
| `auto_reconnect` | `bool` | `auto_reconnect_changed` | Read / Write | Enables startup connect and periodic retry timer in `Websocket.qml`. Persists to `config.json`. |
| `reconnect_interval_ms` | `int` | `reconnect_interval_ms_changed` | Read / Write | Reconnect polling interval in ms (default `2000`). Persists to `config.json`. |
| `view_refresh_hz` | `int` | `view_refresh_hz_changed` | Read / Write | UI graph refresh rate cap (`1..120`, default `20`). Persists under `ui.view_refresh_hz`. |
| `min_log_level` | `str` | `min_log_level_changed` | Read / Write | Minimum toast severity (`"INFO"`, `"WARN"`, `"ERR"`). Persists under `ui.min_log_level`. |
| `camera_mode` | `str` | `camera_config_changed` | Read-only | Camera target selection mode: `"auto"` or `"manual"`. |
| `camera_profile` | `str` | `camera_config_changed` | Read-only | RTSP transport/latency profile: `"udp_high"` or `"tcp_low"`. |
| `camera_manual_target` | `str` | `camera_config_changed` | Read-only | Manual camera IP or full URL override (`192.168.0.108` default). |
| `camera_username` | `str` | `camera_config_changed` | Read-only | Amcrest camera digest/RTSP username (default `"admin"`). |
| `camera_password` | `str` | `camera_config_changed` | Read-only | Amcrest camera RTSP password. |
| `camera_rtsp_url` | `str` | `camera_config_changed` | Read-only | Computed RTSP/stream URL with credentials and auto-detected subnet IP (`192.168.1.108` vs `192.168.0.108`). |
| `camera_active` | `bool` | `camera_active_changed` | Read-only | Whether the camera stream player in `Video.qml` should be active. |
| `telemetry` | `QVariantMap` | `telemetry_changed` | Read-only | Latest live frame snapshot (`seconds`, `uptime`, `packet_id`, `values`). |
| `loaded_meta` | `QVariantMap` | `telemetry_changed` | Read-only | Active loaded file metadata (`source`, `path`, `resolvedPath`, `name`, `columns`, `units`, `count`, `minTime`, `maxTime`, `duration`). |
| `default_graph_cards` | `QVariantList` | `channels_changed` | Read-only | Normalized default card definitions loaded from `config/graphs/graphs.json`. |
| `available_channels` | `QVariantList` | `channels_changed` | Read-only | List of `{"key", "title", "unit", "allowed_units", "color"}` dicts for `GraphEditDialog.qml`. |
| `recording` | `bool` | `recording_changed` | Read / Write | Whether synchronized client + server CSV telemetry recording is active. |
| `armed` | `bool` | `armed_changed` | Read / Write | System `SAFE` (`False`) / `ARMED` (`True`) interlock state synced from server. |
| `valve_definitions` | `QVariantList` | `config_changed` | Read-only | Actuator card metadata list pushed in server `init` (or seeded from config). |
| `valves` | `QVariantMap` | `valves_changed` | Read-only | Current normalized actuator state map (`{"N2OV": "CLOSED", ...}`). |
| `local_data` | `QVariantList` | `local_data_changed` | Read-only | Filenames discovered in `CONFIG_DIR / "data"`. |
| `remote_data` | `QVariantList` | `remote_data_changed` | Read-only | Filenames reported by server `GET /api/data` / WS `remote_data_list`. |
| `external_data` | `QVariantList` | `external_data_changed` | Read-only | Persisted file paths opened from arbitrary disk locations via `open_data()`. |

---

## 4. Python `Backend` Exposed Slots (`@QtCore.Slot`)

### 4.1 Logging, Config, Settings & Desktop
| Slot Signature | Return Type | Description |
| :--- | :--- | :--- |
| `log(level: str, msg: str)` | `None` | Logs at `INFO`, `WARN`, or `ERR` to console and emits `log_sent(level, msg)`. |
| `info(msg)` / `log_info(msg)` | `None` | Convenience `INFO` log helpers. |
| `warn(msg)` / `log_warn(msg)` | `None` | Convenience `WARN` log helpers. |
| `err(msg)` / `log_error(msg)` | `None` | Convenience `ERR` log helpers. |
| `load_config()` | `QVariantMap` | Reloads `config.json`, seeds valves, applies `QT_FFMPEG_RTSP_TRANSPORT`, emits change signals. |
| `save_config(data: QVariantMap)` | `bool` | Writes `data` to `config.json` and emits `config_changed`. |
| `get_setting(key: str, default=None)` | `QVariant` | Reads a top-level key from `config.json` in memory. |
| `set_setting(key: str, value: QVariant)` | `None` | Updates a top-level key and saves `config.json`. |
| `set_server_url(url: str)` | `None` | Setter slot for `server_url`. |
| `set_auto_reconnect(enabled: bool)` | `None` | Setter slot for `auto_reconnect`. |
| `set_reconnect_interval_ms(interval: int)` | `None` | Setter slot for `reconnect_interval_ms`. |
| `set_view_refresh_hz(hz: int)` | `None` | Setter slot for `view_refresh_hz`. |
| `set_min_log_level(level: str)` | `None` | Setter slot for `min_log_level`. |
| `get_split_config()` | `QVariantMap` | Reads `{split_active, left_page, right_page, last_right_page, focused_pane, split_ratio}`. |
| `save_split_config(split_active, left_page, right_page, last_right_page, focused_pane, split_ratio)` | `None` | Persists split-view pane state to `config.json` when changed. |
| `connect()` / `connect_to_server()` | `None` | Emits `connect_requested` to initiate WebSocket startup. |
| `show_in_file_browser(url: str)` | `None` | Opens enclosing directory in the OS file manager using `QUrl.fromLocalFile` + `QDesktopServices.openUrl`. |

### 4.2 Camera Controls
| Slot Signature | Return Type | Description |
| :--- | :--- | :--- |
| `set_camera_settings(mode: str, profile: str, manual_target: str)` | `None` | Updates mode (`auto`/`manual`), transport profile (`udp_high`/`tcp_low`), and manual target IP/URL. |
| `set_camera_active(active: bool)` | `None` | Sets stream active state (stopping active player state cleanly when deactivated). |
| `configure_camera_player(player: QObject)` | `None` | Lazy-imports `QtMultimedia` and sets `LowLatencyStreaming` + 5 s `networkTimeout` on `MediaPlayer`. |
| `toggle_camera()` | `None` | Toggles `camera_active` / emits `camera_toggle_requested`. |
| `set_camera_credentials(username: str, password: str)` | `None` | Persists Amcrest camera credentials to `config.json`. |
| `set_camera_manual_target(target: str)` | `None` | Persists manual target IP/URL to `config.json`. |

### 4.3 Actuators, Telemetry, Recording & Data Files
| Slot Signature | Return Type | Description |
| :--- | :--- | :--- |
| `on_ws_connected_changed(connected: bool)` | `None` | Refreshes remote files on connect, re-syncs active recording, or auto-disarms & emits `disconnected` / `websocket_closed` on drop. |
| `set_armed(value: bool)` | `None` | Updates local `armed` property state. |
| `actuate_valve(valve_id: str, action: str)` | `None` | Checks `armed`, `external`, and `single_use`; emits outbound `command` JSON on `ws_send_requested`. |
| `abort()` | `None` | Emits `{"type": "abort", "command": "ABORT"}` regardless of `armed` state. |
| `ingest_ws_message(raw_message: str)` | `None` | Parses single/JSONL WS frames once: handles `init` (including `channels`), `valve_state`, `armed`, `alert`, `remote_data_*`, and ingests telemetry into `ColumnarTelemetryBuffer`. |
| `load_graphs_config()` | `None` | Reloads `config/graphs/graphs.json` (`channels` + `default_cards`) and emits `channels_changed`. |
| `save_graphs_config(cards: QVariantList)` | `bool` | Normalizes units/card layout fields and writes `graphs.json`. |
| `get_channel_meta(channel: str)` | `QVariantMap` | Returns `{"key", "title", "unit", "allowed_units", "color"}`. |
| `set_recording(active: bool)` / `toggle_recording()` | `None` / `bool` | Starts or stops synchronized local + server two-row CSV recording. |
| `pull_server_recording_state(filename: str = "")` | `None` | Fetches in-progress server CSV (`GET /api/data/{filename}` or WS fallback) into `_live_buffer`. |
| `load_data(mode_or_path: str, file_path: str = "")` | `QVariant` | Loads local, external, or cached/remote CSV/JSONL (async `QThreadPool` if > 10 MB; HTTP `GET /api/data/{filename}` if remote uncached). |
| `get_channel_data(source_mode, channel, t_start, t_end, max_buckets=300, filter_outliers_3std=False, smoothing_window=1, target_unit="")` | `QVariantMap` | Windowed time-series query from `ColumnarTelemetryBuffer` with optional unit conversion to `target_unit`. |
| `get_batch_channel_data(source_mode: str, requests: QVariantList)` | `QVariantMap` | Evaluates multiple graph card queries `{index, channel, tStart, tEnd, maxBuckets, filterOutliers3Std, smoothingWindow, targetUnit}` in one call. |
| `open_data(open_where: str = "")` | `str` | Opens lazy-imported `QFileDialog`, adds to `external_data`, emits `data_opened`, and loads file. |
| `add_external_data(file_path)` / `hide_external_data(file_path)` | `None` | Adds or hides a path in `config.json` `external_data`. |
| `refresh_local_data()` / `refresh_remote_data()` | `QVariantList` / `None` | Refreshes `local_data` from disk or `remote_data` via HTTP `GET /api/data` (WS fallback). |
| `download_remote_data(filename: str)` | `None` | Downloads remote log via HTTP `GET /api/data/{filename}` (WS fallback) to `CONFIG_DIR / "data"`. |
| `push_data_to_remote(mode_or_path: str, filename: str = "")` | `None` | Uploads local/external log via HTTP `PUT /api/data/{filename}` (WS fallback). |
| `mark_data_for_deletion(mode, filename)` / `unmark_data_for_deletion(mode, filename)` | `None` | Tracks pending soft-delete marks for the Dashboard UI. |
| `rename_data(mode, old_name, new_name)` / `delete_data(mode, filename)` | `bool` | Executes local/external disk ops or HTTP `POST /api/data/{name}/rename` & `DELETE /api/data/{name}` (WS fallback). |

---

## 5. Internal QML Component Signals

- **`Settings.qml`:** `minLogLevelUpdated(level)`, `autoConnectToggled(enabled)` (bound in `main.qml` to `backend.set_min_log_level()` and `sharedWebSocket`).
- **`NotificationToast.qml` & `NotificationTray.qml`:** `dismissed()`, `timeout()`, `clearRequested()`.
- **`PageHelper.qml`, `PopoutWindow.qml`, `PoppedOutPlaceholder.qml`, `SplitPaneFrame.qml`, `SplitTabBar.qml`, `SplitResizeHandle.qml`:** `returnRequested(pageName)`, `ratioChanged(newRatio)`, `swapRequested()`, `closeRequested()`, `focusRequested()`.
- **`Sidebar.qml` & `pages/sidebar/*.qml`:** `navigateRequested(pageName)`, `openInLeftRequested(pageName)`, `openInRightRequested(pageName)`, `openInNewWindowRequested(pageName)`, `settingsRequested()`, `notificationsRequested()`, `abortRequested()`, `keybindsToggled(enabled)`, `presetSelected(preset)`, `customSecondsModified(seconds)`, `smoothAllToggled(active)`, `editLayoutToggled(active)`, `timeScaleChanged(seconds)`.
- **`pages/actuators/ActuatorCard.qml`:** `actuateRequested(valveId, action)`, `confirmRequested(valveId, action, label)`.
- **`pages/dashboard/*.qml`:** `modeSelected(mode)`, `dataSelected(name)`, `dataDoubleClicked(name)`, `refreshRequested()`, `undoDeleteRequested(...)`, `renameRequested(name)`, `deleteRequested(name)`, `hideRequested(name)`, `showInBrowserRequested()`, `openDataRequested()`, `deleteDataRequested()`, `downloadDataRequested()`, `pushDataRequested()`, `renameConfirmed(newName)`, `deleteConfirmed()`.
- **`pages/graphs/*.qml`:** `editRequested(index)`, `removeRequested(index)`, `moveRequested(fromIndex, toIndex)`, `resizeRequested(index, newColSpan, newHeight)`, `settingsApplied(index, updatedConfig)`, `picked(key)`.

---

## 6. Resolved Signal & Bridge Audit History (Phases 1–4)

All signal gaps identified in earlier drafts are now resolved:
- **Redundant QML socket parsing removed:** `webSocketMessageReceived`, `jsonReceived`, and `messageReceived` were retired; raw frames pass straight from `sharedWebSocket` to `backend.ingest_ws_message()`.
- **Remote & local Dashboard lifecycle wired:** `disconnected`, `websocket_closed`, `local_data`, `remote_data`, `external_data`, `refresh_local_data`, `refresh_remote_data`, `download_remote_data`, `push_data_to_remote`, `mark_data_for_deletion`, `unmark_data_for_deletion`, `rename_data`, and `delete_data` are all implemented on `Backend` (`LogManager`).
- **Unified `min_log_level`:** `QtCore.Settings` was removed from `main.qml`; toast log severity now persists inside `config.json` (`ui.min_log_level`) alongside `view_refresh_hz`.
