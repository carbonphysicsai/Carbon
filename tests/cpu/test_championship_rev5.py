"""Synthetic accuracy-leg fixtures for the prospectively registered rev-5 rule."""

import math

import pytest

from carbon.championship_stats import (
    BATTERY_REV5_TESTNET,
    Rev5Case,
    Rev5Contender,
    Rev5Rule,
    select_rev5_winner,
)
from carbon.championship_stats.rev5 import _student_t_quantile


def _rule(n=8, k=2, margin=0.02, draw_unit="case"):
    return Rev5Rule(
        "rule", "contract", "fresh-batch", "king", n, k, margin, 0.01, draw_unit
    )


def _contender(name="a", improvements=None, *, gate=True, important=True, blocks=None):
    improvements = improvements or (0.04,) * 8
    blocks = blocks or tuple(f"case-{i}" for i in range(len(improvements)))
    return Rev5Contender(
        name,
        tuple(
            Rev5Case(f"case-{i}", blocks[i], 1.0, 1.0 - d)
            for i, d in enumerate(improvements)
        ),
        gate,
        important,
    )


def test_registered_battery_parameters_and_t_quantile():
    assert BATTERY_REV5_TESTNET == {
        "drawn_cases": 4000,
        "max_contenders": 10,
        "margin_rel": 0.0225,
        "alpha_round": 0.01,
        "draw_unit": "case",
    }
    assert _student_t_quantile(0.999, 79) == pytest.approx(3.195, rel=0.001)
    assert _student_t_quantile(0.999, 3999) == pytest.approx(3.093, rel=0.001)


def test_best_qualifying_contender_wins_without_carry_forward():
    result = select_rev5_winner(
        _rule(), (_contender("a"), _contender("b", (0.06,) * 8))
    )
    assert result.winner_id == "b"
    assert result.unique_cases == 8
    assert all(row.qualified for row in result.outcomes)
    assert (
        select_rev5_winner(_rule(), (_contender("a"), _contender("b"))).winner_id
        == "king"
    )
    assert select_rev5_winner(_rule(), ()).winner_id == "king"


def test_gate_and_posted_margin_and_strict_statistical_guard():
    assert select_rev5_winner(_rule(), (_contender(gate=False),)).winner_id == "king"
    assert (
        select_rev5_winner(_rule(), (_contender(important=False),)).winner_id == "king"
    )
    assert select_rev5_winner(_rule(margin=0.05), (_contender(),)).winner_id == "king"
    # A positive mean with a large observed paired spread does not cross t × SE.
    noisy = _contender(
        improvements=(0.12, 0.12, 0.12, 0.12, -0.04, -0.04, -0.04, -0.04)
    )
    outcome = select_rev5_winner(_rule(k=1), (noisy,)).outcomes[0]
    assert outcome.relative_improvement == pytest.approx(0.04)
    assert outcome.statistical_threshold > outcome.paired_improvement
    assert not outcome.qualified


def test_duplicates_collapse_before_mean_and_se():
    cases = _contender().cases
    duplicated = Rev5Contender("a", cases + (cases[0],), True, True)
    result = select_rev5_winner(_rule(n=9), (duplicated,))
    assert result.unique_cases == 8
    assert result.outcomes[0].block_count == 8
    changed = Rev5Contender(
        "a", cases + (Rev5Case("case-0", "case-0", 1, 0.8),), True, True
    )
    with pytest.raises(ValueError, match="conflicting values"):
        select_rev5_winner(_rule(n=9), (changed,))


def test_shared_batch_draw_unit_and_registered_k_fail_closed():
    with pytest.raises(ValueError, match="registered K"):
        select_rev5_winner(_rule(k=1), (_contender("a"), _contender("b")))
    other = Rev5Contender(
        "b",
        tuple(Rev5Case(f"other-{i}", f"other-{i}", 1, 0.9) for i in range(8)),
        True,
        True,
    )
    with pytest.raises(ValueError, match="same sealed paired batch"):
        select_rev5_winner(_rule(), (_contender("a"), other))
    with pytest.raises(ValueError, match="one block per case"):
        select_rev5_winner(_rule(), (_contender(blocks=("shared",) * 8),))


def test_stress_note_correlated_blocks_use_block_se_not_naive_case_se():
    # REV5_STRESS_NOTE: 80 natural blocks of 50 correlated cases. A naive
    # case-level guard can be much smaller than the registered block guard.
    shocks = (0.08,) * 40 + (-0.04,) * 40
    cases = tuple(
        Rev5Case(f"case-{block}-{item}", f"block-{block}", 1.0, 1.0 - shock)
        for block, shock in enumerate(shocks)
        for item in range(50)
    )
    contender = Rev5Contender("a", cases, True, True)
    result = select_rev5_winner(
        _rule(n=4000, k=10, draw_unit="registered_block"), (contender,)
    )
    row = result.outcomes[0]
    assert row.block_count == 80
    assert row.block_se > 0.005
    assert row.statistical_threshold > row.paired_improvement
    naive_se = math.sqrt(
        sum(
            (c.king_error - c.contender_error - row.paired_improvement) ** 2
            for c in cases
        )
        / (3999 * 4000)
    )
    assert row.block_se > naive_se * 6
    assert result.winner_id == "king"


def test_stress_note_independent_shocks_use_observed_se():
    # The skew and wrong-calibration scenarios need no posted SD; the current
    # round's case-level observations set the guard.
    deviations = [0.0] * 3970 + [0.1] * 22 + [0.3] * 8
    improvements = tuple(0.05 + deviation for deviation in deviations)
    contender = _contender(improvements=improvements)
    result = select_rev5_winner(_rule(n=4000, k=10), (contender,))
    assert result.outcomes[0].block_count == 4000
    assert result.outcomes[0].block_se > 0
    assert result.winner_id == "a"
