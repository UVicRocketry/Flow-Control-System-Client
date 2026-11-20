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
from typing import Any

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:  # pragma: no cover - stdlib fallback when numpy is absent
    np = None  # type: ignore[assignment]
    HAS_NUMPY = False

from telemetry_files import extract_flat_values

DEFAULT_MAX_LIVE_SAMPLES = 50_000


UNIT_ALIASES: dict[str, str] = {
    "kpa": "kPa",
    "psi": "psi",
    "psig": "psi",
    "psia": "psi",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "lb": "lbs",
    "lbs": "lbs",
    "pound": "lbs",
    "pounds": "lbs",
    "n": "N",
    "newton": "N",
    "newtons": "N",
    "lbf": "lbf",
    "c": "°C",
    "°c": "°C",
    "degc": "°C",
    "f": "°F",
    "°f": "°F",
    "degf": "°F",
    "k": "K",
    "kelvin": "K",
}

CATEGORY_UNITS: dict[str, list[str]] = {
    "pressure": ["kPa", "psi"],
    "mass": ["kg", "lbs"],
    "force": ["N", "lbf"],
    "temperature": ["°C", "°F", "K"],
}

UNIT_TO_CATEGORY: dict[str, str] = {
    "kPa": "pressure",
    "psi": "pressure",
    "kg": "mass",
    "lbs": "mass",
    "N": "force",
    "lbf": "force",
    "°C": "temperature",
    "°F": "temperature",
    "K": "temperature",
}

_PSI_TO_KPA = 6.8947572932
_KG_TO_LBS = 2.20462262185
_LBS_TO_KG = 0.45359237
_N_TO_LBF = 0.2248089431
_LBF_TO_N = 4.4482216153
_G0 = 9.80665

_UNIT_CONVERSION_TABLE: dict[tuple[str, str], tuple[float, float]] = {
    ("kPa", "psi"): (1.0 / _PSI_TO_KPA, 0.0),
    ("psi", "kPa"): (_PSI_TO_KPA, 0.0),
    ("kg", "lbs"): (_KG_TO_LBS, 0.0),
    ("kg", "lbf"): (_KG_TO_LBS, 0.0),
    ("lbs", "kg"): (_LBS_TO_KG, 0.0),
    ("lbf", "kg"): (_LBS_TO_KG, 0.0),
    ("lbf", "lbs"): (1.0, 0.0),
    ("lbs", "lbf"): (1.0, 0.0),
    ("N", "lbf"): (_N_TO_LBF, 0.0),
    ("N", "lbs"): (_N_TO_LBF, 0.0),
    ("lbf", "N"): (_LBF_TO_N, 0.0),
    ("lbs", "N"): (_LBF_TO_N, 0.0),
    ("N", "kg"): (1.0 / _G0, 0.0),
    ("kg", "N"): (_G0, 0.0),
    ("°C", "°F"): (1.8, 32.0),
    ("°F", "°C"): (1.0 / 1.8, -32.0 / 1.8),
    ("°C", "K"): (1.0, 273.15),
    ("K", "°C"): (1.0, -273.15),
    ("°F", "K"): (1.0 / 1.8, -32.0 / 1.8 + 273.15),
    ("K", "°F"): (1.8, -273.15 * 1.8 + 32.0),
}


def normalize_unit(unit: str | None) -> str:
    """returns canonical display unit string for known unit aliases."""
    raw = str(unit or "").strip()
    if not raw:
        return ""
    return UNIT_ALIASES.get(raw.lower(), raw)


