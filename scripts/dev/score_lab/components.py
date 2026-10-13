"""Optional toy score components for OPT-15c; every weight is caller supplied.

These wrappers operate on the existing Validator candidate call shape and
receive scoring-side references only. They select no production score rule.
"""

from __future__ import annotations

import math
import statistics

from .core import LabRefused

COMPONENT_KEYS = frozenset(
    ("crps_weight", "gradient_weight", "cvar_tail_fraction", "cheap_margin_weight")
)


def _weight(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise LabRefused("component_weight")
    return float(value)


def _score(result):
    if result is None or result.get("score") is None:
        return None
    value = result["score"]
    if type(value) not in (int, float) or not math.isfinite(value):
        raise LabRefused("component_score_nonfinite")
    return float(value)


def with_cheap_margin(rule, *, weight):
    """Blend the base score with gain above the registered cheap arm."""
    weight = _weight(weight)
    if weight > 1:
        raise LabRefused("component_cheap_margin_weight")

    def wrapped(predictions, references, metadata):
        cheap = metadata.get("cheap_predictions")
        if not isinstance(cheap, dict) or set(cheap) != set(references):
            return None
        candidate = rule(predictions, references, metadata)
        baseline = rule(cheap, references, metadata)
        a, b = _score(candidate), _score(baseline)
        if a is None or b is None or baseline.get("gate") == "FAIL":
            return None
        return {**candidate, "score": (1 - weight) * a + weight * max(0.0, a - b)}

    return wrapped


def gaussian_crps(mean, sigma, truth):
    """Proper Gaussian CRPS, with a point-mass limit at zero uncertainty."""
    if any(
        type(x) not in (int, float) or not math.isfinite(x)
        for x in (mean, sigma, truth)
    ):
        raise LabRefused("component_crps_input")
    if sigma < 0:
        raise LabRefused("component_crps_input")
    if sigma == 0:
        return abs(mean - truth)
    z = (truth - mean) / sigma
    cdf = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    density = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    return sigma * (z * (2 * cdf - 1) + 2 * density - 1 / math.sqrt(math.pi))


def with_crps(rule, *, weight):
    """Penalise objective distribution error on resolved score-side cells."""
    weight = _weight(weight)

    def wrapped(predictions, references, metadata):
        result = rule(predictions, references, metadata)
        base = _score(result)
        if base is None:
            return None
        values = []
        for qid, actions in references.items():
            if qid not in predictions:
                return None
            for aid, ref in actions.items():
                if (
                    ref["status"] not in ("FEASIBLE", "INFEASIBLE")
                    or ref.get("objective") is None
                ):
                    continue
                pred = predictions[qid].get(aid)
                if not isinstance(pred, dict) or "sigma" not in pred:
                    return None
                values.append(
                    gaussian_crps(pred["objective"], pred["sigma"], ref["objective"])
                )
        if not values:
            return None
        return {**result, "score": base - weight * statistics.fmean(values)}

    return wrapped


def with_gradient_sign(rule, *, weight):
    """Penalise wrong finite-difference signs on registered score-side probes."""
    weight = _weight(weight)

    def wrapped(predictions, references, metadata):
        result = rule(predictions, references, metadata)
        base = _score(result)
        if base is None:
            return None
        probes = metadata.get("probes")
        if not isinstance(probes, list) or not probes:
            return None
        wrong = 0
        for qid, lo, hi, expected in probes:
            if (
                qid not in references
                or qid not in predictions
                or expected not in (-1, 1)
            ):
                raise LabRefused("component_gradient_probe")
            pair = predictions[qid]
            if lo not in pair or hi not in pair:
                return None
            change = pair[hi]["objective"] - pair[lo]["objective"]
            if type(change) not in (int, float) or not math.isfinite(change):
                raise LabRefused("component_gradient_probe")
            wrong += change * expected <= 0
        return {**result, "score": base - weight * wrong / len(probes)}

    return wrapped


def with_cvar(rule, *, tail_fraction):
    """Aggregate worst per-question rule scores; refuse nondecomposable rules."""
    if (
        type(tail_fraction) not in (int, float)
        or not math.isfinite(tail_fraction)
        or not 0 < tail_fraction <= 1
    ):
        raise LabRefused("component_cvar_fraction")

    def wrapped(predictions, references, metadata):
        scores = []
        gates = []
        for qid, row in references.items():
            if qid not in predictions:
                return None
            one_metadata = {**metadata, "questions": {qid: metadata["questions"][qid]}}
            one_metadata["probes"] = [
                p for p in metadata.get("probes", []) if p[0] == qid
            ]
            if "cheap_predictions" in metadata:
                one_metadata["cheap_predictions"] = {
                    qid: metadata["cheap_predictions"][qid]
                }
            result = rule({qid: predictions[qid]}, {qid: row}, one_metadata)
            value = _score(result)
            if value is None:
                return None
            scores.append(value)
            gates.append(result.get("gate"))
        if not scores:
            return None
        tail = max(1, math.ceil(tail_fraction * len(scores)))
        return {
            "score": statistics.fmean(sorted(scores)[:tail]),
            "gate": "FAIL" if "FAIL" in gates else "PASS",
            "detail": {"tail_questions": tail, "total_questions": len(scores)},
        }

    return wrapped


def compose(rule, spec):
    """Compose toy-only levers in a fixed order, with every setting explicit."""
    if not isinstance(spec, dict) or not spec or set(spec) - COMPONENT_KEYS:
        raise LabRefused("component_spec")
    if "crps_weight" in spec:
        rule = with_crps(rule, weight=spec["crps_weight"])
    if "gradient_weight" in spec:
        rule = with_gradient_sign(rule, weight=spec["gradient_weight"])
    if "cvar_tail_fraction" in spec:
        rule = with_cvar(rule, tail_fraction=spec["cvar_tail_fraction"])
    if "cheap_margin_weight" in spec:
        rule = with_cheap_margin(rule, weight=spec["cheap_margin_weight"])
    return rule
