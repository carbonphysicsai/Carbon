"""Prospective v4 export: fixtures only; no PyBaMM or reference solves in CI."""

import copy
import json
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.battery import outputs_v4 as v4
from carbon.battery import reference, reference_v4, truth_env


def case():
    return reference.BatteryCase("public-v4-fixture", 1, 0.5, 25, 0.2)


class Variables(dict):
    def __getitem__(self, name):
        return SimpleNamespace(entries=super().__getitem__(name))


def solution():
    times = np.asarray(v4.GRID, dtype=float)
    data = Variables(
        {
            "Time [s]": times,
            "Voltage [V]": 3.6 + times / 10000,
            "Volume-averaged cell temperature [K]": 298.15 + times / 10000,
            "Current [A]": np.full(121, -1),
            "Total heating [W]": np.full(121, -0.2),
            "Discharge capacity [A.h]": -times / 3600,
        }
    )
    charge = Variables(
        {"Negative electrode lithium plating reaction overpotential [V]": [0.01, 0.02]}
    )
    discharge = Variables({"Discharge capacity [A.h]": [0.1, 5.1]})
    steps1 = [charge] * 7
    steps1[5] = discharge
    steps = [charge] * 6
    steps[4] = discharge
    data.cycles = [SimpleNamespace(steps=steps1)] + [SimpleNamespace(steps=steps)] * 29
    return data


def record():
    return reference_v4.extract(solution(), case(), nominal_capacity_ah=5.0)


def test_current_heat_and_soc_share_the_existing_grid_with_documented_signs():
    result = record()
    assert result["schema"] == v4.SCHEMA
    assert result["grid_s"] == list(range(0, 3601, 30))
    assert result["outputs"]["current_a"] == [-1.0] * 121
    assert (
        result["outputs"]["heat_w"] == [-0.2] * 121
    )  # signed total, not irreversible heat
    assert result["outputs"]["soc"][0] == 0.2
    assert result["outputs"]["soc"][-1] == pytest.approx(0.4)
    # Charge balance on an exact fixture: A*s -> Ah, positive discharge.
    charge_ah = np.trapezoid(result["outputs"]["current_a"], result["grid_s"]) / 3600
    assert result["outputs"]["soc"][-1] - case().soc0 == pytest.approx(-charge_ah / 5)
    assert result["outputs"]["capacity_ah"] == [5.0] * 4
    assert v4.CONTRACT["law_adoption"]["B11"] == "HUMAN_INPUT"
    assert v4.CONTRACT["registered_challenge_version"] == "HUMAN_INPUT"


@pytest.mark.parametrize("name", list(v4.SHAPES))
def test_missing_or_nonfinite_v4_outputs_cannot_be_successful_reference_records(name):
    result = record()
    del result["outputs"][name]
    with pytest.raises(v4.OutputV4Refused, match="outputs"):
        v4.validate(result)
    result = record()
    result["outputs"][name] = (
        float("nan") if v4.SHAPES[name] == 0 else [float("nan")] * v4.SHAPES[name]
    )
    with pytest.raises(v4.OutputV4Refused, match="output:"):
        v4.validate(result)


def test_extraction_refuses_truncation_and_missing_physics_variables():
    data = solution()
    data["Time [s]"] = [0, 30]
    with pytest.raises(v4.OutputV4Refused, match="solution_time"):
        reference_v4.extract(data, case(), nominal_capacity_ah=5.0)
    data = solution()
    del data["Total heating [W]"]
    with pytest.raises(KeyError):
        reference_v4.extract(data, case(), nominal_capacity_ah=5.0)


def test_v4_records_require_the_case_identity_and_input_basis():
    result = record()
    del result["inputs"]
    with pytest.raises(v4.OutputV4Refused, match="inputs"):
        v4.validate(result)
    with pytest.raises(v4.OutputV4Refused, match="identity"):
        v4.validate(None)


