"""Cooling's sealed-exam population: a placed 4 x 4 design x condition grid,
every cell valid, about a third predicted on each side of both limits."""

from __future__ import annotations

import random

import pytest

from carbon.cold_plate import analytic
from carbon.cold_plate.exam import feasibility
from carbon.cold_plate_exam import domain, population


@pytest.fixture(scope="module")
def drawn():
    return population.draw(random.Random(2), 16)


def test_a_batch_is_one_placed_full_grid(drawn):
    cases, tries = drawn
    assert tries >= 1 and len(cases) == 16
    designs, conditions = population.grid_of(cases)
    assert len(designs) == len(conditions) == 4
    assert all(population.admitted(c) for c in cases)
    predicted = [
        feasibility(
            c,
            analytic.predict(c),
            die_limit_c=domain.DIE_LIMIT_C,
            hydraulic_limit_w=domain.HYDRAULIC_LIMIT_W,
        )
        for c in cases
    ]
    die = sum(p["die_peak_c"] <= domain.DIE_LIMIT_C for p in predicted)
    hydraulic = sum(p["hydraulic_w"] <= domain.HYDRAULIC_LIMIT_W for p in predicted)
    assert population.WINDOW[0] <= die <= population.WINDOW[1]
    assert population.WINDOW[0] <= hydraulic <= population.WINDOW[1]


def test_draws_are_deterministic_and_never_published(drawn):
    from carbon.challenge_validator.confirmation_sources import PopulationSource

    cases, _ = drawn
    assert population.draw(random.Random(2), 16)[0] == cases
    source = PopulationSource(
        "chip-cold-plate", "cold_plate_exam", ("cold-plate-*", "cooling-*")
    )
    published = source.published(population.REPOSITORY)
    assert not {source.key(c) for c in cases} & published


def test_only_a_full_grid_of_sixteen_is_drawn_or_accepted(drawn):
    cases, _ = drawn
    with pytest.raises(ValueError):
        population.draw(random.Random(2), 8)
    with pytest.raises(ValueError):
        population.grid_of(cases[:15])
    broken = [dict(c) for c in cases]
    broken[0]["channel_width_mm"] += 1e-3  # a fifth design
    with pytest.raises(ValueError):
        population.grid_of(broken)


def test_a_missing_evidence_root_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(population, "_PUBLISHED", {})
    monkeypatch.setattr(population, "REPOSITORY", tmp_path)
    with pytest.raises(RuntimeError, match="cooling_published_evidence_missing"):
        population.draw(random.Random(1), 16)
    assert population._PUBLISHED == {}
