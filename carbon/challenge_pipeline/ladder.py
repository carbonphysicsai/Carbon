"""The construction ladder: how a Challenge's construction freedom grows.

Authority: `Design_Specs/Challenge_Admission.md` §3 (planning levels 0-5) and
the Challenge Roadmap's construction ladder (rev 2.2, OWNER-CHALLENGE-ROADMAP-03).
Every Challenge starts at Level 0, its pinned recipe and registered operations,
and climbs one level at a time in internal testing. The owners then choose
its best construction level, and the Challenge is frozen, locked and opened
to miners at that level. Nothing here is battery-specific: a Challenge
supplies its registered construction contract token, its expansion records
(`carbon/reconstruction/expansions/<challenge>/NNNN.json`) and the test that
shows Carbon rebuilds each level it reaches.

A pipeline record's `construction` block is checked against these rules:

- **Levels are contiguous from 0.** A level not listed is NOT_RUN, never a
  pass. The record's `level` is the highest listed one.
- **A level is reached only with its reconstruction** (OWNER-GRAPHITE-02): it
  names the expansion record that opened it and the test that shows Carbon
  rebuilds it, and both are in the repository.
- **A level above 0 starts from Graphite's accepted proposal**
  (`proposals.py`). Graphite proposes every level's capabilities, and the
  construction contract owner accepts them.
- **Climb one level at a time.** Every level below the current one is TESTED or
  FROZEN, with its evidence.
- **The current level names the newest expansion record.** A newer record means
  the contract widened or narrowed after the pipeline last looked, and the
  record is stale until it is reviewed.
- **The climb is internal; miners get the chosen level** (`LAUNCH`). `chosen`
  is null until the owners choose the best level internal testing supports.
  It must be a TESTED or FROZEN level at or below `level`. Only the chosen
  level may be FROZEN, because the frozen run, the lock and the miners' opening
  all happen there.
- **TESTED and FROZEN rest on unconditional evidence**
  (OWNER-GRAPHITE-TEST-WAVE-03 §2, `conditional-evidence.v1`). Exploration
  continues past an open finding, but a result tagged with open findings is
  never a level's TESTED or FROZEN evidence.

These checks keep a record coherent. They do not open a level, judge whether a
widening was wise or replace the admission ledger's own rule that no expansion
follows a finding (`admission_expansion_after_finding`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from carbon.challenge_readiness import conditional_evidence

#: Admission §3's planning levels, word for word.
LEVELS = {
    0: "Current challenge recipe and registered operations",
    1: "Custom loss expressions using a bounded operation set",
    2: "Training schedules, optimisers and permitted TRAIN sampling",
    3: "Training-time numerical routines such as preconditioners",
    4: "New architectures exporting through a constrained inference interface",
    5: "Custom inference in an independently isolated execution stage",
}
STATES = ("OPEN", "TESTED", "FROZEN")
NOT_RUN = "NOT_RUN"
EXPANSIONS = "carbon/reconstruction/expansions"
ENTRY_KEYS = {
    "level",
    "state",
    "proposal",
    "expansion_record",
    "reconstruction",
    "evidence",
}
TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RECORD_NAME = re.compile(r"^\d{4}\.json$")
PROPOSALS = "carbon/challenge_pipeline/proposals"

#: The climb procedure (Admission §3 and the Graphite admission handoff §8),
#: run for every level above 0 before it may be TESTED.
CLIMB_PROCEDURE = (
    (
        "Graphite proposes the level's capabilities for this Challenge, with their bounds, "
        "the research behind them, the reconstruction work each needs and the attack surface "
        "it opens; the construction contract owner accepts or declines the proposal."
    ),
    "Record the changed contract and permissions as an expansion record.",
    "Ship Carbon's reconstruction for the new level, with a test that Carbon rebuilds it.",
    "Run valid constructions under the previous and the expanded profile.",
    "Run matched adversarial budgets under both profiles.",
    "Remove the new permission and repeat the comparison (ablation).",
    "Test interactions with earlier permissions (combined-permission attacks).",
    "Reconstruct promising valid submissions on clean workers.",
)

#: After internal testing (owner, 2026-10-02: "This is all internal testing. We
#: choose a best construction level. Then lock and open challenge to miners!").
#: The climb runs on development-only contracts that only Carbon's own Graphite
#: campaigns read; miners only ever see the chosen, locked level.
LAUNCH = (
    (
        "Choose the Challenge's construction level: the owners choose the best level the "
        "internal evidence supports, which need not be the highest tested."
    ),
    (
        "Freeze at the chosen level, lock it, and open the Challenge to miners at that level "
        "once validators serve its contract: a miner sends a declarative recipe and the "
        "contract digest it was written against, the validator rebuilds it with the "
        "reconstruction pinned in its own Carbon version, and a digest it does not serve is "
        "refused."
    ),
)


class LadderError(ValueError):
    """A construction block breaks the ladder's rules."""


def empty():
    """The block of a family with no construction contract yet."""
    return {"challenge": None, "level": None, "chosen": None, "levels": []}


