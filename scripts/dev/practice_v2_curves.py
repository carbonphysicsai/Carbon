#!/usr/bin/env python3
"""Practice-v2 leg values for every eligible catalog entry, for the scale curves.

DEVELOPMENT, $0 of Carbon money: it builds and queries the SAME way a miner's
catalog practice does (Launchpad's `DirectPractice`, `MotorCatalogPractice`,
`CoolingCatalogPractice`), so each result is the exam's own v2 grader run on the
public practice grid (`practice_dual.feedback_v2`): aggregate leg values and failed
gate names, never a per-case value. A floor row (`ctrl.train_mean`, no build) is
written per Challenge. Nothing here is a sealed grade, a minimum or a registered
value; the output carries that banner.

Run on a CPU box that has Docker, the pinned PyTorch CPU worker image and the
catalog children installed (the Test Lead's pair-build VM):

    python scripts/dev/practice_v2_curves.py --out-dir OUT \
        --parent-identity /path/to/torch-cpu-worker-image-identity.json \
        --cache-root /path/to/library-cache

    --list            print the candidate list and exit (no Docker needed)
    --only F08        one Challenge (f08|f02|motor|cooling), or F08:CATALOG_ID
    --ids-file F      only the catalog ids listed in F (one per line)
    --floor-only      write only the floor rows ($0, no Docker)

One JSON per candidate under OUT/<kind>-<version>/ (resumable: an existing result
is skipped; a failure is recorded with its reason code, never retried silently),
and OUT/curves_input.json joining them for the curve step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "carbon.practice-v2-curves-input.v1"
BANNER = (
    "DEVELOPMENT practice-v2 leg values on the public practice grid, from the exam's "
    "own v2 grader. Not sealed grades, not minimums; no registered value changed."
)
#: kind -> (challenge id, the launch version whose practice grid and catalog it uses)
TARGETS = {
    "f08": ("f08-ribbed-bracket", "1.5"),
    "f02": ("f02", "2.4"),
    "motor": ("electric-motor-magnetics", "1.5"),
    "cooling": ("chip-cold-plate", "1.4"),
}


def candidates(kind):
    """Catalog ids the version offers (the entries a miner's practice can run)."""
    from carbon.backbone_catalog import listing

    challenge_id, version = TARGETS[kind]
    return sorted(item["catalog_id"] for item in listing.entries(challenge_id, version))


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def train_mean_row(train_raw, adapter):
    """The floor's one row: the public TRAIN mean of the outputs, in the space the
    grader measures (`calibration_grade._train_mean`'s rule; a test pins them equal)."""
    import io

    import numpy as np

    native = getattr(adapter, "_native_train", None)
    if native is not None:
        train_raw = native()
    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        targets = np.asarray(data["targets"], dtype=float)
    mean = targets.mean(axis=0)
    if native is not None:
        from carbon.cold_plate import output_encoding

        mean = output_encoding.encode_targets(mean[None, :])[0]
    return [float(v) for v in mean]


def floor_row(kind):
    """The floor: every row is the public TRAIN mean of the outputs, graded by
    the same v2 grader (no build, no Docker)."""
    from carbon.challenge_kit import physical_pack
    from carbon.scoring import practice_dual, practice_grid

    _challenge_id, version = TARGETS[kind]
    adapter = practice_grid.adapter(kind, version)
    public = physical_pack.public_roles(adapter.CHALLENGE, version)
    mean = train_mean_row(public["train"], adapter)

    def predict(cases):
        return [list(mean) for _ in cases]

    return practice_dual.feedback_v2(kind, version, predict)


def make_ledger(kind, args):
    """A frozen, uncapped development ledger for one Challenge's builds (the
    calibration store's shape: no grant, owner `curves`)."""
    from carbon.development_session.research_ledger import VERSION, CampaignLedger

    _challenge_id, version = TARGETS[kind]
    work = Path(args.out_dir) / ".work" / f"{kind}-{version}"
    work.mkdir(parents=True, exist_ok=True)
    ledger = CampaignLedger(work, clock=lambda: int(time.time()))
    ledger.freeze(
        {
            "schema": VERSION,
            "campaign_id": "practice-v2-curves",
            "implementation": "practice_v2_curves",
            "objective": "practice-v2-curves-only",
            "sampling": "none",
            "control": "practice-v2-curves-only",
            "selection": "practice-v2-curves-only",
            "replica_policy": "none",
            "provider": "none",
            "owner": "curves",
        }
    )
    return ledger


def practice_for(kind, args):
    """The version's catalog practice, over a real ledger and parent."""
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    _challenge_id, version = TARGETS[kind]
    ledger = make_ledger(kind, args)
    common = {
        "ledger": ledger,
        "owner": "curves",
        "parent": load_image_identity(Path(args.parent_identity)),
        "cache_root": Path(args.cache_root),
        "version": version,
        "root": ROOT,
    }
    if kind == "f08":
        from carbon.f08.catalog_practice import F08DirectPractice

        return F08DirectPractice(**common)
    if kind == "f02":
        from carbon.f02.catalog_practice import F02DirectPractice

        return F02DirectPractice(**common)
    if kind == "motor":
        from carbon.motor.catalog_practice import MotorCatalogPractice

        return MotorCatalogPractice(**common)
    from carbon.cold_plate.catalog_practice import CoolingCatalogPractice

    return CoolingCatalogPractice(**common)


def recipe_for(kind, catalog_id):
    _challenge_id, version = TARGETS[kind]
    if kind == "motor":
        from carbon.challenge_registry.motor import catalog_recipe

        return catalog_recipe(catalog_id, version)
    if kind == "cooling":
        from carbon.challenge_registry.cold_plate import catalog_recipe

        return catalog_recipe(catalog_id, version=version)
    from carbon.challenge_registry.direct import catalog_recipe
    from carbon.direct_campaign.spec import SPECS

    return catalog_recipe(SPECS[_challenge_id], catalog_id, version=version)


def one_result(kind, catalog_id, practice):
    """One candidate: its v2 practice document, or the reason it did not score."""
    started = time.time()
    record = {
        "kind": kind,
        "challenge": dict(zip(("id", "version"), TARGETS[kind])),
        "catalog_id": catalog_id,
    }
    try:
        outcome = practice(
            f"curves-{kind}-{hashlib.sha256(catalog_id.encode()).hexdigest()[:12]}",
            recipe_for(kind, catalog_id),
        )
        record["practice_dual"] = outcome["practice_dual"]
        record["state_digest"] = (outcome.get("fit") or {}).get("state_digest")
        if outcome.get("backend") is not None:
            record["backend"] = outcome["backend"]
        record["status"] = (
            "SCORED" if record["practice_dual"].get("available") else "UNAVAILABLE"
        )
    # A candidate that fails is a row in the table, not a stop.
    except Exception as exc:  # noqa: BLE001
        record["status"] = "BUILD_FAILED"
        record["reason_code"] = getattr(exc, "code", None) or type(exc).__name__
        record["tail"] = str(exc)[-300:]
    record["wall_seconds"] = round(time.time() - started, 1)
    return record


def run(args, *, practice_factory=practice_for):
    out = Path(args.out_dir)
    kinds = [
        k for k in TARGETS if args.only is None or args.only.split(":")[0].lower() == k
    ]
    chosen = args.only.split(":")[1] if args.only and ":" in args.only else None
    listed = (
        {
            line.strip()
            for line in Path(args.ids_file).read_text().splitlines()
            if line.strip()
        }
        if getattr(args, "ids_file", None)
        else None
    )
    written = []
    for kind in kinds:
        directory = out / f"{kind}-{TARGETS[kind][1]}"
        directory.mkdir(parents=True, exist_ok=True)
        floor = directory / "_floor.json"
        if not floor.exists():
            floor.write_bytes(
                _canonical(
                    {
                        "kind": kind,
                        "catalog_id": "ctrl.train_mean",
                        "practice_dual": floor_row(kind),
                    }
                )
            )
        written.append(floor)
        if args.floor_only:
            continue
        practice = practice_factory(kind, args)
        for catalog_id in candidates(kind):
            if chosen is not None and catalog_id != chosen:
                continue
            if listed is not None and catalog_id not in listed:
                continue
            target = directory / (catalog_id.replace("/", "_") + ".json")
            if not target.exists():
                target.write_bytes(_canonical(one_result(kind, catalog_id, practice)))
            written.append(target)
    rows = [json.loads(p.read_bytes()) for p in written]
    joined = {"schema": SCHEMA, "banner": BANNER, "rows": rows}
    (out / "curves_input.json").write_bytes(
        json.dumps(joined, indent=1, sort_keys=True).encode() + b"\n"
    )
    return joined


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir")
    parser.add_argument("--parent-identity")
    parser.add_argument("--cache-root")
    parser.add_argument("--only")
    parser.add_argument("--ids-file")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--floor-only", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    if args.list:
        print(json.dumps({k: candidates(k) for k in TARGETS}, indent=1))
        return 0
    if not args.out_dir or (
        not args.floor_only and not (args.parent_identity and args.cache_root)
    ):
        parser.error(
            "--out-dir, and --parent-identity and --cache-root unless --floor-only"
        )
    joined = run(args)
    scored = sum(r.get("status") == "SCORED" for r in joined["rows"])
    print(json.dumps({"rows": len(joined["rows"]), "scored": scored}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
