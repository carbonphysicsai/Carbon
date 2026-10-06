"""The same-miner self-improvement factor study (VALIDATOR-14 §7).

Synthetic evaluators only: the study's arithmetic and neighbour enumeration,
not any Challenge's real errors.
"""

import pytest

from carbon.rewards import self_improvement_study as sis

STRATEGY = {"backbone": "knn", "parameters": {"neighbours": 5, "ridge": 1e-3}}
SURFACES = {"neighbours": ("uint", 1, 64), "ridge": ("float", 1e-6, 1.0, 10.0)}


def test_every_one_step_change_of_one_parameter_is_enumerated():
    found = sis.one_step_neighbours(STRATEGY, SURFACES)
    assert [c for c, _ in found] == [
        "neighbours=4",
        "neighbours=6",
        "ridge=0.0001",
        "ridge=0.01",
    ]
    for _, variant in found:
        changed = [
            k
            for k in STRATEGY["parameters"]
            if variant["parameters"][k] != STRATEGY["parameters"][k]
        ]
        assert len(changed) == 1
    assert STRATEGY["parameters"] == {"neighbours": 5, "ridge": 1e-3}


def test_ranges_and_choices_are_respected():
    edge = {"parameters": {"neighbours": 1, "kernel": "rbf"}}
    surfaces = {"neighbours": ("uint", 1, 64), "kernel": ("choice", ["rbf", "lap"])}
    assert [c for c, _ in sis.one_step_neighbours(edge, surfaces)] == [
        "kernel='lap'",
        "neighbours=2",
    ]
    with pytest.raises(ValueError):
        sis.one_step_neighbours(edge, {"kernel": ("mystery",)})


def test_the_proposed_factor_sits_above_the_largest_one_step_gain():
    errors = {
        5: {"a": 1.0, "b": 1.0},
        4: {"a": 0.9, "b": 0.9},  # a 10% apparent gain from one step
        6: {"a": 1.1, "b": 1.1},
    }

    def evaluate(strategy):
        return errors[strategy["parameters"]["neighbours"]]

    neighbours = sis.one_step_neighbours(
        {"parameters": {"neighbours": 5}}, {"neighbours": ("uint", 1, 64)}
    )
    result = sis.study(
        {"parameters": {"neighbours": 5}}, neighbours, evaluate, margin=0.01
    )
    assert result["status"] == "PROPOSED_NOT_ADOPTED"
    assert result["max_apparent_improvement"] == pytest.approx(0.1)
    assert result["proposed_factor"] == pytest.approx(0.11)


def test_no_gain_anywhere_proposes_only_the_margin():
    def evaluate(strategy):
        return {"a": 1.0 + abs(strategy["parameters"]["neighbours"] - 5)}

    neighbours = sis.one_step_neighbours(
        {"parameters": {"neighbours": 5}}, {"neighbours": ("uint", 1, 64)}
    )
    result = sis.study({"parameters": {"neighbours": 5}}, neighbours, evaluate)
    assert result["proposed_factor"] == 0.0
