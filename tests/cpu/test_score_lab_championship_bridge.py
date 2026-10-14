"""Synthetic-only rev-5 bridge controls; no actual championship or model run."""

import copy
from dataclasses import asdict, replace

import pytest

from carbon.championship_stats import (
    Rev5Case,
    Rev5Contender,
    Rev5Rule,
    select_rev5_winner,
)
from scripts.dev.score_lab import championship_bridge as bridge
from scripts.dev.score_lab.core import SCHEMA, LabRefused


def fixture():
    questions = tuple(f"S-{i}" for i in range(8))
    evidence = {
        "schema": bridge.SCHEMA,
        "scope": bridge.SCOPE,
        "metric": {
            "id": "fixture-accuracy-v1",
            "kind": "nonnegative_case_accuracy_error",
            "unit": "toy-error",
            "source_sha256": "a" * 64,
        },
        "case_blocks": {q: q for q in questions},
        "errors": {
            "king": {q: 1.0 for q in questions},
            "good": {q: 0.9 for q in questions},
            "known-bad": {q: 0.8 for q in questions},
        },
    }
    rule = Rev5Rule(
        "fixture-rule", "fixture-contract", "round-1", "king", 8, 2, 0.02, 0.01, "case"
    )
    return evidence, rule, questions


def receipts(evidence, rule, draws):
    return {
        a: {
            "receipt_id": f"synthetic-guard-{a}-{rule.batch_id}",
            "artifact_id": a,
            "batch_sha256": bridge.batch_binding(evidence, rule, draws),
            "g_feas": "FAIL" if a == "known-bad" else "PASS",
            "important_region": "PASS",
        }
        for a in evidence["errors"]
    }


def select(evidence, rule, draws, guards=None):
    return bridge.accuracy_round(
        evidence,
        rule,
        draws=draws,
        contenders=tuple(a for a in evidence["errors"] if a != rule.king_id),
        guards=receipts(evidence, rule, draws) if guards is None else guards,
    )


def value_panel():
    return {
        "schema": SCHEMA,
        "scope": bridge.SCOPE,
        "score_questions": {"S": {}},
        "value_questions": {"V0": {}, "V1": {}},
        "members": [
            {
                "id": a,
                "recipe": a,
                "kind": "MODEL",
                "score_predictions": {"S": {}},
                "value_losses": {"V0": value, "V1": value},
            }
            for a, value in (("king", 0.0), ("good", -2.0), ("known-bad", 2.0))
        ],
    }


def test_exact_library_parity_and_determinism():
    evidence, rule, draws = fixture()
    before = copy.deepcopy(evidence)
    actual = select(evidence, rule, draws)
    expected = select_rev5_winner(
        rule,
        tuple(
            Rev5Contender(
                a,
                tuple(Rev5Case(q, q, 1.0, evidence["errors"][a][q]) for q in draws),
                a != "known-bad",
                True,
            )
            for a in ("good", "known-bad")
        ),
    )
    assert actual["winner_id"] == expected.winner_id == "good"
    assert actual["outcomes"] == [asdict(r) for r in expected.outcomes]
    assert select(evidence, rule, draws) == actual
    assert evidence == before


def test_guards_are_effective_and_ties_stay_with_king():
    evidence, rule, draws = fixture()
    guards = receipts(evidence, rule, draws)
    guards["known-bad"]["g_feas"] = "PASS"
    assert select(evidence, rule, draws, guards)["winner_id"] == "known-bad"
    guards["known-bad"]["important_region"] = "FAIL"
    assert select(evidence, rule, draws, guards)["winner_id"] == "good"
    evidence["errors"]["known-bad"] = copy.deepcopy(evidence["errors"]["good"])
    guards = receipts(evidence, rule, draws)
    guards["known-bad"]["g_feas"] = "PASS"
    assert select(evidence, rule, draws, guards)["winner_id"] == "king"


def test_duplicate_cases_are_collapsed_by_existing_rule():
    evidence, rule, draws = fixture()
    original = select(evidence, rule, draws)
    repeated = draws + draws
    result = select(evidence, replace(rule, drawn_cases=16), repeated)
    assert result["unique_cases"] == 8
    assert result["outcomes"] == original["outcomes"]


