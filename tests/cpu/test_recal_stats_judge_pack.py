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
    # The real judge file carries its own top-level pack_digest, which `register_pack` refuses in the body.
    declared = dual_score.register_pack(body)["pack_digest"]
    raw = json.dumps({**body, "pack_digest": declared}, sort_keys=True).encode()
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
    pack = rs.load_judge_pack(path)[0]
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


def test_rebuilds_below_the_judge_minimums_are_counted_and_keep_their_totals(
    tmp_path,
):
    path, sha, _body = _judge(tmp_path)
    rows = _good()
    rows[2] = (0.1, 0.6)  # A below the minimum
    rows[7] = (0.5, 0.3)  # D below the minimum
    doc = _doc({"mgn": _member(rows, same=False, within=True)})
    out = rs.measure(doc, {"Motor": rs.load_judge_pack(path)})
    motor = out["challenges"]["Motor"]
    every = [_total(a, d) for a, d in rows]
    # minimums change a row's status, never its total: all ten are valid rebuild-noise measurements
    assert motor["sigma"] == pytest.approx(statistics.stdev(every))
    assert motor["minimum_failed"]["by_member"] == {"mgn": 2}
    assert motor["gated"] == {"by_member": {"mgn": 0}, "control_seeds": 0}
    header = out["judge_minimums"]["Motor"]
    assert header["source_sha256"] == sha
    assert header["minimums"] == {"A": MIN_A, "D": MIN_D}
    assert header["score_pack_digest"].startswith("sha256:")
    # Without the judge pack the same rows give the same sigma.
    plain = rs.measure(copy.deepcopy(doc))["challenges"]["Motor"]
    assert plain["sigma"] == motor["sigma"]
    assert "minimum_failed" not in plain and "judge_minimums" not in rs.measure(doc)


