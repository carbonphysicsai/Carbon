"""S1/S3/H2/H4: scoped metadata and producer aggregates, never qualification."""

from __future__ import annotations

import importlib
import json
from functools import wraps
from pathlib import Path

from . import evidence_checks as ec
from .model import FAIL, NOT_BUILT, PASS, REVIEW_REQUIRED, Result, digest
from .runtime_checks import Invalid
from .study_checks import _bytes, _finite, _json

LEVELS = [2, 3, 4]
AUDIT_REGISTRATION_SCHEMA = "carbon.readiness.gate-audit-registration.v1"
AUDIT_PANEL_SCHEMA = "carbon.readiness.gate-audit-panel.v1"
MEASUREMENT_SCHEMA = "carbon.readiness.margin-measurement.v1"
MEASUREMENT_RUN_SCHEMA = "carbon.readiness.margin-measurement-run.v1"
POPULATIONS = ("practice", "hidden", "tuning")


def _guard(function):
    @wraps(function)
    def checked(item, ctx):
        try:
            return function(item, ctx)
        except (Invalid, ec.EvidenceInvalid):
            return Result(
                FAIL, f"{item['id']} evidence invalid; scope, shape or binding refused"
            )
        except (OSError, ValueError, TypeError, KeyError, ImportError):
            return Result(
                FAIL, f"{item['id']} evidence or adapter unavailable/malformed"
            )

    return checked


def _record(ctx, item):
    records = ctx.data.get("scoring_by_level", {})
    if type(records) is not dict or type(records.get(item, {})) is not dict:
        raise Invalid("scoring_registration_malformed")
    record = records.get(item, {}).get(str(ctx.level))
    if record is None:
        return None
    if (
        type(record) is not dict
        or record.get("challenge") != ctx.challenge
        or record.get("levels") != LEVELS
        or ctx.level not in LEVELS
        or type(record.get("basis")) is not str
        or not record["basis"].strip()
    ):
        raise Invalid("scoring_registration_scope_mismatch")
    return record


def _missing(item):
    return Result(NOT_BUILT, f"no {item} evidence registered for this Challenge/level")


def _adapter(ctx, record):
    module = importlib.import_module(record["adapter"])
    source = Path(module.__file__).resolve().relative_to(ctx.repository.resolve())
    _, sha = _bytes(ctx, source.as_posix())
    if getattr(module, "CHALLENGE", None) != ctx.challenge:
        raise Invalid("scoring_adapter_challenge_mismatch")
    files = record.get("code", [])
    if type(files) is not list:
        raise Invalid("scoring_adapter_pins_malformed")
    return module, (sha, *(_bytes(ctx, path)[1] for path in files))


def _registration(ctx, record, schema):
    registration, sha = _json(ctx, record["registration"])
    if (
        registration.get("schema") != schema
        or registration.get("challenge") != ctx.challenge
        or registration.get("levels") != LEVELS
        or not registration.get("basis")
    ):
        raise Invalid("producer_registration_scope_mismatch")
    return registration, sha


def _roster(ctx, record, registration):
    adapter, code = _adapter(ctx, record)
    expected = adapter.gate_roster(ctx.repository)
    gates = registration.get("gates")
    if (
        type(expected) is not dict
        or not expected
        or type(gates) is not list
        or any(type(g) is not dict or type(g.get("name")) is not str for g in gates)
        or len({g["name"] for g in gates}) != len(gates)
        or {g["name"] for g in gates} != set(expected)
    ):
        raise Invalid("scorer_gate_registration_coverage_mismatch")
    for gate in gates:
        metadata = expected[gate["name"]]
        if gate.get("scope") != metadata["scope"]:
            raise Invalid("scorer_gate_scope_mismatch")
        if metadata["unit"] is not None and gate.get("unit") != metadata["unit"]:
            raise Invalid("scorer_gate_unit_mismatch")
    return code


def _panel(ctx, item, registration, schema):
    loaded = ec._panel(ctx, item, registration, schema)
    if loaded is not None and loaded[0].get("levels") != LEVELS:
        raise Invalid("producer_panel_level_mismatch")
    return loaded


