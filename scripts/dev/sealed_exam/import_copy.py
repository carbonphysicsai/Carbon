#!/usr/bin/env python3
"""Import one delivered signed copy into a validator's pack store (grading host, as the validator user).

    python scripts/dev/sealed_exam/import_copy.py --store <pack store dir> --copy <signed copy .json> \
        --hotkey <this validator's hotkey> [--producer-public-key <hex>]

The copy was issued for ONE hotkey (`copy_issuance`); this verifies the producer's signature, binds the batch to its
roles, checks the copy is this hotkey's, rebuilds the canonical pack beside it and stores both owner-only
(`copy_delivery.import_copy`). Prints the canonical manifest digest (the only identity that leaves the machine) and
nothing else; a copy that does not verify is refused with its typed code and nothing is stored. Importing the same
copy again changes nothing.

``--producer-public-key`` defaults to the release-pinned exam producer key of the installed network
(`validator_host.pinned_producer_key`); give it only for a rehearsal copy signed by a rehearsal key.

Then: `receiver_setup prepare --pack-store <store> --pack-digest <digest> --speed-sample-key-file <K_speed file> ...`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def import_one(store, copy, hotkey, producer_public_key=None):
    """The canonical manifest digest of the imported copy (see the module docstring)."""
    from carbon.challenge_validator import copy_delivery
    from carbon.challenge_validator.sealed_pack_import import SealedPackStore
    from carbon.challenge_validator.validator_host import pinned_producer_key

    package = json.loads(Path(copy).read_bytes())
    key = pinned_producer_key() if producer_public_key is None else producer_public_key
    return copy_delivery.import_copy(
        SealedPackStore(store), package, key, hotkey=hotkey
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", required=True)
    parser.add_argument("--copy", required=True)
    parser.add_argument("--hotkey", required=True)
    parser.add_argument("--producer-public-key")
    args = parser.parse_args(argv)
    try:
        digest = import_one(
            args.store, args.copy, args.hotkey, args.producer_public_key
        )
    except (ValueError, KeyError, TypeError, OSError) as refused:
        # a typed refusal names the check, never a secret
        code = getattr(refused, "code", type(refused).__name__)
        print(json.dumps({"refused": code}), file=sys.stderr)
        return 2
    print(json.dumps({"canonical_digest": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
