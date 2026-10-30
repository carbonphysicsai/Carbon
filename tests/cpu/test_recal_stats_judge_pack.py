"""recal_stats --judge-pack: the calibration recals' rows re-judged on the judge pack's leg minimums.

The recals run on CALIBRATION packs (minimums null); minimums only change a row's status, never its legs or total
(dual_score). These tests pin that the re-judge equals scoring the same legs on the judge pack, and what it does to
sigma, the seed spread and the control choice.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import statistics
from pathlib import Path

import pytest
from test_dual_score import fixture as toy_pack

from carbon.scoring import dual_score
from carbon.scoring.engine import ScoreEngine

_spec = importlib.util.spec_from_file_location(
    "recal_stats", Path(__file__).parents[2] / "scripts" / "dev" / "recal_stats.py"
)
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

MIN_A, MIN_D = 0.2, 0.4
W = 0.8


def H(c):
    return c * 64


def _judge(tmp_path, a=MIN_A, d=MIN_D):
    body, _benchmark = toy_pack()
    body["legs"]["A"]["minimum"] = a
    body["legs"]["D"]["minimum"] = d
    path = tmp_path / "judge-score-pack.json"
    raw = json.dumps(body, sort_keys=True).encode()
    path.write_bytes(raw)
    return path, "sha256:" + hashlib.sha256(raw).hexdigest(), body


def _total(a, d):
    return (1 - W) * a + W * d


def _legs(a, d):
    return {"A": a, "D": d, "decision_outcome": "VERIFIED_FEASIBLE"}


def _scored_on_the_judge_pack(body, a, d):
    """The same legs graded on the judge pack by the receiver's own engine."""
    _, benchmark = toy_pack()
    measurements = benchmark["models"][0]["measurements"]
    measurements["A"]["value"], measurements["D"]["value"] = a, d
    row = ScoreEngine.score_dual_benchmark_v4(
        benchmark, dual_score.register_pack(body)
    )["models"][0]
    return row["status"], row["score"]


@pytest.mark.parametrize(
    "a,d",
    [
        (0.9, 0.9),
        (0.2, 0.4),  # exactly the minimums: passes
        (0.1999999, 0.9),
        (0.9, 0.3999999),
        (0.0, 0.0),
        (1.0, 0.45),
    ],
)
def test_the_rejudge_equals_scoring_the_same_legs_on_the_judge_pack(tmp_path, a, d):
    path, _sha, body = _judge(tmp_path)
    pack, _ = rs.load_judge_pack(path)
    got = rs.rejudge(_legs(a, d), pack, "x")
    assert got == _scored_on_the_judge_pack(body, a, d)
    failing = a < MIN_A or d < MIN_D
    assert (got[0] == "REQUIRED_LEG_MINIMUM_FAILED") is failing
    if not failing:
        assert got[1] == pytest.approx(_total(a, d))


def _member(rows, same=True, within=False, fp="a"):
    totals = [_total(a, d) for a, d in rows]
    return {
        "reference_fingerprint": H(fp),
        "seed0_totals": totals,
        "seed0_legs": [_legs(a, d) for a, d in rows],
        "state_digests": [H("1")] * 10 if same else [H(str(i)) for i in range(10)],
        "within_noise": within,
    }


def _doc(members, control_rows=None, panel=None):
    panel = panel or list(members)
    control = next(iter(members))
    rows = control_rows or [(0.5, 0.5)] * 10
    return {
        "schema": rs.SCHEMA_IN,
        "challenges": {
            "Motor": {
                "pack_digest": H("b"),
                "class_record_digest": H("c"),
                "control_basis_bit_identical": "ten bit-identical",
                "control_basis_within_noise": "smallest sigma within noise",
                "panel": panel,
                "members": members,
                "control_seed_totals": {control: [_total(a, d) for a, d in rows]},
                "control_seed_legs": {control: [_legs(a, d) for a, d in rows]},
            }
        },
    }


def _good(offset=0.0):
    return [(0.5 + 0.01 * i + offset, 0.6) for i in range(10)]


def test_rebuilds_below_the_judge_minimums_are_excluded_from_sigma_and_counted(
    tmp_path,
):
    path, sha, _body = _judge(tmp_path)
    rows = _good()
    rows[2] = (0.1, 0.6)  # A below the minimum
    rows[7] = (0.5, 0.3)  # D below the minimum
    doc = _doc({"mgn": _member(rows, same=False, within=True)})
    out = rs.measure(doc, {"Motor": rs.load_judge_pack(path)})
    motor = out["challenges"]["Motor"]
    kept = [_total(a, d) for i, (a, d) in enumerate(rows) if i not in (2, 7)]
    assert motor["sigma"] == pytest.approx(statistics.stdev(kept))
    assert motor["minimum_failed"]["by_member"] == {"mgn": 2}
    header = out["judge_minimums"]["Motor"]
    assert header["source_sha256"] == sha
    assert header["minimums"] == {"A": MIN_A, "D": MIN_D}
    assert header["score_pack_digest"].startswith("sha256:")
    # Without the judge pack the same rows give the calibration sigma over all ten.
    plain = rs.measure(copy.deepcopy(doc))["challenges"]["Motor"]
    assert plain["sigma"] == pytest.approx(
        statistics.stdev([_total(a, d) for a, d in rows])
    )
    assert "minimum_failed" not in plain and "judge_minimums" not in rs.measure(doc)


