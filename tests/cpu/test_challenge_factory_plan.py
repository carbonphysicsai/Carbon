"""Check a proposed document plan; never execute its scientific pilot."""

import json
import math
import re
from datetime import datetime
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding.telemetry import analyze

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "docs/development/challenge_pipeline/challenge-factory"


def document(name):
    return json.loads((FOLDER / name).read_text(encoding="utf-8"))


def test_ten_reused_holds_keep_value_cost_and_source_caveats():
    plan = document("candidates.json")
    source = json.loads((ROOT / plan["source"]).read_text(encoding="utf-8"))
    lookup = {row["id"]: row for row in source["original80"] + source["buyer_side20"]}
    assert len(plan["candidates"]) == 10
    assert len({row["id"] for row in plan["candidates"]}) == 10
    for row in plan["candidates"]:
        prior = lookup[row["id"]]
        assert prior["screen"] == "HOLD"
        assert prior["admitted"] is False
        assert row["source_keys"] == prior["sources"]
        for new_key, prior_key in (
            ("V2_eur_source", "V2_eur"),
            ("V3_decisions_year_source", "V3_decisions_year"),
            ("C2_eur_source", "C2_eur"),
        ):
            assert row[new_key] == pytest.approx(prior[prior_key])
        assert max(row["C2_eur_source"]) <= 100  # estimate only, not cap acceptance
        assert (FOLDER / "families" / f"{row['family']}.md").is_file()


def test_planning_ranking_is_reproducible_and_cannot_claim_earned_value():
    plan = document("candidates.json")
    priorities = []
    for rank, row in enumerate(plan["candidates"], 1):
        scores = row["scores_L_A_H_assumption"]
        assert len(scores) == 3 and all(
            type(score) is int and 1 <= score <= 5 for score in scores
        )
        days = row["active_engineering_days_low_base_high_assumption"]
        assert 0 < days[0] <= days[1] <= days[2]
        w = min(scores) / 5
        assert row["winnability_base_assumption"] == pytest.approx(w)
        priority = (
            w * row["V2_eur_source"][1] * row["V3_decisions_year_source"][1] / days[1]
        )
        assert row["priority_base"] == pytest.approx(priority)
        assert row["rank"] == rank
        priorities.append(priority)
    assert priorities == sorted(priorities, reverse=True)
    assert math.isclose(sum(plan["stage_effort_shares_assumption"].values()), 1)
    assert plan["status"] == "PROPOSED_ASSUMPTION"
    assert plan["admitted_count"] == plan["incremental_annual_value_eur_floor"] == 0
    assert plan["dispatch_authorized"] is False
    assert plan["solver_runs"] == plan["spend"] == 0
    assert plan["thresholds"] == "HUMAN_INPUT"


def test_historical_arrival_clocks_not_invented_labour_or_accepted_exits():
    timing = document("timing.json")
    history = json.loads(
        (ROOT / timing["historical_source"]).read_text(encoding="utf-8")
    )
    assert timing["historical_main"] == history["main"]
    assert timing["cohorts"] == history["cohorts"] == 11
    assert timing["milestone_rows"] == len(history["rows"]) == 110
    assert (
        timing["accepted_stage_elapsed_rows"]
        == sum(row["stage_elapsed_s"] is not None for row in history["rows"])
        == 0
    )
    assert (
        timing["human_effort_rows"]
        == sum(row["team_effort_hours"] is not None for row in history["rows"])
        == 0
    )
    for new, prior in zip(
        timing["slow_arrivals"],
        history["slowest_recurring_observed_arrivals"],
        strict=True,
    ):
        assert new["stage"] == prior["stage"]
        assert new["distinct_events"] == prior["sample_n"]
        assert new["median_arrival_s"] == prior["median_arrival_gap_s"]
        assert new["max_arrival_s"] == prior["max_arrival_gap_s"]
    for key in (
        "human_active_h",
        "agent_active_h",
        "full_onboarding_active_h",
        "earned_speedup",
    ):
        assert timing[key] is None
    assert timing["auto_stage_acceptance"] is False


