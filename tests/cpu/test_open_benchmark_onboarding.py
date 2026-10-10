"""Public drafting handoff: full scopes, parity and no invented acceptance."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import law, packet, panel, status

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = "docs/development/challenge_pipeline/open-benchmark-onboarding/"
FOLDER = ROOT / RELATIVE
TOKENS = ("backward-facing-step", "metagrating-3d")


def read(name):
    return json.loads((FOLDER / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("token", TOKENS)
def test_four_outputs_reproduce_without_panel_or_source_approval(token):
    draft = packet.generate(read(token + "-brief.json"), ROOT)
    assert (FOLDER / (token + "-packet.md")).read_text(encoding="utf-8") == (
        packet.render(draft)
    )
    assert packet.render(draft).count("\n## ") == 10
    assert len(draft["fields"]) == 38
    assert all(v["status"] == "HUMAN_INPUT" for v in draft["fields"].values())
    assert read(token + "-law.json") == law.generate(draft)
    assert read(token + "-panel.json") == panel.generate(draft)
    view = status.generate(ROOT, token, bindings_path=RELATIVE + "artifacts.json")
    assert (FOLDER / (token + "-status.md")).read_text(encoding="utf-8") == (
        status.render(view) + "\n"
    )


@pytest.mark.parametrize("token", TOKENS)
def test_missing_reference_cases_do_not_become_solved_or_infeasible(token):
    proposed = read(token + "-law.json")
    assert proposed["panel_basis"] is None and proposed["diversity"] is None
    assert proposed["bank"]["E"] is None and proposed["bank"]["B"] is None
    assert proposed["bank"]["threshold_variation_renews_exposure"] is False
    assert proposed["k"]["recommendation"] is None
    assert "UNRESOLVED" in proposed["NONE_FEASIBLE"]["recommendation"]
    assert "NO_REDRAW" in proposed["NONE_FEASIBLE"]["recommendation"]
    near = proposed["T2a"]
    assert near["near_refinement_bands"] == 2
    assert near["minimum_distinct_feasible"] == 5
    assert near["minimum_distinct_infeasible"] == 5
    assert near["band_widths"] == "HUMAN_INPUT"
    output = read(token + "-panel.json")
    assert output["registration_status"] == "PROPOSED_NOT_DISPATCHABLE"
    assert output["cases"] == [] and output["case_count"] is None
    assert output["reuse_check"]["status"] == "UNKNOWN_NO_INDEX"
    assert output["cost"]["eur"] is None


@pytest.mark.parametrize("token", TOKENS)
def test_status_reports_what_was_read_without_passing_stage_exits(token):
    view = status.generate(ROOT, token, bindings_path=RELATIVE + "artifacts.json")
    assert view["binding_status"] == "CONFIGURED"
    assert view["current_stage"] == "UNDETERMINED_WITHOUT_VERIFIED_EXIT_EVIDENCE"
    assert not view["tested_challenge_claim"]
    assert sum(s["what_was_checked"]["read"] for s in view["stages"]) == 4
    assert sum(s["what_was_checked"]["configured"] for s in view["stages"]) == 4
    assert all(not s["exit_verified"] for s in view["stages"])
    assert view["observed_artifact_stages"] == [
        "S0_brief",
        "S1_packet",
        "S3_feasibility_value_panel",
        "S4_question_law",
    ]


def test_research_priority_and_complete_cost_accounting_are_retained():
    source = json.loads(
        (ROOT / "Business/research/benchmark-challenge-briefs/briefs.json").read_text(
            encoding="utf-8"
        )
    )
    assert tuple(b["id"] for b in source["briefs"]) == TOKENS
    assert source["authorization"]["spend"] is False
    for brief in source["briefs"]:
        cost = brief["cost"]
        draft = read(brief["id"] + "-brief.json")["fields"]
        assert cost["actual_runtime"] is None and cost["actual_memory"] is None
        for scenario in ("low", "base", "high"):
            hours = (
                Decimal(str(cost["complete_cases"][scenario]))
                * Decimal(str(cost["host_hours_per_complete_case"][scenario]))
                + Decimal(str(cost["anchor_host_hours"][scenario]))
                + Decimal(str(cost["comparator_host_hours"][scenario]))
            )
            assert hours == Decimal(str(cost["total_host_hours"][scenario]))
            euros = (hours * Decimal("1.37")).quantize(Decimal("0.01"))
            assert euros == Decimal(str(cost["startup_eur"][scenario]))
            assert str(cost["startup_eur"][scenario]) in draft["cost"]["value"]
        assert "ASSUMPTION" in draft["cost"]["value"]
        assert "not a grant" in draft["cost"]["value"]
        assert "full equal-budget campaign" in draft["cost"]["value"]


def test_full_physical_jobs_and_novelty_limits_remain_explicit():
    step = read("backward-facing-step-brief.json")
    optical = read("metagrating-3d-brief.json")
    assert "2D turbulent" in step["physics"]
    assert "total-pressure loss" in step["decision"]
    assert "complete" in step["fields"]["objective"]["value"]
    assert "Cp is not total-pressure loss" in step["fields"]["outputs"]["value"]
    assert "full x/y/z" in optical["fields"]["refinement"]["value"].lower() or (
        "Full x/y/z" in optical["physics"]
    )
    assert "1D stripes" in optical["fields"]["exclusions"]["value"]
    assert (
        "One hardware period must stay fixed"
        in optical["fields"]["conditions"]["value"]
    )
    for brief in (step, optical):
        assert "excluded" in brief["fields"]["disclosure"]["value"]
        assert "implemented" in brief["fields"]["disclosure"]["value"]
        assert "No solver runs" in brief["fields"]["permissions"]["value"]
        assert "HUMAN_INPUT" in brief["fields"]["hard_limits"]["value"]
        assert "HUMAN_INPUT" in brief["fields"]["P"]["value"]


def test_run_basis_pins_sources_tools_and_all_stable_outputs():
    run = read("tool-run.json")
    assert run["status"] == "DRAFT_GENERATORS_EXERCISED_NOT_STAGE_ACCEPTANCE"
    assert run["solver_runs"] == 0 and run["spend_authorized"] is False
    assert run["protected_material_access"] is False
    assert run["authority_main"] == "94b193525f5d55eb20168ebbdbcf43ddf33653f1"
    for relative, digest in run["inputs_and_tools"].items():
        assert packet.digest((ROOT / relative).read_bytes()) == digest, relative
    for relative, digest in run["outputs"].items():
        assert packet.digest((ROOT / relative).read_bytes()) == digest, relative
    assert len(run["candidate_views"]) == 2
    for row in run["candidate_views"]:
        assert row["source_extract_count"] == 0
        assert row["field_count"] == 38
        assert row["read_artifacts"] == row["configured_artifacts"] == 4
        assert row["verified_exits"] == 0
        assert row["tested_challenge_claim"] is False