def infer_channel_category(channel: str, csv_unit: str | None = None) -> str:
    """
    infers the physical data category ('pressure', 'mass', 'force',
    'temperature') prioritizing csv_unit when present for legacy CSVs.
    """
    ch = str(channel or "").strip().upper()
    norm_csv = normalize_unit(csv_unit)
    if norm_csv:
        if (ch in ("M_RUN_TANK", "L_RUN_TANK") or "MASS" in ch) and norm_csv in (
            "kg",
            "lbs",
            "lbf",
        ):
            return "mass"
        if norm_csv in UNIT_TO_CATEGORY:
            return UNIT_TO_CATEGORY[norm_csv]

    if ch.startswith("M_") or ch == "L_RUN_TANK" or "MASS" in ch:
        return "mass"
    if ch.startswith("P_"):
        return "pressure"
    if ch.startswith("T_"):
        return "temperature"
    if ch.startswith("L_"):
        return "force"
    return "pressure"


def allowed_units_for_channel(channel: str, csv_unit: str | None = None) -> list[str]:
    """returns valid dropdown units for the channel's physical data type."""
    category = infer_channel_category(channel, csv_unit)
    return list(CATEGORY_UNITS[category])


def default_unit_for_channel(channel: str, csv_unit: str | None = None) -> str:
    """returns the primary SI/standard unit for a channel's data type."""
    return allowed_units_for_channel(channel, csv_unit)[0]


def coerce_allowed_unit(
    channel: str, requested_unit: str | None, csv_unit: str | None = None
) -> str:
    """normalizes requested_unit and keeps it if valid for this channel."""
    allowed = allowed_units_for_channel(channel, csv_unit)
    norm = normalize_unit(requested_unit)
    if norm in allowed:
        return norm
    return allowed[0]


def get_unit_conversion_factors(
    source_unit: str | None, target_unit: str | None
) -> tuple[float, float]:
    """returns (scale, offset) so v_target = scale * v_source + offset."""
    src = normalize_unit(source_unit)
    dst = normalize_unit(target_unit)
    if not src or not dst or src == dst:
        return 1.0, 0.0
    return _UNIT_CONVERSION_TABLE.get((src, dst), (1.0, 0.0))


def apply_unit_conversion_to_series(
    series: dict, source_unit: str | None, target_unit: str | None
) -> dict:
    """transforms bucketed series points and stats from source_unit to target_unit."""
    if not series or series.get("rawCount", 0) == 0:
        return series
    scale, offset = get_unit_conversion_factors(source_unit, target_unit)
    if scale == 1.0 and offset == 0.0:
        return series

    series["vs"] = [scale * x + offset for x in series.get("vs", [])]
    series["minVs"] = [scale * x + offset for x in series.get("minVs", [])]
    series["maxVs"] = [scale * x + offset for x in series.get("maxVs", [])]
    series["min"] = scale * float(series.get("min", 0.0)) + offset
    series["max"] = scale * float(series.get("max", 0.0)) + offset
    series["mean"] = scale * float(series.get("mean", 0.0)) + offset
    series["latest"] = scale * float(series.get("latest", 0.0)) + offset
    series["std"] = abs(scale) * float(series.get("std", 0.0))
    return series


def register_channel_if_missing(
    known_channels: dict, key: str, csv_unit: str | None = None
) -> bool:
    """
    registers a newly discovered channel key with default unit and theme colour.
    returns True if a new channel was added.
    """
    if not key or key in known_channels:
        return False
    category = infer_channel_category(key, csv_unit)
    color = (
        "theme:highlight"
        if category == "pressure"
        else ("theme:neutral" if category == "temperature" else "theme:positive")
    )
    known_channels[key] = {
        "title": key.replace("_", " ").title(),
        "unit": default_unit_for_channel(key, csv_unit),
        "color": color,
    }
    return True


def format_channel_meta(
    known_channels: dict, channel: str, csv_units: dict | None = None
) -> dict:
    """returns normalized metadata dictionary including allowed_units."""
    meta = known_channels.get(channel, {})
    csv_u = (csv_units or {}).get(channel)
    allowed = allowed_units_for_channel(channel, csv_u)
    unit = coerce_allowed_unit(channel, meta.get("unit"), csv_u)
    return {
        "key": channel,
        "title": meta.get("title", channel),
        "unit": unit,
        "allowed_units": allowed,
        "color": meta.get("color", "theme:highlight"),
    }


