"""S3/H2 producer-evidence checks for the DEVELOPMENT readiness gate.

Registrations live in the repository; panels of reference margins or private
case inputs stay on the producer. Neither case IDs nor overlap witnesses enter
the returned aggregates. Missing evidence never becomes a readiness pass.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .model import FAIL, NOT_BUILT, PASS, Result

MARGIN_REGISTRATION_SCHEMA = "carbon.readiness.gate-margin-registration.v1"
MARGIN_PANEL_SCHEMA = "carbon.readiness.gate-margin-panel.v1"
OVERLAP_REGISTRATION_SCHEMA = "carbon.readiness.tuning-overlap-registration.v1"
OVERLAP_PANEL_SCHEMA = "carbon.readiness.tuning-overlap-panel.v1"
PUBLIC_PRIORS = frozenset({"rotating_pool", "TRAIN", "PRACTICE", "practice_decision"})


class EvidenceInvalid(ValueError):
    pass


def _digest(path: Path) -> str:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise EvidenceInvalid("evidence_unreadable") from error


def _load(path: Path) -> dict:
    try:
        document = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        raise EvidenceInvalid("evidence_unreadable") from error
    if type(document) is not dict:
        raise EvidenceInvalid("evidence_not_object")
    return document


def _registered(ctx, filename: str, schema: str) -> tuple[dict, Path] | None:
    path = (
        ctx.repository
        / "carbon/challenge_pipeline/readiness"
        / ctx.challenge
        / filename
    )
    if not path.is_file():
        return None
    document = _load(path)
    if document.get("schema") != schema or document.get("challenge") != ctx.challenge:
        raise EvidenceInvalid("registration_identity_mismatch")
    return document, path


def _panel(ctx, item: str, registration: dict, schema: str) -> tuple[dict, str] | None:
    named = ctx.evidence_paths.get(item)
    if not named:
        return None
    path = Path(named).resolve()
    if path == ctx.repository.resolve() or ctx.repository.resolve() in path.parents:
        raise EvidenceInvalid("private_panel_inside_repository")
    if _digest(path) != registration.get("panel_digest"):
        raise EvidenceInvalid("panel_digest_mismatch")
    document = _load(path)
    if document.get("schema") != schema or document.get("challenge") != ctx.challenge:
        raise EvidenceInvalid("panel_identity_mismatch")
    return document, _digest(path)


def _finite(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _p01(values: list[float]) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * 0.01
    lower = math.floor(index)
    upper = math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def margin_study(registration: dict, panel: dict) -> tuple[dict, ...]:
    """Compute every registered gate's minimum, empirical p01 and fragility."""
    gates = registration.get("gates")
    observed = panel.get("margins")
    if type(gates) is not list or not gates or type(observed) is not dict:
        raise EvidenceInvalid("margin_gates_missing")
    names = [gate.get("name") for gate in gates if type(gate) is dict]
    if len(names) != len(gates) or len(set(names)) != len(gates):
        raise EvidenceInvalid("margin_gate_names_invalid")
    if set(observed) != set(names):
        raise EvidenceInvalid("margin_gate_coverage_incomplete")
    result = []
    for gate in gates:
        name, unit, boundary = (
            gate.get("name"),
            gate.get("unit"),
            gate.get("fragile_below"),
        )
        values = observed[name]
        if (
            type(name) is not str
            or not name
            or type(unit) is not str
            or not unit
            or not _finite(boundary)
            or type(values) is not list
            or not values
            or not all(_finite(v) for v in values)
        ):
            raise EvidenceInvalid("margin_gate_malformed")
        result.append(
            {
                "gate": name,
                "unit": unit,
                "n": len(values),
                "minimum": min(values),
                "p01": _p01(values),
                "fragile": min(values) <= boundary,
            }
        )
    return tuple(result)


