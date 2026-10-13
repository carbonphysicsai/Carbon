"""Public code/contract metadata only; no dataset or deployment is opened."""

import json
from pathlib import Path

from carbon.challenge_validator.battery_scoring import BatteryPracticeRule

from . import exam, physics_gate
from .challenge import CHALLENGE as KEY
from .value import admissibility

CHALLENGE = KEY.challenge_id


def promotion_rule():
    key = BatteryPracticeRule.RULE_KEY
    return {"key": key, "rule": exam.RULES[key]}


def gate_roster(repository):
    """Implemented gates, with their scopes kept distinct from activation.

    No scalar margin unit is defined for schema validity or mixed-output repeat
    checks. None records that owner input; it is never an invented proxy unit.
    """
    units = {
        "initial_voltage": "V",
        "initial_temperature": "degC",
        "voltage_ceiling": "V",
        "voltage_floor": "V",
        "capacity_bound": "Ah",
    }
    roster = {
        gate.gate_id: {"unit": units.get(gate.gate_id), "scope": "EXAM"}
        for gate in exam.GATES
    }
    if admissibility.THRESHOLD_BANDS is not None:
        roster["near_optimism_bands"] = {"unit": "bands", "scope": "VALUE_STUDY_ONLY"}
    contract = json.loads((Path(repository) / physics_gate.CONTRACT).read_bytes())
    for law in contract["laws"]:
        if law.get("adoption") == "ADOPTED":
            if law["id"] != "B15":
                raise ValueError("physics_gate_roster_requires_owner_mapping")
            roster[physics_gate.CODE] = {"unit": "degC", "scope": "OPT_IN_B15"}
    return roster
