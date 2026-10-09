"""Battery's published case pools and Carbon's declarative draw from them
(Level 2 `training_data.pool_selection`, BATTERY-L2-POOL-SELECTION-01).

**A pool version** is an immutable, content-addressed manifest
(`carbon.battery.public-pool.v1`, under `pools/`): its parts, each with its
pinned source file, digest and case count, the digest of its sorted case ids,
the refusal list applied, its parent and the overlap verdict. Its digest is
its identity, and a recipe names a pool by that digest.

- **v1 is TRAIN v1 only** (the Test Lead, 2026-10-07): 400 public, solved
  cases, the set Level 0 trains on, so v1 needs no new solve or publication.
  PRACTICE is never in a pool, and a recipe naming it is refused.
- **Later versions** add retired, published bank cases through the
  Validator's producer path, each checked by `confirmation.overlap_check`
  before it exists. None is registered yet.

**The draw.** A recipe never names a case. Carbon draws the subset from the
recipe alone: the cases inside the recipe's `box`, per stratum, ranked by
`sha256(seed + ":" + case_id)` where the seed is the canonical digest of the
recipe's `pool_selection`, the first `n_s` of each stratum kept. The same
recipe gives the same subset on every validator, with no random-number
library involved. Stratum counts follow the normalised weights by largest
remainder, so they always sum to the recipe's `cases`.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .domain import INPUTS

HERE = Path(__file__).resolve().parent
POOLS_DIR = HERE / "pools"
POOL_SCHEMA = "carbon.battery-public-pool.v1"
DRAW_SCHEMA = "carbon.battery-pool-draw.v1"
#: Parts a pool may hold. PRACTICE is never one (the Test Lead, 2026-10-07).
PARTS = ("train", "bank")
REFUSED_PARTS = ("practice",)
#: The largest stratum weight a recipe may give (the design's [0, 2]).
MAX_WEIGHT = 2.0
SELECTION_KEYS = frozenset({"pool_version", "strata", "box", "cases"})


class PoolRefused(ValueError):
    def __init__(self, issues):
        super().__init__(", ".join(code for code, _ in issues))
        self.issues = tuple(issues)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def manifest_v1(train):
    """Pool v1's manifest from TRAIN v1 (`challenge.PublicMaterial.train`)."""
    from .challenge import TRAIN_V1_PATH, TRAIN_V1_SHA256

    return {
        "schema": POOL_SCHEMA,
        "version": "public-pool-v1",
        "parts": [
            {
                "part": "train",
                "source": TRAIN_V1_PATH,
                "source_sha256": TRAIN_V1_SHA256,
                "cases": len(train.case_ids),
                "case_ids_digest": sha256(canonical(sorted(train.case_ids))),
            }
        ],
        "refused_case_ids": [],
        "parent": None,
        "overlap_check": (
            "NOT_RUN_FOR_V1: v1 is exactly TRAIN v1, the public set Level 0 "
            "already trains on; confirmation.overlap_check binds every later "
            "version on the producer before it exists"
        ),
    }


def registered():
    """{digest: manifest} for every committed pool version."""
    found = {}
    for path in sorted(POOLS_DIR.glob("public-pool-v*.json")):
        manifest = json.loads(path.read_text())
        found[sha256(canonical(manifest))] = manifest
    return found


def _box_issues(box, path):
    if type(box) is not dict:
        return [("pool.box_malformed", path)]
    issues = []
    for name, bounds in box.items():
        if name not in INPUTS:
            issues.append(("pool.box_unknown_input", f"{path}/{name}"))
        elif (
            type(bounds) is not list
            or len(bounds) != 2
            or not all(
                type(b) in (int, float) and type(b) is not bool and math.isfinite(b)
                for b in bounds
            )
            or not bounds[0] < bounds[1]
        ):
            issues.append(("pool.box_malformed", f"{path}/{name}"))
    return issues


