"""Validated, immutable DEVELOPMENT Guard inputs; no scientific registry."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from types import MappingProxyType

from carbon.challenge_validator import validity
from carbon.trust_map.acceptance import AcceptanceRefused, load_acceptance
from carbon.trust_map.core import MAP_SCHEMA

CONTRACT_SCHEMA = "carbon.product.guard-contract.v2"
ENVELOPE_SCHEMA = "carbon.product.guard-envelope.v1"
POLICY_SCHEMA = "carbon.product.guard-policy.v2"
REFERENCE_SCHEMA = "carbon.product.guard-reference.v3"
PRIMITIVES = {"bound", "initial_condition", "prefix_invariance"}


class GuardConfigurationError(ValueError):
    """Configuration refused with a fixed code, never an input/exception echo."""


def require(condition, code):
    if not condition:
        raise GuardConfigurationError(code)


def number(value, *, nonnegative=False):
    require(type(value) in (int, float), "finite_number_required")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise GuardConfigurationError("finite_number_required") from None
    require(math.isfinite(value), "finite_number_required")
    require(not nonnegative or value >= 0, "nonnegative_number_required")
    return value


def count(value, low=0, high=1_000_000):
    require(type(value) is int and low <= value <= high, "bounded_count_required")
    return value


def token(value):
    require(
        type(value) is str
        and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,95}", value) is not None,
        "token_required",
    )
    return value


def sha(value):
    require(
        type(value) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None,
        "digest_required",
    )
    return value


def unit(value):
    require(
        type(value) is str
        and re.fullmatch(r"[\w°µ·*/^ .%()+-]{1,60}", value) is not None,
        "unit_required",
    )
    return value


def closed(value, fields):
    require(type(value) is dict and set(value) == set(fields), "closed_shape_required")


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise GuardConfigurationError("plain_finite_data_required") from None


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def snapshot(value):
    encoded = canonical(value)
    require(len(encoded) <= 2_000_000, "configuration_size_limit")
    try:
        return json.loads(encoded)
    except (ValueError, RecursionError):
        raise GuardConfigurationError("plain_finite_data_required") from None


def freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(freeze(item) for item in value)
    return value


def thaw(value):
    """Copy validated frozen data for a receipt; never expose configured state."""
    if isinstance(value, MappingProxyType):
        return {key: thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [thaw(item) for item in value]
    return value


def header(value, schema, fields):
    closed(value, {"schema", "scope", "version", *fields})
    require(value["schema"] == schema, "schema_mismatch")
    require(value["scope"] == "DEVELOPMENT", "development_only")
    token(value["version"])


def envelope(raw):
    value = snapshot(raw)
    header(value, ENVELOPE_SCHEMA, {"inputs"})
    inputs = value["inputs"]
    require(type(inputs) is dict and 1 <= len(inputs) <= 16, "inputs_required")
    for name, bounds in inputs.items():
        token(name)
        closed(bounds, {"low", "high", "unit"})
        low, high = number(bounds["low"]), number(bounds["high"])
        require(low < high and math.isfinite(high - low), "envelope_bounds_invalid")
        bounds.update(low=low, high=high)
        unit(bounds["unit"])
    return value


def declaration(raw, names):
    """Reuse native semantics with a checked snapshot, not mutable host data."""
    if isinstance(raw, validity.Undeclared):
        require(
            type(raw.reason) is str
            and bool(raw.reason.strip())
            and type(raw.owner) is str
            and bool(raw.owner.strip()),
            "validity_owner_required",
        )
        return validity.Undeclared(raw.reason, raw.owner)
    if isinstance(raw, validity.NoPropertyModel):
        require(
            type(raw.reason) is str and bool(raw.reason.strip()),
            "validity_basis_required",
        )
        return validity.NoPropertyModel(raw.reason)
    require(isinstance(raw, validity.Declared), "validity_declaration_required")
    models = []
    for model in raw.models:
        token(model.name)
        require(
            type(model.source) is str and bool(model.source.strip()),
            "validity_source_required",
        )
        quantities = []
        for name, low, high in model.quantities:
            require(name in names, "validity_observation_not_in_query")
            low = None if low is None else number(low)
            high = None if high is None else number(high)
            require(low is not None or high is not None, "validity_range_required")
            quantities.append((name, low, high))
        try:
            models.append(
                validity.ValidityModel(model.name, tuple(quantities), model.source)
            )
        except (ValueError, TypeError):
            raise GuardConfigurationError("validity_declaration_invalid") from None
    require(bool(models), "validity_declaration_required")
    return validity.Declared(tuple(models))


def declaration_body(value):
    if isinstance(value, validity.Declared):
        return {
            "kind": "Declared",
            "models": [
                {"name": m.name, "quantities": m.quantities, "source": m.source}
                for m in value.models
            ],
        }
    if isinstance(value, validity.Undeclared):
        return {"kind": "Undeclared", "reason": value.reason, "owner": value.owner}
    return {"kind": "NoPropertyModel", "reason": value.reason}


def contract(raw, inputs):
    value = snapshot(raw)
    header(
        value,
        CONTRACT_SCHEMA,
        {"challenge", "family", "reference_image", "outputs", "laws"},
    )
    token(value["challenge"])
    token(value["family"])
    sha(value["reference_image"])
    outputs = value["outputs"]
    require(type(outputs) is dict and 1 <= len(outputs) <= 32, "outputs_required")
    for name, desc in outputs.items():
        token(name)
        closed(desc, {"length", "unit"})
        count(desc["length"], 1, 4096)
        unit(desc["unit"])
    laws = value["laws"]
    require(type(laws) is list and len(laws) <= 128, "law_list_required")
    ids = set()
    for law in laws:
        closed(law, {"id", "type", "status", "spec", "adoption_ref", "calibration"})
        name = token(law["id"])
        require(name not in ids, "duplicate_law")
        ids.add(name)
        token(law["type"])
        require(law["status"] in ("ADOPTED", "DIAGNOSTIC"), "law_status_required")
        if law["status"] == "DIAGNOSTIC":
            continue  # Diagnostic definitions never impose a verdict requirement.
        require(law["type"] in PRIMITIVES, "adopted_primitive_unsupported")
        sha(law["adoption_ref"])
        spec = law["spec"]
        fields = {
            "bound": {"output", "low", "high"},
            "initial_condition": {"output", "input"},
            "prefix_invariance": {"output", "inputs", "points"},
        }[law["type"]]
        closed(spec, fields)
        require(spec["output"] in outputs, "law_output_not_required")
        if law["type"] == "bound":
            require(
                spec["low"] is not None or spec["high"] is not None,
                "law_bound_required",
            )
            for key in ("low", "high"):
                if spec[key] is not None:
                    spec[key] = number(spec[key])
            require(
                spec["low"] is None
                or spec["high"] is None
                or spec["low"] <= spec["high"],
                "law_bound_invalid",
            )
        elif law["type"] == "initial_condition":
            require(spec["input"] in inputs, "law_input_not_required")
            require(
                inputs[spec["input"]]["unit"] == outputs[spec["output"]]["unit"],
                "law_units_mismatch",
            )
        else:
            require(
                type(spec["inputs"]) is list and bool(spec["inputs"]),
                "prefix_inputs_required",
            )
            require(
                len(set(spec["inputs"])) == len(spec["inputs"])
                and set(spec["inputs"]) <= set(inputs),
                "prefix_inputs_invalid",
            )
            count(spec["points"], 1, outputs[spec["output"]]["length"])
        calibration = law["calibration"]
        closed(
            calibration,
            {"image_digest", "record_digest", "reference_error", "tolerance", "unit"},
        )
        require(
            sha(calibration["image_digest"]) == value["reference_image"],
            "law_calibration_image_mismatch",
        )
        sha(calibration["record_digest"])
        floor = number(calibration["reference_error"], nonnegative=True)
        tolerance = number(calibration["tolerance"], nonnegative=True)
        require(tolerance >= floor, "tolerance_tighter_than_reference")
        require(
            calibration["unit"] == outputs[spec["output"]]["unit"],
            "calibration_units_mismatch",
        )
        calibration.update(reference_error=floor, tolerance=tolerance)
    return value


def reference(raw, image, family):
    if raw is None:
        return None, None
    value = snapshot(raw)
    header(
        value,
        REFERENCE_SCHEMA,
        {
            "image_digest",
            "criteria_digest",
            "code_verification_ref",
            "owner_acceptance_ref",
            "status",
            "acceptance_scope",
        },
    )
    require(sha(value["image_digest"]) == image, "reference_image_mismatch")
    sha(value["criteria_digest"])
    for key in ("code_verification_ref", "owner_acceptance_ref"):
        sha(value[key])
    require(
        value["status"] in ("READY", "UNRESOLVED", "FAILED_REFERENCE", "FAILED_INFRA"),
        "reference_status_invalid",
    )
    scope = value["acceptance_scope"]
    closed(
        scope,
        {"family", "observables", "verification_conditions", "application_conditions"},
    )
    token(scope["family"])
    observables = scope["observables"]
    require(
        type(observables) is list
        and len(observables) <= 32
        and all(type(name) is str for name in observables)
        and len(set(observables)) == len(observables),
        "acceptance_observables_required",
    )
    for name in observables:
        token(name)
    for field in ("verification_conditions", "application_conditions"):
        conditions = scope[field]
        require(
            type(conditions) is dict and len(conditions) <= 16,
            "acceptance_conditions_required",
        )
        for name, required_value in conditions.items():
            token(name)
            if required_value is not None:
                conditions[name] = number(required_value)
    accepted = None
    if value["status"] == "READY":
        require(scope["family"] == family, "reference_acceptance_family_mismatch")
        try:
            accepted = load_acceptance(family, image, value["criteria_digest"])
        except AcceptanceRefused:
            raise GuardConfigurationError(
                "reference_verification_unavailable"
            ) from None
        require(
            scope["family"] == accepted["family"]
            and scope["verification_conditions"] == accepted["conditions"],
            "reference_verification_scope_mismatch",
        )
        require(
            value["code_verification_ref"] == accepted["link_digest"],
            "reference_verification_link_mismatch",
        )
    return value, accepted


def native_map(raw, model_id, image, inputs, outputs):
    if raw is None:
        return None
    value = snapshot(raw)
    closed(
        value,
        {
            "schema",
            "maturity",
            "model",
            "spec",
            "top_models",
            "source",
            "reference_verification",
            "cells",
            "basis",
            "methods",
            "scored_case_selection",
        },
    )
    require(
        value["schema"] == MAP_SCHEMA and value["maturity"] == "DEVELOPMENT",
        "native_development_map_required",
    )
    require(
        value["model"] == model_id and value["scored_case_selection"] == "FORBIDDEN",
        "map_identity_mismatch",
    )
    closed(value["source"], {"kind", "evidence", "source_sha256"})
    require(value["source"]["kind"] in ("PUBLIC", "RELEASED"), "disclosed_map_required")
    require(
        type(value["source"]["evidence"]) is str and bool(value["source"]["evidence"]),
        "map_disclosure_basis_required",
    )
    sha("sha256:" + value["source"]["source_sha256"])
    verification = value["reference_verification"]
    closed(
        verification,
        {
            "schema",
            "scope",
            "family",
            "image_digest",
            "criteria_digest",
            "link_digest",
            "decision",
            "conditions",
        },
    )
    require(sha(verification["image_digest"]) == image, "map_reference_mismatch")
    try:
        accepted = load_acceptance(
            verification["family"], image, sha(verification["criteria_digest"])
        )
    except AcceptanceRefused:
        raise GuardConfigurationError("map_verification_unavailable") from None
    require(verification == accepted, "map_acceptance_receipt_mismatch")
    spec = value["spec"]
    closed(spec, {"axes", "bands", "marginalized", "outputs", "near_limit"})
    require(
        type(spec["axes"]) is list and len(spec["axes"]) == 2, "two_map_axes_required"
    )
    axes = [*spec["axes"], spec["bands"]]
    dimensions = []
    for axis in axes:
        closed(axis, {"name", "edges"})
        require(axis["name"] in inputs, "map_axis_unknown")
        require(
            type(axis["edges"]) is list and 2 <= len(axis["edges"]) <= 65,
            "map_edges_required",
        )
        edges = [number(v) for v in axis["edges"]]
        require(all(a < b for a, b in pairwise(edges)), "map_edges_invalid")
        require(
            inputs[axis["name"]]["low"] <= edges[0]
            and edges[-1] <= inputs[axis["name"]]["high"],
            "map_outside_surrogate_envelope",
        )
        axis["edges"] = edges
        dimensions.append(len(edges) - 1)
    require(type(spec["marginalized"]) is list, "map_marginalization_required")
    names = [a["name"] for a in axes] + spec["marginalized"]
    require(
        len(set(names)) == len(names) and set(names) == set(inputs),
        "map_context_mismatch",
    )
    closed(spec["outputs"], outputs)
    for description in spec["outputs"].values():
        closed(description, {"length", "unit"})
        count(description["length"], 1, 4096)
        unit(description["unit"])
    require(spec["outputs"] == outputs, "map_output_contract_mismatch")
    require(
        type(spec["near_limit"]) is list and bool(spec["near_limit"]),
        "map_near_limit_required",
    )
    for condition in spec["near_limit"]:
        closed(condition, {"output", "statistic", "operator", "value"})
        require(
            condition["output"] in outputs
            and condition["statistic"] in ("max", "abs_min")
            and condition["operator"] in ("le", "ge"),
            "map_near_limit_invalid",
        )
        number(condition["value"])
    closed(value["methods"], {"error", "disagreement", "marginalization"})
    require(
        all(
            type(method) is str and 0 < len(method) <= 500
            for method in value["methods"].values()
        ),
        "map_method_basis_required",
    )
    require(
        type(value["top_models"]) is list and len(value["top_models"]) >= 2,
        "map_top_models_required",
    )
    require(
        len(set(value["top_models"])) == len(value["top_models"]),
        "map_top_models_duplicate",
    )
    for name in value["top_models"]:
        token(name)
    cells = value["cells"]
    require(type(cells) is list and 1 <= len(cells) <= 4096, "map_cells_required")
    seen, total = set(), 0
    nx, ny, nb = dimensions
    require(nx * ny * nb <= 4096, "map_grid_size_limit")
    for cell in cells:
        closed(
            cell,
            {
                "band",
                "y",
                "x",
                "count",
                "status",
                "near_limit_count",
                "error",
                "disagreement",
            },
        )
        coordinate = (
            count(cell["band"], 0, nb - 1),
            count(cell["y"], 0, ny - 1),
            count(cell["x"], 0, nx - 1),
        )
        require(coordinate not in seen, "map_duplicate_cell")
        seen.add(coordinate)
        n = count(cell["count"])
        total += n
        count(cell["near_limit_count"], 0, n)
        require(
            cell["status"] == ("OBSERVED" if n else "NO_DATA"),
            "map_count_status_mismatch",
        )
        for layer in ("error", "disagreement"):
            closed(cell[layer], outputs)
            for result in cell[layer].values():
                closed(result, {"median", "p90"})
                if n:
                    result.update(
                        {key: number(v, nonnegative=True) for key, v in result.items()}
                    )
                    require(
                        result["median"] <= result["p90"], "map_quantile_order_invalid"
                    )
                else:
                    require(
                        all(v is None for v in result.values()),
                        "empty_map_cell_has_measurement",
                    )
    require(len(seen) == nx * ny * nb, "map_cell_grid_incomplete")
    closed(value["basis"], {"cases", "models", "top_models"})
    require(count(value["basis"]["cases"], 1) == total, "map_basis_mismatch")
    require(
        count(value["basis"]["top_models"], 2) == len(value["top_models"]),
        "map_top_basis_mismatch",
    )
    count(value["basis"]["models"], len(value["top_models"]))
    return value


def policy(raw, pins, inputs, outputs):
    if raw is None:
        return None
    value = snapshot(raw)
    header(
        value,
        POLICY_SCHEMA,
        {
            "basis",
            "authority_ref",
            "pins",
            "probe_steps",
            "max_model_calls",
            "map_limits",
            "min_cell_count",
            "uncertainty",
            "laws",
            "latency_target_ms",
        },
    )
    require(
        value["basis"] in ("SYNTHETIC_FIXTURE", "REGISTERED_DEVELOPMENT"),
        "development_policy_basis_required",
    )
    # External record references are host assertions; this is not authentication.
    if value["authority_ref"] is not None:
        sha(value["authority_ref"])
    require(value["pins"] == pins, "policy_identity_mismatch")
    closed(value["laws"], {"mode"})
    require(
        value["laws"]["mode"] in ("REQUIRED_ADOPTED", "EXPLICIT_NO_LAWS"),
        "law_policy_required",
    )
    closed(value["probe_steps"], inputs)
    for name, step in value["probe_steps"].items():
        step = number(step)
        require(
            0 < step <= inputs[name]["high"] - inputs[name]["low"], "probe_step_invalid"
        )
        value["probe_steps"][name] = step
    count(value["max_model_calls"], 1, 256)
    count(value["min_cell_count"], 1)
    closed(value["map_limits"], outputs)
    for name, limits in value["map_limits"].items():
        closed(limits, {"unit", "max_error_p90", "max_disagreement_p90"})
        require(limits["unit"] == outputs[name]["unit"], "map_limit_units_mismatch")
        for key in ("max_error_p90", "max_disagreement_p90"):
            limits[key] = number(limits[key], nonnegative=True)
    uncertainty = value["uncertainty"]
    closed(uncertainty, {"mode", "calibration", "max_width"})
    require(
        uncertainty["mode"] in ("EXPLICIT_NO_INTERVALS", "REQUIRED"),
        "uncertainty_policy_required",
    )
    calibration = uncertainty["calibration"]
    if calibration is not None:
        closed(calibration, {"image_digest", "record_digest"})
        require(
            sha(calibration["image_digest"]) == pins["reference_image"],
            "uncertainty_image_mismatch",
        )
        sha(calibration["record_digest"])
        closed(uncertainty["max_width"], outputs)
        for name, limit in uncertainty["max_width"].items():
            closed(limit, {"unit", "value"})
            require(
                limit["unit"] == outputs[name]["unit"], "uncertainty_units_mismatch"
            )
            limit["value"] = number(limit["value"], nonnegative=True)
    else:
        require(uncertainty["max_width"] is None, "uncertainty_calibration_required")
    if value["latency_target_ms"] is not None:
        value["latency_target_ms"] = number(value["latency_target_ms"])
        require(value["latency_target_ms"] > 0, "latency_target_invalid")
    return value


@dataclass(frozen=True)
class ModelBinding:
    """Trusted host's DEVELOPMENT callable/identity assertion, not attestation."""

    model_id: str
    artifact_digest: str
    runtime_digest: str
    predict: Callable

    def __post_init__(self):
        token(self.model_id)
        sha(self.artifact_digest)
        sha(self.runtime_digest)
        require(callable(self.predict), "trusted_callable_required")


@dataclass(frozen=True)
class Prediction:
    """Adapter output; finite shape/unit semantics are checked against the contract."""

    outputs: dict
    intervals: dict | None = None