def list_available_channels(
    known_channels: dict, csv_units: dict | None = None
) -> list:
    """returns a list of channel metadata dictionaries for QML combo boxes."""
    return [
        format_channel_meta(known_channels, key, csv_units) for key in known_channels
    ]


def _extract_ws_seconds(data_obj: dict) -> float:
    raw_sec = data_obj.get("seconds")
    if raw_sec is None:
        raw_sec = data_obj.get("uptime", data_obj.get("time", time.time()))
    try:
        return float(raw_sec)
    except (ValueError, TypeError):
        return time.time()


def _parse_ws_telemetry_obj(msg: object) -> tuple[dict, dict, float] | None:
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


def _parse_ws_telemetry_line(line: str) -> tuple[dict, dict, float] | None:
    line = line.strip()
    if not line:
        return None
    try:
        msg = json.loads(line)
    except Exception:
        return None

    return _parse_ws_telemetry_obj(msg)


def ingest_ws_telemetry_frames(
    raw_message: str | list[dict],
    known_channels: dict,
    live_records: list,
    live_seconds: list,
    live_t0: float | None,
    latest_telemetry: dict,
    max_live_samples: int = DEFAULT_MAX_LIVE_SAMPLES,
) -> tuple[bool, list, float | None, dict]:
    """
    parses incoming WebSocket text frames (supporting both single JSON packets,
    multi-line JSONL streams, or pre-parsed message dicts), appends samples to
    a bounded live_records ring buffer, and returns
    (new_channels_added, ingested_records, live_t0, latest_telemetry).
    """
    if not raw_message:
        return False, [], live_t0, latest_telemetry

    new_channels = False
    ingested_records = []

    if isinstance(raw_message, list):
        parsed_items = (_parse_ws_telemetry_obj(obj) for obj in raw_message)
    else:
        parsed_items = (
            _parse_ws_telemetry_line(line) for line in raw_message.splitlines()
        )

    for parsed in parsed_items:
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

    if max_live_samples > 0 and len(live_records) > max_live_samples:
        overflow = len(live_records) - max_live_samples
        del live_records[:overflow]
        del live_seconds[:overflow]

    return new_channels, ingested_records, live_t0, latest_telemetry


