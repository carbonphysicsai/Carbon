"""Install the backbone catalog's child images (owner-run; never from MCP).

Each entry's child image goes over the PyTorch CPU parent. On a miner it reads
the checked Launchpad setup; on a receiver host, which has no miner setup, it
reads the receiver's operator record and installs over the parent and into the
cache the receiver itself verifies at start:

    python -m scripts.dev.catalog_install [IDS...] [--wheelhouse DIR]
        [--state-dir DIR | --receiver-config RECEIVER.json]

An entry with pinned wheels takes them from `--wheelhouse`, by default the
host's own wheelhouse (`~/.carbon/catalog-wheelhouse`, built by
`python -m scripts.dev.catalog_wheelhouse`) when it exists. Without one, an
install of every entry skips those entries, each with a line on stderr naming
that command; one named by id is refused.

This lives under `scripts/dev`, beside the owner installers it calls, and not
in `carbon.backbone_catalog`: miner paths read the catalog, and nothing they
import may reach these installers or the receiver (Validator, 2026-10-20;
`tests/invariants/test_attack_store_unreachable.py`).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from carbon.backbone_catalog import pipeline
from scripts.dev import catalog_wheelhouse, library_bundle

#: What a skipped wheel entry tells the owner to run first.
WHEELHOUSE_STEP = "python -m scripts.dev.catalog_wheelhouse"


def _declares_wheels(item):
    return bool(json.loads(pipeline.bundle_files(item)["bundle.json"])["wheels"])


def _missing_wheel(item, wheelhouse):
    """The first of `item`'s pinned wheels that `wheelhouse` does not hold,
    or None."""
    declared = json.loads(pipeline.bundle_files(item)["bundle.json"])["wheels"]
    return next(
        (name for name in sorted(declared) if not (Path(wheelhouse) / name).is_file()),
        None,
    )


def install(
    catalog_ids=None,
    *,
    wheelhouse=None,
    state_dir=None,
    receiver_config=None,
    skipped=None,
):
    """Install each entry's child image over its PyTorch CPU parent, so
    practice and the receiver can build it.

    A miner installs from its checked Launchpad setup (`state_dir`,
    `library_bundle.install_bundle`); a receiver host from its operator record
    (`receiver_config`, `library_bundle.install_receiver_bundle`).

    An install of every entry never stops at one (M1 E2E R10-1: a wheelhouse
    without a newly pinned wheel stopped the whole catalog at 12 of 56): an
    entry whose pinned wheel the wheelhouse lacks, or whose install fails, is
    skipped, named on stderr and appended to `skipped` as {catalog_id,
    reason, wheel or detail}, and the rest go on. An entry named by id is
    refused as before."""
    if state_dir is not None and receiver_config is not None:
        raise pipeline.CatalogBroken(
            "install for a miner setup or a receiver, not both"
        )
    if wheelhouse is None and catalog_wheelhouse.DEFAULT_DIRECTORY.is_dir():
        wheelhouse = catalog_wheelhouse.DEFAULT_DIRECTORY
    skipped = [] if skipped is None else skipped
    installed = []
    for item in pipeline.load()["entries"]:
        catalog_id = item["catalog_id"]
        if catalog_ids and catalog_id not in catalog_ids:
            continue
        pipeline.verify(item)
        if wheelhouse is None and not catalog_ids and _declares_wheels(item):
            print(
                f"skipped {catalog_id}: its pinned wheels need a "
                f"wheelhouse; build it with {WHEELHOUSE_STEP}, then install again",
                file=sys.stderr,
            )
            skipped.append({"catalog_id": catalog_id, "reason": "wheelhouse_missing"})
            continue
        missing = None if wheelhouse is None else _missing_wheel(item, wheelhouse)
        if missing is not None and not catalog_ids:
            print(
                f"skipped {catalog_id}: its pinned wheel {missing} is not in the "
                f"wheelhouse {wheelhouse}; fetch it with {WHEELHOUSE_STEP}, then "
                "install again",
                file=sys.stderr,
            )
            skipped.append(
                {"catalog_id": catalog_id, "reason": "wheel_missing", "wheel": missing}
            )
            continue
        try:
            with tempfile.TemporaryDirectory() as work:
                directory = pipeline.bundle_directory(
                    item, Path(work) / "bundle", wheelhouse=wheelhouse
                )
                if receiver_config is not None:
                    result = library_bundle.install_receiver_bundle(
                        directory, receiver_config
                    )
                else:
                    kwargs = {} if state_dir is None else {"state_dir": state_dir}
                    result = library_bundle.install_bundle(directory, **kwargs)
        except Exception as failure:  # one entry never stops the rest
            if catalog_ids:
                raise
            detail = f"{type(failure).__name__}: {failure}"[:300]
            print(
                f"skipped {catalog_id}: its install failed: {detail}", file=sys.stderr
            )
            skipped.append(
                {"catalog_id": catalog_id, "reason": "install_failed", "detail": detail}
            )
            continue
        installed.append({"catalog_id": catalog_id, **result})
    if state_dir is not None and receiver_config is None:
        stage_gpu_twins(
            catalog_ids, wheelhouse=wheelhouse, state_dir=state_dir, skipped=skipped
        )
    return installed


def gpu_runtimes(state_dir):
    """The GPU build runtimes this install's GPU workers serve: the runner
    profile's (`gpu_image`, `extra_gpu_image`) and, before Review wrote one,
    the installer's record (`gpu_image_manifest`, `torch_gpu_image_manifest`)."""
    from carbon.development_session.gpu_practice import gpu_runtime
    from carbon.reconstruction.worker.docker_runtime import load_image_identity
    from scripts.dev.miner_launchpad import installed

    environment = Path(state_dir) / "environment"
    paths = []
    try:
        cfg = json.loads((environment / "runner-profile.json").read_bytes())
        paths += [cfg.get(f) for f in ("gpu_image", "extra_gpu_image")]
    except (OSError, ValueError):
        pass
    record = installed.read(Path(state_dir)) or {}
    paths += [record.get(f) for f in ("gpu_image_manifest", "torch_gpu_image_manifest")]
    found = []
    for path in paths:
        if type(path) is not str:
            continue
        try:
            runtime = gpu_runtime(load_image_identity(Path(path)))
        except Exception:  # noqa: BLE001 - a record that cannot be read serves none
            runtime = None
        if runtime is not None and runtime not in found:
            found.append(runtime)
    return found


