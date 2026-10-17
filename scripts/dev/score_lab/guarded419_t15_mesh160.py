"""One prospective T15/h1 mesh160 reference-only diagnostic; no verdict.

The source fixes a real spatial mesh and a distinct identity. A returned point
only informs the predeclared 160/320 route stop. Scientific method acceptance,
finite resource admission and any later mesh320 are independent decisions.
"""

from __future__ import annotations

import math
from decimal import Decimal

from carbon.design_search import tasks
from scripts.dev.battery import guarded_reference as guard

ADMISSION = "carbon.scorelab.guarded419.t15-mesh160-diagnostic-admission.v1"
RECORD = "carbon.battery.guarded419-t15-mesh160-diagnostic-record.v1"
METHOD_ID = (
    "carbon.scorelab.battery-v3.t15-mesh160-nonverdict-diagnostic.dev-proposal.v1"
)
OBSERVER_ID = (
    "carbon.scorelab.battery-v3.t15-mesh160-returned-entry-observer.dev-proposal.v1"
)
DATASET = "carbon.scorelab.battery-v3.t15-mesh160-one-case-diagnostic.dev-proposal.v1"
CASE_ID = "scorelab-v3:t15-pair-probe-dev-v1:c1=1.25:c2=0.70:sv=4.10:T15:h1:mesh160"
SOLVER_TOLERANCES = {"rtol": 1e-7, "atol": 1e-9}
NUMERICAL_CONFIGURATION = {
    "spatial_points_each": {name: 160 for name in ("x_n", "x_s", "x_p", "r_n", "r_p")},
    "solver": "pybamm.IDAKLUSolver",
    "rtol": SOLVER_TOLERANCES["rtol"],
    "atol": SOLVER_TOLERANCES["atol"],
    "solver_output_variables": [
        "Voltage [V]",
        "Current [A]",
        "Volume-averaged cell temperature [K]",
        "Negative electrode lithium plating reaction overpotential [V]",
        "Discharge capacity [A.h]",
        "Loss of capacity to negative lithium plating [A.h]",
        "Total heating [W]",
    ],
    "experiment_model_mode": "legacy",
    "temporal_step_policy": "ADAPTIVE_IDAKLU_NO_FIXED_STEP_OVERRIDE",
    "observer_sampling": "FINITE_RETURNED_ENTRIES_NOT_CONTINUOUS_MINIMUM",
    "numerical_adequacy": "UNVALIDATED_NONVERDICT_DIAGNOSTIC",
}
METHOD = {
    "id": METHOD_ID,
    "scope": "PUBLIC_DEVELOPMENT",
    "case_id": CASE_ID,
    "parent_protocol_id": guard.METHOD_ID,
    "observer_id": OBSERVER_ID,
    "numerical_configuration": NUMERICAL_CONFIGURATION,
    "control_voltage_v": guard.CONTROL_V,
    "raw_voltage_maximum_v": guard.RAW_MAX_V,
    "tracking_v": guard.TRACKING_V,
    "cycles": 30,
    "claim": "ONE_RETURNED_OBSERVATION_NONVERDICT_NO_PHYSICAL_BOUND",
    "method_acceptance": "SCIENTIFIC_OWNER_REQUIRED",
}
STOP_LOWER = Decimal("0.00083765025470999752")
STOP_UPPER = Decimal("0.00095294822320053092")


def job():
    """Exact new source identity; a rung label alone cannot select mesh160."""
    return {
        "case_id": CASE_ID,
        "c1": 1.25,
        "c2": 0.70,
        "switch_voltage_v": 4.10,
        "h_multiplier": 1.0,
        "t_amb_c": 15.0,
        "soc0": 0.1,
        "refined": True,
        "rung": 4,
        "reference_method": METHOD_ID,
        "reference_method_digest": tasks.digest(METHOD),
        "reference_admission": ADMISSION,
        "reference_dataset": DATASET,
        "reference_role": "PUBLIC_DIAGNOSTIC",
    }


def validate_job(candidate):
    if type(candidate) is not dict or tasks.digest(candidate) != tasks.digest(job()):
        raise tasks.TaskError("exact one-case T15 mesh160 diagnostic job required")