def gate_margin_study(item, ctx) -> Result:
    try:
        registered = _registered(
            ctx, "gate-margin-registration.json", MARGIN_REGISTRATION_SCHEMA
        )
        if registered is None:
            return Result(NOT_BUILT, "S3 gate-margin registration is absent")
        registration, path = registered
        loaded = _panel(ctx, "S3", registration, MARGIN_PANEL_SCHEMA)
        if loaded is None:
            return Result(NOT_BUILT, "S3 registered reference-margin panel is absent")
        panel, panel_digest = loaded
        measures = margin_study(registration, panel)
        evidence = tuple(
            f"{row['gate']}: min={row['minimum']} p01={row['p01']} "
            f"unit={row['unit']} fragile={row['fragile']} n={row['n']}"
            for row in measures
        ) + (f"registration:{_digest(path)}", f"panel:{panel_digest}")
        return Result(
            PASS, "every registered gate has a reference-margin study", evidence
        )
    except EvidenceInvalid as error:
        return Result(FAIL, f"S3 evidence invalid: {error}")


def _case_key(inputs: dict) -> bytes:
    if type(inputs) is not dict or not inputs:
        raise EvidenceInvalid("overlap_case_malformed")
    try:
        return json.dumps(
            inputs, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except (TypeError, ValueError) as error:
        raise EvidenceInvalid("overlap_case_malformed") from error


def overlap_study(registration: dict, panel: dict, registered_roles: set[str]) -> dict:
    """Compare distinct case inputs across every declared sealed and public role."""
    tuning = registration.get("tuning_role")
    sealed = registration.get("sealed_roles")
    unsealed = registration.get("unsealed_roles")
    groups = panel.get("groups")
    if (
        type(tuning) is not str
        or tuning not in registered_roles
        or type(sealed) is not list
        or type(unsealed) is not list
        or not all(type(r) is str for r in sealed + unsealed)
        or len(set(sealed + unsealed + [tuning])) != len(sealed + unsealed) + 1
        or set(sealed + unsealed + [tuning]) != registered_roles
        or type(groups) is not dict
    ):
        raise EvidenceInvalid("overlap_role_roster_incomplete")
    expected = {tuning, *sealed, *PUBLIC_PRIORS}
    if set(groups) != expected:
        raise EvidenceInvalid("overlap_group_coverage_incomplete")
    keys = {}
    for role, cases in groups.items():
        if type(cases) is not list or not cases:
            raise EvidenceInvalid("overlap_group_empty")
        values = [_case_key(case) for case in cases]
        if len(set(values)) != len(values):
            raise EvidenceInvalid("overlap_within_group")
        keys[role] = set(values)
    for left in sorted(keys):
        for right in sorted(keys):
            if left < right and keys[left] & keys[right]:
                raise EvidenceInvalid("overlap_between_groups")
    return {"groups": len(keys), "cases": sum(map(len, keys.values()))}


def tuning_overlap(item, ctx) -> Result:
    try:
        registered = _registered(
            ctx, "tuning-overlap-registration.json", OVERLAP_REGISTRATION_SCHEMA
        )
        if registered is None:
            return Result(NOT_BUILT, "H2 tuning-overlap registration is absent")
        registration, path = registered
        loaded = _panel(ctx, "H2", registration, OVERLAP_PANEL_SCHEMA)
        if loaded is None:
            return Result(NOT_BUILT, "H2 registered overlap panel is absent")
        panel, panel_digest = loaded
        registry_path = (
            ctx.repository
            / "carbon/challenge_validator/confirmation_sets/registry.json"
        )
        registry = _load(registry_path).get("sets")
        if type(registry) is not dict:
            raise EvidenceInvalid("confirmation_registry_malformed")
        from carbon.challenge_validator.interface import digest as registry_digest

        roles = set()
        for role, pinned in registry.items():
            document = _load(registry_path.parent / f"{role}.json")
            if document.get("role") != role or registry_digest(document) != pinned:
                raise EvidenceInvalid("confirmation_role_digest_mismatch")
            if document.get("challenge_id") == ctx.challenge:
                roles.add(role)
        summary = overlap_study(registration, panel, roles)
        return Result(
            PASS,
            "tuning and all registered sealed/public groups have no case overlap",
            (
                f"groups:{summary['groups']}",
                f"cases:{summary['cases']}",
                f"registration:{_digest(path)}",
                f"panel:{panel_digest}",
            ),
        )
    except EvidenceInvalid as error:
        return Result(FAIL, f"H2 evidence invalid: {error}")
