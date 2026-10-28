# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Telemetry Time-Series & Channel Processing
handles channel metadata inference, live WebSocket frame ingestion,
and windowed time-series downsampling, 3-std outlier filtering, and smoothing.
"""

import bisect
import json
import math
import time

from telemetry_files import extract_flat_values


def register_channel_if_missing(known_channels: dict, key: str) -> bool:
    """
    registers a newly discovered channel key with default unit and theme colour
    inferred from its prefix (P_ -> PSI, T_ -> °C, L_ -> lbf).
    returns True if a new channel was added.
    """
    if not key or key in known_channels:
        return False
    unit = (
        "PSI"
        if key.startswith("P_")
        else ("°C" if key.startswith("T_") else ("lbf" if key.startswith("L_") else ""))
    )
    color = (
        "theme:highlight"
        if key.startswith("P_")
        else ("theme:neutral" if key.startswith("T_") else "theme:positive")
    )
    known_channels[key] = {
        "title": key.replace("_", " ").title(),
        "unit": unit,
        "color": color,
    }
    return True


def format_channel_meta(known_channels: dict, channel: str) -> dict:
    """returns normalized metadata dictionary for a single channel key."""
    meta = known_channels.get(channel, {})
    return {
        "key": channel,
        "title": meta.get("title", channel),
        "unit": meta.get("unit", ""),
        "color": meta.get("color", "theme:highlight"),
    }


def list_available_channels(known_channels: dict) -> list:
    """returns a list of channel metadata dictionaries for QML combo boxes."""
    return [format_channel_meta(known_channels, key) for key in known_channels]


def ingest_ws_telemetry_frames(
    raw_message: str,
    known_channels: dict,
    live_records: list,
    live_seconds: list,
    live_t0: float | None,
    latest_telemetry: dict,
) -> tuple[bool, list, float | None, dict]:
    """
    parses incoming WebSocket text frames (supporting both single JSON packets
    and multi-line JSONL streams) and appends samples to live_records using 'seconds'.
    returns (new_channels_added, ingested_records, updated_live_t0, updated_latest_telemetry).
    """
    if not raw_message:
        return False, [], live_t0, latest_telemetry

    new_channels = False
    ingested_records = []

    for line in raw_message.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        if not isinstance(msg, dict):
            continue

        msg_type = msg.get("type", "")
        if msg_type and msg_type != "telemetry":
            continue

        data_obj = msg.get("data", msg) if isinstance(msg.get("data"), dict) else msg
        values = extract_flat_values(data_obj)
        if not values:
            continue

        raw_sec = data_obj.get("seconds")
        if raw_sec is None:
            raw_sec = data_obj.get("uptime", data_obj.get("time", time.time()))
        try:
            sec_val = float(raw_sec)
        except (ValueError, TypeError):
            sec_val = time.time()

        # anchor live_t0 on first epoch-style value so live plots start near t=0s
        if live_t0 is None:
            live_t0 = sec_val if sec_val > 1e6 else 0.0
        rel_s = sec_val - live_t0 if live_t0 > 0 else sec_val

        for ch_key in values:
            if register_channel_if_missing(known_channels, ch_key):
                new_channels = True

        record = {"t": rel_s, "values": values}
        live_records.append(record)
        live_seconds.append(rel_s)
        ingested_records.append(record)

        merged_vals = dict(latest_telemetry.get("values", {}))
        merged_vals.update(values)
        latest_telemetry = {
            "seconds": rel_s,
            "uptime": float(data_obj.get("uptime", rel_s)),
            "packet_id": int(data_obj.get("packet_id", len(live_records))),
            "values": merged_vals,
        }

    return new_channels, ingested_records, live_t0, latest_telemetry


def query_channel_series(
    records: list,
    seconds_list: list,
    channel: str,
    t_start: float,
    t_end: float,
    max_buckets: int = 300,
    filter_outliers_3std: bool = False,
    smoothing_window: int = 1,
) -> dict:
    """
    computes windowed, optionally 3-std outlier-filtered, bucket-downsampled,
    and moving-average smoothed time-series points for a given channel.
    - when t_end <= 0: treats abs(t_start) as a trailing window duration in seconds
      ending at the most recent sample in seconds_list.
    - when t_end > 0: slices the explicit [t_start, t_end] interval.
    """
    empty_res = {
        "points": [],
        "min": 0.0,
        "max": 100.0,
        "mean": 0.0,
        "std": 0.0,
        "latest": 0.0,
        "rawCount": 0,
        "filteredCount": 0,
        "bucketCount": 0,
        "tMin": 0.0,
        "tMax": 30.0,
    }
    if not records or not seconds_list or not channel:
        return empty_res

    dataset_min_t = seconds_list[0]
    dataset_max_t = seconds_list[-1]

    if t_end <= 0.0:
        # preset window mode: t_start holds negative window_seconds (e.g. -30, -60, -180)
        window_sec = abs(t_start) if t_start != 0.0 else 30.0
        win_end = dataset_max_t
        if window_sec >= 99999.0:
            win_start = dataset_min_t
        else:
            win_start = max(dataset_min_t, win_end - window_sec)
    else:
        win_start = max(dataset_min_t, min(t_start, t_end))
        win_end = min(dataset_max_t, max(t_start, t_end))

    # binary-search slice indices in O(log N)
    idx_left = bisect.bisect_left(seconds_list, win_start)
    idx_right = bisect.bisect_right(seconds_list, win_end)
    sliced = records[idx_left:idx_right]

    raw_pts = []
    for r in sliced:
        v = r["values"].get(channel)
        if v is not None:
            raw_pts.append((r["t"], float(v)))

    raw_n = len(raw_pts)
    if raw_n == 0:
        empty_res["tMin"] = win_start
        empty_res["tMax"] = max(win_start + 1.0, win_end)
        return empty_res

    # compute mean and standard deviation across raw windowed points
    sum_v = sum(p[1] for p in raw_pts)
    mean_v = sum_v / raw_n
    variance = sum((p[1] - mean_v) ** 2 for p in raw_pts) / raw_n if raw_n > 1 else 0.0
    std_v = math.sqrt(variance)

    # 3-standard-deviation outlier removal (drops spikes outside mean +/- 3*std)
    if filter_outliers_3std and std_v > 1e-6 and raw_n >= 4:
        threshold = 3.0 * std_v
        filtered_pts = [p for p in raw_pts if abs(p[1] - mean_v) <= threshold]
        if not filtered_pts:
            filtered_pts = raw_pts
    else:
        filtered_pts = raw_pts

    filtered_n = len(filtered_pts)

    # recompute clean min/max/mean after outlier rejection so y-axis autoscale isn't skewed
    clean_min = min(p[1] for p in filtered_pts)
    clean_max = max(p[1] for p in filtered_pts)
    clean_mean = sum(p[1] for p in filtered_pts) / filtered_n
    latest_v = filtered_pts[-1][1]

    # fixed time-bucket aggregation for downsampling dense datasets while preserving min/max envelope
    max_b = max(10, int(max_buckets))
    dt_span = max(win_end - win_start, 1e-3)

    if filtered_n <= max_b:
        bucketed = [
            {"t": p[0], "v": p[1], "minV": p[1], "maxV": p[1], "count": 1}
            for p in filtered_pts
        ]
    else:
        bucket_size = dt_span / float(max_b)
        buckets = {}
        for t_val, v_val in filtered_pts:
            b_idx = int((t_val - win_start) / bucket_size)
            if b_idx >= max_b:
                b_idx = max_b - 1
            elif b_idx < 0:
                b_idx = 0
            if b_idx not in buckets:
                buckets[b_idx] = [v_val, 1, v_val, v_val]
            else:
                b = buckets[b_idx]
                b[0] += v_val
                b[1] += 1
                if v_val < b[2]:
                    b[2] = v_val
                if v_val > b[3]:
                    b[3] = v_val

        bucketed = []
        for b_idx in sorted(buckets.keys()):
            b_sum, b_cnt, b_min, b_max = buckets[b_idx]
            b_t = win_start + (b_idx + 0.5) * bucket_size
            bucketed.append(
                {
                    "t": b_t,
                    "v": b_sum / b_cnt,
                    "minV": b_min,
                    "maxV": b_max,
                    "count": b_cnt,
                }
            )

    # optional centered moving-average smoothing pass over bucketed series
    sw = max(1, int(smoothing_window))
    if sw > 1 and len(bucketed) > 1:
        half_w = sw // 2
        smoothed = []
        for i in range(len(bucketed)):
            lo = max(0, i - half_w)
            hi = min(len(bucketed), i + half_w + 1)
            avg_val = sum(bucketed[j]["v"] for j in range(lo, hi)) / (hi - lo)
            item = dict(bucketed[i])
            item["v"] = avg_val
            smoothed.append(item)
        bucketed = smoothed

    return {
        "points": bucketed,
        "min": clean_min,
        "max": clean_max,
        "mean": clean_mean,
        "std": std_v,
        "latest": latest_v,
        "rawCount": raw_n,
        "filteredCount": filtered_n,
        "bucketCount": len(bucketed),
        "tMin": win_start,
        "tMax": win_end,
    }
