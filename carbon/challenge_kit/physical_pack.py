"""Public roles of the normal-construction DEVELOPMENT evaluation pack.

The receiver binds an opted-in pack to the construction material at every use:
its construction kit, interface and physics contract must equal the material's
documents and its train role must equal the material's TRAIN bytes. This module
builds those roles from the same source-owned functions the construction path
uses (``physical_public``), plus exact reviewed contract bytes, so the two can
only agree.

Private roles stay HUMAN_INPUT unless ``--exposed-development-bank`` is given.
That option binds the already-committed, exposed DEVELOPMENT decision bank
(Motor: 48 queries, their counted GetDP references and completion record) as
case_bank, reference_rows and solver_evidence. It moves no protected material
and makes no hidden-exam claim. The score pack and source registration remain
HUMAN_INPUT for their producer.

    python -m carbon.challenge_kit.physical_pack ROOT \
        --challenge electric-motor-magnetics [--exposed-development-bank]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from carbon.motor import challenge as motor
from carbon.motor import domain as motor_domain

from . import physical_public, physical_public_train

_DATA = Path(__file__).with_name("data")
_REPOSITORY = Path(__file__).resolve().parents[2]
PACK_SCHEMA = "carbon.challenge-evaluation-pack.v1"
UNAVAILABLE = "HUMAN_INPUT"
#: Exact reviewed bytes per public role, with their pinned sha256. The Motor
#: physics and accuracy contracts are the scorer's own (their hashes equal the
#: ScoreEngine physics_contract_digest and measurement_contract_digest);
#: the limit and objective documents are the reviewed counted-pack role inputs.
_ROLE_FILES = {
    motor.CHALLENGE.challenge_id: {
        "physics_contract": (
            "motor-applied-physics-contract-20261018.json",
            "74e3f30ce38d997e3b7f74505d67981bedcf77de28235ea60bf43f26be9483fd",
        ),
        "accuracy_definition": (
            "motor-applied-g1-measurement-contract-20261018.json",
            "8f374907064891b5a5d261d9d31d8c4159c69577e44daa6234ed83c79bd3f782",
        ),
        "important_limit_definition": (
            "motor-important-limit-definition-20261018.json",
            "3b532c6ef1b5c0ab02b692f16d2b565840fd77d75c71e92b44c0f11d32e0ef44",
        ),
        "design_objective": (
            "motor-design-objective-20261018.json",
            "cfc30f1e6b32415a6fa613413d94baf32efc23063d8b1aed71bd31a24bbe46c3",
        ),
    },
}
PACK_VERSIONS = {
    motor.CHALLENGE.challenge_id: "motor-normal-construction-development-1"
}
PRIVATE_ROLES = ("case_bank", "reference_rows", "solver_evidence", "score_pack")
#: The exposed DEVELOPMENT decision bank, committed in the repository, pinned.
_BANKS = {
    motor.CHALLENGE.challenge_id: {
        "study": (
            "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json",
            "cf00f2bbbfe8cd0adad7d668d921fa2e0f24d97353d7391885d88b4d0139e56d",
        ),
        "references": (
            "docs/development/evidence/track-b-replay/motor-counted-v2.json",
            "186ca2eae8cebb1b5b2cf253c4df70eb9de0b168900f24dd714d2ce87cc17714",
        ),
        "completion": (
            "docs/development/evidence/motor-decision-counted-v2/completion.json",
            "4662e9679ce3e2a7b7c3e3e357ca04d0546e3909b6dc11e8c241d538a0331f56",
        ),
    },
}


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _files(challenge_id: str, version: str) -> dict:
    if challenge_id not in _ROLE_FILES:
        raise ValueError("no normal-construction pack for this Challenge")
    physical_public.construction_kit(challenge_id, version)  # refuses unknown versions
    return _ROLE_FILES[challenge_id]


def _role_file(challenge_id: str, version: str, role: str) -> bytes:
    name, pinned = _files(challenge_id, version)[role]
    raw = (_DATA / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError(f"pinned {role} bytes differ")
    return raw


def physics_contract(challenge_id: str, version: str) -> dict:
    """The Challenge's physics contract, for the construction material to carry."""
    return json.loads(_role_file(challenge_id, version, "physics_contract"))


def public_roles(challenge_id: str, version: str) -> dict[str, bytes]:
    """Every public role's exact bytes; nothing is defaulted or inferred."""
    roles = {
        "construction_kit": _canonical(
            physical_public.construction_kit(challenge_id, version)
        ),
        "interface": _canonical(
            physical_public.interface_document(challenge_id, version)
        ),
        "train": physical_public_train.load_public_train(challenge_id)["train"],
    }
    for role in _files(challenge_id, version):
        roles[role] = _role_file(challenge_id, version, role)
    return roles


