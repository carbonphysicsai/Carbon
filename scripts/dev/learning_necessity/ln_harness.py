#!/usr/bin/env python3
"""LN-HARNESS-01: the UP-side training harness of the learning-necessity gate (LEARNING_NECESSITY_GATE_SPEC_20261101 §2).

For one Challenge version it trains the contender catalog entries on the version's PUBLIC TRAIN only and exports each
contender's predictions on the probe INPUTS. It never reads a truth: there is no truth argument, and the export holds
predictions and the probe inputs' digest only. Scoring is the version's own ``measure_pool`` in custody, elsewhere.

What it enforces (Validator conditions, "Validator rulings" in the spec):

- the grid (the explicit ~8 settings per architecture, k, fold seed, seed, contenders) lives in ONE registered file; the run
  refuses unless the grid's canonical sha256 equals the digest it is given, and it records that digest;
- every setting, and the default recipe, is checked by the entry's own settings schema (``backbone_catalog.settings
  .resolve``): a knob outside the catalog's vocabulary refuses the whole run before anything trains;
- every fit is timed against the version's registered rebuild wall (``version_registry.entry(...).rebuild_wall_seconds``);
  a setting with a fit over it is recorded OVER_LIMIT and cannot be selected (soft check: the process is not killed, the
  pod's own rent recipe bounds the whole run);
- selection is k-fold on TRAIN, folds fixed by the recorded seed; the default recipe and the selected setting are then
  refit on all TRAIN and both predict the probe inputs;
- a contender absent from the version's listing is replaced by the next candidate of its family, and the substitution is
  recorded;
- the record names the host and driver (rented-GPU runs are an existence proof, not bit-identical).

Aggregates only: the tuned recipes stay private to Carbon (the record is CARBON_PRIVATE, never a miner hint).

    python ln_harness.py digest GRID.json
    python ln_harness.py run --grid GRID.json --grid-digest sha256:... --version 2.5 --probe-inputs probe.npy --out OUT
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import math
import platform
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

GRID_SCHEMA = "carbon.ln-grid.v1"
RECORD_SCHEMA = "carbon.ln-harness-record.v1"
GRID_KEYS = {"schema", "status", "challenge", "k", "fold_seed", "seed", "contenders"}
CONTENDER_KEYS = {"role", "candidates", "settings"}
SETTING_KEYS = {"configuration", "train_use"}


class Refused(ValueError):
    """The run cannot start (or finish) honestly; the message is a typed code."""


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


# ---------------------------------------------------------------- the registered grid


def load_grid(path, expected_digest):
    """The grid document, only when its canonical digest is the one registered. A grid is digested BEFORE any training."""
    if not expected_digest:
        raise Refused("grid_digest_required")
    grid = json.loads(Path(path).read_text(encoding="utf-8"))
    if digest(grid) != expected_digest:
        raise Refused("grid_digest_mismatch")
    if (
        not isinstance(grid, dict)
        or set(grid) != GRID_KEYS
        or grid["schema"] != GRID_SCHEMA
    ):
        raise Refused("grid_shape_invalid")
    if not (type(grid["k"]) is int and grid["k"] >= 2):
        raise Refused("grid_k_invalid")
    for name in ("fold_seed", "seed"):
        if type(grid[name]) is not int or grid[name] < 0:
            raise Refused(f"grid_{name}_invalid")
    contenders = grid["contenders"]
    if not isinstance(contenders, list) or not contenders:
        raise Refused("grid_contenders_invalid")
    for each in contenders:
        if not isinstance(each, dict) or set(each) != CONTENDER_KEYS:
            raise Refused("grid_contender_invalid")
        if not (
            each["candidates"] and all(isinstance(c, str) for c in each["candidates"])
        ):
            raise Refused("grid_contender_invalid")
        settings = each["settings"]
        if settings is not None and not (
            isinstance(settings, list)
            and settings
            and all(isinstance(s, dict) and set(s) == SETTING_KEYS for s in settings)
        ):
            raise Refused("grid_settings_invalid")
    return grid


# ---------------------------------------------------------------- the version's own material


def load_train(challenge_id, version):
    """The version's PUBLIC TRAIN ``(inputs, targets)``. F02 is the first target."""
    if challenge_id == "f02":
        from carbon.challenge_kit import f02_train

        data = f02_train.load_public_train(version)
        return data["inputs"], data["targets"]
    raise Refused("train_not_registered_for_this_challenge")


def resolve_entries(grid, challenge_id, version):
    """``[(contender, item, substituted_from)]``: each contender's first candidate the version lists; refuses when none."""
    from carbon.backbone_catalog import listing

    offered = {e["catalog_id"]: e for e in listing.entries(challenge_id, version)}
    out = []
    for each in grid["contenders"]:
        for index, candidate in enumerate(each["candidates"]):
            if candidate in offered:
                out.append(
                    (each, offered[candidate], each["candidates"][0] if index else None)
                )
                break
        else:
            raise Refused("contender_not_offered_by_the_version:" + each["role"])
    return out