class ColumnarTelemetryBuffer:
    """
    Bounded columnar float64 storage for time-series telemetry.
    Uses numpy float64 arrays when available and falls back to Python float
    lists when numpy is absent.
    """

    def __init__(self, max_samples: int = DEFAULT_MAX_LIVE_SAMPLES):
        self.max_samples = int(max_samples)
        self._seconds: list[float] = []
        self._columns: dict[str, list[float]] = {}
        self._np_seconds: Any = None
        self._np_columns: dict[str, Any] = {}

    def clear(self) -> None:
        self._seconds.clear()
        self._columns.clear()
        self._np_seconds = None
        self._np_columns.clear()

    @property
    def seconds(self) -> list[float]:
        return self._seconds

    def _invalidate_np_cache(self) -> None:
        self._np_seconds = None
        self._np_columns.clear()

    def _trim_to_capacity(self) -> None:
        if self.max_samples <= 0 or len(self._seconds) <= self.max_samples:
            return
        overflow = len(self._seconds) - self.max_samples
        del self._seconds[:overflow]
        for vals in self._columns.values():
            del vals[:overflow]

    def append_records(self, records: list[dict]) -> None:
        """Appends `{t, values}` records into aligned columnar arrays."""
        if not records:
            return
        self._invalidate_np_cache()
        for rec in records:
            t_val = float(rec.get("t", 0.0))
            vals = rec.get("values", {})
            n_prev = len(self._seconds)
            self._seconds.append(t_val)
            for ch in vals:
                if ch not in self._columns:
                    self._columns[ch] = [math.nan] * n_prev
            for ch, col_vals in self._columns.items():
                raw = vals.get(ch)
                col_vals.append(float(raw) if raw is not None else math.nan)
        self._trim_to_capacity()

    def load_records(self, records: list[dict], seconds_list: list[float]) -> None:
        """Replaces buffer contents with a loaded dataset."""
        self.clear()
        if not records:
            return
        if len(seconds_list) == len(records):
            seeded = [
                {"t": sec, "values": rec.get("values", {})}
                for sec, rec in zip(seconds_list, records)
            ]
            self.append_records(seeded)
        else:
            self.append_records(records)

    def _resolve_channel_key(self, channel: str) -> str:
        if channel in self._columns:
            return channel
        if channel == "M_RUN_TANK" and "L_RUN_TANK" in self._columns:
            return "L_RUN_TANK"
        if channel == "L_RUN_TANK" and "M_RUN_TANK" in self._columns:
            return "M_RUN_TANK"
        return channel

    def slice_channel(
        self, channel: str, win_start: float, win_end: float
    ) -> tuple[Any, Any]:
        """Slices valid samples for `channel` within `[win_start, win_end]`."""
        key = self._resolve_channel_key(channel)
        if not self._seconds or key not in self._columns:
            return [], []

        if HAS_NUMPY and np is not None:
            if self._np_seconds is None:
                self._np_seconds = np.asarray(self._seconds, dtype=np.float64)
            col_arr = self._np_columns.get(key)
            if col_arr is None:
                col_arr = np.asarray(self._columns[key], dtype=np.float64)
                self._np_columns[key] = col_arr
            idx_l = int(np.searchsorted(self._np_seconds, win_start, side="left"))
            idx_r = int(np.searchsorted(self._np_seconds, win_end, side="right"))
            if idx_l >= idx_r:
                return [], []
            sub_t = self._np_seconds[idx_l:idx_r]
            sub_v = col_arr[idx_l:idx_r]
            finite = np.isfinite(sub_v)
            return sub_t[finite], sub_v[finite]

        idx_l = bisect.bisect_left(self._seconds, win_start)
        idx_r = bisect.bisect_right(self._seconds, win_end)
        col_list = self._columns[key]
        t_out: list[float] = []
        v_out: list[float] = []
        for idx in range(idx_l, idx_r):
            val = col_list[idx]
            if not math.isnan(val):
                t_out.append(self._seconds[idx])
                v_out.append(val)
        return t_out, v_out

    def query_series(
        self,
        channel: str,
        t_start: float,
        t_end: float,
        max_buckets: int = 300,
        filter_outliers_3std: bool = False,
        smoothing_window: int = 1,
        source_unit: str | None = None,
        target_unit: str | None = None,
    ) -> dict:
        """Queries a single channel from columnar storage with unit conversion."""
        win_start, win_end = _compute_window_bounds(self._seconds, t_start, t_end)
        if not self._seconds or not channel:
            return _empty_series_result(win_start, win_end)
        t_vals, v_vals = self.slice_channel(channel, win_start, win_end)
        series = _series_from_channel_arrays(
            t_vals,
            v_vals,
            win_start,
            win_end,
            max_buckets,
            filter_outliers_3std,
            smoothing_window,
        )
        return apply_unit_conversion_to_series(series, source_unit, target_unit)

    def query_batch(
        self, requests: list, source_units: dict[str, str] | None = None
    ) -> dict:
        """Queries multiple cards against columnar storage in one pass."""
        results: dict = {}
        if not requests:
            return results
        src_map = source_units or {}
        for req in requests:
            if not isinstance(req, dict):
                continue
            card_id = str(req.get("index", ""))
            ch = str(req.get("channel", ""))
            src_u = req.get("sourceUnit") or src_map.get(ch)
            results[card_id] = self.query_series(
                channel=ch,
                t_start=float(req.get("tStart", -30.0)),
                t_end=float(req.get("tEnd", -1.0)),
                max_buckets=int(req.get("maxBuckets", 300)),
                filter_outliers_3std=bool(req.get("filterOutliers3Std", False)),
                smoothing_window=int(req.get("smoothingWindow", 1)),
                source_unit=src_u,
                target_unit=req.get("targetUnit"),
            )
        return results


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