@_guard
def promotion_margin(item, ctx):
    record = _record(ctx, "S1")
    if record is None:
        if ctx.level <= 1:
            from .checks import recorded_tests

            return recorded_tests(item, ctx)
        return _missing("S1")
    adapter, code = _adapter(ctx, record)
    active = adapter.promotion_rule()
    rule, key = active["rule"], active["key"]
    comparison = rule.get("comparison")
    if (
        type(key) is not str
        or not key
        or type(comparison) is not dict
        or any(
            not _finite(comparison.get(k))
            for k in ("n_min", "n_boot", "alpha", "important_min")
        )
        or not _finite(rule.get("equivalence_margin_rel"))
    ):
        raise Invalid("promotion_rule_structure_incomplete")
    evidence = (*code, f"active_rule:{key}", f"rule:{digest(rule)}")
    if record.get("measurement") is None:
        return Result(
            REVIEW_REQUIRED,
            "active rule structure holds; margin/noise measurement is HUMAN_INPUT",
            evidence,
        )
    measurement, sha = _json(ctx, record["measurement"])
    if (
        measurement.get("schema") != MEASUREMENT_SCHEMA
        or measurement.get("challenge") != ctx.challenge
        or measurement.get("levels") != LEVELS
        or measurement.get("rule_key") != key
        or measurement.get("rule_digest") != digest(rule)
        or measurement.get("equivalence_margin_rel") != rule["equivalence_margin_rel"]
        or type(measurement.get("noise_source")) is not str
        or measurement["noise_source"] in ("", "HUMAN_INPUT")
    ):
        raise Invalid("margin_measurement_binding_mismatch")
    run, run_sha = _json(ctx, measurement["run"]["path"])
    observations = run.get("observations")
    if (
        measurement["run"].get("sha256") != run_sha
        or run.get("schema") != MEASUREMENT_RUN_SCHEMA
        or run.get("challenge") != ctx.challenge
        or run.get("levels") != LEVELS
        or run.get("noise_source") != measurement["noise_source"]
        or run.get("rule_digest") != digest(rule)
        or run.get("equivalence_margin_rel") != rule["equivalence_margin_rel"]
        or type(run.get("method")) is not str
        or not run["method"].strip()
        or type(observations) is not list
        or not observations
        or not all(_finite(x) for x in observations)
    ):
        raise Invalid("margin_measurement_run_mismatch")
    return Result(
        PASS,
        "active rule and committed margin/noise measurement binding checked; no qualification",
        (*evidence, sha, run_sha),
    )


@_guard
def gate_margin_study(item, ctx):
    record = _record(ctx, "S3")
    if record is None:
        return ec.gate_margin_study(item, ctx) if ctx.level <= 1 else _missing("S3")
    registration, sha = _registration(ctx, record, ec.MARGIN_REGISTRATION_SCHEMA)
    code = _roster(ctx, record, registration)
    unknown = False
    for gate in registration["gates"]:
        boundary, unit = gate.get("fragile_below"), gate.get("unit")
        unknown |= boundary is None or unit in (None, "HUMAN_INPUT")
        if (boundary is not None and not _finite(boundary)) or (
            unit not in (None, "HUMAN_INPUT") and (type(unit) is not str or not unit)
        ):
            raise Invalid("margin_gate_malformed")
    if unknown:
        # A missing owner value cannot hide a malformed supplied panel.
        loaded = _panel(ctx, "S3", registration, ec.MARGIN_PANEL_SCHEMA)
        if loaded is not None:
            margins = loaded[0].get("margins")
            if (
                type(margins) is not dict
                or set(margins) != {g["name"] for g in registration["gates"]}
                or any(
                    type(values) is not list
                    or not values
                    or not all(_finite(v) for v in values)
                    for values in margins.values()
                )
            ):
                raise Invalid("margin_gate_malformed")
        return Result(
            NOT_BUILT,
            "S3 fragility boundaries/scalar margin units require owner input",
            (*code, sha),
        )
    loaded = _panel(ctx, "S3", registration, ec.MARGIN_PANEL_SCHEMA)
    if loaded is None:
        return Result(
            NOT_BUILT,
            "S3 registered public-reference-margin panel is absent",
            (*code, sha),
        )
    panel, panel_sha = loaded
    measures = ec.margin_study(registration, panel)
    return Result(
        PASS,
        "all current registered gates have margin arithmetic; fragility is reported, not adjudicated",
        (*code, sha, panel_sha, json.dumps(measures, sort_keys=True)),
    )


def registered_roles(ctx):
    directory = "carbon/challenge_validator/confirmation_sets/"
    registry, sha = _json(ctx, directory + "registry.json")
    from carbon.challenge_validator.interface import digest as role_digest

    roles, evidence = set(), [sha]
    for role, pin in registry["sets"].items():
        if (
            type(role) is not str
            or not role
            or "/" in role
            or "\\" in role
            or ".." in role
        ):
            raise Invalid("confirmation_role_token_invalid")
        document, file_sha = _json(ctx, directory + role + ".json")
        if document.get("role") != role or role_digest(document) != pin:
            raise Invalid("confirmation_role_digest_mismatch")
        evidence.append(file_sha)
        if document.get("challenge_id") == ctx.challenge:
            roles.add(role)
    return roles, tuple(evidence)


