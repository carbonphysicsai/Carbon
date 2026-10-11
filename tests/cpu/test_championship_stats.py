"""Toy-only championship statistics and MARGIN-SIZING-04 planning parity."""

import json
import math
from pathlib import Path

import pytest

from carbon.championship_stats import (
    AlphaLedger,
    BoundedMixture,
    Contender,
    Evidence,
    PairedCase,
    PairedRound,
    confirm_noninferiority,
    holm,
    select_winner,
)
from carbon.championship_stats.planning import (
    detectable_improvement,
    m04_rounds_to_win,
)


def _mixture() -> BoundedMixture:
    return BoundedMixture(-1, 1, 0, (0.5, 1), (0.5, 0.5))


def _round(artifact="a", incumbent="i", round_id="r1", *, gate=True, offset=0):
    return PairedRound(
        artifact,
        incumbent,
        round_id,
        tuple(PairedCase(f"c{offset + j}", 0.5, 0.1) for j in range(20)),
        gate,
    )


def test_accuracy_is_paired_and_g_feas_is_hard_gate():
    evidence = Evidence("a", "i", _mixture(), 20).update(_round(gate=False))
    assert evidence.count == 20
    assert evidence.mean_improvement == pytest.approx(0.4)
    assert evidence.g_feas_passed is False
    ledger = AlphaLedger("day", 0.05).invest("a", "i", 0.05)
    assert select_winner((Contender(evidence, True),), ledger) is None


def test_only_confirmed_positive_evidence_wins():
    cases = tuple(PairedCase(f"winner-{j}", 0.5, 0.1) for j in range(100))
    evidence = Evidence("a", "i", _mixture(), 100).update(
        PairedRound("a", "i", "r", cases, True)
    )
    ledger = AlphaLedger("day", 0.05).invest("a", "i", 0.05)
    assert evidence.anytime_p_value < 0.05
    assert select_winner((Contender(evidence, True),), ledger) == "a"
    assert select_winner((Contender(evidence, False),), ledger) is None


def test_carry_forward_requires_new_cases_and_same_artifacts():
    first = Evidence("a", "i", _mixture(), 20).update(_round())
    second = first.update(_round(round_id="r2", offset=20))
    assert second.count == 40 and second.max_e_value >= first.max_e_value
    with pytest.raises(ValueError, match="round already"):
        first.update(_round())
    with pytest.raises(ValueError, match="case already"):
        first.update(_round(round_id="r2"))
    with pytest.raises(ValueError, match="artifact or incumbent changed"):
        first.update(_round(incumbent="other", round_id="r2", offset=20))
    with pytest.raises(ValueError, match="artifact or incumbent changed"):
        first.update(_round(artifact="other", round_id="r2", offset=20))
    fresh = Evidence("a", "other", _mixture(), 20)
    assert fresh.count == 0 and fresh.max_e_value == 1


def test_holm_is_full_family_and_ties_keep_incumbent():
    assert holm({"a": 0.01, "b": 0.02, "c": 0.9}, 0.05) == {"a", "b"}
    assert holm({"a": 0.025, "b": 0.04}, 0.05) == frozenset()
    a = Evidence("a", "i", _mixture(), 20).update(_round())
    b = Evidence("b", "i", _mixture(), 20).update(_round("b"))
    ledger = AlphaLedger("day", 0.05).invest("a", "i", 0.025)
    ledger = ledger.invest("b", "i", 0.025)
    assert select_winner((Contender(a, True), Contender(b, True)), ledger) is None
    assert select_winner((Contender(a, False),), ledger) is None
    with pytest.raises(ValueError, match="no daily alpha allocation"):
        select_winner((Contender(Evidence("c", "i", _mixture(), 20), False),), ledger)


def test_contenders_must_share_the_fresh_championship_batch():
    a = Evidence("a", "i", _mixture(), 20).update(_round())
    b = Evidence("b", "i", _mixture(), 20).update(_round("b", offset=20))
    ledger = AlphaLedger("day", 0.05).invest("a", "i", 0.025)
    ledger = ledger.invest("b", "i", 0.025)
    with pytest.raises(ValueError, match="same fresh championship batch"):
        select_winner((Contender(a, True), Contender(b, True)), ledger)


def test_alpha_is_spent_once_per_artifact_and_globally_capped():
    ledger = AlphaLedger("day", 0.05).invest("digest-a", "i", 0.03)
    with pytest.raises(ValueError, match="already allocated"):
        ledger.invest("digest-a", "i", 0.01)
    with pytest.raises(ValueError, match="exhausted"):
        ledger.invest("digest-b", "i", 0.03)
    assert ledger.invest("digest-b", "i", 0.02).remaining == pytest.approx(0)


