"""SUBMISSION-RATE-STUDY-01 arm H: the frozen, ordered candidate library
(run sheet D.1).

    python scripts/dev/rate_study/library.py          # write library-v1.json
    python scripts/dev/rate_study/library.py --check  # refuse a stale file

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
ORDER_SEED = "SUBMISSION-RATE-STUDY-01/arm-H/library-v1"
SOURCES = ("ev4", "graphite-run5")
OUT = REPOSITORY / "docs/development/evidence/submission-rate-study-01/library-v1.json"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def build():
    from carbon.battery.value import panel

    entries = {}
    for source in SOURCES:
        for label, strategy, _seeds in panel.PANELS[source]:
            digest = sha256(canonical(strategy))
            entry = entries.setdefault(
                digest,
                {"strategy_digest": digest, "strategy": strategy, "sources": []},
            )
            entry["sources"].append({"panel": source, "label": label})

    def rank(entry):
        return hashlib.sha256(
            (ORDER_SEED + ":" + entry["strategy_digest"]).encode("utf-8")
        ).hexdigest()

    ordered = sorted(entries.values(), key=rank)
    for index, entry in enumerate(ordered):
        entry["position"] = index
    body = {
        "schema": SCHEMA,
        "study": STUDY,
        "arm": "H",
        "sources": list(SOURCES),
        "order_seed": ORDER_SEED,
        "order_rule": "ascending sha256(order_seed + ':' + strategy_digest)",
        "cycle": "a run needing more than len(entries) submissions continues from position 0",
        "entries": ordered,
    }
    return {**body, "library_digest": sha256(canonical(body))}


def render(document):
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rate_study.library")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            print("library-v1.json is stale: rerun without --check")
            return 1
        print(json.loads(text)["library_digest"])
        return 0
    OUT.write_text(text)
    print(json.loads(text)["library_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
