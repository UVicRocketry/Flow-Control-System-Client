# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Telemetry File I/O
handles resolving data file paths,
parsing .csv / .jsonl telemetry files, and revealing files in the OS browser.
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from config_manager import CONFIG_DIR, CURRENT_DIR, REPO_ROOT


def _add_float_items(values: dict, mapping: dict, skip_keys: set | None = None) -> None:
    for k, v in mapping.items():
        if skip_keys and (k in skip_keys or isinstance(v, (dict, list))):
            continue
        try:
            values[str(k)] = float(v)
        except (ValueError, TypeError):
            pass


def extract_flat_values(data_obj: dict) -> dict:
    """
    flattens nested telemetry sub-dictionaries (pressures, temperatures,
    loads, etc.) and top-level numeric fields into {channel_key: float}.
    """
    values = {}
    groups = ("pressures", "temperatures", "loads", "channels", "values")
    for group_key in groups:
        sub = data_obj.get(group_key)
        if isinstance(sub, dict):
            _add_float_items(values, sub)

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
    _add_float_items(values, data_obj, skip_keys)
    return values


def _unit_for_channel(ch: str, known_channels: dict) -> str:
    """returns the CSV header unit string for a channel key."""
    if ch in known_channels and known_channels[ch].get("unit"):
        u = str(known_channels[ch]["unit"])
        return "C" if u == "°C" else u.lower() if u == "PSI" else u
    if ch.startswith("M_") or ch == "L_RUN_TANK":
        return "kg"
    if ch.startswith("P_"):
        return "kPa"
    if ch.startswith("T_"):
        return "C"
    if ch.startswith("L_"):
        return "N"
    return ""


