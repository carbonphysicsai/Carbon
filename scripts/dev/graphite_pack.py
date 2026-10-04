"""Build or check the Graphite miner edition's shared card pack.

    python scripts/dev/graphite_pack.py build --snapshot SNAPSHOT.json [--out DIR]
    python scripts/dev/graphite_pack.py check --snapshot SNAPSHOT.json

`SNAPSHOT.json` is the frozen phase-2 snapshot file
(`<phase-2 root>/backfill/cards/snapshots/<sha256>.json`). It is read only: its
sha256 must equal its file name and the digest pinned in
`carbon.agent_campaign.graphite.miner.pack.SOURCE_SNAPSHOT_DIGEST`.

`build` writes `<out>/<pack digest>.json.gz` write-once (default: the
package's `packs/` directory) and prints the digest to pin as
`SHARED_PACK_DIGEST`. `check` rebuilds the pack in memory and compares it with
the shipped file byte for byte and with the pinned digest; it writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from carbon.agent_campaign.graphite.miner import pack


def _summary(document_bytes, document):
    return {
        "pack_digest": pack.digest(document_bytes),
        "cards": len(document["cards"]),
        "withheld_protected": len(document["withheld"]["withheld_protected"]),
        "protected_at_build": len(document["withheld"]["protected_at_build"]),
        "known_not_indexed": len(document["known_not_indexed"]),
        "source_snapshot": document["source"]["snapshot_file_digest"],
    }


def build(args):
    document_bytes, document = pack.build_document(args.snapshot)
    _, path = pack.write_pack(document_bytes, Path(args.out))
    print(json.dumps({**_summary(document_bytes, document), "path": path.name}))
    return 0


def check(args):
    document_bytes, document = pack.build_document(args.snapshot)
    value = pack.digest(document_bytes)
    shipped = pack.pack_path(pack.SHARED_PACK_DIGEST)
    same = (
        value == pack.SHARED_PACK_DIGEST
        and shipped.is_file()
        and shipped.read_bytes() == pack.compress(document_bytes)
    )
    print(json.dumps({**_summary(document_bytes, document), "reproduced": same}))
    return 0 if same else 1


def parser():
    top = argparse.ArgumentParser(prog="graphite-pack")
    commands = top.add_subparsers(dest="command", required=True)
    one = commands.add_parser("build")
    one.add_argument("--snapshot", required=True)
    one.add_argument("--out", default=str(pack.PACKS))
    one.set_defaults(handler=build)
    two = commands.add_parser("check")
    two.add_argument("--snapshot", required=True)
    two.set_defaults(handler=check)
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except pack.PackError as error:
        print(json.dumps({"status": "REFUSED", "reason_code": error.code}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
