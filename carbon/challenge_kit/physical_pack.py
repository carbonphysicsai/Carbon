"""Public roles of the normal-construction DEVELOPMENT evaluation pack.

The receiver binds an opted-in pack to the construction material at every use:
its construction kit, interface and physics contract must equal the material's
documents and its train role must equal the material's TRAIN bytes. This module
builds those roles from the same source-owned functions the construction path
uses (``physical_public``), plus exact reviewed contract bytes, so the two can
only agree. Private roles stay HUMAN_INPUT: binding a case bank, references,
solver evidence or a score pack is a custody step this module never performs.

    python -m carbon.challenge_kit.physical_pack ROOT --challenge electric-motor-magnetics
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from carbon.motor import challenge as motor

from . import physical_public, physical_public_train

_DATA = Path(__file__).with_name("data")
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


def write_public_pack(root: Path, challenge_id: str, version: str) -> Path:
    """Write the public roles and a draft manifest, private roles HUMAN_INPUT.

    Returns the manifest path; ``evaluation_pack.prepare_pack`` seals it. The
    directory must be new or empty, so an earlier pack is never overwritten.
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
    manifest = {
        "schema": PACK_SCHEMA,
        "challenge": {"id": challenge_id, "version": version},
        "pack_version": PACK_VERSIONS[challenge_id],
        "public": public,
        "private": {role: UNAVAILABLE for role in PRIVATE_ROLES},
    }
    path = root / "evaluation-pack.json"
    path.write_bytes(_canonical(manifest))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--challenge", required=True)
    args = parser.parse_args(argv)
    if args.challenge not in _ROLE_FILES:
        parser.error("no normal-construction pack for this Challenge")
    version = physical_public_train._source(args.challenge)[0].CHALLENGE.version
    path = write_public_pack(args.root, args.challenge, version)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
