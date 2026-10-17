"""One-case mesh160 source and non-verdict route controls."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import numpy as np

from carbon.design_search import tasks
from scripts.dev.battery import feasibility02
from scripts.dev.score_lab import guarded419_t15_mesh160 as diagnostic
from scripts.dev.score_lab import guarded419_t15_mesh160_worker as worker


class Mesh160DiagnosticTest(unittest.TestCase):
    def test_diagnostic_extracts_finite_returned_array_location(self):
        def entry(values):
            return types.SimpleNamespace(entries=np.asarray(values, dtype=float))

        step = {
            "Time [s]": entry([0, 1, 2]),
            "Volume-averaged cell temperature [K]": entry([298, 299, 300]),
            "Voltage [V]": entry([4.1, 4.15, 4.19]),
            "Total heating [W]": entry([0, 0, 0]),
            "Discharge capacity [A.h]": entry([0, 1, 2]),
            "Negative electrode lithium plating reaction overpotential [V]": entry(
                [[0.001, 0.0008, 0.001], [0.002, 0.003, 0.002]]
            ),
        }
        cooling = {"h_w_m2k": 1.0, "area_m2": 1.0, "t_amb_k": 298.0}
        summary = feasibility02._step_summary(step, cooling, plating_diagnostic=True)
        self.assertEqual(summary["plating_observation"]["shape"], [2, 3])
        self.assertEqual(summary["plating_observation"]["time_axis"], 1)
        self.assertEqual(summary["plating_observation"]["min_index"], [0, 1])
        self.assertEqual(summary["plating_observation"]["min_at_s"], 1.0)
        step["Negative electrode lithium plating reaction overpotential [V]"] = entry(
            [[0.001, 0.0008, 0.001], [0.002, 0.003, 0.002], [0.004, 0.005, 0.006]]
        )
        with self.assertRaisesRegex(ValueError, "time axis is ambiguous"):
            feasibility02._step_summary(step, cooling, plating_diagnostic=True)

    def test_distinct_exact_job_and_no_rung_label_alias(self):
        expected = diagnostic.job()
        diagnostic.validate_job(expected)
        self.assertEqual(expected["rung"], 4)
        self.assertTrue(expected["case_id"].endswith(":mesh160"))
        self.assertEqual(
            feasibility02._guarded_job_context(expected),
            {"schema": diagnostic.RECORD, "reference_identity": diagnostic.observer()},
        )
        for change in (
            {"case_id": expected["case_id"].replace(":mesh160", ":mesh80")},
            {"rung": 3},
            {"c1": 1.5},
            {"reference_admission": "carbon.scorelab.guarded419.eval-admission.v1"},
            {"reference_role": "PUBLIC_EVALUATION"},
            {"switch_voltage_v": 4.0},
        ):
            with self.subTest(change=change), self.assertRaises(tasks.TaskError):
                diagnostic.validate_job({**expected, **change})
        bare = {**expected, "reference_admission": "unknown", "rung": 4}
        with self.assertRaises(tasks.TaskError):
            feasibility02._guarded_job_context(bare)

    def test_actual_simulation_uses_160_points_and_explicit_tolerances(self):
        captured = {}

        class Values(dict):
            def __init__(self, _name):
                super().__init__(
                    {
                        feasibility02.H_NAME: 2.0,
                        feasibility02.AREA_NAME: 1.0,
                        feasibility02.CAPACITY_NAME: 1.0,
                    }
                )

        def solver(**kwargs):
            captured["solver"] = kwargs
            return object()

        def simulation(_model, **kwargs):
            captured["simulation"] = kwargs
            return object()

        fake = types.SimpleNamespace(
            lithium_ion=types.SimpleNamespace(DFN=lambda _options: object()),
            ParameterValues=Values,
            IDAKLUSolver=solver,
            Experiment=lambda steps: captured.setdefault("steps", steps),
            Simulation=simulation,
        )
        with mock.patch.dict(sys.modules, {"pybamm": fake}):
            _, cooling = feasibility02._simulation(diagnostic.job())
        self.assertEqual(
            cooling["numerical_configuration"], diagnostic.NUMERICAL_CONFIGURATION
        )
        self.assertEqual(
            captured["simulation"]["var_pts"],
            diagnostic.NUMERICAL_CONFIGURATION["spatial_points_each"],
        )
        self.assertEqual(
            {k: captured["solver"][k] for k in ("rtol", "atol")},
            diagnostic.SOLVER_TOLERANCES,
        )
        self.assertEqual(captured["simulation"]["experiment_model_mode"], "legacy")
        self.assertEqual(len(captured["steps"]), 30)
        self.assertTrue(captured["steps"][0][0].startswith("Rest for 2 minutes"))
        self.assertIn("Hold at 4.19 V", captured["steps"][0][3])

    @staticmethod
    def record(value):
        cycles = [
            {
                "cycle": index,
                "phases": {
                    name: {
                        "plating_min_v": value if name == "cc1" else value + 1,
                        "t_start_s": 0.0,
                        "t_end_s": 1.0,
                        "plating_observation": {
                            "status": "FINITE_RETURNED_ENTRIES",
                            "shape": [3],
                            "entry_count": 3,
                            "time_axis": 0,
                            "min_index": [0],
                            "min_at_s": 0.0,
                            "min_v": value if name == "cc1" else value + 1,
                        },
                    }
                    for name in ("cc1", "cc2", "cv")
                },
            }
            for index in range(1, 31)
        ]
        return {
            "numerical_configuration": diagnostic.NUMERICAL_CONFIGURATION,
            "whole_programme": {
                "plating_min_v": value,
                "plating_min_cycle": 1,
                "plating_min_phase": "cc1",
                "v_max_v": 4.19,
            },
            "per_cycle": cycles,
        }

    def test_predeclared_route_band_never_becomes_a_verdict(self):
        with mock.patch.object(
            diagnostic,
            "tracking_report",
            return_value={"status": "TRACKING_COMPATIBLE"},
        ):
            inside = diagnostic.route_readout(self.record(0.0008982390331130684))
            below = diagnostic.route_readout(self.record(0.0008))
            upper = diagnostic.route_readout(self.record(0.001))
        self.assertEqual(inside["mesh320_route"], "STOP_UNCHANGED_PAIR_IMPOSSIBLE")
        self.assertEqual(
            below["mesh320_route"],
            "MATHEMATICALLY_POSSIBLE_SEPARATE_ADMISSION_REQUIRED",
        )
        self.assertEqual(
            upper["mesh320_route"],
            "MATHEMATICALLY_POSSIBLE_SEPARATE_ADMISSION_REQUIRED",
        )
        for result in (inside, below, upper):
            self.assertFalse(result["reference_verdict"])
            self.assertFalse(result["automatic_next_stage"])
            self.assertFalse(result["model_release"])
            self.assertFalse(result["score_release"])

    def test_missing_tracking_or_raw_extremum_stays_unresolved(self):
        row = self.record(0.0008)
        with mock.patch.object(
            diagnostic,
            "tracking_report",
            return_value={"status": "REFERENCE_UNRESOLVED"},
        ):
            self.assertEqual(
                diagnostic.route_readout(row)["status"], "REFERENCE_UNRESOLVED"
            )
        changed = copy.deepcopy(row)
        changed["whole_programme"]["plating_min_v"] = 0.0007
        with mock.patch.object(
            diagnostic,
            "tracking_report",
            return_value={"status": "TRACKING_COMPATIBLE"},
        ):
            outcome = diagnostic.route_readout(changed)
        self.assertEqual(outcome["status"], "REFERENCE_UNRESOLVED")
        self.assertEqual(outcome["mesh320_route"], "NOT_ADMITTED")
        changed = copy.deepcopy(row)
        changed["per_cycle"][0]["phases"]["cc1"]["plating_observation"]["min_at_s"] = (
            2.0
        )
        with mock.patch.object(
            diagnostic,
            "tracking_report",
            return_value={"status": "TRACKING_COMPATIBLE"},
        ):
            self.assertEqual(
                diagnostic.route_readout(changed)["status"], "REFERENCE_UNRESOLVED"
            )

    def test_raw_voltage_guard_and_nonfinite_observation_refuse(self):
        with mock.patch.object(
            diagnostic,
            "tracking_report",
            return_value={"status": "TRACKING_COMPATIBLE"},
        ):
            for changed in (
                {"v_max_v": 4.2},
                {"plating_min_v": float("nan")},
            ):
                row = self.record(0.0008)
                row["whole_programme"].update(changed)
                self.assertEqual(
                    diagnostic.route_readout(row)["status"], "REFERENCE_UNRESOLVED"
                )

    def test_worker_spec_and_source_pins_refuse_drift_before_output(self):
        with (
            mock.patch.object(
                worker, "_provenance", side_effect=AssertionError("too far")
            ),
            self.assertRaises(tasks.TaskError),
        ):
            worker.run({}, records_path="unused")
        with (
            self.subTest("actual source bytes"),
            TemporaryDirectory(dir=Path.cwd()) as name,
        ):
            root = Path(name)
            pins = {}
            for relative in worker.REQUIRED_SOURCES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(relative.encode())
                pins[relative] = hashlib.sha256(relative.encode()).hexdigest()
            spec = {
                "schema": worker.SCHEMA,
                "scope": "PUBLIC_DEVELOPMENT",
                "execution_source": "a" * 40,
                "source_files": pins,
                "job": diagnostic.job(),
                "observer": diagnostic.observer(),
                "attempt_id": "t15-mesh160-01",
            }
            worker._spec(spec)
            self.assertEqual(
                worker._source(spec, root, environ={"CODE_REF": "a" * 40}),
                "POD_CODE_REF_AND_LOCAL_BYTES",
            )
            path = root / worker.MODULE
            path.write_bytes(b"drift")
            with self.assertRaises(tasks.TaskError):
                worker._source(spec, root, environ={"CODE_REF": "a" * 40})

    def test_worker_one_attempt_retains_raw_and_stops(self):
        spec = {
            "schema": worker.SCHEMA,
            "scope": "PUBLIC_DEVELOPMENT",
            "execution_source": "a" * 40,
            "source_files": {name: "0" * 64 for name in worker.REQUIRED_SOURCES},
            "job": diagnostic.job(),
            "observer": diagnostic.observer(),
            "attempt_id": "t15-mesh160-01",
        }
        row = {
            **diagnostic.job(),
            "schema": diagnostic.RECORD,
            "status": "OK",
            "numerical_configuration": diagnostic.NUMERICAL_CONFIGURATION,
        }
        called = []

        def solve(job):
            called.append(job)
            return row

        with TemporaryDirectory(dir=Path.cwd()) as name:
            records = Path(name) / "records.jsonl"
            with (
                mock.patch.object(worker, "_source", return_value="PINNED"),
                mock.patch.object(
                    worker, "_provenance", return_value={"schema": "test"}
                ),
                mock.patch.object(
                    diagnostic,
                    "route_readout",
                    return_value={
                        "status": "RETURNED_NONVERDICT_DIAGNOSTIC",
                        "reference_verdict": False,
                        "automatic_next_stage": False,
                    },
                ),
            ):
                self.assertEqual(
                    worker.run(
                        spec, records_path=records, solve=solve, stamp=lambda r, _p: r
                    ),
                    0,
                )
            self.assertEqual(len(called), 1)
            self.assertEqual(
                json.loads(records.read_text())["case_id"], diagnostic.CASE_ID
            )
            receipt = json.loads(Path(str(records) + ".mesh160.json").read_text())
            self.assertEqual(
                receipt["raw_records_sha256"],
                hashlib.sha256(records.read_bytes()).hexdigest(),
            )
            self.assertFalse(receipt["automatic_retry"])
            self.assertFalse(receipt["automatic_next_stage"])
            self.assertFalse(receipt["reference_verdict"])
            with self.assertRaises(tasks.TaskError):
                worker.run(
                    spec, records_path=records, solve=solve, stamp=lambda r, _p: r
                )
            self.assertEqual(len(called), 1)

    def test_worker_rejects_type_changed_job_echo(self):
        row = {**diagnostic.job(), "schema": diagnostic.RECORD}
        self.assertTrue(worker._job_echo_valid(row))
        row["h_multiplier"] = True
        self.assertFalse(worker._job_echo_valid(row))


if __name__ == "__main__":
    unittest.main()
