"""Battery's level-climb-1 record: Graphite's Level 2 and Level 3 climb
proposals, kept as the planner wrote them, and the Test Lead's F1 disposition
for development-only variants (OWNER-GRAPHITE-DEV-LEVELS-01).

The accepted contract proposals (`level-N.json`) are unchanged: a climb is
recorded beside them under `climbs/`, never as a contract decision.
"""

from __future__ import annotations

import json

from carbon.challenge_pipeline import proposals
from carbon.challenge_pipeline.state import PROTOCOL
from carbon.reconstruction import capability_registry as cr

BATTERY = cr.BATTERY_CHALLENGE
CLIMBS = proposals.PROPOSALS / BATTERY / "climbs"
DISPOSITIONS = {"ACCEPTED", "ACCEPTED_WITH_CHANGES", "DROPPED"}


def protocol():
    return json.loads(PROTOCOL.read_text())


def climb(level):
    return json.loads((CLIMBS / f"level-climb-1-level-{level}.json").read_text())


def disposition():
    return json.loads((CLIMBS / "level-climb-1-disposition.json").read_text())


def test_the_climb_proposals_are_valid_and_still_proposed():
    for level in (2, 3):
        proposal = climb(level)
        proposals.validate(proposal, f"climb level {level}", protocol())
        assert proposal["status"] == "PROPOSED" and proposal["level"] == level
        assert proposal["proposed_by"]["session"] == "level-climb-1"


def test_every_proposed_capability_has_a_disposition_and_nothing_else_does():
    record = disposition()
    assert record["scope"] == "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS"
    assert record["reviewed_by"] == "test-lead"
    for level in (2, 3):
        proposed = {c["id"] for c in climb(level)["capabilities"]}
        decided = record["levels"][str(level)]
        assert set(decided) == proposed
        assert all(d["disposition"] in DISPOSITIONS for d in decided.values())


def test_the_review_keeps_four_and_drops_the_two_duplicates():
    levels = disposition()["levels"]
    kept = {
        c
        for level in levels.values()
        for c, d in level.items()
        if d["disposition"] != "DROPPED"
    }
    assert kept == {
        "data.pool_selection",
        "optimizer.muon_spectral",
        "numerics.quasi_newton_family",
        "numerics.line_search",
    }


def test_the_contract_proposals_are_untouched_by_the_climb():
    loaded = proposals.load_proposals(protocol())
    for level in (2, 3):
        assert loaded[(BATTERY, level)]["proposed_by"]["session"] == "level-plan-3"
    assert not any(
        c.capability_id == "data.pool_selection"
        for c in cr.contract(BATTERY).capabilities
    )