def test_the_control_seed_spread_ignores_failing_seeds_and_reports_them(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    control_rows = [(0.5, 0.5)] * 8 + [(0.1, 0.5), (0.9, 0.9)]
    doc = _doc({"fc": _member([(0.5, 0.6)] * 10)}, control_rows=control_rows)
    doc["challenges"]["Motor"]["members"]["fc"]["seed0_totals"][1] = _total(0.5, 0.61)
    doc["challenges"]["Motor"]["members"]["fc"]["seed0_legs"][1] = _legs(0.5, 0.61)
    out = rs.measure(doc, {"Motor": rs.load_judge_pack(path)})["challenges"]["Motor"]
    kept = [_total(0.5, 0.5)] * 8 + [_total(0.9, 0.9)]
    assert out["seed_spread"] == pytest.approx(max(kept) - min(kept))
    assert out["minimum_failed"]["control_seeds"] == 1


def test_a_control_whose_official_seed_row_fails_the_minimums_is_not_chosen(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    first = [(0.1, 0.6)] + [(0.5, 0.6)] * 9  # rebuild 0 below the A minimum
    members = {
        "first": _member(first, same=True, fp="d"),
        "second": _member([(0.5, 0.6)] * 10, same=True, fp="e"),
    }
    doc = _doc(members, panel=["first", "second"])
    seeds = [(0.5, 0.6 + 0.01 * i) for i in range(10)]
    for entry in ("first", "second"):
        doc["challenges"]["Motor"]["control_seed_totals"][entry] = [
            _total(a, d) for a, d in seeds
        ]
        doc["challenges"]["Motor"]["control_seed_legs"][entry] = [
            _legs(a, d) for a, d in seeds
        ]
    out = rs.measure(doc, {"Motor": rs.load_judge_pack(path)})["challenges"]["Motor"]
    assert out["control"]["entry_id"] == "second"
    # Without the minimums the first bit-identical member is the control, as before.
    plain = rs.measure(copy.deepcopy(doc))["challenges"]["Motor"]
    assert plain["control"]["entry_id"] == "first"


def test_fewer_than_two_passing_rebuilds_is_refused(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    rows = [(0.1, 0.6)] * 9 + [(0.5, 0.6)]
    doc = _doc({"mgn": _member(rows, same=False, within=True)})
    with pytest.raises(rs.StatsError, match="only 1 rebuild"):
        rs.measure(doc, {"Motor": rs.load_judge_pack(path)})


def test_missing_legs_or_a_total_the_judge_pack_does_not_reproduce_is_refused(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    pack = rs.load_judge_pack(path)
    doc = _doc({"mgn": _member(_good(), same=False, within=True)})
    del doc["challenges"]["Motor"]["members"]["mgn"]["seed0_legs"]
    with pytest.raises(rs.StatsError, match="seed0_legs"):
        rs.measure(doc, {"Motor": pack})
    doc = _doc({"mgn": _member(_good(), same=False, within=True)})
    doc["challenges"]["Motor"]["members"]["mgn"]["seed0_legs"][4]["A"] = None
    with pytest.raises(rs.StatsError, match="numeric A and D"):
        rs.measure(doc, {"Motor": pack})
    doc = _doc({"mgn": _member(_good(), same=False, within=True)})
    doc["challenges"]["Motor"]["members"]["mgn"]["seed0_totals"][4] += 0.01
    with pytest.raises(rs.StatsError, match="not the recorded"):
        rs.measure(doc, {"Motor": pack})


def test_a_judge_pack_for_an_unknown_challenge_is_refused(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    doc = _doc({"mgn": _member(_good(), same=False, within=True)})
    with pytest.raises(rs.StatsError, match="not in the input"):
        rs.measure(doc, {"Cooling": rs.load_judge_pack(path)})


def test_the_command_prints_the_minimums_source_digest_header(tmp_path, capsys):
    path, sha, _body = _judge(tmp_path)
    doc = _doc({"mgn": _member(_good(), same=False, within=True)})
    source, out = tmp_path / "in.json", tmp_path / "out.json"
    source.write_text(json.dumps(doc))
    assert (
        rs.main([str(source), "--out", str(out), "--judge-pack", f"Motor={path}"]) == 0
    )
    captured = capsys.readouterr()
    assert sha in captured.err and "judge-pack minimums" in captured.err
    written = json.loads(out.read_text())
    assert written["judge_minimums"]["Motor"]["source_sha256"] == sha
    assert rs.main([str(source), "--judge-pack", "Motor"]) == 2
    assert (
        rs.main(
            [
                str(source),
                "--judge-pack",
                f"Motor={path}",
                "--judge-pack",
                f"Motor={path}",
            ]
        )
        == 2
    )
