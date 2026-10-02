"""Level proposals: Graphite proposes the capabilities for every construction level.

The owner, 2026-10-02: "I want graphite to propose capabilities for every
construction level" (OWNER-CHALLENGE-ROADMAP-03, amended).

The ladder (`ladder.py`) is generic, but what each level admits for a given
Challenge is not. So for every Challenge, Graphite proposes the capabilities
for every level, 0 through 5. Each proposal is one file,
`carbon/challenge_pipeline/proposals/<challenge>/level-<n>.json`. It says:
- for each capability, what it adds, its bounds, the research behind it
  (Graphite's method cards and development experiments), the reconstruction
  work Carbon must ship for it, and the attack surface it opens;
- what the level deliberately leaves out.

**Graphite proposes; it does not decide.**
- The construction contract owner (the technical owner) accepts or declines
  each proposal.
- A level above 0 is reached only with an accepted proposal.
- The climb procedure's experiments then decide whether the level holds, and
  a person locks it before miners get it.
- Graphite never writes the contract or an expansion record.

Nothing here is battery-specific.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from carbon.challenge_pipeline.ladder import LEVELS

PROPOSALS = Path(__file__).with_name("proposals")
SCHEMA = "carbon.challenge-pipeline.level-proposal.v1"
KEYS = {
    "schema",
    "challenge",
    "level",
    "recorded_at",
    "proposed_by",
    "capabilities",
    "left_out",
    "status",
}
OPTIONAL = {"decision"}
CAPABILITY_KEYS = {
    "id",
    "adds",
    "bounds",
    "rationale",
    "sources",
    "reconstruction",
    "attack_surface",
}
STATUSES = ("PROPOSED", "ACCEPTED", "DECLINED")
TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CAPABILITY_ID = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
NAME = re.compile(r"^level-([0-5])$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ProposalError(ValueError):
    """A level proposal breaks the rules."""


def _text(value):
    return isinstance(value, str) and value.strip() != ""


def path_for(challenge, level, root=None):
    base = (
        PROPOSALS
        if root is None
        else Path(root) / "carbon/challenge_pipeline/proposals"
    )
    return base / challenge / f"level-{level}.json"


def validate(proposal, where, protocol):
    if not isinstance(proposal, dict) or not (KEYS <= set(proposal) <= KEYS | OPTIONAL):
        raise ProposalError(f"{where}: keys are {sorted(KEYS)} (and a decision)")
    if proposal["schema"] != SCHEMA:
        raise ProposalError(f"{where}: unknown schema")
    if not TOKEN.match(str(proposal["challenge"])):
        raise ProposalError(f"{where}: challenge is a contract token")
    if proposal["level"] not in LEVELS:
        raise ProposalError(f"{where}: level is 0-5")
    try:
        recorded = datetime.datetime.fromisoformat(str(proposal["recorded_at"]))
    except ValueError as error:
        raise ProposalError(f"{where}: recorded_at is an ISO time") from error
    if recorded.utcoffset() != datetime.timedelta(0):
        raise ProposalError(f"{where}: recorded_at is UTC")
    by = proposal["proposed_by"]
    if not (
        isinstance(by, dict)
        and set(by) == {"agent", "role", "session"}
        and by["agent"] == "graphite"
        and _text(by["role"])
        and _text(by["session"])
    ):
        raise ProposalError(
            f"{where}: proposed_by is {{agent: graphite, role, session}}; Graphite "
            "proposes every level's capabilities (OWNER-CHALLENGE-ROADMAP-03)"
        )
    capabilities = proposal["capabilities"]
    if not isinstance(capabilities, list):
        raise ProposalError(f"{where}: capabilities is a list")
    seen = set()
    for item in capabilities:
        if not (isinstance(item, dict) and set(item) == CAPABILITY_KEYS):
            raise ProposalError(f"{where}: a capability is {sorted(CAPABILITY_KEYS)}")
        at = f"{where} capability {item.get('id')}"
        if not CAPABILITY_ID.match(str(item["id"])) or item["id"] in seen:
            raise ProposalError(f"{at}: id is a unique <group>.<name>")
        seen.add(item["id"])
        for key in ("adds", "bounds", "rationale", "reconstruction", "attack_surface"):
            if not _text(item[key]):
                raise ProposalError(f"{at}: {key} is a statement")
        if not (
            isinstance(item["sources"], list)
            and item["sources"]
            and all(_text(s) for s in item["sources"])
        ):
            raise ProposalError(f"{at}: name the research behind it (sources)")
    if not (
        isinstance(proposal["left_out"], list)
        and all(_text(s) for s in proposal["left_out"])
    ):
        raise ProposalError(f"{where}: left_out is a list of statements")
    if not capabilities and not proposal["left_out"]:
        raise ProposalError(
            f"{where}: an empty proposal says in left_out why the level adds nothing"
        )
    status, decision = proposal["status"], proposal.get("decision")
    if status not in STATUSES:
        raise ProposalError(f"{where}: status is one of {STATUSES}")
    if status == "PROPOSED":
        if decision is not None:
            raise ProposalError(f"{where}: a PROPOSED level has no decision yet")
    elif not (
        isinstance(decision, dict)
        and set(decision) == {"by", "on", "ref"}
        and decision["by"] == protocol["owners"]["technical"]
        and DATE.match(str(decision["on"]))
        and _text(decision["ref"])
    ):
        raise ProposalError(
            f"{where}: {status} needs a decision {{by, on, ref}} by the construction "
            "contract owner (the technical owner)"
        )
    return proposal


def load_proposals(protocol, directory=PROPOSALS):
    """Every proposal, validated, keyed by (challenge, level)."""
    out = {}
    for path in sorted(Path(directory).glob("*/level-*.json")):
        match = NAME.match(path.stem)
        proposal = json.loads(path.read_text(encoding="utf-8"))
        where = f"proposal {path.parent.name}/{path.name}"
        if not match:
            raise ProposalError(f"{where}: named level-<0-5>.json")
        validate(proposal, where, protocol)
        if (proposal["challenge"], proposal["level"]) != (
            path.parent.name,
            int(match.group(1)),
        ):
            raise ProposalError(f"{where}: filed under its own challenge and level")
        out[(proposal["challenge"], proposal["level"])] = proposal
    return out
