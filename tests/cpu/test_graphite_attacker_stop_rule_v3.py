"""Stop rule v3: K is 3 per reachable family, and the final report names what is unreachable.

After the stage A L2 to L4 triage: a session ends once every REACHABLE family has three
counted attempts; every family the Attacker cannot reach is named in the final report with
its covering test, and one with no route and no covering test is a REPORTED GAP, never a
silent pass; a reachable family with no attempt (NOT_RUN) blocks a done report. v1 and v2
records keep their meaning.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test_graphite_attacker_stop_rule import (
    CID,
    DETERMINISTIC,
    REACHABLE,
    TOOLS,
    _adapter,
    _attempts,
    _table,
)

from carbon.agent_campaign.attack import engine
from carbon.agent_campaign.attack.adapter import ADAPTERS
from carbon.agent_campaign.graphite import phase4

V3 = phase4.STOP_RULE_V3


def table_v3(per_family, adapter=None, tools=TOOLS):
    return phase4.stop_rule_coverage(
        adapter or _adapter(), tools, _attempts(per_family), schema=V3
    )


def baseline_run(family, *, evidence=True):
    rows = [{"family": family, "role": "attack", "verdict": "HELD"}]
    if evidence:
        rows += [
            {"family": family, "role": "specimen", "verdict": "FIRED"},
            {"family": family, "role": "control", "verdict": "PASSED"},
        ]
    return engine.FamilyRun(
        family=family,
        check="x",
        records=tuple(rows),
        budget=None,
        available=1,
        attempted=1,
    )


# -- the rule as recorded --------------------------------------------------------------------
def test_the_v3_record_has_k_three_and_the_gap_rule():
    record = phase4.stop_rule_record(V3)
    assert record["schema"] == V3 and record["k"] == 3 == phase4.STOP_RULE_K_V3
    assert record["not_run_blocks_done"] is True
    assert phase4.GAP_LABEL in record["unreachable_report"]
    assert {row["subject"] for row in record["deterministic_coverage"]} == DETERMINISTIC
    assert V3 in phase4.STOP_RULES


def test_v1_and_v2_keep_k_two_and_gain_nothing():
    for schema in (phase4.STOP_RULE_V1, phase4.STOP_RULE_V2):
        record = phase4.stop_rule_record(schema)
        assert record["k"] == 2
        assert (
            "unreachable_report" not in record and "not_run_blocks_done" not in record
        )
        table = phase4.stop_rule_coverage(_adapter(), TOOLS, schema=schema)
        assert table["k"] == 2
        assert all("covering_test" not in row for row in table["unreachable"])
    assert phase4.stop_rule_record().get("schema") == phase4.STOP_RULE_V2


# -- K per reachable family ------------------------------------------------------------------
def test_two_attempts_per_family_finish_under_v2_but_not_v3():
    two = dict.fromkeys(REACHABLE, 2)
    assert phase4.finish_verdict(_table(two), None)[0] is True  # v2
    ok, refusal = phase4.finish_verdict(table_v3(two), None)
    assert not ok and "staged_bytes (2/3)" in refusal["reason"]


def test_three_attempts_in_every_reachable_family_finish_under_v3():
    table = table_v3(dict.fromkeys(REACHABLE, 3))
    assert phase4.finish_verdict(table, None) == (True, None)
    assert all(row["covered"] for row in table["families"])


def test_one_family_short_of_three_blocks_the_finish_whatever_the_others_did():
    table = table_v3({**dict.fromkeys(REACHABLE, 9), "recipe_surface": 2})
    ok, refusal = phase4.finish_verdict(table, 50)
    assert not ok and "recipe_surface (2/3)" in refusal["reason"]


# -- the unreachable families in the final report --------------------------------------------
def test_the_table_names_a_covering_test_only_where_one_is_registered():
    rows = {r["family"]: r for r in table_v3({})["unreachable"]}
    assert rows["rebuild_identity"]["covering_test"].startswith(phase4.COVERED_PREFIX)
    assert rows["mandatory_failure"]["covering_test"] is None


def test_an_unreachable_family_is_named_with_its_covering_test():
    table = table_v3(dict.fromkeys(REACHABLE, 3))
    outcome = phase4.stop_rule_outcome(
        table, [baseline_run("mandatory_failure"), baseline_run("recipe_forgery")]
    )
    by_family = {row["family"]: row for row in outcome["unreachable"]}
    assert by_family["mandatory_failure"]["covering_test"].startswith(
        "deterministic baseline run"
    )
    assert by_family["rebuild_identity"]["reported_gap"] is False  # a registered label


def test_a_family_with_no_attempt_route_and_no_covering_test_is_a_reported_gap():
    table = table_v3(dict.fromkeys(REACHABLE, 3))
    outcome = phase4.stop_rule_outcome(table, [baseline_run("mandatory_failure")])
    assert outcome["status"] == "DONE_WITH_GAPS"
    assert "recipe_forgery" in outcome["gaps"]
    assert "mandatory_failure" not in outcome["gaps"]
    gap = next(r for r in outcome["unreachable"] if r["family"] == "recipe_forgery")
    assert gap["covering_test"] is None and gap["reported_gap"] is True
    assert outcome["gap_label"] == phase4.GAP_LABEL


def test_a_baseline_run_with_no_evidence_does_not_cover_a_family():
    table = table_v3(dict.fromkeys(REACHABLE, 3))
    outcome = phase4.stop_rule_outcome(
        table, [baseline_run("mandatory_failure", evidence=False)]
    )
    assert "mandatory_failure" in outcome["gaps"]


def test_every_unreachable_family_covered_is_done_without_gaps():
    table = table_v3(dict.fromkeys(REACHABLE, 3))
    runs = [baseline_run(r["family"]) for r in table["unreachable"]]
    outcome = phase4.stop_rule_outcome(table, runs)
    assert outcome["status"] == "DONE" and outcome["gaps"] == []


# -- NOT_RUN blocks a done report ------------------------------------------------------------
def test_a_reachable_family_with_no_attempt_blocks_a_done_report():
    # The money floor can end a session early; the report then says INCOMPLETE.
    table = table_v3({**dict.fromkeys(REACHABLE, 3), "staged_bytes": 0})
    outcome = phase4.stop_rule_outcome(table, [])
    assert outcome["status"] == "INCOMPLETE"
    assert outcome["not_run"] == ["staged_bytes"] and outcome["under_k"] == [
        "staged_bytes"
    ]


def test_a_reachable_family_under_k_makes_the_report_incomplete():
    table = table_v3({**dict.fromkeys(REACHABLE, 3), "recipe_surface": 2})
    outcome = phase4.stop_rule_outcome(table, [])
    assert outcome["status"] == "INCOMPLETE" and outcome["not_run"] == []


# -- a level whose doors reach one family ----------------------------------------------------
def test_level_two_lists_its_unreachable_families_and_reports_each_as_a_gap():
    adapter = ADAPTERS[(CID, 2)]
    adapter = adapter() if isinstance(adapter, type) else adapter
    table = phase4.stop_rule_coverage(adapter, TOOLS, schema=V3)
    reachable = [row["family"] for row in table["families"]]
    assert len(reachable) >= 1
    unreachable = [row["family"] for row in table["unreachable"]]
    assert unreachable  # the L2 families the doors do not reach
    found = []
    for family in reachable:
        found += _door_attempts(table, family, len(found))
    full = phase4.stop_rule_coverage(adapter, TOOLS, found, schema=V3)
    outcome = phase4.stop_rule_outcome(full, [])
    assert outcome["status"] in ("DONE_WITH_GAPS", "DONE")
    assert set(outcome["gaps"]) <= set(unreachable)


def _door_attempts(table, family, offset):
    """Three attempts through the family's first door."""
    from test_graphite_attacker_stop_rule import _attempt

    door = next(r for r in table["families"] if r["family"] == family)["doors"][0]
    name, _, shape = door.partition("[")
    arguments = {}
    if shape:
        kind, _, action = shape.rstrip("]").partition("/")
        arguments = {"kind": kind, "action": action}
    return [_attempt(offset + n + 1, name, arguments) for n in range(3)]


# -- the live Attacker runs under v3 ---------------------------------------------------------
def test_a_live_attacker_provider_is_built_under_the_v3_rule(monkeypatch):
    built = {}

    def provider(**kwargs):
        built.update(kwargs)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(phase4, "AttackerProvider", provider)
    phase4.live_provider(
        "/tmp/none", grant=object(), model=object(), adapter=object(), miner_attach=None
    )
    assert built["stop_rule"] == V3


def test_the_provider_resumes_a_v3_session_under_the_v3_record():
    provider = object.__new__(phase4.AttackerProvider)
    opened = {"session_limits": {"stop_rule": phase4.stop_rule_record(V3)}}
    base = {"session_limits": {"stop_rule": "current"}}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            phase4.Phase3Provider, "_expected_limits", lambda self, o: dict(base)
        )
        expected = provider._expected_limits(opened)["session_limits"]["stop_rule"]
    assert expected == phase4.stop_rule_record(V3)
