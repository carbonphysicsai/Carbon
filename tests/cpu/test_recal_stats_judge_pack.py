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


# --- gated rebuilds: a null total because a hard gate failed ---------------------------------------------------------------

F08_SEEDS = [
    0.42181190434059457,
    0.4224448318,
    0.4152694308,
    None,
    None,
    None,
    0.4200110,
    None,
    0.4224263,
    None,
]


def _gate_legs(a=0.4, d=0.5, outcome="MANDATORY_GATE_FAILED"):
    return {"A": a, "D": d, "decision_outcome": outcome}


def _f08_doc(seeds=None, gated_at=(3, 4, 5, 7, 9), legs=None):
    """The real F08 shape: a panel of one member with ten bit-identical totals, and ten control seeds, some gated."""
    seeds = list(F08_SEEDS if seeds is None else seeds)
    total = 0.42181190434059457
    member = {
        "reference_fingerprint": H("a"),
        "seed0_totals": [total] * 10,
        "state_digests": [H("1")] * 10,
        "within_noise": False,
        "seed0_legs": [_legs(total, total)] * 10,
    }
    control_legs = [
        _gate_legs() if i in gated_at else _legs(t, t) for i, t in enumerate(seeds)
    ]
    return {
        "schema": rs.SCHEMA_IN,
        "challenges": {
            "F08": {
                "pack_digest": H("b"),
                "class_record_digest": H("c"),
                "control_basis_bit_identical": "ten bit-identical",
                "control_basis_within_noise": "smallest sigma within noise",
                "panel": ["FC"],
                "members": {"FC": member},
                "control_seed_totals": {"FC": seeds},
                "control_seed_legs": {"FC": legs if legs is not None else control_legs},
            }
        },
    }


def test_the_real_f08_shape_gated_seeds_are_excluded_and_counted(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    out = rs.measure(_f08_doc(), {"F08": rs.load_judge_pack(path)})
    f08 = out["challenges"]["F08"]
    assert f08["sigma"] == 0.0
    assert f08["seed_spread"] == pytest.approx(0.0071754010, abs=1e-10)
    assert f08["value"] == pytest.approx(0.0071754010, abs=1e-10)
    assert f08["gated"] == {"by_member": {"FC": 0}, "control_seeds": 5}
    assert f08["minimum_failed"]["control_seeds"] == 0
    assert f08["control"]["entry_id"] == "FC"


def test_the_gated_count_is_in_the_measurement_digest(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    packs = {"F08": rs.load_judge_pack(path)}
    first = rs.measure(_f08_doc(), packs)
    again = rs.measure(_f08_doc(), packs)
    other = rs.measure(
        _f08_doc(seeds=F08_SEEDS[:3] + [0.4201] + F08_SEEDS[4:], gated_at=(4, 5, 7, 9)),
        packs,
    )
    assert first["measurement_digest"] == again["measurement_digest"]
    assert other["challenges"]["F08"]["gated"]["control_seeds"] == 4
    assert other["measurement_digest"] != first["measurement_digest"]


def test_a_null_total_without_a_gate_failure_is_a_refusal_not_gated(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    # legs that explain every number and every gated rebuild, except rebuild 9: a null whose legs look normal
    legs = [
        _gate_legs() if i in (3, 4, 5, 7) else _legs(t, t)
        for i, t in enumerate(F08_SEEDS)
    ]
    legs[9] = _legs(0.42, 0.42)
    with pytest.raises(rs.StatsError, match="missing data is not gated"):
        rs.measure(_f08_doc(legs=legs), {"F08": rs.load_judge_pack(path)})
    # the same null with no legs entry at all, and with a non-dict entry
    for entry in (None, "gated"):
        broken = list(legs)
        broken[9] = entry
        with pytest.raises(rs.StatsError, match="not gated"):
            rs.measure(_f08_doc(legs=broken), {"F08": rs.load_judge_pack(path)})


def test_nulls_are_refused_without_a_judge_pack():
    with pytest.raises(rs.StatsError, match="finite numbers"):
        rs.measure(_f08_doc())


def test_nine_gated_rows_leave_one_kept_and_are_refused(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    seeds = [0.4218] + [None] * 9
    with pytest.raises(rs.StatsError, match="only 1 rebuild"):
        rs.measure(
            _f08_doc(seeds=seeds, gated_at=tuple(range(1, 10))),
            {"F08": rs.load_judge_pack(path)},
        )
    # eight gated leave two kept: allowed
    seeds = [0.4218, 0.4220] + [None] * 8
    out = rs.measure(
        _f08_doc(seeds=seeds, gated_at=tuple(range(2, 10))),
        {"F08": rs.load_judge_pack(path)},
    )
    assert out["challenges"]["F08"]["gated"]["control_seeds"] == 8


@pytest.mark.parametrize(
    "legs",
    [
        {"A": 0.4, "D": 0.5, "decision_outcome": "GATE_FAILED"},
        {
            "A": 0.4,
            "D": 0.5,
            "decision_outcome": "VERIFIED_FEASIBLE",
            "status": "MANDATORY_GATE_FAILED",
        },
        {
            "A": 0.4,
            "D": 0.5,
            "decision_outcome": "POOL_GRADED",
            "gates": {"speed": "FAIL"},
        },
        {
            "A": 0.4,
            "D": 0.5,
            "decision_outcome": "POOL_GRADED",
            "gates": {"physics_pool": False},
        },
    ],
)
def test_every_shape_of_a_gate_failure_is_recognised(legs):
    assert rs.gate_failed(legs) is True


@pytest.mark.parametrize(
    "legs",
    [
        None,
        "gated",
        {},
        {"A": 0.4, "D": 0.5, "decision_outcome": "VERIFIED_FEASIBLE"},
        {"A": 0.4, "D": 0.5, "gates": {"speed": "PASS", "physics_pool": True}},
        {"A": 0.4, "D": 0.5, "decision_outcome": "REFERENCE_UNRESOLVED"},
    ],
)
def test_a_normal_or_unreadable_legs_entry_is_not_a_gate_failure(legs):
    assert rs.gate_failed(legs) is False


def test_a_member_whose_official_seed_row_is_gated_is_not_an_eligible_control(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    doc = _f08_doc()
    challenge = doc["challenges"]["F08"]
    good = 0.4218
    second = {
        "reference_fingerprint": H("e"),
        "seed0_totals": [good] * 10,
        "state_digests": [H("2")] * 10,
        "within_noise": False,
        "seed0_legs": [_legs(good, good)] * 10,
    }
    first = challenge["members"]["FC"]
    first["seed0_totals"][0] = None  # the official seed 0 rebuild is gated
    first["seed0_legs"][0] = _gate_legs()
    challenge["members"]["SECOND"] = second
    challenge["panel"] = ["FC", "SECOND"]
    challenge["control_seed_totals"]["SECOND"] = [
        0.4218 + 0.0001 * i for i in range(10)
    ]
    challenge["control_seed_legs"]["SECOND"] = [
        _legs(0.4218 + 0.0001 * i, 0.4218 + 0.0001 * i) for i in range(10)
    ]
    out = rs.measure(doc, {"F08": rs.load_judge_pack(path)})["challenges"]["F08"]
    assert out["control"]["entry_id"] == "SECOND"
    assert out["gated"]["by_member"] == {"FC": 1, "SECOND": 0}
