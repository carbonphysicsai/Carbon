"""Public, pure development unified-construction derivation (PLT-16).

These libraries grant no admission. No compiler, signer, evaluator, registry
file, process or network is accessed by classify/derive/commitment.
"""

from __future__ import annotations

import hashlib
import json
import math
import re

from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy
from carbon.schema.strategy import dry_validate

LEGACY_SCHEMA = "carbon.unified-construction-contract.v1"
SCHEMA = "carbon.unified-construction-contract.v2"
LEGACY_BINDING_SCHEMA = "carbon.unified-construction-binding.v1"
BINDING_SCHEMA = "carbon.unified-construction-binding.v2"
MAX_BYTES = 2 * 1024 * 1024
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
FIELDS = {
    "schema",
    "version",
    "registry_version",
    "challenge",
    "base_contract_digest",
    "families",
    "base_fields",
    "types",
    "ceiling",
    "common_checks",
    "scope",
}
TYPE_FIELDS = {
    "type",
    "label",
    "fields",
    "arms",
    "open",
    "owner_acceptance",
    "within_ceiling",
    "checks",
    "registration_digest",
}
ARM_FIELDS = {
    "name",
    "variant",
    "digest",
    "fields",
    "expression",
    "bounds",
    "requirements",
    "external_allowed",
}


class UnifiedRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def canonical(value):
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise UnifiedRefused("construction_unclassified") from None


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def _strings(value):
    return (
        type(value) is list
        and all(type(v) is str and v for v in value)
        and len(set(value)) == len(value)
    )


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _field(value):
    if (
        type(value) is not dict
        or set(value) != {"kind", "low", "high", "default", "families"}
        or value["kind"]
        not in {"uint", "float", "bool", "choice", "pool", "digest", "expression"}
        or not (value["families"] is None or _strings(value["families"]))
    ):
        return False
    kind, low, high = value["kind"], value["low"], value["high"]
    if kind in {"uint", "float"}:
        return (
            _number(low)
            and _number(high)
            and low <= high
            and _number(value["default"])
            and low <= value["default"] <= high
            and (kind != "uint" or type(low) is type(high) is int)
            and (kind != "uint" or type(value["default"]) is int)
        )
    if kind == "choice":
        return _strings(low) and bool(low) and high is None and value["default"] in low
    if kind == "pool":
        return (
            type(low) is dict
            and set(low) == {"versions", "parts", "inputs", "weight"}
            and type(low["versions"]) is dict
            and bool(low["versions"])
            and all(
                type(k) is str and SHA.fullmatch(k) and type(v) is int and v > 0
                for k, v in low["versions"].items()
            )
            and _strings(low["parts"])
            and _strings(low["inputs"])
            and type(low["weight"]) is list
            and len(low["weight"]) == 2
            and all(_number(v) for v in low["weight"])
            and low["weight"][0] <= low["weight"][1]
            and high is None
            and value["default"] is None
        )
    return low is high is None and (
        type(value["default"]) is bool if kind == "bool" else value["default"] is None
    )


