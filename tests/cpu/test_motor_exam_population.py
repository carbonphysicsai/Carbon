"""Motor's placed sealed-exam population (OWNER-MOTOR-EXAM-DRAW-01): 30 cases
from the registered uniform law, placed by a TRAIN-fitted predictor so about a
third lands on each side of both limits; placement only, never a label."""

from __future__ import annotations

import random

import pytest

from carbon.challenge_validator import motor_sealed as sealed
from carbon.challenge_validator.confirmation_sources import PopulationSource
from carbon.challenge_validator.motor_sealed_source import motor_sealed_family
from carbon.motor_exam import population


@pytest.fixture(scope="module")
def drawn():
    return population.draw(random.Random(7), 30)


def test_a_batch_is_thirty_admitted_cases_placed_in_the_window(drawn):
    cases, tries = drawn
    assert tries >= 1 and len(cases) == 30
    assert all(population.admitted(c) for c in cases)
    torque, ripple = population.predict(cases)
    low, high = population.WINDOW
    assert low <= int((torque >= 4.0).sum()) <= high
    assert low <= int((ripple <= 0.30).sum()) <= high


def test_draws_are_deterministic_and_never_published(drawn):
    cases, _ = drawn
    assert population.draw(random.Random(7), 30)[0] == cases
    source = PopulationSource("electric-motor-magnetics", "motor", ("motor-*",))
    published = source.published(population.REPOSITORY)
    assert not {source.key(c) for c in cases} & published


def test_only_a_thirty_case_batch_is_drawn():
    with pytest.raises(ValueError):
        population.draw(random.Random(7), 29)


def test_the_placement_fit_refuses_a_changed_train(tmp_path, monkeypatch):
    monkeypatch.setattr(population, "_CACHE", {})
    monkeypatch.setattr(population, "TRAIN", (population.TRAIN[0], "0" * 64))
    with pytest.raises(RuntimeError, match="motor_placement_train_differs"):
        population.predict([{}])


def test_the_family_draws_the_placed_population_under_the_owner_record():
    family = motor_sealed_family()
    assert family.population_version == population.POPULATION_VERSION
    source = family.population()
    assert source.laws == frozenset({population.POPULATION_VERSION})
    rule = sealed.hidden_rule()
    assert rule["population"]["version"] == population.POPULATION_VERSION
    assert rule["population"]["law"] == "placed"
    assert rule["population"]["authority"] == "OWNER-MOTOR-EXAM-DRAW-01"
    cases = source.draw(random.Random(3), 30, population.POPULATION_VERSION)
    assert len(cases) == 30
