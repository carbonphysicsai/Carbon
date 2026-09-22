"""Sufficient statistics for unpinned divergence, without choosing a convention.

Pinned GPU divergence measured zero - both A40 devices identical, and identical
to a third device of a different class - so there is no pinned epsilon to size a
tolerance against. The size has to come from the unpinned runs, which produce
different digests. A digest establishes *different* and not *how different*.

This emits enough to derive any relative convention afterwards rather than one
number under a convention chosen here. `|a-b| / |a|`, `|a-b| / max(|a|,|b|)` and
`|a-b| / ||.||` are all computable from what is printed, so the run produces the
measurement and the scientific holder decides what it means. Choosing the
denominator here would be defining the measurement, which is not this script's
to define - and the figure it would be compared against, `1.151e-05` from the
CPU instruction-set work, has no recorded convention either.

Absolute quantities are reported beside the relative ingredients deliberately.
The reproducibility implementation records an **absolute** per-output difference
(`NumericalDelta.absolute_delta`, an observed value rather than a threshold),
while the study reasons in relative terms. Reporting both defers nothing and
leaves that reconciliation visible instead of implied.

    python divergence_report.py <artifacts-root>
"""

from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path

import numpy as np

# `condition-dN-sM-index` from the matrix. The session and the in-session index
# are stripped to form the group, so every run of one condition on one device
# lands in the same cell however many sessions produced it.
#
# That grouping is the measurement's point: unpinned, the autotuner chooses
# kernels once per process, so the divergence worth sizing is the one *between*
# sessions. Grouping by full label would pair only runs that shared a process
# and would report near-zero.
RUN = re.compile(r"^(?P<group>.+?)(?:-s\d+)?-(?P<index>\d+)$")


def _load(path: Path) -> np.ndarray | None:
    if not path.is_file():
        return None
    if path.suffix == ".npy":
        return np.asarray(np.load(path)).ravel()
    with np.load(path) as bundle:
        return np.concatenate([np.asarray(bundle[k]).ravel() for k in sorted(bundle)])


def statistics(a: np.ndarray, b: np.ndarray) -> dict:
    """Everything a relative convention could need, and the absolute figures.

    Deliberately no ratio: the denominator is the convention, and the convention
    is the part this does not choose.
    """
    if a.shape != b.shape:
        return {"error": f"shape mismatch {a.shape} vs {b.shape}"}
    difference = np.abs(a - b)
    differing = int(np.count_nonzero(difference))
    return {
        "elements": int(a.size),
        "differing_elements": differing,
        "differing_fraction": differing / a.size if a.size else 0.0,
        "max_abs_difference": float(difference.max()) if a.size else 0.0,
        "mean_abs_difference": float(difference.mean()) if a.size else 0.0,
        "l2_abs_difference": float(np.linalg.norm(difference)),
        # The denominators a convention might use, reported rather than applied.
        "max_abs_a": float(np.abs(a).max()) if a.size else 0.0,
        "max_abs_b": float(np.abs(b).max()) if b.size else 0.0,
        "l2_a": float(np.linalg.norm(a)),
        "l2_b": float(np.linalg.norm(b)),
        # Elementwise denominators at the position of the largest difference, so
        # a per-element convention is derivable and not only a global one.
        "at_max": _at_max(a, b, difference),
    }


def _at_max(a: np.ndarray, b: np.ndarray, difference: np.ndarray) -> dict:
    if not a.size or not difference.any():
        return {}
    where = int(np.argmax(difference))
    return {
        "index": where,
        "a": float(a[where]),
        "b": float(b[where]),
        "abs_difference": float(difference[where]),
    }