def _compute_mean_std(v_vals: Any) -> tuple[float, float]:
    """computes population (mean, std) for a non-empty sequence of floats."""
    if HAS_NUMPY and np is not None:
        arr = np.asarray(v_vals, dtype=np.float64)
        return float(np.mean(arr)), float(np.std(arr))
    n = len(v_vals)
    sum_v = 0.0
    sum_sq = 0.0
    for v_val in v_vals:
        sum_v += v_val
        sum_sq += v_val * v_val
    mean_v = sum_v / n
    variance = max(0.0, (sum_sq / n) - (mean_v * mean_v)) if n > 1 else 0.0
    return mean_v, math.sqrt(variance)


def _smooth_bucket_means(vs_arr: Any, smoothing_window: int) -> list[float]:
    sw = max(1, int(smoothing_window))
    if sw <= 1 or len(vs_arr) <= 1:
        return [float(x) for x in vs_arr]
    half_w = sw // 2
    n_b = len(vs_arr)
    out = []
    for i in range(n_b):
        lo = max(0, i - half_w)
        hi = min(n_b, i + half_w + 1)
        out.append(float(np.mean(vs_arr[lo:hi])))
    return out


def _series_numpy(
    t_vals: Any,
    v_vals: Any,
    win_start: float,
    win_end: float,
    max_buckets: int,
    filter_outliers_3std: bool,
    smoothing_window: int,
) -> dict:
    t_arr = np.asarray(t_vals, dtype=np.float64)
    v_arr = np.asarray(v_vals, dtype=np.float64)
    raw_n = int(v_arr.size)
    max_b = max(10, int(max_buckets))
    dt_span = max(win_end - win_start, 1e-3)
    bucket_size = dt_span / float(max_b)
    inv_bucket_size = float(max_b) / dt_span

    mean_v = float(np.mean(v_arr))
    std_v = float(np.std(v_arr))
    t_clean, v_clean = t_arr, v_arr
    clean_mean = mean_v
    if filter_outliers_3std and raw_n >= 4 and std_v > 1e-6:
        mask = np.abs(v_arr - mean_v) <= 3.0 * std_v
        if bool(np.any(mask)):
            t_clean = t_arr[mask]
            v_clean = v_arr[mask]
            clean_mean = float(np.mean(v_clean))

    b_idx = np.floor(t_clean * inv_bucket_size).astype(np.int64)
    if b_idx.size > 1 and bool(np.any(b_idx[1:] < b_idx[:-1])):
        order = np.argsort(b_idx, kind="mergesort")
        b_idx = b_idx[order]
        v_sorted = v_clean[order]
    else:
        v_sorted = v_clean

    unique_b, start_idx, counts = np.unique(
        b_idx, return_index=True, return_counts=True
    )
    ts_arr = np.clip((unique_b + 0.5) * bucket_size, win_start, win_end)
    vs_arr = np.add.reduceat(v_sorted, start_idx) / counts
    min_vs_arr = np.minimum.reduceat(v_sorted, start_idx)
    max_vs_arr = np.maximum.reduceat(v_sorted, start_idx)

    return {
        "ts": [float(x) for x in ts_arr],
        "vs": _smooth_bucket_means(vs_arr, smoothing_window),
        "minVs": [float(x) for x in min_vs_arr],
        "maxVs": [float(x) for x in max_vs_arr],
        "min": float(np.min(v_clean)),
        "max": float(np.max(v_clean)),
        "mean": clean_mean,
        "std": std_v,
        "latest": float(v_clean[-1]),
        "rawCount": raw_n,
        "filteredCount": int(v_clean.size),
        "bucketCount": int(unique_b.size),
        "tMin": win_start,
        "tMax": win_end,
    }