class UnifiedContract:
    """Validated closed data, held as immutable canonical bytes."""

    __slots__ = ("_raw",)

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("unified contract is immutable")
        object.__setattr__(self, name, value)

    def __init__(self, document):
        # Round-trip through the same bounded strict JSON parser as input.
        try:
            document = parse_strategy(canonical(document), max_bytes=MAX_BYTES)
            self._validate(document)
        except (MalformedStrategy, KeyError, TypeError, ValueError) as refused:
            if isinstance(refused, UnifiedRefused):
                raise
            raise UnifiedRefused("construction_unclassified") from None
        self._raw = canonical(document)

    @staticmethod
    def _validate(doc):
        if (
            set(doc) != FIELDS
            or doc["schema"] not in {LEGACY_SCHEMA, SCHEMA}
            or doc["scope"] != "DEVELOPMENT_SHADOW_ONLY"
        ):
            raise UnifiedRefused("construction_unclassified")
        if any(
            type(doc[k]) is not str or not doc[k]
            for k in ("version", "registry_version", "challenge")
        ) or not SHA.fullmatch(doc["base_contract_digest"]):
            raise UnifiedRefused("construction_unclassified")
        if (
            not _strings(doc["families"])
            or not doc["families"]
            or not _strings(doc["common_checks"])
        ):
            raise UnifiedRefused("construction_unclassified")
        if doc["ceiling"] is not None and (
            type(doc["ceiling"]) is not int or not 0 <= doc["ceiling"] <= 4
        ):
            raise UnifiedRefused("construction_unclassified")
        if type(doc["base_fields"]) is not dict or any(
            type(k) is not str or not _field(v) for k, v in doc["base_fields"].items()
        ):
            raise UnifiedRefused("construction_unclassified")
        if type(doc["types"]) is not list:
            raise UnifiedRefused("construction_unclassified")
        names, field_names = set(), set()
        for row in doc["types"]:
            if (
                type(row) is not dict
                or set(row) != TYPE_FIELDS
                or type(row["type"]) is not str
                or not row["type"]
                or row["type"] in names
            ):
                raise UnifiedRefused("construction_unclassified")
            names.add(row["type"])
            if (
                type(row["label"]) is not int
                or row["label"] not in (1, 2, 3, 4)
                or row["open"] not in ("INTERNAL", "EXTERNAL")
                or type(row["within_ceiling"]) is not bool
            ):
                raise UnifiedRefused("construction_unclassified")
            if row["owner_acceptance"] is not None and (
                type(row["owner_acceptance"]) is not str
                or not row["owner_acceptance"].startswith("OWNER-")
            ):
                raise UnifiedRefused("construction_unclassified")
            if row["open"] == "EXTERNAL" and row["owner_acceptance"] is None:
                raise UnifiedRefused("construction_unclassified")
            if (
                type(row["fields"]) is not dict
                or not row["fields"]
                or set(row["fields"]) & field_names
                or any(not _field(v) for v in row["fields"].values())
            ):
                raise UnifiedRefused("construction_unclassified")
            field_names.update(row["fields"])
            if (
                type(row["checks"]) is not list
                or not row["checks"]
                or any(
                    type(c) is not dict
                    or set(c) != {"id", "status"}
                    or type(c["id"]) is not str
                    or not c["id"]
                    or c["status"] not in ("PASS", "FAIL", "UNAVAILABLE")
                    for c in row["checks"]
                )
            ):
                raise UnifiedRefused("construction_unclassified")
            if type(row["arms"]) is not list:
                raise UnifiedRefused("construction_unclassified")
            arms = set()
            for arm in row["arms"]:
                if (
                    type(arm) is not dict
                    or set(arm) != ARM_FIELDS
                    or arm["name"] in arms
                    or (arm["name"] is not None and type(arm["name"]) is not str)
                    or type(arm["variant"]) is not str
                    or not SHA.fullmatch(arm["digest"])
                    or set(arm["fields"]) != set(row["fields"])
                    or any(not _field(v) for v in arm["fields"].values())
                    or type(arm["bounds"]) is not list
                    or (
                        arm["expression"] is not None
                        and type(arm["expression"]) is not dict
                    )
                ):
                    raise UnifiedRefused("construction_unclassified")
                if any(
                    arm["fields"][k]["default"] != row["fields"][k]["default"]
                    for k in row["fields"]
                ):
                    raise UnifiedRefused("construction_unclassified")
                if any(
                    f["kind"] == "expression" for f in arm["fields"].values()
                ) and not _profile(arm["expression"]):
                    raise UnifiedRefused("construction_unclassified")
                if type(arm["requirements"]) is not list or any(
                    type(r) is not dict
                    or set(r) != {"when", "field", "op", "value"}
                    or not _strings(r["when"])
                    or not set(r["when"]) <= set(row["fields"])
                    or type(r["field"]) is not str
                    or r["field"] not in set(doc["base_fields"]) | set(row["fields"])
                    or r["op"] not in ("in", "not_in", "gt", "absent")
                    or (r["op"] in ("in", "not_in") and not _strings(r["value"]))
                    or (r["op"] == "gt" and not _number(r["value"]))
                    or (r["op"] == "absent" and r["value"] is not None)
                    for r in arm["requirements"]
                ):
                    raise UnifiedRefused("construction_unclassified")
                arms.add(arm["name"])
                if type(arm["external_allowed"]) is not bool:
                    raise UnifiedRefused("construction_unclassified")
            registered = {k: row[k] for k in ("type", "label", "fields", "arms")}
            if row["registration_digest"] != digest(registered):
                raise UnifiedRefused("construction_unclassified")

    @property
    def document(self):
        return json.loads(self._raw)

    @property
    def digest(self):
        return "sha256:" + hashlib.sha256(self._raw).hexdigest()

    def facts(self):
        doc = self.document
        return {
            "unified_digest": self.digest,
            "registry_version": doc["registry_version"],
            "scope": doc["scope"],
            "ceiling": doc["ceiling"],
            "types": [
                {
                    k: row[k]
                    for k in (
                        "type",
                        "label",
                        "open",
                        "within_ceiling",
                        "checks",
                        "registration_digest",
                    )
                }
                for row in doc["types"]
            ],
        }


