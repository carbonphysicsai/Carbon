"""Executable readiness controls, not scientific qualification or host evidence.

The first controls wrap existing public registration checks. All other items
stay UNCONTROLLED. No private panel, provider, shell or host probe is opened.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
import math
import re
from dataclasses import dataclass
from pathlib import Path

from .model import FAIL, PASS, Result, digest, file_digest

UNCONTROLLED = "UNCONTROLLED"
CONTROL_FAILED = "CONTROL_FAILED"
CONTROL_OK = "CONTROL_OK"
_PIN = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _pinned(value):
    return type(value) is str and _PIN.fullmatch(value) is not None


@dataclass(frozen=True)
class Control:
    check: str
    mutation: str
    reason: str
    property: str
    measurement_kind: str

    def __post_init__(self):
        if self.measurement_kind not in ("STRUCTURAL", "NUMERICAL"):
            raise ValueError("control_measurement_kind_must_be_explicit")


# Add a control only with an actual refusal and a corresponding positive path.
# A test pins this registry to the item/check binding; no generic error counts.
CONTROLS = {
    "P1": Control(
        "registered_l0",
        "unregistered_challenge",
        "the challenge is not in the registry",
        "An unregistered identity cannot resolve the construction path.",
        "STRUCTURAL",
    ),
    "P2": Control(
        "scoring_registered",
        "missing_adapter",
        "no Interface v1 validator adapter is recorded",
        "Scoring alone cannot compensate for a missing validator adapter.",
        "STRUCTURAL",
    ),
    "A4": Control(
        "admission_controller",
        "unregistered_challenge",
        "no admission controller is designated",
        "An identity with no controller designation cannot pass A4.",
        "STRUCTURAL",
    ),
}


def measurement_summary(document=None):
    """Aggregate-only diagnostics: margins and noise must share a named unit.

    No new tolerance or noise estimate is chosen. Missing metadata cannot earn
    a noise-resolved pass. This function never reads a panel or adjudicates
    physical adequacy; a source digest is a binding, not scientific approval.
    """
    empty = {
        "checked_count": 0,
        "minimum": None,
        "p01": None,
        "unit": None,
        "noise_estimate": None,
        "noise_unit": None,
        "source_digest": None,
        "noise_source_digest": None,
        "status": "HUMAN_INPUT",
    }
    if document is None:
        return empty
    if type(document) is not dict or document.get("scope") not in (
        "SYNTHETIC_FIXTURE",
        "PUBLIC_DEVELOPMENT",
    ):
        raise ValueError("measurement_scope_must_be_public_or_synthetic")
    values = document.get("margins")
    unit = document.get("unit")
    if (
        type(values) is not list
        or not values
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in values)
        or type(unit) is not str
        or unit.strip() in ("", "HUMAN_INPUT")
        or not _pinned(document.get("source_digest"))
    ):
        raise ValueError("margin_values_or_unit_missing")
    ordered = sorted(values)
    index = (len(ordered) - 1) * 0.01
    lower, upper = math.floor(index), math.ceil(index)
    fraction = index - lower
    quantile = (1 - fraction) * ordered[lower] + fraction * ordered[upper]
    if not math.isfinite(quantile):
        raise ValueError("margin_quantile_not_finite")
    out = {
        **empty,
        "checked_count": len(values),
        "minimum": min(values),
        "p01": quantile,
        "unit": unit,
        "source_digest": document.get("source_digest"),
        "scope": document["scope"],
    }
    noise = document.get("noise_estimate")
    if noise is None:
        return out
    if (
        type(noise) not in (int, float)
        or not math.isfinite(noise)
        or noise < 0
        or document.get("noise_unit") != unit
        or not _pinned(document.get("noise_source_digest"))
    ):
        raise ValueError("noise_unit_or_provenance_invalid")
    out.update(
        noise_estimate=noise,
        noise_unit=unit,
        noise_source_digest=document["noise_source_digest"],
        status=("WITHIN_NOISE" if out["minimum"] <= noise else "ABOVE_NOISE"),
    )
    return out


def _call(function, item, ctx):
    try:
        result = function(item, ctx)
    except Exception as error:  # noqa: BLE001 - infrastructure is not detection
        return {"status": "ERROR", "detail": type(error).__name__}
    if not isinstance(result, Result) or type(result.detail) is not str:
        return {"status": "ERROR", "detail": "check_did_not_return_Result"}
    return {"status": result.status, "detail": result.detail}


def evaluate(item, ctx, function, measurement=None):
    """Exercise BOTH signs through the supplied live registered checker.

    The positive specimen is the current public context, not an asserted PASS.
    A missing prerequisite on it reports NO_POSITIVE_WITNESS; a caught error on
    the bad specimen is CONTROL_FAILED, not successful refusal.
    """
    base = {
        "status": UNCONTROLLED,
        "scope": "PUBLIC_REGISTRATION_ONLY",
        "checked_count": 0,
        "positive": None,
        "negative": None,
        "spec_digest": None,
        "specimen_digest": None,
        "checker_digest": None,
        "control_code_digest": file_digest(__file__),
        "measurement": measurement_summary(),
        "detail": "No executable control registered; owner: Carbon Validator.",
    }
    if measurement is not None:
        try:
            base["measurement"] = measurement_summary(measurement)
        except ValueError as error:
            return {**base, "status": CONTROL_FAILED, "detail": str(error)}
    spec = CONTROLS.get(item["id"])
    if spec is None:
        return base
    if spec.check != item["check"] or function is None:
        return {**base, "status": CONTROL_FAILED, "detail": "control_binding_mismatch"}
    # These checks read public code/registration only. A context cannot carry
    # producer paths or a cache populated by another item into either sign.
    positive_ctx = dataclasses.replace(
        ctx, data=copy.deepcopy(ctx.data), cache={}, evidence_paths={}
    )
    data = copy.deepcopy(ctx.data)
    challenge = ctx.challenge
    if spec.mutation == "unregistered_challenge":
        challenge = "negative-control-unregistered"
    elif spec.mutation == "missing_adapter":
        data.pop("validator_adapter", None)
    else:
        return {**base, "status": CONTROL_FAILED, "detail": "control_mutation_unknown"}
    negative_ctx = dataclasses.replace(
        positive_ctx, challenge=challenge, data=data, cache={}, evidence_paths={}
    )
    try:
        source = inspect.getsourcefile(function)
        if source is None:
            raise ValueError("checker_source_missing")
        pin = file_digest(Path(source))
    except (OSError, TypeError, ValueError):
        return {**base, "status": CONTROL_FAILED, "detail": "checker_source_unpinned"}
    specimen_pin = digest({"challenge": challenge, "level": ctx.level, "data": data})
    positive = _call(function, item, positive_ctx)
    negative = _call(function, item, negative_ctx)
    detected = negative["status"] == FAIL and spec.reason in negative["detail"]
    if not detected:
        status, detail = CONTROL_FAILED, "bad_specimen_not_refused_for_expected_reason"
    elif positive["status"] != PASS:
        status, detail = UNCONTROLLED, "NO_POSITIVE_WITNESS: current input did not pass"
    else:
        status, detail = CONTROL_OK, spec.property
    return {
        **base,
        "status": status,
        "checked_count": 2,
        "positive": positive,
        "negative": negative,
        "spec_digest": digest(dataclasses.asdict(spec)),
        "specimen_digest": specimen_pin,
        "checker_digest": pin,
        "measurement": (
            measurement_summary(measurement)
            if measurement is not None or spec.measurement_kind == "NUMERICAL"
            else {
                **measurement_summary(),
                "status": "NONSCALAR_STRUCTURAL_CHECK",
                "definition_owner": "Carbon Validator",
                "reason": "No physical scalar margin/noise is defined; not zero noise.",
            }
        ),
        "detail": detail,
    }


def controlled_status(original, control):
    if original != PASS:
        return original
    if control["status"] == CONTROL_OK:
        measurement = control["measurement"]
        if measurement["status"] in ("WITHIN_NOISE", "HUMAN_INPUT"):
            return measurement["status"]
        return PASS
    return control["status"]


def summary(rows):
    passing = sum(row["controlled_status"] == PASS for row in rows)
    return {
        "checked_items": len(rows),
        "passing_items": passing,
        "uncontrolled_items": sum(
            row["control"]["status"] == UNCONTROLLED for row in rows
        ),
        "control_failed_items": sum(
            row["control"]["status"] == CONTROL_FAILED for row in rows
        ),
        "control_specimens_checked": sum(
            row["control"]["checked_count"] for row in rows
        ),
    }