def _bucket_all_samples(
    t_vals: list[float],
    v_vals: list[float],
    inv_bucket_size: float,
) -> tuple[dict, float, float, float, float, float]:
    """accumulates all samples into time buckets and returns stats in a single pass."""
    raw_n = len(v_vals)
    sum_v = 0.0
    sum_sq = 0.0
    clean_min = v_vals[0]
    clean_max = v_vals[0]
    buckets: dict = {}
    floor = math.floor

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
    return buckets, clean_min, clean_max, mean_v, math.sqrt(variance), v_vals[-1]


def _bucket_filtered_samples(
    t_vals: list[float],
    v_vals: list[float],
    inv_bucket_size: float,
    mean_v: float,
    threshold: float,
) -> tuple[dict, float, float, float, float, int]:
    """accumulates samples within |v - mean_v| <= threshold into time buckets."""
    clean_sum = 0.0
    filtered_n = 0
    clean_min = math.inf
    clean_max = -math.inf
    latest_v = v_vals[-1]
    buckets: dict = {}
    floor = math.floor

    for t_val, v_val in zip(t_vals, v_vals):
        if abs(v_val - mean_v) > threshold:
            continue
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

    return buckets, clean_min, clean_max, clean_sum, latest_v, filtered_n


def _try_bucket_filtered_samples(
    t_vals: list[float],
    v_vals: list[float],
    inv_bucket_size: float,
) -> tuple[dict, float, float, float, float, float, int] | None:
    """
    attempts 3-std outlier filtering and bucketing.
    returns None if std is degenerate or all points are rejected, signaling
    the caller to fall back to unfiltered bucketing.
    """
    mean_v, std_v = _compute_mean_std(v_vals)
    if std_v <= 1e-6:
        return None

    buckets, clean_min, clean_max, clean_sum, latest_v, filtered_n = (
        _bucket_filtered_samples(t_vals, v_vals, inv_bucket_size, mean_v, 3.0 * std_v)
    )
    if filtered_n == 0:
        return None

    return (
        buckets,
        clean_min,
        clean_max,
        clean_sum / filtered_n,
        std_v,
        latest_v,
        filtered_n,
    )


