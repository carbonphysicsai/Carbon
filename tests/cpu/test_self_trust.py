"""Self-trust rule carbon.self-trust.report-only.v1 (`carbon.scoring.self_trust`): block, refusals, calibration, send-back.

Synthetic values only: every coverage / weight / anchor / cut / cost below is a fixture, never a registered science value
(HUMAN_INPUT for every version until its owner registers it). No hidden data, no Challenge material.
"""

from __future__ import annotations

import ast
import math
import pathlib
from dataclasses import replace
from statistics import NormalDist

import pytest

from carbon.scoring import self_trust as st

ROOT = pathlib.Path(__file__).resolve().parents[2]


def rule(form=st.INTERVAL, **changes):
    base = st.SelfTrustRule(
        rule=st.RULE_ID,
        form=form,
        outputs=("a", "b"),
        send_back_outputs=("a",),
        nominal_coverage=0.5,
        output_weights={"a": 0.5, "b": 0.5},
        interval_score_anchor_u={"a": 6.0, "b": 6.0},
        badly_wrong_cut_u={"a": 1.0},
        miss_cost=1.0,
        send_back_cost=0.25,
        calibration_weight=0.5,
    )
    return replace(base, **changes)


def answer(r, flag=False, sigmas=None, bands=None):
    return st.TrustAnswer(form=r.form, sigmas=sigmas or {}, bands=bands or {}, flag=flag)


def case(r, p, t, u=None, flag=False, sigmas=None, bands=None, status=st.PRESENT):
    u = u or {name: 1.0 for name in p}
    ans = None if status != st.PRESENT else answer(r, flag, sigmas, bands)
    return st.TrustCase(predictions=p, truths=t, u=u, status=status, answer=ans)


# -- registration -------------------------------------------------------------------------------------------------------


def test_complete_registration_passes():
    st.check(rule())
    st.check(rule(st.SIGMA))


@pytest.mark.parametrize("field", st.SCIENCE_FIELDS)
def test_every_science_value_is_required(field):
    with pytest.raises(st.SelfTrustRefused, match=f"self_trust_{field}_is_human_input"):
        st.check(rule(**{field: None}))


@pytest.mark.parametrize(
    "changes, code",
    [
        ({"rule": "other.v1"}, "rule_is_not_the_registered_one"),
        ({"form": "quantiles"}, "form_unknown"),
        ({"outputs": ()}, "outputs_malformed"),
        ({"outputs": ("a", "a")}, "outputs_malformed"),
        ({"send_back_outputs": ("c",)}, "send_back_outputs_must_be_a_subset"),
        ({"nominal_coverage": 1.0}, "nominal_coverage_must_be_in_0_1"),
        ({"nominal_coverage": 0.0}, "nominal_coverage_must_be_in_0_1"),
        ({"nominal_coverage": True}, "nominal_coverage_must_be_in_0_1"),
        ({"output_weights": {"a": 1.0}}, "output_weights_must_cover_exactly"),
        ({"output_weights": {"a": 0.5, "b": 0.6}}, "output_weights_must_sum_to_1"),
        ({"output_weights": {"a": -0.5, "b": 1.5}}, "output_weights_must_be_non_negative"),
        ({"interval_score_anchor_u": {"a": 6.0, "b": 0.0}}, "anchor_u_must_be_positive"),
        ({"badly_wrong_cut_u": {"a": 1.0, "b": 1.0}}, "badly_wrong_cut_u_must_cover_exactly"),
        ({"badly_wrong_cut_u": {"a": math.inf}}, "badly_wrong_cut_u_must_be_positive"),
        ({"miss_cost": 0.0}, "miss_cost_must_be_positive"),
        ({"send_back_cost": 1.0}, "send_back_cost_must_be_in_0_miss_cost"),
        ({"send_back_cost": 0.0}, "send_back_cost_must_be_in_0_miss_cost"),
        ({"calibration_weight": 1.5}, "calibration_weight_must_be_in_0_1"),
    ],
)
def test_out_of_domain_values_refuse(changes, code):
    with pytest.raises(st.SelfTrustRefused, match=code):
        st.check(rule(**changes))


