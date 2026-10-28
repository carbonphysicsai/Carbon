#!/usr/bin/env python3
"""Build a pool-graded version's sealed pack in custody (M3; Validator V8_RULINGS section 11).

    python scripts/dev/sealed_exam/pool_pack.py build \
        --challenge electric-motor-magnetics --version 1.5 \
        --batch-dir CUSTODY/motor-grid-batch  --set-dir CUSTODY/phase1-sets/motor-phase1-set \
        --out-dir OUT --inference-image-id sha256:... [--set-digest sha256:...]

``--batch-dir`` holds the Challenge's sealed A batch exactly as the current launch version carries it:
`sealed-batch.json` (document and terminal records; the canonical form is fine, it is canonicalised again here).
``--set-dir`` is the custody Phase-1 set directory (`pool-source-<tid>.json` per target and `sets.json`).

It writes under ``--out-dir``:

- ``pack/``: the complete receiver pack (the canonical bank: sealed cells, private probes and every pool row in
  one seeded interleaving; the pool material rides in the carried batch, never in a public file) with its
  ``sealed-batch.json`` (canonical, pool included) beside the roles;
- ``record.json``: digests and counts only (pack manifest digest, batch fingerprints, set digest, row counts).

Nothing here signs, issues a copy or touches a key: the signed copy is the Lead's `copy_issuance` step on the
canonical pack. The truths stay in custody inside the pack's private files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _writer(challenge):
    if challenge == "electric-motor-magnetics":
        from carbon.scoring import motor_sealed_dual_pack as module
    elif challenge == "f08-ribbed-bracket":
        from carbon.scoring import f08_sealed_dual_pack as module
    elif challenge == "f02":
        from carbon.scoring import f02_sealed_dual_pack as module
    elif challenge == "chip-cold-plate":
        from carbon.scoring import cooling_encoded_dual_pack as module
    else:
        raise SystemExit("no pool pack writer for this Challenge")
    return module


def build(
    *,
    challenge,
    version,
    batch_dir,
    out_dir,
    inference_image_id,
    set_dir=None,
    set_digest=None,
    material=None,
    calibration=False,
    response_reference=None,
):
    """The pool pack and its record. ``material`` (a ready `pool_version` material) replaces ``--set-dir``."""
    from carbon.challenge_kit.version_registry import find
    from carbon.scoring import copy_package, pool_exam, pool_version
    from carbon.scoring import sealed_batch_source as source

    module = _writer(challenge)
    if version not in module.POOL_VERSIONS:
        raise SystemExit(f"{challenge} {version} is not a pool-graded version")
    kit = source._kit(challenge)
    carried = source.read_batch(batch_dir)
    if carried is None:
        raise SystemExit("--batch-dir has no sealed-batch.json")
    document, records = carried
    if "pool" in document:
        raise SystemExit("the A batch already carries a pool: give the plain A batch")
    predecessor = find(challenge, version).predecessor
    # A scoring successor can follow another pool version (Cooling 1.6).
    # The input here is the plain A batch, so its native-grid ancestor supplies
    # the shape/dtype before this version's pool is attached below.
    while source._pool_graded(challenge, predecessor):
        predecessor = find(challenge, predecessor).predecessor
    plain = source._build(challenge, kit, document, records, predecessor)
    if material is None:
        material = pool_version.material_from_set_dir(
            set_dir,
            kind=pool_version.KINDS[challenge],
            version=version,
            input_dtype=plain["inputs"].dtype.str,
            set_digest=set_digest,
        )
    if response_reference is not None:
        # F02 2.5: the solver's local slope per sealed probe group (`f02_response_reference.py`), in the material
        material = pool_version.check_material(
            {**material, pool_version.RESPONSE_REFERENCE: response_reference}
        )
    with_pool = {**document, "pool": material}
    raw, source_fp, canonical_fp = copy_package.canonical_batch(
        challenge, version, with_pool, records
    )
    canonical = json.loads(raw)
    bank = source._build(
        challenge, kit, canonical["document"], canonical["records"], version
    )
    out = Path(out_dir)
    pack_root = out / "pack"
    manifest_path = module.write_sealed_pack(
        pack_root,
        bank,
        version=version,
        inference_image_id=inference_image_id,
        calibration=calibration,
    )
    (pack_root / source.SEALED_BATCH_FILE).write_bytes(raw)
    cohorts = list(bank["cohorts"])
    accounting = pool_version.row_accounting(material, dtype=material["input_dtype"])
    record = {
        "schema": "carbon.pool-pack.record.v1",
        "challenge": challenge,
        "version": version,
        "pack_manifest_sha256": "sha256:"
        + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "batch_source_fingerprint": source_fp,
        "batch_canonical_fingerprint": canonical_fp,
        "set_digest": material["set_digest"],
        "input_dtype": material["input_dtype"],
        "pool_accounting": accounting,
        "rows": {
            "total": len(cohorts),
            "pool": cohorts.count(pool_exam.POOL_COHORT),
            "probes": cohorts.count("probe_response"),
            "cells": len(cohorts)
            - cohorts.count(pool_exam.POOL_COHORT)
            - cohorts.count("probe_response"),
        },
    }
    (out / "record.json").write_text(
        json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("build")
    for flag in ("challenge", "version", "batch-dir", "set-dir", "out-dir"):
        one.add_argument("--" + flag, required=True)
    one.add_argument("--inference-image-id", required=True)
    one.add_argument("--set-digest")
    one.add_argument(
        "--response-reference",
        help="F02 2.5: the f02_response_reference.py build output (JSON), carried in the pool material",
    )
    one.add_argument("--calibration", action="store_true")
    acc = sub.add_parser("accounting")
    for flag in ("challenge", "version", "set-dir", "input-dtype"):
        acc.add_argument("--" + flag, required=True)
    acc.add_argument("--set-digest")
    args = parser.parse_args(argv)
    if args.command == "accounting":
        from carbon.scoring import pool_version

        material = pool_version.material_from_set_dir(
            args.set_dir,
            kind=pool_version.KINDS[args.challenge],
            version=args.version,
            input_dtype=args.input_dtype,
            set_digest=args.set_digest,
        )
        print(
            json.dumps(
                pool_version.row_accounting(material, dtype=args.input_dtype),
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    record = build(
        challenge=args.challenge,
        version=args.version,
        batch_dir=args.batch_dir,
        out_dir=args.out_dir,
        inference_image_id=args.inference_image_id,
        set_dir=args.set_dir,
        set_digest=args.set_digest,
        calibration=args.calibration,
        response_reference=(
            json.loads(Path(args.response_reference).read_text(encoding="utf-8"))
            if args.response_reference
            else None
        ),
    )
    print(json.dumps(record, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
