"""The one registered source of each Challenge's KOTH rule (KOTH-TAKEOVER-RULE-01).

`koth_rebuild_noise.json` holds each Challenge's registered rebuild noise,
`{value, measurement_digest}`, once its measurement record has been reviewed.
A Challenge absent from it has none: the comparator then decides UNAVAILABLE
and the private-exam ladder steps at eta. The KOTH comparator and the Ladder
both read this file, so the margin and the feedback step can never disagree.
Changing it is a reviewed, reserved change (rewards and what miners see).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from carbon.challenge_validator.bank_promotion import COMPARATOR_SCHEMA
from carbon.challenge_validator.interface import is_digest

REGISTRY = Path(__file__).with_name("koth_rebuild_noise.json")
SCHEMA = "carbon.koth.rebuild-noise-registry.v1"


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
        raise RegistryInvalid("koth_registry_invalid")
    from carbon.challenge_validator.exam_cap import registered_challenges

    known = registered_challenges()
    for challenge, noise in document["challenges"].items():
        if (
            # A plain lookup would silently ignore a misspelled id: refuse it.
            challenge not in known
            or type(noise) is not dict
            or set(noise) != {"value", "measurement_digest"}
            or type(noise["value"]) not in (int, float)
            or not math.isfinite(noise["value"])
            # Never 0: an all-equal measurement registers the total's resolution.
            or not noise["value"] > 0
            or not is_digest(noise["measurement_digest"])
        ):
            raise RegistryInvalid("koth_registry_invalid")
    return document["challenges"]


def rebuild_noise(challenge_id, *, path=REGISTRY):
    """The Challenge's registered `{value, measurement_digest}`, or None."""
    noise = _load(path).get(challenge_id)
    return None if noise is None else dict(noise)


def comparator(challenge_id, score_pack, accuracy_definition, *, path=REGISTRY):
    """The DEVELOPMENT comparator for one Challenge and its selected pack:
    the pack's score digest, its leg-minimum source entries (never contenders)
    and the registered rebuild noise (None means UNAVAILABLE)."""
    from carbon.scoring.physical_dual_pack import minimum_source_entry_ids

    return {
        "schema": COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": challenge_id,
        "score_pack_digest": score_pack["pack_digest"],
        "rebuild_noise": rebuild_noise(challenge_id, path=path),
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": minimum_source_entry_ids(accuracy_definition),
        "baseline_total": baseline_total(score_pack),
    }


def baseline_total(score_pack):
    """The total of a model sitting exactly on the pack's leg minimums: Carbon's
    baseline, the unpaid starting king the first crown must beat by the margin
    (OWNER-FIRST-CROWN-BEATS-BASELINE-01). None when the pack has no minimums."""
    legs = score_pack["legs"]
    a, d = legs["A"]["minimum"], legs["D"]["minimum"]
    if a is None or d is None:
        return None
    w = score_pack["value_weight"]
    if score_pack["combination"] == "weighted_arithmetic_mean":
        return (1 - w) * a + w * d
    if a == 0 or d == 0:
        return 0.0
    return min(a, d) * math.exp((1 - w) * math.log(a) + w * math.log(d))
