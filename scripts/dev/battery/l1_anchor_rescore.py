"""Rescore recovered practice outputs under the Graphite frozen rule (Level 1 Q1 same-basis check).

The six Launchpad rehearsal anchors in the Level 1 Q1 panel carried a practice-feedback v3 aggregate
whose rule was unnamed, so the Test Lead excluded them from the gate metric. Their stored practice
outputs were recovered. This reads each recovered `predictions.json`, checks that the `export.stream`
digest equals the recorded `output_digest`, scores the predictions with the Graphite frozen rule
(`BatteryPracticeRule.score`, the 200 public PRACTICE cases) and writes a path-free record:

    python -m scripts.dev.battery.l1_anchor_rescore --anchors ANCHORS.json --root REPO --out q1_rescore.L1.json

`ANCHORS.json` is `{"rows": [{"submission_id", "lane", "practice": [{"score", "output_digest"}],
"practice_outputs": {"predictions", "export_stream"}}]}`. Public data only; nothing is trained, no pod
is used. The record keeps digests and scores, never a host path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

CHALLENGE = "battery-fastcharge-ageing-development-v1"
SCHEMA = "carbon.graphite.l1-anchor-rescore.v1"


def sha256_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def member_name(row):
    """`minerH-bsub-8df17aba-s0`: the lane, the submission's short id and the seed suffix."""
    return f"{row['lane']}-{row['submission_id'][:13]}-s0"


def rescore(anchors, root):
    from carbon.battery.practice import PracticeSet
    from carbon.challenge_pipeline.readiness.model import digest
    from carbon.challenge_validator import scoring

    rule = scoring.scoring_for(CHALLENGE).frozen_rule(root)
    rows = []
    for row in sorted(anchors["rows"], key=member_name):
        outputs = row["practice_outputs"]
        recorded = row["practice"][0]
        stream = sha256_of(outputs["export_stream"])
        _, summary = rule.score(json.loads(Path(outputs["predictions"]).read_bytes()))
        rows.append(
            {
                "member": member_name(row),
                "submission_id": row["submission_id"],
                "predictions_sha256": sha256_of(outputs["predictions"]),
                "export_stream_sha256": stream,
                "recorded_output_digest": recorded["output_digest"],
                "output_digest_matches": stream == recorded["output_digest"],
                "recorded_score": recorded["score"],
                "recomputed_score": summary["score"],
                "n_scored": summary["n_scored"],
                "n_missing": summary["n_missing"],
                "eligible": summary["eligible"],
            }
        )
    return {
        "schema": SCHEMA,
        "challenge": CHALLENGE,
        "rule": "Graphite frozen rule: BatteryPracticeRule.score on the public PRACTICE cases",
        "rule_identity_digest": digest(rule.identity),
        "practice_source_sha256": PracticeSet.load(root).source_sha256,
        "lower_is_better": True,
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m scripts.dev.battery.l1_anchor_rescore"
    )
    parser.add_argument("--anchors", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(args.root).resolve()))
    anchors = json.loads(Path(args.anchors).read_bytes())
    record = rescore(anchors, args.root)
    anchors_bytes = Path(args.anchors).read_bytes()
    record["anchors_source_sha256"] = (
        "sha256:" + hashlib.sha256(anchors_bytes).hexdigest()
    )
    Path(args.out).write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    bad = [r["member"] for r in record["rows"] if not r["output_digest_matches"]]
    if bad:
        print(
            "export.stream digest differs from the recorded output_digest: "
            + ", ".join(bad)
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