def _bank_file(challenge_id: str, name: str) -> bytes:
    path, pinned = _BANKS[challenge_id][name]
    raw = (_REPOSITORY / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError(f"pinned development bank {name} differs")
    return raw


def development_bank(challenge_id: str, version: str) -> dict:
    """The exposed DEVELOPMENT decision bank, in fixed design-then-condition order.

    ``inputs`` rows follow the numeric interface's input names and dtype;
    ``references`` are the counted solver outputs for the same rows. The
    construction material's practice inputs/reference must be these arrays, so
    the scored query equals the pack's case bank byte for byte.
    """
    _files(challenge_id, version)
    if challenge_id not in _BANKS:
        raise ValueError("no development bank for this Challenge")
    study = json.loads(_bank_file(challenge_id, "study"))
    solved = {
        case["case_id"]: case
        for case in json.loads(_bank_file(challenge_id, "references"))["cases"]
    }
    case_ids, rows, references, records = [], [], [], []
    for design in study["designs"]:
        for condition in study["conditions"]:
            case_id = f"decision-{design['design_id']}-{condition['condition_id']}"
            record = solved.get(case_id)
            if record is None or record.get("status") != "OK":
                raise ValueError(f"{case_id} has no accepted reference")
            values = {**design["values"], **condition["values"]}
            case_ids.append(case_id)
            rows.append([float(values[name]) for name in motor_domain.INPUTS])
            references.append([float(v) for v in record["outputs"]["torque_nm"]])
            records.append(record)
    inputs = np.asarray(rows, dtype="<f8")
    targets = np.asarray(references, dtype="<f8")
    if (
        len(solved) != len(case_ids)
        or inputs.shape != (len(case_ids), len(motor_domain.INPUTS))
        or targets.shape != (len(case_ids), motor_domain.ANGLE_STEPS)
        or not np.isfinite(inputs).all()
        or not np.isfinite(targets).all()
    ):
        raise ValueError("development bank tensor differs")
    inputs.setflags(write=False)
    targets.setflags(write=False)
    return {
        "case_ids": tuple(case_ids),
        "inputs": inputs,
        "references": targets,
        "reference_records": records,
        "solver_evidence": _bank_file(challenge_id, "completion"),
    }


def _development_private_roles(challenge_id: str, version: str) -> dict[str, bytes]:
    from carbon.development_session.bundle_construction_worker import _tensors

    bank = development_bank(challenge_id, version)
    return {
        "case_bank": _tensors(inputs=np.array(bank["inputs"])),
        "reference_rows": _canonical(bank["reference_records"]),
        "solver_evidence": bank["solver_evidence"],
    }


def write_public_pack(
    root: Path,
    challenge_id: str,
    version: str,
    *,
    exposed_development_bank: bool = False,
) -> Path:
    """Write the public roles and a draft manifest; returns the manifest path.

    Private roles are HUMAN_INPUT, or, with ``exposed_development_bank``, the
    committed exposed bank for case_bank, reference_rows and solver_evidence.
    ``evaluation_pack.prepare_pack`` seals the draft. The directory must be new
    or empty, so an earlier pack is never overwritten.
    """
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("pack directory must be empty")
    public = {}
    for role, body in sorted(public_roles(challenge_id, version).items()):
        name = f"public/{role}.{'npz' if role == 'train' else 'json'}"
        (root / "public").mkdir(mode=0o700, exist_ok=True)
        (root / name).write_bytes(body)
        public[role] = {"path": name}
    private = {role: UNAVAILABLE for role in PRIVATE_ROLES}
    pack_version = PACK_VERSIONS[challenge_id]
    if exposed_development_bank:
        (root / "private").mkdir(mode=0o700)
        for role, body in _development_private_roles(challenge_id, version).items():
            name = f"private/{role}.{'npz' if role == 'case_bank' else 'json'}"
            (root / name).write_bytes(body)
            private[role] = {"path": name}
        pack_version += "-exposed-bank"
    manifest = {
        "schema": PACK_SCHEMA,
        "challenge": {"id": challenge_id, "version": version},
        "pack_version": pack_version,
        "public": public,
        "private": private,
    }
    path = root / "evaluation-pack.json"
    path.write_bytes(_canonical(manifest))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--exposed-development-bank", action="store_true")
    args = parser.parse_args(argv)
    if args.challenge not in _ROLE_FILES:
        parser.error("no normal-construction pack for this Challenge")
    version = physical_public_train._source(args.challenge)[0].CHALLENGE.version
    path = write_public_pack(
        args.root,
        args.challenge,
        version,
        exposed_development_bank=args.exposed_development_bank,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
