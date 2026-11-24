"""Crowns decided on the OFFICIAL grades, with no crown rebuild (owner 14 Nov, verbatim via the Lead: crown rebuilds dropped;
"No protection. New kings win. I don't need a queue of contenders building"; the margin ".0129").

THE DEFAULT FOR EVERY VERSION (owner rule of 14 Nov, every exam; Lead 17 Nov 2026): a receiver always installs it
(`install`). The margin is the version's owner-set row in `REGISTRY` (V2 ruling 17 Nov: never derived). A version with no
row yet still grades and counts exactly as before; only its crown decisions wait (`margin_unset`: `CROWN_MARGIN_UNSET`,
filed like a queued crown and decided by the sweep, in admission order, once the row lands with the next start).

The rule: a contender whose OFFICIAL total is greater than
the sitting king's OFFICIAL total plus the registered margin becomes king at once; a tie (within the margin) keeps the king.
Contenders are decided in queue order by the existing sweep (`crown_pause_sweep`, oldest-first; an undecided earlier one
holds later ones back), each against the king of its moment. That is exactly `bank_promotion.compare_private_pair` on the two
official grades with the margin in the comparator's noise slot; this module only switches off what follows it today:

- the crown multi-rebuild average (`crown_average`: the screening against the king's N-rebuild mean, the N rebuilds of the
  contender and the king's re-measure rebuilds): `install` sets ``crown_average.ACTIVE`` to None for the served version;
- the repeat gate (a second grade of every state the decision read): `bank_promotion.consider_private` applies the crown
  change directly in this mode.

WHICH RECORDED NUMBER RANKS a version (owner G-LEAD-83, 24 Nov 2026) is part of its row: ``"score": "A"`` ranks it by its
accuracy half (`SCORES`), the leg A every private evaluation already keeps beside its total (``model_p.physics_benefit``);
absent, the total, as every row before it. It changes no grade, no evaluation, no key and no old record: a decision reads
another recorded number, with the row's own margin on that number, and its private record says which. Every reader of the
ranked number (the crown decision, the king page, the board, the miner's own Ladder) asks this module; none names a version.

The operator's crown pause, the crown hold and the queue order are unchanged. Only a process that never installs the rule
(a tool, a test) has `ACTIVE` None and the old repeat-gate decision.
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


#: ``{"challenge", "version", "margin", "digest"}`` for the version this receiver serves (``margin`` and ``digest`` None
#: while the version has no row: `margin_unset`; plus ``score`` when it is not ranked by its total), or None in a process
#: that never installed it.
ACTIVE = None
#: The recorded number a version is ranked by: the total, or its accuracy half (a row's ``"score"``).
TOTAL, ACCURACY = "total", "A"
SCORES = (TOTAL, ACCURACY)
#: Where an evaluation's ``model_p`` keeps each (`private_evaluation_evidence`).
_FIELD = {TOTAL: "total_score", ACCURACY: "physics_benefit"}
#: What a version ranked by each number adds to its Ladder key, so a change of the number starts a fresh Ladder and no old
#: document is rewritten (`ladder_store.ladder_label`).
_LABEL = {TOTAL: "", ACCURACY: "+accuracy"}
#: The reason of a crown decision that waits for its version's margin row (filed and swept like a queued crown).
CROWN_MARGIN_UNSET = "crown_margin_unset"
#: The noise slot's digest while no margin is registered: the comparison then only screens (margin 0) which contenders
#: would change the crown, and every such decision waits (`margin_unset`).
UNSET_DIGEST = (
    "sha256:" + hashlib.sha256(b"carbon.crown-official.margin-unset").hexdigest()
)


def _entry_digest(key, entry):
    raw = json.dumps([SCHEMA, key, entry], sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def registered(challenge_id, version, *, path=None):
    """The registered official-score rule of ``challenge_id version``: ``{"margin", "digest"}`` (plus ``"score"`` when its
    entry names another number than the total), or None when the version has no entry. A registry that cannot be read, or
    an entry that is not exactly ``{"margin": a finite number in [0, 1)}`` with or without ``"score": "A"``, refuses (`CrownOfficialInvalid`): the receiver does not start on a malformed rule.
    """
    try:
        document = json.loads(Path(REGISTRY if path is None else path).read_bytes())
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
    score = entry.get("score", TOTAL) if type(entry) is dict else None
    if (
        type(entry) is not dict
        or set(entry) not in ({"margin"}, {"margin", "score"})
        # the total is the absent key, never spelled
        or (("score" in entry) and score != ACCURACY)
        or type(margin) not in (int, float)
        or isinstance(margin, bool)
        or not math.isfinite(margin)
        or not 0 <= margin < 1
    ):
        raise CrownOfficialInvalid("crown_official_entry_malformed")
    return {
        "margin": float(margin),
        "digest": _entry_digest(key, entry),
        **({} if score == TOTAL else {"score": score}),
    }


def score_of(challenge_id, version):
    """The recorded number this version is ranked by (`SCORES`): its row's, else the total. Read from the registry, so a
    process that installs nothing (the board operator, a tool) reads the same answer; a malformed registry refuses.
    """
    rule = registered(challenge_id, version)
    return TOTAL if rule is None else rule.get("score", TOTAL)


def value(model, score):
    """The ranked number of one evaluation's ``model_p``, or None when it keeps none."""
    return model.get(_FIELD[score]) if type(model) is dict else None


