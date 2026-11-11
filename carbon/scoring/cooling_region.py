"""Cooling's official derive inside the SIGNED extended region (B5; Carbon Validator-B 11 Nov, W1-W5).

The Cooling derive (`pool_adapters._cooling`: `customer_decision.quantities` -> `exam.gates` + `exam.feasibility`) refuses
any input outside `domain.INPUT_BOUNDS`, the TRAIN box, because `exam.feasibility` and `exam.die_peak_c` call
`domain.check_inputs`. A version that scores beyond TRAIN inside its signed region (Cooling 1.8) needs that derive on the
region's EXTENDED bounds. The receipted reads did it with an in-process widen (`pfr_cool_prep.widen`:
``domain.INPUT_BOUNDS.update(region["extended"])``); the grader never writes that global (W1). Instead:

- `bounds` = ``{**domain.INPUT_BOUNDS, **region["extended"]}``: exactly widen()'s bounds, as a local value;
- `bounded_binding` returns the version's official binding with a derive that runs the SAME steps as the official one
  (the 32-value row, the decode, every law gate of `exam.gates`, then the feasibility quantities), with the input check
  against those bounds. Every law gate stays; a case outside the region still derives None (W2);
- the region document is the version's SEALED one, checked against the sha its registration names (`pool_version`), never
  typed (W1), and only a version registering one gets it (W3).

The steps are copies of `domain.check_inputs`, `exam.die_peak_c`, `exam.feasibility` and `pool_adapters._cooling`'s derive
with only the bounds changed; tests pin those sources by sha, so a change there is seen, and prove in-box rows derive
byte-equal to today's and in-region rows equal to the receipted widen() derive (W4).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math

KIND = "cooling"


class RegionRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise RegionRefused(code)


def canonical_sha256(document) -> str:
    """The region record's canonical sha256 (the receipted `pool_common.canonical`: sorted keys, no spaces)."""
    try:
        raw = json.dumps(document, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        raise RegionRefused("region_document_not_json") from None
    return hashlib.sha256(raw.encode()).hexdigest()


def bounds(document):
    """``{input: (low, high)}``: the TRAIN box with each input the region extends replaced by its extended bounds (the
    receipted widen()'s ``INPUT_BOUNDS.update(region["extended"])``, as a local value). Refuses a region that is not a
    dict with an ``extended`` dict of known inputs, each a finite pair ``low < high``.
    """
    from carbon.cold_plate import domain

    _require(type(document) is dict, "region_document_must_be_a_dict")
    extended = document.get("extended")
    _require(type(extended) is dict and extended, "region_has_no_extended_bounds")
    _require(set(extended) <= set(domain.INPUTS), "region_extends_an_unknown_input")
    out = dict(domain.INPUT_BOUNDS)
    for name, pair in extended.items():
        _require(
            type(pair) in (list, tuple)
            and len(pair) == 2
            and all(
                type(v) in (int, float) and not isinstance(v, bool) and math.isfinite(v)
                for v in pair
            )
            and pair[0] < pair[1],
            "region_bounds_malformed",
        )
        out[name] = (pair[0], pair[1])
    return out


def check_inputs(case, box):
    """`domain.check_inputs` with ``box`` in place of the module's INPUT_BOUNDS (same refusals, same floats)."""
    from carbon.cold_plate.domain import INPUTS

    if set(case) != set(INPUTS):
        raise ValueError(
            "inputs must be exactly " + ", ".join(INPUTS) + f"; got {sorted(case)}"
        )
    values = {}
    for name in INPUTS:
        value = case[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
        low, high = box[name]
        if not low <= value <= high:
            raise ValueError(f"{name}={value} is outside [{low}, {high}]")
        values[name] = float(value)
    return values


def die_peak_c(case, outputs):
    """`exam.die_peak_c` on an already checked ``case`` (its own check_inputs call is the only difference)."""
    from carbon.cold_plate.domain import (
        PROFILE_SEGMENTS,
        TIM_RESISTANCE_M2K_W,
        heat_flux,
    )

    seg = 30.0 / PROFILE_SEGMENTS
    profile = list(outputs["profile_c"])
    through_tim = max(
        t + heat_flux(case, (i + 0.5) * seg) * TIM_RESISTANCE_M2K_W
        for i, t in enumerate(profile)
    )
    return through_tim + max(0.0, outputs["peak_c"] - max(profile))


def bounded_derive(version, box):
    """The official Cooling derive (`pool_adapters._cooling`) with the input check on ``box``."""
    from carbon.cold_plate import customer_decision as decision
    from carbon.cold_plate import exam, output_encoding
    from carbon.cold_plate.domain import derived
    from carbon.scoring import pool_adapters

    encoded = pool_adapters._cooling_encoded(version)

    def derive(inputs, raw):
        row = pool_adapters._finite_row(raw)
        if row is None or len(row) != 32:
            return None
        try:
            native = output_encoding.decode_flat(row) if encoded else row
            outputs = {
                "peak_c": native[0],
                "profile_c": list(native[1:31]),
                "pressure_drop_pa": native[31],
            }
            # `decision.quantities`: every law gate first (a failed gate is no quantity), then the feasibility row
            if set(outputs) != set(exam.SHAPES):
                return None
            verdicts = exam.gates(outputs, dict(inputs))
            if any(verdict == exam.FAIL for verdict in verdicts.values()):
                return None
            case = check_inputs(dict(inputs), box)
            hydraulic = outputs["pressure_drop_pa"] * derived(case)["flow_m3_s"]
            die = die_peak_c(case, outputs)
        except (decision.DecisionError, ValueError, OverflowError):
            return None
        return {"die_peak_c": die, "hydraulic_w": hydraulic}

    return derive


def bounded_binding(binding, document):
    """``binding`` (the version's official Cooling binding) with its derive bounded by the region ``document``."""
    _require(binding.kind == KIND, "region_binding_is_cooling_only")
    return dataclasses.replace(
        binding, derive=bounded_derive(binding.version, bounds(document))
    )


__all__ = [
    "KIND",
    "RegionRefused",
    "bounded_binding",
    "bounded_derive",
    "bounds",
    "canonical_sha256",
    "check_inputs",
    "die_peak_c",
]
