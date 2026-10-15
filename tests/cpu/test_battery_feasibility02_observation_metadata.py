"""Synthetic recorded arrays only: diagnostics do not qualify temporal adequacy."""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.dev.battery import feasibility02 as worker


@pytest.mark.parametrize(
    "times,status,gap,duplicates",
    [
        ([], "EMPTY_TIME_VECTOR", None, None),
        ([5], "SINGLE_TIME_POINT", None, None),
        ([0, 2, 2, 9], "OBSERVED_NONDECREASING", 7, 1),
        ([2, 2, 2], "OBSERVED_NONDECREASING", 0, 2),
        ([0, 9, 2], "BACKWARDS_TIME_VECTOR", None, None),
        ([0, float("nan")], "NONFINITE_TIME_VECTOR", None, None),
        ([0, float("inf")], "NONFINITE_TIME_VECTOR", None, None),
        ([-1e308, 1e308], "NONFINITE_TIME_DIFFERENCE", None, None),
        ([0, "unknown"], "INVALID_TIME_VECTOR", None, None),
    ],
)
def test_actual_time_inventory_preserves_order_and_types_unknowns(
    times, status, gap, duplicates
):
    before = list(times)
    metadata = worker._time_observations(times)
    assert metadata["observation_sample_count"] == len(times)
    assert metadata["status"] == status
    assert metadata["max_observed_time_gap_s"] == gap
    assert metadata["duplicate_time_count"] == duplicates
    assert times == before
    json.dumps(metadata, allow_nan=False)


def _step(times, *, charge=None, temperatures=None):
    times = np.asarray(times, dtype=float)
    count = len(times)
    arrays = {
        "Time [s]": times,
        "Volume-averaged cell temperature [K]": (
            np.full(count, 300.0) if temperatures is None else np.array(temperatures)
        ),
        "Voltage [V]": np.linspace(3, 4.2, count),
        "Discharge capacity [A.h]": (
            np.linspace(0, -0.8, count) if charge is None else np.array(charge)
        ),
        "Total heating [W]": np.full(count, 2.0),
        "Negative electrode lithium plating reaction overpotential [V]": np.full(
            count, 0.01
        ),
    }
    return {key: SimpleNamespace(entries=value) for key, value in arrays.items()}


COOLING = {"h_w_m2k": 2.0, "area_m2": 3.0, "t_amb_k": 300.0}


def test_phase_diagnostics_do_not_change_any_legacy_summary_quantity():
    summary = worker._step_summary(
        _step([0, 2, 2, 9], temperatures=[300, 302, 301, 301]), COOLING
    )
    metadata = summary.pop("time_observations")
    assert metadata["max_observed_time_gap_s"] == 7
    assert metadata["duplicate_time_count"] == 1
    assert summary == {
        "t_start_s": 0.0,
        "t_end_s": 9.0,
        "t_max_c": 302.0 - 273.15,
        "t_max_at_s": 2.0,
        "t_min_c": 300.0 - 273.15,
        "v_max_v": 4.2,
        "v_max_at_s": 9.0,
        "v_min_v": 3.0,
        "plating_min_v": 0.01,
        "charge_ah": 0.8,
        "cooling_peak_w": 12.0,
        "cooling_energy_j": 54.0,
        "heating_energy_j": 18.0,
    }


def test_single_phase_point_retains_old_values_but_has_no_measured_gap():
    summary = worker._step_summary(_step([7]), COOLING)
    assert summary["t_start_s"] == summary["t_end_s"] == 7
    assert summary["cooling_energy_j"] == 0
    assert summary["time_observations"]["status"] == "SINGLE_TIME_POINT"
    assert summary["time_observations"]["max_observed_time_gap_s"] is None


def _cycle(times, charges):
    # Four explicit steps, including empty steps, preserve the original clock's
    # concatenation and duplicate boundary samples without any resampling.
    steps = [_step(times, charge=charges)]
    steps.extend(_step([], charge=[]) for _ in range(3))
    return SimpleNamespace(steps=steps)


