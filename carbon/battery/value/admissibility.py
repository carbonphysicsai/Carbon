"""Battery near-limit optimism: an admissibility gate, built and inactive.

The TRACK-B-STUCK-01 recommendation, approved on 2026-10-03, has two parts:
- keep the deciding rule for ranking;
- add a separate admissibility gate that a model fails when it overstates
  safety margins near the limits, which is how the boundary-optimist control
  fails.

This module is that gate.

**Measured quantity.** SR-3's near-limit optimism: the mean over the
published important region (`domain.is_important`) of how far the model's
plating and peak-temperature margins exceed the reference's, in the decision
contract's band units (`margins.margin_component`, the `mean_optimism_bands`
field).

**The cutoff is a science value.** `THRESHOLD_BANDS` is None (HUMAN_INPUT)
until the SciML/technical lead sets it. While it is None, every verdict is
INACTIVE and no score changes. Once set, a model at or above it is
inadmissible: its score is 0 under every rule, so ranking cannot compensate
for a mandatory failure (constitution §7.3).

It is applied to value-study results, not to the live exam rule. Putting it
into the testnet rule is its own approval.

    python -m carbon.battery.value.admissibility --out DIR
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

#: HUMAN_INPUT: the SciML/technical lead sets this (bands of near-limit
#: optimism). None keeps the gate inactive.
THRESHOLD_BANDS = None

INACTIVE, PASS, FAIL = "INACTIVE", "PASS", "FAIL"
SCHEMA = "carbon.battery.admissibility-optimism.v1"
SOURCES = {
    "ev2-2026-10-01": "docs/development/evidence/sr3-2026-10-02/results.json",
    "ev4-2026-10-01": "docs/development/evidence/sr-ev4-2026-10-02/sr3/results.json",
}


def near_optimism(contract, predictions, case_ids, refs):
    """A member's mean near-limit optimism in bands, or None if unmeasured."""
    from .margins import margin_component
    from .near import near_cases

    class _Store:
        def __init__(self, refs):
            self.refs = refs

    component = margin_component(
        contract, predictions, near_cases(_Store(refs), case_ids), refs
    )
    return None if component is None else component["mean_optimism_bands"]


def verdict(optimism, threshold=None):
    """INACTIVE while no cutoff is set; otherwise PASS, or FAIL at or above it.
    An unmeasured optimism fails a set gate: it is never waved through."""
    threshold = THRESHOLD_BANDS if threshold is None else threshold
    if threshold is None:
        return INACTIVE
    if optimism is None:
        return FAIL
    return FAIL if optimism >= threshold else PASS


def gated(score, optimism, threshold=None):
    """A rule score after the gate: unchanged unless the gate fails, then 0."""
    return 0.0 if verdict(optimism, threshold) == FAIL else score


def _mean_loss(members, group):
    losses = [
        members[m]["loss_verification"]
        for m in group
        if members[m]["loss_verification"] is not None
    ]
    return statistics.mean(losses) if losses else None


def evidence(root="."):
    """The optimism distribution on retained results, for setting the cutoff.

    Descriptive only: no cutoff is chosen here. For each retained result it
    reports:
    - each eligible real member's optimism;
    - each constructed control's optimism;
    - how many real members sit at or above each control's level, and their
      mean verification decision loss against the rest.
    """
    root = Path(root)
    out = {}
    for dataset, source in SOURCES.items():
        near = json.loads((root / source).read_text())["near_component"]
        members = json.loads(
            (root / "docs/development/evidence" / dataset / "results.json").read_text()
        )["summary"]["members"]
        real = {
            m: near[m]["mean_optimism_bands"]
            for m in near
            if members[m]["kind"] == "RECONSTRUCTED" and members[m]["eligible"]
        }
        controls = {
            m: near[m]["mean_optimism_bands"]
            for m in near
            if members[m]["kind"] != "RECONSTRUCTED"
        }
        at_control_levels = {}
        for control, level in sorted(controls.items()):
            above = [m for m, v in real.items() if v >= level]
            below = [m for m in real if m not in above]

            at_control_levels[control] = {
                "level_bands": level,
                "real_members_at_or_above": len(above),
                "mean_verification_loss_at_or_above": _mean_loss(members, above),
                "mean_verification_loss_below": _mean_loss(members, below),
            }
        values = sorted(real.values())
        out[dataset] = {
            "source": source,
            "real_members": len(values),
            "real_min": values[0],
            "real_median": statistics.median(values),
            "real_max": values[-1],
            "real": dict(sorted(real.items())),
            "controls": dict(sorted(controls.items())),
            "at_control_levels": at_control_levels,
        }
    return {
        "schema": SCHEMA,
        "threshold_bands": THRESHOLD_BANDS,
        "state": INACTIVE if THRESHOLD_BANDS is None else "ACTIVE",
        "threshold_owner": "SciML/technical lead (HUMAN_INPUT)",
        "datasets": out,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.battery.value.admissibility"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = evidence(".")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "optimism.json").write_text(
        json.dumps(report, sort_keys=True, indent=1)
    )
    print(
        json.dumps(
            {
                k: {
                    "real_median": round(v["real_median"], 3),
                    "optimist": round(v["controls"]["control-boundary_optimist"], 3),
                }
                for k, v in report["datasets"].items()
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