def collect(root: Path) -> dict[str, dict[str, list[Path]]]:
    """Group retained runs by cell label, keeping predictions and parameters."""
    cells: dict[str, dict[str, list[Path]]] = {}
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        match = RUN.match(directory.name)
        if match is None:
            continue
        cell = cells.setdefault(
            match.group("group"), {"predictions": [], "checkpoint_leaves": []}
        )
        predictions = directory / "predictions.npy"
        if predictions.is_file():
            cell["predictions"].append(predictions)
        state = directory / "checkpoint" / "state.npz"
        if state.is_file():
            cell["checkpoint_leaves"].append(state)
    return cells


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"no artifacts directory at {root}", file=sys.stderr)
        return 2

    cells = collect(root)
    report: dict[str, object] = {
        "schema": "carbon.study.unpinned-divergence.v1",
        "note": (
            "sufficient statistics only; no relative convention is applied here, "
            "and no tolerance is proposed"
        ),
        "predictions_note": (
            "predictions are the quantity the study reasons about, produced "
            "through the registered predict() from identical archive inputs"
        ),
        # Said explicitly because the numbers invite the wrong reading. The
        # checkpoint holds 71 leaves, and not all of them are trained
        # parameters: one carries a counter of order 1e9 and two carry the step
        # count. Its max-abs and L2 denominators are dominated by those, so a
        # relative figure derived from this block is not the trained-parameter
        # quantity the CPU instruction-set work reported, and must not be
        # compared against it.
        "checkpoint_leaves_note": (
            "every leaf in the checkpoint, including non-parameter leaves such "
            "as counters and the step count; NOT the trained-parameter quantity, "
            "and its denominators are dominated by those leaves"
        ),
        "cells": {},
    }
    # Pairs are taken across every retained run, within a cell and between cells
    # of the same condition, because the interesting comparison for an unpinned
    # figure is between separate processes rather than within one.
    for name, kinds in sorted(cells.items()):
        entry: dict[str, object] = {}
        for kind, paths in kinds.items():
            arrays = [(p, _load(p)) for p in sorted(paths)]
            arrays = [(p, a) for p, a in arrays if a is not None]
            entry[kind] = {
                "runs": len(arrays),
                "pairs": [
                    {
                        "a": str(pa.relative_to(root)),
                        "b": str(pb.relative_to(root)),
                        **statistics(aa, bb),
                    }
                    for (pa, aa), (pb, bb) in itertools.combinations(arrays, 2)
                ],
            }
        report["cells"][name] = entry

    # The compact summary is printed *before* the JSON, and that ordering is the
    # point rather than a preference. A pod's log is read back through a bounded
    # window, and the full report is larger than that window: on the H100 class
    # run the body scrolled past and the figures could not be recovered from a
    # completed, correct measurement. A summary after the body would be cut by
    # the same bound. A few lines first survive any window that begins at the
    # report.
    #
    # The relative figures here apply the convention amendment 5 fixed. The raw
    # statistics below remain the record, so a different ratification is still a
    # recomputation rather than another run.
    print("DIVERGENCE_SUMMARY_BEGIN")
    for name, kinds in sorted(report["cells"].items()):
        pairs = kinds.get("predictions", {}).get("pairs", [])
        usable = [p for p in pairs if "max_abs_difference" in p]
        if not usable:
            print(f"{name}\tpredictions\tpairs=0\tno comparable runs retained")
            continue
        rel_l2 = max(p["l2_abs_difference"] / p["l2_a"] for p in usable if p["l2_a"])
        rel_max = max(
            p["max_abs_difference"] / max(p["max_abs_a"], p["max_abs_b"])
            for p in usable
            if max(p["max_abs_a"], p["max_abs_b"])
        )
        print(
            f"{name}\tpredictions\tpairs={len(usable)}"
            f"\tdiffering={min(p['differing_elements'] for p in usable)}"
            f"-{max(p['differing_elements'] for p in usable)}"
            f"/{usable[0]['elements']}"
            f"\tmax_abs={max(p['max_abs_difference'] for p in usable):.9g}"
            f"\trel_l2={rel_l2:.6g}\tmax_rel={rel_max:.6g}"
        )
    print("DIVERGENCE_SUMMARY_END")
    print("DIVERGENCE_BEGIN")
    print(json.dumps(report, indent=1, sort_keys=True))
    print("DIVERGENCE_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
