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
    BURGERS_CHALLENGE,
    CONTRACTS,
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


class _Vocabulary:
    """One Challenge's contract, indexed for verdicts (OD-8: per Challenge)."""

    def __init__(self, challenge):
        item = CONTRACTS[challenge]
        self.challenge, self.digest = challenge, item.digest
        self.entries = item.capabilities
        self.by_id = {c.capability_id: c for c in item.capabilities}
        self.fields = catalog_surfaces(challenge)
        self.families = dict(rebuildable_families(challenge))
        #: Registry entries a parameter key or backbone name can name.
        self.by_name = {}
        for c in item.capabilities:
            self.by_name.setdefault(c.capability_id.partition(".")[2], c)


_VOCABULARIES = {token: _Vocabulary(token) for token in CONTRACTS}
_BURGERS = _VOCABULARIES[BURGERS_CHALLENGE]


def _nearest(text, choices):
    """Registered suggestions for text Carbon does not recognize. Only the
    suggestions are returned, never the text."""
    if type(text) is not str:
        return []
    return difflib.get_close_matches(text, sorted(choices), n=3, cutoff=0.6)


def availability(capability):
    """One capability's availability in the design-check vocabulary.

    What launch shows at the moment of choosing and what check-design answers
    for a design are the same verdicts, from this one function.
    """
    if capability.status is Status.REBUILDABLE_DEVELOPMENT:
        return {"verdict": SUPPORTED, "capability": capability.capability_id}
    return _registered(capability)


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


def _backbone(value, vocabulary=_BURGERS):
    if value in vocabulary.families:
        return {
            "verdict": SUPPORTED,
            "capability": f"model_family.{value}",
            "lab_kind": vocabulary.families[value],
        }
    capability = vocabulary.by_name.get(value) if type(value) is str else None
    if capability is not None and capability.dimension is Dimension.MODEL_FAMILY:
        return _registered(capability)
    return {
        "verdict": REFUSED,
        "reason": "unrecognized",
        "nearest": _nearest(value, vocabulary.families),
    }


def _field(key, backbone, vocabulary=_BURGERS):
    if key in vocabulary.fields:
        applies = vocabulary.fields[key][5]
        capability = next(
            c.capability_id
            for c in vocabulary.entries
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
    capability = vocabulary.by_name.get(key)
    if (
        capability is not None
        and capability.status is not Status.REBUILDABLE_DEVELOPMENT
    ):
        return _registered(capability)
    return {
        "verdict": REFUSED,
        "reason": "unrecognized",
        "nearest": _nearest(key, set(vocabulary.fields) | set(vocabulary.by_name)),
    }


def _requested(value, vocabulary=_BURGERS):
    capability = vocabulary.by_id.get(value) if type(value) is str else None
    if capability is None:
        return {
            "verdict": REFUSED,
            "reason": "unrecognized",
            "nearest": _nearest(value, vocabulary.by_id),
        }
    if capability.status is Status.REBUILDABLE_DEVELOPMENT:
        return {"verdict": SUPPORTED, "capability": capability.capability_id}
    return _registered(capability)


def _rebuild_battery(strategy):
    """The battery contract's compile: the same compiler, its own catalog."""
    from carbon.battery.compile import compile_recipe
    from carbon.battery.contracts import (
        IMPLEMENTATION_ID,
        IMPLEMENTATION_VERSION,
        implementation_digest,
    )

    from .research_catalog import RecipeRejected

    try:
        _, recipe = compile_recipe(strategy)
    except RecipeRejected as rejected:
        return {
            "accepted": False,
            "issues": [
                {"code": i.code, "path": i.path} for i in rejected.rejected.issues
            ],
        }
    return {
        "accepted": True,
        "canonical": {
            name: {
                "value": value,
                "source": "selected" if name in recipe.supplied else "defaulted",
            }
            for name, value in recipe.values
        },
        "implementation": {
            "family": recipe.family,
            "implementation_id": IMPLEMENTATION_ID,
            "implementation_version": IMPLEMENTATION_VERSION,
            "implementation_digest": implementation_digest(),
            "recipe_digest": recipe.recipe_digest,
            "plan_digest": recipe.plan_digest,
        },
    }


def _rebuild(strategy):
    """Compile with the validator's compiler; name every issue, or return the
    canonical design Carbon would rebuild."""
    if strategy.get("challenge_id") != BURGERS_CHALLENGE:
        return _rebuild_battery(strategy)
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

    # The strategy names its Challenge; only that Challenge's contract answers.
    vocabulary = _VOCABULARIES.get(strategy.get("challenge_id"))
    if vocabulary is None:
        return {
            "schema": CHECK_SCHEMA,
            "verdict": OVERALL[REFUSED],
            "challenge": {
                "verdict": REFUSED,
                "reason": "unrecognized",
                "nearest": _nearest(strategy.get("challenge_id"), _VOCABULARIES),
            },
            "evidence": "DEVELOPMENT_COMPILE_ONLY",
            "qualification": False,
        }
    backbone = _backbone(strategy.get("backbone"), vocabulary)
    # Positions in sorted key order: the miner knows their own keys, and the
    # verdict never repeats one Carbon does not recognize.
    keys = sorted(strategy["parameters"], key=str)
    fields = [
        {"position": i, **_field(key, strategy.get("backbone"), vocabulary)}
        for i, key in enumerate(keys)
    ]
    for item, key in zip(fields, keys):
        if item["verdict"] == SUPPORTED or "capability" in item:
            item["field"] = key  # a registered name, safe to repeat
    wanted = [
        {"position": i, **_requested(v, vocabulary)} for i, v in enumerate(requested)
    ]

    verdicts = [backbone["verdict"], *(f["verdict"] for f in fields)]
    verdicts += [w["verdict"] for w in wanted]
    worst = min(verdicts, key=_ORDER.index)
    result = {
        "schema": CHECK_SCHEMA,
        "verdict": OVERALL[worst],
        "backbone": backbone,
        "fields": fields,
        "requested": wanted,
        # The contract this verdict was given under; a submission records it
        # and a validator refuses a different one by name.
        "contract": {"challenge": vocabulary.challenge, "digest": vocabulary.digest},
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
