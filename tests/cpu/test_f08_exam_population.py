"""F08's sealed-exam population (OWNER-F02-F08-EXAM-DRAW-01): the N1r law's
pinned fit, band and safe/unsafe split, with the seed choosing the geometry;
every published geometry is an overlap key."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from carbon.f08 import domain, population

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/development/evidence/f08-near-limit-public-20261020"


def test_the_inputs_are_the_interfaces_and_the_registrations():
    from carbon.challenge_kit import f08_public, f08_train
    from carbon.challenge_pipeline import structures_readiness as s

    names = f08_public.interface_document(f08_train.CHALLENGE_ID, "1.2")["input"]
    assert tuple(names["names"]) == domain.INPUTS == tuple(s.FIELDS)


def test_the_pinned_fit_places_every_n1r_geometry_on_its_target():
    """N1r's 32 targets were 0.125 + 0.025 (i + 0.5) / 16 for each half; the
    pinned coefficients put every committed N1r geometry on one of them."""
    targets = [0.125 + 0.025 * (i + 0.5) / 16 for i in range(16)]
    targets += [0.15 + 0.025 * (i + 0.5) / 16 for i in range(16)]
    placed = sorted(
        population.predicted(action)
        for b in range(4)
        for action in json.loads((EVIDENCE / f"n1r-b{b}-actions.json").read_text())[
            "actions"
        ]
    )
    assert placed == pytest.approx(targets, abs=5e-5)


def test_the_fits_ladder_source_is_the_committed_ladder():
    import hashlib

    assert (
        hashlib.sha256((EVIDENCE / "ladder-observed.json").read_bytes()).hexdigest()
        == population.FIT_SOURCES_SHA256["f08-rr07-ladder/observed.json"]
    )


def test_draws_are_stratified_and_deterministic():
    cases, attempts = population.draw(random.Random(7), 8)
    assert cases == population.draw(random.Random(7), 8)[0]
    assert cases != population.draw(random.Random(8), 8)[0]
    assert attempts >= 8
    assert len({tuple(c.values()) for c in cases}) == 8
    assert [population.stratum(population.predicted(c)) for c in cases] == list(
        range(8)
    )
    for case in cases:
        assert tuple(case) == domain.INPUTS
        assert population.admitted(case)
    safe = [population.predicted(c) < domain.LIMIT_MM_PER_N for c in cases]
    assert safe == [True] * 4 + [False] * 4


def test_off_lattice_invalid_and_out_of_band_geometries_are_refused():
    case = population.draw(random.Random(3), 1)[0][0]
    assert population.admitted(case)
    assert not population.admitted({**case, "length_mm": case["length_mm"] + 1.0})
    assert not population.admitted({k: v for k, v in case.items() if k != "width_mm"})
    # Outside the registered range (thickness 4-8 mm).
    assert not population.admitted({**case, "thickness_mm": 8.5})
    far = {
        "length_mm": 180.0,
        "width_mm": 100.0,
        "thickness_mm": 8.0,
        "rib_height_mm": 16.0,
        "rib_thickness_mm": 5.0,
        "relief_length_mm": 20.0,
    }
    assert population.predicted(far) < population.BAND[0]
    assert not population.admitted(far)


def test_every_published_f08_geometry_is_an_overlap_key():
    import numpy as np

    from carbon.challenge_kit import f08_train
    from carbon.challenge_validator.confirmation_sources import source_for

    source = source_for(f08_train.CHALLENGE_ID)
    published = source.published(ROOT)
    assert source.laws == frozenset({population.POPULATION_VERSION})
    train = np.asarray(f08_train.load_public_train("1.2")["inputs"]).tolist()
    assert len(train) == 287
    assert all(source.key(dict(zip(domain.INPUTS, r))) in published for r in train)
    for b in range(4):
        for action in json.loads((EVIDENCE / f"n1r-b{b}-actions.json").read_text())[
            "actions"
        ]:
            assert source.key(action) in published
    for action in json.loads((EVIDENCE / "ladder-actions.json").read_text())["actions"]:
        assert source.key(action) in published


def test_draws_never_repeat_a_published_geometry():
    """The producer refuses a batch that repeats a published case and never
    redraws a role; 50 published geometries lie in the band."""
    from carbon.challenge_kit import f08_train
    from carbon.challenge_validator.confirmation_sources import source_for

    source = source_for(f08_train.CHALLENGE_ID)
    published = source.published(ROOT)
    for seed in range(300):
        cases, _ = population.draw(random.Random(seed), 8)
        assert not {source.key(c) for c in cases} & published


def test_a_missing_evidence_root_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(population, "_PUBLISHED", {})
    monkeypatch.setattr(population, "REPOSITORY", tmp_path)
    with pytest.raises(RuntimeError, match="f08_published_evidence_missing"):
        population.draw(random.Random(1), 8)
    assert population._PUBLISHED == {}


def test_an_empty_published_set_fails_closed_and_is_not_cached(monkeypatch):
    from carbon.challenge_validator import confirmation_sources

    monkeypatch.setattr(population, "_PUBLISHED", {})
    real = confirmation_sources.PopulationSource.published
    monkeypatch.setattr(
        confirmation_sources.PopulationSource, "published", lambda self, repo: set()
    )
    with pytest.raises(RuntimeError, match="f08_published_set_empty"):
        population.draw(random.Random(1), 8)
    assert population._PUBLISHED == {}
    monkeypatch.setattr(confirmation_sources.PopulationSource, "published", real)
    assert len(population.draw(random.Random(1), 8)[0]) == 8
