"""EXAM_BATCH_QA_SPEC_20261020: image, then straddle, then the seeded
spot-check; fail closed without U; only {digest, verdict} is public."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

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
        "unresolved_cases": {},
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
        # Logged with their reference values (host-only record).
        "unresolved_cases": {"c2": 95.05, "c3": 94.95},
    }
    assert record["failure"] is None  # 2 of 6 is a third on each side


def test_more_unresolved_than_the_allowed_fraction_fails():
    """Motor (Validator, 2026-10-20): more than 1/3 of a batch within U stops."""
    values = [90.0, 91.0, 95.05, 94.95, 95.02, 99.0, 100.0, 101.0, 89.0]
    batch = _batch(values)
    spec = {**SPEC, "unresolved_max_fraction": 1 / 3, "straddle_min_fraction": 0.2}
    assert qa.judge(batch, spec, _fine(batch))["failure"] is None  # 3 of 9
    over = _batch(values[:3] + [95.0, 94.99] + values[3:])
    record = qa.judge(over, spec, _fine(over))
    assert record["failure"] == "unresolved_over_fraction:peak"  # 5 of 11
    assert len(record["straddle"]["peak"]["unresolved_cases"]) == 5
    # Without the field, no such stop (the other Challenges' rule).
    assert (
        qa.judge(over, {**SPEC, "straddle_min_fraction": 0.2}, _fine(over))["failure"]
        is None
    )


def test_motor_u_is_the_validators_rounded_up_bands():
    import json

    u = qa.registered_u("electric-motor-magnetics")
    assert u == {"mean_torque_nm": 0.0052, "ripple_fraction": 0.026}
    path, _pin = qa.U_RECORDS["electric-motor-magnetics"]
    record = json.loads((ROOT / path).read_text())
    # Each U covers its own measured full-range band (rounded up, never down).
    for q, band in record["bands"].items():
        assert u[q] >= band["largest_full_range"]


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


def test_registered_u_is_read_by_sha_and_refuses_a_change(tmp_path, monkeypatch):
    assert qa.registered_u("f08-ribbed-bracket") == {
        "static_tip_mm_per_n": 6.7e-07,
        "worst_dynamic_mm_per_n": 3.9e-05,
    }
    assert qa.registered_u("f02") == {"peak_top_c": 0.012}
    path, _pin = qa.U_RECORDS["f02"]
    changed = tmp_path / path
    changed.parent.mkdir(parents=True)
    changed.write_bytes((ROOT / path).read_bytes() + b" ")
    try:
        qa.registered_u("f02", root=tmp_path)
    except ValueError as exc:
        assert "differs" in str(exc)
    else:
        raise AssertionError("a changed record was accepted")
    try:
        qa.registered_u("motor")
    except ValueError as exc:
        assert "no registered" in str(exc)
    spec = {
        "challenge": "f02",
        "verified_image_digests": [IMAGE],
        "limits": [{"quantity": "peak_top_c", "threshold": 95.0, "feasible": "<="}],
        "u": "registered",
    }
    batch = {
        "batch_digest": "f02-b",
        "image_digest": IMAGE,
        "cases": [
            {"case_id": f"c{i}", "quantities": {"peak_top_c": v}}
            for i, v in enumerate([90.0, 93.0, 94.5, 95.5, 97.0, 100.0])
        ],
    }
    fine = {
        i: {"peak_top_c": c["quantities"]["peak_top_c"] + 0.005}
        for c in batch["cases"]
        for i in [c["case_id"]]
        if i in qa.spot_case_ids(batch)
    }
    assert qa.judge(batch, spec, fine)["verdict"] == "PASS"


def test_the_f08_record_regenerates_from_its_committed_script_and_ladder():
    import json
    import subprocess
    import sys

    folder = ROOT / "docs/development/evidence/f08-near-limit-public-20261020"
    out = subprocess.run(
        [
            sys.executable,
            str(folder / "reference-uncertainty/f08_reference_uncertainty.py.txt"),
            str(folder / "ladder-observed.json"),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    committed = json.loads(
        (folder / "reference-uncertainty/f08-reference-uncertainty.json").read_text()
    )
    assert json.loads(out) == committed


def _motor_batch():
    values = [
        (4.5, 0.10), (4.6, 0.12), (4.7, 0.20), (4.8, 0.15), (3.0, 0.50), (3.1, 0.60),
        (3.2, 0.45), (3.3, 0.40), (4.9, 0.11), (3.4, 0.55), (5.0, 0.18), (2.9, 0.70),
    ]  # fmt: skip
    return {
        "batch_digest": "m1",
        "image_digest": IMAGE,
        "cases": [
            {
                "case_id": f"m{i}",
                "quantities": {"mean_torque_nm": t, "ripple_fraction": r},
            }
            for i, (t, r) in enumerate(values)
        ],
    }


MOTOR_SPEC = {
    "challenge": "electric-motor-magnetics",
    "verified_image_digests": [IMAGE],
    "limits": [
        {"quantity": "mean_torque_nm", "threshold": 4.0, "feasible": ">="},
        {"quantity": "ripple_fraction", "threshold": 0.30, "feasible": "<="},
    ],
    "u": "registered",
}


def test_a_motor_spec_cannot_drop_or_change_the_pinned_unresolved_stop():
    """The 1/3 stop is in Motor's pinned U record (Validator): a spec that
    omits it, or sets another value, is refused before any other check."""
    assert qa.registered_unresolved_max("electric-motor-magnetics") == 1 / 3
    batch = _motor_batch()
    by = {c["case_id"]: c["quantities"] for c in batch["cases"]}
    fine = {i: dict(by[i]) for i in qa.spot_case_ids(batch)}
    omitted = qa.judge(batch, MOTOR_SPEC, fine)
    assert omitted["verdict"] == "FAIL"
    assert omitted["failure"] == "spec_unresolved_max_fraction"
    changed = qa.judge(batch, {**MOTOR_SPEC, "unresolved_max_fraction": 0.5}, fine)
    assert changed["failure"] == "spec_unresolved_max_fraction"
    kept = qa.judge(batch, {**MOTOR_SPEC, "unresolved_max_fraction": 1 / 3}, fine)
    assert kept["verdict"] == "PASS" and kept["failure"] is None
    # A record without the field (F02, F08) imposes no such stop.
    assert qa.registered_unresolved_max("f02") is None


COOLING_SPEC = {
    "challenge": "chip-cold-plate",
    "verified_image_digests": [IMAGE],
    "limits": [
        {"quantity": "die_peak_c", "threshold": 100.0, "feasible": "<="},
        {"quantity": "hydraulic_w", "threshold": 0.25, "feasible": "<="},
    ],
    "u": "registered",
    "unresolved_max_cases": 1,
    "refine_unresolved": {"mesh_family": "graded-hotspot-v1", "resolution": 4.0},
}


def _cooling_batch(overrides=None):
    die = [
        95.0,
        96.0,
        97.0,
        98.0,
        99.0,
        94.0,
        93.0,
        92.0,
        103.0,
        104.0,
        105.0,
        106.0,
        107.0,
        108.0,
        102.0,
        101.0,
    ]
    hyd = [
        0.20,
        0.21,
        0.22,
        0.23,
        0.30,
        0.31,
        0.32,
        0.33,
        0.19,
        0.18,
        0.17,
        0.16,
        0.35,
        0.36,
        0.37,
        0.38,
    ]
    cases = [
        {"case_id": f"g{i:02d}", "quantities": {"die_peak_c": d, "hydraulic_w": h}}
        for i, (d, h) in enumerate(zip(die, hyd, strict=True))
    ]  # fmt: skip
    for case_id, q, value in overrides or ():
        next(c for c in cases if c["case_id"] == case_id)["quantities"][q] = value
    return {"batch_digest": "cool-1", "image_digest": IMAGE, "cases": cases}


def _fine_same(batch, extra=None):
    by = {c["case_id"]: dict(c["quantities"]) for c in batch["cases"]}
    fine = {i: by[i] for i in qa.spot_case_ids(batch)}
    fine.update(extra or {})
    return fine


def test_cooling_u_is_registered_with_a_relative_hydraulic_term():
    assert qa.registered_u("chip-cold-plate") == {
        "die_peak_c": 0.037,
        "hydraulic_w": {"relative": 0.03},
    }
    assert qa.u_at({"relative": 0.03}, 0.25) == pytest.approx(0.0075)
    assert qa.registered_rules("chip-cold-plate") == {
        "unresolved_max_cases": 1,
        "refine_unresolved": {"mesh_family": "graded-hotspot-v1", "resolution": 4.0},
    }


def test_a_clean_cooling_grid_passes():
    batch = _cooling_batch()
    record = qa.judge(batch, COOLING_SPEC, _fine_same(batch))
    assert record["verdict"] == "PASS", record["failure"]


def test_hydraulic_within_three_percent_of_its_own_value_is_unresolved():
    # 0.244 is 0.006 below 0.25: within 3% of 0.244 (0.00732).
    batch = _cooling_batch([("g00", "hydraulic_w", 0.244)])
    within = qa.unresolved_cases(
        batch, {**COOLING_SPEC, "u": qa.registered_u("chip-cold-plate")}
    )
    assert within["hydraulic_w"] == {"g00": 0.244} and within["die_peak_c"] == {}


def test_two_cells_within_u_stop_the_family():
    batch = _cooling_batch(
        [("g00", "die_peak_c", 99.98), ("g01", "hydraulic_w", 0.249)]
    )
    record = qa.judge(batch, COOLING_SPEC, _fine_same(batch))
    assert record["failure"] == "unresolved_over_count"


def test_one_cell_within_u_is_re_solved_finer():
    spot = qa.spot_case_ids(_cooling_batch())
    cell = next(f"g{i:02d}" for i in range(16) if f"g{i:02d}" not in spot)
    batch = _cooling_batch([(cell, "die_peak_c", 99.98)])
    assert qa.spot_case_ids(batch) == spot  # the digest, not the values, seeds it
    hydraulic = next(c for c in batch["cases"] if c["case_id"] == cell)["quantities"][
        "hydraulic_w"
    ]

    def judged(die):
        extra = {cell: {"die_peak_c": die, "hydraulic_w": hydraulic}}
        return qa.judge(batch, COOLING_SPEC, _fine_same(batch, extra))

    resolved = judged(99.95)
    assert resolved["verdict"] == "PASS", resolved["failure"]
    assert resolved["straddle"]["die_peak_c"]["refined_cases"] == {cell: 99.95}
    # Still within U one level finer: the batch is redrawn.
    assert judged(100.01)["failure"] == "unresolved_after_refine:die_peak_c"
    missing = qa.judge(batch, COOLING_SPEC, _fine_same(batch))
    assert missing["failure"] == "refine_missing:die_peak_c"


def test_a_cooling_spec_cannot_drop_or_change_its_pinned_rules():
    batch = _cooling_batch()
    for rule in ("unresolved_max_cases", "refine_unresolved"):
        spec = {k: v for k, v in COOLING_SPEC.items() if k != rule}
        assert qa.judge(batch, spec, _fine_same(batch))["failure"] == f"spec_{rule}"
    changed = {**COOLING_SPEC, "unresolved_max_cases": 2}
    assert (
        qa.judge(batch, changed, _fine_same(batch))["failure"]
        == "spec_unresolved_max_cases"
    )


def test_a_hydraulic_spot_step_above_three_percent_fails():
    batch = _cooling_batch()
    spot = qa.spot_case_ids(batch)[0]
    by = {c["case_id"]: c["quantities"] for c in batch["cases"]}
    step = {spot: {**by[spot], "hydraulic_w": by[spot]["hydraulic_w"] * 1.04}}
    record = qa.judge(batch, COOLING_SPEC, _fine_same(batch, step))
    assert record["failure"] == f"spot_check:{spot}:hydraulic_w"
