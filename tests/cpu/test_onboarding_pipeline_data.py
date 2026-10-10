"""ONBOARDING-PIPELINE-01 data: the stage map, blocker taxonomy and cycle metrics.

These are documentation data, not runtime authority. The tests keep them honest:
every cited file exists, every blocker is a register row, ranks are a permutation,
a duration is never invented (UNKNOWN until a record states it), and no spend
figure or account detail enters the public repository.
"""

import json
import re
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
FOLDER = REPOSITORY / "docs/development/challenge_pipeline/onboarding"
REGISTER = REPOSITORY / "docs/development/graphite/LESSONS_REGISTER.md"
PATH_PREFIXES = ("docs/", ".agent/", "Design_Specs/", "carbon/", "tests/")


def _load(name):
    return json.loads((FOLDER / name).read_text(encoding="utf-8"))


def _cited_paths(items):
    for item in items:
        if item.startswith(PATH_PREFIXES):
            yield item.split(" (")[0].strip()


def test_the_stage_map_is_ordered_and_every_cited_file_exists():
    stages = _load("stage_map.json")["stages"]
    assert [s["order"] for s in stages] == list(range(len(stages)))
    assert len({s["id"] for s in stages}) == len(stages)
    for stage in stages:
        for key in ("entry", "exit", "owner_session", "owner_basis", "note"):
            assert stage[key].strip(), (stage["id"], key)
        assert stage["status"] in {"VERIFIED", "UNVERIFIED"}
        assert stage["evidence"], stage["id"]
        for path in _cited_paths(stage["evidence"]):
            assert (REPOSITORY / path).exists(), (stage["id"], path)


def test_the_stage_map_covers_the_owner_stages_in_order():
    ids = [s["id"] for s in _load("stage_map.json")["stages"]]
    expected = [
        "S0_brief",
        "S1_packet",
        "S2_solver_package",
        "S3_feasibility_value_panel",
        "S4_question_law",
        "S5_bank",
        "S6_readiness",
        "S7_stage_a",
        "S8_stage_b",
        "S9_stage_c",
        "S10_tested",
    ]
    assert ids == expected


def test_tested_is_never_defined_as_qualification():
    tested = _load("stage_map.json")["stages"][-1]
    assert tested["id"] == "S10_tested"
    assert len(re.findall(r"\(\d\)", tested["exit"])) == 9
    assert "cheap-baseline comparison (V4)" in tested["exit"]
    assert "PASSES VALUE" in tested["exit"]
    assert "screen-then-solver-verify" in tested["exit"]
    for claim in ("scientific qualification", "LIVE", "launch claim"):
        assert claim in tested["note"]
    assert "not" in tested["note"].lower()


def test_unverified_marks_are_recorded_with_what_would_clear_them():
    for stage in _load("stage_map.json")["stages"]:
        if stage["status"] == "UNVERIFIED":
            assert "ruling" in stage["note"].lower() or "ask" in stage["note"].lower()


def test_every_blocker_is_a_register_row_and_ranks_are_a_permutation():
    blockers = _load("blocker_taxonomy.json")["blockers"]
    register = REGISTER.read_text(encoding="utf-8")
    assert [b["id"] for b in blockers] == [f"B{i}" for i in range(1, len(blockers) + 1)]
    assert sorted(b["rank"] for b in blockers) == list(range(1, len(blockers) + 1))
    for blocker in blockers:
        assert re.search(
            rf"^\| {blocker['register_row']} \|", register, re.MULTILINE
        ), blocker["id"]
        assert blocker["cause_source"], blocker["id"]
        assert blocker["automation"]["kind"] in {"generator", "check", "template"}
        for path in _cited_paths(blocker["cause_source"]):
            assert (REPOSITORY / path).exists(), (blocker["id"], path)


def test_no_duration_is_invented():
    blockers = _load("blocker_taxonomy.json")["blockers"]
    for blocker in blockers:
        assert blocker["time_lost"] == "UNKNOWN", blocker["id"]
    for line in (
        (FOLDER / "cycle_metrics.jsonl").read_text(encoding="utf-8").splitlines()
    ):
        row = json.loads(line)
        assert row["schema"] == "carbon.challenge-pipeline.onboarding-cycle-metric.v1"
        assert row["cycle_days"] == "UNKNOWN"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"])
        assert row["source"].strip()


def test_the_pages_hold_no_spend_figure_or_account_detail():
    for path in (x for x in FOLDER.iterdir() if x.is_file()):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\$\s?\d|USD\s?\d|\d\s?USD", text), path.name
        assert not re.search(
            r"(?i)balance of|account id|api[_ -]?key\s*[:=]", text
        ), path.name


def test_the_bank_stage_quotes_the_owner_and_attributes_the_reading_to_the_test_lead():
    bank = next(s for s in _load("stage_map.json")["stages"] if s["id"] == "S5_bank")
    assert "It's a cost benefit analysis for the team with a 500 max." in bank["entry"]
    assert "The Test Lead's reading" in bank["entry"]
    assert "EUR 500" in bank["entry"]
    assert "The grant file is what binds spend" in bank["entry"]
    assert "nothing above EUR 500" in bank["entry"]
