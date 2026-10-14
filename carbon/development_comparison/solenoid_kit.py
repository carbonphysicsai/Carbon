"""Proposed solenoid L0 kit: whole 27-state force/field curves, not motor torque.

Material/coil/absolute anchor and native axisymmetric reference acceptance are
Data Collection/owner holds. Scaling uses the four existing proposal bounds.
No TRAIN point or stroke sample is an independent geometry or buyer job.
"""

from __future__ import annotations

import json
import math

from carbon.development_comparison.carbon_arm import ArmRefused, Kit

FAMILY = "solenoid-pole"
SCHEMA = "carbon.solenoid-pole.material-domain.v1"
TRAIN_SCHEMA = "carbon.solenoid-pole.train-record.v1"
COORDS = (
    ("tip_radius_over_Ra", (0.6, 1.0)),
    ("nose_length_over_S", (0.0, 0.5)),
    ("shoulder_radius_over_Ra", (1.0, 1.4)),
    ("yoke_web_over_Ra", (0.35, 0.75)),
)
STRATA = ("nominal", "hot", "gap")
CURRENTS = (0.25, 0.60, 1.0)
STROKES = tuple(i / 8 for i in range(9))
QUANTITIES = (
    "force_closing_n",
    "flux_linkage_wbturn",
    "peak_b_t",
    "coenergy_j",
    "dc_loss_w",
)
OUTPUTS = tuple(f"{q}_{j:02d}" for q in QUANTITIES for j in range(27))
OBSERVABLES = (*OUTPUTS, "force_envelope_error_n")


def kit_from_bytes(data):
    """Only a closed, fully bound public material-domain sidecar yields a kit."""
    doc = json.loads(data)
    if type(doc) is not dict or set(doc) != {
        "schema",
        "scope",
        "anchor_digest",
        "material_digest",
        "coil_digest",
        "domain_digest",
        "conditions",
        "strata",
        "coordinate_bounds",
        "current_fractions",
        "stroke_fractions",
        "force_targets_n",
    }:
        raise ArmRefused("SOLENOID_DOMAIN_SHAPE")
    if doc["schema"] != SCHEMA or doc["scope"] != "PUBLIC_DEVELOPMENT":
        raise ArmRefused("SOLENOID_PUBLIC_DOMAIN_REQUIRED")
    import re

    for key in ("anchor_digest", "material_digest", "coil_digest", "domain_digest"):
        if type(doc[key]) is not str or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", doc[key]
        ):
            raise ArmRefused("SOLENOID_ABSOLUTE_INPUT_HOLD")
    if (
        doc["strata"] != list(STRATA)
        or doc["coordinate_bounds"] != {n: list(b) for n, b in COORDS}
        or doc["current_fractions"] != list(CURRENTS)
        or doc["stroke_fractions"] != list(STROKES)
        or type(doc["conditions"]) is not dict
        or set(doc["conditions"].values()) != set(STRATA)
    ):
        raise ArmRefused("SOLENOID_DOMAIN_DRIFT")
    conditions = doc["conditions"].copy()
    targets = doc["force_targets_n"]
    if (
        type(targets) is not dict
        or set(targets) != set(STRATA)
        or any(
            type(v) is not list
            or len(v) != 27
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
            for v in targets.values()
        )
    ):
        raise ArmRefused("SOLENOID_BUYER_TARGETS_REQUIRED")

    def inputs(row):
        if row["condition"] not in conditions:
            raise ArmRefused("SOLENOID_CONDITION_UNREGISTERED")
        return {**row["action"], "stratum": conditions[row["condition"]]}

    def domain(values):
        return values["stratum"] in STRATA and all(
            type(values[n]) in (int, float)
            and math.isfinite(values[n])
            and lo <= values[n] <= hi
            for n, (lo, hi) in COORDS
        )

    def reduce(row, predictions):
        values = predictions[0].copy()
        target = targets[conditions[row["condition"]]]
        values["force_envelope_error_n"] = max(
            abs(values[f"force_closing_n_{j:02d}"] - target[j]) for j in range(27)
        )
        return values

    return Kit(
        kit_id="carbon.solenoid-pole.kit.proposed.v1",
        family=FAMILY,
        train_schema=TRAIN_SCHEMA,
        inputs=COORDS,
        categorical=frozenset(),
        observables=OBSERVABLES,
        outputs=OUTPUTS,
        reduce=reduce,
        row_inputs=inputs,
        model_id="carbon.solenoid-pole.mlp-l0.proposed.v1",
        onehot=(("stratum", STRATA),),
        domain=domain,
    )