def test_between_point_crossing_retains_original_clock_and_observed_bracket():
    clock = worker._soc_clock(_cycle([0, 120, 300], [0, -0.4, -0.8]), 0.1, 1.0)
    metadata = clock.pop("soc80_observation")
    expected_fraction = (0.8 - 0.5) / (0.9 - 0.5)
    expected_time = 120 + expected_fraction * 180
    assert clock == {
        "status": "REACHED",
        "time_s": expected_time,
        "minutes": expected_time / 60,
        "soc10_time_s": None,
    }
    assert metadata["time_endpoints_s"] == [120, 300]
    assert metadata["soc_endpoints"] == [0.5, 0.9]
    assert metadata["interpolation_fraction"] == expected_fraction
    assert metadata["observed_bracket_width_s"] == 180
    assert metadata["exact_upper_sample_hit"] is False


def test_exact_upper_hit_keeps_wide_observed_bracket():
    clock = worker._soc_clock(_cycle([0, 120, 600], [0, -0.4, -0.8]), 0.0, 1.0)
    metadata = clock["soc80_observation"]
    assert clock["time_s"] == 600
    assert clock["soc10_time_s"] == 30
    assert metadata["exact_upper_sample_hit"] is True
    assert metadata["interpolation_fraction"] == 1
    assert metadata["observed_bracket_width_s"] == 480


@pytest.mark.parametrize(
    "times,charges,soc0,expected",
    [
        ([0, 120], [0, -0.2], 0.1, {"status": "NOT_REACHED", "horizon_s": 120.0, "soc_end": 0.1 + 0.2}),
        ([5, 120], [0, -0.2], 0.8, {"status": "AT_START", "time_s": 5.0}),
    ],
)
def test_no_crossing_status_keeps_original_fields_and_null_bracket(
    times, charges, soc0, expected
):
    clock = worker._soc_clock(_cycle(times, charges), soc0, 1.0)
    metadata = clock.pop("soc80_observation")
    assert clock == expected
    assert metadata["status"] == "UNAVAILABLE_" + expected["status"]
    assert metadata["time_endpoints_s"] is None
    assert metadata["interpolation_fraction"] is None
    assert metadata["observed_bracket_width_s"] is None


@pytest.mark.parametrize(
    "times,socs,fraction,status",
    [
        ([10, 1], [0.1, 0.9], 0.875, "INVALID_TIME_VECTOR"),
        ([-1e308, 1e308], [0.1, 0.9], 0.875, "INVALID_TIME_VECTOR"),
        ([0, 10], [-1e308, 1e308], 0.0, "NONFINITE_BRACKET_ARITHMETIC"),
        ([0, 10], [0.1, float("nan")], 0.5, "NONFINITE_OR_MISMATCHED_SOC_VECTOR"),
        ([0, 10], [0.1, 0.9], float("inf"), "INVALID_INTERPOLATION_FRACTION"),
        ([0, 10], [0.1, 0.9], 1.5, "INVALID_INTERPOLATION_FRACTION"),
        ([0, 10], [0.9, 0.9], 0.5, "INVALID_SOC_CROSSING"),
    ],
)
def test_bad_crossing_arithmetic_is_null_and_never_a_temporal_pass(
    times, socs, fraction, status
):
    metadata = worker._soc80_observation(times, socs, crossing=1, fraction=fraction)
    assert metadata["status"] == status
    assert metadata["interpolation_fraction"] is None
    assert metadata["observed_bracket_width_s"] is None
    assert "adequate" not in metadata
    json.dumps(metadata, allow_nan=False)


def test_duplicate_times_are_not_discarded_from_crossing_inventory():
    clock = worker._soc_clock(_cycle([0, 120, 120, 300], [0, -0.2, -0.4, -0.8]), 0.1, 1.0)
    metadata = clock["soc80_observation"]
    assert metadata["time_observations"]["observation_sample_count"] == 4
    assert metadata["time_observations"]["duplicate_time_count"] == 1
    assert metadata["time_endpoints_s"] == [120, 300]


def _fake_pybamm(monkeypatch):
    class FakeInstalledClass:
        pass

    fake = SimpleNamespace(
        __version__="synthetic-version-only",
        BaseSolver=FakeInstalledClass,
        Solution=FakeInstalledClass,
        Experiment=FakeInstalledClass,
        set_logging_level=lambda _: None,
    )
    monkeypatch.setitem(sys.modules, "pybamm", fake)
    return fake


