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


def install(catalog_ids=None, *, wheelhouse=None, state_dir=None, receiver_config=None):
    """Install each entry's child image over its PyTorch CPU parent, so
    practice and the receiver can build it.

    A miner installs from its checked Launchpad setup (`state_dir`,
    `library_bundle.install_bundle`); a receiver host from its operator record
    (`receiver_config`, `library_bundle.install_receiver_bundle`)."""
    if state_dir is not None and receiver_config is not None:
        raise pipeline.CatalogBroken(
            "install for a miner setup or a receiver, not both"
        )
    if wheelhouse is None and catalog_wheelhouse.DEFAULT_DIRECTORY.is_dir():
        wheelhouse = catalog_wheelhouse.DEFAULT_DIRECTORY
    installed = []
    for item in pipeline.load()["entries"]:
        if catalog_ids and item["catalog_id"] not in catalog_ids:
            continue
        pipeline.verify(item)
        if wheelhouse is None and not catalog_ids and _declares_wheels(item):
            print(
                f"skipped {item['catalog_id']}: its pinned wheels need a "
                f"wheelhouse; build it with {WHEELHOUSE_STEP}, then install again",
                file=sys.stderr,
            )
            continue
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
            installed.append({"catalog_id": item["catalog_id"], **result})
    return installed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("catalog_id", nargs="*")
    parser.add_argument("--wheelhouse", type=Path)
    host = parser.add_mutually_exclusive_group()
    host.add_argument("--state-dir", type=Path)
    host.add_argument("--receiver-config", type=Path)
    args = parser.parse_args(argv)
    try:
        print(
            json.dumps(
                install(
                    args.catalog_id,
                    wheelhouse=args.wheelhouse,
                    state_dir=args.state_dir,
                    receiver_config=args.receiver_config,
                ),
                indent=1,
                default=str,
            )
        )
    except pipeline.CatalogBroken as broken:
        print("refused: " + str(broken), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