@pytest.mark.parametrize("field", ("draws", "contenders"))
def test_non_string_identities_refused_before_hashing(field):
    evidence, rule, draws = fixture()
    inputs = {"draws": draws, "contenders": ("good", "known-bad")}
    inputs[field] = ([],)
    with pytest.raises(LabRefused, match="case_or_artifact_identity"):
        bridge.accuracy_round(evidence, rule, guards={}, **inputs)


def test_case_draw_blocks_cannot_be_relabelled_as_shared_block():
    evidence, rule, draws = fixture()
    evidence["case_blocks"] = {q: "one-block" for q in draws}
    with pytest.raises(LabRefused, match="case_draw_block_mismatch"):
        select(evidence, rule, draws)


def test_value_overlap_checked_against_actual_championship_draws():
    evidence, rule, draws = fixture()
    committed = select(evidence, rule, draws)
    panel = value_panel()
    # The panel's decorative score side says only S; actual draw S-0 still binds.
    panel["value_questions"][draws[0]] = panel["value_questions"].pop("V0")
    for member in panel["members"]:
        member["value_losses"][draws[0]] = member["value_losses"].pop("V0")
    with pytest.raises(LabRefused, match="score_value_case_overlap"):
        bridge.value_diagnostic(committed, panel)


@pytest.mark.parametrize("guard", ("g_feas", "important_region"))
def test_unresolved_guard_never_enters_selector(monkeypatch, guard):
    evidence, rule, draws = fixture()
    guards = receipts(evidence, rule, draws)
    guards["good"][guard] = "UNRESOLVED"
    monkeypatch.setattr(
        bridge,
        "select_rev5_winner",
        lambda *a: pytest.fail("unsettled guard entered selector"),
    )
    result = select(evidence, rule, draws, guards)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["reason"] == "unresolved_hard_guard"
    assert result["winner_id"] is None


def test_missing_accuracy_not_counted_as_candidate_failure(monkeypatch):
    evidence, rule, draws = fixture()
    evidence["errors"]["good"][draws[0]] = None
    monkeypatch.setattr(
        bridge,
        "select_rev5_winner",
        lambda *a: pytest.fail("unresolved measurement entered selector"),
    )
    result = select(evidence, rule, draws)
    assert result["reason"] == "unresolved_accuracy_measurement"
    assert result["winner_id"] is None


@pytest.mark.parametrize(
    "mutation", ("negative", "nan", "aggregate", "public", "receipt", "metric")
)
def test_wrong_scope_measurement_or_guard_binding_refused(mutation):
    evidence, rule, draws = fixture()
    guards = receipts(evidence, rule, draws)
    if mutation in ("negative", "nan"):
        evidence["errors"]["good"][draws[0]] = (
            -1 if mutation == "negative" else float("nan")
        )
    elif mutation == "aggregate":
        evidence["metric"]["kind"] = "signed_whole_panel_gain"
    elif mutation == "public":
        evidence["scope"] = "PUBLIC_DEVELOPMENT"
    elif mutation == "receipt":
        guards["good"]["batch_sha256"] = "b" * 64
    else:
        evidence["metric"].pop("unit")
    with pytest.raises(LabRefused):
        select(evidence, rule, draws, guards)


def test_value_is_read_after_commit_and_changes_no_championship_output():
    evidence, rule, draws = fixture()
    committed = select(evidence, rule, draws)
    before = copy.deepcopy(committed)
    panel = value_panel()
    diagnostic = bridge.value_diagnostic(committed, panel)
    assert diagnostic["crown_is_best_compared_value"]
    panel["members"][1]["value_losses"]["V0"] = 10.0
    changed = bridge.value_diagnostic(committed, panel)
    assert not changed["crown_is_best_compared_value"]
    assert changed["regret_against_best_compared_member"] > 0
    assert committed == before
    panel["members"][2]["value_losses"]["V0"] = None
    masked = bridge.value_diagnostic(committed, panel)
    assert masked["value_questions"] == 1
    assert masked["value_questions_offered"] == 2
    assert masked["crown_is_best_compared_value"]
    committed["winner_id"] = "known-bad"
    with pytest.raises(LabRefused, match="commit_binding"):
        bridge.value_diagnostic(committed, panel)