@_guard
def tuning_overlap(item, ctx):
    record = _record(ctx, "H2")
    if record is None:
        return ec.tuning_overlap(item, ctx) if ctx.level <= 1 else _missing("H2")
    registration, sha = _registration(ctx, record, ec.OVERLAP_REGISTRATION_SCHEMA)
    roles, code = registered_roles(ctx)
    if registration.get("tuning_role") not in roles:
        raise Invalid("tuning_role_not_registered")
    classifications = [
        registration.get("sealed_roles"),
        registration.get("unsealed_roles"),
    ]
    if any(
        value not in (None, "HUMAN_INPUT") and type(value) is not list
        for value in classifications
    ):
        raise Invalid("overlap_role_roster_incomplete")
    if any(value in (None, "HUMAN_INPUT") for value in classifications):
        loaded = _panel(ctx, "H2", registration, ec.OVERLAP_PANEL_SCHEMA)
        if loaded is not None:
            groups = loaded[0].get("groups")
            if (
                type(groups) is not dict
                or not groups
                or any(
                    type(values) is not list or not values for values in groups.values()
                )
            ):
                raise Invalid("overlap_group_empty")
            for values in groups.values():
                for inputs in values:
                    ec._case_key(inputs)
        return Result(
            NOT_BUILT,
            "H2 sealed/unsealed custody classification is HUMAN_INPUT",
            (*code, sha),
        )
    # Check the roster even before a panel is supplied.
    sealed, unsealed = registration["sealed_roles"], registration["unsealed_roles"]
    if (
        type(sealed) is not list
        or type(unsealed) is not list
        or not all(type(r) is str for r in sealed + unsealed)
        or len(set(sealed + unsealed + [registration["tuning_role"]]))
        != len(sealed + unsealed) + 1
        or set(sealed + unsealed + [registration["tuning_role"]]) != roles
    ):
        raise Invalid("overlap_role_roster_incomplete")
    loaded = _panel(ctx, "H2", registration, ec.OVERLAP_PANEL_SCHEMA)
    if loaded is None:
        return Result(
            NOT_BUILT, "H2 registered producer overlap panel is absent", (*code, sha)
        )
    panel, panel_sha = loaded
    summary = ec.overlap_study(registration, panel, roles)
    return Result(
        PASS,
        "registered groups checked for distinct inputs; no witnesses disclosed",
        (
            *code,
            sha,
            panel_sha,
            f"groups:{summary['groups']}",
            f"cases:{summary['cases']}",
        ),
    )


def audit_study(registration, panel):
    populations = panel.get("populations")
    allowed = {gate["name"] for gate in registration["gates"]}
    if type(populations) is not dict or set(populations) != set(POPULATIONS):
        raise ec.EvidenceInvalid("audit_population_coverage_incomplete")
    if any(
        type(p) is not dict or not p or not set(p) <= allowed
        for p in populations.values()
    ):
        raise ec.EvidenceInvalid("audit_population_gates_invalid")
    names = set().union(*(set(p) for p in populations.values()))
    if set(populations["practice"]) - (
        set(populations["hidden"]) | set(populations["tuning"])
    ):
        raise ec.EvidenceInvalid("audit_practice_only_gate")
    result = []
    for name in sorted(names):
        counts = {}
        for population in POPULATIONS:
            rows = populations[population].get(name, [])
            if type(rows) is not list or (name in populations[population] and not rows):
                raise ec.EvidenceInvalid("audit_gate_rows_empty")
            if any(
                type(r) is not dict
                or set(r) != {"passed", "margin"}
                or type(r["passed"]) is not bool
                or not _finite(r["margin"])
                for r in rows
            ):
                raise ec.EvidenceInvalid("audit_gate_row_malformed")
            if any(
                (r["passed"] and r["margin"] < 0)
                or (not r["passed"] and r["margin"] > 0)
                for r in rows
            ):
                raise ec.EvidenceInvalid("audit_verdict_margin_contradiction")
            margins = [r["margin"] for r in rows]
            passed = sum(r["passed"] for r in rows)
            counts[population] = {
                "checked": len(rows),
                "pass": passed,
                "fail": len(rows) - passed,
                "minimum": min(margins) if margins else None,
                "p01": ec._p01(margins) if margins else None,
            }
        result.append({"gate": name, "populations": counts})
    return result


@_guard
def gate_audit(item, ctx):
    record = _record(ctx, "H4")
    if record is None:
        if ctx.level <= 1:
            from .checks import recorded_tests

            return recorded_tests(item, ctx)
        return _missing("H4")
    registration, sha = _registration(ctx, record, AUDIT_REGISTRATION_SCHEMA)
    code = _roster(ctx, record, registration)
    loaded = _panel(ctx, "H4", registration, AUDIT_PANEL_SCHEMA)
    if loaded is None:
        return Result(
            NOT_BUILT,
            "H4 producer audit panel absent; hidden host is an operator prerequisite",
            (*code, sha),
        )
    panel, panel_sha = loaded
    report = audit_study(registration, panel)
    # Generic runner review remains separate, but cannot accept an uncommitted
    # or stale framing against a different registered panel.
    review_path = (
        "carbon/challenge_pipeline/readiness/" + ctx.challenge + "/reviews/H4.json"
    )
    if (ctx.repository / review_path).exists():
        from .runner import review_problem

        review, _ = _json(ctx, review_path)
        if (
            review_problem(review, ctx.challenge, ctx.level, "H4")
            or review.get("reviewer") != "Test Lead"
            or review.get("binding")
            != {"panel_digest": panel_sha, "registration_digest": sha}
        ):
            raise Invalid("audit_framing_scope_or_digest_mismatch")
    return Result(
        PASS,
        "H4 aggregate report computed for all populations; framing is separate",
        (*code, sha, panel_sha, json.dumps(report, sort_keys=True)),
    )
