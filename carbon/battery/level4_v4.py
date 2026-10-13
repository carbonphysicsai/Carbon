"""Prospective graph-v4 field semantics; pure data at import.

The submitted graph owns its architecture. Recipe width/depth remain valid
on ordinary recipes and historical v3, but are refused on a v4 graph recipe.
Pinned battery implementation and the graph reconstruction are unchanged.
"""

from __future__ import annotations

import json

VERSION = "battery-l4-graph-v4"
ARM = "inert_fields"
FIELD = "composition_graphs"
CAPABILITY = "hybrid.composition_graphs"
INERT_FIELDS = ("width", "depth")
FIELD_INERT = "level4_field_inert"


def check_strategy(strategy, granted):
    """The registered v4 compiler hook; never echoes a supplied value."""
    if CAPABILITY not in granted:
        return
    parameters = strategy.get("parameters")
    if type(parameters) is not dict or FIELD not in parameters:
        return
    issues = [
        (f"{FIELD_INERT}:{name}", "/parameters/" + name)
        for name in INERT_FIELDS
        if name in parameters
    ]
    if issues:
        from carbon.reconstruction.development_variants import VariantRefused

        raise VariantRefused(issues[0][0], issues=issues)


def variant_document(*, base=None):
    """Extend the existing graph policy prospectively, retaining every bound."""
    from . import level4

    document = level4.variant_document(version=VERSION, base=base)
    document["authority"] += "; PLT-18 Carbon Validator inert-fields ruling 2026-10-13"
    document["review"] = {
        "reviewer": "Carbon Validator, with Launchpad agreement",
        "record": (
            "PLT-18: prospectively refuse width/depth when composition_graphs "
            "sets the network; v3 and all containment/pinned implementations "
            "remain unchanged"
        ),
    }
    document["widened"][0]["bounds"]["inert_recipe_fields"] = list(INERT_FIELDS)
    return document


def starter_recipe():
    """A v4 recipe with the dead controls omitted; catalog defaults still apply."""
    from . import level4

    strategy = json.loads(json.dumps(level4.level0_strategies()["scaffold_mlp"]))
    for name in INERT_FIELDS:
        strategy["parameters"].pop(name, None)
    return strategy
