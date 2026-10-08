"""SUBMISSION-RATE-STUDY-01 arm H: the frozen, ordered candidate libraries
(run sheet D.1).

    python scripts/dev/rate_study/library.py          # write every version
    python scripts/dev/rate_study/library.py --check  # refuse a stale file

**library-v2 (current; Test Lead ruling, 2026-10-08).** A new version, a
superset of v1, so that a run at m = 4 (144 submissions) never repeats a
recipe: the route does not rescore a repeat (plan O7c). v1 is kept exactly as
recorded. v2 adds a deterministic grid over EV4's own sweep axes, which
conditions on nothing measured; every recipe compiles:
- MLP: EV4's grid (steps 500/1500/3000/6000 x width 64/128/256/512) at
  depths 1 and 4 (EV4 covers 2 and 3);
- DeepONet: the same steps x widths at `deeponet_depth` 2 and 3, where not
  already in v1;
- kNN: `neighbours` 2, 7, 20, 30 and 50.
v2 has its own order seed, so its order is not v1's.

**library-v1** (superseded before any run; unchanged):

The library is every distinct recipe of EV4's panel (`panel.PANELS["ev4"]`:
80 recipes behind EV4's 100 members) and of Graphite's run-5 constructions
(`panel.PANELS["graphite-run5"]`: 9), deduplicated by the canonical digest of
the strategy document. A recipe in both keeps both sources. Panel seeds are
dropped: the validator, not the candidate, chooses the rebuild seed.

The order is random but study-only. Each entry's rank key is
`sha256(ORDER_SEED + ":" + strategy_digest)`, sorted ascending. `ORDER_SEED`
is a public string, not a hidden seed: it is derived from nothing hidden and
gates nothing, and it is recorded in the file. Arm H submits entries in this
order and never conditions on any result. A run that needs more submissions
than the library holds continues from the start of the order (`cycle`).

Pure standard library plus Carbon's own panel module. It reads no operator
record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))

SCHEMA = "carbon.rate-study.candidate-library.v1"
STUDY = "SUBMISSION-RATE-STUDY-01"
SOURCES = ("ev4", "graphite-run5")
GRID = "rate-study-grid-v2"
EVIDENCE = REPOSITORY / "docs/development/evidence/submission-rate-study-01"
VERSIONS = ("v1", "v2")
CURRENT = "v2"
CHALLENGE_ID = "battery-fastcharge-ageing-development-v1"
STEPS = (500, 1500, 3000, 6000)
WIDTHS = (64, 128, 256, 512)
#: The fewest distinct recipes v2 must hold: the m = 4 run's submissions.
MINIMUM_V2 = 144


def order_seed(version):
    return f"SUBMISSION-RATE-STUDY-01/arm-H/library-{version}"


def out(version):
    return EVIDENCE / f"library-{version}.json"


def _strategy(backbone, parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE_ID,
        "backbone": backbone,
        "parameters": parameters,
    }


def extension():
    """v2's grid, `(label, strategy)` in a fixed order. Recipes already in v1
    are dropped by `build`'s deduplication."""
    rows = [
        (
            f"mlp_t{steps}_w{width}_d{depth}",
            _strategy("mlp", {"steps": steps, "width": width, "depth": depth}),
        )
        for depth in (1, 4)
        for steps in STEPS
        for width in WIDTHS
    ]
    rows += [
        (
            f"deeponet_t{steps}_w{width}_d{depth}",
            _strategy(
                "deeponet", {"steps": steps, "width": width, "deeponet_depth": depth}
            ),
        )
        for depth in (2, 3)
        for steps in STEPS
        for width in WIDTHS
    ]
    rows += [
        (f"knn{n}", _strategy("knn", {"neighbours": n})) for n in (2, 7, 20, 30, 50)
    ]
    return rows


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def build(version=CURRENT):
    from carbon.battery.value import panel

    if version not in VERSIONS:
        raise ValueError("unknown library version " + str(version))
    rows = [
        (source, label, strategy)
        for source in SOURCES
        for label, strategy, _seeds in panel.PANELS[source]
    ]
    if version == "v2":
        rows += [(GRID, label, strategy) for label, strategy in extension()]
    entries = {}
    for source, label, strategy in rows:
        digest = sha256(canonical(strategy))
        if source == GRID and digest in entries:
            continue  # already in v1; v1's sources stand
        entry = entries.setdefault(
            digest,
            {"strategy_digest": digest, "strategy": strategy, "sources": []},
        )
        entry["sources"].append({"panel": source, "label": label})
    seed = order_seed(version)

    def rank(entry):
        return hashlib.sha256(
            (seed + ":" + entry["strategy_digest"]).encode("utf-8")
        ).hexdigest()

    ordered = sorted(entries.values(), key=rank)
    for index, entry in enumerate(ordered):
        entry["position"] = index
    body = {
        "schema": SCHEMA,
        "study": STUDY,
        "arm": "H",
        "sources": list(SOURCES),
        "order_seed": seed,
        "order_rule": "ascending sha256(order_seed + ':' + strategy_digest)",
        "cycle": "a run needing more than len(entries) submissions continues from position 0",
        "entries": ordered,
    }
    if version == "v2":
        # v1's body is unchanged (its digest is pinned); v2 names itself.
        body["version"] = "v2"
        body["sources"] = [*SOURCES, GRID]
        body["supersedes"] = "library-v1"
    return {**body, "library_digest": sha256(canonical(body))}


def render(document):
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rate_study.library")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    for version in VERSIONS:
        text = render(build(version))
        path = out(version)
        if args.check:
            if not path.exists() or path.read_text() != text:
                print(path.name + " is stale: rerun without --check")
                return 1
        else:
            path.write_text(text)
        print(version, json.loads(text)["library_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