def stage_gpu_twins(catalog_ids=None, *, wheelhouse=None, state_dir, skipped=None):
    """Stage each entry's GPU twin material for every GPU runtime this
    install serves (`gpu_runtimes`), where practice's GPU build prepares its
    overlay from it (M1 E2E S4: only the CPU build was staged, so every GPU
    practice fell back with "pinned bundle material is not staged"). Inert:
    the pinned bytes and wheels are copied into the owner's library cache;
    nothing is built or run. An entry whose twin cannot be staged is named
    in `skipped` and the rest go on. Returns the staged [{catalog_id,
    runtime}]."""
    skipped = [] if skipped is None else skipped
    runtimes = gpu_runtimes(state_dir)
    if not runtimes:
        return []
    if wheelhouse is None and catalog_wheelhouse.DEFAULT_DIRECTORY.is_dir():
        wheelhouse = catalog_wheelhouse.DEFAULT_DIRECTORY
    staged = []
    for item in pipeline.load()["entries"]:
        catalog_id = item["catalog_id"]
        if catalog_ids and catalog_id not in catalog_ids:
            continue
        for runtime in runtimes:
            if runtime not in (item.get("bundle_refs") or {}):
                continue
            try:
                with tempfile.TemporaryDirectory() as work:
                    directory = pipeline.twin_directory(
                        item, runtime, Path(work) / "twin", wheelhouse=wheelhouse
                    )
                    library_bundle.stage_bundle(directory, state_dir=state_dir)
            except Exception as failure:  # noqa: BLE001 - one twin never stops the rest
                detail = f"{type(failure).__name__}: {failure}"[:300]
                print(
                    f"skipped {catalog_id} {runtime} build: {detail}", file=sys.stderr
                )
                skipped.append(
                    {
                        "catalog_id": catalog_id,
                        "reason": "gpu_twin_not_staged",
                        "runtime": runtime,
                        "detail": detail,
                    }
                )
                continue
            staged.append({"catalog_id": catalog_id, "runtime": runtime})
    return staged


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("catalog_id", nargs="*")
    parser.add_argument("--wheelhouse", type=Path)
    host = parser.add_mutually_exclusive_group()
    host.add_argument("--state-dir", type=Path)
    host.add_argument("--receiver-config", type=Path)
    # Where the skipped entries are written as JSON, for the Control Center's
    # background install (scripts/dev/miner_launchpad/catalog_build.py).
    parser.add_argument("--report", type=Path)
    # Only the GPU twins' material (inert; no build), for the GPU workers
    # setup has just added (M1 E2E S4).
    parser.add_argument("--gpu-twins-only", action="store_true")
    args = parser.parse_args(argv)
    skipped = []
    try:
        if args.gpu_twins_only:
            if args.state_dir is None:
                parser.error("--gpu-twins-only needs --state-dir")
            installed = stage_gpu_twins(
                args.catalog_id,
                wheelhouse=args.wheelhouse,
                state_dir=args.state_dir,
                skipped=skipped,
            )
        else:
            installed = install(
                args.catalog_id,
                wheelhouse=args.wheelhouse,
                state_dir=args.state_dir,
                receiver_config=args.receiver_config,
                skipped=skipped,
            )
    except pipeline.CatalogBroken as broken:
        print("refused: " + str(broken), file=sys.stderr)
        return 1
    print(json.dumps(installed, indent=1, default=str))
    if args.report is not None:
        args.report.write_text(
            json.dumps({"installed": len(installed), "skipped": skipped}),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