def test_the_v4_solver_uses_one_unchanged_simulation_and_types_failures(monkeypatch):
    calls = []
    simulation = SimpleNamespace(parameter_values={"Nominal cell capacity [A.h]": 5})

    def solve(**kwargs):
        calls.append(kwargs)
        return solution()

    simulation.solve = solve
    monkeypatch.setattr(
        reference, "build_simulation", lambda c, cycles, refined: simulation
    )
    job = {"case_id": case().case_id, **case().inputs()}
    result = reference_v4.reference_solver(job)
    assert result["status"] == "OK" and len(calls) == 1
    assert calls[0]["save_at_cycles"] == [1, 10, 20, 30]
    simulation.solve = lambda **kwargs: (_ for _ in ()).throw(MemoryError())
    assert reference_v4.reference_solver(job)["status"] == "FAILED_INFRA"
    simulation.solve = lambda **kwargs: (_ for _ in ()).throw(
        ValueError("failed reference")
    )
    assert reference_v4.reference_solver(job)["status"] == "REFERENCE_SOLVER_FAILED"


def jobs(tmp_path):
    path = tmp_path / "jobs.v4.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.battery.truth-jobs.v4",
                "output_contract_digest": v4.digest(),
                "fingerprint": "v4-fixture",
                "jobs": [],
            }
        )
    )
    return path


def test_v4_refuses_existing_v3_bytes_before_appending(tmp_path, monkeypatch):
    monkeypatch.setattr(truth_env, "provenance", lambda repo: {"fixture": True})
    records = tmp_path / "records.jsonl"
    original = b'{"case_id":"old","status":"OK","outputs":{}}\n'
    records.write_bytes(original)
    records.chmod(0o600)
    with pytest.raises(truth_env.TruthEnvironmentError, match="pre-existing"):
        truth_env.solve(jobs(tmp_path), records, output_version="v4")
    assert records.read_bytes() == original
    assert not (tmp_path / "records.jsonl.output-contract.json").exists()


def test_version_bound_records_resume_without_rewriting_prior_bytes(
    tmp_path, monkeypatch
):
    from carbon.battery import truth

    monkeypatch.setattr(truth_env, "provenance", lambda repo: {"fixture": True})
    records = tmp_path / "records.v4.jsonl"
    jobs_path = jobs(tmp_path)

    class FixtureService:
        def __init__(self, path, **kwargs):
            self.path = path

        def run(self, jobs):
            with self.path.open("a") as stream:
                stream.write(
                    json.dumps({"case_id": "fixture-failure", "status": "FAILED_INFRA"})
                    + "\n"
                )
            return {"jobs": 0, "fixture": True}

    monkeypatch.setattr(truth, "TruthService", FixtureService)
    truth_env.solve(jobs_path, records, output_version="v4")
    original = records.read_bytes()
    assert json.loads(original)["schema"] == v4.SCHEMA
    truth_env.solve(jobs_path, records, output_version="v4")
    assert records.read_bytes().startswith(original)
    with pytest.raises(truth_env.TruthEnvironmentError, match="v3 refuses"):
        truth_env.solve(jobs_path, records)


def test_v4_container_route_is_explicit_separate_and_offline(tmp_path):
    old = truth_env.solve_command(tmp_path / "overlay", tmp_path)
    new = truth_env.solve_command(tmp_path / "overlay", tmp_path, output_version="v4")
    assert "/work/records.jsonl" in old and "/work/jobs.json" in old and "solve" in old
    assert (
        "/work/records.v4.jsonl" in new
        and "/work/jobs.v4.json" in new
        and "solve-v4" in new
    )
    assert new[new.index("--network") + 1] == "none"
    assert "--read-only" in new and "--cap-drop" in new


def test_v4_schema_identity_and_pinned_training_modules_stay_prospective():
    from carbon.battery import implementation_versions as versions

    assert (
        "outputs_v4.py" not in versions.MODULES
        and "reference_v4.py" not in versions.MODULES
    )
    # Existing versions keep their own registered digests; no snapshot edited.
    assert versions.CURRENT == "3.0"
    result = copy.deepcopy(record())
    result["schema"] = "v3"
    with pytest.raises(v4.OutputV4Refused, match="identity"):
        v4.validate(result)
