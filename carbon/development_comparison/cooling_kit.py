"""Registration-bound cooling L0 kit at the lid-side TIM2 case plane.

Learn the independently observed peak and cell pressure. Flow and hydraulic
power are derived identically for every arm; legacy heated-face peaks are not
TIM2 labels. No solver, map characterization or qualification is supplied.
"""

from __future__ import annotations

import json
import math

from carbon.challenge_pipeline import cooling_readiness as cr
from carbon.cold_plate import domain as cell
from carbon.development_comparison.carbon_arm import ArmRefused, Kit

FAMILY = cr.FAMILY
TRAIN_SCHEMA = "carbon.cooling-cell.tim2-train-record.v1"
OUTPUTS = ("peak_case_c", "cell_pressure_drop_pa")
OBSERVABLES = (*OUTPUTS, "half_cell_flow_m3_s", "half_cell_hydraulic_power_w")


def kit_from_bytes(data):
    registration = cr.validate(json.loads(data))
    services = {s["id"]: s for s in registration["services"]}
    rules = registration["grammar"]

    def inputs(row):
        if row["condition"] not in services:
            raise ArmRefused("COOLING_SERVICE_UNREGISTERED")
        return {**row["action"], "service": row["condition"]}

    def supported(values):
        if set(values) != {*cr.ACTION, "service"} or values["service"] not in services:
            return False
        for name in cr.ACTION:
            value, rule = values[name], rules[name]
            if type(value) not in (int, float) or not math.isfinite(value):
                return False
            if not rule["min"] <= value <= rule["max"]:
                return False
            index = (value - rule["min"]) / rule["step"]
            if not math.isclose(index, round(index), abs_tol=1e-8):
                return False
        return True

    def reduce(row, predictions):
        service = services[row["condition"]]
        physical = cell.check_inputs(
            {**row["action"], **{n: service[n] for n in cr.SERVICE_VALUES}}
        )
        geometry = cell.derived(physical)
        flow = geometry["flow_m3_s"] / geometry["channels"] / 2
        return {
            **predictions[0],
            "half_cell_flow_m3_s": flow,
            "half_cell_hydraulic_power_w": predictions[0]["cell_pressure_drop_pa"]
            * flow,
        }

    # Scale against the existing physical bounds, including fixed flow, so
    # a point-B registration never introduces a zero-width feature divisor.
    return Kit(
        kit_id="carbon.cooling-cell.tim2-kit.proposed.v1:" + registration["digest"],
        family=FAMILY,
        train_schema=TRAIN_SCHEMA,
        inputs=tuple((n, cell.INPUT_BOUNDS[n]) for n in cr.ACTION),
        categorical=frozenset(),
        observables=OBSERVABLES,
        outputs=OUTPUTS,
        row_inputs=inputs,
        reduce=reduce,
        model_id="carbon.cooling-cell.mlp-l0.proposed.v1",
        onehot=(("service", tuple(services)),),
        domain=supported,
    )
