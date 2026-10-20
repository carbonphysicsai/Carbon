"""F02's sealed-exam population (OWNER-F02-F08-EXAM-DRAW-01): the approved S1
law with fresh seeds, never an exam action, never a published schedule."""

from __future__ import annotations

import json
import random
from pathlib import Path

from carbon.f02 import population

ROOT = Path(__file__).resolve().parents[2]


def test_draws_are_the_s1_lattice_and_deterministic():
    cases, attempts = population.draw(random.Random(7), 8)
    assert cases == population.draw(random.Random(7), 8)[0]
    assert len(cases) == 8 and attempts >= 8
    assert len({(c["peak_w"], c["on_time_s"]) for c in cases}) == 8
    for case in cases:
        assert set(case) == {"peak_w", "on_time_s"}
        assert case["peak_w"] == int(case["peak_w"]) and 70 <= case["peak_w"] <= 100
        assert 4.0 <= case["on_time_s"] <= 6.0
        assert round(case["on_time_s"] * 10) == case["on_time_s"] * 10
        assert population.admitted(case)


def test_the_law_matches_train40_v2_s1_resolution():
    """Every TRAIN40-v2 S1 row is in the law's lattice (same law, other seed)."""
    rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/development/evidence/f02-cold-pack-20261020/train40v2.jsonl"
        )
        .read_text()
        .splitlines()
    ]
    s1 = [r for r in rows if r["case_id"].endswith("v2s1")]
    assert len(s1) == 24
    for row in s1:
        case = {k: row["inputs"][k] for k in ("peak_w", "on_time_s")}
        assert population.admitted(case)


def test_exam_actions_and_off_lattice_points_are_refused():
    for peak, on_time in population.EXAM_ACTIONS:
        if 70 <= peak <= 100 and 4.0 <= on_time <= 6.0:
            assert not population.admitted({"peak_w": peak, "on_time_s": on_time})
    assert not population.admitted({"peak_w": 85.5, "on_time_s": 5.1})
    assert not population.admitted({"peak_w": 69.0, "on_time_s": 5.0})
    assert not population.admitted({"peak_w": 80.0, "on_time_s": 6.1})
    assert not population.admitted({"peak_w": 80.0, "on_time_s": 5.05})


def test_every_published_f02_schedule_is_an_overlap_key():
    from carbon.challenge_validator.confirmation_sources import source_for

    source = source_for("f02")
    published = source.published(ROOT)
    assert source.laws == frozenset({population.POPULATION_VERSION})
    rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/development/evidence/f02-cold-pack-20261020/train40v2.jsonl"
        )
        .read_text()
        .splitlines()
    ]
    assert all(source.key(r["inputs"]) in published for r in rows)
