"""The signed slack of each per-answer physics gate, and the pool's near-limit design counts (the gate-margin card, operator-side).

CUSTODY / SCRATCH only (the Q8 read of `q3_q8_whatif.py`): nothing here is imported by a grader, and no live gate changes. The
live gates give names and verdicts only (`pool_adapters.physics_gates`); this module reads, for the SAME answer, the quantity each
gate tests and the threshold it tests it against, using the gate's own helpers and constants (`carbon.motor.exam`,
`carbon.cold_plate.exam`, `f02_physics`, `f08_physics`, `pool_adapters`), and STOPS on any answer whose slack sign disagrees
with the live verdict (`SlackParity`).

Per gate (Validator rulings, 1 Nov):
- the RAW signed slack, in the gate's own unit, is always reported (slack >= 0 passes; a STRICT gate, ``>``, passes at > 0);
- the normalised margin m = slack / scale ONLY for a law that carries a REGISTERED scale (Validator correction: these laws
  compare against the answer's own values or inputs, several on an interval scale such as degC, so dividing by the
  threshold is not meaningful). Today that is Motor's motoring_mean_nonnegative, whose scale is its registered allowance.
  Every other law reports its raw slack and "no registered scale" (its near band is "unscaled");
- a gate with no continuous quantity (the schema / finite gates) reports no margin.

The near-limit counts (`near_limit_counts`) are the pool's own: per feasibility limit (`pool_grader.Limit.margin`) and region
class, the kept pool designs whose TRUE output is within +-U and +-3U of the limit, with U the target's registered
`u_at` (a relative U is relative to the true value). Counts only: never a design, a value or a target.
"""

from __future__ import annotations

import math
import statistics

#: The near-gate band on m (the Q8 spec).
NEAR = 0.10
#: The schema gate of each kind: an answer failing it carries no other gate (the live gates skip the laws then).
SCHEMA = {
    "motor": "schema_finite",
    "cooling": "schema_finite",
    "f02": "finite_peak",
    "f08": "finite_native_summary",
}


class SlackParity(ValueError):
    """A slack whose sign disagrees with the live gate's verdict on the same answer: the read is not the gate's; STOP."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _law(slack, threshold, strict=False, scale=None):
    """One law's reading: its signed slack, the threshold it is compared with (informational), strictness, and its
    REGISTERED scale (None when the law has none)."""
    return {
        "slack": float(slack),
        "threshold": float(threshold),
        "strict": strict,
        "scale": None if scale is None else float(scale),
    }


def _motor(_version, _inputs, raw):
    from carbon.motor import exam

    curve = exam._curve({"torque_nm": list(raw)})
    if curve is None:
        return {}
    allowance = (
        exam.MEAN_ALLOWANCE_REL * max(abs(t) for t in curve)
        + exam.MEAN_ALLOWANCE_FLOOR_NM
    )
    # the gate: mean(torque) >= -allowance
    return {
        "motoring_mean_nonnegative": _law(
            statistics.fmean(curve) + allowance, -allowance, scale=allowance
        )
    }


def _cooling(version, inputs, raw):
    from carbon.cold_plate import exam, output_encoding
    from carbon.scoring import pool_adapters

    row = pool_adapters._finite_row(raw)
    if row is None or len(row) != 32:
        return {}
    native = (
        output_encoding.decode_flat(row)
        if pool_adapters._cooling_encoded(version)
        else row
    )
    prediction = {
        "peak_c": native[0],
        "profile_c": list(native[1:31]),
        "pressure_drop_pa": native[31],
    }
    if not exam._finite_shape(prediction):
        return {}
    profile = exam._values(prediction, "profile_c")
    peak = float(prediction["peak_c"])
    inlet = dict(inputs)["inlet_c"]
    bound = max(profile) - exam._ulp(max(profile))
    return {
        # min(profile) > inlet
        "face_above_inlet": _law(min(profile) - inlet, inlet, strict=True),
        # peak >= max(profile) - ulp(max(profile))
        "peak_bounds_profile": _law(peak - bound, bound),
        # pressure_drop > 0
        "pressure_drop_positive": _law(
            float(prediction["pressure_drop_pa"]), 0.0, strict=True
        ),
    }


def _f02(_version, _inputs, raw):
    from carbon.scoring import f02_physics, pool_adapters

    row = pool_adapters._finite_row(raw)
    if row is None or len(row) != 1:
        return {}
    # peak >= INITIAL_C
    return {
        "peak_not_below_initial": _law(
            row[0] - f02_physics.INITIAL_C, f02_physics.INITIAL_C
        )
    }


def _f08(version, _inputs, raw):
    from carbon.scoring import f08_dual_measurement, f08_dual_pack, pool_adapters

    targets = list(f08_dual_pack._targets(version))
    rule = f08_dual_measurement.SANITY_RULE if version == "1.7" else None
    row = pool_adapters._finite_row(raw)
    if row is None or not f08_dual_measurement.native_summary(
        row,
        targets=targets,
        frequency_targets=f08_dual_pack._FREQUENCIES,
        frequency_band_hz=f08_dual_pack._MEASUREMENT["frequency_band_hz"],
        rule=rule,
    ):
        return {}
    named = dict(zip(targets, row, strict=True))
    peaks = [
        named["peak_tip_z005_mm_per_n"],
        named["peak_tip_z010_mm_per_n"],
        named["peak_tip_z020_mm_per_n"],
    ]
    static = named["static_tip_mm_per_n"]
    # every peak >= static; peaks[0] >= peaks[1] >= peaks[2] (the tightest pair is the slack, its lower side the threshold)
    pairs = [(peaks[0] - peaks[1], peaks[1]), (peaks[1] - peaks[2], peaks[2])]
    ordered = min(pairs, key=lambda p: p[0])
    return {
        "peak_not_below_static": _law(min(peaks) - static, static),
        "peaks_ordered_by_damping": _law(ordered[0], ordered[1]),
    }


_KINDS = {"motor": _motor, "cooling": _cooling, "f02": _f02, "f08": _f08}


def margin(law):
    """m = slack / the law's registered scale, or None when it carries none ("no registered scale")."""
    return None if law["scale"] is None else law["slack"] / law["scale"]


