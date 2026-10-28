# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Telemetry File I/O & Demo Generation
handles resolving data file paths, generating synthetic demo logs,
parsing .csv / .jsonl telemetry files, and revealing files in the OS file browser.
"""

import csv
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from config_manager import CONFIG_DIR, CURRENT_DIR, REPO_ROOT


def extract_flat_values(data_obj: dict) -> dict:
    """
    flattens nested telemetry sub-dictionaries (pressures, temperatures, loads, etc.)
    and top-level numeric fields into a single {channel_key: float} map.
    """
    values = {}
    for group_key in ("pressures", "temperatures", "loads", "channels", "values"):
        sub = data_obj.get(group_key)
        if isinstance(sub, dict):
            for k, v in sub.items():
                try:
                    values[str(k)] = float(v)
                except (ValueError, TypeError):
                    pass

    # ignore time and metadata fields when scanning top-level keys
    skip_keys = {
        "packet_id",
        "seconds",
        "timestamp",
        "time",
        "t",
        "uptime",
        "type",
        "pressures",
        "temperatures",
        "loads",
        "channels",
        "values",
    }
    for k, v in data_obj.items():
        if k in skip_keys or isinstance(v, (dict, list)):
            continue
        try:
            values[str(k)] = float(v)
        except (ValueError, TypeError):
            pass
    return values


def _unit_for_channel(ch: str, known_channels: dict) -> str:
    """returns the CSV header unit string for a channel key."""
    if ch in known_channels and known_channels[ch].get("unit"):
        u = str(known_channels[ch]["unit"])
        return "C" if u == "°C" else u.lower() if u == "PSI" else u
    if ch.startswith("P_"):
        return "psi"
    if ch.startswith("T_"):
        return "C"
    if ch == "L_THRUST":
        return "N"
    if ch.startswith("L_"):
        return "kg"
    return ""


def generate_demo_csv(dest_path: Path, seed_name: str, known_channels: dict) -> None:
    """
    generates a realistic 180-second (1,800 samples @ 10 Hz) multi-channel CSV
    telemetry log matching the two-row header format (units row + channel names + seconds).
    includes occasional >3-std sensor spikes to demonstrate outlier smoothing.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    channels = [
        "P_INJECTOR",
        "P_COMB_CHMBR",
        "P_N2O_FLOW",
        "P_N2_FLOW",
        "P_RUN_TANK",
        "L_RUN_TANK",
        "L_THRUST",
        "T_RUN_TANK",
        "T_INJECTOR",
        "T_COMB_CHMBR",
        "T_POST_COMB",
    ]
    for k in known_channels:
        if k not in channels:
            channels.append(k)

    units_row = [_unit_for_channel(ch, known_channels) for ch in channels] + ["s"]
    header_row = channels + ["seconds"]

    # derive deterministic phase offset from file name so each demo file looks distinct
    phase_offset = (sum(ord(c) for c in seed_name) % 100) * 0.1

    with open(dest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(units_row)
        writer.writerow(header_row)
        for idx in range(1800):
            s = round(idx * 0.1, 6)
            # logistic sigmoid product simulating ramp-up (s=25), steady flow, and blowdown (s=145)
            envelope = (
                1.0
                / (1.0 + math.exp(-(s - 25.0) * 0.25))
                * (1.0 / (1.0 + math.exp((s - 145.0) * 0.18)))
            )
            row_vals = {
                "P_RUN_TANK": 740.0
                - 160.0 * (s / 180.0)
                + 18.0 * math.sin(s * 0.15 + phase_offset),
                "T_RUN_TANK": 21.0 - 12.0 * (s / 180.0) + 0.6 * math.cos(s * 0.2),
                "L_RUN_TANK": max(
                    5.0, 48.0 - 34.0 * (s / 180.0) + 0.3 * math.sin(s * 0.5)
                ),
                "P_N2O_FLOW": 610.0 * envelope
                + 12.0 * math.sin(s * 0.8 + phase_offset),
                "P_N2_FLOW": 800.0 - 45.0 * (s / 180.0) + 6.0 * math.cos(s * 0.3),
                "P_COMB_CHMBR": 420.0 * envelope + 14.0 * math.sin(s * 1.3),
                "P_INJECTOR": 540.0 * envelope + 10.0 * math.cos(s * 1.1),
                "T_INJECTOR": 22.0 + 35.0 * envelope + 1.2 * math.sin(s * 0.4),
                "T_COMB_CHMBR": 25.0 + 680.0 * envelope + 15.0 * math.sin(s * 0.9),
                "T_POST_COMB": 24.0 + 520.0 * envelope + 11.0 * math.cos(s * 0.85),
                "L_THRUST": 380.0 * envelope + 9.5 * math.sin(s * 1.7 + phase_offset),
            }
            # inject synthetic >3-std spikes at fixed indices for smoothing verification
            if idx in (180, 520, 890, 1240, 1590):
                for k in row_vals:
                    row_vals[k] += (
                        450.0
                        if k.startswith("P_")
                        else (180.0 if k.startswith("T_") else 160.0)
                    )

            writer.writerow([round(row_vals.get(ch, 0.0), 3) for ch in channels] + [s])


def resolve_data_file(target: str, known_channels: dict) -> Path:
    """
    resolves a requested data filename against direct paths, CONFIG_DIR/data,
    and repository log folders; synthesizes a demo CSV if no matching file exists yet.
    """
    p = Path(target)
    if p.exists() and p.is_file():
        return p

    candidates = [
        CONFIG_DIR / "data" / p.name,
        CURRENT_DIR.parent / "data" / p.name,
        REPO_ROOT.parent / "PDP-Ground-Support-Rewrite" / "contents" / "logs" / p.name,
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            return cand

    # generate sample CSV in CONFIG_DIR / "data" so built-in browser entries work out-of-the-box
    fallback_csv = CONFIG_DIR / "data" / (p.stem + ".csv")
    if not fallback_csv.exists():
        generate_demo_csv(fallback_csv, p.name, known_channels)
    return fallback_csv


def _is_header_row(row: list[str]) -> bool:
    """
    returns True if a CSV row consists of column names rather than numeric data cells.
    used to detect two-row headers (row 0 = units, row 1 = channel names).
    """
    if not row:
        return False
    numeric_count = 0
    non_empty_count = 0
    for cell in row:
        s = cell.strip()
        if not s:
            continue
        non_empty_count += 1
        try:
            float(s)
            numeric_count += 1
        except ValueError:
            pass
    return non_empty_count > 0 and numeric_count == 0


def parse_telemetry_file(resolved_path: Path) -> tuple[list, list, list]:
    """
    parses a .csv or .jsonl telemetry file into (records, raw_seconds, discovered_cols).
    supports both single-header CSVs and two-row header CSVs
    (where row 0 lists units like 'psi,psi,...,s' and row 1 lists channel names + 'seconds').
    ignores 'timestamp' columns and uses 'seconds' for time indexing.
    """
    records = []
    raw_seconds = []
    discovered_cols = []

    suffix = resolved_path.suffix.lower()
    if suffix == ".jsonl":
        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                vals = extract_flat_values(obj)
                if not vals:
                    continue
                sec_raw = obj.get(
                    "seconds", obj.get("uptime", obj.get("time", len(records) * 0.1))
                )
                try:
                    s_val = float(sec_raw)
                except (ValueError, TypeError):
                    s_val = len(records) * 0.1
                for k in vals:
                    if k not in discovered_cols:
                        discovered_cols.append(k)
                raw_seconds.append(s_val)
                records.append({"t": s_val, "values": vals})
    else:
        with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            first_row = next(reader, None)
            if first_row:
                second_row = next(reader, None)
                pending_data_rows = []

                # check if first_row is a units header (e.g. psi,psi,...,s) and second_row is channel names
                if second_row is not None and _is_header_row(second_row):
                    clean_header = [h.strip() for h in second_row]
                else:
                    clean_header = [h.strip() for h in first_row]
                    if second_row is not None:
                        pending_data_rows.append(second_row)

                # locate the 'seconds' column (or fallback 'time'/'t'/'uptime'); ignore 'timestamp'
                time_col_idx = None
                for idx, col_name in enumerate(clean_header):
                    if col_name.lower() in ("seconds", "time", "t", "uptime"):
                        time_col_idx = idx
                        break

                ignored_cols = {"timestamp", "seconds", "time", "t", "uptime"}
                value_cols = [
                    (idx, col_name)
                    for idx, col_name in enumerate(clean_header)
                    if idx != time_col_idx
                    and col_name
                    and col_name.lower() not in ignored_cols
                ]
                discovered_cols = [col_name for _, col_name in value_cols]

                def _consume_row(row: list[str], row_idx: int):
                    if not row:
                        return
                    if time_col_idx is not None and time_col_idx < len(row):
                        try:
                            s_val = float(row[time_col_idx])
                        except (ValueError, TypeError):
                            s_val = row_idx * 0.1
                    else:
                        s_val = row_idx * 0.1

                    vals = {}
                    for col_idx, col_name in value_cols:
                        if col_idx < len(row):
                            cell = row[col_idx].strip()
                            if not cell:
                                continue
                            try:
                                vals[col_name] = float(cell)
                            except (ValueError, TypeError):
                                pass
                    if vals:
                        raw_seconds.append(s_val)
                        records.append({"t": s_val, "values": vals})

                row_counter = 0
                for p_row in pending_data_rows:
                    _consume_row(p_row, row_counter)
                    row_counter += 1
                for row in reader:
                    _consume_row(row, row_counter)
                    row_counter += 1

    # normalize unix epoch seconds (>100,000s) to relative seconds while keeping run seconds intact
    if raw_seconds:
        s0 = raw_seconds[0]
        if s0 > 100000.0:
            raw_seconds = [round(s - s0, 6) for s in raw_seconds]
            for idx, rec in enumerate(records):
                rec["t"] = raw_seconds[idx]

    # ensure records are sorted monotonically by seconds so bisect slicing works
    if len(records) > 1 and any(
        raw_seconds[i] > raw_seconds[i + 1] for i in range(len(raw_seconds) - 1)
    ):
        paired = sorted(zip(raw_seconds, records), key=lambda x: x[0])
        raw_seconds = [p[0] for p in paired]
        records = [p[1] for p in paired]

    return records, raw_seconds, discovered_cols


def reveal_in_file_browser(url: str, log_info_fn=None, log_warn_fn=None) -> None:
    """reveals the target file in the native OS file manager."""
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
                if log_info_fn:
                    log_info_fn(f"Showing file: {target_file.name}")
                return

            # fallback to xdg-open on parent directory if dbus FileManager1 is unavailable
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(target_dir)])
                if log_info_fn:
                    log_info_fn(f"Showing in data folder: {target_dir}")
                return

        elif sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{target_file}"')
            if log_info_fn:
                log_info_fn(f"Showing file in Explorer: {target_file.name}")
            return

        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target_file)])
            if log_info_fn:
                log_info_fn(f"Showing file in Finder: {target_file.name}")
            return

    except Exception as e:
        if log_warn_fn:
            log_warn_fn(f"Failed to open data file location: {e}")
