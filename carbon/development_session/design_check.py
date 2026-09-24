"""Can I submit this design? A verdict for every choice, before any training.

A miner describes a design in the full construction vocabulary: a strategy
(backbone and parameters) and, optionally, registry capability ids for choices
Carbon may not rebuild yet ("optimizer.lion", "training_data.curriculum").
The check answers per item from the construction capability registry, and -
only when every item is one Carbon rebuilds - compiles the strategy with the
same compiler the validator uses and returns the canonical design, resolved
defaults and implementation identities, or each named rebuild issue.

It never silently downgrades a design to the nearest supported recipe, and it
never repeats text a miner supplied that Carbon does not recognize: such an item
is identified by its position, with the nearest registered ids as suggestions.

The verdict is engineering state. "submittable" means Carbon rebuilds the design
in DEVELOPMENT; it is not qualification, admission or a promise of any score.
"""

from __future__ import annotations

import difflib
import json

from carbon.reconstruction.capability_registry import (
    REGISTRY,
    Blocker,
    Dimension,
    Status,
    catalog_surfaces,
    rebuildable_families,
)

CHECK_SCHEMA = "carbon.design-check.v1"
MAX_REQUESTED = 256

#: Item verdicts, and the overall verdict each one forces, most restrictive first.
EXCLUDED = "excluded"
OWNER = "needs_owner_decision"
NOT_YET = "not_yet_rebuildable"
REFUSED = "refused"
SUPPORTED = "supported"
_ORDER = (EXCLUDED, OWNER, NOT_YET, REFUSED, SUPPORTED)
OVERALL = {
    EXCLUDED: "excluded",
    OWNER: "needs_owner_decision",
    NOT_YET: "not_yet_rebuildable",
    REFUSED: "refused",
    SUPPORTED: "submittable",
}

_BY_ID = {c.capability_id: c for c in REGISTRY}
_FIELDS = catalog_surfaces()
_FAMILIES = dict(rebuildable_families())
#: Registry entries a parameter key or backbone name can name, by short name.
_BY_NAME = {}
for _c in REGISTRY:
    _BY_NAME.setdefault(_c.capability_id.partition(".")[2], _c)


def _nearest(text, choices):
    """Registered suggestions for text Carbon does not recognize. Only the
    suggestions are returned, never the text."""
    if type(text) is not str:
        return []
    return difflib.get_close_matches(text, sorted(choices), n=3, cutoff=0.6)


def _registered(capability):
    """The verdict for a registry entry Carbon does not rebuild."""
    verdict = {
        Blocker.EXCLUDED: EXCLUDED,
        Blocker.OWNER_DECISION: OWNER,
        Blocker.ENGINEERING: NOT_YET,
    }[capability.blocker]
    item = {
        "verdict": verdict,
        "capability": capability.capability_id,
        "status": capability.status.value,
        "blocker": capability.blocker.value,
    }
    if capability.trigger is not None:
        item["trigger"] = capability.trigger.value
    return item


def _backbone(value):
    if value in _FAMILIES:
        return {
            "verdict": SUPPORTED,
            "capability": f"model_family.{value}",
            "lab_kind": _FAMILIES[value],
        }
    capability = _BY_NAME.get(value) if type(value) is str else None
    if capability is not None and capability.dimension is Dimension.MODEL_FAMILY:
        return _registered(capability)
    return {
        "verdict": REFUSED,
        "reason": "unrecognized",
        "nearest": _nearest(value, _FAMILIES),
    }


def _field(key, backbone):
    if key in _FIELDS:
        applies = _FIELDS[key][5]
        capability = next(
            c.capability_id
            for c in REGISTRY
            if c.surface is not None and c.capability_id.endswith("." + key)
        )
        if applies is None or backbone in applies:
            return {"verdict": SUPPORTED, "capability": capability}
        return {
            "verdict": REFUSED,
            "reason": "not_applicable",
            "capability": capability,
            "families": list(applies),
        }
    capability = _BY_NAME.get(key)
    if (
        capability is not None
        and capability.status is not Status.REBUILDABLE_DEVELOPMENT
    ):
        return _registered(capability)
    return {
        "verdict": REFUSED,
        "reason": "unrecognized",
        "nearest": _nearest(key, set(_FIELDS) | set(_BY_NAME)),
    }