def _within(value, field, family):
    if field["families"] is not None and family not in field["families"]:
        return False
    kind = field["kind"]
    if kind == "bool":
        return type(value) is bool
    if kind == "uint":
        return type(value) is int and field["low"] <= value <= field["high"]
    if kind == "float":
        return _number(value) and field["low"] <= value <= field["high"]
    if kind == "choice":
        return any(type(value) is type(v) and value == v for v in field["low"])
    if kind == "digest":
        return type(value) is str and SHA.fullmatch(value) is not None
    if kind == "pool":
        return _pool(value, field["low"])
    return type(value) is dict


def _pool(value, profile):
    if type(value) is not dict or not {"pool_version", "strata", "cases"} <= set(
        value
    ) <= {"pool_version", "strata", "cases", "box"}:
        return False
    version, strata, cases, box = (
        value.get(k) for k in ("pool_version", "strata", "cases", "box")
    )
    if (
        type(version) is not str
        or version not in profile["versions"]
        or type(cases) is not int
        or not 1 <= cases <= profile["versions"][version]
    ):
        return False
    if (
        type(strata) is not dict
        or not strata
        or any(
            k not in profile["parts"]
            or not _number(v)
            or not profile["weight"][0] <= v <= profile["weight"][1]
            for k, v in strata.items()
        )
        or not any(v > 0 for v in strata.values())
    ):
        return False
    box = {} if "box" not in value else box
    return type(box) is dict and all(
        k in profile["inputs"]
        and type(v) is list
        and len(v) == 2
        and all(_number(b) for b in v)
        and v[0] < v[1]
        for k, v in box.items()
    )


def _profile(profile):
    keys = {
        "operations",
        "terms",
        "time_terms",
        "max_nodes",
        "max_depth",
        "max_arity",
        "scale",
        "exponent",
        "cap_at",
        "excess_over",
        "expm1_cap",
        "const",
    }
    return (
        type(profile) is dict
        and set(profile) == keys
        and all(_strings(profile[k]) for k in ("operations", "terms", "time_terms"))
        and all(
            type(profile[k]) is int and 1 <= profile[k] <= MAX_BYTES
            for k in ("max_nodes", "max_depth", "max_arity")
        )
        and all(
            type(profile[k]) is list
            and len(profile[k]) == 2
            and all(_number(v) for v in profile[k])
            and profile[k][0] <= profile[k][1]
            for k in (
                "scale",
                "exponent",
                "cap_at",
                "excess_over",
                "expm1_cap",
                "const",
            )
        )
    )


