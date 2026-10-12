"""f02 base-only baseline transients (EVIDENCE-PRODUCER-STAGES-01, Test Lead 2026-10-12).

    python3 f02_baselines.py plan ROOT

The f02 impulse-response comparator needs each context's response to the 20 W
base alone. The cheap-baseline specification assigns the steady-baseline pins
to Data Collection. One transient per cooling pair x initial temperature x
source split: 8 decks. The waveform does not matter with no burst.

Same stack, mesh 1 and dt 1 as the menu primaries. The schedule is the
constant 20 W base over the 120 s horizon (`waveform: constant`,
`peak_w: 20`), starting at the context's initial temperature.

The deck manifest (`f02-menu-v2/baseline-decks-manifest.json`) is registered
before any solve. The reference stage solves these decks with the menu's own
runner, which re-checks every deck file's digest.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f02_deck as deck
import f02_menu as menu

MANIFEST = "docs/development/evidence/reference-packages-01/f02-menu-v2/baseline-decks-manifest.json"


def contexts():
    """(name, case) for each cooling pair x initial x split."""
    for (coolant, h), t0, split in itertools.product(
        menu.COOLING, menu.INITIAL_C, menu.SPLITS
    ):
        name = f"c{coolant:g}-i{t0:g}-s{split:g}-baseline"
        yield name, {"coolant_c": coolant, "h_w_m2_k": h, "initial_c": t0, "left_source_fraction": split,
                     "waveform": "constant", "peak_w": deck.BASE_W, "on_time_s": 0.0}  # fmt: skip


def baseline_name(context_name):
    """The baseline deck for a menu context (its waveform is irrelevant; waveform
    names may contain a hyphen, as two-pulse does)."""
    for waveform in menu.FAMILIES:
        if context_name.endswith("-" + waveform):
            return context_name[: -len(waveform) - 1] + "-baseline"
    raise ValueError(f"no registered waveform in {context_name!r}")


def plan(root):
    root = Path(root)
    entries = []
    for name, case in contexts():
        deck.write_case(case, root / "cases" / name)
        entries.append(
            {
                "case": name,
                "context": name,
                "peak_w": deck.BASE_W,
                "on_time_s": 0.0,
                "tag": "baseline",
            }
        )
    menu._manifest(root, entries)
    return len(entries)


if __name__ == "__main__":
    if sys.argv[1:2] != ["plan"]:
        raise SystemExit("usage: f02_baselines.py plan ROOT")
    print(plan(sys.argv[2]))
