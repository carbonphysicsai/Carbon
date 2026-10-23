"""Motor's adapter for the shared physical dual pack and producer.

DEVELOPMENT only, exposed development bank (``physical_pack.development_bank``,
committed repository material): never a hidden-exam or paying claim.

``physical_dual_pack`` owns the pack documents, the builder and the producer;
this module owns only what is Motor's. The score pack is the committed applied
definition (MOTOR_APPLIED_SCORE_DEFINITION_20261018, sha256 b4ea72a5...,
candidate ``base__A1__arithmetic__wd0p5::G1_BALANCED_BASELINE``) with its legs,
gates, minima, weight and decision policy unchanged, bound to this producer's
measurement basis. It is a new evaluation version; its results are not
compared with the historical replay. No value is chosen here. A and D are
measured by ``motor_dual_measurement``.
"""

from __future__ import annotations

import functools
import io
import json
import re
import sys
from pathlib import Path

from carbon.scoring import motor_dual_measurement as mdm
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring.physical_dual_pack import sha as _sha

CHALLENGE = "electric-motor-magnetics"
VERSION = "1.0"
#: The committed applied definition this pack reproduces (see module docstring).
SOURCE_DEFINITION_SHA256 = (
    "sha256:b4ea72a5cc251b9315705912c42d061971a31c07b6cc15a0365dd9a042d48a3c"
)
#: The historical G1 gate-policy measurement contract (the definition's identity
#: preimage); kept as lineage, not as this pack's measurement basis.
G1_MEASUREMENT_CONTRACT_SHA256 = (
    "sha256:8f374907064891b5a5d261d9d31d8c4159c69577e44daa6234ed83c79bd3f782"
)
#: The committed applied definition's file (sha256 SOURCE_DEFINITION_SHA256).
DEFINITION_FILE = (
    Path(__file__).resolve().parents[1]
    / "challenge_kit/data/motor-applied-score-definition-20261018.json"
)
#: MOTOR_DUAL_TRANSFER_ACQUISITION_MANIFEST_20261018: the source of the
#: verification budget, the one value the applied definition does not hold.
ACQUISITION_MANIFEST_SHA256 = (
    "sha256:9e32f3a3b233ca81e84475a715319a6c24ec48296560d460563fa28bdad76a53"
)
ACQUISITION_MANIFEST_FILE = DEFINITION_FILE.with_name(
    "motor-dual-transfer-acquisition-manifest-20261018.json"
)
_SIGNED_MARGIN_CELL = re.compile(
    r"max\(abs\(mean_margin_error_nm\)/([0-9]+(?:\.[0-9]+)?),"
    r"abs\(ripple_margin_error_fraction\)/([0-9]+(?:\.[0-9]+)?)\)"
)


@functools.cache
def applied_definition():
    """The committed applied definition, read only at its pinned bytes."""
    raw = DEFINITION_FILE.read_bytes()
    if _sha(raw) != SOURCE_DEFINITION_SHA256:
        raise ValueError("motor applied score definition differs from its pin")
    return json.loads(raw)


@functools.cache
def _verification_budget():
    raw = ACQUISITION_MANIFEST_FILE.read_bytes()
    if _sha(raw) != ACQUISITION_MANIFEST_SHA256:
        raise ValueError("motor acquisition manifest differs from its pin")
    budget = json.loads(raw)["verification_budget"]
    if type(budget) is not int or budget < 1:
        raise ValueError("motor acquisition manifest budget differs")
    return budget


def _definition_values():
    """The definition's "A" and "D" values, verbatim; no value is chosen here."""
    a, d = applied_definition()["A"], applied_definition()["D"]
    cell = _SIGNED_MARGIN_CELL.fullmatch(a["signed_margin_cell"])
    if (
        a["reducer"] != "minimum of eight unit benefits"
        or a["benefit"] != "1/(1+loss/scale)"
        or cell is None
        or d["benefit"] != f"1/(1+verified_regret/{d['scale']})"
    ):
        raise ValueError("motor applied score definition form differs")
    return {
        "losses": list(a["losses"]),
        "A_reducer": "minimum",
        "f0_scale": a["f0_scale"],
        "signed_margin_scale": a["signed_margin_scale"],
        "signed_margin_cell": {
            "mean_torque_nm": float(cell.group(1)),
            "ripple_fraction": float(cell.group(2)),
        },
        "D_scale": d["scale"],
        "verification_budget": _verification_budget(),
    }


def _applied_pack():
    """The definition's "applied_score_pack" less its three digests, which the
    shared registrar re-derives for this pack's physics and measurement basis."""
    pack = applied_definition()["applied_score_pack"]
    return {
        k: v
        for k, v in pack.items()
        if k
        not in ("pack_digest", "physics_contract_digest", "measurement_contract_digest")
    }


