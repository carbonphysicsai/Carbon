"""Battery's screening grain and per-coldkey ladder step (SCREENING-GRAIN-01).

The reference implementation of `docs/development/evidence/battery-screening-
grain/screening-grain-vN.json` (OWNER-BATTERY-CHAMPIONSHIP-04 §3 and the Test
Lead's noise-floor ruling, 2026-10-12), for PLT-08's ladder:

- `load` reads the highest-numbered file version;
- `entry_for` finds the ONE entry matching a deployment, or None (no match,
  or more than one: SEALED_UNTIL_GRAIN, fail closed);
- `own_se` is a coldkey's own screening SE from ITS OWN scored cases only;
- `update` decides one ladder step: NO_UPDATE below the registered minimum,
  and otherwise an update only when the score beats the displayed best by more
  than max(grain, own SE rounded up to 0.5 %) and by at least one grid step.

Pure and stdlib-only. It reads no case identity and returns no per-case or
per-window value: only the display decision and the grid value.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from pathlib import Path

GRAIN_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs/development/evidence/battery-screening-grain"
)
STEP = 0.005
SEALED = "SEALED_UNTIL_GRAIN"
NO_UPDATE = "NO_UPDATE"
UPDATE = "UPDATE"
_VERSION = re.compile(r"screening-grain-v([0-9]+)\.json")


def round_up(value):
    """`value` rounded UP to a 0.5 % step, with a 0.5 % floor."""
    return max(math.ceil(round(value / STEP, 9)) * STEP, STEP)


def load(directory=GRAIN_DIR):
    """The highest-numbered screening-grain-vN.json, or None."""
    found = []
    for path in Path(directory).glob("screening-grain-v*.json"):
        m = _VERSION.fullmatch(path.name)
        if m:
            found.append((int(m.group(1)), path))
    if not found:
        return None
    return json.loads(max(found)[1].read_text())


def entry_for(doc, deployment):
    """The one entry whose `match` the deployment satisfies, else None.
    `deployment`: {"rule", "score_section", "rule_digest"?, "score_candidate"?,
    "registry_sha256"?}. Every key an entry's `match` names must be equal."""
    if doc is None:
        return None
    hits = [
        e
        for e in doc.get("entries", [])
        if all(deployment.get(k) == v for k, v in e["match"].items())
    ]
    return hits[0] if len(hits) == 1 else None


def own_se(rule, own_errors, own_regrets=None):
    """A coldkey's own relative screening SE, from its own scored cases (and,
    under v3, its own design-question regrets) only; None if unmeasurable."""
    errors = [float(x) for x in own_errors]
    if len(errors) < 2:
        return None
    e_mean = statistics.fmean(errors)
    e_se = statistics.stdev(errors) / math.sqrt(len(errors))
    if rule == "v2-bank-sched":
        return None if e_mean <= 0 else e_se / e_mean
    if rule == "v3-bank-sched":
        regrets = [float(x) for x in (own_regrets or [])]
        if len(regrets) < 2:
            return None
        r_mean = statistics.fmean(regrets)
        r_se = statistics.stdev(regrets) / math.sqrt(len(regrets))
        return 0.5 * math.sqrt((e_se / (1 + e_mean)) ** 2 + (r_se / (1 + r_mean)) ** 2)
    return None


def coldkey_own_se(rule, records, coldkey):
    """`own_se` over the scored cases of `coldkey`'s records only.
    `records`: iterables of {"coldkey", "errors", "regrets"?}; any other
    coldkey's record is never read past its `coldkey` field."""
    errors, regrets = [], []
    for record in records:
        if record.get("coldkey") != coldkey:
            continue
        errors.extend(record["errors"])
        regrets.extend(record.get("regrets") or [])
    return own_se(rule, errors, regrets), len(errors), len(regrets)


def grid(entry, score, grain):
    """The grid exponent, rounded toward the worse side by the entry's sense."""
    k = math.log(score) / math.log(1 + grain)
    return math.ceil(k) if entry["sense"] == "lower_is_better" else math.floor(k)


def update(doc, entry, displayed_best, score, own, n_cases, n_questions=0):
    """One ladder decision: `(state, displayed)`.

    - SEALED with no entry (fail closed);
    - NO_UPDATE below the registered minimum, never an update at the grain;
    - UPDATE only when the score beats the displayed best by more than
      max(grain, round_up(own)) relatively AND by at least one grid step;
      the display is then the grid value rounded toward the worse side."""
    if entry is None or doc is None:
        return SEALED, displayed_best
    floor = doc["noise_floor"]
    grain = entry["grain"]
    needs_questions = entry["match"]["rule"] == "v3-bank-sched"
    if n_cases < floor["min_cases"] or (
        needs_questions and n_questions < floor["min_design_questions"]
    ):
        return NO_UPDATE, displayed_best
    if own is None:
        return NO_UPDATE, displayed_best
    step = max(grain, round_up(own))
    k = grid(entry, score, grain)
    shown = (1 + grain) ** k
    if displayed_best is None:
        return UPDATE, shown
    # The displayed best is always a grid value: recover its exponent exactly.
    k_best = round(math.log(displayed_best) / math.log(1 + grain))
    if entry["sense"] == "lower_is_better":
        better = displayed_best / score - 1 > step and k <= k_best - 1
    else:
        better = score / displayed_best - 1 > step and k >= k_best + 1
    return (UPDATE, shown) if better else (NO_UPDATE, displayed_best)
