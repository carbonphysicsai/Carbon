"""Rule joint-chip-thermal-typed-state.v1 (case-level RUNAWAY; model-eval ruling 22 Nov 03:03:09Z, shape only).

Synthetic values only: the band, the event weight and the anchors below are fixtures, never registered numbers
(HUMAN_INPUT).
"""

import ast
import pathlib

import pytest

from carbon.scoring import case_state_output as cso
from carbon.scoring import typed_state_output as tso

REG = cso.CaseState("runaway", cso.RULE_ID, "stability_margin", 0.0, 0.1, 0.5)
R, B = cso.RUNAWAY, cso.BOUNDED
FAR = 1.0  # a band truth far from the centre (resolvable)
NEAR = 0.05  # within band_u = 0.1 of 0.0 (not resolvable)


def test_registration_refuses_human_input_and_wrong_rule():
    cso.check(REG)
    for field in ("band_output", "band_center", "band_u", "event_weight"):
        with pytest.raises(cso.CaseStateRefused, match=f"{field}_is_human_input"):
            cso.check(cso.CaseState(**{**REG.__dict__, field: None}))
    with pytest.raises(cso.CaseStateRefused, match="rule_is_not_the_registered_one"):
        cso.check(cso.CaseState(**{**REG.__dict__, "rule": tso.RULE_ID}))
    for weight in (0.0, 1.0, float("nan"), True):
        with pytest.raises(cso.CaseStateRefused, match="event_weight_must_be_in_0_1"):
            cso.check(cso.CaseState(**{**REG.__dict__, "event_weight": weight}))
    with pytest.raises(cso.CaseStateRefused, match="band_u_must_be_non_negative"):
        cso.check(cso.CaseState(**{**REG.__dict__, "band_u": -0.1}))
    with pytest.raises(cso.CaseStateRefused, match="band_output_missing"):
        cso.check(cso.CaseState(**{**REG.__dict__, "band_output": "runaway"}))


def test_states_reference_fault_vs_invalid_answer():
    assert cso.state(R) == R and cso.state(B) == B
    for bad in (None, "", "runaway", "NOT_REACHED", 1.0, True):
        assert cso.state(bad) is None
        with pytest.raises(cso.CaseStateRefused, match="truth_unreadable"):
            cso.truth_state(bad)


@pytest.mark.parametrize(
    "truth,pred,scored",
    [(B, B, True), (B, R, False), (R, B, False), (R, R, False)],
)
def test_masking_c2(truth, pred, scored):
    assert cso.numeric_scored(truth, pred) is scored


def test_masking_refuses_an_ungated_answer():
    with pytest.raises(cso.CaseStateRefused, match="prediction_invalid"):
        cso.numeric_scored(B, 3.0)


@pytest.mark.parametrize(
    "truth,pred,miss",
    [(B, B, 0), (R, R, 0), (B, R, 1), (R, B, 1)],
)
def test_event_symmetric_c4(truth, pred, miss):
    # model-eval's change: a missed runaway (finite answers on a RUNAWAY case) is charged like a false alarm
    assert cso.case_sums(REG, truth, pred, FAR) == (miss, 1)


@pytest.mark.parametrize("truth,pred", [(B, R), (R, B), (R, R)])
def test_band_neither_credits_nor_charges_c3(truth, pred):
    assert cso.case_sums(REG, truth, pred, NEAR) == cso.ZERO


def test_band_truth_must_be_finite():
    with pytest.raises(cso.CaseStateRefused, match="band_truth_not_finite"):
        cso.case_sums(REG, R, R, float("inf"))