def test_a_non_rule_refuses():
    with pytest.raises(st.SelfTrustRefused, match="rule_malformed"):
        st.check({"rule": st.RULE_ID})


# -- T1: the block ------------------------------------------------------------------------------------------------------


def test_block_widths():
    assert st.block_width(rule(st.SIGMA)) == 3  # 2 sigmas + flag
    assert st.block_width(rule(st.INTERVAL)) == 5  # 2 (lo, hi) + flag
    assert st.accepted_widths(10, None) == (10,)
    assert st.accepted_widths(10, rule(st.SIGMA)) == (10,)  # undeclared: the width of today
    assert st.accepted_widths(10, rule(st.SIGMA), declared=True) == (13,)
    assert st.accepted_widths(10, None, declared=True) == (10,)
    with pytest.raises(st.SelfTrustRefused, match="base_width_malformed"):
        st.accepted_widths(0, None)


def test_no_rule_is_the_identity():
    raw = [1.0, 2.0, 3.0, 4.0, 5.0]
    split = st.split_row(raw, 3, None)
    assert split.base is raw and split.status == st.NOT_ADOPTED and split.answer is None


def test_absent_block_leaves_the_row_untouched():
    raw = [1.0, 2.0, 3.0]
    split = st.split_row(raw, 3, rule(st.SIGMA))
    assert split.base is raw and split.status == st.ABSENT and split.answer is None


def test_present_sigma_block_splits():
    r = rule(st.SIGMA)
    split = st.split_row([1.0, 2.0, 3.0, 0.5, 0.25, 1.0], 3, r, declared=True)
    assert split.base == [1.0, 2.0, 3.0]
    assert split.status == st.PRESENT
    assert split.answer.sigmas == {"a": 0.5, "b": 0.25} and split.answer.flag is True


def test_present_interval_block_splits():
    r = rule(st.INTERVAL)
    split = st.split_row([9.0, 1.0, 3.0, -2.0, 2.0, 0.0], 1, r, declared=True)
    assert split.base == [9.0]
    assert split.answer.bands == {"a": (1.0, 3.0), "b": (-2.0, 2.0)} and split.answer.flag is False


def test_wrong_width_is_left_to_todays_path():
    raw = [1.0, 2.0, 3.0, 0.5]
    split = st.split_row(raw, 3, rule(st.SIGMA), declared=True)
    assert split.base is raw and split.status == st.WIDTH_INVALID


def test_width_alone_never_switches_the_mode():
    # V2 pre-read: a miner who sends W + block WITHOUT declaring it has a wrong width (today's OUTPUT_CONTRACT_DIFFERS),
    # and a declared candidate that sends only W has a wrong width too.
    r = rule(st.SIGMA)
    block_row = [1.0, 2.0, 3.0, 0.5, 0.25, 1.0]
    undeclared = st.split_row(block_row, 3, r)
    assert undeclared.base is block_row and undeclared.status == st.WIDTH_INVALID
    declared_short = st.split_row([1.0, 2.0, 3.0], 3, r, declared=True)
    assert declared_short.status == st.WIDTH_INVALID


@pytest.mark.parametrize(
    "block",
    [
        [0.0, 0.25, 0.0],  # sigma 0
        [-0.5, 0.25, 0.0],  # negative sigma
        [math.nan, 0.25, 0.0],
        [math.inf, 0.25, 0.0],
        [0.5, 0.25, 0.5],  # flag neither 0 nor 1
        [0.5, True, 0.0],  # a bool cell
        [0.5, "0.25", 0.0],  # a string cell
    ],
)
def test_unreadable_sigma_block_is_block_invalid(block):
    split = st.split_row([1.0, *block], 1, rule(st.SIGMA), declared=True)
    assert split.status == st.BLOCK_INVALID and split.answer is None
    assert split.base == [1.0]  # the physics answer is still the first W values


