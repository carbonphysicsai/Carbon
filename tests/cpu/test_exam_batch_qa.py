"""EXAM_BATCH_QA_SPEC_20261020: image, then straddle, then the seeded
spot-check; fail closed without U; only {digest, verdict} is public."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "exam_batch_qa", ROOT / "scripts/dev/challenge_pools/exam_batch_qa.py"
)
qa = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(qa)

IMAGE = "sha256:" + "a" * 64
SPEC = {
    "challenge": "synthetic",
    "verified_image_digests": [IMAGE],
    "limits": [{"quantity": "peak", "threshold": 95.0, "feasible": "<="}],
    "u": {"peak": 0.1},
}


def _batch(values, digest="b1"):
    return {
        "batch_digest": digest,
        "image_digest": IMAGE,
        "cases": [
            {"case_id": f"c{i}", "quantities": {"peak": v}}
            for i, v in enumerate(values)
        ],
    }


STRADDLE = [90.0, 91.0, 92.0, 98.0, 99.0, 100.0]


def _fine(batch, delta=0.01):
    by = {c["case_id"]: c["quantities"]["peak"] for c in batch["cases"]}
    return {i: {"peak": by[i] + delta} for i in qa.spot_case_ids(batch)}


def test_a_good_batch_passes_and_only_digest_and_verdict_are_public():
    batch = _batch(STRADDLE)
    record = qa.judge(batch, SPEC, _fine(batch))
    assert record["verdict"] == "PASS" and record["failure"] is None
    assert record["straddle"]["peak"] == {
        "feasible": 3,
        "infeasible": 3,
        "unresolved": 0,
    }
    assert len({r["case_id"] for r in record["spot_check"]}) == 3
    assert qa.public(record) == {"batch_digest": "b1", "verdict": "PASS"}


def test_the_spot_draw_is_seeded_by_the_batch_digest():
    a, b = _batch(STRADDLE * 3, "x"), _batch(STRADDLE * 3, "y")
    assert qa.spot_case_ids(a) == qa.spot_case_ids(_batch(STRADDLE * 3, "x"))
    assert qa.spot_case_ids(a) != qa.spot_case_ids(b)


def test_checks_run_in_order_and_stop_at_the_first_failure():
    batch = dict(_batch(STRADDLE), image_digest="sha256:" + "b" * 64)
    record = qa.judge(batch, SPEC, {})
    assert record["failure"] == "image_not_verified"
    assert record["straddle"] is None and record["spot_check"] is None
    lopsided = _batch([90.0, 91.0, 92.0, 93.0, 94.0, 99.0])
    record = qa.judge(lopsided, SPEC, {})
    assert record["failure"] == "straddle_short:peak" and record["spot_check"] is None


def test_cases_within_u_are_unresolved_and_count_on_neither_side():
    batch = _batch([90.0, 91.0, 95.05, 94.95, 99.0, 100.0])
    record = qa.judge(batch, SPEC, _fine(batch))
    assert record["straddle"]["peak"] == {
        "feasible": 2,
        "infeasible": 2,
        "unresolved": 2,
    }
    assert record["failure"] is None  # 2 of 6 is a third on each side


def test_no_registered_u_fails_closed():
    batch = _batch(STRADDLE)
    record = qa.judge(batch, {**SPEC, "u": {"peak": None}}, _fine(batch))
    assert record["verdict"] == "FAIL" and record["failure"] == "u_unregistered:peak"


def test_a_spot_check_outside_u_or_a_side_flip_fails():
    batch = _batch(STRADDLE)
    far = qa.judge(batch, SPEC, _fine(batch, delta=0.5))
    assert far["failure"].startswith("spot_check:")
    near = _batch([90.0, 91.0, 95.12, 98.0, 99.0, 100.0], "flip")
    fine = {
        i: {"peak": (94.99 if i == "c2" else c["quantities"]["peak"])}
        for c in near["cases"]
        for i in [c["case_id"]]
        if i in qa.spot_case_ids(near)
    }
    record = qa.judge(near, {**SPEC, "u": {"peak": 0.2}}, fine)
    assert "c2" in qa.spot_case_ids(near)  # the seeded draw includes c2
    # c2 (95.12) is within U = 0.2 of 95: UNRESOLVED, so crossing to 94.99
    # inside U is not a label flip, and the batch passes.
    assert record["failure"] is None
    row = next(r for r in record["spot_check"] if r["case_id"] == "c2")
    assert row["reference_resolved"] is False and row["label_flip"] is False
    missing = qa.judge(batch, SPEC, {})
    assert missing["failure"].startswith("spot_check:")


def test_the_record_carries_its_own_digest():
    batch = _batch(STRADDLE)
    record = qa.judge(batch, SPEC, _fine(batch))
    body = {k: v for k, v in record.items() if k != "sha256"}
    assert record["sha256"] == qa.hashlib.sha256(qa._canonical(body)).hexdigest()