def test_confirmation_needs_fresh_bounded_evidence_and_strict_margin():
    evidence = Evidence("a", "i", _mixture(), 20).update(_round())
    positive = PairedRound(
        "a",
        "i",
        "confirm",
        tuple(PairedCase(f"fresh-{j}", 0.6, 0.1) for j in range(100)),
        True,
    )
    negative = PairedRound(
        "a",
        "i",
        "confirm",
        tuple(PairedCase(f"fresh-{j}", 0.1, 0.6) for j in range(100)),
        True,
    )
    assert confirm_noninferiority(
        evidence,
        positive,
        confirmation_cases=100,
        delta_c=0.1,
        lower=-1,
        upper=1,
        alpha=0.05,
    )
    assert not confirm_noninferiority(
        evidence,
        negative,
        confirmation_cases=100,
        delta_c=0.1,
        lower=-1,
        upper=1,
        alpha=0.05,
    )
    assert not confirm_noninferiority(
        evidence,
        PairedRound("a", "i", "confirm", positive.cases, False),
        confirmation_cases=100,
        delta_c=0.1,
        lower=-1,
        upper=1,
        alpha=0.05,
    )
    with pytest.raises(ValueError, match="fresh cases"):
        confirm_noninferiority(
            evidence,
            _round(),
            confirmation_cases=20,
            delta_c=0.1,
            lower=-1,
            upper=1,
            alpha=0.05,
        )
    with pytest.raises(ValueError, match="exceeds registered bounds"):
        confirm_noninferiority(
            evidence,
            PairedRound("a", "i", "confirm", (PairedCase("fresh", 2.0, 0),), True),
            confirmation_cases=1,
            delta_c=0.1,
            lower=-1,
            upper=1,
            alpha=0.05,
        )


def test_invalid_predictions_and_bounds_refused():
    with pytest.raises(ValueError, match="registered positive N"):
        Evidence("a", "i", _mixture(), 0)
    with pytest.raises(ValueError, match="registered N"):
        Evidence("a", "i", _mixture(), 21).update(_round())
    with pytest.raises(ValueError, match="finite"):
        PairedCase("c", math.nan, 0.1)
    with pytest.raises(ValueError, match="duplicate case"):
        PairedRound("a", "i", "r", (PairedCase("c", 0.1, 0.2),) * 2, True)
    with pytest.raises(ValueError, match="exceeds registered bounds"):
        Evidence("a", "i", _mixture(), 1).update(
            PairedRound("a", "i", "r", (PairedCase("c", 5, 0),), True)
        )


@pytest.mark.parametrize(
    ("cases", "contenders", "sd", "expected"),
    [
        (2000, 1, 0.28, 0.015567795074935145),
        (2000, 5, 0.46, 0.032585453666121034),
        (3000, 20, 0.70, 0.04663051514575631),
    ],
)
def test_m04_detectable_improvement_same_inputs(cases, contenders, sd, expected):
    assert detectable_improvement(
        sd=sd, cases=cases, contenders=contenders, alpha=0.05, power=0.8
    ) == pytest.approx(expected, abs=1e-12)


def test_m04_carry_forward_and_false_takeover_same_inputs():
    probabilities = m04_rounds_to_win(
        improvement=0.02,
        sd=0.46,
        cases_per_round=3000,
        alpha_art=0.05,
        max_rounds=14,
        repetitions=3000,
        seed=3,
    )
    assert probabilities[0] == 0.104
    assert probabilities[2] == 0.849
    assert next(i + 1 for i, p in enumerate(probabilities) if p >= 0.8) == 3
    false_rate = m04_rounds_to_win(
        improvement=0,
        sd=0.46,
        cases_per_round=2000,
        alpha_art=0.05,
        max_rounds=14,
        repetitions=6000,
        seed=3,
    )[-1]
    assert false_rate == 0.006


def test_m04_all_championship_detectable_figures_from_reference_fixture():
    """The copied aggregate output is generated by the supplied m04.py."""
    path = Path(__file__).parent.parent / "fixtures" / "margin_sizing_04.json"
    reference = json.loads(path.read_text(encoding="utf-8"))
    noise = {"close": 0.28, "median": 0.46, "wide": 0.70}
    assert len(reference["championship"]) == 6
    for row in reference["championship"]:
        for name, sd in noise.items():
            actual = detectable_improvement(
                sd=sd,
                cases=row["N"],
                contenders=row["contenders"],
                alpha=0.05,
                power=0.8,
            )
            assert actual == pytest.approx(row["holm"][name], abs=1e-12)
    assert reference["carry_forward_false_rate_14_rounds"] == 0.006
