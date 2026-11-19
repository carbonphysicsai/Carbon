"""exam-cooling 19 Nov (Cooling 1.8 encoding v2): a version graded WITH a region may register its own region bound
(`pool_version.register_region_bound`), used in place of `cooling_region.bounded_binding`; add-only; every unregistered
version and every grade without a region keep exactly the binding they had. Every region, case and row is SYNTHETIC.
"""

from __future__ import annotations

import random

import pytest
from test_cooling_region import REGION, TRAIN, _cases, _row

from carbon.scoring import cooling_region, pool_exam, pool_version


@pytest.fixture
def clean_bounds():
    saved = dict(pool_version._REGION_BOUNDS)
    pool_version._REGION_BOUNDS.clear()
    yield
    pool_version._REGION_BOUNDS.clear()
    pool_version._REGION_BOUNDS.update(saved)


def _recording(calls):
    def bound(binding, region):
        calls.append((binding.version, region))
        return cooling_region.bounded_binding(binding, region)

    return bound


def test_an_unregistered_version_with_a_region_keeps_cooling_region_bounded_binding(
    clean_bounds, monkeypatch
):
    calls = []
    real = cooling_region.bounded_binding

    def spy(binding, region):
        calls.append(binding.version)
        return real(binding, region)

    monkeypatch.setattr(cooling_region, "bounded_binding", spy)
    pool_version.register_region_bound("cooling", "1.8", _recording([]))
    pool_version.official_binding("cooling", "1.7", region=REGION)
    assert calls == ["1.7"]


def test_a_registered_bound_is_used_with_a_region_and_grades_a_row(clean_bounds):
    default = pool_version.official_binding("cooling", "1.8", region=REGION)
    calls = []
    pool_version.register_region_bound("cooling", "1.8", _recording(calls))
    mine = pool_version.official_binding("cooling", "1.8", region=REGION)
    assert calls == [("1.8", REGION)]
    for case in _cases(random.Random(11), TRAIN, 20):
        row = _row(case)
        derived = mine.derive(case, row)
        assert derived is not None
        assert derived == default.derive(case, row)


def test_a_registered_bound_is_add_only_and_its_region_refusal_keeps_its_code(
    clean_bounds,
):
    first = _recording([])
    pool_version.register_region_bound("cooling", "1.8", first)
    pool_version.register_region_bound("cooling", "1.8", first)  # again: no-op
    with pytest.raises(ValueError):
        pool_version.register_region_bound("cooling", "1.8", _recording([]))
    assert pool_version._REGION_BOUNDS[("cooling", "1.8")] is first

    pool_version._REGION_BOUNDS.clear()

    def refuses(binding, region):
        raise cooling_region.RegionRefused("region_bounds_malformed")

    pool_version.register_region_bound("cooling", "1.8", refuses)
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_version.official_binding("cooling", "1.8", region=REGION)
    assert caught.value.code == "region_bounds_malformed"


def test_a_grade_without_a_region_never_reads_the_registry(clean_bounds):
    before = pool_version.official_binding("cooling", "1.8")

    def never(binding, region):
        raise AssertionError("a grade without a region read the region bound")

    pool_version.register_region_bound("cooling", "1.8", never)
    after = pool_version.official_binding("cooling", "1.8")
    case = _cases(random.Random(3), TRAIN, 1)[0]
    row = _row(case)
    assert after.derive(case, row) == before.derive(case, row)
