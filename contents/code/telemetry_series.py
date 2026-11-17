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
        else (
            "°C" if key.startswith("T_")
            else ("lbf" if key.startswith("L_") else "")
        )
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


def _extract_ws_seconds(data_obj: dict) -> float:
    raw_sec = data_obj.get("seconds")
    if raw_sec is None:
        raw_sec = data_obj.get("uptime", data_obj.get("time", time.time()))
    try:
        return float(raw_sec)
    except (ValueError, TypeError):
        return time.time()


def _parse_ws_telemetry_line(line: str) -> tuple[dict, dict, float] | None:
    line = line.strip()
    if not line:
        return None
    try:
        msg = json.loads(line)
    except Exception:
        return None

    if not isinstance(msg, dict):
        return None

    msg_type = msg.get("type", "")
    if msg_type and msg_type != "telemetry":
        return None

    raw_data = msg.get("data")
    data_obj = raw_data if isinstance(raw_data, dict) else msg
    values = extract_flat_values(data_obj)
    if not values:
        return None

    return data_obj, values, _extract_ws_seconds(data_obj)


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
    and multi-line JSONL streams) and appends samples to live_records.
    returns (new_channels_added, ingested_records, live_t0, latest_telemetry).
    """
    if not raw_message:
        return False, [], live_t0, latest_telemetry

    new_channels = False
    ingested_records = []

    for line in raw_message.splitlines():
        parsed = _parse_ws_telemetry_line(line)
        if parsed is None:
            continue
        data_obj, values, sec_val = parsed

        # anchor live_t0 on first epoch value so live plots start near t=0s
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


def _compute_window_bounds(
    seconds_list: list, t_start: float, t_end: float
) -> tuple[float, float]:
    """
    computes (win_start, win_end) for a query.
    in live/preset mode (t_end <= 0), locks (win_end - win_start) to the full
    chosen window_sec so the X-axis never autoscales or stretches.
    """
    if not seconds_list:
        if t_end <= 0.0:
            has_w = t_start != 0.0 and abs(t_start) < 99999.0
            return 0.0, abs(t_start) if has_w else 30.0
        lo = min(t_start, t_end)
        return lo, max(lo + 1.0, max(t_start, t_end))

    dataset_min_t = seconds_list[0]
    dataset_max_t = seconds_list[-1]

    if t_end <= 0.0:
        window_sec = abs(t_start) if t_start != 0.0 else 30.0
        if window_sec >= 99999.0:
            win_start = dataset_min_t
            win_end = max(dataset_min_t + 30.0, dataset_max_t)
        else:
            win_end = dataset_max_t
            win_start = win_end - window_sec
    else:
        win_start = max(dataset_min_t, min(t_start, t_end))
        win_end = min(dataset_max_t, max(t_start, t_end))
        if win_end <= win_start:
            win_end = win_start + 1.0

    return win_start, win_end


def _empty_series_result(win_start: float, win_end: float) -> dict:
    return {
        "ts": [],
        "vs": [],
        "minVs": [],
        "maxVs": [],
        "min": 0.0,
        "max": 100.0,
        "mean": 0.0,
        "std": 0.0,
        "latest": 0.0,
        "rawCount": 0,
        "filteredCount": 0,
        "bucketCount": 0,
        "tMin": win_start,
        "tMax": max(win_start + 1e-3, win_end),
    }


def _finalize_buckets(
    buckets: dict,
    win_start: float,
    win_end: float,
    bucket_size: float,
    smoothing_window: int,
) -> tuple[list[float], list[float], list[float], list[float]]:
    ts: list[float] = []
    vs: list[float] = []
    min_vs: list[float] = []
    max_vs: list[float] = []
    for b_idx in sorted(buckets):
        b_sum, b_cnt, b_min, b_max = buckets[b_idx]
        b_t = (b_idx + 0.5) * bucket_size
        if b_t < win_start:
            b_t = win_start
        elif b_t > win_end:
            b_t = win_end
        ts.append(b_t)
        vs.append(b_sum / b_cnt)
        min_vs.append(b_min)
        max_vs.append(b_max)

    sw = max(1, int(smoothing_window))
    if sw > 1 and len(vs) > 1:
        half_w = sw // 2
        n_b = len(vs)
        vs = [
            sum(vs[max(0, i - half_w) : min(n_b, i + half_w + 1)])
            / (min(n_b, i + half_w + 1) - max(0, i - half_w))
            for i in range(n_b)
        ]
    return ts, vs, min_vs, max_vs


def _series_from_channel_arrays(
    t_vals: list[float],
    v_vals: list[float],
    win_start: float,
    win_end: float,
    max_buckets: int = 300,
    filter_outliers_3std: bool = False,
    smoothing_window: int = 1,
) -> dict:
    """computes a channel's downsampled & smoothed series in a single pass."""
    raw_n = len(v_vals)
    if raw_n == 0:
        return _empty_series_result(win_start, win_end)

    max_b = max(10, int(max_buckets))
    dt_span = max(win_end - win_start, 1e-3)
    bucket_size = dt_span / float(max_b)
    inv_bucket_size = float(max_b) / dt_span
    floor = math.floor

    if not filter_outliers_3std or raw_n < 4:
        sum_v = 0.0
        sum_sq = 0.0
        clean_min = v_vals[0]
        clean_max = v_vals[0]
        buckets: dict = {}

        for t_val, v_val in zip(t_vals, v_vals):
            sum_v += v_val
            sum_sq += v_val * v_val
            if v_val < clean_min:
                clean_min = v_val
            if v_val > clean_max:
                clean_max = v_val

            b_idx = floor(t_val * inv_bucket_size)
            b = buckets.get(b_idx)
            if b is None:
                buckets[b_idx] = [v_val, 1, v_val, v_val]
            else:
                b[0] += v_val
                b[1] += 1
                if v_val < b[2]:
                    b[2] = v_val
                if v_val > b[3]:
                    b[3] = v_val

        mean_v = sum_v / raw_n
        variance = max(0.0, (sum_sq / raw_n) - (mean_v * mean_v)) if raw_n > 1 else 0.0
        std_v = math.sqrt(variance)
        filtered_n = raw_n
        clean_mean = mean_v
        latest_v = v_vals[-1]
    else:
        sum_v = 0.0
        sum_sq = 0.0
        for v_val in v_vals:
            sum_v += v_val
            sum_sq += v_val * v_val
        mean_v = sum_v / raw_n
        variance = max(0.0, (sum_sq / raw_n) - (mean_v * mean_v))
        std_v = math.sqrt(variance)

        if std_v > 1e-6:
            threshold = 3.0 * std_v
            clean_sum = 0.0
            filtered_n = 0
            clean_min = 0.0
            clean_max = 0.0
            latest_v = v_vals[-1]
            buckets = {}
            for t_val, v_val in zip(t_vals, v_vals):
                if abs(v_val - mean_v) <= threshold:
                    if filtered_n == 0:
                        clean_min = v_val
                        clean_max = v_val
                    else:
                        if v_val < clean_min:
                            clean_min = v_val
                        if v_val > clean_max:
                            clean_max = v_val
                    clean_sum += v_val
                    filtered_n += 1
                    latest_v = v_val
                    b_idx = floor(t_val * inv_bucket_size)
                    b = buckets.get(b_idx)
                    if b is None:
                        buckets[b_idx] = [v_val, 1, v_val, v_val]
                    else:
                        b[0] += v_val
                        b[1] += 1
                        if v_val < b[2]:
                            b[2] = v_val
                        if v_val > b[3]:
                            b[3] = v_val
            if filtered_n == 0:
                return _series_from_channel_arrays(
                    t_vals, v_vals, win_start, win_end, max_buckets, False, smoothing_window
                )
            clean_mean = clean_sum / filtered_n
        else:
            return _series_from_channel_arrays(
                t_vals, v_vals, win_start, win_end, max_buckets, False, smoothing_window
            )

    ts, vs, min_vs, max_vs = _finalize_buckets(
        buckets, win_start, win_end, bucket_size, smoothing_window
    )
    return {
        "ts": ts,
        "vs": vs,
        "minVs": min_vs,
        "maxVs": max_vs,
        "min": clean_min,
        "max": clean_max,
        "mean": clean_mean,
        "std": std_v,
        "latest": latest_v,
        "rawCount": raw_n,
        "filteredCount": filtered_n,
        "bucketCount": len(ts),
        "tMin": win_start,
        "tMax": win_end,
    }


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
    computes windowed, optionally 3-std outlier-filtered, fixed-timespan
    bucketed, and moving-average smoothed time-series points for a channel.
    """
    win_start, win_end = _compute_window_bounds(seconds_list, t_start, t_end)
    if not records or not seconds_list or not channel:
        return _empty_series_result(win_start, win_end)

    idx_left = bisect.bisect_left(seconds_list, win_start)
    idx_right = bisect.bisect_right(seconds_list, win_end)
    t_vals: list[float] = []
    v_vals: list[float] = []
    for idx in range(idx_left, idx_right):
        r = records[idx]
        v = r["values"].get(channel)
        if v is not None:
            t_vals.append(r["t"])
            v_vals.append(float(v))

    return _series_from_channel_arrays(
        t_vals,
        v_vals,
        win_start,
        win_end,
        max_buckets,
        filter_outliers_3std,
        smoothing_window,
    )


def query_batch_channels(
    records: list, seconds_list: list, requests: list
) -> dict:
    """
    executes a batched query across multiple GraphCards in a single pass,
    extracting all requested channels per time-window slice in one loop.
    """
    results: dict = {}
    if not requests:
        return results

    bounds_groups: dict = {}
    for req in requests:
        if not isinstance(req, dict):
            continue
        t_start = float(req.get("tStart", -30.0))
        t_end = float(req.get("tEnd", -1.0))
        bounds_key = (t_start, t_end)
        group = bounds_groups.get(bounds_key)
        if group is None:
            w_start, w_end = _compute_window_bounds(
                seconds_list, t_start, t_end
            )
            if records and seconds_list:
                i_left = bisect.bisect_left(seconds_list, w_start)
                i_right = bisect.bisect_right(seconds_list, w_end)
            else:
                i_left, i_right = 0, 0
            group = [w_start, w_end, i_left, i_right, []]
            bounds_groups[bounds_key] = group
        group[4].append(req)

    for w_start, w_end, i_left, i_right, group_reqs in bounds_groups.values():
        if i_left >= i_right:
            for req in group_reqs:
                results[str(req.get("index", ""))] = _empty_series_result(
                    w_start, w_end
                )
            continue

        channel_arrays: dict[str, tuple[list[float], list[float]]] = {}
        for req in group_reqs:
            ch = str(req.get("channel", ""))
            if ch and ch not in channel_arrays:
                channel_arrays[ch] = ([], [])

        ch_items = list(channel_arrays.items())
        for idx in range(i_left, i_right):
            r = records[idx]
            t_val = r["t"]
            vals = r["values"]
            for ch, (ts_list, vs_list) in ch_items:
                v = vals.get(ch)
                if v is not None:
                    ts_list.append(t_val)
                    vs_list.append(float(v))

        for req in group_reqs:
            card_id = str(req.get("index", ""))
            ch = str(req.get("channel", ""))
            max_b = int(req.get("maxBuckets", 300))
            f3std = bool(req.get("filterOutliers3Std", False))
            smooth = int(req.get("smoothingWindow", 1))
            if not ch:
                results[card_id] = _empty_series_result(w_start, w_end)
            else:
                t_vals, v_vals = channel_arrays[ch]
                results[card_id] = _series_from_channel_arrays(
                    t_vals, v_vals, w_start, w_end, max_b, f3std, smooth
                )

    return results
