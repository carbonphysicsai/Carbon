"""Pure preparation of published coarse labels for construction, NEVER truth.

No file access or numerical evaluation. Root authenticates delivery/role, runs
the extraction in TEST, and retains excluded/nonfinite rows in its ledger.
These are not completed rows of the separately registered 4,000-TRAIN plan.
"""

from __future__ import annotations

import hashlib
import json
import re

from carbon.design_search import tasks

SOURCE_SHA = "c6c23a5211af1e16b6decb6e702448d77471a7343fb05ff78e697bce2fa807b7"
REGISTRY_SHA = "b3007401e8a24aa4761d87f07832a0acfb4cd1e3230983bede5dd66ba8eaa4ba"
BASE_REGISTRY_SHA = "ce0ee4dd838fe78e1c902a883c3d4791705ae0efac20553fdb422bf2e320e632"
QUANTITIES = ("charging_t_max_c", "plating_min_v", "v_max_v", "q30_over_q1", "minutes")
NUMBER = r"[0-9]+(?:\.[0-9]+)?"
KEY = re.compile(rf"c1=({NUMBER}),c2=({NUMBER}),sv=({NUMBER}):h([124])@T({NUMBER})")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def prepare(
    raw,
    registry_raw,
    base_registry_raw,
    *,
    plan,
    expected_plan_digest,
    source_digest,
    registry_digest,
    base_registry_digest,
    scope,
):
    """Return JSONL bytes and a role/coverage receipt, without fits or solves.

    The actual five quantities are copied unchanged; old verdicts and voltage
    allowance are NOT carried into the new evaluator. Null labels remain null
    and the existing trainer counts/excludes them. No imputation or redraw.
    """
    from .owner_v3 import acquisition_inputs

    if scope not in ("SYNTHETIC_FIXTURE", "PUBLIC_DEVELOPMENT"):
        raise tasks.TaskError("development construction only")
    if (
        _sha(raw) != source_digest
        or _sha(registry_raw) != registry_digest
        or _sha(base_registry_raw) != base_registry_digest
    ):
        raise tasks.TaskError("construction source or registry bytes differ")
    if scope == "PUBLIC_DEVELOPMENT" and (
        source_digest != "sha256:" + SOURCE_SHA
        or registry_digest != "sha256:" + REGISTRY_SHA
        or base_registry_digest != "sha256:" + BASE_REGISTRY_SHA
    ):
        raise tasks.TaskError("registered published construction source required")
    document, registry = json.loads(raw), json.loads(registry_raw)
    if (
        document.get("schema") != "carbon.battery.feasibility02-v2-rescore.v1"
        or registry.get("schema")
        != "carbon.battery.feasibility02-v2-rescore-registry.v1"
    ):
        raise tasks.TaskError("published construction source schemas required")
    stages = [
        acquisition_inputs(plan, expected_digest=expected_plan_digest, stage=s)["jobs"]
        for s in ("calibration-pilot", "calibration-rest", "evaluation")
    ]
    exclusions = {
        tuple(
            float(j[k])
            for k in ("c1", "c2", "switch_voltage_v", "h_multiplier", "t_amb_c", "soc0")
        )
        for jobs in stages
        for j in jobs
    }
    records, excluded = [], []
    for case, values in document["cells"].items():
        match = KEY.fullmatch(case)
        if (
            match is None
            or type(values) is not dict
            or not set(QUANTITIES) <= set(values)
        ):
            raise tasks.TaskError(
                "construction input identity or observable inventory missing"
            )
        c1, c2, switch, cooling, ambient = map(float, match.groups())
        identity = (c1, c2, switch, cooling, ambient, 0.1)
        if identity in exclusions:
            excluded.append(case)
            continue
        record = {
            "schema": "carbon.battery-v3.train-record.v1",
            "case_id": "published-coarse402:" + case,
            "source": "public coarse feasibility02 study; construction/discovery only",
            "source_digest": source_digest,
            "registry_digest": registry_digest,
            "base_registry_digest": base_registry_digest,
            "inputs": {
                "c1": c1,
                "c2": c2,
                "switch_v": switch,
                "cooling": int(cooling),
                "ambient_c": ambient,
                "soc0": 0.1,
            },
            "outputs": {q: values[q] for q in QUANTITIES},
        }
        if scope == "SYNTHETIC_FIXTURE":
            record["fixture"] = True
        records.append(record)
    data = b"".join((json.dumps(r, allow_nan=False) + "\n").encode() for r in records)
    ranges = (
        {
            q: [
                min(r["inputs"][q] for r in records),
                max(r["inputs"][q] for r in records),
            ]
            for q in ("c1", "c2", "switch_v", "ambient_c")
        }
        if records
        else {}
    )
    receipt = {
        "schema": "carbon.scorelab.public-coarse-construction.v1",
        "scope": scope,
        "role": "PUBLIC_CONSTRUCTION_DISCOVERY_ONLY",
        "plan_digest": expected_plan_digest,
        "source_digest": source_digest,
        "registry_digest": registry_digest,
        "base_registry_digest": base_registry_digest,
        "source_rows": len(document["cells"]),
        "offered_training_rows": len(records),
        "calibration_evaluation_exclusions": excluded,
        "input_ranges_before_trainer_quality_exclusion": ranges,
        "TRAIN_plan_completed_rows_claimed": 0,
        "numerical_evaluation_reference": False,
        "qualification": False,
        "training_jsonl_digest": _sha(data),
    }
    return data, {**receipt, "receipt_digest": tasks.digest(receipt)}