def newest_record(challenge, root):
    directory = Path(root) / EXPANSIONS / challenge
    names = sorted(
        p.name for p in directory.glob("*.json") if RECORD_NAME.match(p.name)
    )
    return f"{EXPANSIONS}/{challenge}/{names[-1]}" if names else None


def state_of(construction, level):
    for entry in construction["levels"]:
        if entry["level"] == level:
            return entry["state"]
    return NOT_RUN


def validate(construction, where, root):
    if not isinstance(construction, dict) or set(construction) != {
        "challenge",
        "level",
        "chosen",
        "levels",
    }:
        raise LadderError(
            f"{where}: construction is {{challenge, level, chosen, levels}}"
        )
    challenge, level, chosen, levels = (
        construction["challenge"],
        construction["level"],
        construction["chosen"],
        construction["levels"],
    )
    if not isinstance(levels, list):
        raise LadderError(f"{where}: levels is a list")
    if not levels:
        if level is not None or chosen is not None:
            raise LadderError(f"{where}: a level needs its levels listed")
        if challenge is not None and not TOKEN.match(str(challenge)):
            raise LadderError(f"{where}: challenge is a registered contract token")
        return construction
    if not (isinstance(challenge, str) and TOKEN.match(challenge)):
        raise LadderError(
            f"{where}: a Challenge on the ladder names its contract token"
        )
    numbers = [
        entry.get("level") if isinstance(entry, dict) else None for entry in levels
    ]
    if numbers != list(range(len(levels))) or len(levels) > len(LEVELS):
        raise LadderError(
            f"{where}: levels are contiguous from 0 (Admission §3 has 0-5)"
        )
    if level != numbers[-1]:
        raise LadderError(f"{where}: level is the highest listed level")
    prefix = f"{EXPANSIONS}/{challenge}/"
    for entry in levels:
        at = f"{where} level {entry['level']}"
        if set(entry) != ENTRY_KEYS:
            raise LadderError(f"{at}: keys are {sorted(ENTRY_KEYS)}")
        if entry["state"] not in STATES:
            raise LadderError(
                f"{at}: state is one of {STATES}; an unlisted level is {NOT_RUN}"
            )
        record = entry["expansion_record"]
        if not (isinstance(record, str) and record.startswith(prefix)):
            raise LadderError(f"{at}: names the expansion record under {prefix}")
        for kind in ("expansion_record", "reconstruction"):
            ref = entry[kind]
            if not (isinstance(ref, str) and ref and (Path(root) / ref).exists()):
                raise LadderError(
                    f"{at}: {kind} {ref!r} is not in the repository; a level is reached "
                    "only with its expansion record and Carbon's reconstruction for it"
                )
        proposal = entry["proposal"]
        expected = f"{PROPOSALS}/{challenge}/level-{entry['level']}.json"
        if proposal is None:
            if entry["level"] > 0:
                raise LadderError(
                    f"{at}: a level above 0 is reached only with Graphite's accepted "
                    f"proposal ({expected})"
                )
        else:
            path = Path(root) / str(proposal)
            if proposal != expected or not path.exists():
                raise LadderError(
                    f"{at}: the proposal is {expected}, in the repository"
                )
            if json.loads(path.read_text(encoding="utf-8")).get("status") != "ACCEPTED":
                raise LadderError(f"{at}: the proposal is not ACCEPTED")
        if entry["state"] in ("TESTED", "FROZEN"):
            evidence = entry["evidence"]
            if not (isinstance(evidence, str) and (Path(root) / evidence).exists()):
                raise LadderError(
                    f"{at}: {entry['state']} needs its evidence in the repository"
                )
            try:
                conditional_evidence.require_unconditional_path(
                    Path(root) / evidence, site=f"{at} {entry['state']} evidence"
                )
            except conditional_evidence.ConditionalEvidenceError as error:
                raise LadderError(
                    f"{at}: {error}; a level is {entry['state']} only on "
                    "unconditional evidence (conditional-evidence.v1)"
                ) from error
        elif entry["evidence"] is not None:
            raise LadderError(f"{at}: an OPEN level has no evidence yet")
    for entry in levels[:-1]:
        if entry["state"] == "OPEN":
            raise LadderError(
                f"{where}: level {entry['level']} is still OPEN; climb one level at a time"
            )
    if chosen is not None and (
        chosen not in numbers or state_of(construction, chosen) == "OPEN"
    ):
        raise LadderError(
            f"{where}: the chosen level is a TESTED or FROZEN level the climb reached"
        )
    for entry in levels:
        if entry["state"] == "FROZEN" and entry["level"] != chosen:
            raise LadderError(
                f"{where}: only the chosen level is FROZEN; the frozen run, the lock and "
                "the miners' opening happen at the chosen level"
            )
    newest = newest_record(challenge, root)
    if levels[-1]["expansion_record"] != newest:
        raise LadderError(
            f"{where}: the current level names {levels[-1]['expansion_record']}, but the "
            f"newest expansion record is {newest}; review the change and update the record"
        )
    return construction
