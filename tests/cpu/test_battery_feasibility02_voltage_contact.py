"""Synthetic evidence controls only; no PyBaMM import, solve or qualification."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.dev.battery import feasibility02 as worker


class Expression:
    def __init__(self, function):
        self.function = function

    def evaluate(self, *, t, y, inputs):
        return self.function(t, y, inputs)

    def __str__(self):
        return "synthetic Voltage [V] - 4.2"


class Step(dict):
    pass


def descriptor(*, voltage=False, target=4.2, direction="charge"):
    class VoltageTermination:
        value = target
        operator = None

        def get_event_name(self, step):
            operator = ">" if step.direction == "charge" else "<"
            return f"Voltage {operator} {self.value} [V] [experiment]"

    return SimpleNamespace(
        description="synthetic CV" if voltage else "synthetic CC",
        control_kind=SimpleNamespace(value="voltage" if voltage else "current"),
        value=target if voltage else -0.4,
        direction=direction,
        termination=[] if voltage else [VoltageTermination()],
    )


def step(times=(0, 1, 2), volts=(4.0, 4.1, 4.2), *, termination=None):
    sample = Step(
        {
            "Time [s]": SimpleNamespace(entries=np.asarray(times)),
            "Voltage [V]": SimpleNamespace(entries=np.asarray(volts)),
        }
    )
    sample.termination = termination or "event: Voltage > 4.2 [V] [experiment]"
    sample.closest_event_idx = 0
    sample.t_event = np.asarray([times[-1]]) if len(times) else None
    sample.y_event = np.asarray([[volts[-1]]]) if len(volts) else None
    event = SimpleNamespace(
        event_type=SimpleNamespace(name="TERMINATION"),
        name="Voltage > 4.2 [V] [experiment]",
        expression=Expression(lambda t, y, inputs: 4.2 - y[0, 0]),
    )
    sample.all_models = [
        SimpleNamespace(
            events=[event],
            variables={
                "Voltage [V]": Expression(lambda t, y, inputs: y[0, 0]),
                "Battery voltage [V]": Expression(lambda t, y, inputs: y[0, 0]),
            },
            submodels={"external circuit": SimpleNamespace(control="algebraic")},
            algebraic={},
        )
    ]
    sample.all_inputs = [{"actual_input": 7}]
    return sample


def observe(sample, definition=None):
    result = worker._voltage_contact_observation(
        sample, descriptor() if definition is None else definition
    )
    json.dumps(result, allow_nan=False)
    assert result["acceptance_effect"] == "NONE_DIAGNOSTIC_ONLY"
    assert result["continuous_voltage_bound"] == "NOT_ESTABLISHED"
    assert "accepted" not in result and "PASS" not in result.values()
    return result


def test_terminal_roundoff_is_retained_separately_from_interior_and_event():
    terminal = 4.2000000000003
    sample = step(volts=(4.0, 4.1, terminal))
    before = sample["Voltage [V]"].entries.copy()
    result = observe(sample)
    assert result["samples"]["all"]["maximum"]["value_v"] == terminal
    assert result["samples"]["strict_interior"]["maximum"]["value_v"] == 4.1
    assert result["samples"]["terminal"]["voltage_v"] == terminal
    assert result["samples"]["penultimate"]["voltage_v"] == 4.1
    state = result["terminal_state"]
    assert state["termination_events"][0]["signed_residual"] == 4.2 - terminal
    assert state["matches_last_observed_time"] is True
    assert state["Voltage [V]"] == terminal
    np.testing.assert_array_equal(sample["Voltage [V]"].entries, before)


def test_large_interior_overshoot_cannot_be_hidden_by_correct_terminal_event():
    result = observe(step(volts=(4.0, 4.6, 4.2)))
    assert result["samples"]["strict_interior"]["maximum"] == {
        "index": 1,
        "time_s": 1.0,
        "value_v": 4.6,
    }
    assert result["terminal_state"]["termination_events"][0]["signed_residual"] == 0
    assert result["samples"]["all"]["maximum"]["value_v"] == 4.6


def test_cv_signed_residual_extrema_keep_every_sample_and_gross_errors():
    result = observe(step(volts=(4.19, 4.5, 4.2)), descriptor(voltage=True))
    residual = result["cv_voltage_minus_target"]
    assert residual["target_v"] == 4.2
    assert residual["extrema"]["count"] == 3
    assert residual["extrema"]["maximum"]["value_v"] == 4.5 - 4.2
    assert residual["extrema"]["minimum"]["value_v"] == 4.19 - 4.2
    assert (
        residual["positive_count"],
        residual["negative_count"],
        residual["zero_count"],
    ) == (1, 1, 1)


@pytest.mark.parametrize("termination", ["final time", "event: wrong event", "unknown"])
def test_event_state_presence_never_rewrites_wrong_or_final_time_termination(
    termination,
):
    result = observe(step(termination=termination))
    assert result["termination"] == termination
    assert result["terminal_state"]["status"] == "OBSERVED"
    assert (
        result["terminal_state"]["event_identity_basis"]
        == "LIBRARY_NEAREST_RESIDUAL_NOT_ROOT_CERTIFICATION"
    )


def test_wrong_target_direction_and_control_kind_are_actual_evidence_not_phase_labels():
    result = observe(step(), descriptor(target=4.3, direction="discharge"))
    assert result["descriptor"]["direction"] == "discharge"
    assert result["descriptor"]["terminations"][0]["value"] == 4.3
    assert (
        result["descriptor"]["terminations"][0]["event_name"]
        == "Voltage < 4.3 [V] [experiment]"
    )
    assert result["cv_voltage_minus_target"] is None
    wrong_cv = observe(step(), descriptor(voltage=True, target=4.4))
    assert wrong_cv["cv_voltage_minus_target"]["target_v"] == 4.4


@pytest.mark.parametrize(
    "times,volts",
    [
        ([], []),
        ([0, 1], [4.0]),
        ([0, 0, 2], [4.0, 4.1, 4.2]),
        ([0, 2, 1], [4.0, 4.1, 4.2]),
        ([0, float("nan"), 2], [4.0, 4.1, 4.2]),
        ([0, 1, 2], [4.0, float("inf"), 4.2]),
    ],
)
def test_missing_duplicate_reordered_or_nonfinite_samples_stay_explicit(times, volts):
    result = observe(step(times=times, volts=volts))
    assert result["status"] == "INVALID_OR_UNAVAILABLE_OBSERVATION"
    assert result["samples"] is None


@pytest.mark.parametrize("state", [None, [[float("nan")]], [[1, 2]], []])
def test_missing_or_malformed_event_state_never_certifies_contact(state):
    sample = step()
    sample.y_event = state
    result = observe(sample)
    assert result["terminal_state"]["status"] == "UNAVAILABLE"
    assert result["samples"]["all"]["maximum"]["value_v"] == 4.2


def test_state_evaluation_reads_actual_inputs_and_all_termination_events():
    sample = step()
    sample.closest_event_idx = 1
    model = sample.all_models[-1]
    model.events.append(
        SimpleNamespace(
            event_type=SimpleNamespace(name="TERMINATION"),
            name="wrong-close-event",
            expression=Expression(lambda t, y, inputs: inputs["actual_input"]),
        )
    )
    result = observe(sample)
    assert result["terminal_state"]["library_closest_event_name"] == "wrong-close-event"
    assert result["terminal_state"]["termination_events"][1]["signed_residual"] == 7


def test_descriptor_and_model_equation_are_separate_from_sample_subtraction():
    sample = step()

    class Variable:
        name = "Current variable [A]"

    sample.all_models[-1].algebraic[Variable()] = Expression(lambda t, y, inputs: 0.123)
    result = observe(sample, descriptor(voltage=True))
    assert result["cv_voltage_minus_target"]["extrema"]["maximum"]["value_v"] == 0
    equations = result["terminal_state"]["current_control_equations"]
    assert equations[0]["signed_residual"] == 0.123


def test_descriptor_absence_is_not_a_fabricated_control_identity():
    result = worker._voltage_contact_observation(step(), None)
    assert result["status"] == "DESCRIPTOR_UNAVAILABLE"
    assert result["descriptor"] is None
    assert result["cv_voltage_minus_target"] is None


def test_sample_fingerprint_changes_when_an_interior_value_changes():
    first = step()
    changed = copy.deepcopy(first)
    changed["Voltage [V]"].entries[1] = 4.6
    a, b = observe(first), observe(changed)
    assert (
        a["samples"]["paired_float64_le_sha256"]
        != b["samples"]["paired_float64_le_sha256"]
    )


def test_all_thirty_cycles_keep_phase_mapping_raw_maxima_and_legacy_calibration(
    monkeypatch,
):
    import inspect
    import sys

    from carbon.design_search import tasks
    from scripts.dev.score_lab import owner_v3_numerics as numerics

    fake = SimpleNamespace(set_logging_level=lambda _: None)
    monkeypatch.setitem(sys.modules, "pybamm", fake)
    monkeypatch.setattr(inspect, "getsourcefile", lambda _: None)
    definitions, cycles = [], []

    def complete_sample(start, *, phase):
        sample = step(times=(start, start + 1, start + 2))
        for name, values in {
            "Volume-averaged cell temperature [K]": [300, 301, 300],
            "Total heating [W]": [1, 1, 1],
            "Discharge capacity [A.h]": (
                [0, 0.5, 1] if phase == "discharge" else [0, -0.4, -0.8]
            ),
            "Negative electrode lithium plating reaction overpotential [V]": [0.01] * 3,
        }.items():
            sample[name] = SimpleNamespace(entries=np.array(values))
        if phase == "rest_after_discharge":
            sample["Voltage [V]"].entries[1] = 4.7
        definition = descriptor(voltage=phase == "cv")
        definition.description = f"actual-{len(definitions)}-{phase}"
        definitions.append(definition)
        return sample

    for cycle in range(30):
        samples = [complete_sample(0, phase="initial_rest")] if cycle == 0 else []
        samples.extend(
            complete_sample(3 * (len(definitions) + offset), phase=phase)
            for offset, phase in enumerate(worker.PHASES)
        )
        cycles.append(SimpleNamespace(steps=samples))

    class Solution:
        def __init__(self):
            self.cycles = cycles

        def __getitem__(self, _):
            return SimpleNamespace(entries=np.array([0.0]))

    sim = SimpleNamespace(
        experiment=SimpleNamespace(steps=definitions),
        solver=None,
        solve=lambda **_: Solution(),
    )
    monkeypatch.setattr(
        worker,
        "_simulation",
        lambda _: (
            sim,
            {
                "h_w_m2k": 2.0,
                "area_m2": 3.0,
                "t_amb_k": 300.0,
                "nominal_capacity_ah": 1.0,
            },
        ),
    )
    result = worker.solve_one({"case_id": "synthetic-full30-contact", "soc0": 0.1})
    assert result["status"] == "OK"
    assert len(result["per_cycle"]) == 30
    assert result["q30_over_q1"] == 1.0
    all_observations = [result["initial_rest"]["voltage_contact_observation"]]
    for cycle in result["per_cycle"]:
        assert set(cycle["phases"]) == set(worker.PHASES)
        for phase in worker.PHASES:
            summary = cycle["phases"][phase]
            all_observations.append(summary["voltage_contact_observation"])
            if phase == "rest_after_discharge":
                assert summary["v_max_v"] == 4.7
                assert (
                    summary["voltage_contact_observation"]["samples"][
                        "strict_interior"
                    ]["maximum"]["value_v"]
                    == 4.7
                )
    assert len(all_observations) == 181
    assert [row["descriptor"]["description"] for row in all_observations] == [
        definition.description for definition in definitions
    ]
    assert result["whole_programme"]["v_max_v"] == 4.7
    assert result["whole_programme"]["v_max_phase"] == "rest_after_discharge"
    values = {
        "charging_t_max_c": 27,
        "plating_min_v": 0.01,
        "minutes": 50,
        "q30_over_q1": result["q30_over_q1"],
        "v_max_v": 4.2000000000003,
    }
    receipt = numerics.pair_enclosures(
        values, values, expected_policy_digest=tasks.digest(numerics.POLICY)
    )
    assert receipt["status"] == "REFERENCE_UNRESOLVED"
    assert receipt["intervals"]["v_max_v"] == [4.2000000000003, 4.2000000000003]