def test_unreadable_interval_block_is_block_invalid():
    split = st.split_row(
        [1.0, 3.0, 1.0, 0.0, 1.0, 0.0], 1, rule(st.INTERVAL), declared=True
    )  # lo > hi
    assert split.status == st.BLOCK_INVALID


# -- T2/T3: calibration -------------------------------------------------------------------------------------------------


def test_interval_score_by_hand():
    # c = 0.5: a = 0.5, 2 / a = 4
    assert st.interval_score(1.0, 3.0, 2.0, 0.5) == 2.0
    assert st.interval_score(1.0, 3.0, 5.0, 0.5) == 2.0 + 4.0 * 2.0
    assert st.interval_score(1.0, 3.0, 0.0, 0.5) == 2.0 + 4.0 * 1.0


def test_gaussian_crps_at_the_mean():
    assert st.gaussian_crps(5.0, 2.0, 5.0) == pytest.approx(2.0 * (math.sqrt(2) - 1) / math.sqrt(math.pi))


def test_binomial_two_sided_p_by_hand():
    assert st.binomial_two_sided_p(5, 10, 0.5) == pytest.approx(1.0)
    assert st.binomial_two_sided_p(10, 10, 0.5) == pytest.approx(2.0 / 1024.0)
    assert st.binomial_two_sided_p(0, 1, 0.5) == pytest.approx(1.0)


def test_interval_calibration_by_hand():
    r = rule(st.INTERVAL)
    band = {"a": (1.0, 3.0), "b": (1.0, 3.0)}
    cases = [
        case(r, {"a": 2.0, "b": 2.0}, {"a": 2.0, "b": 2.0}, {"a": 2.0, "b": 2.0}, bands=band),  # IS 2 -> 1 U
        case(r, {"a": 2.0, "b": 2.0}, {"a": 5.0, "b": 2.0}, {"a": 2.0, "b": 2.0}, bands=band),  # a: IS 10 -> 5 U
        case(r, {"a": 2.0, "b": 2.0}, {"a": 0.0, "b": 2.0}, {"a": 2.0, "b": 2.0}, bands=band),  # a: IS 6 -> 3 U
    ]
    out = st.report(r, cases)
    assert out["status"] == st.SCORED
    a, b = out["outputs"]["a"], out["outputs"]["b"]
    assert a["covered"] == 1 and a["coverage"] == pytest.approx(1 / 3)
    assert a["coverage_gap"] == pytest.approx(1 / 3 - 0.5)
    assert a["mean_interval_score_u"] == pytest.approx(3.0)
    assert a["calibration_skill"] == pytest.approx(0.5)  # 1 - 3 / 6
    assert a["mean_crps_u"] is None
    assert b["coverage"] == 1.0 and b["mean_interval_score_u"] == pytest.approx(1.0)
    assert b["calibration_skill"] == pytest.approx(1 - 1 / 6)
    assert out["calibration_skill"] == pytest.approx(0.5 * 0.5 + 0.5 * (1 - 1 / 6))


def test_sigma_band_uses_the_registered_coverage():
    r = rule(st.SIGMA, nominal_coverage=0.8)
    z = NormalDist().inv_cdf(0.9)
    sig = {"a": 1.0, "b": 1.0}
    inside = case(r, {"a": 0.0, "b": 0.0}, {"a": 0.99 * z, "b": 0.0}, sigmas=sig)
    outside = case(r, {"a": 0.0, "b": 0.0}, {"a": 1.01 * z, "b": 0.0}, sigmas=sig)
    out = st.report(r, [inside, outside])
    a = out["outputs"]["a"]
    assert a["covered"] == 1
    expected = [2 * z, 2 * z + (2 / 0.2) * (0.01 * z)]
    assert a["mean_interval_score_u"] == pytest.approx(sum(expected) / 2)
    assert a["mean_crps_u"] is not None and a["mean_crps_u"] > 0


