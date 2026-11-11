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

Nothing here signs or issues a copy: the signed copy is the Lead's `copy_issuance` step on the canonical pack. The
truths stay in custody inside the pack's private files.

A MENU-D version (its pool_constants registration carries a ``menu`` block) also takes:

- ``--menu-dir``: design-optimum's sealed menus, ``<task>.menu.json`` (carbon.d-menu.v1) + ``<task>.problem.json``
  per task, in its own ``<output>@<duty>`` naming. They are renamed to the door's ``<duty>/<output>``
  (`pool_menu.menu_material`), checked by the door's own loader, and ride in the pool material (``menu``), so every
  (menu design x duty) becomes a plain pool row of the bank. ``menu-shas`` prints the record shas to register FIRST
  (the build refuses unless the registration names exactly these shas).
- ``--crown-key-file``: the validator host's K_crown file (owner-private), read only to derive the menu draw and
  re-check keys for the in-pack baseline's own graded measure; a fresh run of the baseline answers the keyed re-check
  subset (Carbon's model, never a miner's). Nothing is written from it.
"""

from __future__ import annotations

import argparse
import contextlib
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


#: The sealed documents a version's raw registration asks for: (material key, CLI flag, the registration leaf that
#: requires it, how the file is read). A leaf present with any value but null (HUMAN_INPUT counts: a registration still
#: to fill) requires the document; a document whose leaf is absent or null refuses. These are the grader's own rules
#: (pool_exam.attach_coverage_plan / attach_physics / attach_variant_starts and the cells attach under it), checked
#: here before a pack is written, so a 1.8 pack can no longer leave them out (mc-exam-B, Wed 11 Nov 2026, blocker B2).
SEALED_DOCUMENTS = (
    ("coverage_plan", "coverage-plan", ("optimizer", "coverage_plan_sha256"), "json"),
    (
        "coverage_plan_sums",
        "coverage-plan-sums",
        ("optimizer", "coverage_plan_sums_sha256"),
        "text",
    ),
    ("scoring_cells", "scoring-cells", ("physics",), "json"),
    ("in_range_cases", "in-range-cases", ("physics", "in_range_cases_sha256"), "json"),
    ("variant_starts", "variant-starts", ("optimizer", "variant_rule"), "json"),
    ("region", "region", ("physics", "region_sha256"), "json"),
)


def _registered_leaf(entry, path):
    value = entry
    for key in path:
        if type(value) is not dict or key not in value:
            return False
        value = value[key]
    return value is not None


def read_document(path, kind):
    """One sealed document file: exact text (the plan's SHA256SUMS) or JSON."""
    text = Path(path).read_text(encoding="utf-8")
    return text if kind == "text" else json.loads(text)


def _with_documents(challenge, version, material, documents, *, constants=None):
    """``material`` with the version's registered sealed documents added (``documents``: material key -> document or
    None), or SystemExit naming the flag. Reads only the raw registration (as crown_hold does).
    """
    from carbon.scoring import pool_version

    keys = {
        pool_version.COVERAGE_PLAN,
        pool_version.COVERAGE_PLAN_SUMS,
        pool_version.SCORING_CELLS,
        pool_version.IN_RANGE_CASES,
        pool_version.VARIANT_STARTS,
        pool_version.REGION,
    }
    if keys != {row[0] for row in SEALED_DOCUMENTS}:
        raise SystemExit(
            "pool_pack's sealed-document table differs from pool_version's material keys"
        )
    documents = dict(documents or {})
    unknown = set(documents) - keys
    if unknown:
        raise SystemExit(f"unknown sealed document(s): {sorted(unknown)}")
    try:
        raw = json.loads(Path(constants or pool_version.CONSTANTS).read_bytes())
        entry = raw["versions"].get(f"{challenge} {version}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise SystemExit("the pool constants registration is unreadable") from None
    entry = entry if type(entry) is dict else {}
    added = dict(material)
    for key, flag, leaf, _kind in SEALED_DOCUMENTS:
        given = documents.get(key) is not None
        required = _registered_leaf(entry, leaf)
        if required and not given:
            raise SystemExit(
                f"{challenge} {version} registers {'.'.join(leaf)}: give --{flag}"
            )
        if given and not required:
            raise SystemExit(
                f"{challenge} {version} does not register {'.'.join(leaf)}: --{flag} refused"
            )
        if given:
            added[key] = documents[key]
    return pool_version.check_material(added)


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
    menu_dir=None,
    crown_key_file=None,
    documents=None,
):
    """The pool pack and its record. ``material`` (a ready `pool_version` material) replaces ``--set-dir``.

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
    material = _with_documents(challenge, version, material, documents)
    menu_shas = None
    if menu_dir is not None:
        material, menu_shas = _with_menu(challenge, version, material, menu_dir)
    else:
        from carbon.challenge_validator.crown_hold import menu_registered

        # the raw registration's `menu` key (no other constant read): a menu version never builds without its menu
        if menu_registered(challenge, version):
            raise SystemExit(f"{challenge} {version} registers a menu: give --menu-dir")
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
    with _menu_keys(module, menu_shas, crown_key_file):
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
    accounting = pool_version.row_accounting(
        material, dtype=material["input_dtype"], challenge=challenge
    )
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
        # a menu version: the registered record shas (shas and counts only, never a menu value)
        **(
            {}
            if menu_shas is None
            else {"menu": {"tasks": len(menu_shas), "records_sha256": menu_shas}}
        ),
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


def _menu_pairs(menu_dir):
    """``[(problem_doc, record_doc)]`` of a menu directory: one ``<task>.problem.json`` per ``<task>.menu.json``."""
    folder = Path(menu_dir)
    records = sorted(folder.glob("*.menu.json"))
    if not records:
        raise SystemExit("--menu-dir has no <task>.menu.json")
    pairs = []
    for path in records:
        stem = path.name[: -len(".menu.json")]
        problem = folder / f"{stem}.problem.json"
        if not problem.is_file():
            raise SystemExit(f"--menu-dir: {stem}.menu.json has no {stem}.problem.json")
        pairs.append(
            (
                json.loads(problem.read_text(encoding="utf-8")),
                json.loads(path.read_text(encoding="utf-8")),
            )
        )
    extra = {p.name for p in folder.glob("*.problem.json")} - {
        r.name[: -len(".menu.json")] + ".problem.json" for r in records
    }
    if extra:
        raise SystemExit(f"--menu-dir: problem files with no menu: {sorted(extra)}")
    return pairs


def menu_shas(challenge, version, menu_dir):
    """The door-form record shas of a menu directory (what pool_constants registers), shas only."""
    from carbon.scoring import pool_adapters, pool_menu, pool_version

    binding = pool_adapters.official_binding(pool_version.KINDS[challenge], version)
    _material, shas = pool_menu.menu_material(
        _menu_pairs(menu_dir),
        input_names=list(binding.input_names),
        design_names=list(binding.design_names),
    )
    return shas


def _with_menu(challenge, version, material, menu_dir):
    """The pool material with the sealed menu, refused unless the registration names exactly its record shas."""
    from carbon.scoring import pool_exam, pool_menu, pool_version

    try:
        menu, shas = pool_menu.menu_material(
            _menu_pairs(menu_dir),
            input_names=material["input_names"],
            design_names=material["design_names"],
        )
        rule = pool_version.registered_menu(challenge, version)
    except (pool_exam.ExamRefused, pool_version.PoolConstantsNotRegistered) as exc:
        raise SystemExit(f"menu refused: {getattr(exc, 'code', exc)}") from exc
    if rule is None or dict(rule.records_sha256) != shas:
        raise SystemExit(
            "register these menu record shas in pool_constants first: "
            + json.dumps(shas, sort_keys=True)
        )
    return pool_version.check_material({**material, pool_version.MENU: menu}), shas


def _baseline_recheck(module):
    """The in-pack baseline's re-check source: a FRESH run of the writer's own ``pool_baseline`` on the keyed subset."""
    import inspect

    baseline = getattr(module, "pool_baseline", None)
    if baseline is None:
        raise SystemExit(
            "a menu version's writer has no pool_baseline to answer the re-check"
        )
    takes_names = "names" in inspect.signature(baseline).parameters

    def recheck(positions, bank_rows, names):
        rows = [bank_rows[i] for i in positions]
        outputs, _seconds = baseline(
            bank_rows=rows,
            sample_count=1,
            **({"names": names} if takes_names else {}),
        )
        return [list(row) for row in outputs]

    return recheck


@contextlib.contextmanager
def _menu_keys(module, menu_shas, crown_key_file):
    """For a menu version only: the draw + re-check keys from K_crown and the baseline's fresh re-check, staged for the
    in-pack baseline's graded measure; both are cleared on exit. Nothing for any other version.
    """
    if menu_shas is None:
        yield
        return
    if crown_key_file is None:
        raise SystemExit(
            "a menu version's pack needs --crown-key-file (the in-pack baseline is graded on the menu)"
        )
    from carbon.challenge_validator.crown_average_host import read_crown_key
    from carbon.scoring import pool_menu

    pool_menu.install_key(read_crown_key(str(Path(crown_key_file).resolve())))
    try:
        with pool_menu.staged_rowcheck(_baseline_recheck(module)):
            yield
    finally:
        pool_menu.install_key(None)


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
        "--menu-dir",
        type=Path,
        help="a menu-D version: design-optimum's sealed <task>.menu.json + <task>.problem.json",
    )
    one.add_argument(
        "--crown-key-file",
        type=Path,
        help="a menu-D version: the validator host's K_crown file (owner-private; keys derived, nothing written)",
    )
    for key, flag, leaf, kind in SEALED_DOCUMENTS:
        one.add_argument(
            "--" + flag,
            type=Path,
            help=f"required when the version registers {'.'.join(leaf)} ({kind}); carried in the sealed material",
        )
    shas = sub.add_parser("menu-shas")
    for flag in ("challenge", "version", "menu-dir"):
        shas.add_argument("--" + flag, required=True)
    acc = sub.add_parser("accounting")
    for flag in ("challenge", "version", "set-dir", "input-dtype"):
        acc.add_argument("--" + flag, required=True)
    acc.add_argument("--set-digest")
    args = parser.parse_args(argv)
    if args.command == "menu-shas":
        print(
            json.dumps(
                menu_shas(args.challenge, args.version, args.menu_dir),
                sort_keys=True,
                indent=2,
            )
        )
        return 0
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
        menu_dir=args.menu_dir,
        crown_key_file=args.crown_key_file,
        documents={
            key: read_document(getattr(args, flag.replace("-", "_")), kind)
            for key, flag, _leaf, kind in SEALED_DOCUMENTS
            if getattr(args, flag.replace("-", "_")) is not None
        },
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
