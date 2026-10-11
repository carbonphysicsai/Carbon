"""Print unadopted criteria from actual spec/worker bytes; no solver invocation."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = "docs/development/challenge_pipeline/code-verification/specs.json"


def prepare(kind, root=ROOT):
    source = (root / SPEC).read_bytes()
    spec = json.loads(source)
    rows = [row for row in spec["tests"] if row["kind"] == kind]
    if len(rows) != 1 or rows[0]["format"] != "carbon.code-verification.fields.v1":
        raise ValueError(
            "registered field-export test required; heat uses #1030's native result contract"
        )
    row = rows[0]
    # The closed, repo-owned registry names the worker, never an untrusted path.
    worker = (root / row["worker"]).read_bytes()
    return {
        "kind": row["kind"],
        "family": row["family"],
        "h": row["h"],
        "t": row["t"],
        "order_band": row["order_band"],
        "status": "HUMAN_INPUT",
        "spec_digest": "sha256:" + hashlib.sha256(source).hexdigest(),
        "adapter_digest": "sha256:" + hashlib.sha256(worker).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind")
    args = parser.parse_args()
    print(json.dumps(prepare(args.kind), indent=2))


if __name__ == "__main__":
    main()
