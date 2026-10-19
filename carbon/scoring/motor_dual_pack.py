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


EVALUATION_VERSION = "motor-dual-development-bank-90-v1"
CASE_ID = "motor-development-bank-90"
OUTPUT = {"quantity": "torque_nm", "unit": "N.m"}
FILES = ("motor_dual_pack.py", "motor_dual_measurement.py")
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


def _platform_arguments(parser):
    parser.add_argument(
        "--inference-image",
        required=True,
        help="sha256 digest of the judge inference image the minimums belong to",
    )
    parser.add_argument("--device-class", default=physical.DEVICE_CLASS)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Write the complete Motor DEVELOPMENT evaluation pack."
    )
    parser.add_argument("root", type=Path, help="new or empty pack directory")
    _platform_arguments(parser)
    args = parser.parse_args(argv)
    print(
        write_development_pack(
            args.root.resolve(),
            inference_image_id=args.inference_image,
            device_class=args.device_class,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