def check_settings(contender, item):
    """Every grid setting and the default recipe through the entry's own settings schema (a catalog refusal re-raised)."""
    from carbon.backbone_catalog import settings
    from carbon.backbone_catalog.entries import CatalogRefused

    try:
        settings.resolve(item, {}, {})
        resolved = [
            settings.resolve(item, dict(s["configuration"]), dict(s["train_use"]))
            for s in (contender["settings"] or [])
        ]
    except CatalogRefused as refusal:
        raise Refused(
            f"setting_outside_the_catalog_vocabulary:{item['catalog_id']}:{refusal}"
        ) from refusal
    return resolved


def rebuild_wall_seconds(challenge_id, version):
    from carbon.challenge_kit import version_registry

    wall = version_registry.entry(challenge_id, version).rebuild_wall_seconds
    if not (type(wall) in (int, float) and wall > 0):
        raise Refused("rebuild_wall_not_registered")
    return wall


# ---------------------------------------------------------------- folds, fitting, predicting


def make_folds(n, k, fold_seed):
    """``k`` held-out index lists (a seeded permutation split as evenly as possible); recorded in the record."""
    if not 2 <= k <= n:
        raise Refused("k_fold_needs_2_to_n_folds")
    order = np.random.default_rng(fold_seed).permutation(n)
    return [sorted(int(i) for i in part) for part in np.array_split(order, k)]


def predict(product, inputs):
    return np.asarray(product["apply"](product["parameters"], inputs), dtype=np.float64)


def timed_fit(builder, x, y, *, seed, configuration, train_use):
    start = time.monotonic()
    product = builder(x, y, seed=seed, configuration=configuration, train_use=train_use)
    return product, time.monotonic() - start


def rmse(prediction, truth):
    return float(math.sqrt(np.mean((np.asarray(prediction) - np.asarray(truth)) ** 2)))


def cross_validate(builder, setting, folds, x, y, *, seed, wall):
    """Mean held-out RMSE of one resolved setting over the folds, and its slowest fit; OVER_LIMIT when a fit passes the wall."""
    configuration, train_use = setting
    errors, slowest = [], 0.0
    for held in folds:
        keep = [i for i in range(len(x)) if i not in set(held)]
        product, seconds = timed_fit(
            builder,
            x[keep],
            y[keep],
            seed=seed,
            configuration=configuration,
            train_use=train_use,
        )
        slowest = max(slowest, seconds)
        errors.append(rmse(predict(product, x[held]), y[held]))
    out = {
        "fold_rmse": errors,
        "mean_rmse": float(np.mean(errors)),
        "slowest_fit_seconds": slowest,
    }
    out["state"] = "OVER_LIMIT" if slowest > wall else "OK"
    return out


def select(table):
    """Index of the lowest mean CV RMSE among OK settings (first wins a tie); None when none is OK."""
    ok = [(row["mean_rmse"], i) for i, row in enumerate(table) if row["state"] == "OK"]
    return min(ok)[1] if ok else None


# ---------------------------------------------------------------- catalog builders (from the entry's pinned bundle source)


def load_catalog_builder(item):
    """The entry's pinned ``carbon_candidate.build.build``: the bundle's source is extracted, its build module is checked
    against the settings schema's sha256, and it is imported fresh. It needs the entry's runtime (torch / jax) on the pod.
    """
    from carbon.backbone_catalog import pipeline, settings

    schema = settings.SCHEMAS[item["settings_schema"]]
    source = pipeline.bundle_files(item)["source.tar.gz"]
    member = pipeline._source_member(source, schema.build_member)
    if "sha256:" + hashlib.sha256(member).hexdigest() != schema.build_sha256:
        raise Refused("catalog_build_differs_from_its_pin:" + item["catalog_id"])
    target = Path(tempfile.mkdtemp(prefix="ln-build-"))
    with tarfile.open(fileobj=io.BytesIO(source), mode="r:gz") as archive:
        archive.extractall(target, filter="data")
    for name in [
        m
        for m in sys.modules
        if m == "carbon_candidate" or m.startswith("carbon_candidate.")
    ]:
        del sys.modules[name]
    sys.path.insert(0, str(target))
    try:
        module = importlib.import_module("carbon_candidate.build")
    finally:
        sys.path.remove(str(target))
    return module.build


def host_record():
    out = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
    }
    for name in ("torch", "jax"):
        try:
            module = importlib.import_module(name)
            out[name] = getattr(module, "__version__", "unknown")
        except ImportError:  # a missing runtime is recorded, not fatal here
            out[name] = None
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        out["gpu"] = gpu.stdout.strip().splitlines() if gpu.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        out["gpu"] = None
    return out