def resolve_data_file(target: str, known_channels: dict | None = None) -> Path:
    """
    resolves a requested data filename against direct paths, CONFIG_DIR/data,
    and repository log folders.
    """
    p = Path(target)
    if p.exists() and p.is_file():
        return p
    if p.is_absolute():
        raise FileNotFoundError(f"File not found: {target}")

    candidates = [
        CONFIG_DIR / "data" / p.name,
        CURRENT_DIR.parent / "data" / p.name,
        (
            REPO_ROOT.parent
            / "PDP-Ground-Support-Rewrite"
            / "contents"
            / "logs"
            / p.name
        ),
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            return cand

    raise FileNotFoundError(f"File not found: {target}")


def _is_header_row(row: list[str]) -> bool:
    """
    returns True if a CSV row consists of column names rather than numbers.
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


def _parse_jsonl_line(line: str, fallback_t: float) -> tuple[float, dict] | None:
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    vals = extract_flat_values(obj)
    if not vals:
        return None
    sec_raw = obj.get("seconds", obj.get("uptime", obj.get("time", fallback_t)))
    try:
        s_val = float(sec_raw)
    except (ValueError, TypeError):
        s_val = fallback_t
    return s_val, vals


def _parse_jsonl_file(resolved_path: Path) -> tuple[list, list, list]:
    records, raw_seconds, discovered_cols = [], [], []
    with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parsed = _parse_jsonl_line(line, len(records) * 0.1)
            if parsed is None:
                continue
            s_val, vals = parsed
            for k in vals:
                if k not in discovered_cols:
                    discovered_cols.append(k)
            raw_seconds.append(s_val)
            records.append({"t": s_val, "values": vals})
    return records, raw_seconds, discovered_cols


def _parse_csv_time(row: list[str], row_idx: int, time_col_idx: int | None) -> float:
    if time_col_idx is not None and time_col_idx < len(row):
        try:
            return float(row[time_col_idx])
        except (ValueError, TypeError):
            pass
    return row_idx * 0.1


def _consume_csv_row(
    row: list[str],
    row_idx: int,
    time_col_idx: int | None,
    value_cols: list,
    raw_seconds: list,
    records: list,
) -> None:
    if not row:
        return
    s_val = _parse_csv_time(row, row_idx, time_col_idx)
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


def _extract_csv_units(
    first_row: list[str], clean_header: list[str], value_cols: list
) -> dict[str, str]:
    clean_units = [u.strip() for u in first_row]
    if len(clean_units) == len(clean_header) + 1 and clean_units[0] == "":
        clean_units = clean_units[1:]

    csv_units: dict[str, str] = {}
    for idx, col_name in value_cols:
        if idx < len(clean_units) and clean_units[idx]:
            csv_units[col_name] = clean_units[idx]

    if "L_RUN_TANK" in csv_units and "M_RUN_TANK" not in csv_units:
        csv_units["M_RUN_TANK"] = csv_units["L_RUN_TANK"]
    elif "M_RUN_TANK" in csv_units and "L_RUN_TANK" not in csv_units:
        csv_units["L_RUN_TANK"] = csv_units["M_RUN_TANK"]
    return csv_units


def _parse_csv_file(resolved_path: Path) -> tuple[list, list, list, dict[str, str]]:
    records, raw_seconds, discovered_cols = [], [], []
    csv_units: dict[str, str] = {}
    with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        first_row = next(reader, None)
        if not first_row:
            return records, raw_seconds, discovered_cols, csv_units

        second_row = next(reader, None)
        pending_data_rows = []
        # check if first_row is units (psi,psi,...,s) and second_row is names
        has_units_row = second_row is not None and _is_header_row(second_row)
        if has_units_row:
            clean_header = [h.strip() for h in second_row]
        else:
            clean_header = [h.strip() for h in first_row]
            if second_row is not None:
                pending_data_rows.append(second_row)

        # locate 'seconds' column (or time/t/uptime); ignore 'timestamp'
        time_col_idx = None
        for idx, col_name in enumerate(clean_header):
            if col_name.lower() in ("seconds", "time", "t", "uptime"):
                time_col_idx = idx
                break

        ignored_cols = {"timestamp", "seconds", "time", "t", "uptime"}
        value_cols = [
            (idx, col_name)
            for idx, col_name in enumerate(clean_header)
            if idx != time_col_idx and col_name and col_name.lower() not in ignored_cols
        ]
        discovered_cols = [col_name for _, col_name in value_cols]
        if has_units_row:
            csv_units = _extract_csv_units(first_row, clean_header, value_cols)

        row_counter = 0
        for p_row in pending_data_rows:
            _consume_csv_row(
                p_row,
                row_counter,
                time_col_idx,
                value_cols,
                raw_seconds,
                records,
            )
            row_counter += 1
        for row in reader:
            _consume_csv_row(
                row,
                row_counter,
                time_col_idx,
                value_cols,
                raw_seconds,
                records,
            )
            row_counter += 1
    return records, raw_seconds, discovered_cols, csv_units


def parse_telemetry_file_with_units(
    resolved_path: Path,
) -> tuple[list, list, list, dict[str, str]]:
    """
    parses a .csv or .jsonl telemetry file into
    (records, raw_seconds, cols, csv_units).
    supports single-header and two-row-header CSVs (units + channel names).
    ignores 'timestamp' columns and uses 'seconds' for time indexing.
    """
    if resolved_path.suffix.lower() == ".jsonl":
        records, raw_seconds, discovered_cols = _parse_jsonl_file(resolved_path)
        csv_units: dict[str, str] = {}
    else:
        records, raw_seconds, discovered_cols, csv_units = _parse_csv_file(
            resolved_path
        )

    # normalize unix epoch seconds (>100,000s) to relative seconds
    if raw_seconds:
        s0 = raw_seconds[0]
        if s0 > 100000.0:
            raw_seconds = [round(s - s0, 6) for s in raw_seconds]
            for idx, rec in enumerate(records):
                rec["t"] = raw_seconds[idx]

    # ensure records are sorted monotonically so bisect slicing works
    if len(records) > 1 and any(
        raw_seconds[i] > raw_seconds[i + 1] for i in range(len(raw_seconds) - 1)
    ):
        paired = sorted(zip(raw_seconds, records), key=lambda x: x[0])
        raw_seconds = [p[0] for p in paired]
        records = [p[1] for p in paired]

    return records, raw_seconds, discovered_cols, csv_units


def parse_telemetry_file(resolved_path: Path) -> tuple[list, list, list]:
    """
    parses a .csv or .jsonl telemetry file into (records, raw_seconds, cols).
    """
    records, raw_seconds, discovered_cols, _ = parse_telemetry_file_with_units(
        resolved_path
    )
    return records, raw_seconds, discovered_cols


def list_local_data_files() -> list[str]:
    """
    scans CONFIG_DIR / 'data' for telemetry files (.csv, .jsonl, .bin)
    and returns their filenames sorted newest-first (then alphabetically).
    """
    data_dir = CONFIG_DIR / "data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return []

    allowed_exts = {".csv", ".jsonl", ".bin"}
    entries = []
    for p in data_dir.iterdir():
        if p.is_file() and p.suffix.lower() in allowed_exts:
            try:
                mtime = p.stat().st_mtime
            except OSError:
                mtime = 0.0
            entries.append((mtime, p.name))

    entries.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in entries]


def rename_data_file(mode: str, old_name: str, new_name: str) -> Path:
    """renames a local or external telemetry file and returns the new Path."""
    new_clean = Path(new_name.strip()).name
    if not new_clean:
        raise ValueError("New filename cannot be empty.")

    if mode == "local":
        src = CONFIG_DIR / "data" / Path(old_name).name
    else:
        src = Path(old_name)

    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    if Path(new_clean).suffix == "" and src.suffix:
        new_clean = new_clean + src.suffix

    dst = src.with_name(new_clean)
    if dst.exists() and dst != src:
        raise FileExistsError(f"Target file already exists: {dst.name}")

    src.rename(dst)
    return dst


def delete_data_file(mode: str, filename: str) -> Path:
    """deletes a local or external telemetry file and returns its Path."""
    if mode == "local":
        target = CONFIG_DIR / "data" / Path(filename).name
    else:
        target = Path(filename)

    if not target.exists():
        raise FileNotFoundError(f"File not found: {target}")

    target.unlink()
    return target


def init_recording_csv(dest_path: Path, known_channels: dict) -> list[str]:
    """
    creates a new telemetry CSV file with the standard two-row header
    (units row + channel names + seconds) and returns the ordered channel list.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    channels = list(known_channels.keys())
    if not channels:
        channels = [
            "P_INJECTOR",
            "P_COMB_CHMBR",
            "P_N2O_FLOW",
            "P_N2_FLOW",
            "P_RUN_TANK",
            "M_RUN_TANK",
            "L_THRUST",
            "T_RUN_TANK",
            "T_INJECTOR",
            "T_COMB_CHMBR",
            "T_POST_COMB",
        ]
    units_row = [_unit_for_channel(ch, known_channels) for ch in channels] + ["s"]
    header_row = channels + ["seconds"]
    with open(dest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(units_row)
        writer.writerow(header_row)
    return channels


def append_recording_rows(
    dest_path: Path, channels: list[str], ingested_records: list[dict]
) -> None:
    """appends newly ingested live telemetry records to a recording CSV."""
    if not ingested_records or not channels:
        return
    with open(dest_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for rec in ingested_records:
            vals = rec.get("values", {})
            t_val = round(float(rec.get("t", 0.0)), 6)
            row = [
                round(float(vals[ch]), 4) if ch in vals else "" for ch in channels
            ] + [t_val]
            writer.writerow(row)


def _reveal_linux(
    target_file: Path, target_dir: Path, is_dir: bool, log_info_fn
) -> None:
    if not is_dir:
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

    # fallback to xdg-open on directory if dbus FileManager1 is unavailable
    if shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", str(target_dir)])
        if log_info_fn:
            log_info_fn(f"Showing folder: {target_dir}")


def _reveal_desktop(target_file: Path, is_dir: bool, log_info_fn) -> None:
    if sys.platform == "win32":
        flag = "" if is_dir else "/select,"
        subprocess.Popen(f'explorer {flag}"{target_file}"')
        label = "Explorer"
    else:
        cmd = ["open", str(target_file)] if is_dir else ["open", "-R", str(target_file)]
        subprocess.Popen(cmd)
        label = "Finder"
    if log_info_fn:
        log_info_fn(f"Showing in {label}: {target_file.name}")


def reveal_in_file_browser(url: str, log_info_fn=None, log_warn_fn=None) -> None:
    """reveals the target file or directory in the native OS file manager."""
    candidate = Path(url)
    if not candidate.exists():
        local_candidate = CONFIG_DIR / "data" / candidate.name
        if local_candidate.exists():
            candidate = local_candidate
    target_file = candidate.resolve()
    is_dir = target_file.is_dir()
    target_dir = target_file if is_dir else target_file.parent
    try:
        if sys.platform.startswith("linux"):
            _reveal_linux(target_file, target_dir, is_dir, log_info_fn)
        elif sys.platform in ("win32", "darwin"):
            _reveal_desktop(target_file, is_dir, log_info_fn)
    except Exception as e:
        if log_warn_fn:
            log_warn_fn(f"Failed to open data file location: {e}")
