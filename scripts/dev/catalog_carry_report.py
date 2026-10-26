#!/usr/bin/env python3
"""Per-entry record of a version's catalog carry (V8_RULINGS section 12 item 3).

    python scripts/dev/catalog_carry_report.py [--out FILE]

For every version that offers another version's receipted catalog entries, lists each carried entry with the two
versions' TRAIN digests (equal) and the interface fields that differ (only `/challenge/version` is allowed). It
reruns nothing: it is the input-identity diff the pair rule uses (`carbon.backbone_catalog.carries`), written so the
Validator can read the carry entry by entry. A carry the rule refuses is reported as refused, never listed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def report():
    from carbon.backbone_catalog import carries, listing
    from carbon.backbone_catalog.entries import CatalogRefused
    from carbon.challenge_kit import physical_material, version_registry

    out = []
    for (challenge_id, version), entry in sorted(version_registry.VERSIONS.items()):
        sources = [v for v in entry.catalog_entries_from if v != version]
        if not sources:
            continue
        record = {"challenge": challenge_id, "version": version, "from": {}}
        try:
            diffs = carries.require_identity_only(challenge_id, version)
        except CatalogRefused as refused:
            record["refused"] = str(refused)
            out.append(record)
            continue
        offered = [e["catalog_id"] for e in listing.entries(challenge_id, version)]
        for source in sources:
            record["from"][source] = {
                "train_digest_equal": (
                    physical_material.construction_kit(challenge_id, source)[
                        "train_digest"
                    ]
                    == physical_material.construction_kit(challenge_id, version)[
                        "train_digest"
                    ]
                ),
                "interface_diff": diffs[source],
            }
        record["entries_offered"] = len(offered)
        record["entry_ids"] = offered
        out.append(record)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    text = json.dumps(report(), indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
