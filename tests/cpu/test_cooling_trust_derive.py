"""The jax derive of Cooling's two scored decision quantities (carbon/cold_plate/trust_derive.py, SELF_TRUST H3e) equals the numpy reference
(`exam.die_peak_c`, `domain.derived`, `output_encoding.decode_row`) on random cases and encoded rows.
"""

from __future__ import annotations

import numpy as np
import pytest

jax = pytest.importorskip("jax")

from carbon.cold_plate import domain, exam, output_encoding, trust_derive

jax.config.update("jax_enable_x64", True)


def reference(case, row):
    outputs = output_encoding.decode_row(row[:32])
    die = exam.die_peak_c(case, outputs)
    hydraulic = outputs["pressure_drop_pa"] * domain.derived(case)["flow_m3_s"]
    return die, hydraulic


def cases(count, seed=1):
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < count:
        case = {name: rng.uniform(*domain.INPUT_BOUNDS[name]) for name in domain.INPUTS}
        try:
            domain.hotspot_shape(case)
        except ValueError:  # a hot spot that cannot reach its ratio is not a case
            continue
        row = np.concatenate(
            [
                [rng.uniform(-3, 3)],  # the peak's encoded excess
                rng.uniform(35, 95, domain.PROFILE_SEGMENTS),  # the profile
                [rng.uniform(2, 10)],  # the pressure's encoded value
                rng.normal(size=2),  # Cooling 1.8's two extra slots: ignored
            ]
        )
        out.append((case, row))
    return out


def test_the_outputs_are_the_pool_adapters_two_quantities_in_its_order():
    assert trust_derive.OUTPUTS == ("die_peak_c", "hydraulic_w")


def test_the_jax_derive_equals_the_numpy_reference_on_random_cases():
    batch = cases(40)
    rows = np.stack([row for _case, row in batch])
    inputs = np.array([[case[name] for name in domain.INPUTS] for case, _row in batch])
    got = np.asarray(trust_derive.derive(rows, inputs))
    assert got.shape == (40, 2)
    for index, (case, row) in enumerate(batch):
        die, hydraulic = reference(case, row)
        assert got[index, 0] == pytest.approx(die, rel=1e-9)
        assert got[index, 1] == pytest.approx(hydraulic, rel=1e-9)


def test_the_derive_reads_the_32_first_slots_and_ignores_the_rest():
    ((case, row),) = cases(1, seed=7)
    inputs = np.array([[case[name] for name in domain.INPUTS]])
    base = np.asarray(trust_derive.derive(row[None, :32], inputs))
    wide = np.asarray(trust_derive.derive(row[None, :], inputs))
    np.testing.assert_array_equal(base, wide)


def test_the_hydraulic_power_scales_with_the_flow_and_the_die_peak_with_the_heat_load():
    ((case, row),) = cases(1, seed=3)
    inputs = np.array([[case[name] for name in domain.INPUTS]])
    base = np.asarray(trust_derive.derive(row[None, :], inputs))[0]
    more_flow = inputs.copy()
    more_flow[0, domain.INPUTS.index("flow_lpm_per_kw")] *= 1.1
    assert np.asarray(trust_derive.derive(row[None, :], more_flow))[
        0, 1
    ] == pytest.approx(base[1] * 1.1)
    hotter = inputs.copy()
    hotter[0, domain.INPUTS.index("heat_load_w")] *= 1.05
    assert np.asarray(trust_derive.derive(row[None, :], hotter))[0, 0] > base[0]