def test_skill_clips_at_zero_beyond_the_anchor():
    r = rule(st.INTERVAL, interval_score_anchor_u={"a": 0.5, "b": 6.0})
    band = {"a": (1.0, 3.0), "b": (1.0, 3.0)}
    out = st.report(r, [case(r, {"a": 2.0, "b": 2.0}, {"a": 2.0, "b": 2.0}, bands=band)])
    a = out["outputs"]["a"]
    assert a["calibration_skill_raw"] < 0 and a["calibration_skill"] == 0.0


# -- T4/T5: send-back ---------------------------------------------------------------------------------------------------


def _send_back_cases(r, flags):
    # a: badly wrong (3 U), b: badly wrong (3 U), c: right, d: right; bands wide enough to cover everything
    band = {"a": (-10.0, 10.0), "b": (-10.0, 10.0)}
    errors = [3.0, 3.0, 0.0, 0.0]
    return [
        case(r, {"a": 0.0, "b": 0.0}, {"a": e, "b": 0.0}, flag=f, bands=band)
        for e, f in zip(errors, flags, strict=True)
    ]


def test_send_back_by_hand():
    r = rule(st.INTERVAL)
    out = st.report(r, _send_back_cases(r, [True, False, True, False]))
    sb = out["send_back"]
    assert (sb["badly_wrong"], sb["flagged"], sb["caught"], sb["missed"], sb["false_alarms"]) == (2, 2, 1, 1, 1)
    assert sb["loss"] == pytest.approx((1.0 * 1 + 0.25 * 2) / 4)
    assert sb["loss_never_flag"] == pytest.approx(0.5)
    assert sb["loss_oracle"] == pytest.approx(0.125)
    assert out["send_back_skill"] == pytest.approx(1 / 3)
    assert out["total"] == pytest.approx(0.5 * out["calibration_skill"] + 0.5 * (1 / 3))


def test_never_flag_scores_zero_and_oracle_scores_one():
    r = rule(st.INTERVAL)
    assert st.report(r, _send_back_cases(r, [False] * 4))["send_back_skill"] == 0.0
    assert st.report(r, _send_back_cases(r, [True, True, False, False]))["send_back_skill"] == pytest.approx(1.0)


def test_flagging_everything_is_clipped_not_rewarded():
    r = rule(st.INTERVAL)
    sb = st.report(r, _send_back_cases(r, [True] * 4))["send_back"]
    # (miss * 2 - cost * 4) / ((miss - cost) * 2) = (2 - 1) / 1.5
    assert sb["send_back_skill_raw"] == pytest.approx(1 / 1.5)
    r2 = rule(st.INTERVAL, send_back_cost=0.75)
    sb2 = st.report(r2, _send_back_cases(r2, [True] * 4))["send_back"]
    assert sb2["send_back_skill_raw"] < 0 and sb2["send_back_skill"] == 0.0


def test_the_cut_is_strict():
    r = rule(st.INTERVAL)
    band = {"a": (-10.0, 10.0), "b": (-10.0, 10.0)}
    at_cut = case(r, {"a": 0.0, "b": 0.0}, {"a": 1.0, "b": 0.0}, bands=band)
    assert st.badly_wrong(r, at_cut) is False
    past = case(r, {"a": 0.0, "b": 0.0}, {"a": 1.0 + 1e-9, "b": 0.0}, bands=band)
    assert st.badly_wrong(r, past) is True


def test_no_badly_wrong_case_gives_the_send_back_part_no_evidence():
    r = rule(st.INTERVAL)
    out = st.report(r, _send_back_cases(r, [False] * 4)[2:])
    assert out["send_back_skill"] is None
    assert out["total"] is None and out["total_reason"] == "self_trust_send_back_has_no_badly_wrong_case"
    r1 = rule(st.INTERVAL, calibration_weight=1.0)
    assert st.report(r1, _send_back_cases(r1, [False] * 4)[2:])["total"] == pytest.approx(
        st.report(r1, _send_back_cases(r1, [False] * 4)[2:])["calibration_skill"]
    )