#: v2: the paired repeat is the identical graded procedure (per-case pairs,
#: Validator 2026-10-19), the registered repeat tolerance unchanged; v1 packs
#: (batched repeats) stay as history and are not re-scored.
EVALUATION_VERSION = "motor-dual-development-bank-90-v2"
CASE_ID = "motor-development-bank-90"
#: Every registered Challenge version: its evaluation version and case id
#: (step-2 batch, STEP2_BATCH_VERSIONS_20261020: 1.1 serves allowlist v6 with no
#: step caps; measurement unchanged). No default version.
VERSIONS = {
    "1.0": (EVALUATION_VERSION, CASE_ID),
    "1.1": ("motor-dual-development-bank-90-v3", CASE_ID),
    # Validator, 2026-10-20: 1.2 is 1.1's bank, physics and roles under the
    # backbone-catalog kit, so it is 1.1's measurement under 1.1's name.
    "1.2": ("motor-dual-development-bank-90-v3", CASE_ID),
    # Allowlist v7's catalog version (Validator, 2026-10-20): the predecessor's
    # measurement under its evaluation version; only the served allowlist differs.
    "1.3": ("motor-dual-development-bank-90-v3", CASE_ID),
    # Graph route v2 (`challenge_kit.version_lineage`; Validator no-limits
    # binding, 2026-10-23): construction only, so the predecessor's measurement
    # under its evaluation version.
    "1.4": ("motor-dual-development-bank-90-v3", CASE_ID),
}
OUTPUT = {"quantity": "torque_nm", "unit": "N.m"}
FILES = ("motor_dual_pack.py", "motor_dual_measurement.py")
#: Legs a measured baseline run sets minimums for.
MINIMUM_LEGS = ("A", "D")
MANIFEST_NAME = physical.MANIFEST_NAME
bank_digest = physical.bank_digest
Refused = mdm.MotorMeasurementRefused
validate_definition = mdm.validate_definition
_ADAPTER = sys.modules[__name__]


def definition(*, bank, train_raw):
    """Motor's registered accuracy definition fields (the shared module adds
    the producer, TRAIN and bank pins)."""
    return {
        "schema": mdm.DEFINITION_SCHEMA,
        "method": mdm.METHOD,
        "source_definition_sha256": SOURCE_DEFINITION_SHA256,
        "g1_measurement_contract_sha256": G1_MEASUREMENT_CONTRACT_SHA256,
        "paired_repeat_procedure": "per_case",
        "cohort_counts": {
            "practice": 30,
            "pilot_ordinary": 8,
            "pilot_difficult": 4,
            "decision_representative": 32,
            "decision_boundary_stress": 16,
        },
        **_definition_values(),
    }


def applied_pack(**_):
    return _applied_pack()


def physics_contract():
    """Motor's physics role is Data Collection's (``physical_pack``)."""
    return


def _train_records(train_raw):
    import numpy as np

    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        targets = np.asarray(data["targets"], dtype=float)
    return [
        {"status": "OK", "outputs": {"torque_nm": [float(v) for v in row]}}
        for row in targets
    ]


#: The registered Motor baseline (learned-krr-v1: kernel ridge, length 4,
#: ridge 1e-4; Launchpad's KRR baseline packet 5e200e38).
BASELINE = {"model": "kernel_ridge", "length": 4.0, "ridge": 1e-4}


def baseline_outputs(cases):
    """The registered baseline rebuilt from public TRAIN, predicted on
    ``cases`` (input dicts), with its linear algebra pinned to one thread."""
    return physical.single_threaded(
        "carbon.scoring.motor_dual_pack:_baseline_here", cases=list(cases)
    )


def _baseline_here(*, cases):
    from carbon.motor import recipes
    from carbon.motor.challenge import PublicMaterial

    model = recipes.build(
        BASELINE["model"],
        {"length": BASELINE["length"], "ridge": BASELINE["ridge"]},
        PublicMaterial.load(Path(__file__).resolve().parents[2]).train,
    )
    return [[float(v) for v in model.predict(case)["torque_nm"]] for case in cases]


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    return mdm.measure(
        bank=bank_rows,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        limits=limits,
        objective=objective,
        train=_train_records(train_raw),
    )


def producer_digest():
    return physical.producer_digest(_ADAPTER)


def pack_documents(**kwargs):
    return physical.pack_documents(_ADAPTER, **kwargs)


def write_development_pack(root, **platform):
    return physical.write_development_pack(_ADAPTER, root, **platform)


def produce(**kwargs):
    return physical.produce(_ADAPTER, **kwargs)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Write the complete Motor DEVELOPMENT evaluation pack."
    )
    physical.add_builder_arguments(parser)
    args = parser.parse_args(argv)
    print(write_development_pack(args.root.resolve(), **physical.builder_options(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