# ---------------------------------------------------------------- the run


def load_probe(path, n_in):
    probe = np.load(path, allow_pickle=False)
    if (
        probe.ndim != 2
        or probe.shape[1] != n_in
        or probe.dtype.kind != "f"
        or not np.isfinite(probe).all()
    ):
        raise Refused("probe_inputs_shape_or_values_invalid")
    return probe


def run(
    grid_path,
    grid_digest,
    version,
    probe_path,
    out_dir,
    *,
    builders=None,
    challenge_id="f02",
    log=print,
):
    """The whole harness for one version. ``builders`` maps catalog_id to a build callable (tests); default: the pins."""
    grid = load_grid(grid_path, grid_digest)
    if grid["challenge"] != {"id": challenge_id, "version": version}:
        raise Refused("grid_is_for_another_challenge_version")
    x, y = load_train(challenge_id, version)
    probe = load_probe(probe_path, x.shape[1])
    entries = resolve_entries(grid, challenge_id, version)
    checked = {
        item["catalog_id"]: check_settings(each, item) for each, item, _ in entries
    }
    wall = rebuild_wall_seconds(challenge_id, version)
    folds = make_folds(len(x), grid["k"], grid["fold_seed"])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    seed = grid["seed"]
    contenders = []
    for each, item, substituted_from in entries:
        cid = item["catalog_id"]
        builder = (builders or {}).get(cid) or load_catalog_builder(item)
        default = settings_resolve_default(item)
        record = {
            "role": each["role"],
            "catalog_id": cid,
            "substituted_for": substituted_from,
            "tuned": each["settings"] is not None,
        }
        chosen = None
        if each["settings"] is not None:
            table = []
            for configuration_use in checked[cid]:
                row = cross_validate(
                    builder, configuration_use, folds, x, y, seed=seed, wall=wall
                )
                table.append(row)
                log(
                    f"{cid} setting {len(table)}/{len(each['settings'])}: {row['state']} cv_rmse={row['mean_rmse']:.6g}"
                )
            chosen = select(table)
            record["cv"] = table
            record["selected_index"] = chosen
            record["selected_setting"] = (
                None if chosen is None else each["settings"][chosen]
            )
        fits = {"default": default}
        if chosen is not None:
            fits["tuned"] = checked[cid][chosen]
        exports = {}
        for label, (configuration, train_use) in fits.items():
            product, seconds = timed_fit(
                builder,
                x,
                y,
                seed=seed,
                configuration=configuration,
                train_use=train_use,
            )
            if seconds > wall:
                record.setdefault("over_limit_final_fits", []).append(label)
                continue
            prediction = predict(product, probe)
            if (
                prediction.shape[0] != probe.shape[0]
                or not np.isfinite(prediction).all()
            ):
                raise Refused("prediction_invalid:" + cid)
            target = out / cid
            target.mkdir(exist_ok=True)
            buffer = io.BytesIO()
            np.save(buffer, prediction.astype(np.float32), allow_pickle=False)
            (target / f"{label}.npy").write_bytes(buffer.getvalue())
            exports[label] = {
                "file": f"{cid}/{label}.npy",
                "sha256": "sha256:" + hashlib.sha256(buffer.getvalue()).hexdigest(),
                "fit_seconds": seconds,
            }
        record["exports"] = exports
        contenders.append(record)
    document = {
        "schema": RECORD_SCHEMA,
        "visibility": "CARBON_PRIVATE",
        "challenge": grid["challenge"],
        "grid_digest": grid_digest,
        "k": grid["k"],
        "fold_seed": grid["fold_seed"],
        "seed": seed,
        "folds": folds,
        "rebuild_wall_seconds": wall,
        "train_rows": len(x),
        "probe_inputs_sha256": "sha256:"
        + hashlib.sha256(np.ascontiguousarray(probe).tobytes()).hexdigest(),
        "probe_rows": int(probe.shape[0]),
        "host": host_record(),
        "contenders": contenders,
        "truths_read": False,
    }
    (out / "record.json").write_text(
        json.dumps(document, indent=1, sort_keys=True), encoding="utf-8"
    )
    return document


def settings_resolve_default(item):
    from carbon.backbone_catalog import settings

    return settings.resolve(item, {}, {})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("digest", help="print the grid's canonical digest")
    one.add_argument("grid")
    two = sub.add_parser("run")
    two.add_argument("--grid", required=True)
    two.add_argument("--grid-digest", required=True)
    two.add_argument("--version", required=True)
    two.add_argument("--probe-inputs", required=True)
    two.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "digest":
        print(digest(json.loads(Path(args.grid).read_text(encoding="utf-8"))))
        return 0
    try:
        run(args.grid, args.grid_digest, args.version, args.probe_inputs, args.out)
    except Refused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
