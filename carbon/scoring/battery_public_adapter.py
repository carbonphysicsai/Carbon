"""Battery's practice adapter: ``battery_dual_pack``'s measure on the public
development bank, through modules a miner-reachable surface may import (Phase A).

The same registered A/D packet, composed exactly as ``battery_dual_pack`` composes
it, on ``battery_public_dual`` (``battery_dual_measurement`` without the edge to
the battery panel's attack harness). Equality with ``battery_dual_pack`` is pinned
in ``tests/cpu/test_battery_public_dual.py``. DEVELOPMENT only; practice feedback,
never an exam grade.
"""

from __future__ import annotations

from pathlib import Path

from carbon.scoring import battery_public_dual as pdm

CHALLENGE = "battery-fastcharge-ageing-development-v1"
VERSION = "2.0"
EVALUATION_VERSION = "battery-dual-development-bank-v2"
CASE_ID = "battery-development-bank"
#: 2.2 (Battery's launch version, 2.1 plus the backbone catalog) serves 2.1's
#: bank and pack set (Validator, 2026-10-22), so the same measurement.
VERSIONS = {version: (EVALUATION_VERSION, CASE_ID) for version in ("2.0", "2.1", "2.2")}
Refused = pdm.BatteryMeasurementRefused
_REPOSITORY = Path(__file__).resolve().parents[2]


def input_names():
    from carbon.battery import domain

    return list(domain.INPUTS)


def _contract():
    """EV4's decision contract, the one the quiz and the pack's limit and
    objective roles carry."""
    from carbon.battery.value import contract as ev

    document, _digest = ev.load(_REPOSITORY / pdm.CONTRACT)
    return document


def definition(*, bank, train_raw):
    """Battery's registered accuracy definition fields (as ``battery_dual_pack``)."""
    practice = [
        record
        for cohort, record in zip(
            bank["cohorts"], bank["reference_records"], strict=True
        )
        if cohort == "practice"
    ]
    _rated, mask = pdm.rated_cases(practice)
    return {
        "schema": pdm.DEFINITION_SCHEMA,
        "method": pdm.METHOD,
        "registry": {
            "path": pdm.REGISTRY[0],
            "sha256": pdm.REGISTRY[1],
            "candidate": pdm.CANDIDATE,
        },
        "g_feas": pdm.registry_gate(),
        "paired_repeat_procedure": "per_case",
        "paired_repeat": {"procedure": "per_case", "floor": 0},
        "unresolved_mask": mask,
        "decision_scenarios": pdm.decision_scenarios(),
        "ev4_references": pdm.pinned("ev4_references"),
        "b15_probe_plan": pdm.pinned("b15_probe_plan"),
    }


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    return pdm.measure(
        bank=bank_rows,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        contract=_contract(),
    )
