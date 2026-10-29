"""When a Challenge serves each miner's per-part feedback (schema v4).

PART_FEEDBACK_GRANULARITY section 3: a Challenge serves v4 only after the
custody feedback-leak attack on its launch version has passed. Until then it
serves v3. `part_feedback_attacks.json` holds, per ``<Challenge id>@<evaluation
version>``, the digest of the passed attack's evidence (aggregates only, kept in
custody); the Test Lead registers an entry after a pass, and the change is
reviewed and reserved (what miners see). An entry absent here means v3.

This module is standard library only, as the challenge-validator package is a
miner-reachable surface.
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.challenge_validator.interface import is_digest

REGISTRY = Path(__file__).with_name("part_feedback_attacks.json")
SCHEMA = "carbon.part-feedback.attack-registry.v1"


class RegistryInvalid(ValueError):
    """The registry file is not exactly the registered shape."""


def _load(path=REGISTRY):
    document = json.loads(Path(path).read_bytes())
    if (
        type(document) is not dict
        or set(document) != {"schema", "challenges"}
        or document["schema"] != SCHEMA
        or type(document["challenges"]) is not dict
    ):
        raise RegistryInvalid("part_feedback_registry_invalid")
    for key, entry in document["challenges"].items():
        if (
            type(key) is not str
            or key.count("@") != 1
            or not all(key.split("@"))
            or type(entry) is not dict
            or set(entry) != {"attack_digest"}
            or not is_digest(entry["attack_digest"])
        ):
            raise RegistryInvalid("part_feedback_registry_invalid")
    return document["challenges"]


def served(challenge_id, exam_version, *, path=REGISTRY):
    """Whether this Challenge serves v4 on this evaluation version: its leak attack
    passed and is registered. False means v3."""
    return f"{challenge_id}@{exam_version}" in _load(path)


def parts_registry(score_pack):
    """``{"A": [metric, ...], "D": [metric, ...]}``: the registered component
    metric names of the score pack's A and D legs, in the pack's order. Nothing
    else a pack carries is read."""
    legs = score_pack["legs"] if type(score_pack) is dict else None
    if type(legs) is not dict or not {"A", "D"} <= set(legs):
        raise RegistryInvalid("part_feedback_score_pack")
    return {
        name: [component["metric"] for component in legs[name]["components"]]
        for name in ("A", "D")
    }