def passes(law):
    return law["slack"] > 0 if law["strict"] else law["slack"] >= 0


def answer_laws(gates, inputs, raw):
    """``{law: {"slack", "threshold", "strict", "scale"}}`` for one pool answer of the Challenge whose live `PhysicsGates` is
    ``gates``, after checking each law's sign against the live verdict on the same answer (`SlackParity` on a mismatch).
    """
    failed = set(gates.failed(inputs, list(raw)))
    laws = _KINDS[gates.kind](gates.version, inputs, raw)
    schema = SCHEMA[gates.kind]
    if not laws:
        if schema not in failed:
            raise SlackParity(f"gate_slack_parity:{schema}")
        return {}
    if schema in failed or set(laws) | {schema} != set(gates.gate_names):
        raise SlackParity("gate_slack_parity:gate_names")
    for name, law in laws.items():
        if passes(law) == (name in failed) or not math.isfinite(law["slack"]):
            raise SlackParity(f"gate_slack_parity:{name}")
    return laws


def entry_summary(gates, rows, raw_rows):
    """One entry's physics_pool laws over EVERY pool answer it gave (``rows`` / ``raw_rows`` exactly as
    `pool_gates.failed_gates` receives them): per law, the minimum raw slack, the minimum m (None where the law has no
    scale), and the answer counts per band. Aggregates only."""
    out = {name: None for name in gates.gate_names if name != SCHEMA[gates.kind]}
    schema_failed = 0
    for row, raw in zip(rows, raw_rows, strict=True):
        laws = answer_laws(gates, row["inputs"], raw)
        if not laws:
            schema_failed += 1
            continue
        for name, law in laws.items():
            m = margin(law)
            held = out[name] or {
                "slack_min": math.inf,
                "m_min": math.inf,
                "answers": 0,
                "fail": 0,
                "near": 0,
                "unscaled": 0,
            }
            held["answers"] += 1
            held["slack_min"] = min(held["slack_min"], law["slack"])
            if not passes(law):
                held["fail"] += 1
            if m is None:
                held["unscaled"] += 1
            else:
                held["m_min"] = min(held["m_min"], m)
                if passes(law) and m < NEAR:
                    held["near"] += 1
            out[name] = held
    for name, held in out.items():
        if held is not None and held["m_min"] == math.inf:
            held["m_min"] = None  # no answer of this law has a scale
    return {"schema_failed": schema_failed, "laws": out}


def physics_pool_m(summary):
    """The entry's physics_pool m: the minimum m over its laws and answers, or None when any law it answered has no
    registered scale (a law with no scale could fail where every scaled one passes)."""
    laws = [held for held in summary["laws"].values() if held is not None]
    if summary["schema_failed"] or not laws or any(h["unscaled"] for h in laws):
        return None
    return min(h["m_min"] for h in laws)


def near_limit_counts(specs, region_class):
    """Per feasibility limit (``"<output> <kind> <bound>"``) and region class: how many kept pool designs have a TRUE
    output within +-U and +-3U of the limit (U = the target's registered `u_at`), with a total per limit. Also the designs
    the build itself excluded for a margin within U (`TargetSpec.excluded`), per class. Counts only.
    """
    out, excluded = {}, {}
    for spec in specs:
        cls = region_class(spec)
        excluded[cls] = excluded.get(cls, 0) + spec.excluded
        for limit in spec.limits:
            key = f"{limit.output} {limit.kind} {limit.bound!r}"
            per = out.setdefault(key, {})
            for group in (cls, "total"):
                per.setdefault(group, {"designs": 0, "within_u": 0, "within_3u": 0})
            for index, truth in enumerate(spec.truths):
                distance = abs(limit.margin(truth[limit.output]))
                u = spec.u_at(index, limit.output)
                for group in (cls, "total"):
                    per[group]["designs"] += 1
                    per[group]["within_u"] += distance <= u
                    per[group]["within_3u"] += distance <= 3 * u
    return {"limits": out, "excluded_at_build": excluded}
