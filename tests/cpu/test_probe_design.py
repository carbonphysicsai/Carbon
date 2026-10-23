"""The private probe design (Validator conditions on receipt 615327e56): probes are
interleaved with the exam cells in a seeded content order, each probe base point
draws its own step from 0.5-1.5% of the span, and the probe region is the
registered input bounds."""

from __future__ import annotations

import numpy as np
import pytest

from carbon.scoring import cooling_physics, motor_physics, probe_design

BOUNDS = [(0.0, 10.0), (100.0, 200.0), (-5.0, 5.0)]


def _bank(n=8):
    inputs = np.array(
        [[1.0 + i, 120.0 + 5 * i, -2.0 + 0.5 * i] for i in range(n)], dtype="<f8"
    )
    return {
        "case_ids": tuple(f"c{i}" for i in range(n)),
        "cohorts": ("cell",) * n,
        "inputs": inputs,
        "references": np.ones((n, 2), dtype="<f8"),
        "reference_records": [{"status": "OK", "design_id": f"d{i}"} for i in range(n)],
    }


def _probed(bank=None, bases=4, **kwargs):
    bank = bank or _bank()
    cases = [dict(enumerate(map(float, row))) for row in bank["inputs"]]
    return probe_design.with_probes(
        bank,
        cases,
        challenge="test",
        bounds=BOUNDS,
        valid=lambda x: True,
        bases=bases,
        dtype="<f8",
        **kwargs,
    )


def _rows(bank):
    probes = [
        (i, r["probe"])
        for i, (c, r) in enumerate(
            zip(bank["cohorts"], bank["reference_records"], strict=True)
        )
        if c == probe_design.PROBE_COHORT
    ]
    return probes


def test_the_probes_are_interleaved_with_the_cells_never_a_suffix():
    bank = _probed()
    cohorts = list(bank["cohorts"])
    assert cohorts.count("cell") == 8 and cohorts.count("probe_response") == 4 * 7
    last_cell = max(i for i, c in enumerate(cohorts) if c == "cell")
    first_probe = min(i for i, c in enumerate(cohorts) if c != "cell")
    assert first_probe < last_cell  # a probe sits before the final cell
    assert cohorts[:8] != ["cell"] * 8 and cohorts[-8:] != ["cell"] * 8


def test_the_order_is_deterministic_from_the_cell_content_alone():
    first, again = _probed(), _probed()
    assert (first["inputs"] == again["inputs"]).all()
    assert first["case_ids"] == again["case_ids"]
    other = _bank()
    other["inputs"] = other["inputs"] + 0.25
    moved = _probed(other)
    assert not np.array_equal(first["inputs"], moved["inputs"])


def test_the_interleave_does_not_depend_on_the_cell_order():
    """Seeded from the sorted cell content, so a validator copy (same cells,
    different order) reorders the same probes the same way."""
    bank = _bank()
    shuffled = {**bank, "inputs": bank["inputs"][::-1]}
    assert probe_design.shuffle_seed(bank["inputs"]) == probe_design.shuffle_seed(
        shuffled["inputs"]
    )


def test_every_probe_row_is_unreferenced_and_the_mask_matches():
    bank = _probed()
    mask = bank["reference_present"]
    for flag, cohort, ref in zip(
        mask, bank["cohorts"], bank["references"], strict=True
    ):
        assert flag is (cohort == "cell")
        assert np.isnan(ref).all() == (not flag)


def test_each_probe_base_draws_its_own_step_in_the_half_to_one_and_a_half_percent():
    bank = _probed(bases=6)
    spans = [hi - lo for lo, hi in BOUNDS]
    rows = _rows(bank)
    by_base = {}
    for index, probe in rows:
        by_base.setdefault(probe["base"], {})[(probe["dim"], probe["sign"])] = index
    steps = []
    for k, members in by_base.items():
        base = bank["inputs"][members[(None, 0)]]
        fractions = set()
        for dim, span in enumerate(spans):
            plus = bank["inputs"][members[(dim, 1)]][dim] - base[dim]
            minus = base[dim] - bank["inputs"][members[(dim, -1)]][dim]
            assert plus == pytest.approx(minus)
            fractions.add(round(plus / span, 9))
        assert len(fractions) == 1  # one step per base, every input
        steps.append(fractions.pop())
    low, high = probe_design.DELTA_RANGE
    assert all(low <= f <= high for f in steps)
    assert len({round(f, 6) for f in steps}) > 1  # not one fixed step


def test_the_step_range_is_the_validators():
    assert probe_design.DELTA_RANGE == (0.005, 0.015)


def test_the_groups_and_law_rows_survive_the_interleave():
    bank = _probed(extra=(("twice", lambda x: [x[0], x[1], x[2]]),))
    rows = _rows(bank)
    grouped = probe_design.groups(rows)
    assert len(grouped) == 4 and all(len(g["dims"]) == 3 for g in grouped)
    pairs = probe_design.law_pairs(rows, "twice")
    assert len(pairs) == 4


def test_the_motor_probe_region_is_the_registered_bounds_but_for_the_current_floor():
    from carbon.motor import domain

    j = domain.INPUTS.index("current_density_a_mm2")
    for index, name in enumerate(domain.INPUTS):
        low, high = motor_physics.PROBE_BOUNDS[index]
        if index == j:
            # 1 A/mm^2 is the floor of the positivity law and the TRAIN fits;
            # the top leaves room for the scaled-current law row inside 15.
            assert (low, high) == (1.0, 13.0)
        else:
            assert (low, high) == domain.INPUT_BOUNDS[name]
    base = [0.0] * len(domain.INPUTS)
    base[j] = 12.0
    assert (
        dict(motor_physics.probe_extra())["j_up"](base)[j]
        == domain.INPUT_BOUNDS["current_density_a_mm2"][1]
    )
    base[j] = 4.0
    assert dict(motor_physics.probe_extra())["j_up"](base)[j] == pytest.approx(6.0)


def test_the_cooling_probe_region_is_the_registered_bounds_with_a_safe_inlet_shift():
    from carbon.cold_plate import domain

    assert cooling_physics.PROBE_BOUNDS == tuple(
        domain.INPUT_BOUNDS[n] for n in domain.INPUTS
    )
    inlet = domain.INPUTS.index("inlet_c")
    low, high = domain.INPUT_BOUNDS["inlet_c"]
    shift = dict(cooling_physics.probe_extra())["inlet_shift"]
    base = [domain.INPUT_BOUNDS[n][0] for n in domain.INPUTS]
    for value in (low, 38.0, 41.0, high):
        base[inlet] = value
        moved = shift(base)[inlet]
        assert low <= moved <= high and abs(moved - value) == 5.0
