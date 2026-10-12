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


# -- levels after #1184: declared families make every level family reachable but L1's two ----------
def _level_adapter(level):
    adapter = ADAPTERS[(CID, level)]
    return adapter() if isinstance(adapter, type) else adapter


def _door_attempts(table, family, offset):
    """Three attempts through the family's first door, declaring the family in the hypothesis."""
    from test_graphite_attacker_stop_rule import _attempt

    door = next(r for r in table["families"] if r["family"] == family)["doors"][0]
    base = door.split("+")[0]
    name, _, shape = base.partition("[")
    arguments = {"hypothesis": f"[family: {family}]"}
    if shape:
        kind, _, action = shape.rstrip("]").partition("/")
        arguments.update({"kind": kind, "action": action})
    return [_attempt(offset + n + 1, name, arguments) for n in range(3)]


def _full_outcome(level):
    adapter = _level_adapter(level)
    table = phase4.stop_rule_coverage(adapter, TOOLS, schema=V3)
    found = []
    for row in table["families"]:
        found += _door_attempts(table, row["family"], len(found))
    full = phase4.stop_rule_coverage(adapter, TOOLS, found, schema=V3)
    return table, full, phase4.stop_rule_outcome(full, [])


def test_level_one_reports_its_two_unreachable_families_as_gaps():
    table, full, outcome = _full_outcome(1)
    unreachable = sorted(r["family"] for r in table["unreachable"])
    assert unreachable == ["l1_permission_ablation", "l1_rebuild_identity"]
    assert all(row["covered"] for row in full["families"])
    assert outcome["status"] == "DONE_WITH_GAPS"
    assert sorted(outcome["gaps"]) == unreachable


@pytest.mark.parametrize("level", [2, 3, 4])
def test_levels_two_to_four_reach_every_family_and_finish_without_gaps(level):
    table, full, outcome = _full_outcome(level)
    assert table["unreachable"] == []
    assert all(row["covered"] for row in full["families"])
    assert outcome["status"] == "DONE" and outcome["gaps"] == []


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


# -- v1 and v2 are untouched, and v3 is chosen only by name (invariant 10) -------------------
#: Digests of what v1 and v2 produced on main before v3 existed (canonical JSON, sorted keys):
#: the records, the empty and two-each coverage tables, the finish refusal and the brief block.
GOLDEN = {
    "STOP_RULE_V1.record": "1d2477fe17d0d9c3fd19e2496c48b385d9e7ead46baecaa255a3325919c5c1e6",
    "STOP_RULE_V1.empty": "0ce6849e786e126543ca244dd49d29e741c23084b145c27ace428032df065cae",
    "STOP_RULE_V1.two_each": "7f7dad24d161c6c01177d3bad165aedfb63a55c8a1fa91b2e55de825c2458c10",
    "STOP_RULE_V1.refusal": "d610533595594e638d28d9f720b90d20dee80c1331e7869df589a25e34438429",
    "STOP_RULE_V2.record": "3d4b6fbdaee84280da10439ed8783310df74585761813bfe75733ead14c18efc",
    "STOP_RULE_V2.empty": "1773b168e356dffc7c83ef75016ae35c703f928a99eb0f9d5621a88eae6dfbbc",
    "STOP_RULE_V2.two_each": "76b5565cdf5352b4c47e0124de03e2e8e49dfb029a26d9645c95188156490569",
    "STOP_RULE_V2.refusal": "be83671603c811795c47413f756a9c43f3d42bbf07a0b891f8671376ead21867",
    "observation": "d1372cb36ab49e21a458a50de90b639bc25598c39dd97f5c4d8193e69201f6d5",
}


def _digest(value):
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_v1_and_v2_outputs_are_byte_identical_to_what_main_produced_before_v3():
    got = {}
    for name in ("STOP_RULE_V1", "STOP_RULE_V2"):
        schema = getattr(phase4, name)
        got[name + ".record"] = _digest(phase4.stop_rule_record(schema))
        got[name + ".empty"] = _digest(
            phase4.stop_rule_coverage(_adapter(), TOOLS, schema=schema)
        )
        got[name + ".two_each"] = _digest(
            phase4.stop_rule_coverage(
                _adapter(), TOOLS, _attempts(dict.fromkeys(REACHABLE, 2)), schema=schema
            )
        )
        short = phase4.stop_rule_coverage(
            _adapter(),
            TOOLS,
            _attempts({**dict.fromkeys(REACHABLE, 2), "staged_bytes": 1}),
            schema=schema,
        )
        got[name + ".refusal"] = _digest(phase4.finish_verdict(short, None)[1])
    got["observation"] = _digest(
        phase4.brief_observation(_adapter(), stop_rule=True)["stop_rule"]
    )
    assert got == GOLDEN


