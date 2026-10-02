"""The construction ladder: how a Challenge's construction freedom grows.

Authority: `Design_Specs/Challenge_Admission.md` §3 (planning levels 0-5) and
the Challenge Roadmap's construction ladder (rev 2.2, OWNER-CHALLENGE-ROADMAP-03).
Every Challenge starts at Level 0, its pinned recipe and registered operations,
and climbs one level at a time. Nothing here is battery-specific: a Challenge
supplies its registered construction contract token, its expansion records
(`carbon/reconstruction/expansions/<challenge>/NNNN.json`) and the test that
shows Carbon rebuilds each level it reaches.

A pipeline record's `construction` block is checked against these rules:

- **Levels are contiguous from 0.** A level not listed is NOT_RUN, never a
  pass. The record's `level` is the highest listed one.
- **A level is reached only with its reconstruction** (OWNER-GRAPHITE-02): it
  names the expansion record that opened it and the test that shows Carbon
  rebuilds it, and both are in the repository.
- **Climb one level at a time.** Every level below the current one is TESTED or
  FROZEN, with its evidence.
- **The current level names the newest expansion record.** A newer record means
  the contract widened or narrowed after the pipeline last looked, and the
  record is stale until it is reviewed.

These checks keep a record coherent. They do not open a level, judge whether a
widening was wise or replace the admission ledger's own rule that no expansion
follows a finding (`admission_expansion_after_finding`).
"""

from __future__ import annotations

import re
from pathlib import Path

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
ENTRY_KEYS = {"level", "state", "expansion_record", "reconstruction", "evidence"}
TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RECORD_NAME = re.compile(r"^\d{4}\.json$")

#: The climb procedure (Admission §3 and the Graphite admission handoff §8),
#: run for every level above 0 before it may be TESTED.
CLIMB_PROCEDURE = (
    "Record the changed contract and permissions as an expansion record.",
    "Ship Carbon's reconstruction for the new level, with a test that Carbon rebuilds it.",
    "Run valid constructions under the previous and the expanded profile.",
    "Run matched adversarial budgets under both profiles.",
    "Remove the new permission and repeat the comparison (ablation).",
    "Test interactions with earlier permissions (combined-permission attacks).",
    "Reconstruct promising valid submissions on clean workers.",
    (
        "Open the level to miners only after a person locks it, and only once validators "
        "serve the new contract: a miner sends a declarative recipe and the contract digest "
        "it was written against, the validator rebuilds it with the reconstruction pinned in "
        "its own Carbon version, and a digest it does not serve is refused."
    ),
)


class LadderError(ValueError):
    """A construction block breaks the ladder's rules."""


def empty():
    """The block of a family with no construction contract yet."""
    return {"challenge": None, "level": None, "levels": []}


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
        "levels",
    }:
        raise LadderError(f"{where}: construction is {{challenge, level, levels}}")
    challenge, level, levels = (
        construction["challenge"],
        construction["level"],
        construction["levels"],
    )
    if not isinstance(levels, list):
        raise LadderError(f"{where}: levels is a list")
    if not levels:
        if level is not None:
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
        if entry["state"] in ("TESTED", "FROZEN"):
            evidence = entry["evidence"]
            if not (isinstance(evidence, str) and (Path(root) / evidence).exists()):
                raise LadderError(
                    f"{at}: {entry['state']} needs its evidence in the repository"
                )
        elif entry["evidence"] is not None:
            raise LadderError(f"{at}: an OPEN level has no evidence yet")
    for entry in levels[:-1]:
        if entry["state"] == "OPEN":
            raise LadderError(
                f"{where}: level {entry['level']} is still OPEN; climb one level at a time"
            )
    newest = newest_record(challenge, root)
    if levels[-1]["expansion_record"] != newest:
        raise LadderError(
            f"{where}: the current level names {levels[-1]['expansion_record']}, but the "
            f"newest expansion record is {newest}; review the change and update the record"
        )
    return construction