# -- T6: read status ----------------------------------------------------------------------------------------------------


def test_all_absent_is_absent_with_no_scores():
    r = rule(st.INTERVAL)
    cases = [case(r, {"a": 0.0, "b": 0.0}, {"a": 0.0, "b": 0.0}, status=st.ABSENT)] * 3
    out = st.report(r, cases)
    assert out["status"] == st.ABSENT and out["total"] is None and out["outputs"] is None


@pytest.mark.parametrize("other", [st.ABSENT, st.BLOCK_INVALID, st.WIDTH_INVALID])
def test_mixed_or_unreadable_is_invalid(other):
    r = rule(st.INTERVAL)
    band = {"a": (-1.0, 1.0), "b": (-1.0, 1.0)}
    good = case(r, {"a": 0.0, "b": 0.0}, {"a": 0.0, "b": 0.0}, bands=band)
    bad = case(r, {"a": 0.0, "b": 0.0}, {"a": 0.0, "b": 0.0}, status=other)
    out = st.report(r, [good, bad])
    assert out["status"] == st.INVALID and out["total"] is None and out["send_back"] is None


def test_reference_faults_refuse():
    r = rule(st.INTERVAL)
    band = {"a": (-1.0, 1.0), "b": (-1.0, 1.0)}
    with pytest.raises(st.SelfTrustRefused, match="u_must_be_positive"):
        st.report(r, [case(r, {"a": 0.0, "b": 0.0}, {"a": 0.0, "b": 0.0}, {"a": 0.0, "b": 1.0}, bands=band)])
    with pytest.raises(st.SelfTrustRefused, match="truth_not_a_number"):
        st.report(r, [case(r, {"a": 0.0, "b": 0.0}, {"a": math.nan, "b": 0.0}, bands=band)])
    with pytest.raises(st.SelfTrustRefused, match="read_set_empty"):
        st.report(r, [])
    with pytest.raises(st.SelfTrustRefused, match="case_status_unknown"):
        st.report(r, [case(r, {"a": 0.0, "b": 0.0}, {"a": 0.0, "b": 0.0}, status=st.NOT_ADOPTED)])


def test_report_is_deterministic():
    r = rule(st.INTERVAL)
    cases = _send_back_cases(r, [True, False, True, False])
    assert st.report(r, cases) == st.report(r, list(cases))


# -- disclosure ---------------------------------------------------------------------------------------------------------


def test_public_projection_is_the_allow_list_only():
    r = rule(st.INTERVAL)
    out = st.report(r, _send_back_cases(r, [True, False, True, False]))
    projected = st.public(out)
    assert tuple(projected) == st.PUBLIC_FIELDS
    flat = repr(projected)
    for private in ("badly_wrong", "missed", "caught", "false_alarms", "loss", "n_cases", "interval_score", "crps"):
        assert private not in flat
    assert set(projected["coverage"]) == {"a", "b"}


# -- isolation: no sealing version reads this module ---------------------------------------------------------------------


def test_nothing_in_carbon_imports_self_trust_yet():
    """Adoption is a version's explicit act: until a next version registers the rule, no carbon module imports it
    (so Motor 1.9, Cooling 1.8, BT 3.2 and RB 2.0 grade paths, contracts, encodings and digests cannot move)."""
    importers = []
    for path in sorted((ROOT / "carbon").rglob("*.py")):
        if path.name == "self_trust.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]
            if any(n.endswith("self_trust") for n in names):
                importers.append(str(path.relative_to(ROOT)))
    assert importers == []


def test_self_trust_imports_no_carbon_module():
    tree = ast.parse((ROOT / "carbon" / "scoring" / "self_trust.py").read_text(encoding="utf-8"))
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and m.startswith("carbon") for m in modules)
