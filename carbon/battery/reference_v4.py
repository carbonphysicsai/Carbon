"""Prospective v4 export beside the unchanged v3 reference and training code.

Uses the existing pinned DFN simulation and its already-stored current, heat
and discharge-capacity variables. No new scientific tolerance is selected.
There is one solve, and all seven quantities are extracted from that solution.
"""

from __future__ import annotations

import time

import numpy as np

from . import outputs_v4, reference


def extract(solution, case, *, nominal_capacity_ah):
    """Extract grid-aligned outputs; never extrapolate a truncated solution."""
    grid = np.asarray(outputs_v4.GRID, dtype=float)
    t = np.asarray(solution["Time [s]"].entries, dtype=float)
    if (
        t.ndim != 1
        or not len(t)
        or not np.all(np.isfinite(t))
        or t[0] > grid[0]
        or t[-1] < grid[-1]
        or np.any(np.diff(t) < 0)
    ):
        raise outputs_v4.OutputV4Refused("battery_v4_solution_time")
    if not outputs_v4._finite(nominal_capacity_ah) or nominal_capacity_ah <= 0:
        raise outputs_v4.OutputV4Refused("battery_v4_nominal_capacity")

    def sampled(name):
        values = np.asarray(solution[name].entries, dtype=float)
        if values.shape != t.shape or not np.all(np.isfinite(values)):
            raise outputs_v4.OutputV4Refused("battery_v4_solution_variable:" + name)
        return np.interp(grid, t, values)

    voltage = sampled("Voltage [V]")
    temperature = sampled("Volume-averaged cell temperature [K]") - 273.15
    current = sampled("Current [A]")
    heat = sampled("Total heating [W]")
    discharged = sampled("Discharge capacity [A.h]")
    soc = case.soc0 - (discharged - discharged[0]) / nominal_capacity_ah
    cycles = list(solution.cycles)
    if len(cycles) < 30 or any(
        cycles[k - 1] is None for k in outputs_v4.CAPACITY_CYCLES
    ):
        raise outputs_v4.OutputV4Refused("battery_v4_missing_cycle")
    charge = [cycles[0].steps[i + 1] for i in reference._CHARGE_STEPS]
    plating_values = [
        np.asarray(
            s["Negative electrode lithium plating reaction overpotential [V]"].entries,
            dtype=float,
        )
        for s in charge
    ]
    if any(not v.size or not np.all(np.isfinite(v)) for v in plating_values):
        raise outputs_v4.OutputV4Refused("battery_v4_plating")
    plating = min(float(np.min(v)) for v in plating_values)
    capacity = []
    for cycle in outputs_v4.CAPACITY_CYCLES:
        step = cycles[cycle - 1].steps[
            reference._DISCHARGE_STEP + (1 if cycle == 1 else 0)
        ]
        values = np.asarray(step["Discharge capacity [A.h]"].entries)
        if not len(values) or not np.all(np.isfinite(values)):
            raise outputs_v4.OutputV4Refused("battery_v4_capacity")
        capacity.append(float(values[-1] - values[0]))
    return outputs_v4.validate(
        {
            "schema": outputs_v4.SCHEMA,
            "output_contract_digest": outputs_v4.digest(),
            "status": "OK",
            "case_id": case.case_id,
            "inputs": case.inputs(),
            "grid_s": list(outputs_v4.GRID),
            "capacity_cycles": list(outputs_v4.CAPACITY_CYCLES),
            "nominal_capacity_ah": nominal_capacity_ah,
            "nominal_capacity_source": "OKane2022 Nominal cell capacity [A.h]",
            "outputs": {
                "voltage_v": voltage.tolist(),
                "temperature_c": temperature.tolist(),
                "plating_margin_v": plating,
                "capacity_ah": capacity,
                "current_a": current.tolist(),
                "heat_w": heat.tolist(),
                "soc": soc.tolist(),
            },
        }
    )


def reference_solver(job):
    """One v4 DEVELOPMENT solve under truth_env's verified runtime."""
    case = reference.BatteryCase(
        job["case_id"], job["c1"], job["c2"], job["t_amb_c"], job["soc0"]
    )
    start = time.perf_counter()
    try:
        simulation = reference.build_simulation(case, 30, job.get("refined", False))
        solution = simulation.solve(
            initial_soc=case.soc0,
            save_at_cycles=list(outputs_v4.CAPACITY_CYCLES),
            calc_esoh=False,
        )
        record = extract(
            solution,
            case,
            nominal_capacity_ah=float(
                simulation.parameter_values["Nominal cell capacity [A.h]"]
            ),
        )
    except MemoryError:
        return {
            "schema": outputs_v4.SCHEMA,
            "status": "FAILED_INFRA",
            "reason": "memory_bound",
        }
    except Exception as exc:  # noqa: BLE001 -- typed reference failure
        return {
            "schema": outputs_v4.SCHEMA,
            "status": "REFERENCE_SOLVER_FAILED",
            "error": type(exc).__name__,
        }
    record.update(
        refined=job.get("refined", False),
        n_cycles=30,
        wall_s=time.perf_counter() - start,
    )
    return record