def _expression(node, profile):
    """Only structural arm selection; no expression compilation/evaluation."""
    count = 0

    def visit(item, depth):
        nonlocal count
        count += 1
        if (
            count > profile["max_nodes"]
            or depth > profile["max_depth"]
            or type(item) is not dict
        ):
            raise ValueError
        if set(item) == {"term"}:
            if item["term"] in profile["terms"]:
                return "case"
            if item["term"] in profile["time_terms"]:
                return "time"
            raise ValueError
        if set(item) == {"const"} and "const" in profile["operations"]:
            if (
                not _number(item["const"])
                or not profile["const"][0] <= item["const"] <= profile["const"][1]
            ):
                raise ValueError
            return None
        op = item.get("op")
        if op not in profile["operations"] or op == "const":
            raise ValueError
        if op in {"add", "mul", "max", "min", "div", "sub"}:
            args = item.get("args")
            if (
                set(item) != {"op", "args"}
                or type(args) is not list
                or not (
                    len(args) == 2
                    if op in {"div", "sub"}
                    else 2 <= len(args) <= profile["max_arity"]
                )
            ):
                raise ValueError
            sorts = {visit(child, depth + 1) for child in args} - {None}
            if len(sorts) > 1:
                raise ValueError
            return next(iter(sorts), None)
        if op in {"mean_t", "max_t"}:
            if (
                set(item) != {"op", "arg", "over"}
                or item["over"] not in {"voltage", "temperature", "both"}
                or visit(item["arg"], depth + 1) != "time"
            ):
                raise ValueError
            return "case"
        knobs = {
            "scale": ("by", "scale"),
            "pow": ("exponent", "exponent"),
            "cap": ("at", "cap_at"),
            "excess": ("over", "excess_over"),
            "expm1": ("cap", "expm1_cap"),
        }
        if op in knobs:
            name, bounds = knobs[op]
            if (
                set(item) != {"op", "arg", name}
                or not _number(item[name])
                or not profile[bounds][0] <= item[name] <= profile[bounds][1]
            ):
                raise ValueError
        elif op not in {"log1p", "sqrt", "neg", "exp"} or set(item) != {"op", "arg"}:
            raise ValueError
        return visit(item["arg"], depth + 1)

    try:
        return visit(node, 1) != "time"
    except (KeyError, TypeError, ValueError):
        return False


def _input(strategy):
    try:
        raw = strategy if type(strategy) in (str, bytes) else canonical(strategy)
        parsed = parse_strategy(raw, max_bytes=MAX_BYTES)
    except MalformedStrategy as refused:
        raise UnifiedRefused(refused.code) from None
    result = dry_validate(parsed)
    if not result.ok:
        raise UnifiedRefused("strategy_refused")
    return parsed


def _requirements(arm, values, base_fields):
    fields = {**base_fields, **arm["fields"]}
    for rule in arm["requirements"]:
        if not any(
            k in values and values[k] != fields[k]["default"] for k in rule["when"]
        ):
            continue
        value = values.get(rule["field"], fields[rule["field"]]["default"])
        op, expected = rule["op"], rule["value"]
        if (
            (op == "in" and value not in expected)
            or (op == "not_in" and value in expected)
            or (op == "gt" and (not _number(value) or value <= expected))
            or (op == "absent" and rule["field"] in values)
        ):
            return False
    return True


def derive(strategy, unified_contract):
    """Content-derived observational binding; grants no opening/admission."""
    if type(unified_contract) is not UnifiedContract:
        raise UnifiedRefused("construction_unclassified")
    strategy = _input(strategy)
    doc = unified_contract.document
    if strategy["challenge_id"] != doc["challenge"]:
        raise UnifiedRefused("challenge_mismatch")
    if strategy["backbone"] not in doc["families"]:
        raise UnifiedRefused("backbone_not_in_contract")
    values, family = strategy["parameters"], strategy["backbone"]
    widened = {name: row for row in doc["types"] for name in row["fields"]}
    if set(values) - set(doc["base_fields"]) - set(widened):
        raise UnifiedRefused("parameter_unknown")
    for name, value in values.items():
        if name not in widened and not _within(value, doc["base_fields"][name], family):
            raise UnifiedRefused("parameter_refused")
    used = [
        row
        for row in doc["types"]
        if any(
            name in values
            and (
                type(values[name]) is not type(field["default"])
                or values[name] != field["default"]
            )
            for name, field in row["fields"].items()
        )
    ]
    arms = {}
    for row in doc["types"]:
        # Even an explicitly supplied default must have the registered type.
        present = {k: v for k, v in values.items() if k in row["fields"]}
        if row in used and not row["arms"]:
            raise UnifiedRefused("construction_type_unregistered")
        matches = [
            arm
            for arm in row["arms"]
            if _requirements(arm, values, doc["base_fields"])
            and all(
                _within(v, arm["fields"][k], family)
                and (
                    v is None
                    or arm["fields"][k]["kind"] != "expression"
                    or _expression(v, arm["expression"])
                )
                for k, v in present.items()
            )
        ]
        if present and not matches:
            raise UnifiedRefused("construction_unclassified")
        if row in used:
            chosen = matches[0]
            arms[row["type"]] = {
                "arm": chosen["name"],
                "variant": chosen["variant"],
                "variant_digest": chosen["digest"],
            }
    if len(used) > 1 and doc["schema"] == LEGACY_SCHEMA:
        raise UnifiedRefused("construction_combination_unregistered")
    return {
        "schema": (
            LEGACY_BINDING_SCHEMA if doc["schema"] == LEGACY_SCHEMA else BINDING_SCHEMA
        ),
        "unified_digest": unified_contract.digest,
        "registry_version": doc["registry_version"],
        "change_set": [row["type"] for row in used],
        "arms": arms,
        "derived_label": max((row["label"] for row in used), default=0),
    }


