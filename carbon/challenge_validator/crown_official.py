"""Crowns decided on the OFFICIAL grades, with no crown rebuild (owner 14 Nov, verbatim via the Lead: crown rebuilds dropped;
"No protection. New kings win. I don't need a queue of contenders building"; the margin ".0129").

The rule, for a version that registers it (`REGISTRY`, outside ``carbon/``): a contender whose OFFICIAL total is greater than
the sitting king's OFFICIAL total plus the registered margin becomes king at once; a tie (within the margin) keeps the king.
Contenders are decided in queue order by the existing sweep (`crown_pause_sweep`, oldest-first; an undecided earlier one
holds later ones back), each against the king of its moment. That is exactly `bank_promotion.compare_private_pair` on the two
official grades with the margin in the comparator's noise slot; this module only switches off what follows it today:

- the crown multi-rebuild average (`crown_average`: the screening against the king's N-rebuild mean, the N rebuilds of the
  contender and the king's re-measure rebuilds): `install` sets ``crown_average.ACTIVE`` to None for the served version;
- the repeat gate (a second grade of every state the decision read): `bank_promotion.consider_private` applies the crown
  change directly in this mode.

The operator's crown pause, the crown hold and the queue order are unchanged. A version without an entry: `ACTIVE` is None
and every crown decision is exactly as before.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "crown_official_score.json"
)
SCHEMA = "carbon.crown-official-score.v1"
#: The ``rule`` of an official-score crown's private verification record (filed beside the decision, read by
#: `winner_eligibility._averaged_crown` as the crown's verification in place of an N-rebuild average).
RECORD_RULE = "official_score"


class CrownOfficialInvalid(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


#: ``{"challenge", "version", "margin", "digest"}`` for the version this receiver serves, or None (off).
ACTIVE = None


def _entry_digest(key, entry):
    raw = json.dumps([SCHEMA, key, entry], sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def registered(challenge_id, version, *, path=REGISTRY):
    """The registered official-score rule of ``challenge_id version``: ``{"margin", "digest"}``, or None when the version
    has no entry. A registry that cannot be read, or an entry that is not exactly ``{"margin": a finite number in [0, 1)}``,
    refuses (`CrownOfficialInvalid`): the receiver does not start on a malformed rule.
    """
    try:
        document = json.loads(Path(path).read_bytes())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise CrownOfficialInvalid("crown_official_registry_unreadable") from exc
    if (
        type(document) is not dict
        or document.get("schema") != SCHEMA
        or type(document.get("versions")) is not dict
    ):
        raise CrownOfficialInvalid("crown_official_registry_malformed")
    key = f"{challenge_id} {version}"
    entry = document["versions"].get(key)
    if entry is None:
        return None
    margin = entry.get("margin") if type(entry) is dict else None
    if (
        type(entry) is not dict
        or set(entry) != {"margin"}
        or type(margin) not in (int, float)
        or isinstance(margin, bool)
        or not math.isfinite(margin)
        or not 0 <= margin < 1
    ):
        raise CrownOfficialInvalid("crown_official_entry_malformed")
    return {"margin": float(margin), "digest": _entry_digest(key, entry)}


def install(challenge_id, version, *, path=REGISTRY, log=None):
    """At receiver start, for the version it ACTUALLY serves: turn the official-score rule on (and the crown average OFF)
    when the version registers it, else off. Logs ``crown_official_score=<bool> margin=<value|none>``.
    """
    global ACTIVE
    from carbon.challenge_validator import crown_average

    rule = registered(challenge_id, version, path=path)
    ACTIVE = (
        None
        if rule is None
        else {"challenge": challenge_id, "version": version, **rule}
    )
    if ACTIVE is not None:
        # no crown rebuild of any kind in this mode: no screening vs a rebuild mean, no N-rebuild decision, no re-measure
        crown_average.ACTIVE = None
    say = log or (lambda line: print(line, flush=True))
    say(
        f"crown_official_score={str(ACTIVE is not None).lower()}"
        f" margin={'none' if ACTIVE is None else ACTIVE['margin']}"
    )
    return ACTIVE


def comparator(registered_comparator):
    """The comparator the official-score rule decides with: the registered one with the rule's margin in its noise slot
    (``{"value": margin, "measurement_digest": the rule entry's digest}``), or None when the rule is off. (A receiver serves
    one version, the one `install` read the rule for; `bank_promotion._comparator` still checks the comparator is this
    evaluation's.)"""
    if ACTIVE is None or type(registered_comparator) is not dict:
        return None
    return {
        **registered_comparator,
        "rebuild_noise": {
            "value": ACTIVE["margin"],
            "measurement_digest": ACTIVE["digest"],
        },
    }


__all__ = [
    "ACTIVE",
    "RECORD_RULE",
    "REGISTRY",
    "SCHEMA",
    "CrownOfficialInvalid",
    "comparator",
    "install",
    "registered",
]
