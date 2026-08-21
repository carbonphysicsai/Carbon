"""Reference structural validator for Carbon PhysicalSystemSpec v0.1.

AUTHORING-ONLY / NON-RUNTIME / NON-SCORING.

This module validates document shape and internal references. It does not
validate scientific correctness, numerical adequacy, Challenge LIVE status,
Score Pack semantics, or product qualification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence
import re


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_EXTENSION_NAMESPACE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z][A-Za-z0-9_-]*)+$")

_SUPPORTED_OPS = {
    "var", "param", "field", "const",
    "add", "mul", "pow", "neg", "eq",
    "partial", "derivative",
}

_FORBIDDEN_KEYS = {
    "master_secret",
    "official_seed",
    "official_seeds",
    "live_eval_tensor",
    "live_stress_tensor",
    "materialized_eval",
    "materialized_stress",
    "hidden_exam_tensor",
}

_MISSING_PREFIXES = ("UNRESOLVED", "HUMAN_INPUT", "UNKNOWN")


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # ERROR | WARNING | INFO
    code: str
    path: str
    message: str


def validate_physical_system_spec(spec: Mapping[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    _scan_forbidden_keys(spec, "$", issues)

    required = [
        "physical_system_spec_id", "version", "status", "classification",
        "system", "variables", "governing_relations", "domains",
        "assumptions", "provenance",
    ]
    for key in required:
        if key not in spec:
            _err(issues, "PSS001", f"$.{key}", f"missing required field {key!r}")

    _validate_identifier(spec.get("physical_system_spec_id"), "$.physical_system_spec_id", issues)
    _nonempty_string(spec.get("version"), "$.version", issues, "PSS003")
    _nonempty_string(spec.get("status"), "$.status", issues, "PSS004")
    _nonempty_string(spec.get("classification"), "$.classification", issues, "PSS005")

    system = spec.get("system")
    if isinstance(system, Mapping):
        for key in ("family", "system_class", "spatial_dimension"):
            if key not in system:
                _err(issues, "PSS010", f"$.system.{key}", "missing required system field")
        _nonempty_string(system.get("family"), "$.system.family", issues, "PSS011")
        _nonempty_string(system.get("system_class"), "$.system.system_class", issues, "PSS012")
        dim = system.get("spatial_dimension")
        if not isinstance(dim, int) or isinstance(dim, bool) or dim < 0:
            _err(issues, "PSS013", "$.system.spatial_dimension", "must be an integer >= 0")
    elif system is not None:
        _err(issues, "PSS014", "$.system", "must be a mapping")

    symbols = _build_symbol_table(spec.get("variables"), spec.get("parameters"), issues)
    indep = symbols["independent"]

    relations = spec.get("governing_relations")
    if _is_missing_state(relations):
        _warn(issues, "PSS020", "$.governing_relations", "governing relations explicitly unresolved")
    elif isinstance(relations, Sequence) and not isinstance(relations, (str, bytes)):
        if len(relations) == 0:
            _err(issues, "PSS021", "$.governing_relations", "must contain at least one relation or typed unresolved state")
        seen_rel_ids: set[str] = set()
        for i, relation in enumerate(relations):
            path = f"$.governing_relations[{i}]"
            if not isinstance(relation, Mapping):
                _err(issues, "PSS022", path, "relation must be a mapping")
                continue
            rid = relation.get("relation_id")
            _validate_identifier(rid, f"{path}.relation_id", issues)
            if isinstance(rid, str):
                if rid in seen_rel_ids:
                    _err(issues, "PSS023", f"{path}.relation_id", f"duplicate relation_id {rid!r}")
                seen_rel_ids.add(rid)
            _nonempty_string(relation.get("kind"), f"{path}.kind", issues, "PSS024")
            machine = relation.get("machine_semantics")
            if _is_missing_state(machine):
                _warn(issues, "PSS025", f"{path}.machine_semantics", "machine semantics explicitly unresolved")
            elif isinstance(machine, Mapping):
                _validate_expr(machine, f"{path}.machine_semantics", symbols, indep, issues)
            else:
                _err(issues, "PSS026", f"{path}.machine_semantics", "must be a relation IR mapping or typed unresolved state")
            if not relation.get("display_text") and not _is_missing_state(machine):
                _warn(issues, "PSS027", f"{path}.display_text", "display text missing for reviewable machine semantics")
    elif relations is not None:
        _err(issues, "PSS028", "$.governing_relations", "must be a list or typed unresolved state")

    _validate_conditions(spec.get("conditions"), symbols, indep, issues)
    _validate_extensions(spec.get("extensions"), issues)

    assumptions = spec.get("assumptions")
    if assumptions is not None and not _string_sequence(assumptions):
        _err(issues, "PSS040", "$.assumptions", "must be a sequence of strings")

    if spec.get("reconciliation_issues"):
        _warn(issues, "PSS041", "$.reconciliation_issues", "open reconciliation issues remain; scientific review required")

    if spec.get("classification") == "controlled_partner_semantics":
        _warn(issues, "PSS042", "$.classification", "controlled semantics require separate transport/storage/disclosure policy")

    return sorted(issues, key=lambda x: (x.path, x.severity, x.code, x.message))


def is_structurally_valid(spec: Mapping[str, Any]) -> bool:
    return not any(i.severity == "ERROR" for i in validate_physical_system_spec(spec))


def _build_symbol_table(variables: Any, parameters: Any, issues: list[ValidationIssue]) -> dict[str, set[str]]:
    table = {"independent": set(), "state": set(), "field": set(), "observed": set(), "parameter": set()}
    seen: dict[str, str] = {}

    if not isinstance(variables, Mapping):
        _err(issues, "PSS050", "$.variables", "must be a mapping")
        variables = {}

    categories = {
        "independent": variables.get("independent", []),
        "state": variables.get("state", []),
        "field": variables.get("fields", []),
        "observed": variables.get("observed", []),
        "parameter": parameters or [],
    }

    for category, entries in categories.items():
        path_key = "parameters" if category == "parameter" else f"variables.{category if category != 'field' else 'fields'}"
        if entries is None:
            entries = []
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            _err(issues, "PSS051", f"$.{path_key}", "must be a sequence")
            continue
        for i, entry in enumerate(entries):
            path = f"$.{path_key}[{i}]"
            if not isinstance(entry, Mapping):
                _err(issues, "PSS052", path, "symbol declaration must be a mapping")
                continue
            symbol = entry.get("symbol") or entry.get("name")
            _validate_identifier(symbol, f"{path}.symbol", issues)
            if not isinstance(symbol, str):
                continue
            if symbol in seen:
                _err(issues, "PSS053", f"{path}.symbol", f"duplicate symbol {symbol!r}; already declared as {seen[symbol]}")
                continue
            seen[symbol] = category
            table[category].add(symbol)

    if not table["independent"]:
        _err(issues, "PSS054", "$.variables.independent", "at least one independent variable is required")
    if not table["state"]:
        _err(issues, "PSS055", "$.variables.state", "at least one state variable is required")

    return table


def _validate_expr(expr: Mapping[str, Any], path: str, symbols: Mapping[str, set[str]], indep: set[str], issues: list[ValidationIssue]) -> None:
    op = expr.get("op")
    if op not in _SUPPORTED_OPS:
        _err(issues, "PSS060", f"{path}.op", f"unsupported relation operator {op!r}")
        return

    if op in {"var", "param", "field"}:
        name = expr.get("name", expr.get("id"))
        _validate_identifier(name, f"{path}.name", issues)
        category = {"var": "state", "param": "parameter", "field": "field"}[op]
        if isinstance(name, str) and name not in symbols[category] and not (op == "var" and name in symbols["observed"]):
            _err(issues, "PSS061", f"{path}.name", f"{op} {name!r} is not declared in the matching symbol class")
        return

    if op == "const":
        if "value" not in expr:
            _err(issues, "PSS062", path, "const requires value")
        return

    if op in {"add", "mul"}:
        args = expr.get("args")
        if not isinstance(args, Sequence) or isinstance(args, (str, bytes)) or len(args) < 2:
            _err(issues, "PSS063", f"{path}.args", f"{op} requires at least two args")
            return
        for i, child in enumerate(args):
            _validate_child(child, f"{path}.args[{i}]", symbols, indep, issues)
        return

    if op == "eq":
        if "args" in expr:
            args = expr.get("args")
            if not isinstance(args, Sequence) or isinstance(args, (str, bytes)) or len(args) != 2:
                _err(issues, "PSS064", f"{path}.args", "eq requires exactly two args")
                return
            _validate_child(args[0], f"{path}.args[0]", symbols, indep, issues)
            _validate_child(args[1], f"{path}.args[1]", symbols, indep, issues)
        else:
            if "lhs" not in expr or "rhs" not in expr:
                _err(issues, "PSS065", path, "eq requires args[2] or lhs/rhs")
                return
            _validate_child(expr["lhs"], f"{path}.lhs", symbols, indep, issues)
            _validate_child(expr["rhs"], f"{path}.rhs", symbols, indep, issues)
        return

    if op == "neg":
        child = expr.get("expr", expr.get("arg"))
        if child is None:
            _err(issues, "PSS066", path, "neg requires expr/arg")
            return
        _validate_child(child, f"{path}.expr", symbols, indep, issues)
        return

    if op == "pow":
        if "base" not in expr or "exponent" not in expr:
            _err(issues, "PSS067", path, "pow requires base and exponent")
            return
        _validate_child(expr["base"], f"{path}.base", symbols, indep, issues)
        exponent = expr["exponent"]
        if isinstance(exponent, Mapping):
            _validate_expr(exponent, f"{path}.exponent", symbols, indep, issues)
        return

    if op in {"partial", "derivative"}:
        child = expr.get("expr")
        wrt = expr.get("wrt")
        order = expr.get("order")
        if child is None:
            _err(issues, "PSS068", f"{path}.expr", f"{op} requires expr")
        else:
            _validate_child(child, f"{path}.expr", symbols, indep, issues)
        if wrt not in indep:
            _err(issues, "PSS069", f"{path}.wrt", f"derivative axis {wrt!r} is not a declared independent variable")
        if not isinstance(order, int) or isinstance(order, bool) or order <= 0:
            _err(issues, "PSS070", f"{path}.order", "derivative order must be a positive integer")
        return


def _validate_child(child: Any, path: str, symbols: Mapping[str, set[str]], indep: set[str], issues: list[ValidationIssue]) -> None:
    if not isinstance(child, Mapping):
        _err(issues, "PSS071", path, "expression child must be a mapping")
        return
    _validate_expr(child, path, symbols, indep, issues)


def _validate_conditions(conditions: Any, symbols: Mapping[str, set[str]], indep: set[str], issues: list[ValidationIssue]) -> None:
    if conditions is None:
        return
    if not isinstance(conditions, Mapping):
        _err(issues, "PSS080", "$.conditions", "must be a mapping")
        return
    seen: set[str] = set()
    for group in ("initial", "boundary"):
        entries = conditions.get(group, []) or []
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            _err(issues, "PSS081", f"$.conditions.{group}", "must be a sequence")
            continue
        for i, condition in enumerate(entries):
            path = f"$.conditions.{group}[{i}]"
            if not isinstance(condition, Mapping):
                _err(issues, "PSS082", path, "condition must be a mapping")
                continue
            cid = condition.get("condition_id")
            _validate_identifier(cid, f"{path}.condition_id", issues)
            if isinstance(cid, str):
                if cid in seen:
                    _err(issues, "PSS083", f"{path}.condition_id", f"duplicate condition_id {cid!r}")
                seen.add(cid)
            _nonempty_string(condition.get("type"), f"{path}.type", issues, "PSS084")
            target = condition.get("target")
            allowed_targets = symbols["state"] | symbols["field"] | symbols["observed"]
            if target not in allowed_targets:
                _err(issues, "PSS085", f"{path}.target", f"condition target {target!r} is not a declared state/field/observed symbol")
            if "region" not in condition:
                _err(issues, "PSS086", f"{path}.region", "condition region is required")
            if "provenance" not in condition:
                _warn(issues, "PSS087", f"{path}.provenance", "condition provenance is missing")


def _validate_extensions(extensions: Any, issues: list[ValidationIssue]) -> None:
    if extensions is None:
        return
    if not isinstance(extensions, Mapping):
        _err(issues, "PSS090", "$.extensions", "must be a mapping")
        return
    for namespace, envelope in extensions.items():
        path = f"$.extensions.{namespace}"
        if not isinstance(namespace, str) or not _EXTENSION_NAMESPACE.match(namespace):
            _err(issues, "PSS091", path, "extension namespace must be namespaced, e.g. 'carbon.regime_features'")
        if not isinstance(envelope, Mapping):
            _err(issues, "PSS092", path, "extension envelope must be a mapping")
            continue
        _nonempty_string(envelope.get("extension_version"), f"{path}.extension_version", issues, "PSS093")
        if "payload" not in envelope:
            _err(issues, "PSS094", f"{path}.payload", "extension envelope requires payload")


def _scan_forbidden_keys(value: Any, path: str, issues: list[ValidationIssue]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in _FORBIDDEN_KEYS:
                _err(issues, "PSS100", child_path, "forbidden protected-material key in PhysicalSystemSpec")
            _scan_forbidden_keys(child, child_path, issues)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for i, child in enumerate(value):
            _scan_forbidden_keys(child, f"{path}[{i}]", issues)


def _validate_identifier(value: Any, path: str, issues: list[ValidationIssue]) -> None:
    if not isinstance(value, str) or not value or not _IDENTIFIER.match(value):
        _err(issues, "PSS002", path, "must be a non-empty canonical identifier")


def _nonempty_string(value: Any, path: str, issues: list[ValidationIssue], code: str) -> None:
    if not isinstance(value, str) or not value.strip():
        _err(issues, code, path, "must be a non-empty string")


def _string_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and all(isinstance(x, str) for x in value)


def _is_missing_state(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(_MISSING_PREFIXES)


def _err(issues: list[ValidationIssue], code: str, path: str, message: str) -> None:
    issues.append(ValidationIssue("ERROR", code, path, message))


def _warn(issues: list[ValidationIssue], code: str, path: str, message: str) -> None:
    issues.append(ValidationIssue("WARNING", code, path, message))
