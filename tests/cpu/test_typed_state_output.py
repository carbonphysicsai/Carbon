"""Rule bt32-threshold-recovery-two-part.v1 (spec line rev 2, sha256 d0f6fc57...): the Validator's build checks 1-10.

Synthetic values only: the threshold / U / weight below are fixtures, never the registered 3.2 numbers (HUMAN_INPUT).
"""

import hashlib
import math

import pytest

from carbon.scoring import typed_state_output as tso

REC = tso.TypedOutput("threshold_recovery_s", "recovery", tso.RULE_ID, 85.0, "peak_top_c", 0.5, 2.0, 0.5)
FIRST = tso.TypedOutput("first_95c_crossing_s", "first_crossing", tso.RULE_ID, 95.0, "peak_top_c", 0.5, 2.0, 0.5)
FAR = 90.0  # a truth peak far from 85 C (resolvable)
NEAR = 85.2  # within band_u = 0.5 of 85 C (not resolvable)
A_C = 8.0  # a synthetic admitted value anchor (> 1)


def test_registration_refuses_human_input_and_wrong_rule():
    tso.check(REC)
    tso.check(FIRST)
    for field in ("threshold_c", "band_u", "value_u", "event_weight"):
        with pytest.raises(tso.TypedOutputRefused, match=f"{field}_is_human_input"):
            tso.check(tso.TypedOutput(**{**REC.__dict__, field: None}))
    with pytest.raises(tso.TypedOutputRefused, match="rule_is_not_the_registered_one"):
        tso.check(tso.TypedOutput(**{**REC.__dict__, "rule": "other.v1"}))
    with pytest.raises(tso.TypedOutputRefused, match="event_weight_must_be_in_0_1"):
        tso.check(tso.TypedOutput(**{**REC.__dict__, "event_weight": 1.0}))


# -- check 1: the 9 recovery state pairs + a missing key ------------------------------------------------------------
RECOVERY_VALUES = {"NEVER_REACHED": "NEVER_REACHED", "NOT_RECOVERED": "NOT_RECOVERED", "VALUE": 10.0}


@pytest.mark.parametrize("truth", sorted(RECOVERY_VALUES))
@pytest.mark.parametrize("pred", sorted(RECOVERY_VALUES))
def test_check1_nine_state_pairs(truth, pred):
    t, p = RECOVERY_VALUES[truth], RECOVERY_VALUES[pred]
    assert tso.state("recovery", p) is not None  # no token ever fails the gate
    m, log_b, b, t_count = tso.case_sums(REC, t, p, FAR)
    assert m == (0 if truth == pred else 1)
    assert t_count == (1 if truth == "VALUE" else 0)
    assert b == (1 if truth == pred == "VALUE" else 0)
    assert log_b == 0.0  # equal values (or no value pair): floored at 1 U


def test_check1_missing_key_null_and_garbage_stay_invalid():
    for bad in (None, "NOT_REACHED", "never_reached", -1.0, math.nan, math.inf, True, [], {}):
        assert tso.state("recovery", bad) is None
    with pytest.raises(tso.TypedOutputRefused, match="prediction_invalid"):
        tso.case_sums(REC, 10.0, None, FAR)
    with pytest.raises(tso.TypedOutputRefused, match="truth_unreadable"):
        tso.case_sums(REC, None, 10.0, FAR)  # a truth must be typed by the reference, never null


# -- check 2: the coverage factor -------------------------------------------------------------------------------------
def _value_score(cases):
    return tso.combine(REC, tso.cell_sums(REC, cases), m_anchor=0, value_anchor=A_C)


def test_check2_calling_empty_never_pays_where_own_error_is_within_the_anchor():
    truths = [10.0, 20.0, 30.0, 40.0]
    errors = [1.0, 3.0, 7.9, 6.0]  # in U (value_u = 2): every own error <= A_c = 8
    answered = [(t, t + e * REC.value_u, FAR) for t, e in zip(truths, errors)]
    base = _value_score(answered)
    for k in range(len(answered)):
        dropped = list(answered)
        dropped[k] = (truths[k], "NEVER_REACHED", FAR)
        assert _value_score(dropped) <= base + 1e-12
    # and a case whose own error is WORSE than A_c may be dropped profitably (the rule as written, not a hole)
    worse = answered[:3] + [(40.0, 40.0 + 20.0 * REC.value_u, FAR)]
    assert _value_score(worse[:3] + [(40.0, "NEVER_REACHED", FAR)]) >= _value_score(worse) - 1e-12


def test_check2_band_case_called_empty_leaves_t():
    in_t = tso.case_sums(REC, 10.0, "NEVER_REACHED", FAR)
    in_band = tso.case_sums(REC, 10.0, "NEVER_REACHED", NEAR)
    assert in_t == (1, 0.0, 0, 1)  # resolvable: an EVENT miss and in T (coverage charges it)
    assert in_band == (0, 0.0, 0, 0)  # band: neither an event miss nor in T
    base = [(20.0, 22.0, FAR)]
    assert _value_score(base + [(10.0, "NEVER_REACHED", NEAR)]) == _value_score(base)


# -- check 3: m_anchor = 0 / check 4: |T| = 0 -------------------------------------------------------------------------
def test_check3_m_anchor_zero_scores_value_only():
    cases = [(10.0, 12.0, FAR), ("NEVER_REACHED", 5.0, FAR)]
    sums = tso.cell_sums(REC, cases)
    only_value = tso.combine(REC, sums, m_anchor=0, value_anchor=A_C)
    m, log_b, b, t = sums
    assert only_value == tso.log_skill(A_C, math.exp(log_b / b)) * b / t


