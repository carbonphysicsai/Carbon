"""Print the per-field digests of a sealed bank, to compare the build host's bank with the grading host's.

``physical_dual_pack.bank_digest`` pins a bank's case ids, cohorts, inputs, native records and reference mask.
When a pack's definition names one bank and the receiver resolves another (``binding  BANK DIFFERS`` in the
grade repro), this prints, for the bank built from a sealed batch, each field's digest as the bank lists it and
in case_id order, so a field-by-field comparison names the difference: the same ``by_case_id`` with a different
``as listed`` is order only, a different ``by_case_id`` is content. Digests only; nothing is written.

    # on the build host: the canonical batch directory (holds the sealed batch file the pack was built from)
    PYTHONPATH=<checkout> python -B bank_fields.py --private-root <dir with the sealed batch> \
        --challenge electric-motor-magnetics --version 1.5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import grade_explain
except ImportError:  # pragma: no cover
    from scripts.dev.sealed_exam import grade_explain


def bank_of(challenge, version, private_root):
    from carbon.scoring import sealed_batch_source as source

    kit = source._kit(challenge)
    if kit is None:
        raise SystemExit("not a sealed-pack Challenge")
    carried = source.read_batch(Path(private_root))
    if carried is None:
        raise SystemExit("no sealed batch in that directory")
    return source._build(challenge, kit, carried[0], carried[1], version)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    bank = bank_of(args.challenge, args.version, args.private_root)
    from carbon.scoring import physical_dual_pack as pdp

    print(f"bank_digest {pdp.bank_digest(bank)}")
    for line in grade_explain.field_lines(bank, "built from the batch"):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