def reader(challenge_id, version):
    """``value`` of the number this version is ranked by, for the readers that take one; None for the total."""
    score = score_of(challenge_id, version)
    return None if score == TOTAL else lambda model: value(model, score)


def label(challenge_id, version):
    """What this version adds to its Ladder key (`_LABEL`)."""
    return _LABEL[score_of(challenge_id, version)]


def ranked_row(graded, challenge_id, version):
    """The graded score row as the miner's own Ladder reads it: unchanged for a version ranked by its total; else a copy
    whose ``score`` is the ranked leg. A row with no score keeps none."""
    score = score_of(challenge_id, version)
    if score == TOTAL or type(graded) is not dict or graded.get("score") is None:
        return graded
    legs = graded.get("legs")
    return {
        **graded,
        "score": legs.get(score) if type(legs) is dict else None,
    }


def decided_by(evidence):
    """The number a crown decision on this evaluation compares: the installed rule's, for every evaluation of the Challenge
    this receiver serves (a king carried from an earlier construction version is compared on the same number as the
    contender he meets, never on another)."""
    if (
        ACTIVE is None
        or type(evidence) is not dict
        or evidence.get("challenge") != ACTIVE["challenge"]
    ):
        return TOTAL
    return ACTIVE.get("score", TOTAL)


def install(challenge_id, version, *, path=None, log=None):
    """At receiver start, for the version it ACTUALLY serves: turn the official-score rule ON (and the crown average OFF),
    for every version: with its registered margin, or, with no row yet, margin None (`margin_unset`: its crowns wait).
    Logs ``crown_official_score=true margin=<value|unset>``.
    """
    global ACTIVE
    from carbon.challenge_validator import crown_average

    rule = registered(challenge_id, version, path=path) or {
        "margin": None,
        "digest": None,
    }
    ACTIVE = {"challenge": challenge_id, "version": version, **rule}
    # no crown rebuild of any kind: no screening vs a rebuild mean, no N-rebuild decision, no re-measure
    crown_average.ACTIVE = None
    say = log or (lambda line: print(line, flush=True))
    say(
        "crown_official_score=true"
        f" margin={'unset' if ACTIVE['margin'] is None else ACTIVE['margin']}"
        + (f" score={ACTIVE['score']}" if "score" in ACTIVE else "")
    )
    return ACTIVE


def margin_unset():
    """Whether the rule is installed and the served version has no margin row yet: its crown decisions wait."""
    return ACTIVE is not None and ACTIVE["margin"] is None


def comparator(registered_comparator):
    """The comparator the official-score rule decides with: the registered one with the rule's margin in its noise slot
    (``{"value": margin, "measurement_digest": the rule entry's digest}``), or None when the rule is off. (A receiver serves
    one version, the one `install` read the rule for; `bank_promotion._comparator` still checks the comparator is this
    evaluation's.)"""
    if ACTIVE is None or type(registered_comparator) is not dict:
        return None
    if ACTIVE["margin"] is None:
        # no row yet: margin 0 only SCREENS which contenders would change the crown; each such decision waits
        noise = {"value": 0.0, "measurement_digest": UNSET_DIGEST}
    else:
        noise = {"value": ACTIVE["margin"], "measurement_digest": ACTIVE["digest"]}
    ranked = {**registered_comparator, "rebuild_noise": noise}
    if ACTIVE.get("score", TOTAL) != TOTAL:
        # Carbon's baseline is a total: never compared with another number, so a first crown waits (no floor registered)
        ranked["baseline_total"] = None
    return ranked


__all__ = [
    "ACCURACY",
    "ACTIVE",
    "CROWN_MARGIN_UNSET",
    "RECORD_RULE",
    "REGISTRY",
    "SCHEMA",
    "SCORES",
    "TOTAL",
    "UNSET_DIGEST",
    "CrownOfficialInvalid",
    "comparator",
    "decided_by",
    "install",
    "label",
    "margin_unset",
    "ranked_row",
    "reader",
    "registered",
    "score_of",
    "value",
]
