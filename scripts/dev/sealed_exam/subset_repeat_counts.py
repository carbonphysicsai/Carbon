"""Count a subset-repeat version's strata on its sealed bank (read-only; run where the sealed bank is in custody).

    python scripts/dev/sealed_exam/subset_repeat_counts.py --pack-root <sealed pack dir> \
        [--challenge electric-motor-magnetics] [--version 1.8] [--copy-hotkey <this validator's hotkey>]

Loads the pack and its carried sealed bank exactly as grading does (`calibration_grade_run.prepare` / `resolve_bank`,
the copy of ``--copy-hotkey`` when given), splits it with the version's code-defined strata
(`subset_repeat_evidence.census`) and prints ONE JSON line of COUNTS ONLY: the sealed cells, each stratum's row count
``n``, its mode (``all`` re-runs every row, ``keyed`` re-runs ``min(k, n)``), the rows it re-runs per grade, the rows
in two strata (by stratum pair) or in none, and the per-grade total (sealed + the sum). ``k`` comes from the
registered f and P (`subset_repeat_evidence.registered_rate`); the strata list in the values file is not needed.

It prints no row, position, id, input, truth or key. It writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def counts(bank, challenge, version):
    """The counts document (see the module docstring) of one sealed bank."""
    from carbon.scoring import subset_repeat_evidence as subset

    defined = subset.definitions(challenge, version)
    counted = subset.census(challenge, version, bank)
    fail_fraction, detect_prob = subset.registered_rate(challenge, version)
    strata = {}
    for name, stratum in defined.items():
        n = len(counted["members"][name])
        per_grade = (
            n
            if stratum.every or n == 0
            else subset.derived_k(fail_fraction, detect_prob, n)
        )
        strata[name] = {
            "n": n,
            "mode": "all" if stratum.every else "keyed",
            "per_grade": per_grade,
            **({} if stratum.n is None else {"registered_n": stratum.n}),
        }
    sealed = len(counted["sealed"])
    return {
        "challenge": challenge,
        "version": version,
        "rows": sealed
        + sum(s["n"] for s in strata.values())
        + sum(counted["overlaps"].values())
        + len(counted["none"]),
        "sealed": sealed,
        "strata": strata,
        "overlaps": dict(sorted(counted["overlaps"].items())),
        "none": len(counted["none"]),
        "per_grade_total": sealed + sum(s["per_grade"] for s in strata.values()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pack-root", required=True, type=Path)
    parser.add_argument("--challenge", default="electric-motor-magnetics")
    parser.add_argument("--version", default="1.8")
    parser.add_argument("--copy-hotkey", default=None)
    args = parser.parse_args(argv)
    from carbon.challenge_validator import calibration_grade_run as run
    from carbon.scoring.subset_repeat_evidence import SubsetRepeatRefused

    try:
        snapshot = run.prepare(args.pack_root, args.challenge, args.version)
        bank, _adapter, _names = run.resolve_bank(
            snapshot, args.pack_root, args.challenge, args.version, args.copy_hotkey
        )
        print(json.dumps(counts(bank, args.challenge, args.version), sort_keys=True))
    except (SubsetRepeatRefused, run.cg.CalibrationRefused) as refused:
        print(
            json.dumps({"refused": getattr(refused, "code", str(refused))}),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
