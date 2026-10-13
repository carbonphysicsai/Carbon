"""Battery's INTERNAL unified shadow contract, assembled from pinned public data.

No compiler or scientific acceptance is imported or granted. The pure classifier
also works with contracts for other Challenges. Intake wiring belongs to PLT-16b.
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.construction.unified import SCHEMA, UnifiedContract, UnifiedRefused, digest
from carbon.reconstruction import capability_registry as cr

TYPE_NAMES = {1: "loss_expressions", 2: "optimizer_and_data", 3: "numerics", 4: "graph"}
EXPECTED = {
    1: {"loss_expressions"},
    2: {"muon_spectral", "pool_selection"},
    3: {"quasi_newton_family", "line_search"},
    4: {"composition_graphs"},
}


def _field(kind, low=None, high=None, default=None, families=None):
    return {
        "kind": kind,
        "low": low,
        "high": high,
        "default": default,
        "families": families,
    }


def _expression(widened):
    core = next(w["bounds"] for w in widened if w["id"] == "objective.loss_expressions")
    profile = {
        **core["limits"],
        "operations": list(core["operations"]),
        "terms": list(core["terms"]),
        "time_terms": [],
    }
    # Unused bounds are zero, never invented production values. Only registered
    # operations can consult them; each granted permission supplies its bounds.
    for key in ("scale", "exponent", "cap_at", "excess_over", "expm1_cap", "const"):
        profile[key] = core.get(key, [0, 0])
    for w in widened:
        bounds = w["bounds"]
        for source, dest in (
            ("adds_operations", "operations"),
            ("adds_terms", "terms"),
            ("adds_time_terms", "time_terms"),
        ):
            profile[dest].extend(bounds.get(source, []))
        for key in ("scale", "exponent", "cap_at", "excess_over", "expm1_cap", "const"):
            if key in bounds:
                profile[key] = bounds[key]
    return profile


def _pool(bounds):
    versions = {}
    # Public manifests contain counts and digests only; no sample is loaded.
    for path in (Path(__file__).with_name("pools")).glob("public-pool-v*.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        pinned = digest(manifest)
        if pinned in bounds["pool_versions"]:
            versions[pinned] = sum(p["cases"] for p in manifest["parts"])
    if set(versions) != set(bounds["pool_versions"]):
        raise UnifiedRefused("construction_unclassified")
    return {
        "versions": versions,
        "parts": bounds["parts"],
        "inputs": bounds["box_inputs"],
        "weight": bounds["weight"],
    }


def _requirements(fields, level):
    rules = []

    def add(when, field, op, value):
        rules.append({"when": when, "field": field, "op": op, "value": value})

    if level == 1:
        add(["loss_expressions"], "backend", "in", ["jax"])
        for name in (
            "h1_weight",
            "h2_weight",
            "relative_loss",
            "spectral_weight",
            "time_weighting",
        ):
            add(["loss_expressions"], name, "absent", None)
    if level == 2:
        add(["muon_spectral"], "backend", "in", ["jax"])
        add(["muon_spectral"], "optimizer_family", "in", ["muon"])
        add(["muon_spectral"], "learning_rate_curve", "not_in", ["train_loss_plateau"])
    if level == 3:
        add(list(fields), "backend", "in", ["jax"])
        add(list(fields), "polish_steps", "gt", 0)
    return rules


def contract(directory=None):
    """Current battery contract; all widenings INTERNAL, ceiling HUMAN_INPUT.

    Changing a policy, current registry order, health/opening facts, or base
    contract changes the unified digest. Missing/moved registrations fail closed.
    """
    base = cr.contract(cr.BATTERY_CHALLENGE)
    registry = cr.development_variant_registry(directory)
    base_fields = {
        c.capability_id.partition(".")[2]: _field(
            c.surface.kind,
            list(c.surface.low) if c.surface.kind == "choice" else c.surface.low,
            c.surface.high,
            c.surface.default,
            None if c.applies_to is None else list(c.applies_to),
        )
        for c in base.capabilities
        if c.surface is not None and c.status is cr.Status.REBUILDABLE_DEVELOPMENT
    }
    rows = []
    for level, name in TYPE_NAMES.items():
        arms = []
        for entry in registry["current"]:
            if entry["challenge"] != base.token or entry["level"] != level:
                continue
            document = cr.development_variant_document(entry["version"], directory)
            if (
                document["base_contract"]["digest"] != base.digest
                or document["challenge"] != base.token
                or document["level"] != level
                or document["participant_code"] is not False
                or document["schema"] != "carbon.construction-development-variant.v1"
                or document["scope"] != "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS"
                or document["status"] != "REGISTERED_DEVELOPMENT_POLICY"
            ):
                raise UnifiedRefused("construction_unclassified")
            fields = {}
            for widened in document["widened"]:
                bounds, surface = widened["bounds"], widened["surface"]
                if bounds.get("permission_only"):
                    continue
                field = widened["id"].partition(".")[2]
                if surface is not None:
                    fields[field] = _field(*surface[1:], families=widened["applies_to"])
                elif field == "loss_expressions":
                    fields[field] = _field("expression", families=widened["applies_to"])
                elif field == "pool_selection":
                    fields[field] = _field(
                        "pool", low=_pool(bounds), families=widened["applies_to"]
                    )
                elif field == "composition_graphs":
                    fields[field] = _field("digest", families=widened["applies_to"])
                else:
                    raise UnifiedRefused("construction_unclassified")
            if set(fields) != EXPECTED[level]:
                raise UnifiedRefused("construction_unclassified")
            arms.append(
                {
                    "name": entry.get("arm"),
                    "variant": entry["version"],
                    "digest": registry["versions"][entry["version"]],
                    "fields": fields,
                    "expression": (
                        _expression(document["widened"]) if level == 1 else None
                    ),
                    "bounds": document["widened"],
                    "requirements": _requirements(fields, level),
                    "external_allowed": not any(
                        w["bounds"].get("use") == "attack panel only"
                        for w in document["widened"]
                    ),
                }
            )
        if not arms:
            raise UnifiedRefused("construction_type_unregistered")
        row = {
            "type": name,
            "label": level,
            "fields": arms[0]["fields"],
            "arms": arms,
            "open": "INTERNAL",
            "owner_acceptance": None,
            "within_ceiling": False,
            "checks": [
                {
                    "id": f"L{level}:registered-compiler-and-security",
                    "status": "UNAVAILABLE",
                }
            ],
        }
        row["registration_digest"] = digest(
            {k: row[k] for k in ("type", "label", "fields", "arms")}
        )
        rows.append(row)
    return UnifiedContract(
        {
            "schema": SCHEMA,
            "version": "battery-unified-shadow-v1",
            "registry_version": digest(registry),
            "challenge": base.token,
            "base_contract_digest": base.digest,
            "families": [f for f, _ in cr.rebuildable_families(base.token)],
            "base_fields": base_fields,
            "types": rows,
            "ceiling": None,
            "common_checks": ["G-FEAS", "B15"],
            "scope": "DEVELOPMENT_SHADOW_ONLY",
        }
    )
