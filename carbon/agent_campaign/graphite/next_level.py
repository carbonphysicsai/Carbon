"""Next-level proposals: what a card points at beyond the recorded contract.

GRAPHITE-D30. When a method card points at a capability outside the current
recorded battery construction contract (a new loss form, an architecture
family, a data pipeline), the Planner or the Constructor may record it with
`graphite_propose_next_level`. Carbon validates the arguments against the
session's offered cards and the recorded contract, and stores a typed,
write-once record with status `PROPOSED` under the run root
(`runs/<run>/next-level/`). The delivery bundle carries a run's proposals.

**A proposal is a request, not a change.** Writing one never widens the
construction surface, never calls the controller's `record_expansion`, never
writes an expansion record, never changes a permission profile or a role's
tools, and never reaches a score. Widening a level stays an owner decision
under the reconstruction rule (OWNER-GRAPHITE-02): a widened surface ships
with Carbon's reconstruction of it, in the same phase.

The proposal's text fields are the agent's words, stored as data. Nothing
reads them back as instructions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from .roles import CONTRACT_DIMENSIONS, NEXT_LEVEL

SCHEMA = "carbon.graphite.next-level-proposal.v1"
PROPOSED = "PROPOSED"
DIRECTORY = "next-level"
#: The most proposals one run may write.
MAX_PER_RUN = 8
MAX_SOURCES = 8
MAX_CAPABILITY = 300
MAX_TEXT = 2000
#: The contract a cited capability id is checked against: Level 0 constructs
#: inside the battery contract (GRAPHITE-D30).
NOT_IN_CONTRACT = "NOT_NAMED_BY_THE_CONTRACT"
AUTHORITY = {
    "status_is_a_request": True,
    "widens_construction_surface": False,
    "records_expansion": False,
    "changes_permissions": False,
    "affects_score": False,
    "decided_by": (
        "the owner, under the reconstruction rule (OWNER-GRAPHITE-02): a "
        "widened surface ships with Carbon's reconstruction of it"
    ),
}
_FIELDS = (
    "capability",
    "source_card_ids",
    "contract_dimension",
    "contract_capability_id",
    "outside_contract_because",
    "reconstruction_needs",
)
_ID = re.compile(r"nlp-[0-9a-f]{16}\Z")


class ProposalRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _text(value, name, limit):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ProposalRefused(f"{name}_is_1_to_{limit}_characters")
    return value.strip()


def _contract():
    """The recorded battery contract (Level 0's), or a typed refusal."""
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE, contract

    from . import experiment as ex

    try:
        recorded = ex.recorded_contract()
    except ex.Unrebuildable:
        raise ProposalRefused("construction_contract_unrecorded") from None
    return recorded, contract(BATTERY_CHALLENGE)


def _cited(capability_id, dimension, live):
    """The status of the contract entry a proposal cites, or NOT_IN_CONTRACT.
    A capability the contract already rebuilds is inside it, not next level."""
    if capability_id == "":
        return NOT_IN_CONTRACT
    if type(capability_id) is not str or len(capability_id) > 200:
        raise ProposalRefused("contract_capability_id_is_text")
    for entry in live.capabilities:
        if entry.capability_id == capability_id or capability_id in entry.realizes:
            if entry.dimension.value != dimension:
                raise ProposalRefused("contract_capability_is_in_another_dimension")
            if entry.status.value == "rebuildable_development":
                raise ProposalRefused("capability_is_inside_the_recorded_contract")
            return entry.status.value
    raise ProposalRefused("contract_capability_id_not_in_the_contract")


def build(arguments, *, literature, run_id, identity, role):
    """A validated proposal record; `ProposalRefused` otherwise."""
    if type(arguments) is not dict or set(arguments) != set(_FIELDS):
        raise ProposalRefused("arguments_are_exactly_the_proposal_fields")
    capability = _text(arguments["capability"], "capability", MAX_CAPABILITY)
    sources = arguments["source_card_ids"]
    if (
        type(sources) is not list
        or not 1 <= len(sources) <= MAX_SOURCES
        or any(type(s) is not str for s in sources)
        or len(set(sources)) != len(sources)
    ):
        raise ProposalRefused("source_card_ids_are_1_to_8_distinct_ids")
    status = getattr(literature, "status", None)
    cards = []
    for card_id in sources:
        if literature.card(card_id) is None:
            raise ProposalRefused("source_card_not_offered_to_this_session")
        cards.append(
            {
                "card_id": card_id,
                "check_status": status(card_id) if status else "SYNTHETIC_FIXTURE",
            }
        )
    dimension = arguments["contract_dimension"]
    if dimension not in CONTRACT_DIMENSIONS:
        raise ProposalRefused("contract_dimension_not_a_contract_dimension")
    recorded, live = _contract()
    cited = _cited(arguments["contract_capability_id"], dimension, live)
    body = {
        "capability": capability,
        "source_cards": cards,
        "literature_snapshot_digest": literature.snapshot_digest,
        "outside_contract": {
            "contract": recorded,
            "dimension": dimension,
            "capability_id": arguments["contract_capability_id"] or None,
            "cited_status": cited,
            "because": _text(
                arguments["outside_contract_because"],
                "outside_contract_because",
                MAX_TEXT,
            ),
        },
        "reconstruction_needs": _text(
            arguments["reconstruction_needs"], "reconstruction_needs", MAX_TEXT
        ),
    }
    proposal_id = "nlp-" + digest(canonical([run_id, identity, body]))[7:23]
    return {
        "schema": SCHEMA,
        "proposal_id": proposal_id,
        "run_id": run_id,
        "identity": identity,
        "role": role,
        "tool": NEXT_LEVEL,
        **body,
        "status": PROPOSED,
        "authority": dict(AUTHORITY),
    }


class ProposalStore:
    """Write-once proposal records under one run's directory."""

    def __init__(self, run_dir):
        self.root = Path(run_dir) / DIRECTORY

    def proposals(self):
        if not self.root.is_dir():
            return []
        return [
            json.loads(path.read_bytes())
            for path in sorted(self.root.glob("nlp-*.json"))
            if _ID.fullmatch(path.stem)
        ]

    def write(self, record):
        if record.get("status") != PROPOSED or record.get("schema") != SCHEMA:
            raise ValueError("a next-level proposal is written PROPOSED")
        if not _ID.fullmatch(record["proposal_id"]):
            raise ValueError("not a proposal id")
        path = self.root / (record["proposal_id"] + ".json")
        if not path.exists() and len(self.proposals()) >= MAX_PER_RUN:
            raise ProposalRefused("run_proposal_limit_reached")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_once(path, canonical(record))
        return path


def propose_tool(arguments, *, literature, run_dir, run_id, identity, role):
    """The tool's answer: the stored record as data, or a typed refusal."""
    try:
        record = build(
            arguments,
            literature=literature,
            run_id=run_id,
            identity=identity,
            role=role,
        )
        ProposalStore(run_dir).write(record)
    except ProposalRefused as refused:
        return {
            "status": "REFUSED_INVALID_REQUEST",
            "reason_code": refused.code,
            "authority_granted": False,
            "dispatched": False,
        }
    return {
        "status": "OK",
        "proposal_id": record["proposal_id"],
        "proposal_status": PROPOSED,
        "authority_granted": False,
        "widens_nothing": True,
        "note": (
            "Recorded for the owner. Nothing was widened; the construction "
            "contract, the permissions and every score are unchanged."
        ),
    }


def listing(root):
    """Every proposal under a phase-3 root's runs, by run then id."""
    out = []
    for run in sorted((Path(root) / "graphite" / "runs").glob("graphite-*")):
        out.extend(ProposalStore(run).proposals())
    return out