def classify(strategy, unified_contract):
    """Public pre-sign preview; pure data, with closed refusal and plain reason."""
    try:
        binding = derive(strategy, unified_contract)
        doc = unified_contract.document
        used = [row for row in doc["types"] if row["type"] in binding["change_set"]]
        checks = doc["common_checks"] + [c["id"] for row in used for c in row["checks"]]
        notices = []
        for row in used:
            refusal, reason = None, None
            if (
                doc["ceiling"] is None
                or row["label"] > doc["ceiling"]
                or not row["within_ceiling"]
            ):
                refusal = "construction_beyond_ceiling"
                reason = (
                    "The registered ceiling does not permit this construction type."
                )
            elif (
                row["open"] != "EXTERNAL"
                or not next(
                    arm
                    for arm in row["arms"]
                    if arm["digest"] == binding["arms"][row["type"]]["variant_digest"]
                )["external_allowed"]
            ):
                refusal = "construction_type_not_open:" + row["type"]
                reason = (
                    "This construction type is INTERNAL; external submission is closed."
                )
            elif any(c["status"] != "PASS" for c in row["checks"]):
                refusal = "construction_type_closed:" + row["type"]
                reason = "A required construction check is unavailable or has failed."
            if refusal:
                notices.append({"type": row["type"], "code": refusal, "reason": reason})
        if doc["schema"] == LEGACY_SCHEMA:
            return {
                "change_set": binding["change_set"],
                "label": binding["derived_label"],
                "checks": list(dict.fromkeys(checks)),
                "binding": binding,
                "refusal": notices[0]["code"] if notices else None,
                "reason": notices[0]["reason"] if notices else None,
            }
        required = next(
            (row for row in used if any(c["status"] != "PASS" for c in row["checks"])),
            None,
        )
        return {
            "change_set": binding["change_set"],
            "label": binding["derived_label"],
            "checks": list(dict.fromkeys(checks)),
            "binding": binding,
            "refusal": (
                "construction_type_closed:" + required["type"] if required else None
            ),
            "reason": (
                "A required construction check is unavailable or has failed."
                if required
                else None
            ),
            "notices": notices,
            "authority": "CLASSIFICATION_ONLY_REBUILD_REQUIRED",
        }
    except UnifiedRefused as refused:
        return {
            "change_set": None,
            "label": None,
            "checks": [],
            "binding": None,
            "refusal": refused.code,
            "reason": "This strategy does not match the registered construction contract.",
        }


def verify_binding(strategy, unified_contract, binding):
    derived = derive(strategy, unified_contract)
    if canonical(derived) != canonical(binding):
        raise UnifiedRefused("construction_binding_mismatch")
    return derived


def commitment(strategy, unified_contract):
    """H(challenge, unified digest, canonical strategy digest), without a level.

    A digest is not permission to sign or submit: callers must check classify.
    This observational library never calls a signer or an intake.
    """
    strategy = _input(strategy)
    derive(strategy, unified_contract)
    return digest(
        {
            "challenge": unified_contract.document["challenge"],
            "unified_digest": unified_contract.digest,
            "canonical_strategy_digest": digest(strategy),
        }
    )
