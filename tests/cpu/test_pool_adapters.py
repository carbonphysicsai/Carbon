"""Pool adapters: each Challenge's side of the pool grader, checked against the registered decision
functions and the version's public roles (no model, no solver)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from carbon.scoring import pool_adapters as pa
from carbon.scoring import practice_dual, practice_grid

VERSIONS = {"motor": "1.4", "cooling": "1.4", "f02": "2.4", "f08": "1.5"}


def _adapter(kind):
    return pa.adapter(kind, VERSIONS[kind], mass_of=lambda design: 0.3)


def _reference_rows(kind):
    chosen = practice_grid.adapter(kind, VERSIONS[kind])
    _bank, _public, _names, rows = practice_dual._rows(chosen)
    return [r for r in rows if r.get("reference_present") and r.get("reference")]


@pytest.mark.parametrize("kind", sorted(VERSIONS))
def test_the_adapter_splits_the_model_row_into_design_and_fixed_values(kind):
    chosen = _adapter(kind)
    names = set(chosen.input_names)
    assert set(chosen.design_names) | set(chosen.condition_names) == names
    assert not set(chosen.design_names) & set(chosen.condition_names)
    assert chosen.objective in chosen.outputs and chosen.sense in ("max", "min")
    assert all(output in chosen.outputs for output, _kind, _bound in chosen.limits)
    row = {name: float(i + 1) for i, name in enumerate(chosen.input_names)}
    rebuilt = chosen.model_row(
        {n: row[n] for n in chosen.condition_names},
        [row[n] for n in chosen.design_names],
    )
    assert rebuilt == [row[n] for n in chosen.input_names]
    with pytest.raises(pa.PoolAdapterRefused):
        (
            chosen.model_row({}, [0.0] * len(chosen.design_names))
            if chosen.condition_names
            else (chosen.model_row({"nope": 1.0}, [0.0] * len(chosen.design_names)))
        )


@pytest.mark.parametrize("kind", sorted(VERSIONS))
def test_the_limits_are_the_versions_registered_public_limits(kind):
    from carbon.challenge_kit import physical_pack

    chosen = practice_grid.adapter(kind, VERSIONS[kind])
    public = physical_pack.public_roles(chosen.CHALLENGE, VERSIONS[kind])
    constraints = json.loads(public["important_limit_definition"])["constraints"]
    bounds = sorted(bound for _output, _kind, bound in _adapter(kind).limits)
    assert bounds == sorted(float(v) for v in constraints.values())


def test_motor_derive_matches_the_registered_decision_quantities():
    from carbon.motor import customer_decision as decision

    chosen = _adapter("motor")
    contract = json.loads(
        __import__("carbon.challenge_kit.physical_pack", fromlist=["x"]).public_roles(
            "electric-motor-magnetics", "1.4"
        )["design_objective"]
    )["decision_contract"]
    rows = _reference_rows("motor")
    assert rows
    for row in rows[:12]:
        derived = chosen.derive_row(
            [row["inputs"][n] for n in chosen.input_names], row["reference"]
        )
        want = decision.quantities(contract, {"torque_nm": list(row["reference"])})
        assert derived == {
            "mean_nm": want["mean_nm"],
            "ripple_fraction": want["ripple_fraction"],
        }
        ok = all(
            (derived[o] <= b) if k == "<=" else (derived[o] >= b)
            for o, k, b in chosen.limits
        )
        assert ok == bool(want["feasible"])


def test_motor_refuses_a_malformed_or_gate_failing_curve_as_none():
    chosen = _adapter("motor")
    inputs = dict.fromkeys(chosen.input_names, 1.0)
    assert chosen.derive(inputs, [1.0] * 59) is None
    assert chosen.derive(inputs, [math.nan] * 60) is None
    assert chosen.derive(inputs, "not numbers") is None


def test_cooling_derive_decodes_the_encoded_row_and_matches_the_decision_quantities():
    from carbon.challenge_kit import physical_pack
    from carbon.cold_plate import customer_decision as decision
    from carbon.cold_plate import output_encoding

    chosen = _adapter("cooling")
    contract = json.loads(
        physical_pack.public_roles("chip-cold-plate", "1.4")["design_objective"]
    )["decision_contract"]
    rows = _reference_rows("cooling")
    assert rows
    for row in rows[:12]:
        native = [float(v) for v in row["reference"]]
        encoded = output_encoding.encode_targets(np.asarray([native]))[0]
        derived = chosen.derive_row(
            [row["inputs"][n] for n in chosen.input_names], list(encoded)
        )
        outputs = {
            "peak_c": native[0],
            "profile_c": native[1:31],
            "pressure_drop_pa": native[31],
        }
        want = decision.quantities(contract, row["inputs"], outputs)
        assert derived is not None
        assert math.isclose(derived["die_peak_c"], want["die_peak_c"], rel_tol=1e-9)
        assert math.isclose(derived["hydraulic_w"], want["hydraulic_w"], rel_tol=1e-9)
    inputs = dict.fromkeys(chosen.input_names, 1.0)
    assert chosen.derive(inputs, [1.0] * 31) is None


def test_f02_derive_is_the_peak_and_the_analytic_extra_energy():
    chosen = _adapter("f02")
    derived = chosen.derive({"peak_w": 90.0, "on_time_s": 4.0}, [93.5])
    assert derived == {"peak_top_c": 93.5, "extra_energy_j": 70.0 * 4.0}
    assert chosen.derive({"peak_w": 90.0, "on_time_s": 4.0}, [1.0, 2.0]) is None
    assert chosen.derive({"peak_w": 90.0, "on_time_s": 4.0}, [math.inf]) is None
    assert chosen.objective == "extra_energy_j" and chosen.sense == "max"


def test_f08_derive_takes_the_worst_tip_and_the_supplied_mass():
    from carbon.scoring import f08_dual_pack

    seen = []
    chosen = pa.adapter("f08", "1.5", mass_of=lambda d: seen.append(d) or 0.31)
    targets = list(f08_dual_pack._targets("1.5"))
    raw = [0.01 * (i + 1) for i in range(len(targets))]
    inputs = {n: float(i + 1) for i, n in enumerate(chosen.input_names)}
    derived = chosen.derive(inputs, raw)
    tips = [raw[targets.index(t)] for t in f08_dual_pack._TIPS]
    assert derived == {
        "static_tip_mm_per_n": raw[targets.index("static_tip_mm_per_n")],
        "worst_dynamic_mm_per_n": max(tips),
        "mass_kg": 0.31,
    }
    assert seen == [[float(i + 1) for i in range(len(chosen.input_names))]]
    assert chosen.registered_u == {"worst_dynamic_mm_per_n": 3.9e-05}
    assert chosen.derive(inputs, raw[:-1]) is None


def test_f08_needs_a_mass_source_and_no_challenge_is_guessed():
    with pytest.raises(pa.PoolAdapterRefused) as raised:
        pa.adapter("f08", "1.5")
    assert raised.value.code == "f08_mass_source_required"
    with pytest.raises(pa.PoolAdapterRefused):
        pa.adapter("battery", "2.1")


def test_the_limits_build_pool_grader_limits():
    from carbon.scoring import pool_grader

    limits = pa.pool_limits(_adapter("cooling"))
    assert all(isinstance(limit, pool_grader.Limit) for limit in limits)
    assert [limit.output for limit in limits] == ["die_peak_c", "hydraulic_w"]
