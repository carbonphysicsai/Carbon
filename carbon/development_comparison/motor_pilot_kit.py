"""Complete 10p/12s holding/peak/cogging panel around the existing slice kit."""

from __future__ import annotations

import numpy as np

from scripts.dev.motor.feasibility02 import topology

from . import carbon_arm as ca
from . import motor_10p12s_kit as mk

CONDITION = "holding-J10-g0_peak-J15-g0_cogging-J0"
COMMANDS = ((0, 0),) + tuple((j, g) for j in (10, 15) for g in (-10, -5, 0, 5, 10))
ROLES = ("holding", "peak", "cogging")
CURVES = tuple(f"{role}_t{i:02d}" for role in ROLES for i in range(48))
METRICS = (
    "holding_mean_nm",
    "holding_pk_pk_nm",
    "holding_ripple_fraction",
    "peak_mean_nm",
    "peak_pk_pk_nm",
    "peak_ripple_fraction",
    "cogging_nm",
)
OBSERVABLES = METRICS + CURVES


def valid(inputs):
    return (
        not topology.validity(topology.TOPOLOGIES["10p12s"], inputs)
        and (inputs["j_a_mm2"], inputs["gamma_deg"]) in COMMANDS
    )


def kit(geometry):
    base = mk.kit(geometry)

    def rows(row):
        if row["condition"] != CONDITION or row["action"]["skew_deg"] not in (0, 2, 4):
            raise ca.ArmRefused("COMPLETE_MOTOR_PANEL_REQUIRED")
        return [{**row, "condition": c} for c in ("J10-g0", "J15-g0")]

    def queries(row):
        holding, peak = (base.row_queries(r) for r in rows(row))
        return holding[:3] + peak[:3] + [holding[3]]

    def reduce(row, predicted):
        h, p = rows(row)
        result = {}
        for role, part, local in (
            ("holding", predicted[:3], h),
            ("peak", predicted[3:6], p),
        ):
            metrics = base.row_values(local, part + [predicted[6]])
            result.update(
                {f"{role}_{k}": metrics[k] for k in mk.OBSERVABLES if k != "cogging_nm"}
            )
            shifts = [
                mk._shift(d)
                for d in (
                    -row["action"]["skew_deg"] / 2,
                    0,
                    row["action"]["skew_deg"] / 2,
                )
            ]
            stacked = np.mean(
                [np.roll([c[o] for o in mk.OUTPUTS], -s) for c, s in zip(part, shifts)],
                0,
            )
            result.update({f"{role}_t{i:02d}": float(v) for i, v in enumerate(stacked)})
        zero = [predicted[6][o] for o in mk.OUTPUTS]
        cogging = np.mean([np.roll(zero, -s) for s in shifts], 0)
        result.update({f"cogging_t{i:02d}": float(v) for i, v in enumerate(cogging)})
        result["cogging_nm"] = float(np.ptp(cogging))
        return result

    return ca.Kit(
        kit_id="carbon.motor-10p12s.complete-panel.kit.v1",
        family="motor",
        train_schema=mk.TRAIN_SCHEMA,
        inputs=tuple(topology.GRAMMAR.items()) + mk.INPUTS[-2:],
        categorical=frozenset(),
        observables=OBSERVABLES,
        row_inputs=lambda row: queries(row)[1],
        model_id="carbon.motor-10p12s.complete-panel.mlp-default.v1",
        outputs=mk.OUTPUTS,
        queries=queries,
        reduce=reduce,
        domain=valid,
    )
