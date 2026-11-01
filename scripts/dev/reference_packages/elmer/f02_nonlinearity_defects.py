"""The three nonlinearity defect metrics of Burst Thermal 3.0, from solved records (OWNER-F02-V3-PICKS-01, step 1).

Is the problem still (nearly) linear and separable once k(T), c_p(T) and the nine inputs are in? For each point of the input
box the dry run solves a small set of VARIANTS (the primary rung), and this module turns the recorded peaks into:

- (i) **property effect**: |peak_kT - peak_const|, the k(T)/c_p(T) solve against constant properties at the coolant
  temperature (variants ``kT`` and ``const``);
- (ii) **affine-in-power defect**: at fixed other inputs, the peak at P_mid against the linear interpolation between P_low and
  P_high (variants ``p_low``, ``p_mid``, ``p_high``, each carrying its ``power_w``);
- (iii) **superposition defect**, the largest of the available parts:
  - additivity: the peak with (coolant + d, start + d) against the base peak + d (variants ``base`` and ``shift``, the latter
    carrying ``delta_c``);
  - the split: the peak at split 0.5 against the mean of the split-0 and split-1 peaks (``split_0``, ``split_05``,
    ``split_1``);
  - the two-pulse response against the sum of the shifted single-pulse responses (``two_pulse`` with its ``series`` and
    ``single`` series each carrying ``shift_s``; the sum is taken on the two-pulse series' own time axis, from the common
    start temperature ``start_c``). This part needs the solved time series and is skipped when they are absent.

Each metric is reported in degrees C and as a multiple of U (the reference uncertainty, a REQUIRED argument: it is the
Validator's, 0.012 C for 2.5, and is not defaulted here). The decision rule (``too_weak``) compares max(ii, iii) over the box
with a threshold that is the owner's to sign and is also a required argument. Nothing here is a score or a gate.

A record is ``{"point": id, "variant": name, "peak_c": value, ...}``; the extra keys are named above.
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict

SCHEMA = "carbon.f02.nonlinearity-defects.v1"
METRICS = ("property_effect", "affine_in_power", "superposition")


class DefectInputRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _finite(value, code):
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
    ):
        raise DefectInputRefused(code)
    return float(value)


def _by_point(records):
    points = defaultdict(dict)
    for record in records:
        if type(record) is not dict or {"point", "variant", "peak_c"} - set(record):
            raise DefectInputRefused("record_incomplete")
        _finite(record["peak_c"], "record_peak")
        if record["variant"] in points[record["point"]]:
            raise DefectInputRefused("record_duplicated")
        points[record["point"]][record["variant"]] = record
    return points


def _interp(series, t):
    """Linear interpolation of ``[(t, value), ...]`` (flat outside the series)."""
    if t <= series[0][0]:
        return series[0][1]
    for (ta, va), (tb, vb) in itertools.pairwise(series):
        if t <= tb:
            return va + (vb - va) * (t - ta) / (tb - ta)
    return series[-1][1]


def property_effect(variants):
    if {"kT", "const"} <= set(variants):
        return abs(variants["kT"]["peak_c"] - variants["const"]["peak_c"])
    return None


def affine_defect(variants):
    if not {"p_low", "p_mid", "p_high"} <= set(variants):
        return None
    low, mid, high = (variants[v] for v in ("p_low", "p_mid", "p_high"))
    p_low, p_mid, p_high = (
        _finite(r.get("power_w"), "record_power") for r in (low, mid, high)
    )
    if not p_low < p_mid < p_high:
        raise DefectInputRefused("record_power_order")
    line = low["peak_c"] + (high["peak_c"] - low["peak_c"]) * (p_mid - p_low) / (
        p_high - p_low
    )
    return abs(mid["peak_c"] - line)


def superposition_parts(variants):
    """``{part: defect_c}`` for the parts these variants allow."""
    parts = {}
    if {"base", "shift"} <= set(variants):
        delta = _finite(variants["shift"].get("delta_c"), "record_delta")
        parts["additivity"] = abs(
            variants["shift"]["peak_c"] - (variants["base"]["peak_c"] + delta)
        )
    if {"split_0", "split_05", "split_1"} <= set(variants):
        mean = (variants["split_0"]["peak_c"] + variants["split_1"]["peak_c"]) / 2
        parts["split"] = abs(variants["split_05"]["peak_c"] - mean)
    two = variants.get("two_pulse")
    if two is not None and two.get("series") and two.get("singles"):
        start = _finite(two.get("start_c"), "record_start")
        series = [tuple(map(float, row)) for row in two["series"]]
        predicted = []
        for t, _ in series:
            total = start
            for single in two["singles"]:
                shift = _finite(single.get("shift_s"), "record_shift")
                rows = [tuple(map(float, row)) for row in single["series"]]
                total += _interp(rows, t - shift) - start
            predicted.append(total)
        parts["two_pulse"] = abs(two["peak_c"] - max(predicted))
    return parts


def defects(records, *, u):
    """Per point and over the box: each metric in C and as a multiple of ``u``.

    Returns ``{"schema", "u", "points": {id: {metric: {"c", "u_multiple"}}}, "max": {metric: {...}}}``; a metric a point has
    no variants for is absent for that point."""
    u = _finite(u, "u_required")
    if not u > 0:
        raise DefectInputRefused("u_required")
    points, worst = {}, {}
    for point, variants in sorted(_by_point(records).items()):
        row = {}
        found = {
            "property_effect": property_effect(variants),
            "affine_in_power": affine_defect(variants),
        }
        parts = superposition_parts(variants)
        if parts:
            found["superposition"] = max(parts.values())
            row["superposition_parts"] = {
                k: {"c": v, "u_multiple": v / u} for k, v in sorted(parts.items())
            }
        for metric, value in found.items():
            if value is None:
                continue
            row[metric] = {"c": value, "u_multiple": value / u}
            if metric not in worst or value > worst[metric]["c"]:
                worst[metric] = {"c": value, "u_multiple": value / u, "point": point}
        points[point] = row
    return {"schema": SCHEMA, "u": u, "points": points, "max": worst}


def too_weak(result, *, threshold_c):
    """The decision rule: the nonlinearity is TOO WEAK when max(affine-in-power, superposition) over the box is below
    ``threshold_c`` (the owner's number; no default). None when neither metric was measured.
    """
    threshold = _finite(threshold_c, "threshold_required")
    seen = [
        result["max"][m]["c"]
        for m in ("affine_in_power", "superposition")
        if m in result["max"]
    ]
    if not seen:
        return None
    return max(seen) < threshold