def test_source_inventory_hashes_actual_bytes_without_claiming_wheel_verification(
    tmp_path, monkeypatch
):
    _fake_pybamm(monkeypatch)
    installed = tmp_path / "installed.py"
    installed.write_bytes(b"# synthetic installed source\n")
    monkeypatch.setattr(inspect, "getsourcefile", lambda _: str(installed))
    simulation = SimpleNamespace(solver=SimpleNamespace())
    metadata = worker._observation_source_metadata(simulation)
    expected = hashlib.sha256(installed.read_bytes()).hexdigest()
    assert all(row["sha256"] == expected for row in metadata["installed_python_sources"].values())
    assert metadata["wheel_authenticity_verification"] == "NOT_PERFORMED_BY_THIS_DIAGNOSTIC"
    assert metadata["output_time_configuration"]["fixed_output_period_s"] is None
    installed.write_bytes(b"# changed source, same reported version\n")
    changed = worker._observation_source_metadata(simulation)
    assert changed["installed_python_sources"]["solver"]["sha256"] != expected


def test_source_hash_unavailable_is_not_substituted_with_version(monkeypatch):
    _fake_pybamm(monkeypatch)
    monkeypatch.setattr(inspect, "getsourcefile", lambda _: None)
    metadata = worker._observation_source_metadata(SimpleNamespace(solver=None))
    assert all(row["sha256"] is None for row in metadata["installed_python_sources"].values())
    assert all(row["status"] == "INSTALLED_PYTHON_SOURCE_UNAVAILABLE" for row in metadata["installed_python_sources"].values())


def test_unreadable_installed_source_does_not_become_a_reference_failure(monkeypatch):
    _fake_pybamm(monkeypatch)

    def denied(_):
        raise OSError("synthetic unreadable source")

    monkeypatch.setattr(inspect, "getsourcefile", denied)
    metadata = worker._observation_source_metadata(SimpleNamespace(solver=None))
    assert all(row["sha256"] is None for row in metadata["installed_python_sources"].values())
    json.dumps(metadata, allow_nan=False)


def test_all_thirty_phase_groups_and_initial_rest_emit_actual_diagnostics(monkeypatch):
    _fake_pybamm(monkeypatch)
    cycles = []
    for cycle in range(30):
        steps = []
        if cycle == 0:
            steps.append(_step([0, 60, 120], charge=[0, 0, 0]))
        for index, phase in enumerate(worker.PHASES):
            charge = [0, 0.5, 1.0] if phase == "discharge" else [0, -0.4, -0.8]
            start = 120 + index * 180
            steps.append(_step([start, start + 30, start + 180], charge=charge))
        cycles.append(SimpleNamespace(steps=steps))

    class Solution:
        def __init__(self):
            self.cycles = cycles

        def __getitem__(self, _):
            return SimpleNamespace(entries=np.array([0.0]))

    class Simulation:
        solver = None

        def solve(self, **_):
            return Solution()

    monkeypatch.setattr(worker, "_simulation", lambda _: (Simulation(), {**COOLING, "nominal_capacity_ah": 1.0}))
    monkeypatch.setattr(inspect, "getsourcefile", lambda _: None)
    record = worker.solve_one({"case_id": "synthetic-full30", "soc0": 0.1})
    assert record["status"] == "OK"
    assert len(record["per_cycle"]) == 30
    assert record["q30_over_q1"] == 1.0
    assert record["initial_rest"]["time_observations"]["max_observed_time_gap_s"] == 60
    for cycle in record["per_cycle"]:
        assert set(cycle["phases"]) == set(worker.PHASES)
        for phase in cycle["phases"].values():
            assert phase["time_observations"]["observation_sample_count"] == 3
            assert phase["time_observations"]["max_observed_time_gap_s"] == 150


def test_solver_failure_retains_old_typed_status_and_no_fabricated_diagnostics(monkeypatch):
    _fake_pybamm(monkeypatch)

    def failed(_):
        raise RuntimeError("synthetic solve failure")

    monkeypatch.setattr(worker, "_simulation", failed)
    record = worker.solve_one({"case_id": "synthetic-failure", "soc0": 0.1})
    assert record["status"] == "REFERENCE_SOLVER_FAILED"
    assert "observation_provenance" not in record
    assert "soc_clock" not in record
