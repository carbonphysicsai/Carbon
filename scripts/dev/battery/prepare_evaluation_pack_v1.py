#!/usr/bin/env python3
"""Prepare an operator-owned Battery v1 public-material pack draft.

The normal receiver seals this draft at admission. This command neither reads
the hidden bank nor supplies reference, Design, or Score Pack authority.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from carbon.battery import challenge
from carbon.battery.construction_bundle_material import (
    PHYSICS_PATH,
    bundle_material,
)
from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    UNAVAILABLE,
    prepare_pack,
)
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical

PACK_VERSION = "battery-v1-public-material-development-1"
DRAFT_NAME = "evaluation-pack.json"


def materialize_draft(operator_root: Path, *, repository_root: Path = ROOT):
    """Pin the served public contract; leave all scoring material unavailable."""
    repository_root = Path(repository_root).resolve()
    operator_root = Path(operator_root).resolve()
    if operator_root.is_relative_to(repository_root):
        raise ValueError("operator pack directory must be outside the repository")
    operator_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not operator_root.is_dir() or (
        os.name == "posix" and operator_root.stat().st_mode & 0o077
    ):
        raise ValueError("owner-only operator pack directory required")

    material = bundle_material(repository_root)
    key = material["challenge_key"]
    if key != challenge.CHALLENGE:
        raise ValueError("Battery source identity changed")
    public = {role: UNAVAILABLE for role in PUBLIC_ROLES}
    public.update(
        construction_kit={"inline": material["construction_kit"]},
        interface={"inline": material["interface_document"]},
        train={"path": challenge.TRAIN_V1_PATH},
        physics_contract={"path": PHYSICS_PATH},
    )
    document = {
        "schema": SCHEMA,
        "challenge": {"id": key.challenge_id, "version": key.version},
        "pack_version": PACK_VERSION,
        "public": public,
        "private": {
            **{role: UNAVAILABLE for role in PRIVATE_ROLES},
            "source_registration": UNAVAILABLE,
        },
    }
    write_once(operator_root / DRAFT_NAME, canonical(document))
    prepared = prepare_pack(
        operator_root,
        DRAFT_NAME,
        public_root=repository_root,
        private_root=operator_root,
        challenge_id=key.challenge_id,
        challenge_version=key.version,
    )
    prepared.snapshot.verify_available(repository_root, operator_root)
    return prepared


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--operator-root",
        type=Path,
        required=True,
        help="owner-only directory outside the repository for the editable draft",
    )
    args = parser.parse_args(argv)
    prepared = materialize_draft(args.operator_root)
    print(
        json.dumps(
            {
                "challenge": {
                    "id": prepared.snapshot.challenge_id,
                    "version": prepared.snapshot.challenge_version,
                },
                "status": "DEVELOPMENT_PUBLIC_MATERIAL_ONLY",
                "missing_roles": prepared.snapshot.missing_roles(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