def test_the_control_seed_spread_keeps_failing_seeds_and_reports_them(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    control_rows = [(0.5, 0.5)] * 8 + [(0.1, 0.5), (0.9, 0.9)]
    doc = _doc({"fc": _member([(0.5, 0.6)] * 10)}, control_rows=control_rows)
    doc["challenges"]["Motor"]["members"]["fc"]["seed0_totals"][1] = _total(0.5, 0.61)
    doc["challenges"]["Motor"]["members"]["fc"]["seed0_legs"][1] = _legs(0.5, 0.61)
    out = rs.measure(doc, {"Motor": rs.load_judge_pack(path)})["challenges"]["Motor"]
    every = [_total(a, d) for a, d in control_rows]
    assert out["seed_spread"] == pytest.approx(max(every) - min(every))
    assert out["minimum_failed"]["control_seeds"] == 1


def test_a_control_whose_official_seed_row_fails_the_minimums_is_still_chosen_and_flagged(
    tmp_path,
):
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
    assert out["control"]["entry_id"] == "first"
    assert out["control_fails_judge_minimums"] is True
    clean = rs.measure(
        _doc(
            {"second": _member([(0.5, 0.6)] * 10, same=True, fp="e")},
            control_rows=[(0.5, 0.5 + 0.01 * i) for i in range(10)],
        ),
        {"Motor": rs.load_judge_pack(path)},
    )["challenges"]["Motor"]
    assert clean["control"]["entry_id"] == "second"
    assert clean["control_fails_judge_minimums"] is False


def test_rows_that_fail_the_minimums_never_count_against_the_two_rebuild_rule(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    rows = [(0.1, 0.6 + 0.01 * i) for i in range(9)] + [(0.5, 0.6)]
    doc = _doc({"mgn": _member(rows, same=False, within=True)})
    out = rs.measure(doc, {"Motor": rs.load_judge_pack(path)})["challenges"]["Motor"]
    assert out["minimum_failed"]["by_member"] == {"mgn": 9}
    assert out["sigma"] == pytest.approx(
        statistics.stdev([_total(a, d) for a, d in rows])
    )


def test_a_minimum_failed_total_must_equal_the_same_legs_scored_without_minimums(
    tmp_path,
):
    path, _sha, _body = _judge(tmp_path)
    rows = _good()
    rows[2] = (0.1, 0.6)
    doc = _doc({"mgn": _member(rows, same=False, within=True)})
    doc["challenges"]["Motor"]["members"]["mgn"]["seed0_totals"][2] += 0.01
    with pytest.raises(rs.StatsError, match="not the recorded"):
        rs.measure(doc, {"Motor": rs.load_judge_pack(path)})


def test_the_real_f08_shape_every_row_failing_minimums_gated_seeds_excluded(tmp_path):
    """Ten bit-identical panel rows, ALL failing the minimums; control seeds gated at 3, 4, 5, 7, 9 and the rest failing."""
    path, _sha, _body = _judge(
        tmp_path, a=0.5, d=0.5
    )  # the totals (about 0.42) are below both
    out = rs.measure(_f08_doc(), {"F08": rs.load_judge_pack(path)})["challenges"]["F08"]
    assert out["control"]["entry_id"] == "FC"
    assert out["sigma"] == 0.0
    assert out["value"] == pytest.approx(F08_VALUE, abs=1e-12)
    assert out["gated"] == {"by_member": {"FC": 0}, "control_seeds": 5}
    assert out["minimum_failed"] == {"by_member": {"FC": 10}, "control_seeds": 5}
    assert out["control_fails_judge_minimums"] is True


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


F08_KEPT = [t for t in F08_SEEDS if t is not None]
# the sample sd (n - 1) of the five kept control seeds, about 0.00304
F08_SD = statistics.stdev(F08_KEPT)
F08_VALUE = 2 * F08_SD


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
    # the range is still reported, for reference
    assert f08["seed_spread"] == pytest.approx(0.0071754010, abs=1e-10)
    assert f08["seed_sd"] == pytest.approx(F08_SD, abs=1e-12)
    assert f08["spread_rule"] == "2sd"
    assert f08["value"] == pytest.approx(F08_VALUE, abs=1e-12)
    assert F08_VALUE == pytest.approx(0.0061, abs=1e-4)
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
    with pytest.raises(rs.StatsError, match="only 1 non-gated rebuild"):
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


# --- the judge pack file in its real shape -------------------------------------------------------------------------------


def test_the_real_judge_file_with_a_top_level_pack_digest_loads_and_is_recorded(
    tmp_path,
):
    path, sha, body = _judge(tmp_path)
    loaded = rs.load_judge_pack(path)
    pack, file_sha, declared = loaded
    assert file_sha == sha and pack == dual_score.register_pack(body)
    assert declared == pack["pack_digest"]
    out = rs.measure(
        _doc({"mgn": _member(_good(), same=False, within=True)}), {"Motor": loaded}
    )
    header = out["judge_minimums"]["Motor"]
    assert header["declared_pack_digest"] == declared
    assert header["declared_pack_digest_matches"] is True
    assert header["score_pack_digest"] == pack["pack_digest"]


def test_a_bare_hex_digest_is_accepted_and_a_mismatch_is_recorded_not_hidden(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    document = json.loads(path.read_text())
    bare = document["pack_digest"].removeprefix("sha256:")
    document["pack_digest"] = bare
    path.write_text(json.dumps(document))
    assert rs.load_judge_pack(path)[2] == "sha256:" + bare
    document["pack_digest"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(document))
    loaded = rs.load_judge_pack(path)
    out = rs.measure(
        _doc({"mgn": _member(_good(), same=False, within=True)}), {"Motor": loaded}
    )
    assert out["judge_minimums"]["Motor"]["declared_pack_digest_matches"] is False


@pytest.mark.parametrize("value", ["abc", "sha256:xyz", 7, None, "", "A" * 64])
def test_a_malformed_pack_digest_in_the_judge_file_is_refused(tmp_path, value):
    path, _sha, _body = _judge(tmp_path)
    document = json.loads(path.read_text())
    document["pack_digest"] = value
    path.write_text(json.dumps(document))
    with pytest.raises(rs.StatsError, match="pack_digest"):
        rs.load_judge_pack(path)


def test_a_judge_file_without_a_digest_still_loads(tmp_path):
    path, _sha, body = _judge(tmp_path)
    path.write_text(json.dumps(body))
    loaded = rs.load_judge_pack(path)
    assert len(loaded) == 2


# --- OWNER-CROWN-MARGIN-2SD-01: the seed term is 2 x the sample sd ---------------------------------------------------------

MOTOR_SEEDS = [
    0.23704820689755804,
    None,
    0.2471802603356559,
    0.23898016572385053,
    0.24386670529535648,
    0.24565049761585236,
    0.24846615332646735,
    0.2411177586352313,
    0.2465566893723074,
    0.24612368545844515,
]
F02_SEEDS = [
    0.4700923055632988,
    0.45000658230108453,
    0.45970616990913743,
    0.5009238001644356,
    0.5122679997277158,
    0.48545056366406475,
    0.44845071370806344,
    0.4499675285093288,
    0.48623923530858726,
    0.4493821989276442,
]


def test_the_motor_shape_one_gated_seed_value_is_two_sd_of_the_nine_kept(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    out = rs.measure(
        _f08_doc(seeds=MOTOR_SEEDS, gated_at=(1,)), {"F08": rs.load_judge_pack(path)}
    )["challenges"]["F08"]
    kept = [t for t in MOTOR_SEEDS if t is not None]
    assert out["gated"]["control_seeds"] == 1
    assert out["seed_sd"] == pytest.approx(statistics.stdev(kept), abs=1e-12)
    assert out["value"] == pytest.approx(2 * statistics.stdev(kept), abs=1e-12)
    assert out["value"] == pytest.approx(0.0079, abs=1e-4)
    assert out["seed_spread"] == pytest.approx(max(kept) - min(kept))


def test_the_f02_shape_ten_seeds_value_is_two_sd(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    out = rs.measure(_f02_doc(), {"F08": rs.load_judge_pack(path)})["challenges"]["F08"]
    assert out["gated"]["control_seeds"] == 0
    assert out["value"] == pytest.approx(2 * statistics.stdev(F02_SEEDS), abs=1e-12)
    assert out["value"] == pytest.approx(0.0473, abs=1e-4)


def _f02_doc():
    return _f08_doc(seeds=F02_SEEDS, gated_at=())


def test_the_margin_is_five_sigma_when_that_is_larger(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    rows = [(0.5 + 0.02 * i, 0.6) for i in range(10)]  # a noisy member
    doc = _doc({"mgn": _member(rows, same=False, within=True)})
    out = rs.measure(doc, {"Motor": rs.load_judge_pack(path)})["challenges"]["Motor"]
    assert out["value"] == pytest.approx(5 * out["sigma"])
    assert out["value"] > 2 * out["seed_sd"]


def test_both_terms_zero_is_still_refused(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    same = [0.42181190434059457] * 10
    with pytest.raises(rs.StatsError, match="both 0"):
        rs.measure(_f08_doc(seeds=same, gated_at=()), {"F08": rs.load_judge_pack(path)})
    with pytest.raises(rs.StatsError, match="both 0"):
        rs.measure(_doc({"fc": _member([(0.5, 0.6)] * 10)}))


def test_the_seed_sd_is_the_sample_sd_over_the_kept_seeds_only(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    out = rs.measure(_f08_doc(), {"F08": rs.load_judge_pack(path)})["challenges"]["F08"]
    # n - 1, not n: the population sd of the same five would be smaller
    assert out["seed_sd"] == pytest.approx(statistics.stdev(F08_KEPT))
    assert out["seed_sd"] > statistics.pstdev(F08_KEPT)


# --- round 4: a null total whose gates all PASS gets its total from its legs ----------------------------------------------

COOLING_A = [
    0.4812,
    0.5011,
    0.4953,
    0.5287,
    0.4906,
    0.5102,
    0.4877,
]  # the 7 all-PASS control seeds, A in [0.48, 0.53]
COOLING_D = 3.7e-13
PASS = {"finite_outputs": "PASS", "envelope": "PASS"}


def _pass_legs(a, d=COOLING_D):
    """A calibration-grade row whose legs fell under a minimum: no recorded total, every gate PASS."""
    return {"A": a, "D": d, "gates": dict(PASS), "decision_outcome": "POOL_GRADED"}


def _fail_legs(a=0.5, d=COOLING_D):
    return {
        "A": a,
        "D": d,
        "gates": {**PASS, "physics_pool": "FAIL"},
        "decision_outcome": "POOL_GRADED",
    }


def _cooling_doc(seed_a=COOLING_A, failed_at=(2, 5, 8), member_a=0.5):
    """The real Cooling shape: one bit-identical member (seed-0 rows all null-total, all PASS), ten control seeds of which
    three fail the physics_pool gate (total null, gated) and seven PASS with a null total.
    """
    it = iter(seed_a)
    legs = [_fail_legs() if i in failed_at else _pass_legs(next(it)) for i in range(10)]
    member = {
        "reference_fingerprint": H("a"),
        "seed0_totals": [None] * 10,
        "seed0_legs": [_pass_legs(member_a)] * 10,
        "state_digests": [H("1")] * 10,
        "within_noise": False,
    }
    return {
        "schema": rs.SCHEMA_IN,
        "challenges": {
            "Cooling": {
                "pack_digest": H("b"),
                "class_record_digest": H("c"),
                "control_basis_bit_identical": "ten bit-identical",
                "control_basis_within_noise": "smallest sigma within noise",
                "panel": ["MGN"],
                "members": {"MGN": member},
                "control_seed_totals": {"MGN": [None] * 10},
                "control_seed_legs": {"MGN": legs},
            }
        },
    }


def test_the_real_cooling_shape_totals_are_computed_from_legs_and_failed_gates_stay_gated(
    tmp_path,
):
    path, _sha, _body = _judge(tmp_path)
    out = rs.measure(_cooling_doc(), {"Cooling": rs.load_judge_pack(path)})
    cooling = out["challenges"]["Cooling"]
    totals = [_total(a, COOLING_D) for a in COOLING_A]
    assert cooling["total_from_legs"] == {"by_member": {"MGN": 10}, "control_seeds": 7}
    assert cooling["total_from_legs_rows"]["control_seeds"] == [0, 1, 3, 4, 6, 7, 9]
    assert cooling["total_from_legs_rows"]["by_member"] == {"MGN": list(range(10))}
    assert cooling["gated"] == {"by_member": {"MGN": 0}, "control_seeds": 3}
    # every computed row is under the judge pack's D minimum: counted, kept
    assert cooling["minimum_failed"] == {"by_member": {"MGN": 10}, "control_seeds": 7}
    assert cooling["control"]["entry_id"] == "MGN"  # bit-identical, seed-0 not gated
    assert cooling["control"]["reference_total"] == pytest.approx(
        _total(0.5, COOLING_D), abs=1e-12
    )
    assert cooling["sigma"] == pytest.approx(
        0.0, abs=1e-15
    )  # identical legs: same total
    assert cooling["seed_sd"] == pytest.approx(statistics.stdev(totals), abs=1e-12)
    assert cooling["value"] == pytest.approx(
        max(5 * cooling["sigma"], 2 * statistics.stdev(totals)), abs=1e-12
    )
    assert cooling["value"] == pytest.approx(2 * statistics.stdev(totals), abs=1e-12)


def test_the_computed_total_is_what_the_same_legs_give_without_minimums(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    unbounded = rs.without_minimums(rs.load_judge_pack(path)[0])
    status, total = rs.rejudge(_pass_legs(0.5), unbounded, "x")
    assert status == "SCORED_DEVELOPMENT_CANDIDATE"
    assert total == pytest.approx(_total(0.5, COOLING_D), abs=1e-12)
    # the judge pack itself withholds the status of the same legs: minimums change status, not the total
    status, _withheld = rs.rejudge(_pass_legs(0.5), rs.load_judge_pack(path)[0], "x")
    assert status == "REQUIRED_LEG_MINIMUM_FAILED"


def test_a_recorded_total_is_never_replaced_by_the_legs(tmp_path):
    # a row with a total keeps the previous rule: the recorded total must equal the legs' (here it does not)
    path, _sha, _body = _judge(tmp_path)
    doc = _f08_doc()
    doc["challenges"]["F08"]["control_seed_totals"]["FC"][0] = 0.9
    with pytest.raises(rs.StatsError, match="not the recorded"):
        rs.measure(doc, {"F08": rs.load_judge_pack(path)})


@pytest.mark.parametrize(
    "legs",
    [
        {"A": 0.5, "D": COOLING_D},  # no gates map
        {"A": 0.5, "D": COOLING_D, "gates": {}},  # an empty gates map proves nothing
        {"A": None, "D": COOLING_D, "gates": dict(PASS)},
        {"A": 0.5, "D": "x", "gates": dict(PASS)},
        {"A": float("nan"), "D": COOLING_D, "gates": dict(PASS)},
        {"A": float("inf"), "D": COOLING_D, "gates": dict(PASS)},
        {"A": True, "D": COOLING_D, "gates": dict(PASS)},
        {"A": 0.5, "gates": dict(PASS)},  # no D
        "gated",
        None,
    ],
    ids=str,
)
def test_a_null_total_the_legs_cannot_give_stays_refused(tmp_path, legs):
    path, _sha, _body = _judge(tmp_path)
    doc = _cooling_doc()
    doc["challenges"]["Cooling"]["control_seed_legs"]["MGN"][0] = legs
    with pytest.raises(rs.StatsError, match="not gated|numeric A and D"):
        rs.measure(doc, {"Cooling": rs.load_judge_pack(path)})


def test_any_gate_failure_is_gated_never_computed(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    for gates in ({**PASS, "g": "FAIL"}, {**PASS, "g": False}, {"g": None}):
        doc = _cooling_doc()
        doc["challenges"]["Cooling"]["control_seed_legs"]["MGN"][0] = {
            **_pass_legs(0.5),
            "gates": gates,
        }
        out = rs.measure(doc, {"Cooling": rs.load_judge_pack(path)})
        cooling = out["challenges"]["Cooling"]
        assert cooling["gated"]["control_seeds"] == 4
        assert cooling["total_from_legs"]["control_seeds"] == 6


def test_the_f08_shape_computes_nothing(tmp_path):
    # the existing real F08 shape (gated seeds with numeric legs) still counts as gated, nothing computed
    path, _sha, _body = _judge(tmp_path)
    out = rs.measure(_f08_doc(), {"F08": rs.load_judge_pack(path)})
    f08 = out["challenges"]["F08"]
    assert f08["total_from_legs"] == {"by_member": {"FC": 0}, "control_seeds": 0}
    assert f08["total_from_legs_rows"]["control_seeds"] == []


def test_two_kept_computed_rows_are_enough_and_one_is_refused(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    packs = {"Cooling": rs.load_judge_pack(path)}
    two = _cooling_doc(seed_a=COOLING_A[:2], failed_at=tuple(range(2, 10)))
    out = rs.measure(two, packs)["challenges"]["Cooling"]
    assert out["total_from_legs"]["control_seeds"] == 2
    one = _cooling_doc(seed_a=COOLING_A[:1], failed_at=tuple(range(1, 10)))
    with pytest.raises(rs.StatsError, match="only 1 non-gated"):
        rs.measure(one, packs)


def test_the_computed_row_marks_are_in_the_measurement_digest(tmp_path):
    path, _sha, _body = _judge(tmp_path)
    packs = {"Cooling": rs.load_judge_pack(path)}
    first = rs.measure(_cooling_doc(), packs)
    other = rs.measure(_cooling_doc(failed_at=(1, 5, 8)), packs)
    assert (
        first["measurement_digest"]
        == rs.measure(_cooling_doc(), packs)["measurement_digest"]
    )
    assert first["measurement_digest"] != other["measurement_digest"]
