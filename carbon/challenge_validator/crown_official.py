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
#: The status a scored evaluation reads as where it holds no number it may rank by (`value`): not scored, so it neither wins
#: nor loses a crown.
UNRANKED = "INDETERMINATE_EVIDENCE"
#: What a version ranked by each number adds to its Ladder key, so a change of the number starts a fresh Ladder and no old
#: document is rewritten (`ladder_store.ladder_label`).
_LABEL = {TOTAL: "", ACCURACY: "+accuracy"}
#: The decimals every public place shows a version's number at, rounded DOWN, when it is ranked by each number (owner
#: G-LEAD-91, 24 Nov 2026: two on the accuracy board); None: as the page's own version shows a total.
_SHOWN = {TOTAL: None, ACCURACY: 2}
#: The reason of a crown decision that waits for its version's margin row (filed and swept like a queued crown).
CROWN_MARGIN_UNSET = "crown_margin_unset"
#: The noise slot's digest while no margin is registered: the comparison then only screens (margin 0) which contenders
#: would change the crown, and every such decision waits (`margin_unset`).
UNSET_DIGEST = (
    "sha256:" + hashlib.sha256(b"carbon.crown-official.margin-unset").hexdigest()
)


#: CROWN-CONFIRMATION-SET (owner, filed 2026-11-25T20:10:34Z, verbatim: "approved: new crowns on Motor 1.9, RB 2.0 and
#: joint must also hold on a small confirmation set, fingerprinted at open and published at close; shown scores stay on
#: the open set."). A version under it carries a ``confirmation`` block in its registry row (per pair, so no other door's
#: grading changes, `grading_scope`), ``{"number": "A", "first_crown": "open_rule_only", "tie": ...}`` when ruled; each
#: value is model-eval's ruling (door-code 8314 points (a) and (b), bank 8442), and an absent one makes the crowns it
#: decides wait (fail closed, never the open rule alone): an empty block ``{}`` is the owner's line with nothing ruled
#: yet. The joint exam's row carries one when its Challenge id and version are registered. ``number`` "A": the
#: confirmation number is the version's physics family value on the confirmation rows (`pool_exam`
#: ``capture["confirmation"]``), the only number those rows give. ``first_crown`` "open_rule_only": a first
#: crown (no king, so no king confirmation number) is decided on the open rule alone, the contender's own confirmation
#: record still required; absent, every first crown waits.
CONFIRMATION_NUMBERS = ("A",)
CONFIRMATION_FIRST_CROWN = ("open_rule_only",)
#: ``tie``: whether a contender whose confirmation number EQUALS the king's holds (``"confirms"``) or not
#: (``"not_confirmed"``: strictly greater needed). Model-eval's ruling (bank 8442: a table that changes only open-set
#: answers keeps the king's confirmation number exactly, so a tie that confirms can crown it with no real gain); absent,
#: every challenger crown waits.
CONFIRMATION_TIE = ("confirms", "not_confirmed")
#: The reasons a crown decision waits on its confirmation (filed and swept like a queued crown, `crown_pause_sweep`).
CROWN_CONFIRMATION_UNSET = "crown_confirmation_unset"
CROWN_CONFIRMATION_UNAVAILABLE = "crown_confirmation_unavailable"
#: The reason a contender that beat the open rule is not crowned: its confirmation number is below the king's, or its
#: confirmation answers were invalid. Decided, never refiled; the king stays. No number is attached to it anywhere.
CROWN_NOT_CONFIRMED = "crown_not_confirmed"
#: A grade's filed confirmation record (`confirmation_record`, `PoolStore.record_confirmation`).
CONFIRMATION_SCHEMA = "carbon.crown-confirmation.v1"
CONFIRMATION_STATUSES = ("MEASURED", "INVALID", "UNAVAILABLE")


