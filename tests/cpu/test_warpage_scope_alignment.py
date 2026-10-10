"""Read-only packet regressions; no solver, panel or scientific qualification."""

import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "docs/development/challenge_pipeline/discovery/warpage-packet"
DATA = json.loads((PACKET / "feasibility-panel.json").read_text(encoding="utf-8"))
TEXT = (PACKET / "PACKAGE_WARPAGE_DESIGN_PACKET.md").read_text(encoding="utf-8")


def test_exact_common_sections_and_original_three_dimensional_job():
    template = (
        ROOT / "docs/development/challenge_pipeline/COMMON_DESIGN_PACKET_V1.md"
    ).read_text(encoding="utf-8")
    assert re.findall(r"^## \d+\. .+$", TEXT, re.MULTILINE) == re.findall(
        r"^## \d+\. .+$", template, re.MULTILINE
    )
    assert "Full three-dimensional" in DATA["physical_scope"]
    assert (
        "complete manufacture/reflow/service thermal history" in DATA["physical_scope"]
    )
    assert DATA["dispatch_authorised"] is False
    assert DATA["challenge_adoption_authorised"] is False
    assert DATA["solver_runs"] == DATA["spend_eur"] == 0
    assert DATA["protected_data_access"] is False
    assert DATA["earned_credibility"] == "NOT_DEMONSTRATED"


def test_both_resolved_frontier_classes_use_two_working_bands():
    gate = DATA["first_panel"]["minimum_contested_counts_user_requirement"]
    assert gate["resolved_feasible_near_per_family_stratum_low_base_high"] == [5] * 3
    assert gate["resolved_infeasible_near_per_family_stratum_low_base_high"] == [5] * 3
    assert gate["working_refinement_bands_both_sides"] == 2
    assert gate["status"] == "TEST_LEAD_WORKING_VALUE_NOT_ADOPTED"
    assert gate["near_band"].startswith("HUMAN_INPUT")
    assert "BOTH within two refinement bands" in TEXT
    assert "never a wider band or weaker limit" in TEXT


def test_questions_per_window_are_not_actions_or_new_physical_exposure():
    law = DATA["question_law"]
    assert "k_low_base_high" not in law
    assert law["k_questions_per_window_low_base_high"] == [4, 8, 12]
    assert law["diagnostic_pool_actions_M_low_base_high"] == [10] * 3
    assert law["actions_per_question"].startswith("HUMAN_INPUT")
    assert all(law[key].startswith("HUMAN_INPUT") for key in ("P", "Q", "w"))
    assert all(law[key] is None for key in ("E", "B", "n", "expected_distinct_winners"))
    assert law["requirement_draws_renew_physical_exposure"] is False
    assert "No redraw" in TEXT
    assert "missing truth" in TEXT and "separate from `NONE_FEASIBLE`" in TEXT


def test_pinned_f08_build_reuse_does_not_claim_full_history_reference():
    reuse = DATA["f08_package_reuse"]
    assert reuse["source_head"] == "0f12834226f65cdb317e7407e1e83e68c135801b"
    assert re.fullmatch("[0-9a-f]{64}", reuse["ccx_archive_sha256"])
    assert reuse["KEEP"] == ["Dockerfile", "build.sh", "sources.lock.json"]
    assert reuse["inspected_only"] is True
    assert reuse["warpage_image_digest"] is None
    assert reuse["full_history_reference_status"] == "NOT_DEMONSTRATED"
    assert len(reuse["missing_feature_proofs"]) == 5
    assert "DO NOT REUSE AS TRUTH" in TEXT and "Modal truncation evidence" in TEXT
    sources = (PACKET / "source-evidence.md").read_text(encoding="utf-8")
    assert reuse["source_head"] in sources and reuse["ccx_archive_sha256"] in sources
    headings = re.findall(r"^## .+$", sources, re.MULTILINE)
    assert len(headings) == len(set(headings))


def test_provisional_registration_has_ten_distinct_slots_and_three_full_histories():
    registration = DATA["provisional_registration"]
    assert registration["status"] == "PROPOSED_SLOTS_NOT_REGISTERED"
    assert registration["runtime_ids"] == []
    assert registration["manifest_sha256"] is None
    designs, strata = registration["design_slots"], registration["strata"]
    assert [item["slot"] for item in designs] == [f"W{i:02}" for i in range(1, 11)]
    assert len({item["change"] for item in designs}) == 10
    assert [item["slot"] for item in strata] == ["S1", "S2", "S3"]
    assert all(item["file_sha256"] is None for item in strata)
    assert len(registration["control_slots"]) == 4
    assert len(registration["witness_pair_slots"]) == 2
    assert registration["refinement_selection"].startswith("HUMAN_INPUT")
    assert registration["counts_do_not_prove_contestability"] is True
    assert registration["failure_reserve_authorizes_retries"] is False
    assert "never hidden EVAL/STRESS/quiz/tuning" in registration["witness_custody"]
    assert "SLOT_UNRESOLVED" in registration["missing_slot"]
    for item in designs + strata:
        assert item["slot"] in TEXT


def test_original_cost_ledgers_still_count_complete_cases_and_high_failure():
    rate, overhead, tax, reserve = map(Decimal, ("1.37", "4", "1.19", "10"))
    c1 = [Decimal(str(x)) for x in DATA["case_cost"]["node_h_low_base_high"]]
    for key, equivalent in (("first_panel", 54), ("original_bank", 151)):
        panel = DATA[key]
        assert panel["equivalent_cases_low_base_high"] == [equivalent] * 3
        expected = [
            rate * (equivalent * cost + overhead) * tax + reserve for cost in c1
        ]
        actual = panel["startup_eur_low_base_high"]
        assert [round(float(x), 6) for x in expected] == [round(x, 6) for x in actual]
    assert DATA["original_bank"]["high_under_cap"] is False
    assert DATA["original_bank"]["affordability_proven"] is False
    assert DATA["original_value"]["demonstrated_benefit_floor_eur"] == 0
    assert DATA["publication_base"] == "f227a55a88cfe736171bb64f602a81eb1777c9ba"
    assert DATA["scope_alignment"]["historical_publication_fields_preserved"] is True


def test_all_eight_comparison_rows_keep_missing_costs_unknown_and_currency_explicit():
    comparison = DATA["current_eight_comparison"]
    assert comparison["currency"] == "USD"
    assert (
        comparison["index_status"]
        == "NOT_COMPUTABLE_COMPLETE_C2_C3_AND_MATCHED_CURRENCY"
    )
    assert len(comparison["missing_basis"]) == 3
    assert comparison["historical_rescore"] is False
    assert comparison["computed_currency_conversion"] is False
    rows = comparison["rows"]
    assert [row["id"] for row in rows] == [
        "battery",
        "motor",
        "cooling-cell",
        "f02",
        "f06",
        "f08",
        "f13",
        "f17",
    ]
    for row in rows:
        assert row["C2"] is row["C3_weekly"] is row["index_low_base_high"] is None
        triple = row["annual_gross_usd_low_base_high"]
        assert len(triple) == 3 and triple == sorted(triple)
        rendered = " / ".join(f"{x:,}" for x in triple)
        assert rendered in TEXT
    assert "null is not zero" in TEXT