def _requested(value):
    capability = _BY_ID.get(value) if type(value) is str else None
    if capability is None:
        return {
            "verdict": REFUSED,
            "reason": "unrecognized",
            "nearest": _nearest(value, _BY_ID),
        }
    if capability.status is Status.REBUILDABLE_DEVELOPMENT:
        return {"verdict": SUPPORTED, "capability": capability.capability_id}
    return _registered(capability)


def _rebuild(strategy):
    """Compile with the validator's compiler; name every issue, or return the
    canonical design Carbon would rebuild."""
    from carbon.construction.model import SelectedSurface
    from carbon.reconstruction.catalogue import reconstruction_capabilities

    from .research_catalog import RecipeRejected, compile_recipe

    try:
        compiled, profile = compile_recipe(strategy)
    except RecipeRejected as rejected:
        return {
            "accepted": False,
            "issues": [
                {"code": i.code, "path": i.path} for i in rejected.rejected.issues
            ],
        }
    plan = compiled.construction_plan
    implementation = next(
        c
        for c in reconstruction_capabilities()
        if c.current_research_selection and c.backbone_kind == profile.backbone_kind
    )
    return {
        "accepted": True,
        "canonical": {
            s.surface_id: {
                "value": s.value.value,
                "source": "selected" if type(s) is SelectedSurface else "defaulted",
            }
            for s in plan.resolved_surfaces
            if hasattr(s, "value")
        },
        "implementation": {
            "backbone_id": implementation.backbone_id,
            "lab_kind": profile.backbone_kind,
            "implementation_id": implementation.implementation_id,
            "implementation_version": implementation.implementation_version,
            "implementation_digest": implementation.implementation_digest,
            "profile_digest": profile.profile_digest,
            "plan_digest": profile.plan_digest,
        },
    }


def check_design(design) -> dict:
    """The verdict for one design. Raises only for a malformed request."""
    if type(design) is not dict or not {"strategy"} <= set(design) <= {
        "strategy",
        "capabilities",
    }:
        raise ValueError("a design is {strategy, capabilities?}")
    strategy = design["strategy"]
    requested = design.get("capabilities", [])
    if type(strategy) is not dict or type(strategy.get("parameters")) is not dict:
        raise ValueError(
            "strategy is {schema_version, challenge_id, backbone, parameters}"
        )
    if type(requested) is not list or len(requested) > MAX_REQUESTED:
        raise ValueError(
            f"capabilities is a list of at most {MAX_REQUESTED} registry ids"
        )
    json.dumps(design, allow_nan=False)  # finite, plain JSON only

    backbone = _backbone(strategy.get("backbone"))
    # Positions in sorted key order: the miner knows their own keys, and the
    # verdict never repeats one Carbon does not recognize.
    keys = sorted(strategy["parameters"], key=str)
    fields = [
        {"position": i, **_field(key, strategy.get("backbone"))}
        for i, key in enumerate(keys)
    ]
    for item, key in zip(fields, keys):
        if item["verdict"] == SUPPORTED or "capability" in item:
            item["field"] = key  # a registered name, safe to repeat
    wanted = [{"position": i, **_requested(v)} for i, v in enumerate(requested)]

    verdicts = [backbone["verdict"], *(f["verdict"] for f in fields)]
    verdicts += [w["verdict"] for w in wanted]
    worst = min(verdicts, key=_ORDER.index)
    result = {
        "schema": CHECK_SCHEMA,
        "verdict": OVERALL[worst],
        "backbone": backbone,
        "fields": fields,
        "requested": wanted,
        "evidence": "DEVELOPMENT_COMPILE_ONLY",
        "qualification": False,
    }
    # Compile only a design made entirely of choices Carbon rebuilds: anything
    # else would be judged as a different design than the one described.
    if backbone["verdict"] == SUPPORTED and all(
        f["verdict"] == SUPPORTED for f in fields
    ):
        result["rebuild"] = _rebuild(strategy)
        if not result["rebuild"]["accepted"] and worst == SUPPORTED:
            result["verdict"] = OVERALL[REFUSED]
    return result