def test_check4_t_zero_scores_event_only():
    cases = [("NEVER_REACHED", "NEVER_REACHED", FAR), ("NOT_RECOVERED", "NEVER_REACHED", FAR)]
    sums = tso.cell_sums(REC, cases)
    assert sums[3] == 0
    assert tso.combine(REC, sums, m_anchor=2, value_anchor=A_C) == 1.0 - 1 / 2
    assert tso.combine(REC, sums, m_anchor=0, value_anchor=A_C) is None  # neither part: not scored


def test_both_parts_combine_with_the_registered_weight():
    cases = [(10.0, 10.0, FAR), ("NEVER_REACHED", 3.0, FAR)]
    sums = tso.cell_sums(REC, cases)
    event = 1.0 - 1 / 4
    value = tso.log_skill(A_C, 1.0) * 1 / 1
    assert tso.combine(REC, sums, m_anchor=4, value_anchor=A_C) == pytest.approx(0.5 * event + 0.5 * value)
    assert tso.combine(REC, sums, m_anchor=4, value_anchor=None) == event  # value tests failed: event only


# -- check 5: the S2 band ---------------------------------------------------------------------------------------------
def test_check5_band_state_error_does_not_move_the_event_part():
    base = [(10.0, 10.0, FAR), ("NEVER_REACHED", "NEVER_REACHED", FAR)]
    right = base + [("NEVER_REACHED", "NEVER_REACHED", NEAR)]
    wrong = base + [("NEVER_REACHED", "NOT_RECOVERED", NEAR)]
    assert tso.cell_sums(REC, right)[0] == tso.cell_sums(REC, wrong)[0] == 0
    assert tso.combine(REC, tso.cell_sums(REC, right), m_anchor=1, value_anchor=None) == tso.combine(
        REC, tso.cell_sums(REC, wrong), m_anchor=1, value_anchor=None
    )
    assert tso.in_band(REC, 85.5) and not tso.in_band(REC, 85.51)


# -- check 6: the panel's two-part form -------------------------------------------------------------------------------
def test_check6_panel_members_predict_state_and_value():
    cases = [(10.0, FAR), ("NEVER_REACHED", FAR), (30.0, NEAR)]
    members = {
        "fit_a": [{"state": 10.0, "value": 10.0}, {"state": 4.0, "value": 4.0}, {"state": "NEVER_REACHED", "value": 36.0}],
        "fit_b": [{"state": "NEVER_REACHED", "value": 14.0}, {"state": "NEVER_REACHED", "value": 1.0}, {"state": 30.0, "value": 30.0}],
    }
    m_anchor, a_c = tso.panel_anchor(REC, members, cases)
    assert m_anchor == 1  # fit_a misses case 2, fit_b misses case 1; the band case is never counted
    # A_c over ALL truth-value cases with each member's VALUE prediction, even where its state says empty
    a_err = math.exp((math.log(max(0.0 / 2, 1)) + math.log(max(6.0 / 2, 1))) / 2)
    b_err = math.exp((math.log(max(4.0 / 2, 1)) + math.log(max(0.0 / 2, 1))) / 2)
    assert a_c == pytest.approx(min(a_err, b_err))
    for bad in ({"state": 10.0}, {"value": 10.0}, {"state": None, "value": 1.0}, {"state": 1.0, "value": "NEVER_REACHED"}):
        broken = {"fit_a": [bad] + members["fit_a"][1:]}
        with pytest.raises(tso.TypedOutputRefused, match="panel_member"):
            tso.panel_anchor(REC, broken, cases)


# -- check 7: the kit text is byte-equal to the spec line rev 2's public string ---------------------------------------
def test_check7_public_text_is_the_spec_lines():
    # sha256 of the rev 2 "Public text" blockquote with each "> " / ">" prefix removed, lines joined by "\n"
    assert hashlib.sha256(tso.PUBLIC_TEXT.encode()).hexdigest() == "ee292ba46e62b79f3463cab92845fd4e30ceb2f71ea34a9720a1446633408cc9"


# -- check 8: first_95c_crossing_s -------------------------------------------------------------------------------------
@pytest.mark.parametrize("truth", ["NOT_REACHED", 30.0])
@pytest.mark.parametrize("pred", ["NOT_REACHED", 31.0])
def test_check8_first_crossing_four_pairs(truth, pred):
    m, _log_b, b, t = tso.case_sums(FIRST, truth, pred, 99.0)
    same = (truth == "NOT_REACHED") == (pred == "NOT_REACHED")
    assert m == (0 if same else 1)
    assert t == (1 if truth != "NOT_REACHED" else 0)
    assert b == (1 if truth != "NOT_REACHED" and pred != "NOT_REACHED" else 0)


def test_check8_first_crossing_refuses_recovery_tokens_and_bands_at_95():
    assert tso.state("first_crossing", "NOT_RECOVERED") is None
    assert tso.state("first_crossing", "NEVER_REACHED") is None
    assert tso.state("first_crossing", None) is None
    assert tso.in_band(FIRST, 95.4) and not tso.in_band(FIRST, 85.0)


# -- check 9: the gate reads B only -----------------------------------------------------------------------------------
def test_check9_gate_reads_only_both_value_cases():
    base = [(10.0, 13.0, FAR), (20.0, 20.0, FAR)]
    mismatch = base + [(30.0, "NEVER_REACHED", FAR), ("NEVER_REACHED", 4.0, FAR)]
    assert tso.gate_ratios(REC, base) == tso.gate_ratios(REC, mismatch) == [1.5, 0.0]
    assert tso.cell_sums(REC, mismatch)[0] == 2  # the mismatches are charged in the EVENT part instead
