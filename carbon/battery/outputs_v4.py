"""Prospective DEVELOPMENT battery output schema. No Challenge registration.

The v3 output interface and every pinned training module remain untouched.
Current is positive for discharge (PyBaMM convention). SOC is the explicitly
named nominal-capacity coulomb-counting observable, not a qualified estimate
of electrochemical state or capacity under ageing.
"""

from __future__ import annotations

import hashlib
import json
import math

SCHEMA = "carbon.battery.reference-record.v4"
CONTRACT_SCHEMA = "carbon.battery.exam-output-contract.v4"
GRID = tuple(range(0, 3601, 30))
CAPACITY_CYCLES = (1, 10, 20, 30)
SHAPES = {
    "voltage_v": 121,
    "temperature_c": 121,
    "plating_margin_v": 0,
    "capacity_ah": 4,
    "current_a": 121,
    "heat_w": 121,
    "soc": 121,
}
CONTRACT = {
    "schema": CONTRACT_SCHEMA,
    "status": "DEVELOPMENT_PROPOSAL",
    "registered_challenge_version": "HUMAN_INPUT",
    "record_schema": SCHEMA,
    "grid_s": list(GRID),
    "capacity_cycles": list(CAPACITY_CYCLES),
    "output_shapes": SHAPES,
    "units": {
        "voltage_v": "V",
        "temperature_c": "degC",
        "plating_margin_v": "V",
        "capacity_ah": "Ah",
        "current_a": "A",
        "heat_w": "W",
        "soc": "dimensionless",
    },
    "current_sign": "positive discharge; negative charge",
    "heat_definition": "PyBaMM Total heating [W], signed total cell heat generation, including reversible heat",
    "soc_definition": "soc0 - (Discharge capacity [A.h](t) - Discharge capacity [A.h](0)) / nominal_capacity_ah",
    "soc_limitations": "nominal-capacity coulomb counting; no clipping; not an independently qualified electrochemical SOC measurement",
    "balance_identity": "soc(t)-soc0 = -integral(current_a dt)/(3600*nominal_capacity_ah)",
    "law_adoption": {
        "B11": "HUMAN_INPUT",
        "B12": "HUMAN_INPUT",
        "B13": "HUMAN_INPUT",
        "B14": "HUMAN_INPUT",
    },
    "tolerances": "HUMAN_INPUT",
    "thermal_parameter_contract": "HUMAN_INPUT",
    "note": "Total heating is not irreversible heating. B14 requires a separate irreversible/reversible decomposition before it is checkable. Current, heat and nominal SOC outputs alone do not qualify B11-B14.",
}


class OutputV4Refused(ValueError):
    """A record does not implement the prospective v4 output interface."""


def digest():
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                CONTRACT, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate(record):
    """Validate a successful v4 record, without scientific gates or scoring."""
    if type(record) is not dict:
        raise OutputV4Refused("battery_v4_record_identity")
    if (
        record.get("schema") != SCHEMA
        or record.get("output_contract_digest") != digest()
    ):
        raise OutputV4Refused("battery_v4_record_identity")
    if record.get("status") != "OK":
        raise OutputV4Refused("battery_v4_reference_not_ok")
    if type(record.get("case_id")) is not str or not record["case_id"]:
        raise OutputV4Refused("battery_v4_case")
    inputs = record.get("inputs")
    if (
        type(inputs) is not dict
        or set(inputs) != {"c1", "c2", "t_amb_c", "soc0"}
        or not all(_finite(value) for value in inputs.values())
    ):
        raise OutputV4Refused("battery_v4_inputs")
    outputs = record.get("outputs")
    if type(outputs) is not dict or set(outputs) != set(SHAPES):
        raise OutputV4Refused("battery_v4_outputs")
    for name, size in SHAPES.items():
        value = outputs[name]
        if size == 0:
            valid = _finite(value)
        else:
            valid = (
                type(value) is list
                and len(value) == size
                and all(_finite(v) for v in value)
            )
        if not valid:
            raise OutputV4Refused("battery_v4_output:" + name)
    if record.get("grid_s") != list(GRID) or record.get("capacity_cycles") != list(
        CAPACITY_CYCLES
    ):
        raise OutputV4Refused("battery_v4_grid")
    if (
        not _finite(record.get("nominal_capacity_ah"))
        or record["nominal_capacity_ah"] <= 0
    ):
        raise OutputV4Refused("battery_v4_nominal_capacity")
    return record