def check(selection, path="/parameters/pool_selection"):
    """The pool manifest a well-formed `selection` names; `PoolRefused`
    naming every issue otherwise. The draw's own size checks are `draw`'s."""
    if type(selection) is not dict or not set(selection) <= SELECTION_KEYS:
        raise PoolRefused([("pool.selection_malformed", path)])
    issues = []
    missing = {"pool_version", "strata", "cases"} - set(selection)
    if missing:
        issues += [("pool.selection_missing", f"{path}/{k}") for k in sorted(missing)]
    manifest = registered().get(selection.get("pool_version"))
    if "pool_version" in selection and manifest is None:
        issues.append(("pool.version_unregistered", path + "/pool_version"))
    strata = selection.get("strata")
    if "strata" in selection:
        if type(strata) is not dict or not strata:
            issues.append(("pool.strata_malformed", path + "/strata"))
        else:
            parts = {p["part"] for p in manifest["parts"]} if manifest else set(PARTS)
            for name, weight in strata.items():
                where = f"{path}/strata/{name}"
                if name in REFUSED_PARTS:
                    issues.append(("pool.practice_refused", where))
                elif name not in parts:
                    issues.append(("pool.part_not_in_version", where))
                elif (
                    type(weight) not in (int, float)
                    or type(weight) is bool
                    or not math.isfinite(weight)
                    or not 0 <= weight <= MAX_WEIGHT
                ):
                    issues.append(("pool.weight_out_of_bounds", where))
            if not issues and not any(w > 0 for w in strata.values()):
                issues.append(("pool.weights_all_zero", path + "/strata"))
    issues += _box_issues(selection.get("box", {}), path + "/box")
    cases = selection.get("cases")
    if "cases" in selection and (type(cases) is not int or cases < 1):
        issues.append(("pool.cases_out_of_bounds", path + "/cases"))
    if issues:
        raise PoolRefused(issues)
    return manifest


def _allocation(strata, cases):
    """Cases per stratum: normalised weights, largest remainder, summing to
    `cases` exactly. Ties go to the earlier stratum name."""
    names = sorted(n for n, w in strata.items() if w > 0)
    total = sum(strata[n] for n in names)
    exact = {n: cases * strata[n] / total for n in names}
    counts = {n: math.floor(exact[n]) for n in names}
    order = sorted(names, key=lambda n: (-(exact[n] - counts[n]), n))
    for n in order[: cases - sum(counts.values())]:
        counts[n] += 1
    return counts


def draw(selection, parts, path="/parameters/pool_selection"):
    """The drawn case ids, sorted. `parts` is `{part: TrainingData}` for the
    named pool version. Refused when the box leaves a stratum short, or when
    `cases` exceeds the pool."""
    manifest = check(selection, path)
    counts = _allocation(selection["strata"], selection["cases"])
    if selection["cases"] > sum(p["cases"] for p in manifest["parts"]):
        raise PoolRefused([("pool.cases_out_of_bounds", path + "/cases")])
    box = selection.get("box", {})
    seed = sha256(canonical(selection))
    chosen = []
    for name, count in counts.items():
        data = parts[name]
        eligible = [
            case_id
            for case_id, x in zip(data.case_ids, data.x, strict=True)
            if all(box[k][0] <= float(x[INPUTS.index(k)]) <= box[k][1] for k in box)
        ]
        if len(eligible) < count:
            raise PoolRefused([("pool.box_too_narrow", f"{path}/strata/{name}")])
        ranked = sorted(
            eligible,
            key=lambda c: hashlib.sha256((seed + ":" + c).encode("utf-8")).hexdigest(),
        )
        chosen += ranked[:count]
    return sorted(chosen)


def subset(train, case_ids):
    """`train` restricted to `case_ids`, in TRAIN's own order."""
    wanted = set(case_ids)
    index = [i for i, c in enumerate(train.case_ids) if c in wanted]
    if len(index) != len(wanted):
        raise ValueError("a drawn case is not in the pool's data")
    return train.take(index)
