"""Owner-v1 controls on toys only; no public outcomes or protected material."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from scripts.dev.score_lab import candidates
from scripts.dev.score_lab import owner_dev_v1 as owner
from scripts.dev.score_lab.core import LabRefused

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = (
    ROOT / "Business/research/score-lab-campaign-01/owner-dev-v1/REGISTRATION.json"
)


def row(cid, margin=5.0, solved=None):
    verdict = owner.v2_label(margin / 1000, None if solved is None else solved / 1000)
    return {
        "m20_mv": margin,
        "sealed_v2": (
            None
            if verdict is None
            else {
                "case_id": cid,
                "source": "ev4",
                "m20_mv": margin,
                "m160_mv": solved,
                **verdict,
            }
        ),
    }


def test_exact_public_candidate_bytes_and_all_ten_functions():
    rules, digest = candidates.load()
    assert (
        hashlib.sha256(candidates.REGISTERED_SOURCE.read_bytes()).hexdigest() == digest
    )
    assert digest == "157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235"
    assert len(rules) == 10 and all(callable(spec["rule"]) for spec in rules.values())
    assert candidates.load(candidates.REGISTERED_SOURCE)[1] == digest


def test_changed_registered_source_refused_before_any_execution(tmp_path, monkeypatch):
    source = tmp_path / "untrusted.py.txt"
    source.write_text(
        "raise AssertionError('executed before digest check')", encoding="utf-8"
    )
    monkeypatch.setattr(candidates, "REGISTERED_SOURCE", source)
    with pytest.raises(LabRefused, match="registered_candidates_digest"):
        candidates.load()


def test_pinned_import_does_not_reopen_a_source_changed_after_check(tmp_path):
    source = tmp_path / "checked.py.txt"
    checked = b"VALUE = 'checked bytes'\n"
    source.write_bytes(checked)
    loader = candidates._PinnedSourceLoader("checked_toy", source, checked)
    spec = importlib.util.spec_from_file_location("checked_toy", source, loader=loader)
    module = importlib.util.module_from_spec(spec)
    source.write_text(
        "raise AssertionError('reopened unchecked source')", encoding="utf-8"
    )
    loader.exec_module(module)
    assert module.VALUE == "checked bytes"


def test_d6_never_invents_aggregate_comparator_or_adopts_proxy():
    rules, _ = candidates.load()
    dispositions = {name: owner.candidate_disposition(name) for name in rules}
    assert all(row["adoptable"] is False for row in dispositions.values())
    assert dispositions["N3-SAFE-PICK-RATE-x-GAIN"]["status"].startswith("EXCLUDED")
    assert dispositions["N4-TOP-REGION-RANKING"]["status"].startswith("EXCLUDED")
    assert dispositions["N1-DECISION-RELEVANCE-ERROR"]["status"].startswith("DEFERRED")
    assert dispositions["INFORCE-G-FEAS/A-Q>@0.05"]["status"] == "BASELINE_CONTROL_ONLY"
    with pytest.raises(LabRefused, match="candidate_outside_frozen_family"):
        owner.candidate_disposition("new-wrapper")


def test_registration_binds_owner_bytes_family_and_development_scope():
    registration = json.loads(REGISTRATION.read_bytes())
    authority = registration["authority"]
    assert (
        hashlib.sha256((ROOT / authority["path"]).read_bytes()).hexdigest()
        == authority["sha256"]
    )
    family = registration["candidates"]
    assert (
        hashlib.sha256((ROOT / family["path"]).read_bytes()).hexdigest()
        == family["sha256"]
    )
    assert family["sha256"] == candidates.REGISTERED_SHA256
    assert registration["job"]["id"] == "battery-v3-job-dev-v1"
    assert registration["selection"]["k"] == 3
    assert registration["P"]["redraws"] == 0
    assert registration["P"]["buyer_mix"]["alpha"] == [2, 3, 8, 5, 2]
    assert registration["Q"]["strata"] == {
        "interior": 0.2,
        "safety_edge": 0.5,
        "pick_edge": 0.3,
    }
    assert registration["job"]["zero_weight_bands_mandatory"] is True
    assert registration["value"]["per_band_tolerance_min"] == 0.5
    assert registration["live_effects"] is registration["qualification"] is False
    assert registration["holdout"]["reveals"] == 1


@pytest.mark.parametrize("margin", [-15, 15, -16, 20])
def test_claim_boundary_and_dominated_uncovered_action_exclude_whole_question(margin):
    rows = {"best": row("best"), "dominated": row("dominated", margin)}
    result = owner.covered_questions({"q": ["best", "dominated"]}, rows)
    assert result["common_questions"] == []
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["excluded_questions"]["q"]["dominated"] == "OUTSIDE_PLATING_V2_CLAIM"
    assert result["plating_status_by_case"]["dominated"] == "UNRESOLVED"
    assert result["pruned_actions"] == 0


def test_pending_is_not_feasible_and_completion_uses_exact_sealed_rule():
    pending = owner.covered_questions({"q": ["a"]}, {"a": row("a", 2)})
    assert pending["plating_status_by_case"]["a"] == "UNRESOLVED"
    decided = owner.covered_questions({"q": ["a"]}, {"a": row("a", 2, 2)})
    assert decided["common_questions"] == ["q"]
    assert decided["plating_status_by_case"]["a"] == "FEASIBLE"
    assert decided["first_line"] == "value conditional on the covered region"


def test_old_rule_wrong_source_and_forged_verdict_are_refused():
    for field, value in (
        ("rule", "m160-d3"),
        ("source", "pdd"),
        ("label", "INFEASIBLE"),
    ):
        bad = row("a")
        bad["sealed_v2"][field] = value
        with pytest.raises(LabRefused):
            owner.covered_questions({"q": ["a"]}, {"a": bad})


def test_missing_reference_never_penalizes_candidate_or_drops_only_action():
    result = owner.covered_questions(
        {"q": ["present", "missing"]}, {"present": row("present")}
    )
    assert result["common_questions"] == []
    assert result["excluded_questions"] == {
        "q": {"missing": "MISSING_OR_FAILED_REFERENCE"}
    }


def test_zero_weight_band_is_still_a_mandatory_case_in_registered_manifest():
    cases = ["5C", "15C", "25C", "35C", "40C-zero-weight"]
    rows = {cid: row(cid) for cid in cases}
    rows["40C-zero-weight"] = row("40C-zero-weight", 20)
    result = owner.covered_questions({"indexed-q": cases}, rows)
    assert not result["common_questions"]
    assert set(result["plating_status_by_case"]) == set(cases)


def test_one_reference_mask_for_every_model_and_controls_no_prediction_argument():
    manifest = {"q1": ["a"], "q2": ["b"]}
    rows = {"a": row("a"), "b": row("b", 20)}
    before = copy.deepcopy((manifest, rows))
    masks = [
        owner.covered_questions(manifest, rows) for _ in ("good", "gamer", "control")
    ]
    assert masks[0] == masks[1] == masks[2]
    assert masks[0]["common_questions"] == ["q1"]
    assert (manifest, rows) == before


def test_top_three_uses_each_rules_leg_scores_and_pessimistic_tied_gamer_rank():
    scores = {"a": 5, "b": 4, "c": 3, "d": 2, "z-gamer": 3}
    result = owner.select_top_three(scores, admitted=list(scores), gamers=["z-gamer"])
    assert result["selected"] == ["a", "b", "c"]
    assert result["no_gamer_in_top_half"] is True  # rank3 > floor(5/2)
    scores["z-gamer"] = 4
    result = owner.select_top_three(scores, admitted=list(scores), gamers=["z-gamer"])
    assert result["gamer_top_half"] == ["z-gamer"]
    assert result["ranks"]["b"] == result["ranks"]["z-gamer"] == 2
    alternate = owner.select_top_three(
        {m: -s for m, s in scores.items()}, admitted=list(scores), gamers=[]
    )
    assert alternate["selected"] != result["selected"]


def test_missing_scores_never_shrink_top_half_denominator():
    result = owner.select_top_three(
        {"a": 3, "b": 2, "c": 1}, admitted=["a", "b", "c", "missing"], gamers=[]
    )
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["admitted_count"] == 4
    assert result["missing_scores"] == ["missing"]


def test_value_never_reselects_top_three_and_unknown_withholds_entire_readout():
    scores = {"a": 4, "b": 3, "c": 2, "value-best": 1}
    selection = owner.select_top_three(scores, admitted=list(scores), gamers=[])
    values = {
        "a": {"q1": 60, "q2": 120},
        "b": {"q1": 120, "q2": 180},
        "c": {"q1": 180, "q2": 240},
        "value-best": {"q1": 0, "q2": 0},
    }
    result = owner.selected_regret_minutes(selection, values, ["q1", "q2"])
    assert set(result["per_selected_member_min"]) == {"a", "b", "c"}
    assert result["per_selected_member_min"]["a"] == [1, 2]
    assert result["mean_regret_min"] == 2.5
    values["b"]["q2"] = None
    unknown = owner.selected_regret_minutes(selection, values, ["q1", "q2"])
    assert unknown["status"] == "INSUFFICIENT_EVIDENCE"
    assert unknown["mean_regret_min"] is None
    assert selection["selected"] == ["a", "b", "c"]


def test_tampered_selection_receipt_refused():
    selection = owner.select_top_three(
        {"a": 3, "b": 2, "c": 1, "d": 0}, admitted=["a", "b", "c", "d"], gamers=[]
    )
    selection["selected"] = ["a", "b", "d"]
    with pytest.raises(LabRefused, match="registered_top_three_selection_required"):
        owner.selected_regret_minutes(selection, {}, ["q"])
