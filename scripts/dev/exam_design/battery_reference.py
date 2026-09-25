"""Battery charging-and-degradation reference: one pinned PyBaMM configuration.

Public/synthetic DEVELOPMENT research for the exam-design campaign. The
reference is *the specified model*, not a real cell: agreement with it is
agreement with PyBaMM's DFN under the OKane2022 parameter set, and says nothing
about real-cell lifetime or safety.

Pinned configuration (``SPEC``):

* model ``pybamm.lithium_ion.DFN`` with solvent-diffusion-limited SEI, partially
  reversible lithium plating, porosity change for both, and a lumped thermal model;
* parameter set ``OKane2022`` exactly as published - no ageing parameter is
  scaled to make degradation larger or faster;
* a two-stage constant-current charge (``c1`` until 4.0 V, ``c2`` until 4.2 V),
  a 4.2 V hold to C/20, 10 min rest, 1C discharge to 2.5 V, 10 min rest;
* cycle 1 starts with a 2 min rest at the initial state of charge, so the first
  sample is an equilibrium state the initial-state gate can check.

Varied inputs (bounded, uniform): ``c1`` first-stage C-rate, ``c2`` second-stage
C-rate, ``t_amb_c`` ambient (= initial) temperature, ``soc0`` initial state of
charge.

Outputs, per case:

* ``voltage_v`` and ``temperature_c`` sampled every 30 s over the first 3600 s;
* ``plating_margin_v``: the minimum, over the cycle-1 charge steps and over the
  negative electrode, of PyBaMM's lithium plating reaction overpotential. A
  negative value means plating conditions were reached. It is an indicator of
  *the model's* plating driving force, not a measured plating quantity;
* ``capacity_ah``: discharge capacity at each declared checkpoint cycle.

Failures are typed so a reference problem is never scored as a model failure:
``REFERENCE_SOLVER_FAILED`` (the solver raised or did not complete every cycle),
``REFERENCE_TIMEOUT`` (the per-case wall limit expired) and ``FAILED_INFRA``
(the worker process died). Only ``OK`` cases can enter a dataset.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import numpy as np

os.environ.setdefault("PYBAMM_DISABLE_TELEMETRY", "true")

SPEC_VERSION = "carbon.exam-design.battery-reference.v1"

SPEC = {
    "spec_version": SPEC_VERSION,
    "challenge_id": "battery-charge-degradation",
    "pybamm_version": "26.8.0.0",
    "model": "DFN",
    "options": {
        "SEI": "solvent-diffusion limited",
        "SEI porosity change": "true",
        "lithium plating": "partially reversible",
        "lithium plating porosity change": "true",
        "thermal": "lumped",
    },
    "parameter_set": "OKane2022",
    "parameter_overrides": ["Ambient temperature [K]", "Initial temperature [K]"],
    "input_bounds": {
        "c1": [0.5, 2.0],
        "c2": [0.2, 1.0],
        "t_amb_c": [5.0, 40.0],
        "soc0": [0.05, 0.5],
    },
    "switch_voltage_v": 4.0,
    "v_max": 4.2,
    "v_min": 2.5,
    "cv_cutoff": "C/20",
    "discharge_rate": "1C",
    "initial_rest_s": 120,
    "grid_step_s": 30,
    "window_s": 3600,
    "mesh_points": 20,
    "solver": {"name": "IDAKLUSolver", "rtol": 1e-5, "atol": 1e-7},
    "refined_mesh_points": 40,
    "refined_solver": {"name": "IDAKLUSolver", "rtol": 1e-6, "atol": 1e-8},
}

OUTPUT_NAMES = ("voltage_v", "temperature_c", "plating_margin_v", "capacity_ah")

# The solver stores only these variables. Storing every variable at every output time made a
# 40-cycle solve hold 6 GB (32 GB refined), which OOM-killed pilot workers; outputs are identical.
STORED_VARIABLES = [
    "Voltage [V]",
    "Current [A]",
    "Volume-averaged cell temperature [K]",
    "Negative electrode lithium plating reaction overpotential [V]",
    "Discharge capacity [A.h]",
    "Loss of capacity to negative lithium plating [A.h]",
    "Total heating [W]",
]


def time_grid() -> np.ndarray:
    return np.arange(0, SPEC["window_s"] + 1, SPEC["grid_step_s"], dtype=float)


@dataclass(frozen=True)
class BatteryCase:
    case_id: str
    c1: float
    c2: float
    t_amb_c: float
    soc0: float

    def inputs(self) -> dict:
        return {
            "c1": self.c1,
            "c2": self.c2,
            "t_amb_c": self.t_amb_c,
            "soc0": self.soc0,
        }

    def vector(self) -> list[float]:
        return [self.c1, self.c2, self.t_amb_c, self.soc0]


def sample_cases(n: int, seed: int, prefix: str) -> list[BatteryCase]:
    """Uniform draws over the declared bounds; P(x) = Q(x) = uniform here."""
    rng = np.random.default_rng(seed)
    b = SPEC["input_bounds"]
    cases = []
    for i in range(n):
        v = {k: float(np.round(rng.uniform(lo, hi), 4)) for k, (lo, hi) in b.items()}
        cases.append(BatteryCase(case_id=f"{prefix}-{i:04d}", **v))
    return cases


def _experiment(case: BatteryCase, n_cycles: int):
    import pybamm

    body = (
        f"Charge at {case.c1}C until {SPEC['switch_voltage_v']} V",
        f"Charge at {case.c2}C until {SPEC['v_max']} V",
        f"Hold at {SPEC['v_max']} V until {SPEC['cv_cutoff']}",
        "Rest for 10 minutes",
        f"Discharge at {SPEC['discharge_rate']} until {SPEC['v_min']} V",
        "Rest for 10 minutes",
    )
    first = (f"Rest for {SPEC['initial_rest_s'] // 60} minutes",) + body
    return pybamm.Experiment([first] + [body] * (n_cycles - 1))


def build_simulation(case: BatteryCase, n_cycles: int, refined: bool = False):
    import pybamm

    model = pybamm.lithium_ion.DFN(dict(SPEC["options"]))
    params = pybamm.ParameterValues(SPEC["parameter_set"])
    t_k = 273.15 + case.t_amb_c
    params.update({"Ambient temperature [K]": t_k, "Initial temperature [K]": t_k})
    npts = SPEC["refined_mesh_points"] if refined else SPEC["mesh_points"]
    var_pts = {"x_n": npts, "x_s": npts, "x_p": npts, "r_n": npts, "r_p": npts}
    s = SPEC["refined_solver"] if refined else SPEC["solver"]
    solver = pybamm.IDAKLUSolver(
        rtol=s["rtol"], atol=s["atol"], output_variables=STORED_VARIABLES
    )
    return pybamm.Simulation(
        model,
        parameter_values=params,
        experiment=_experiment(case, n_cycles),
        var_pts=var_pts,
        solver=solver,
    )


# Step indices inside a cycle (cycle 1 has the initial rest prepended).
_CHARGE_STEPS = (0, 1, 2)
_DISCHARGE_STEP = 4


def solve_case(
    case: BatteryCase, n_cycles: int, checkpoints: list[int], refined: bool = False
) -> dict:
    """Solve one case in-process. Returns a record; never raises for solver failure."""
    import pybamm

    pybamm.set_logging_level("ERROR")
    rec: dict = {
        "case_id": case.case_id,
        "inputs": case.inputs(),
        "refined": refined,
        "n_cycles": n_cycles,
    }
    t0 = time.perf_counter()
    try:
        sim = build_simulation(case, n_cycles, refined)
        t1 = time.perf_counter()
        # Keep full solutions only for cycle 1 and the checkpoint cycles: a 40-cycle DFN solution kept
        # whole needs ~6 GB, which the pilot found OOM-kills parallel workers.
        sol = sim.solve(
            initial_soc=case.soc0,
            save_at_cycles=sorted(set(checkpoints) | {1}),
            calc_esoh=False,
        )
        t2 = time.perf_counter()
    except Exception as exc:  # noqa: BLE001
        rec.update(
            status="REFERENCE_SOLVER_FAILED",
            error=repr(exc)[:300],
            wall_s=time.perf_counter() - t0,
        )
        return rec
    rec["timing_s"] = {"build": t1 - t0, "solve": t2 - t1}
    cycles = list(sol.cycles)
    if len(cycles) < n_cycles or any(
        cycles[k - 1] is None for k in set(checkpoints) | {1}
    ):
        rec.update(
            status="REFERENCE_SOLVER_FAILED",
            error=f"completed {len(cycles)} of {n_cycles} cycles",
            wall_s=time.perf_counter() - t0,
        )
        return rec
    try:
        grid = time_grid()
        t = sol["Time [s]"].entries
        if t[-1] < grid[-1]:
            raise ValueError("solution shorter than the output window")
        v = np.interp(grid, t, sol["Voltage [V]"].entries)
        temp = (
            np.interp(grid, t, sol["Volume-averaged cell temperature [K]"].entries)
            - 273.15
        )
        c1 = cycles[0]
        charge = [c1.steps[i + 1] for i in _CHARGE_STEPS]  # +1: initial rest
        eta = min(
            float(
                np.min(
                    s[
                        "Negative electrode lithium plating reaction overpotential [V]"
                    ].entries
                )
            )
            for s in charge
        )
        q = {}
        for k in sorted(set(checkpoints) | {1}):
            st = cycles[k - 1].steps[_DISCHARGE_STEP + (1 if k == 1 else 0)]
            dq = st["Discharge capacity [A.h]"].entries
            q[k] = float(dq[-1] - dq[0])
        heat = sol["Total heating [W]"].entries
        rec.update(
            status="OK",
            outputs={
                "voltage_v": v.tolist(),
                "temperature_c": temp.tolist(),
                "plating_margin_v": eta,
                "capacity_ah": [q[c] for c in checkpoints],
            },
            diagnostics={
                "capacity_at_checkpoints_ah": {str(k): v for k, v in q.items()},
                "t_max_c": float(
                    np.max(sol["Volume-averaged cell temperature [K]"].entries) - 273.15
                ),
                "t_min_c": float(
                    np.min(sol["Volume-averaged cell temperature [K]"].entries) - 273.15
                ),
                "v_max_v": float(np.max(sol["Voltage [V]"].entries)),
                "v_min_v": float(np.min(sol["Voltage [V]"].entries)),
                "v0_v": float(sol["Voltage [V]"].entries[0]),
                "plated_capacity_ah": float(
                    sol["Loss of capacity to negative lithium plating [A.h]"].entries[
                        -1
                    ]
                ),
                "min_total_heating_w": None if heat is None else float(np.min(heat)),
                "experiment_duration_s": float(t[-1]),
            },
        )
    except Exception as exc:  # noqa: BLE001 -- failure is typed
        rec.update(
            status="REFERENCE_SOLVER_FAILED", error="extraction: " + repr(exc)[:300]
        )
    rec["wall_s"] = time.perf_counter() - t0
    return rec


def _ocp(params, key: str, sto: float, t_k: float) -> float:
    import inspect

    import pybamm

    f = params[key]
    if not callable(f):
        return float(f)
    n = len(inspect.signature(f).parameters)
    args = (pybamm.Scalar(sto),) + ((pybamm.Scalar(t_k),) if n > 1 else ())
    return float(np.asarray(params.evaluate(f(*args))).reshape(-1)[0])


def open_circuit_voltage(soc: float, t_amb_c: float) -> float:
    """Equilibrium cell voltage at ``soc`` and temperature, from the parameter set alone.

    Used by the initial-state gate. It is computed from the published parameters
    and PyBaMM's stoichiometry map, not read from any reference solve, so the gate
    does not take its expected value from the reference it checks.
    """
    import pybamm

    params = pybamm.ParameterValues(SPEC["parameter_set"])
    t_k = 273.15 + t_amb_c
    params.update({"Ambient temperature [K]": t_k, "Initial temperature [K]": t_k})
    x, y = pybamm.lithium_ion.get_initial_stoichiometries(soc, params)
    return _ocp(params, "Positive electrode OCP [V]", y, t_k) - _ocp(
        params, "Negative electrode OCP [V]", x, t_k
    )


def ocv_table(n: int = 4001) -> dict:
    """The published OCV table: parameter-set equilibrium voltage on a uniform SOC grid.

    PyBaMM's initial stoichiometries are linear in state of charge between the
    0 % and 100 % end points, so one end-point solve gives the whole table.
    OKane2022's entropic coefficients are zero, so the table is temperature
    independent.
    """
    import pybamm

    params = pybamm.ParameterValues(SPEC["parameter_set"])
    x0, y0 = pybamm.lithium_ion.get_initial_stoichiometries(0.0, params)
    x1, y1 = pybamm.lithium_ion.get_initial_stoichiometries(1.0, params)
    soc = np.linspace(0.0, 1.0, n)
    t_k = 298.15
    v = [
        _ocp(params, "Positive electrode OCP [V]", y0 + s * (y1 - y0), t_k)
        - _ocp(params, "Negative electrode OCP [V]", x0 + s * (x1 - x0), t_k)
        for s in soc
    ]
    return {
        "schema": "carbon.exam-design.ocv-table.v1",
        "parameter_set": SPEC["parameter_set"],
        "soc": soc.tolist(),
        "ocv_v": v,
        "stoichiometry": {
            "x0": float(x0),
            "x100": float(x1),
            "y0": float(y0),
            "y100": float(y1),
        },
    }


def capacity_bounds_ah() -> dict:
    """Upper bounds on dischargeable capacity from the parameter set.

    Full-electrode capacities (stoichiometry 0 to 1) and the cyclable-lithium
    inventory at the published initial concentrations. The cell cannot discharge
    more than the smallest; degradation only lowers the lithium inventory.
    """
    import pybamm

    p = pybamm.ParameterValues(SPEC["parameter_set"])
    F = 96485.33212
    area = p["Electrode width [m]"] * p["Electrode height [m]"]
    vol_n = (
        p["Negative electrode active material volume fraction"]
        * p["Negative electrode thickness [m]"]
        * area
    )
    vol_p = (
        p["Positive electrode active material volume fraction"]
        * p["Positive electrode thickness [m]"]
        * area
    )
    qn = vol_n * p["Maximum concentration in negative electrode [mol.m-3]"] * F / 3600
    qp = vol_p * p["Maximum concentration in positive electrode [mol.m-3]"] * F / 3600

    def conc(key):
        v = p[key]
        return float(v) if not callable(v) else float(p.evaluate(v(pybamm.Scalar(0.5))))

    qli = (
        (
            vol_n * conc("Initial concentration in negative electrode [mol.m-3]")
            + vol_p * conc("Initial concentration in positive electrode [mol.m-3]")
        )
        * F
        / 3600
    )
    return {
        "negative_ah": float(qn),
        "positive_ah": float(qp),
        "lithium_inventory_ah": float(qli),
        "bound_ah": float(min(qn, qp, qli)),
    }


def main() -> None:  # pragma: no cover - manual smoke entry
    import sys

    case = BatteryCase("smoke-0000", 1.0, 0.5, 25.0, 0.2)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    rec = solve_case(case, n, [1, n])
    print(json.dumps({k: rec[k] for k in rec if k != "outputs"}, indent=1))


if __name__ == "__main__":  # pragma: no cover
    main()