def _series_from_channel_arrays(
    t_vals: Any,
    v_vals: Any,
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

    if HAS_NUMPY and np is not None:
        return _series_numpy(
            t_vals,
            v_vals,
            win_start,
            win_end,
            max_buckets,
            filter_outliers_3std,
            smoothing_window,
        )

    max_b = max(10, int(max_buckets))
    dt_span = max(win_end - win_start, 1e-3)
    bucket_size = dt_span / float(max_b)
    inv_bucket_size = float(max_b) / dt_span

    filtered = (
        _try_bucket_filtered_samples(t_vals, v_vals, inv_bucket_size)
        if filter_outliers_3std and raw_n >= 4
        else None
    )
    if filtered is not None:
        buckets, clean_min, clean_max, clean_mean, std_v, latest_v, filtered_n = (
            filtered
        )
    else:
        buckets, clean_min, clean_max, clean_mean, std_v, latest_v = (
            _bucket_all_samples(t_vals, v_vals, inv_bucket_size)
        )
        filtered_n = raw_n

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


def _resolve_record_value(values: dict, channel: str):
    val = values.get(channel)
    if val is not None:
        return val
    if channel == "M_RUN_TANK":
        return values.get("L_RUN_TANK")
    if channel == "L_RUN_TANK":
        return values.get("M_RUN_TANK")
    return None


def query_channel_series(
    records: list,
    seconds_list: list,
    channel: str,
    t_start: float,
    t_end: float,
    max_buckets: int = 300,
    filter_outliers_3std: bool = False,
    smoothing_window: int = 1,
    source_unit: str | None = None,
    target_unit: str | None = None,
) -> dict:
    """
    computes windowed, optionally 3-std outlier-filtered, fixed-timespan
    bucketed, and moving-average smoothed time-series points for a channel,
    converting from source_unit to target_unit when specified.
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
        v = _resolve_record_value(r["values"], channel)
        if v is not None:
            t_vals.append(r["t"])
            v_vals.append(float(v))

    series = _series_from_channel_arrays(
        t_vals,
        v_vals,
        win_start,
        win_end,
        max_buckets,
        filter_outliers_3std,
        smoothing_window,
    )
    return apply_unit_conversion_to_series(series, source_unit, target_unit)


def _group_requests_by_window(
    records: list, seconds_list: list, requests: list
) -> list[tuple[float, float, int, int, list[dict]]]:
    """groups batch requests by shared (tStart, tEnd) bounds and bisect slice."""
    bounds_groups: dict = {}
    for req in requests:
        if not isinstance(req, dict):
            continue
        t_start = float(req.get("tStart", -30.0))
        t_end = float(req.get("tEnd", -1.0))
        bounds_key = (t_start, t_end)
        group = bounds_groups.get(bounds_key)
        if group is None:
            w_start, w_end = _compute_window_bounds(seconds_list, t_start, t_end)
            if records and seconds_list:
                i_left = bisect.bisect_left(seconds_list, w_start)
                i_right = bisect.bisect_right(seconds_list, w_end)
            else:
                i_left, i_right = 0, 0
            group = (w_start, w_end, i_left, i_right, [])
            bounds_groups[bounds_key] = group
        group[4].append(req)
    return list(bounds_groups.values())


def _extract_window_channel_arrays(
    records: list, i_left: int, i_right: int, group_reqs: list[dict]
) -> dict[str, tuple[list[float], list[float]]]:
    """extracts (t_vals, v_vals) arrays for all channels in a slice in one pass."""
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
            v = _resolve_record_value(vals, ch)
            if v is not None:
                ts_list.append(t_val)
                vs_list.append(float(v))

    return channel_arrays


def _evaluate_window_group(
    records: list,
    w_start: float,
    w_end: float,
    i_left: int,
    i_right: int,
    group_reqs: list[dict],
    results: dict,
    source_units: dict[str, str] | None = None,
) -> None:
    """computes series results for all requests sharing a single time-window slice."""
    if i_left >= i_right:
        for req in group_reqs:
            results[str(req.get("index", ""))] = _empty_series_result(w_start, w_end)
        return

    channel_arrays = _extract_window_channel_arrays(
        records, i_left, i_right, group_reqs
    )
    src_map = source_units or {}
    for req in group_reqs:
        card_id = str(req.get("index", ""))
        ch = str(req.get("channel", ""))
        if not ch:
            results[card_id] = _empty_series_result(w_start, w_end)
            continue
        t_vals, v_vals = channel_arrays[ch]
        series = _series_from_channel_arrays(
            t_vals,
            v_vals,
            w_start,
            w_end,
            int(req.get("maxBuckets", 300)),
            bool(req.get("filterOutliers3Std", False)),
            int(req.get("smoothingWindow", 1)),
        )
        src_u = req.get("sourceUnit") or src_map.get(ch)
        tgt_u = req.get("targetUnit")
        results[card_id] = apply_unit_conversion_to_series(series, src_u, tgt_u)


def query_batch_channels(
    records: list,
    seconds_list: list,
    requests: list,
    source_units: dict[str, str] | None = None,
) -> dict:
    """
    executes a batched query across multiple GraphCards in a single pass,
    extracting all requested channels per time-window slice in one loop.
    """
    results: dict = {}
    if not requests:
        return results

    for w_start, w_end, i_left, i_right, group_reqs in _group_requests_by_window(
        records, seconds_list, requests
    ):
        _evaluate_window_group(
            records,
            w_start,
            w_end,
            i_left,
            i_right,
            group_reqs,
            results,
            source_units,
        )

    return results