def _confirmation_block(block):
    """The registered confirmation block, or `CrownOfficialInvalid`: ``number`` and ``first_crown`` each optional and
    each one of its registered values. An absent key is an unruled value: the crowns it decides wait."""
    if (
        type(block) is not dict
        or not set(block) <= {"number", "first_crown", "tie"}
        or ("number" in block and block["number"] not in CONFIRMATION_NUMBERS)
        or (
            "first_crown" in block
            and block["first_crown"] not in CONFIRMATION_FIRST_CROWN
        )
        or ("tie" in block and block["tie"] not in CONFIRMATION_TIE)
    ):
        raise CrownOfficialInvalid("crown_official_confirmation_malformed")
    return dict(block)


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
    confirmation = (
        _confirmation_block(entry["confirmation"])
        if type(entry) is dict and "confirmation" in entry
        else None
    )
    if (
        type(entry) is not dict
        or set(entry) - {"confirmation"} not in ({"margin"}, {"margin", "score"})
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
        # a version under the owner's confirmation line carries its block (empty while unruled: every crown waits)
        **({} if confirmation is None else {"confirmation": confirmation}),
    }


def score_of(challenge_id, version):
    """The recorded number this version is ranked by (`SCORES`): its row's, else the total. Read from the registry, so a
    process that installs nothing (the board operator, a tool) reads the same answer; a malformed registry refuses.
    """
    rule = registered(challenge_id, version)
    return TOTAL if rule is None else rule.get("score", TOTAL)


def value(model, score):
    """The ranked number of one evaluation's ``model_p``, or None when it keeps none or may not rank by it
    (`row_check_unknown`)."""
    if type(model) is not dict or (score == ACCURACY and row_check_unknown(model)):
        return None
    return model.get(_FIELD[score])


def row_check_unknown(model):
    """Whether a kept evaluation does not show that its answers are a function of each design alone (registry-a 7236, v2
    24 Nov 2026). The fresh row check of a menu version is no gate: a model whose answers change with the batch gets a
    design value of exactly 0.0 (`pool_menu.score`, MODEL_ROW_DEPENDENT) and keeps its accuracy half untouched. So a kept
    design value above zero is the record that the check passed; exactly zero (or none) does not say which it was, and
    such a grade is not ranked by its accuracy half: never given a number, never crowned.
    """
    design = model.get("design_benefit")
    return (
        type(design) not in (int, float)
        or isinstance(design, bool)
        or not math.isfinite(design)
        or design <= 0
    )


def reader(challenge_id, version):
    """``value`` of the number this version is ranked by, for the readers that take one; None for the total."""
    score = score_of(challenge_id, version)
    return None if score == TOTAL else lambda model: value(model, score)


def shown_decimals(challenge_id, version):
    """The decimals this version's number is shown at (`_SHOWN`)."""
    return _SHOWN[score_of(challenge_id, version)]


def label(challenge_id, version):
    """What this version adds to its Ladder key (`_LABEL`)."""
    return _LABEL[score_of(challenge_id, version)]


def ranked_row(graded, challenge_id, version):
    """The graded score row as the miner's own Ladder reads it: unchanged for a version ranked by its total; else a copy
    whose ``score`` is the ranked leg. A row with no score keeps none, and a scored row that may not rank by that leg
    (`value`) is one that does not count (`UNRANKED`): no number is shown and no improvement recorded.
    """
    score = score_of(challenge_id, version)
    if score == TOTAL or type(graded) is not dict or graded.get("score") is None:
        return graded
    legs = graded.get("legs")
    legs = legs if type(legs) is dict else {}
    ranked = value(
        {"physics_benefit": legs.get("A"), "design_benefit": legs.get("D")}, score
    )
    if ranked is None:
        return {**graded, "status": UNRANKED, "score": None}
    return {**graded, "score": ranked}


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
        + (
            f" confirmation={'on' if ACTIVE['confirmation'] else 'unset'}"
            if "confirmation" in ACTIVE
            else ""
        )
    )
    return ACTIVE


def confirmation_rule():
    """The served version's confirmation block (`_confirmation_block`), or None when its crowns need none."""
    return None if ACTIVE is None else ACTIVE.get("confirmation")