def test_trajectory_chains_rounds_without_carry_forward():
    evidence, rule, draws = fixture()
    first = select(evidence, rule, draws)
    second_rule = replace(rule, batch_id="round-2", king_id="good")
    second = select(evidence, second_rule, draws)
    assert second["winner_id"] == "good"
    report = bridge.trajectory_diagnostic((first, second), value_panel())
    assert report["takeovers"] == 1
    assert report["rounds_best_compared_member_holds_crown"] == 2
    assert report["first_round_best_compared_member_holds_crown"] == 1
    with pytest.raises(LabRefused, match="identity_or_chain"):
        bridge.trajectory_diagnostic((first, first), value_panel())


def test_additive_score_offsets_change_relative_margin_despite_same_order():
    """Counterexample, not a supported score conversion or an adopted policy."""
    evidence, rule, draws = fixture()
    evidence["errors"].pop("known-bad")
    winners = []
    for offset in (0.0, 9.0):
        # Same signed gains: king=-1, good=-0.9. Candidate mapping loss=C-score.
        evidence["errors"]["king"] = {q: offset + 1.0 for q in draws}
        evidence["errors"]["good"] = {q: offset + 0.9 for q in draws}
        winners.append(
            select(evidence, replace(rule, max_contenders=1), draws)["winner_id"]
        )
    assert winners == ["good", "king"]


def test_registered_blocks_use_existing_block_means_not_case_count():
    evidence, rule, draws = fixture()
    rule = replace(rule, draw_unit="registered_block")
    evidence["case_blocks"] = {q: "A" if i < 6 else "B" for i, q in enumerate(draws)}
    evidence["errors"].pop("known-bad")
    evidence["errors"]["good"] = {q: 0.5 if i < 6 else 1.2 for i, q in enumerate(draws)}
    expected = select_rev5_winner(
        rule,
        (
            Rev5Contender(
                "good",
                tuple(
                    Rev5Case(
                        q,
                        evidence["case_blocks"][q],
                        1.0,
                        evidence["errors"]["good"][q],
                    )
                    for q in draws
                ),
                True,
                True,
            ),
        ),
    )
    actual = select(evidence, rule, draws)
    assert actual["outcomes"] == [asdict(r) for r in expected.outcomes]
    assert actual["outcomes"][0]["block_count"] == 2
    assert actual["winner_id"] == expected.winner_id == "king"


@pytest.mark.parametrize(
    "condition,reason",
    (
        ("zero", "relative_improvement_undefined_for_zero_king_error"),
        ("block", "fewer_than_two_independent_draw_blocks"),
        ("king_guard", "incumbent_qualification_unavailable"),
    ),
)
def test_undefined_rounds_remain_unscored(condition, reason, monkeypatch):
    evidence, rule, draws = fixture()
    if condition == "zero":
        evidence["errors"]["king"] = {q: 0.0 for q in draws}
    elif condition == "block":
        evidence["case_blocks"] = {q: "one" for q in draws}
        rule = replace(rule, draw_unit="registered_block")
    guards = receipts(evidence, rule, draws)
    if condition == "king_guard":
        guards["king"]["g_feas"] = "FAIL"
    monkeypatch.setattr(
        bridge, "select_rev5_winner", lambda *a: pytest.fail("undefined round scored")
    )
    actual = select(evidence, rule, draws, guards)
    assert actual["status"] == "INSUFFICIENT_EVIDENCE"
    assert actual["reason"] == reason
    assert bridge.value_diagnostic(actual, value_panel())["reason"] == "round_unscored"


def test_no_common_value_outcomes_is_not_zero_regret():
    evidence, rule, draws = fixture()
    actual = select(evidence, rule, draws)
    panel = value_panel()
    panel["members"][0]["value_losses"] = {"V0": None, "V1": None}
    assert bridge.value_diagnostic(actual, panel) == {
        "status": "INSUFFICIENT_EVIDENCE",
        "reason": "no_common_value_outcomes",
    }