def test_existing_public_tool_timers_are_separate_and_reproducible():
    timing = document("timing.json")
    start, end = map(datetime.fromisoformat, timing["recorded_window_utc"])
    events = []
    for path in (ROOT / timing["event_store"]).glob("*.json"):
        event = json.loads(path.read_text(encoding="utf-8"))
        if (
            event["challenge"] == timing["recorded_challenge"]
            and event["source"] == timing["recorded_source"]
            and start <= datetime.fromisoformat(event["at"]) < end
        ):
            events.append(event)
    assert len(events) == 24
    assert {event["actor_kind"] for event in events} == {"TOOL"}
    stages = json.loads(
        (
            ROOT / "docs/development/challenge_pipeline/onboarding/stage_map.json"
        ).read_text(encoding="utf-8")
    )["stages"]
    report = analyze(
        events,
        "motor",
        [stage["id"] for stage in stages],
        events[0]["stage_map_sha256"],
    )
    totals = {}
    for stage in report["stages"]:
        assert stage["active_hours_partial"]["HUMAN"] is None
        assert stage["active_hours_partial"]["AI_AGENT"] is None
        assert stage["accepted_exit_verified"] is False
        value = stage["active_hours_partial"]["TOOL"]
        if value is not None:
            totals[stage["stage"]] = value * 3600
    assert totals == pytest.approx(timing["recorded_tool_active_s"])
    assert sum(totals.values()) == pytest.approx(timing["recorded_tool_total_s"])


def test_target_curve_is_assumption_with_floor_not_speedup_evidence():
    timing = document("timing.json")
    first = timing["target_H1_example_active_h"]
    floor = timing["target_floor_fraction"]
    decay = timing["target_decay"]
    curve = [first * (floor + (1 - floor) * decay**n) for n in range(4)]
    assert curve == pytest.approx(timing["target_examples_active_h"])
    assert curve == sorted(curve, reverse=True)
    assert all(value >= first * floor for value in curve)
    assert timing["target_status"] == "PROPOSED_ASSUMPTION_NOT_MEASURED"
    assert timing["threshold_authority"] == "HUMAN_INPUT"


def test_seven_family_pages_have_explicit_nontransferable_gaps():
    expected = {
        "heat",
        "electrochemistry",
        "electromagnetics",
        "structures",
        "acoustics",
        "cfd",
        "photonics",
    }
    assert {path.stem for path in (FOLDER / "families").glob("*.md")} == expected
    for family in expected:
        text = (FOLDER / "families" / f"{family}.md").read_text(encoding="utf-8")
        for word in (
            "PROPOSED",
            "UNKNOWN",
            "HUMAN_INPUT",
            "Comparator",
            "Equal budget",
            "Per Challenge",
        ):
            assert word.lower() in text.lower(), (family, word)


def test_local_markdown_links_are_real():
    for path in FOLDER.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            assert (path.parent / target.split("#")[0]).resolve().is_file(), (
                path,
                target,
            )


def test_pilot_and_retro_keep_failure_cost_and_scope_distinctions():
    pilot = (FOLDER / "winnability-pilot.md").read_text(encoding="utf-8")
    for phrase in (
        "HUMAN_INPUT",
        "1/3/5",
        "MLP",
        "Solver alone",
        "BLOCKED_REFERENCE",
        "INDETERMINATE",
        "NONE_FEASIBLE",
        "two-refinement-band",
    ):
        assert phrase in pilot
    assert "this document grants\nneither" in pilot
    retro = (FOLDER / "retrospective.md").read_text(encoding="utf-8")
    for phrase in (
        "71/100",
        "99/100",
        "100/100",
        "two robust-SOC",
        "91 tie",
        "not matched",
        "No full cold plate",
    ):
        assert phrase in retro
    assert "Battery v3" in retro and "Motor revised 10p/12s" in retro
    assert "f02 exact adopted" in retro and "Cooling interior cell" in retro
    cooling = json.loads(
        (
            ROOT / "Business/research/ai-chip-cooling-sources/operating-points.json"
        ).read_text(encoding="utf-8")
    )
    central = next(point for point in cooling["points"] if point["id"] == "B")
    assert central["inlet_c_low_base_high"] == [37, 40, 42]
    assert central["interface_heat_W_low_base_high"] == [900, 1000, 1100]
    assert central["base_total_flow_LPM"] == 1.5
    assert central["cell_pressure_allocation_kPa_low_base_high"] == [20, 25, 30]