def observer():
    return {
        "id": OBSERVER_ID,
        "protocol_id": METHOD_ID,
        "method_digest": tasks.digest(METHOD),
        "dataset_id": DATASET,
        "admission_id": ADMISSION,
        "cycles": 30,
        "soc0": 0.1,
        "initial_state": "FRESH",
        "plating_observable": (
            "MIN_FINITE_RETURNED_NEGATIVE_ELECTRODE_OVERPOTENTIAL_ENTRIES"
            "_CC1_CC2_CV_ALL_30_CYCLES"
        ),
        "plating_location_evidence": (
            "PER_CHARGE_PHASE_FINITE_ARRAY_SHAPE_TIME_AXIS_MIN_INDEX_AND_TIME"
        ),
        "raw_voltage": "OBSERVED_INITIAL_REST_AND_ALL_180_PHASES",
        "numerical_claim": "UNVALIDATED_NONVERDICT_DIAGNOSTIC",
    }


def tracking_report(record):
    """Reuse conjunctive raw/programme tracking; never infer physical truth."""
    return guard._tracking_report(
        record,
        expected_job=job(),
        reference_identity=observer(),
        record_schema=RECORD,
        method_digest=tasks.digest(METHOD),
    )


def route_readout(record):
    """Report only whether the unchanged-floor 160/320 route is impossible."""
    tracking = tracking_report(record)
    if tracking["status"] != "TRACKING_COMPATIBLE":
        return {
            "status": "REFERENCE_UNRESOLVED",
            "mesh320_route": "NOT_ADMITTED",
            "tracking": tracking,
            "reference_verdict": False,
        }
    try:
        if record["numerical_configuration"] != NUMERICAL_CONFIGURATION:
            raise ValueError("NUMERICAL_CONFIGURATION_MISMATCH")
        raw_max = record["whole_programme"]["v_max_v"]
        if type(raw_max) is not float or not math.isfinite(raw_max):
            raise ValueError("NONFINITE_RAW_VOLTAGE_MAXIMUM")
        if not raw_max < guard.RAW_MAX_V:
            raise ValueError("RAW_WHOLE_PROGRAMME_VOLTAGE_GUARD")
        raw = record["whole_programme"]["plating_min_v"]
        if type(raw) is not float or not math.isfinite(raw):
            raise ValueError("NONFINITE_RETURNED_PLATING_MINIMUM")
        observed = Decimal(str(raw))
        charging = [
            (cycle["cycle"], phase, cycle["phases"][phase])
            for cycle in record["per_cycle"]
            for phase in ("cc1", "cc2", "cv")
        ]
        if len(charging) != 90:
            raise ValueError("INCOMPLETE_CHARGING_MINIMUMS")
        for _, _, summary in charging:
            value = summary["plating_min_v"]
            observation = summary["plating_observation"]
            shape = observation["shape"]
            index = observation["min_index"]
            axis = observation["time_axis"]
            if (
                type(value) is not float
                or not math.isfinite(value)
                or observation["status"] != "FINITE_RETURNED_ENTRIES"
                or observation["min_v"] != value
                or type(shape) is not list
                or not shape
                or any(type(size) is not int or size < 1 for size in shape)
                or math.prod(shape) != observation["entry_count"]
                or type(axis) is not int
                or not 0 <= axis < len(shape)
                or type(index) is not list
                or len(index) != len(shape)
                or any(
                    type(position) is not int or not 0 <= position < size
                    for position, size in zip(index, shape, strict=True)
                )
                or type(observation["min_at_s"]) is not float
                or not math.isfinite(observation["min_at_s"])
                or not summary["t_start_s"]
                <= observation["min_at_s"]
                <= summary["t_end_s"]
            ):
                raise ValueError("INVALID_RETURNED_PLATING_LOCATION")
        minimum = min(charging, key=lambda item: item[2]["plating_min_v"])
        if (
            minimum[2]["plating_min_v"] != raw
            or record["whole_programme"]["plating_min_cycle"] != minimum[0]
            or record["whole_programme"]["plating_min_phase"] != minimum[1]
        ):
            raise ValueError("RETURNED_EXTREMUM_IDENTITY_MISMATCH")
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "status": "REFERENCE_UNRESOLVED",
            "mesh320_route": "NOT_ADMITTED",
            "reason": str(exc),
            "tracking": tracking,
            "reference_verdict": False,
        }
    inside = STOP_LOWER <= observed < STOP_UPPER
    return {
        "status": "RETURNED_NONVERDICT_DIAGNOSTIC",
        "case_id": CASE_ID,
        "mesh160_plating_min_v": str(observed),
        "stop_band_v": [str(STOP_LOWER), str(STOP_UPPER)],
        "mesh320_route": (
            "STOP_UNCHANGED_PAIR_IMPOSSIBLE"
            if inside
            else "MATHEMATICALLY_POSSIBLE_SEPARATE_ADMISSION_REQUIRED"
        ),
        "tracking": tracking,
        "reference_verdict": False,
        "physical_certificate": False,
        "automatic_next_stage": False,
        "model_release": False,
        "score_release": False,
    }
