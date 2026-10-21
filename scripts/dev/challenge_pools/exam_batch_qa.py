#!/usr/bin/env python3
"""Exam batch QA on the AX42, before a sealed batch joins a Challenge's pool.

Implements EXAM_BATCH_QA_SPEC_20261020 (Carbon Validator, owner-approved) for
any Challenge; nothing here chooses a value. Host-only: the record carries
sealed case values. Only `{batch_digest, verdict}` may be shown publicly.

    exam_batch_qa.py select BATCH.json SPEC.json        # the 3 spot-check case ids
    exam_batch_qa.py judge  BATCH.json SPEC.json FINE.json OUT.json

BATCH.json: {"batch_digest", "image_digest",
             "cases": [{"case_id", "quantities": {q: value}}]}
SPEC.json:  {"challenge", "verified_image_digests": [...],
             "limits": [{"quantity", "threshold", "feasible": "<=" | ">="}],
             "u": {q: number or null} | "registered",  # the Challenge's U record
             "straddle_min_fraction": 1/3 unless the owner set another,
             "unresolved_max_fraction": optional; e.g. Motor's 1/3}
FINE.json:  {case_id: {q: value}} for the selected cases, solved one ratio-2
            refinement finer on the same image.

Checks, in order, stopping at the first failure (no partial publish, no retry
with the same batch):
1. image: the batch's image digest is a pinned, code-verified one
   (`image_not_verified`). A rebuilt image enters `verified_image_digests`
   only after its byte-identical verification-deck proof; that is upstream.
2. straddle, per limit: cases within U of the threshold are UNRESOLVED and
   count on neither side; each side needs at least the minimum fraction of
   all cases (`straddle_short:<q>`). No registered U fails closed
   (`u_unregistered:<q>`): an unresolved band cannot be drawn without it.
   With `unresolved_max_fraction`, more UNRESOLVED cases than that fraction
   fail (`unresolved_over_fraction:<q>`; Validator, Motor U decision
   2026-10-20). Each UNRESOLVED case's reference value is logged in the
   host-only record.
3. spot-check: 3 cases drawn with the seed sha256(batch digest); for every
   limit quantity, |fine - reference| <= U and no label flips
   (`spot_check:<case>:<q>`). A label is a side only where the reference is
   resolved (more than U from the threshold); an UNRESOLVED case has no side
   to flip, so crossing the threshold inside U is not a flip.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from pathlib import Path

SCHEMA = "carbon.exam-batch-qa.v1"
REPOSITORY = Path(__file__).resolve().parents[3]
#: Validator-approved reference-uncertainty records (2026-10-20), read by sha.
#: `"u": "registered"` in a spec takes U from here; no other source is read.
U_RECORDS = {
    "f08-ribbed-bracket": (
        "docs/development/evidence/f08-near-limit-public-20261020/reference-uncertainty/f08-reference-uncertainty.json",
        "19bb06c321c5294a9f598bfc3ca3998d9a4ba1f45500117127cd8e20620d4359",
    ),
    "f02": (
        "docs/development/evidence/f02-cold-pack-20261020/reference-uncertainty/f02-reference-uncertainty.json",
        "e2262bf8eeca845c2b33d0e32b5f184751693a1771d9bd156cadd5613ac2dc6c",
    ),
    # Motor: bounded full-range bands (VALIDATOR_MOTOR_U_DECISION_20261020).
    "electric-motor-magnetics": (
        "docs/development/evidence/motor-reference-uncertainty-20261020/motor-reference-uncertainty.json",
        "04c68c4c0ddb612c2c5729548a6d6e42b849aaab87574dfdb146b10ba4a4b94a",
    ),
}
SPOT_CASES = 3
PASS, FAIL = "PASS", "FAIL"


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _finite(x) -> bool:
    return type(x) in (int, float) and math.isfinite(x)


def side(value, limit) -> str:
    feasible = (
        value <= limit["threshold"]
        if limit["feasible"] == "<="
        else (value >= limit["threshold"])
    )
    return "feasible" if feasible else "infeasible"


def registered_u(challenge: str, root: Path = REPOSITORY) -> dict:
    """U per limit quantity from the Challenge's pinned record; refuses a
    missing record or changed bytes (QA then fails closed upstream)."""
    if challenge not in U_RECORDS:
        raise ValueError(f"no registered reference uncertainty for {challenge}")
    path, pin = U_RECORDS[challenge]
    raw = (Path(root) / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError(f"reference-uncertainty record for {challenge} differs")
    return dict(json.loads(raw)["U"])


def spot_case_ids(batch) -> list[str]:
    """The seeded draw: sha256(batch digest) seeds the choice of 3 cases."""
    seed = int(hashlib.sha256(batch["batch_digest"].encode()).hexdigest(), 16)
    ids = sorted(c["case_id"] for c in batch["cases"])
    if len(ids) < SPOT_CASES:
        raise ValueError("a batch needs at least 3 cases")
    return sorted(random.Random(seed).sample(ids, SPOT_CASES))


def _straddle(batch, spec):
    counts, fraction = {}, spec.get("straddle_min_fraction", 1 / 3)
    n = len(batch["cases"])
    for limit in spec["limits"]:
        q, u = limit["quantity"], spec["u"].get(limit["quantity"])
        if not _finite(u) or u < 0:
            return counts, f"u_unregistered:{q}"
        row = {"feasible": 0, "infeasible": 0, "unresolved": 0, "unresolved_cases": {}}
        for case in batch["cases"]:
            value = case["quantities"].get(q)
            if not _finite(value):
                return counts, f"straddle_short:{q}"
            if abs(value - limit["threshold"]) <= u:
                row["unresolved"] += 1
                row["unresolved_cases"][case["case_id"]] = value
            else:
                row[side(value, limit)] += 1
        counts[q] = row
        most = spec.get("unresolved_max_fraction")
        if most is not None and row["unresolved"] > most * n:
            return counts, f"unresolved_over_fraction:{q}"
        if min(row["feasible"], row["infeasible"]) < fraction * n:
            return counts, f"straddle_short:{q}"
    return counts, None


def _spot(batch, spec, fine):
    by_id = {c["case_id"]: c for c in batch["cases"]}
    rows = []
    for case_id in spot_case_ids(batch):
        for limit in spec["limits"]:
            q, u = limit["quantity"], spec["u"].get(limit["quantity"])
            ref = by_id[case_id]["quantities"][q]
            value = (fine.get(case_id) or {}).get(q)
            resolved = _finite(u) and abs(ref - limit["threshold"]) > u
            flip = (
                resolved and _finite(value) and side(value, limit) != side(ref, limit)
            )
            ok = _finite(u) and _finite(value) and abs(value - ref) <= u and not flip
            rows.append(
                {
                    "case_id": case_id,
                    "quantity": q,
                    "abs_delta": abs(value - ref) if _finite(value) else None,
                    "u": u,
                    "reference_resolved": resolved,
                    "label_flip": bool(flip),
                }
            )
            if not ok:
                return rows, f"spot_check:{case_id}:{q}"
    return rows, None


def judge(batch, spec, fine) -> dict:
    """The host-only QA record; `public()` gives what may be shown."""
    if spec.get("u") == "registered":
        spec = {**spec, "u": registered_u(spec["challenge"])}
    record = {
        "schema": SCHEMA,
        "challenge": spec["challenge"],
        "batch_digest": batch["batch_digest"],
        "image_digest": batch["image_digest"],
        "cases": len(batch["cases"]),
        "straddle": None,
        "spot_check": None,
        "verdict": FAIL,
        "failure": None,
    }
    if batch["image_digest"] not in spec["verified_image_digests"]:
        record["failure"] = "image_not_verified"
    else:
        record["straddle"], failure = _straddle(batch, spec)
        if failure is None:
            record["spot_check"], failure = _spot(batch, spec, fine)
        record["failure"] = failure
        record["verdict"] = PASS if failure is None else FAIL
    record["sha256"] = hashlib.sha256(_canonical(record)).hexdigest()
    return record


def public(record) -> dict:
    return {"batch_digest": record["batch_digest"], "verdict": record["verdict"]}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    if argv[:1] == ["select"] and len(argv) == 3:
        batch, spec = load(argv[1]), load(argv[2])
        if batch["image_digest"] not in spec["verified_image_digests"]:
            print(json.dumps({"stop": "image_not_verified"}))
            return 1
        print(json.dumps({"spot_case_ids": spot_case_ids(batch)}))
        return 0
    if argv[:1] == ["judge"] and len(argv) == 5:
        record = judge(load(argv[1]), load(argv[2]), load(argv[3]))
        Path(argv[4]).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
        print(json.dumps(public(record)))
        return 0 if record["verdict"] == PASS else 1
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
