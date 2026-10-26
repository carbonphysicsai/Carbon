"""Carbon-side error calibration of the current winning model, from the pool truths (CUSTODY ONLY).

OWNER-CONFIDENCE-MIDDLE-PATH-01 (spec EXAM_ADDITIONS_20261025): for Monday Carbon measures how wrong the model is,
per output, in range and out of range, from the model's one-inference table against the sealed pool truths. The
product's Envelope Guard consumes only per-region, per-output summaries, for a model the customer has the rights to.

What it is NOT:
- It is not a score input (invariant 11): it changes no grade, rank, king or emission.
- It never appears on a miner or public surface: not in grade codes, `koth_public`, the published exam, practice
  feedback, the miner guide or Launchpad. Per-row errors, pool designs, targets and seeds never leave custody; this
  module returns only region/output aggregates, labelled `custody_only`.
- It is DEVELOPMENT evidence, "measured on Carbon's sealed pool, n rows": not a qualification, not a guarantee.

Each calibration is bound to the exam version, the model state digest and the pools' digests, and is recomputed on a
new king; earlier ones are kept, never re-scored.

Errors are |predicted - true| / U per output, with U per row (a relative U is r x |that row's true value|). Regions:
"in_range" = the registered-condition targets (inside the TRAIN box, T1-T4), "out_of_range" = the extended targets
(the approved shell, T5/T6). Per output: n, the 50/90/95/99 % quantiles, the maximum, and the one-sided 95 % upper
bound on the miss rate beyond `band_u` (the Clopper-Pearson bound; about 3/n when there are no misses). A row that
fails a physics gate is counted separately and never averaged away.
"""

from __future__ import annotations

import math

SCHEMA = "carbon.pool-calibration.custody.v1"
QUANTILES = (0.5, 0.9, 0.95, 0.99)
#: Field names that must never appear on a miner or public schema (the disclosure test reads this).
CUSTODY_FIELDS = (
    "custody_only",
    "model_state_digest",
    "calibration_pool_digests",
    "miss_rate_upper_95",
    "regions",
    "band_u",
)


class CalibrationRefused(ValueError):
    """The inputs cannot give a sound calibration: a wiring fault, never a candidate's score."""


def _require(condition, reason):
    if not condition:
        raise CalibrationRefused(reason)


def quantile(sorted_values, q):
    """The q-quantile of an ascending list by linear interpolation between the closest ranks."""
    _require(sorted_values, "no_values")
    position = q * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def miss_rate_upper_95(misses, n):
    """The one-sided 95 % Clopper-Pearson upper bound on a miss rate: the p with P(X <= misses | n, p) = 0.05."""
    _require(
        type(n) is int and n > 0 and 0 <= misses <= n, "misses_and_n_must_be_valid"
    )
    if misses == n:
        return 1.0

    def cdf(p):
        total = 0.0
        for i in range(misses + 1):
            log_term = (
                math.lgamma(n + 1)
                - math.lgamma(i + 1)
                - math.lgamma(n - i + 1)
                + i * math.log(p)
                + (n - i) * math.log1p(-p)
            )
            total += math.exp(log_term)
        return total

    low, high = 0.0, 1.0
    for _ in range(80):
        mid = 0.5 * (low + high)
        if cdf(mid) > 0.05:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def calibrate_errors(
    specs, predict, *, exam_version, model_state_digest, band_u, gate_failed=None
):
    """Per-region, per-output error summaries of a model's table over EVERY pool row (queryable and A_gen).

    `predict(conditions, designs)` is the model's table (the grader's own callable); `gate_failed` optionally maps a
    target id to the set of kept-row indices whose answer fails a physics gate (counted apart, left out of the error
    statistics). Custody only: see the module docstring."""
    _require(type(exam_version) is str and exam_version, "exam_version_required")
    _require(
        type(model_state_digest) is str and model_state_digest,
        "model_state_digest_required",
    )
    _require(
        type(band_u) in (int, float) and math.isfinite(band_u) and band_u > 0,
        "band_u_must_be_positive",
    )
    _require(len(specs) >= 1, "no_pools")
    gate_failed = gate_failed or {}
    regions = {"in_range": {}, "out_of_range": {}}
    counts = {"in_range": [0, 0], "out_of_range": [0, 0]}  # rows, gate-failed rows
    errors = {"in_range": {}, "out_of_range": {}}
    for spec in specs:
        region = "out_of_range" if spec.extended else "in_range"
        indices = list(range(len(spec.designs)))
        answers = predict(spec.conditions, [list(spec.designs[i]) for i in indices])
        _require(
            type(answers) is list and len(answers) == len(indices),
            "predict_must_return_one_answer_per_row",
        )
        failed = gate_failed.get(spec.target_id, set())
        for index, answer in zip(indices, answers, strict=True):
            counts[region][0] += 1
            if index in failed:
                counts[region][1] += 1
                continue
            for name in spec.outputs:
                scale = spec.u_at(index, name)
                if scale <= 0.0:
                    continue  # an exactly computed output has no model error to calibrate
                _require(
                    name in answer and math.isfinite(answer[name]),
                    "answer_must_give_every_predicted_output",
                )
                errors[region].setdefault(name, []).append(
                    abs(answer[name] - spec.truths[index][name]) / scale
                )
    for region in regions:
        outputs = {}
        for name, values in sorted(errors[region].items()):
            ordered = sorted(values)
            misses = sum(1 for v in ordered if v > band_u)
            outputs[name] = {
                "n": len(ordered),
                "quantiles": {
                    f"p{round(q * 100)}": quantile(ordered, q) for q in QUANTILES
                },
                "max": ordered[-1],
                "misses_beyond_band": misses,
                "miss_rate_upper_95": miss_rate_upper_95(misses, len(ordered)),
            }
        regions[region] = {
            "rows": counts[region][0],
            "gate_failed_rows": counts[region][1],
            "outputs": outputs,
        }
    return {
        "schema": SCHEMA,
        "custody_only": True,
        "exam_version": exam_version,
        "model_state_digest": model_state_digest,
        "calibration_pool_digests": sorted(spec.digest for spec in specs),
        "band_u": band_u,
        "regions": regions,
        "label": "DEVELOPMENT evidence: measured on Carbon's sealed pool; not a qualification, not a guarantee",
    }