def test_event_score_and_pooling():
    cases = [(R, B, FAR), (B, B, FAR), (B, R, FAR), (R, R, NEAR), (B, B, FAR)]
    sums = cso.cell_sums(REG, cases)
    assert sums == (2, 4)
    assert cso.event_score(sums, m_anchor=4) == pytest.approx(0.5)
    assert cso.event_score(sums, m_anchor=1) == 0.0  # clipped
    assert cso.event_score(sums, m_anchor=0) is None  # no evidence
    assert cso.event_score((0, 0), m_anchor=2) is None
    # a subset on r of R resolvable cases compares rates: (2/4) / (4/8) = 1 -> 0
    assert cso.event_score(sums, m_anchor=4, r_anchor=8) == pytest.approx(0.0)
    assert cso.event_score(sums, m_anchor=2, r_anchor=8) == 0.0
    assert cso.event_score((1, 4), m_anchor=4, r_anchor=8) == pytest.approx(0.5)
    # pooled sums recompose exactly from halves
    halves = cso.cell_sums(REG, cases[:2]), cso.cell_sums(REG, cases[2:])
    assert tuple(map(sum, zip(*halves))) == sums
    with pytest.raises(cso.CaseStateRefused, match="r_anchor_must_cover_m_anchor"):
        cso.event_score(sums, m_anchor=4, r_anchor=3)
    with pytest.raises(cso.CaseStateRefused, match="m_anchor_must_be_a_count"):
        cso.event_score(sums, m_anchor=1.0)


def test_combine_c6():
    assert cso.combine(REG, 1.0, 0.0) == pytest.approx(0.5)
    assert cso.combine(REG, None, 0.25) == 0.25
    assert cso.combine(REG, 0.75, None) == 0.75
    assert cso.combine(REG, None, None) is None


def test_panel_anchor_c5():
    cases = [(R, FAR), (B, FAR), (B, NEAR)]
    members = {"a": [B, B, R], "b": [R, R, B], "c": [R, B, R]}
    assert cso.panel_anchor(REG, members, cases) == 0
    assert cso.panel_anchor(REG, {"a": [B, B, R], "b": [R, R, B]}, cases) == 1
    with pytest.raises(cso.CaseStateRefused, match="member_misaligned:a"):
        cso.panel_anchor(REG, {"a": [B]}, cases)
    with pytest.raises(cso.CaseStateRefused, match="member_state_invalid:a"):
        cso.panel_anchor(REG, {"a": [B, 2.0, R]}, cases)
    with pytest.raises(cso.CaseStateRefused, match="panel_empty"):
        cso.panel_anchor(REG, {}, cases)


def test_time_outputs_reuse_bt32_kinds_under_the_joint_rule():
    throttle = tso.TypedOutput(
        "time_to_throttle_s",
        "first_crossing",
        cso.RULE_ID,
        95.0,
        "peak_c",
        0.5,
        2.0,
        0.5,
    )
    recovery = tso.TypedOutput(
        "recovery_s", "recovery", cso.RULE_ID, 85.0, "peak_c", 0.5, 2.0, 0.5
    )
    cso.check_time(throttle)
    cso.check_time(recovery)
    with pytest.raises(cso.CaseStateRefused, match="time_rule_is_not_the_joint_one"):
        cso.check_time(tso.TypedOutput(**{**throttle.__dict__, "rule": tso.RULE_ID}))
    with pytest.raises(cso.CaseStateRefused, match="value_u_is_human_input"):
        cso.check_time(tso.TypedOutput(**{**throttle.__dict__, "value_u": None}))
    with pytest.raises(cso.CaseStateRefused, match="kind_unknown"):
        cso.check_time(tso.TypedOutput(**{**throttle.__dict__, "kind": "runaway"}))


def test_new_module_only_imports_bt32_never_edits_it():
    # The rule is a NEW module (model-eval: "it never touches BT 3.2 bytes"): BT 3.2's module stays RULE_ID-bound.
    assert tso.RULE_ID == "bt32-threshold-recovery-two-part.v1"
    assert cso.RULE_ID != tso.RULE_ID
    source = pathlib.Path(cso.__file__).read_text(encoding="utf-8")
    imports = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imports <= {"__future__", "dataclasses", "carbon.scoring"}
