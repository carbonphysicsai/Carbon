"""The part-feedback leak-attack payload: the observer shows what the v4 document shows (through the real grade_feedback
functions), the attackers accept only what they are shown, the aggregates hold no model or case, and the pass rule is
mean gap <= margin + 2 SE. Fake data only; no Challenge grader runs here."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

PAYLOAD = Path(__file__).resolve().parents[2] / "scripts/dev/part_feedback_attack"
sys.path.insert(0, str(PAYLOAD))

import attack as at

from carbon.scoring import grade_feedback as gf


def _graded(total, a, d, components=None, gates=None, status="SCORED"):
    return {
        "status": status,
        "total": total,
        "legs": {"A": a, "D": d},
        "components": components or {"c1": 0.5},
        "gates": gates or {"g": True},
    }


def test_the_selftest_sees_a_leak_in_fine_feedback_and_none_in_coarse_or_banded():
    result = at.selftest()
    assert result["ok"], result
    assert set(result["selftest"]) == {
        "fine_feedback_leaks",
        "coarse_feedback_does_not_leak_the_fake",
        "bands_do_not_leak_the_fake",
        "deterministic",
        "no_theta_in_output",
        "a_finer_part_step_than_registered_is_refused",
    }


def test_the_observer_uses_the_ladder_rule_for_the_total_and_the_part_hysteresis():
    observer = at.Observer(total_step=0.02, part_step=0.05, bands=False)
    first = observer.show(_graded(0.50, 0.52, 0.48))
    assert first["improved"] and first["total"] == 0.5 and first["parts"]["A"] == 0.5
    # a total that has not moved a full step is NO_IMPROVEMENT: the shown best does not move
    flat = observer.show(_graded(0.51, 0.53, 0.49))
    assert not flat["improved"] and flat["total"] == 0.5
    # a part keeps its last shown value until the true value moves a full part step (the hysteresis)
    assert flat["parts"]["A"] == first["parts"]["A"]
    moved = observer.show(_graded(0.60, 0.58, 0.62))
    assert moved["improved"] and moved["total"] == 0.6
    assert moved["parts"]["A"] == gf.shown_part(0.58, 0.5, 0.05)


def test_a_failed_gate_or_an_unscored_result_shows_no_numbers():
    observer = at.Observer(0.02, 0.05, False)
    assert observer.show(_graded(0.7, 0.7, 0.7, gates={"g": False})) == {
        "gate_failed": True,
        "scored": False,
    }
    assert observer.show(_graded(0.7, 0.7, 0.7, status="NOT_SCORED")) == {
        "gate_failed": False,
        "scored": False,
    }
    assert (
        observer.best_total is None and observer.parts == {}
    )  # nothing was learned or stored


def test_a_band_observer_shows_three_words_not_numbers():
    assert [at.band_of(x) for x in (0.0, 0.33, 0.34, 0.66, 0.67, 1.0)] == [
        0,
        0,
        1,
        1,
        2,
        2,
    ]
    observer = at.Observer(0.02, 0.05, True)
    shown = observer.show(_graded(0.5, 0.2, 0.9))
    assert (shown["parts"]["A"], shown["parts"]["D"]) == (0, 2)


def test_each_attacker_accepts_only_what_its_own_feedback_says_improved():
    before = {
        "scored": True,
        "improved": False,
        "parts": {"A": 0.5, "D": 0.5, "c1": 0.5},
    }
    rose_a = {
        "scored": True,
        "improved": False,
        "parts": {"A": 0.55, "D": 0.5, "c1": 0.5},
    }
    mixed = {
        "scored": True,
        "improved": False,
        "parts": {"A": 0.55, "D": 0.45, "c1": 0.5},
    }
    better_total = {
        "scored": True,
        "improved": True,
        "parts": {"A": 0.5, "D": 0.45, "c1": 0.5},
    }
    assert not at._accept(
        "total", before, rose_a
    )  # only the Ladder total counts for the total attacker
    assert at._accept("total", before, better_total)
    assert at._accept("A", before, rose_a) and not at._accept("D", before, rose_a)
    assert at._accept("joint", before, rose_a)  # a part rose, none fell
    assert not at._accept("joint", before, mixed)  # a part fell
    assert at._accept("joint", before, better_total)  # the total improved
    assert not at._accept("A", before, {"scored": False, "gate_failed": True})


def test_the_result_is_aggregates_only_and_the_pass_rule_is_the_stated_one():
    binding = at.FakeBinding(ripple=0.08)
    result = at.attack(
        binding, rounds=40, seeds=3, margin=0.01, margin_source="registered"
    )
    assert result["schema"] == at.SCHEMA and result["run_digest"].startswith("sha256:")
    names = {r["attacker"] for r in result["attackers"]}
    assert names == {"total", "A", "D", "a_one", "a_two", "d_one", "joint"}
    for row in result["attackers"]:
        assert set(row) == {
            "attacker",
            "runs",
            "mean_accepted_perturbations",
            "mean_sealed_gain",
            "mean_fresh_gain",
            "mean_gap",
            "se_gap",
            "bound",
            "unscored",
            "outcome",
            "reason",
            "pass",
        }
        assert row["bound"] == pytest.approx(0.01 + 2.0 * row["se_gap"])
        assert row["outcome"] in at.OUTCOMES and row["pass"] == (
            row["outcome"] == "PASS"
        )
        assert set(row["unscored"]) == set(at.UNSCORED_CASES)
    assert result["all_pass"] == all(
        r["outcome"] == "PASS" for r in result["attackers"]
    )
    assert result["config"]["margin_source"] == "registered"
    blob = json.dumps(result)
    for forbidden in ("theta", "case", "seed_of", "pool"):
        assert forbidden not in blob
    assert result["config"]["part_step"] == gf.part_step(None)


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"margin": None}, "margin_required"),
        ({"margin_source": None}, "margin_source_required"),
        ({"margin_source": "guess"}, "margin_source_required"),
        ({"margin": -1}, "margin_required"),
        ({"seeds": 1}, "rounds_and_two_or_more_seeds_required"),
        ({"rounds": 0}, "rounds_and_two_or_more_seeds_required"),
        ({"part_step": 0.01}, "part_step_finer_than_registered"),
    ],
)
def test_the_attack_refuses_a_missing_margin_too_few_seeds_and_a_finer_step(
    kwargs, code
):
    args = {
        "rounds": 10,
        "seeds": 2,
        "margin": 0.01,
        "margin_source": "registered",
        **kwargs,
    }
    with pytest.raises(at.AttackRefused) as refused:
        at.attack(at.FakeBinding(), **args)
    assert refused.value.code == code


def test_a_coarser_part_step_is_accepted_and_recorded():
    result = at.attack(
        at.FakeBinding(),
        rounds=10,
        seeds=2,
        margin=0.01,
        margin_source="provisional_sheet",
        part_step=0.10,
    )
    assert result["config"]["part_step"] == 0.10


def test_a_model_that_does_not_score_unperturbed_is_refused():
    class Broken(at.FakeBinding):
        def grade(self, theta, which):
            return {"status": "NOT_SCORED"}

    with pytest.raises(at.AttackRefused) as refused:
        at.attack(Broken(), rounds=5, seeds=2, margin=0.01, margin_source="registered")
    assert refused.value.code == "unperturbed_model_not_scored_sealed"


def test_the_binding_must_be_module_colon_function():
    with pytest.raises(at.AttackRefused) as refused:
        at._load("no_colon")
    assert refused.value.code == "binding_is_module_colon_function"


def test_the_payload_files_match_their_published_sums():
    listed = {}
    for line in (PAYLOAD / "SHA256SUMS").read_text().splitlines():
        digest, _, name = line.partition("  ")
        listed[name] = digest
    assert set(listed) == set(at.PAYLOAD_FILES)
    for name, digest in listed.items():
        data = (PAYLOAD / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == digest, name
    assert at.sums() == listed


# --- Validator fix 1: a model that breaks on FRESH data while the sealed exam still scores it is never hidden --------


def _zero_counts():
    return dict.fromkeys(at.UNSCORED_CASES, 0)


START = {"sealed": {"total": 0.40}, "fresh": {"total": 0.40}}
SCORED_SEALED = {"status": "SCORED", "total": 0.55}
SCORED_FRESH = {"status": "SCORED", "total": 0.43}
BROKEN = {"status": "GATE_FAILED"}


def test_each_unscored_case_is_counted_and_only_the_fresh_break_keeps_the_sealed_gain():
    counts = _zero_counts()
    assert at._gains(SCORED_SEALED, SCORED_FRESH, START, counts) == pytest.approx(
        (0.15, 0.03)
    )
    assert counts == _zero_counts()
    # sealed scores, fresh does not: the sealed gain stays visible (the strongest overfit signal)
    assert at._gains(SCORED_SEALED, BROKEN, START, counts) == pytest.approx((0.15, 0.0))
    # sealed does not score, fresh does: no sealed gain was made
    assert at._gains(BROKEN, SCORED_FRESH, START, counts) == (0.0, 0.0)
    # neither scores: gap 0, counted
    assert at._gains(BROKEN, BROKEN, START, counts) == (0.0, 0.0)
    assert counts == {
        "fresh_unscored_while_sealed_scores": 1,
        "sealed_unscored_while_fresh_scores": 1,
        "both_unscored": 1,
    }


def test_an_attacker_whose_model_breaks_only_on_fresh_data_fails_with_its_reason():
    zero = _zero_counts()
    assert at._judge(0.0, 0.001, 0.01, zero) == ("PASS", None)
    broke = {**zero, "fresh_unscored_while_sealed_scores": 1}
    assert at._judge(0.0, 0.001, 0.01, broke) == (
        "FAIL",
        "fresh_unscored_while_sealed_scores",
    )
    # the other two cases do not fail by themselves
    assert at._judge(0.0, 0.001, 0.01, {**zero, "both_unscored": 3})[0] == "PASS"
    assert (
        at._judge(0.0, 0.001, 0.01, {**zero, "sealed_unscored_while_fresh_scores": 2})[
            0
        ]
        == "PASS"
    )


class FreshBreaks(at.FakeBinding):
    """Any perturbed model stops scoring on the fresh draw while the sealed exam still scores it."""

    def grade(self, theta, which):
        if which == "fresh" and any(abs(t) > 1e-12 for t in theta):
            return {"status": "NOT_SCORED"}
        return super().grade(theta, which)


def test_end_to_end_a_fresh_only_break_fails_the_run_and_reports_the_count():
    result = at.attack(
        FreshBreaks(),
        rounds=60,
        seeds=3,
        margin=0.01,
        margin_source="registered",
        sigma0=0.2,
    )
    assert not result["all_pass"]
    failed = [
        r
        for r in result["attackers"]
        if r["reason"] == "fresh_unscored_while_sealed_scores"
    ]
    assert failed and all(r["outcome"] == "FAIL" and not r["pass"] for r in failed)
    assert all(r["unscored"]["fresh_unscored_while_sealed_scores"] > 0 for r in failed)


# --- Validator fix 2: a noise-wide SE is INCONCLUSIVE, never a pass ------------------------------------------------


def test_a_run_that_cannot_resolve_the_margin_is_inconclusive_not_a_pass():
    zero = _zero_counts()
    # mean gap 0 is under M + 2 SE, but 2 SE = 0.02 > M = 0.01: the SE could hide any leak
    assert at._judge(0.0, 0.01, 0.01, zero) == ("INCONCLUSIVE", "add_seeds")
    # exactly resolved (2 SE == M) passes
    assert at._judge(0.0, 0.005, 0.01, zero) == ("PASS", None)
    # a gap above the bound is a FAIL even when the SE is wide
    assert at._judge(0.5, 0.01, 0.01, zero) == ("FAIL", "gap_above_margin_plus_2_se")
    # an undefined SE can never pass
    assert at._judge(0.0, float("nan"), 0.01, zero) == ("INCONCLUSIVE", "add_seeds")


class NoisyGap(at.FakeBinding):
    """The fresh grade is a pseudo-random function of theta: attackers' gaps scatter far wider than the margin."""

    def grade(self, theta, which):
        out = super().grade(theta, which)
        if which == "fresh":
            wobble = 0.2 * math.sin(1.0e3 * sum(theta))
            out["total"] = out["total"] + wobble
        return out


def test_end_to_end_two_noisy_seeds_cannot_pass_and_all_pass_needs_every_attacker_to_pass():
    result = at.attack(
        NoisyGap(),
        rounds=60,
        seeds=2,
        margin=0.001,
        margin_source="provisional_sheet",
        sigma0=0.2,
    )
    assert any(r["outcome"] == "INCONCLUSIVE" for r in result["attackers"])
    assert not result["all_pass"]
    for row in result["attackers"]:
        if row["outcome"] == "INCONCLUSIVE":
            assert (
                row["reason"] == "add_seeds"
                and not row["pass"]
                and 2 * row["se_gap"] > 0.001
            )


def test_the_output_says_which_margin_was_used():
    for source in at.MARGIN_SOURCES:
        result = at.attack(
            at.FakeBinding(), rounds=10, seeds=2, margin=0.01, margin_source=source
        )
        assert result["config"]["margin_source"] == source
    assert at.MARGIN_SOURCES == ("registered", "provisional_sheet")
