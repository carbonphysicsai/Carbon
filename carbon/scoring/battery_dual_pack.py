"""Battery's adapter for the shared physical dual pack and producer.

DEVELOPMENT only, exposed development bank (``physical_pack.development_bank``,
committed repository material): never a hidden-exam or paying claim.

``physical_dual_pack`` owns the pack documents, the builder and the producer;
this module owns only what is Battery's. The values are the Carbon
Validator's registered Battery A/D packet (BATTERY_DUAL_PACKET_20261020),
measured by ``battery_dual_measurement``. Still HUMAN_INPUT, so Battery stays
unscored (fail closed): D's EV4 grid rows and B15's public probe pairs (both
wait for the Battery v2 material, which asks for their rows), and the
registered baseline recipe that sets the leg minimums (owner decision;
calibration mode until then).
"""

from __future__ import annotations

import sys
from pathlib import Path

from carbon.scoring import battery_dual_measurement as bdm
from carbon.scoring import physical_dual_pack as physical

CHALLENGE = "battery-fastcharge-ageing-development-v1"
VERSION = "1.0"
EVALUATION_VERSION = "battery-dual-development-bank-v1"
CASE_ID = "battery-development-bank"
OUTPUT = {
    "quantity": "voltage_v,temperature_c,plating_margin_v,capacity_ah",
    "unit": "V,degC,V,Ah",
}
FILES = ("battery_dual_pack.py", "battery_dual_measurement.py")
#: Legs a measured baseline run sets minimums for.
MINIMUM_LEGS = ("A", "D")
MANIFEST_NAME = physical.MANIFEST_NAME
bank_digest = physical.bank_digest
Refused = bdm.BatteryMeasurementRefused
validate_definition = bdm.validate_definition
_ADAPTER = sys.modules[__name__]
_REPOSITORY = Path(__file__).resolve().parents[2]
#: HUMAN_INPUT: the registered baseline recipe (owner decision; the packet
#: recommends Launchpad's Level 0 scaffold_mlp).
BASELINE = None


def input_names():
    from carbon.battery import domain

    return list(domain.INPUTS)


def _contract():
    """EV4's decision contract, the one the quiz and the pack's limit and
    objective roles carry."""
    from carbon.battery import quiz_stratum

    return quiz_stratum.contract(_REPOSITORY)


def definition(*, bank, train_raw):
    """Battery's registered accuracy definition fields (the shared module adds
    the producer, TRAIN and bank pins)."""
    practice = [
        record
        for cohort, record in zip(
            bank["cohorts"], bank["reference_records"], strict=True
        )
        if cohort == "practice"
    ]
    _rated, mask = bdm.rated_cases(practice)
    return {
        "schema": bdm.DEFINITION_SCHEMA,
        "method": bdm.METHOD,
        "registry": {
            "path": bdm.REGISTRY[0],
            "sha256": bdm.REGISTRY[1],
            "candidate": bdm.CANDIDATE,
        },
        "g_feas": bdm.registry_gate(),
        "paired_repeat_procedure": "per_case",
        "paired_repeat": {"procedure": "per_case", "floor": 0},
        "unresolved_mask": mask,
        # HUMAN_INPUT until the Battery v2 material asks for their rows.
        "decision_scenarios": None,
        "b15_probe_plan": None,
    }


def applied_pack(**_):
    """The packet's dual pack: 0.5 A + 0.5 D, the four gates, and D = q
    (q already prices every pick, so the one outcome reported is eligible)."""
    from carbon.scoring import dual_score

    return {
        "schema": dual_score.PACK_SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "challenge": CHALLENGE,
        "hard_gates": list(bdm.GATES),
        "legs": {
            leg: {
                "components": [
                    {
                        "metric": physical.METRICS[leg],
                        "unit": "1",
                        "transform": "unit_benefit",
                        "scale": None,
                        "weight": 1.0,
                    }
                ],
                "minimum": None,
            }
            for leg in ("A", "D")
        },
        "value_weight": 0.5,
        "combination": "weighted_arithmetic_mean",
        "decision_policy": {
            "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
            # The measurement reports VERIFIED_FEASIBLE only (D = q); the
            # others keep the shared packs' policy and never occur.
            "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
            "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
        },
    }


def physics_contract():
    """Battery's physics role is the served material's own."""
    return


def baseline_outputs(cases):
    """The registered baseline is HUMAN_INPUT: refuse, never default."""
    raise Refused("battery_baseline_unregistered")


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    return bdm.measure(
        bank=bank_rows,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        contract=_contract(),
    )


def producer_digest():
    return physical.producer_digest(_ADAPTER)


def pack_documents(**kwargs):
    return physical.pack_documents(_ADAPTER, **kwargs)


def write_development_pack(root, **platform):
    return physical.write_development_pack(_ADAPTER, root, **platform)


def produce(**kwargs):
    return physical.produce(_ADAPTER, **kwargs)
