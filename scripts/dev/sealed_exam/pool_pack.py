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

A NEW version whose pool constants register a coverage plan (``coverage_plan_sha256`` and ``coverage_plan_sums_sha256``,
Validator 11-01 16:55 / 17:15) builds only with ``--coverage-map FILE --coverage-sums FILE``: the class-map document
(`pool_grader.coverage_plan`, in its canonical bytes) and the SHA256SUMS text that lists it. Both are checked against the
registered digests, the map must be listed in the SUMS and must class every target of every set with each set holding
every class, and both ride in the sealed material (`pool_version.COVERAGE_PLAN`, `COVERAGE_PLAN_SUMS`). Any gap refuses
(``refused: <code>``); a version that registers none takes neither and builds exactly as before.

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


def _refuse(code, detail):
    raise SystemExit(f"refused: {code}: {detail}")


def _sha256_hex(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def registered_coverage_plan(challenge, version, *, constants):
    """``(map sha256, SUMS sha256)`` the version's pool constants register, or None when it registers no coverage plan
    (no entry, or neither key: every registered version). Only these two fields are read, so a new version whose other
    constants are still HUMAN_INPUT can be built. A key present as null, HUMAN_INPUT or not 64 hex, or only one of the
    two, refuses (never defaulted)."""
    from carbon.scoring import pool_version

    try:
        document = json.loads(Path(constants).read_bytes())
        if document["schema"] != pool_version.SCHEMA:
            raise ValueError
        entries = document["versions"]
        if type(entries) is not dict:
            raise TypeError
    except (OSError, ValueError, KeyError, TypeError):
        _refuse(
            "pool_constants_unreadable", f"{constants} is not a pool constants file"
        )
    entry = entries.get(f"{challenge} {version}")
    optimizer = entry.get("optimizer") if type(entry) is dict else None
    if type(optimizer) is not dict:
        return None
    keys = ("coverage_plan_sha256", "coverage_plan_sums_sha256")
    present = [key in optimizer for key in keys]
    if not any(present):
        return None
    if not all(present):
        _refuse(
            "coverage_plan_needs_its_map_and_sums_digests",
            "the version registers only one of " + " and ".join(keys),
        )
    values = tuple(optimizer[key] for key in keys)
    if not all(_sha256_hex(value) for value in values):
        _refuse(
            "coverage_plan_digest_not_registered",
            "each registered coverage-plan digest must be 64 hex (null and HUMAN_INPUT refuse)",
        )
    return values


def attach_coverage_plan(
    material, *, challenge, version, coverage_map_raw, coverage_sums_raw, constants
):
    """``material`` with the version's class map and SUMS (`pool_version.COVERAGE_PLAN`, `COVERAGE_PLAN_SUMS`), or
    ``material`` itself for a version that registers no coverage plan (it takes neither input). Refuses
    (``SystemExit("refused: <code>: ...")``) as the grader would (`pool_exam.attach_coverage_plan`), at build time: an
    input missing, a digest that is not the registered one, a map not in its canonical bytes or not listed in the SUMS,
    a target of a set missing from the map, a set without every class. The class names' geometric-v1 check stays the
    grader's (it refuses until the receipted rule is in the repository)."""
    from carbon.scoring import pool_grader, pool_version

    if any(
        key in material
        for key in (pool_version.COVERAGE_PLAN, pool_version.COVERAGE_PLAN_SUMS)
    ):
        _refuse(
            "coverage_plan_already_in_the_material",
            "the class map and its SUMS enter only through --coverage-map / --coverage-sums",
        )
    registered = registered_coverage_plan(challenge, version, constants=constants)
    if registered is None:
        if coverage_map_raw is not None or coverage_sums_raw is not None:
            _refuse(
                "coverage_plan_not_registered",
                f"{challenge} {version} registers no coverage plan: give no --coverage-map / --coverage-sums",
            )
        return material
    map_sha256, sums_sha256 = registered
    if coverage_map_raw is None or coverage_sums_raw is None:
        _refuse(
            "coverage_plan_inputs_missing",
            f"{challenge} {version} registers a coverage plan: --coverage-map and --coverage-sums are required",
        )
    if hashlib.sha256(coverage_map_raw).hexdigest() != map_sha256:
        _refuse(
            "coverage_plan_sha256_mismatch",
            "--coverage-map is not the registered class-map document",
        )
    if hashlib.sha256(coverage_sums_raw).hexdigest() != sums_sha256:
        _refuse(
            "coverage_plan_sums_sha256_mismatch",
            "--coverage-sums is not the registered SHA256SUMS",
        )
    try:
        document = json.loads(coverage_map_raw.decode("utf-8"))
        sums = coverage_sums_raw.decode("utf-8")
        plan = pool_grader.coverage_plan(document)
        listed = pool_grader.sums_list(sums, plan.sha256)
    except (UnicodeDecodeError, ValueError, pool_grader.PoolRefused):
        _refuse(
            "coverage_plan_malformed",
            "the class map or its SUMS does not parse as a coverage plan",
        )
    if pool_grader.coverage_plan_bytes(document) != coverage_map_raw:
        _refuse(
            "coverage_plan_not_canonical",
            "the class-map file must be its document's canonical bytes (the bytes the registered sha256 names)",
        )
    if not listed:
        _refuse(
            "coverage_plan_not_listed_in_its_sums",
            "the SUMS does not list the class map",
        )
    for number, group in enumerate(material["sets"]):
        targets = [pool_grader.load_pool(pool).target_id for pool in group]
        try:
            classes = {plan.class_of(target_id) for target_id in targets}
        except pool_grader.PoolRefused:
            _refuse(
                "target_not_in_the_coverage_plan",
                f"set {number} holds a target the class map does not class",
            )
        if classes != set(plan.classes):
            _refuse(
                "set_missing_a_registered_class",
                f"set {number} does not hold every class of the map",
            )
    return pool_version.check_material(
        {
            **material,
            pool_version.COVERAGE_PLAN: document,
            pool_version.COVERAGE_PLAN_SUMS: sums,
        }
    )


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
    baseline_binding_raw=None,
    calibration_pack_root=None,
    baseline_floor_total=None,
    coverage_map_raw=None,
    coverage_sums_raw=None,
    constants=None,
):
    """The pool pack and its record. ``material`` (a ready `pool_version` material) replaces ``--set-dir``.

    ``coverage_map_raw`` / ``coverage_sums_raw`` (bytes) are a new version's class map and its SUMS, required exactly when
    the pool constants (``constants``, default `pool_version.CONSTANTS`) register a coverage plan (`attach_coverage_plan`).

    The leg minimums are the registered baseline's own graded legs (two builds): ``calibration`` writes the
    minimum-free calibration pack; ``baseline_binding_raw`` (the baseline's retained binding, graded under that
    calibration pack) with ``calibration_pack_root`` writes the judge pack with those minimums. Neither: the adapter's own
    (Motor, F08 and F02 pool versions carry none; Cooling's in-pack baseline sets them, and from 1.7 it is graded through
    ``pool_exam.measure_pool`` like a miner, see ``cooling_pool_baseline_dual_pack``).
    """
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
    material = attach_coverage_plan(
        material,
        challenge=challenge,
        version=version,
        coverage_map_raw=coverage_map_raw,
        coverage_sums_raw=coverage_sums_raw,
        constants=pool_version.CONSTANTS if constants is None else constants,
    )
    with_pool = {**document, "pool": material}
    raw, source_fp, canonical_fp = copy_package.canonical_batch(
        challenge, version, with_pool, records
    )
    canonical = json.loads(raw)
    bank = source._build(
        challenge, kit, canonical["document"], canonical["records"], version
    )
    if (baseline_binding_raw is None) != (calibration_pack_root is None):
        raise SystemExit("--baseline-binding and --calibration-pack go together")
    if calibration and baseline_binding_raw is not None:
        raise SystemExit("a calibration pack takes no baseline binding")
    out = Path(out_dir)
    pack_root = out / "pack"
    minimums = (
        {
            "baseline_binding_raw": baseline_binding_raw,
            "calibration_pack_root": Path(calibration_pack_root),
        }
        if baseline_binding_raw is not None
        else {}
    )
    manifest_path = module.write_sealed_pack(
        pack_root,
        bank,
        version=version,
        inference_image_id=inference_image_id,
        calibration=calibration,
        **minimums,
        # the crown floor (option B), a measured number; only versions whose writer registers one take it (Motor 1.6)
        **(
            {"baseline_floor_total": baseline_floor_total}
            if baseline_floor_total is not None
            else {}
        ),
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
    if pool_version.COVERAGE_PLAN in material:
        # digests only (the map names targets and stays in the sealed material)
        record["coverage_plan_sha256"] = hashlib.sha256(coverage_map_raw).hexdigest()
        record["coverage_plan_sums_sha256"] = hashlib.sha256(
            coverage_sums_raw
        ).hexdigest()
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
    one.add_argument(
        "--baseline-binding",
        type=Path,
        help="the baseline's retained binding, graded under the calibration pack (needs --calibration-pack)",
    )
    one.add_argument(
        "--calibration-pack",
        type=Path,
        help="the calibration pack directory the baseline was graded under (its `pack/`)",
    )
    one.add_argument(
        "--baseline-floor-total",
        type=float,
        help="Motor 1.6: the crown floor (a MEASURED number: the best catalog entry's official total), carried in the score pack",
    )
    one.add_argument(
        "--coverage-map",
        type=Path,
        help="a version registering a coverage plan: its class-map document (canonical bytes; needs --coverage-sums)",
    )
    one.add_argument(
        "--coverage-sums",
        type=Path,
        help="the SHA256SUMS that lists the class map (its registered coverage_plan_sums_sha256)",
    )
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
        baseline_binding_raw=(
            args.baseline_binding.read_bytes() if args.baseline_binding else None
        ),
        calibration_pack_root=args.calibration_pack,
        baseline_floor_total=args.baseline_floor_total,
        response_reference=(
            json.loads(Path(args.response_reference).read_text(encoding="utf-8"))
            if args.response_reference
            else None
        ),
        coverage_map_raw=(
            args.coverage_map.read_bytes() if args.coverage_map else None
        ),
        coverage_sums_raw=(
            args.coverage_sums.read_bytes() if args.coverage_sums else None
        ),
    )
    print(json.dumps(record, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