def confirm(first, candidate, incumbent):
    """The confirmation verdict of an official-score crown change, or None when the served version needs none.

    ``first`` is true for a crown with no king number to hold against (a first crown, or a challenger to a king that
    failed a mandatory gate), false for a challenger to a scored king; a plain dethrone never reads it. ``candidate`` /
    ``incumbent`` are each grade's filed confirmation record (`confirmation_record`, already checked by `bound_to`) or
    None. Returns ``(verdict, reason)``: ``("CONFIRMED", None)``; ``("WAIT", reason)`` for Carbon's gap
    (an unruled value, a record missing or unavailable: never the candidate's); ``("NOT_CONFIRMED",
    CROWN_NOT_CONFIRMED)`` when the contender's confirmation answers were invalid or its number is below the king's (or
    equal to it, unless the registered ``tie`` is ``"confirms"``).
    """
    rule = confirmation_rule()
    if rule is None:
        return None
    if rule.get("number") not in CONFIRMATION_NUMBERS:
        return "WAIT", CROWN_CONFIRMATION_UNSET
    if first and rule.get("first_crown") not in CONFIRMATION_FIRST_CROWN:
        return "WAIT", CROWN_CONFIRMATION_UNSET
    if not first and rule.get("tie") not in CONFIRMATION_TIE:
        return "WAIT", CROWN_CONFIRMATION_UNSET
    mine = _confirmation_status(candidate)
    if mine == "INVALID":
        return "NOT_CONFIRMED", CROWN_NOT_CONFIRMED
    if mine != "MEASURED":
        return "WAIT", CROWN_CONFIRMATION_UNAVAILABLE
    if first:
        return "CONFIRMED", None
    if _confirmation_status(incumbent) != "MEASURED":
        # the king's own record is missing or holds no number (his regrade on this pack files it): Carbon's, so it waits
        return "WAIT", CROWN_CONFIRMATION_UNAVAILABLE
    own, king = candidate["value"], incumbent["value"]
    if own > king or (own == king and rule["tie"] == "confirms"):
        return "CONFIRMED", None
    return "NOT_CONFIRMED", CROWN_NOT_CONFIRMED


def confirmation_record(captured, exam_key, dual_measurement_sha256):
    """One grade's private confirmation record from its measure's capture (`pool_exam` ``capture["confirmation"]``),
    bound to the grade's exam key and dual measurement; None when the measure kept none (no confirmation set). A capture
    that is not one of the measure's shapes is UNAVAILABLE, so the crown waits (Carbon's, never the candidate's)."""
    found = captured.get("confirmation") if type(captured) is dict else None
    if found is None:
        return None
    found = found if type(found) is dict else {}
    status, value = found.get("status"), found.get("value")
    if status not in CONFIRMATION_STATUSES or (
        status == "MEASURED" and not _finite(value)
    ):
        status = "UNAVAILABLE"
    reason = found.get("reason")
    return {
        "schema": CONFIRMATION_SCHEMA,
        "exam_key": exam_key,
        "dual_measurement_sha256": dual_measurement_sha256,
        "status": status,
        "value": float(value) if status == "MEASURED" else None,
        "sets_sha256": found.get("sets_sha256"),
        **({} if reason is None else {"reason": str(reason)}),
    }


def bound_to(record, evidence):
    """``record`` when it is the confirmation record of exactly the grade ``evidence`` binds (its dual measurement and
    its pack), else None: a record of another grade never stands in."""
    if (
        type(record) is not dict
        or type(evidence) is not dict
        or record.get("schema") != CONFIRMATION_SCHEMA
        or record.get("dual_measurement_sha256") is None
        or record.get("dual_measurement_sha256")
        != evidence.get("dual_measurement_receipt_sha256")
        or record.get("exam_key") != evidence.get("evaluation_pack_digest")
    ):
        return None
    return record


def _finite(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _confirmation_status(record):
    if type(record) is not dict:
        return None
    status = record.get("status")
    if status == "MEASURED" and not _finite(record.get("value")):
        return None
    return status


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
    "CONFIRMATION_FIRST_CROWN",
    "CONFIRMATION_NUMBERS",
    "CONFIRMATION_SCHEMA",
    "CONFIRMATION_TIE",
    "CROWN_CONFIRMATION_UNAVAILABLE",
    "CROWN_CONFIRMATION_UNSET",
    "CROWN_MARGIN_UNSET",
    "CROWN_NOT_CONFIRMED",
    "RECORD_RULE",
    "REGISTRY",
    "SCHEMA",
    "SCORES",
    "TOTAL",
    "UNRANKED",
    "UNSET_DIGEST",
    "CrownOfficialInvalid",
    "bound_to",
    "comparator",
    "confirm",
    "confirmation_record",
    "confirmation_rule",
    "decided_by",
    "install",
    "label",
    "margin_unset",
    "ranked_row",
    "reader",
    "registered",
    "row_check_unknown",
    "score_of",
    "shown_decimals",
    "value",
]