def test_v3_is_chosen_only_by_name():
    assert phase4.stop_rule_record()["schema"] == phase4.STOP_RULE_V2
    assert phase4.stop_rule_coverage(_adapter(), TOOLS)["schema"] == phase4.STOP_RULE_V2
    observation = phase4.brief_observation(_adapter(), stop_rule=True)["stop_rule"]
    assert observation["coverage"]["schema"] == phase4.STOP_RULE_V2
    assert "stop_rule" not in phase4.brief_observation(_adapter())
    provider = object.__new__(phase4.AttackerProvider)
    assert not hasattr(provider, "stop_rule") or provider.stop_rule is None


def test_v3_claims_development_evidence_only():
    outcome = phase4.stop_rule_outcome(table_v3(dict.fromkeys(REACHABLE, 3)), [])
    assert outcome["authority"].startswith("DEVELOPMENT evidence only")
    assert "no qualification" in outcome["authority"]


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_no_family_is_dropped_silently_at_any_level(level):
    adapter = ADAPTERS[(CID, level)]
    adapter = adapter() if isinstance(adapter, type) else adapter
    table = phase4.stop_rule_coverage(adapter, TOOLS, schema=V3)
    outcome = phase4.stop_rule_outcome(table, [])
    named = [r["family"] for r in table["families"]] + [
        r["family"] for r in outcome["unreachable"]
    ]
    expected = sorted(f.name for f in adapter.families())
    assert sorted(named) == expected  # each family exactly once
    for row in outcome["unreachable"]:
        # covered by a named test, or visible as a gap: never absent, never blank
        assert (row["covering_test"] is not None) != row["reported_gap"]
    assert set(outcome["gaps"]) == {
        r["family"] for r in outcome["unreachable"] if r["reported_gap"]
    }


# -- declared families and the brief's tagging block ---------------------------------------------
class TaggedAdapter:
    """A level whose doors reach family `a`, and any family an attempt declares in its hypothesis."""

    def __init__(self, names=("a", "b", "c")):
        self._names = names

    def families(self):
        return [SimpleNamespace(name=n) for n in self._names]

    def family_for(self, tool, arguments=None):
        text = (arguments or {}).get("hypothesis", "")
        for name in self._names:
            if f"[family: {name}]" in str(text):
                return name
        return self._names[0]


def test_declared_families_are_reachable_under_v3_only():
    adapter = TaggedAdapter()
    plain = phase4.reachable_families(adapter, TOOLS)
    assert list(plain) == ["a"]  # v1 and v2: the doors reach one family
    declared = phase4.reachable_families(adapter, TOOLS, declare=True)
    assert list(declared) == ["a", "b", "c"]
    assert any(d.endswith("+[family: b]") for d in declared["b"])
    table = phase4.stop_rule_coverage(adapter, TOOLS, schema=V3)
    assert [r["family"] for r in table["families"]] == ["a", "b", "c"]
    assert table["unreachable"] == []
    v2 = phase4.stop_rule_coverage(adapter, TOOLS)
    assert [r["family"] for r in v2["families"]] == ["a"]
    assert [r["family"] for r in v2["unreachable"]] == ["b", "c"]


def test_the_v3_brief_carries_the_tagging_text_and_the_reachable_names():
    brief = phase4.brief_observation(_adapter(), stop_rule=V3)["stop_rule"]
    tagging = brief["tagging"]
    assert (
        tagging["field"] == "hypothesis" and tagging["syntax"] == "[family: <family>]"
    )
    assert tagging["reachable"] == [r["family"] for r in brief["coverage"]["families"]]
    assert "3 counted attempts" in tagging["text"]
    # v1 and v2 briefs carry no tagging block
    assert (
        "tagging"
        not in phase4.brief_observation(_adapter(), stop_rule=True)["stop_rule"]
    )


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_every_reachable_family_is_an_adapter_family_name(level):
    adapter = ADAPTERS[(CID, level)]
    adapter = adapter() if isinstance(adapter, type) else adapter
    names = {f.name for f in adapter.families()}
    assert set(phase4.reachable_families(adapter, TOOLS, declare=True)) <= names
