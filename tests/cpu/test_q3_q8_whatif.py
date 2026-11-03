"""The Q3 / Q8 custody reads and the new-rules what-if (scripts/dev/exam_reads/q3_q8_whatif.py), offline: the statistics, the
decompositions, the store reader, the config, and the re-grade wrappers on a fake graded set. The real re-grade runs in custody.
"""

from __future__ import annotations

import copy
import json
import math
import sqlite3
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

READS = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads"
sys.path.insert(0, str(READS))

import q3_q8_whatif as reads

COMBO = {"combination": "weighted_arithmetic_mean", "value_weight": 0.5}


def _record(a_bank, gens, ds, *, c=1.0, rule=None, combo=COMBO):
    return {
        "a_bank": a_bank,
        "c": c,
        "a_rule": rule or {"kind": "mean"},
        "a_gen_sets": gens,
        "d_sets": ds,
        "combo": combo,
    }


# --- statistics ---------------------------------------------------------------------------------------------------


def test_ranks_share_the_mean_rank_on_ties():
    assert reads.ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]


def test_spearman_is_one_minus_one_and_undefined_for_a_constant_side():
    assert reads.spearman([1, 2, 3, 4], [10, 20, 35, 80]) == pytest.approx(1.0)
    assert reads.spearman([1, 2, 3, 4], [9, 7, 3, 1]) == pytest.approx(-1.0)
    assert reads.spearman([1, 2, 3], [5, 5, 5]) is None
    with pytest.raises(reads.ReadRefused, match="two_paired"):
        reads.spearman([1], [1])


def test_the_bootstrap_interval_is_deterministic_for_its_seed_and_brackets_a_clear_trend():
    x = [float(i) for i in range(30)]
    y = [i + (3 if i % 2 else -3) for i in range(30)]
    first = reads.bootstrap_rho(x, y)
    again = reads.bootstrap_rho(x, y)
    assert first == again
    rho, (low, high) = first
    assert low <= rho <= high and low > 0.8
    other = reads.bootstrap_rho(x, y, seed=reads.SEED + 1)
    assert other[1] != first[1]
    # a constant side never defines rho: the interval is None, not an error
    assert reads.bootstrap_rho([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])[1] is None


def test_flipped_pairs_count_only_strictly_opposite_orders():
    rows = [
        {"bank": 0.9, "gen": 0.1},
        {"bank": 0.8, "gen": 0.2},
        {"bank": 0.7, "gen": 0.2},  # a tie on gen with the row above: not a flip
        {"bank": 0.6, "gen": 0.9},
    ]
    flips, pairs = reads.flipped_pairs(rows, "bank", "gen")
    assert pairs == 6
    # the bank order 1>2>3>4 vs gen: 4 beats 1,2,3 (3 flips); 1 vs 2: gen 0.1<0.2 (flip); 1 vs 3: flip; 2 vs 3 tie
    assert flips == 5


# --- decompositions and the crown ----------------------------------------------------------------------------------


def test_a_and_d_are_combined_the_way_the_pack_does_and_the_modes_isolate_a_leg():
    record = _record(0.8, [0.4, 0.6], [0.5, 0.7])
    assert reads.a_total(record) == pytest.approx(
        statistics.fmean([0.6, 0.7])
    )  # mean rule
    assert reads.a_total(record, mode="bank") == 0.8
    assert reads.a_total(record, mode="gen") == pytest.approx(0.5)
    assert reads.d_total(record) == pytest.approx(0.6)
    assert reads.total_with(record) == pytest.approx(0.5 * 0.65 + 0.5 * 0.6)
    min_rule = _record(0.8, [0.4, 0.6], [0.5, 0.7], rule={"kind": "min"})
    assert reads.a_total(min_rule) == pytest.approx(0.5)
    capped = _record(0.8, [0.4], [0.9], c=0.5)
    assert reads.d_total(capped) == 0.5  # D is capped by C
    geometric = {"combination": "bottleneck_capped_geometric", "value_weight": 0.5}
    assert reads.pack_total(geometric, 0.0, 0.5) == 0.0
    assert reads.pack_total(geometric, 0.25, 1.0) == pytest.approx(
        0.25 * math.exp(0.5 * math.log(0.25))
    )


def _entries():
    # king by total is "K"; "B" has the best A_bank, "G" the best A_gen
    return [
        {"hotkey": "K", "record": _record(0.70, [0.70], [0.80])},
        {"hotkey": "B", "record": _record(0.95, [0.20], [0.60])},
        {"hotkey": "G", "record": _record(0.30, [0.97], [0.62])},
        {"hotkey": "X", "record": _record(0.50, [0.50], [0.40])},
    ]


def test_q3_reports_rho_flips_and_the_crown_under_each_leg_alone():
    out = reads.q3(_entries(), top=4)
    assert out["n"] == 4 and out["king"] == "K"
    assert out["flipped_pairs"] <= out["pairs"] == 6
    assert out["rho"] is not None and -1.0 <= out["rho"] <= 1.0
    # A_bank alone crowns B; A_gen alone crowns G (every other leg unchanged)
    assert out["crown_flip_bank_only"] is True and out["crown_if_bank_only"] == "B"
    assert out["crown_flip_gen_only"] is True and out["crown_if_gen_only"] == "G"
    assert "total" not in json.dumps(out)  # no exact totals leave custody


def test_q3_with_a_king_that_wins_on_both_legs_has_no_crown_flip():
    rows = [
        {"hotkey": "K", "record": _record(0.9, [0.9], [0.9])},
        {"hotkey": "A", "record": _record(0.5, [0.5], [0.5])},
        {"hotkey": "B", "record": _record(0.4, [0.3], [0.5])},
    ]
    out = reads.q3(rows, top=3)
    assert out["crown_flip_bank_only"] is False and out["crown_flip_gen_only"] is False
    assert out["flipped_pairs"] == 0


# --- Q8 -----------------------------------------------------------------------------------------------------------------


def test_q8_with_no_exposed_margin_reports_counts_only_and_says_so():
    entries = [
        {"hotkey": "K", "total": 0.9, "gates": {"g1": True, "g2": True}},
        {"hotkey": "A", "total": 0.5, "gates": {"g1": True, "g2": False}},
        {"hotkey": "B", "total": None, "gates": {"g1": False, "g2": False}},
    ]
    out = reads.q8(entries, lambda _e, _g: None, top=2)
    assert out["g1"] == {"slack_exposed": False, "fail_count": 1, "king_passes": True}
    assert out["g2"]["fail_count"] == 2 and out["g2"]["slack_exposed"] is False


def test_q8_quantiles_near_and_fail_counts_and_the_kings_margin_to_two_figures():
    margins = {"K": 0.123456, "A": 0.05, "B": -0.02, "C": 0.5, "D": 0.09}
    entries = [
        {"hotkey": h, "total": t, "gates": {"g": m >= 0}}
        for (h, m), t in zip(margins.items(), [0.9, 0.8, 0.7, 0.6, 0.5], strict=True)
    ]
    out = reads.q8(entries, lambda e, g: margins[e["hotkey"]], top=3)["g"]
    assert out["slack_exposed"] is True
    assert (
        out["near_count"] == 2 and out["fail_count"] == 1
    )  # 0.05 and 0.09 are near; -0.02 fails
    assert out["q50"] == pytest.approx(0.09)
    assert out["q05"] == pytest.approx(reads.quantile(list(margins.values()), 0.05))
    assert out["top5_q05"] == pytest.approx(
        reads.quantile([0.123456, 0.05, -0.02], 0.05)
    )
    assert out["king_m"] == 0.12


# --- the what-if composition ---------------------------------------------------------------------------------------


def _targets_record():
    # two sets: 4 in_train and 2 extended_shell targets each
    def targets(shell):
        return [{"d": 0.9, "agen": 0.6, "cls": "in_train"} for _ in range(4)] + [
            {"d": shell, "agen": 0.5, "cls": "extended_shell"} for _ in range(2)
        ]

    return {
        "a_bank": 0.8,
        "c": 1.0,
        "a_rule": {"kind": "mean"},
        "combo": COMBO,
        "targets": [targets(0.1), targets(0.3)],
    }


def test_the_balanced_total_gives_a_thin_shell_class_its_equal_say():
    record = _targets_record()
    plain = reads.total_from_targets(record, balanced=False)
    balanced = reads.total_from_targets(record, balanced=True)
    assert (
        plain > balanced
    )  # the shell's low d is no longer averaged away behind the in-train majority
    assert reads.balanced_d_sets(record) == [pytest.approx(0.5), pytest.approx(0.6)]
    # with one class the balanced rule is today's mean
    one = {
        **record,
        "targets": [[{**t, "cls": "in_train"} for t in ts] for ts in record["targets"]],
    }
    assert reads.total_from_targets(one, balanced=True) == reads.total_from_targets(
        one, balanced=False
    )


def test_the_class_bootstrap_is_deterministic_per_class_and_zero_for_identical_targets():
    record = _targets_record()
    first = reads.class_bootstrap(record, resamples=200)
    assert first == reads.class_bootstrap(record, resamples=200)
    assert first["targets_per_class"] == {"extended_shell": [2, 2], "in_train": [4, 4]}
    assert first["seed"] == reads.SEED and first["resamples"] == 200
    for spread in first["class_mean_sd"].values():
        assert spread == pytest.approx(0.0, abs=1e-12)
    varied = _targets_record()
    varied["targets"][0][4]["d"] = 0.0
    spread = reads.class_bootstrap(varied, resamples=300)
    assert spread["class_mean_sd"]["extended_shell"] > 0 and spread["total_sd"] > 0
    assert reads.RESAMPLES == 2000 and reads.SEED == 20261101


def test_gap_and_the_paired_gaming_rule():
    assert reads.gap(0.9, 0.6) == pytest.approx(0.3)
    assert reads.paired_gaming(0.8, 0.7)["holds"] is True
    gained = reads.paired_gaming(0.8, 0.81)
    assert gained["holds"] is False and gained["gain"] == pytest.approx(0.01)


def test_scaled_policies_change_only_the_new_rules_and_leave_the_registered_object_alone():
    from carbon.scoring import pool_version

    registered = pool_version.registered_policies("f08-ribbed-bracket", "1.7")
    new = reads.scaled_policies(registered, pick_k=3, s_h=0.0123, agen_factor=1 / 3)
    assert new.optimizer.pick_rule == {"kind": "top_k", "k": 3}
    assert new.optimizer.d_aggregate == "balanced_region_mean"
    assert (
        new.honesty.scale == 0.0123
        and new.honesty.reduction == registered.honesty.reduction
    )
    for name, value in registered.agen_scales.items():
        assert new.agen_scales[name] == pytest.approx(value / 3)
    assert new.a_rule == registered.a_rule and new.c_rule == registered.c_rule
    assert (
        registered.optimizer.pick_rule is None
        and registered.optimizer.d_aggregate is None
    )


# --- the store and the entries ----------------------------------------------------------------------------------------


def _store(tmp_path, rows):
    path = tmp_path / "pool.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE operations (kind TEXT, state TEXT, body TEXT)")
    connection.executemany(
        "INSERT INTO operations VALUES (?, ?, ?)",
        [("private_evaluation.v1", state, json.dumps(body)) for state, body in rows],
    )
    connection.commit()
    connection.close()
    return path


def _body(
    sid, hotkey, total, *, status="SCORED_DEVELOPMENT_CANDIDATE", version="v-now"
):
    return {
        "submission_id": sid,
        "owner": {"hotkey": hotkey, "request_digest": "sha256:" + "0" * 64},
        "evidence": {
            "challenge": "f08-ribbed-bracket",
            "evaluation_version": version,
            "model_p": {"score_status": status, "total_score": total},
        },
    }


CONFIG = {"challenge": "f08-ribbed-bracket", "evaluation_version": "v-now"}


def test_entries_are_the_current_exams_latest_per_hotkey_and_recipe_with_a_pair_coverage_count(
    tmp_path,
):
    sid = lambda n: "rtsk_" + f"{n:064x}"
    pairs = tmp_path / "tasks"
    for n, recipe in (
        (1, "sha256:" + "a" * 64),
        (2, "sha256:" + "a" * 64),
        (3, "sha256:" + "b" * 64),
    ):
        directory = pairs / f"{sid(n)}.evaluation"
        directory.mkdir(parents=True)
        (directory / "inference-pair.json").write_text(
            json.dumps({"recipe_digest": recipe})
        )
    store = _store(
        tmp_path,
        [
            ("BOUND_DEVELOPMENT_ONLY", _body(sid(1), "hk1", 0.50)),
            (
                "BOUND_DEVELOPMENT_ONLY",
                _body(sid(2), "hk1", 0.60),
            ),  # same hotkey and recipe, later: replaces
            ("BOUND_DEVELOPMENT_ONLY", _body(sid(3), "hk2", 0.40)),
            ("BOUND_DEVELOPMENT_ONLY", _body(sid(4), "hk3", 0.30)),  # no retained pair
            (
                "BOUND_DEVELOPMENT_ONLY",
                _body(sid(5), "hk4", 0.90, version="v-old"),
            ),  # another exam key
            (
                "BOUND_DEVELOPMENT_ONLY",
                _body(sid(6), "hk5", None, status="MANDATORY_GATE_FAILED"),
            ),
            ("OTHER_STATE", _body(sid(7), "hk6", 0.99)),
        ],
    )
    before = store.read_bytes()
    entries, coverage = reads.enumerate_entries(
        reads.read_bodies(store), CONFIG, [pairs]
    )
    assert store.read_bytes() == before  # read-only
    by = {e["hotkey"]: e for e in entries}
    assert set(by) == {"hk1", "hk2", "hk3", "hk5"}
    assert by["hk1"]["submission_id"] == sid(2) and by["hk1"]["total"] == 0.60
    assert by["hk3"]["pair"] is None and by["hk5"]["status"] == "MANDATORY_GATE_FAILED"
    assert coverage == {
        "entries": 4,
        "with_pair": 2,
        "without_pair": 2,
        "pair_found_by_bound_sha": 0,
        "scored": 3,
    }


def test_a_regraded_entrys_pair_is_found_by_the_sha_its_body_binds(tmp_path):
    """A re-prepare re-grades an entry under a new task id: its pair sits under that id, and the body binds its sha256. A file
    at the original id whose bytes are not the bound ones is never used."""
    import hashlib

    sid = lambda n: "rtsk_" + f"{n:064x}"
    tasks = tmp_path / "tasks"

    def pair(task, recipe):
        directory = tasks / f"{task}.evaluation"
        directory.mkdir(parents=True)
        raw = json.dumps({"recipe_digest": recipe}).encode()
        (directory / "inference-pair.json").write_bytes(raw)
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    moved = pair(sid(91), "sha256:" + "a" * 64)  # regraded under task 91
    pair(sid(2), "sha256:" + "c" * 64)  # a stale file at entry 2's own id
    stale_bound = pair(sid(92), "sha256:" + "b" * 64)
    own = pair(sid(3), "sha256:" + "d" * 64)  # still at its own id
    bodies = [
        _body(sid(1), "hk1", 0.5),
        _body(sid(2), "hk2", 0.4),
        _body(sid(3), "hk3", 0.3),
    ]
    bodies[0]["evidence"]["inference_pair_sha256"] = moved
    bodies[1]["evidence"]["inference_pair_sha256"] = stale_bound
    bodies[2]["evidence"]["inference_pair_sha256"] = own
    store = _store(tmp_path, [("BOUND_DEVELOPMENT_ONLY", b) for b in bodies])
    entries, coverage = reads.enumerate_entries(
        reads.read_bodies(store), CONFIG, [tasks]
    )
    by = {e["hotkey"]: e for e in entries}
    assert by["hk1"]["pair"] == tasks / f"{sid(91)}.evaluation" / "inference-pair.json"
    assert by["hk2"]["pair"] == tasks / f"{sid(92)}.evaluation" / "inference-pair.json"
    assert by["hk3"]["pair"] == tasks / f"{sid(3)}.evaluation" / "inference-pair.json"
    assert coverage["pair_found_by_bound_sha"] == 2 and coverage["with_pair"] == 3
    # a bound sha with no retained file is no pair, never the stale file at the entry's own id
    bodies[1]["evidence"]["inference_pair_sha256"] = "sha256:" + "e" * 64
    store.unlink()
    store = _store(tmp_path, [("BOUND_DEVELOPMENT_ONLY", b) for b in bodies])
    entries, _ = reads.enumerate_entries(reads.read_bodies(store), CONFIG, [tasks])
    assert {e["hotkey"]: e["pair"] for e in entries}["hk2"] is None


def _graded_row(stored_status, status, *, stored_total, regraded_total, gates):
    return {
        "stored_status": stored_status,
        "status": status,
        "stored_total": stored_total,
        "regraded_total": regraded_total,
        "gates": gates,
    }


def test_a_stored_scored_entry_regraded_as_gated_stops_the_run():
    flipped = _graded_row(
        "SCORED_DEVELOPMENT_CANDIDATE",
        "NOT_SCORED",
        stored_total=0.5,
        regraded_total=None,
        gates={"native_motor_valid": True, "physics_pool": False},
    )
    with pytest.raises(reads.ReadRefused) as stop:
        reads._check_regrade_matches([flipped])
    assert stop.value.code == (
        "regrade_does_not_reproduce_the_stored_status:"
        "SCORED_DEVELOPMENT_CANDIDATE->NOT_SCORED:physics_pool"
    )
    # the reverse flip stops too; matching statuses and totals pass
    with pytest.raises(reads.ReadRefused):
        reads._check_regrade_matches(
            [
                _graded_row(
                    "MANDATORY_GATE_FAILED",
                    "SCORED",
                    stored_total=None,
                    regraded_total=0.4,
                    gates={"g": True},
                )
            ]
        )
    reads._check_regrade_matches(
        [
            _graded_row(
                "SCORED_DEVELOPMENT_CANDIDATE",
                "SCORED",
                stored_total=0.5,
                regraded_total=0.5,
                gates={"g": True},
            ),
            _graded_row(
                "MANDATORY_GATE_FAILED",
                "NOT_SCORED",
                stored_total=None,
                regraded_total=None,
                gates={"g": False},
            ),
        ]
    )


def test_the_retained_rows_reach_the_grade_as_python_floats_and_pass_motors_typed_gate():
    """The receiver hands ``measure`` its decoded predictions (Python floats). Numpy rows served from the pool table reach
    Motor's ``schema_finite`` as numpy scalars and fail it on every pool answer (the TL's physics_pool finding, 1 Nov).
    """
    import numpy as np

    from carbon.motor import exam
    from carbon.scoring import pool_exam

    regrader = object.__new__(reads.Regrader)
    stored = np.full((1, 60), 1.5)
    regrader.graded = SimpleNamespace(
        bank={"inputs": [[0.0]]}, base_rows=np.zeros((1, 60))
    )
    regrader.input_dtype = np.float32
    regrader.binding = SimpleNamespace(
        read_baseline=lambda *a, **k: (stored, None),
        inputs_digest=lambda *a: "sha256:" + "0" * 64,
    )
    rows = regrader.rows_of("pair.json")
    assert type(rows) is list and all(type(v) is float for v in rows[0])
    served = pool_exam.table_server([{"x": 0.0}], rows, ["x"])([{"x": 0.0}])[0]
    assert exam.gates({"torque_nm": list(served)})["schema_finite"] == exam.PASS
    numpy_served = pool_exam.table_server([{"x": 0.0}], stored, ["x"])([{"x": 0.0}])[0]
    assert exam.gates({"torque_nm": list(numpy_served)})["schema_finite"] == exam.FAIL


def test_the_store_is_opened_read_only(tmp_path):
    store = _store(tmp_path, [])
    with pytest.raises(sqlite3.OperationalError):
        connection = sqlite3.connect(f"file:{store.as_posix()}?mode=ro", uri=True)
        connection.execute("INSERT INTO operations VALUES ('a','b','c')")


# --- the config -----------------------------------------------------------------------------------------------------------


def _config(tmp_path, **over):
    document = {
        "challenge": "f08-ribbed-bracket",
        "version": "1.7",
        "evaluation_version": "v-now",
        "copy_hotkey": "hk",
        "pack_root": "/p",
        "baseline_predictions": "/b",
        "store": "/s",
        "task_roots": ["/t"],
        "margin_n": 0.01,
        "top": 5,
        "gaming": [
            {"mode": "feasible_bias", "k": 3.0, "seed": 7},
            {"mode": "wrong_near", "k": 10.0, "radius": 0.1, "seed": 7},
        ],
        "records": {
            "koth_rebuild_noise_sha256": "a" * 64,
            "proof_grid_sha256": "b" * 64,
            "proof_grid_seed": 20261025,
        },
        "agen_factors": [1.0, 1 / 3],
        "s_h_fraction": 0.25,
        "pick_k": 3,
    }
    document.update(over)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({k: v for k, v in document.items() if v is not None}))
    return path


def test_the_config_requires_every_key_and_refuses_unknown_or_malformed_ones(tmp_path):
    assert reads.load_config(_config(tmp_path))["pick_k"] == 3
    with pytest.raises(reads.ReadRefused, match="config_missing_key:margin_n"):
        reads.load_config(_config(tmp_path, margin_n=None))
    with pytest.raises(reads.ReadRefused, match="config_unknown_key:extra"):
        reads.load_config(_config(tmp_path, extra=1))
    for over, code in (
        ({"top": 1}, "config_top"),
        ({"pick_k": 0}, "config_pick_k"),
        ({"task_roots": []}, "config_task_roots"),
        ({"gaming": []}, "config_gaming"),
        ({"gaming": [{"mode": "feasible_bias", "k": 3.0}]}, "config_gaming"),
        ({"gaming": [{"mode": "wrong_near", "k": 10.0, "seed": 1}]}, "config_gaming"),
        ({"gaming": [{"mode": "other", "k": 1.0, "seed": 1}]}, "config_gaming"),
        ({"records": {"koth_rebuild_noise_sha256": "a" * 64}}, "config_records"),
        (
            {"agen_factors": [0.5]},
            "config_agen_factors",
        ),  # the registered scale (1.0) must be among them
        ({"s_h_fraction": 0}, "config_s_h_fraction"),
    ):
        with pytest.raises(reads.ReadRefused, match=code):
            reads.load_config(_config(tmp_path, **over))


# --- the re-grade wrappers on a fake graded set --------------------------------------------------------------------------


def _registered_pack(*, minimum=None, gates=("g",), **extra):
    """A real registered score pack (`dual_score.register_pack`, the pack writer's own function): mean of A and D at weight 0.5."""
    from test_dual_score import fixture

    from carbon.scoring import dual_score

    body, _benchmark = fixture()
    body = {**body, "value_weight": 0.5, "hard_gates": sorted(gates), **extra}
    for leg in body["legs"].values():
        leg["minimum"] = minimum
    return dual_score.register_pack(body)


class _FakeGraded:
    def __init__(self):
        from carbon.scoring import pool_exam, pool_grader, pool_version

        self.seen = {}
        outer = self

        class Adapter:
            def measure(self, **kwargs):
                capture = kwargs.get("capture")
                outer.seen["capture_passed"] = capture is not None
                try:
                    outer.seen["policies"] = pool_version.registered_policies("c", "v")
                except pool_version.PoolConstantsNotRegistered:
                    outer.seen["policies"] = None
                outer.seen["region"] = pool_grader.region_class(
                    SimpleNamespace(target_id="t2", extended=False)
                )
                outer.seen["predictor"] = pool_exam.pool_plugin.pool_predictor
                if capture is not None:
                    capture["se_basis"] = {
                        "gated": False,
                        "a_bank": 0.5,
                        "c": 1.0,
                        "a_rule": {"kind": "mean"},
                        "sets": [],
                        "total": 0.5,
                    }
                return {}

        self.adapter = Adapter()
        self.roles = {"score_pack": _registered_pack()}
        self.bank = {"pool": {"sets": []}, "inputs": []}
        self.base_rows = [[0.0]]
        self.real = (
            pool_version.registered_policies,
            pool_grader.region_class,
            pool_exam.pool_plugin.pool_predictor,
        )

    def graded(self, *, infer, entry_id):
        self.adapter.measure(bank_rows=[], outputs=infer(None))
        return {"A": 0.5, "D": 0.5, "total": 0.5, "gates": {"g": True}}


def _regrader(fake):
    return reads.Regrader(
        {
            "challenge": "c",
            "version": "v",
            "copy_hotkey": "h",
            "pack_root": "p",
            "baseline_predictions": "b",
        },
        loader=lambda spec, config: (fake, [], None),
    )


def test_the_regrade_injects_the_capture_and_restores_every_patched_function(tmp_path):
    fake = _FakeGraded()
    regrader = _regrader(fake)
    sentinel = object()
    result = regrader.grade(
        [[1.0]],
        "e",
        policies=sentinel,
        classes={"t2": "extended_shell"},
        bias={"mode": "feasible_bias", "k": 3.0, "seed": 1},
    )
    assert result["status"] == "SCORED" and result["basis"]["a_bank"] == 0.5
    assert fake.seen["capture_passed"] is True
    assert fake.seen["policies"] is sentinel
    assert fake.seen["region"] == "extended_shell"
    from carbon.scoring import pool_exam, pool_grader, pool_version

    # during the call the model was wrapped; after it everything is the real function again
    assert fake.seen["predictor"] is not fake.real[2]
    assert pool_version.registered_policies is fake.real[0]
    assert pool_grader.region_class is fake.real[1]
    assert pool_exam.pool_plugin.pool_predictor is fake.real[2]
    assert (
        not hasattr(fake.adapter.measure, "__wrapped__")
        and fake.adapter.measure.__self__ is fake.adapter
    )


def test_the_slack_read_sees_the_pool_answers_the_live_gate_saw_and_changes_nothing():
    """GATE-MARGIN-01: ``slacks=True`` records the answers `pool_gates.failed_gates` receives (the live call still decides),
    and the grade's status, gates and total are those of the same grade without it."""
    from carbon.scoring import pool_adapters, pool_gates

    real_failed = pool_gates.failed_gates
    gates = pool_adapters.physics_gates("motor", "1.5")
    binding = SimpleNamespace(physics_gates=gates)

    class Gating(_FakeGraded):
        def graded(self, *, infer, entry_id):
            rows = infer(None)
            failed = pool_gates.failed_gates(
                binding, [{"inputs": {}}] * len(rows), rows
            )
            self.adapter.measure(bank_rows=[], outputs=rows)
            return {
                "A": 0.5,
                "D": 0.5,
                "total": 0.5,
                "gates": {"physics_pool": not failed},
            }

    answers = [[1.0] * 60, [2.0] * 60]
    plain = _regrader(Gating()).grade(answers, "e")
    read = _regrader(Gating()).grade(answers, "e", slacks=True)
    assert pool_gates.failed_gates is real_failed
    assert {k: read[k] for k in plain} == plain and "physics_slack" not in plain
    law = read["physics_slack"]["laws"]["motoring_mean_nonnegative"]
    assert law["answers"] == 2 and law["fail"] == 0 and law["m_min"] > 0


def test_q8_reports_physics_pool_m_and_a_per_law_block():
    import gate_slack

    from carbon.scoring import pool_exam

    assert reads.PHYSICS_POOL == pool_exam.PHYSICS_GATE

    def law(m, *, fail=0, near=0, unscaled=0):
        return {
            "slack_min": m,
            "m_min": m,
            "answers": 4,
            "fail": fail,
            "near": near,
            "unscaled": unscaled,
        }

    graded = [
        {"hotkey": "K", "status": "SCORED", "regraded_total": 0.9,
         "physics_slack": {"schema_failed": 0, "laws": {"l": law(0.5)}}},
        {"hotkey": "A", "status": "SCORED", "regraded_total": 0.8,
         "physics_slack": {"schema_failed": 0, "laws": {"l": law(0.05, near=1)}}},
        {"hotkey": "B", "status": "NOT_SCORED", "regraded_total": None,
         "physics_slack": {"schema_failed": 0, "laws": {"l": law(-0.2, fail=1)}}},
    ]  # fmt: skip
    block = reads.physics_laws(graded, top=2)["l"]
    assert block["scale"] == "registered" and block["entries"] == 3
    assert block["near_count"] == 1 and block["fail_count"] == 1
    assert block["answers"] == {"answers": 12, "fail": 1, "near": 1, "unscaled": 0}
    assert block["king"] == {"m": 0.5, "fail": 0, "near": 0, "answers": 4}
    rows = [
        {
            **g,
            "total": g["regraded_total"],
            "gates": {"physics_pool": g["status"] == "SCORED"},
        }
        for g in graded
    ]
    table = reads.q8(
        rows,
        lambda e, g: (
            gate_slack.physics_pool_m(e["physics_slack"])
            if g == "physics_pool"
            else None
        ),
        top=2,
    )["physics_pool"]
    assert (
        table["slack_exposed"] and table["king_m"] == 0.5 and table["near_count"] == 1
    )
    # a law with no registered scale: raw quantiles only, and physics_pool exposes no m
    graded[0]["physics_slack"]["laws"]["l"]["unscaled"] = 1
    assert reads.physics_laws(graded)["l"]["scale"] == "no registered scale"
    assert "q50" not in reads.physics_laws(graded)["l"]


def test_the_regrade_without_overrides_touches_nothing(tmp_path):
    fake = _FakeGraded()
    result = _regrader(fake).grade([[1.0]], "e")
    assert fake.seen["capture_passed"] is True
    assert (
        fake.seen["policies"] is None
    )  # the real (unregistered here) lookup ran, untouched
    assert result["gates"] == {"g": True}


def test_the_baseline_error_recorder_collects_each_targets_e_and_restores_the_grader(
    monkeypatch,
):
    from carbon.scoring import pool_grader

    fake = _FakeGraded()
    regrader = _regrader(fake)

    def stand_in(specs, predict, optimizer, honesty):
        return SimpleNamespace(targets=[SimpleNamespace(e=0.1), SimpleNamespace(e=0.3)])

    monkeypatch.setattr(pool_grader, "grade_set", stand_in)
    inner = fake.adapter.measure

    def measure(**kwargs):
        pool_grader.grade_set(
            (), None, None, None
        )  # what the pool grader does for a set
        return inner(**kwargs)

    fake.adapter.measure = measure
    errors = []
    regrader.grade([[1.0]], "e", errors=errors)
    assert errors == [0.1, 0.3]
    assert pool_grader.grade_set is stand_in  # restored to what it was before the call


def test_main_refuses_an_existing_output_and_an_unknown_config(tmp_path):
    config = _config(tmp_path)
    out = tmp_path / "out.json"
    out.write_text("{}")
    with pytest.raises(SystemExit, match="exists"):
        reads.main(["q3", str(config), "--out", str(out)])
    with pytest.raises(reads.ReadRefused):
        reads.main(
            ["q3", str(_config(tmp_path, extra=1)), "--out", str(tmp_path / "o2.json")]
        )


# --- the config builder: values come from the registered records, never typed ---------------------------------------------


def _host(tmp_path):
    entry = {
        "version": "1.7",
        "evaluation_version": "v-now",
        "copy_hotkey": "hk",
        "pack_root": "/p",
        "baseline_predictions": "/b",
        "store": "/s",
        "task_roots": ["/t"],
    }
    path = tmp_path / "host.json"
    path.write_text(
        json.dumps(
            {
                c: entry
                for c in (
                    "f08-ribbed-bracket",
                    "electric-motor-magnetics",
                    "f02",
                    "chip-cold-plate",
                )
            }
        )
    )
    return path


def test_the_config_builder_reads_margin_n_and_the_controls_from_the_records(tmp_path):
    import make_configs

    noise = READS.parents[1] / "validator_host_classes" / "koth_rebuild_noise.json"
    grid = tmp_path / "grid.json"
    grid.write_text(
        json.dumps(
            {"optimism_k": 3.0, "wrong_k": 10.0, "wrong_radius": 0.1, "seed": 20261025}
        )
    )
    configs = make_configs.build(noise, grid, _host(tmp_path), 20261101)
    registry = json.loads(noise.read_bytes())["challenges"]
    assert set(configs) == {
        "f08-ribbed-bracket",
        "electric-motor-magnetics",
        "f02",
        "chip-cold-plate",
    }
    for challenge, config in configs.items():
        assert config["margin_n"] == registry[challenge]["value"]
        assert config["gaming"] == [
            {"mode": "feasible_bias", "k": 3.0, "seed": 20261101},
            {"mode": "wrong_near", "k": 10.0, "radius": 0.1, "seed": 20261101},
        ]
        assert "class_split" not in config and config["s_h_fraction"] == 0.25
        assert (
            config["records"]["koth_rebuild_noise_sha256"]
            == __import__("hashlib").sha256(noise.read_bytes()).hexdigest()
        )
        assert (
            config["records"]["proof_grid_seed"] == 20261025
        )  # the grid's own seed, beside the controls' 20261101
        # every built config passes the script's own strict loader
        path = tmp_path / f"{challenge}.json"
        path.write_text(json.dumps(config))
        assert reads.load_config(path)["pick_k"] == 3
    assert configs["f08-ribbed-bracket"]["agen_factors"] == [1.0, 1.0 / 3.0]
    assert configs["f02"]["agen_factors"] == [1.0]
    assert configs["chip-cold-plate"]["agen_factors"] == [1.0]
    assert (
        configs["chip-cold-plate"]["margin_n"] == registry["chip-cold-plate"]["value"]
    )


def test_the_config_builder_builds_the_challenges_the_host_names_and_refuses_others_by_name(
    tmp_path,
):
    import make_configs

    noise = READS.parents[1] / "validator_host_classes" / "koth_rebuild_noise.json"
    grid = tmp_path / "grid.json"
    grid.write_text(
        json.dumps({"optimism_k": 3.0, "wrong_k": 10.0, "wrong_radius": 0.1, "seed": 1})
    )
    host = json.loads(_host(tmp_path).read_text())
    only = tmp_path / "cooling-only.json"
    only.write_text(json.dumps({"chip-cold-plate": host["chip-cold-plate"]}))
    assert set(make_configs.build(noise, grid, only, 1)) == {"chip-cold-plate"}
    other = tmp_path / "other.json"
    other.write_text(json.dumps({**host, "battery": host["f02"]}))
    with pytest.raises(SystemExit, match="no config rule for battery"):
        make_configs.build(noise, grid, other, 1)
    no_cooling_noise = tmp_path / "noise.json"
    registry = json.loads(noise.read_bytes())
    registry["challenges"].pop("chip-cold-plate")
    no_cooling_noise.write_text(json.dumps(registry))
    with pytest.raises(SystemExit, match="no registered margin_N for chip-cold-plate"):
        make_configs.build(no_cooling_noise, grid, only, 1)
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    with pytest.raises(SystemExit, match="names no Challenge"):
        make_configs.build(noise, grid, empty, 1)


def _null_baseline_config(tmp_path):
    import make_configs

    noise = READS.parents[1] / "validator_host_classes" / "koth_rebuild_noise.json"
    grid = tmp_path / "grid.json"
    grid.write_text(
        json.dumps({"optimism_k": 3.0, "wrong_k": 10.0, "wrong_radius": 0.1, "seed": 1})
    )
    host = json.loads(_host(tmp_path).read_text())
    host["chip-cold-plate"]["baseline_predictions"] = None
    path = tmp_path / "host-null.json"
    path.write_text(json.dumps(host))
    return make_configs.build(noise, grid, path, 1), make_configs.build(
        noise, grid, _host(tmp_path), 1
    )


def test_a_null_baseline_is_written_only_for_the_challenge_whose_host_record_has_none(
    tmp_path,
):
    configs, before = _null_baseline_config(tmp_path)
    assert configs["chip-cold-plate"]["baseline_predictions"] is None
    for challenge in ("f08-ribbed-bracket", "electric-motor-magnetics", "f02"):
        assert json.dumps(configs[challenge], sort_keys=True) == json.dumps(
            before[challenge], sort_keys=True
        )
    path = tmp_path / "cooling.json"
    path.write_text(json.dumps(configs["chip-cold-plate"]))
    assert reads.load_config(path)["baseline_predictions"] is None


@pytest.mark.parametrize("read", ["q3", "whatif"])
def test_a_null_baseline_is_refused_by_name_for_the_reads_that_use_it(tmp_path, read):
    configs, _ = _null_baseline_config(tmp_path)
    config = configs["chip-cold-plate"]
    run = {"q3": reads.run_q3, "whatif": reads.run_whatif}[read]
    with pytest.raises(reads.ReadRefused) as refused:
        run(
            config, tmp_path / "unused.json"
        )  # refused before any pack or store is opened
    assert refused.value.code == f"baseline_predictions_null_refused_for_{read}"


def test_a_null_baseline_serves_q8_the_set_loads_without_a_baseline(
    tmp_path, monkeypatch
):
    """q8 reads no baseline: the loader runs with the baseline reader stubbed out (and restored), and the entries' rows are
    read at the interface's output width."""
    import numpy as np
    import pool_binding

    from carbon.challenge_kit import physical_material

    reads._needs_baseline({"baseline_predictions": None}, "q8")  # accepted
    real_reader = pool_binding.read_baseline
    seen = {}

    def loader(spec, config):
        seen["baseline"] = pool_binding.read_baseline(
            spec["baseline_predictions"], 1, 1, float
        )
        fake = _FakeGraded()
        fake.base_rows = None
        return fake, [], None

    monkeypatch.setattr(
        physical_material,
        "bundle_material",
        lambda challenge, version: {"expected_output_shape": (7, 60)},
    )
    regrader = reads.Regrader(
        {
            "challenge": "c",
            "version": "v",
            "copy_hotkey": "h",
            "pack_root": "p",
            "baseline_predictions": None,
        },
        loader=loader,
    )
    assert seen["baseline"] == (None, None)
    assert pool_binding.read_baseline is real_reader
    asked = {}
    regrader.binding = SimpleNamespace(
        read_baseline=lambda path, rows, width, dtype, **k: (
            asked.update(width=width, dtype=dtype) or np.zeros((rows, width)),
            None,
        ),
        inputs_digest=lambda *a: "sha256:" + "0" * 64,
    )
    regrader.input_dtype = np.float32
    regrader.graded.bank = {"inputs": [[0.0]]}
    rows = regrader.rows_of("pair.json")
    assert asked == {"width": 60, "dtype": np.dtype(float)} and len(rows[0]) == 60


def test_the_region_classes_are_the_pool_materials_own_wherever_its_extended_targets_sit(
    monkeypatch,
):
    """No count or position is assumed (a set's extended target need not be its 5th, a set may have none): each target's
    class is `pool_grader.region_class` of the sealed material, and a config naming a class split is refused.
    """
    from carbon.scoring import pool_grader, pool_version

    def target(name, shell):
        return {"id": name, "shell": shell}

    material = {
        "sets": [
            [target("t1", None), target("t5", {"mode": "designs"}), target("t2", None)],
            [target("u1", None), target("u2", None)],
        ]
    }
    monkeypatch.setattr(
        pool_grader,
        "load_pool",
        lambda d: SimpleNamespace(
            target_id=d["id"], shell=d["shell"], extended=d["shell"] is not None
        ),
    )
    regrader = object.__new__(reads.Regrader)
    regrader.graded = SimpleNamespace(bank={pool_version.POOL_KEY: material})
    classes, order = regrader.sets_and_classes()
    assert classes == {
        "t1": "in_train",
        "t5": "extended_shell",
        "t2": "in_train",
        "u1": "in_train",
        "u2": "in_train",
    }
    assert order == [["t1", "t5", "t2"], ["u1", "u2"]]


def test_a_config_that_still_names_a_class_split_is_refused(tmp_path):
    with pytest.raises(reads.ReadRefused, match="config_unknown_key:class_split"):
        reads.load_config(_config(tmp_path, class_split={"in_train": 4}))


def test_the_config_builder_refuses_an_incomplete_host_record_and_an_unregistered_challenge(
    tmp_path,
):
    import make_configs

    noise = READS.parents[1] / "validator_host_classes" / "koth_rebuild_noise.json"
    grid = tmp_path / "grid.json"
    grid.write_text(
        json.dumps({"optimism_k": 3.0, "wrong_k": 10.0, "wrong_radius": 0.1, "seed": 1})
    )
    host = json.loads(_host(tmp_path).read_text())
    host["f02"].pop("store")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(host))
    with pytest.raises(SystemExit, match="needs exactly"):
        make_configs.build(noise, grid, bad, 1)
    empty = tmp_path / "noise.json"
    empty.write_text(json.dumps({"challenges": {}}))
    with pytest.raises(SystemExit, match="no registered margin_N"):
        make_configs.build(empty, grid, _host(tmp_path), 1)


# --- R26 / E8: under a candidate rule set the leg minimums are the baseline's own legs under it --------------------------


class _MinimumGraded(_FakeGraded):
    """A graded set whose grade reads the score pack's leg minimums at call time, as calibration_grade does: legs below a
    minimum leave the total unscored (REQUIRED_LEG_MINIMUM_FAILED), a failing gate leaves it gated.
    """

    def __init__(self, legs, gates=None):
        super().__init__()
        self.legs, self.gate_values = legs, gates or {"g": True}
        self.roles["score_pack"] = _registered_pack(minimum=0.9, gates=self.gate_values)
        self.seen_minimums = []

    def graded(self, *, infer, entry_id):
        self.adapter.measure(bank_rows=[], outputs=infer(None))
        legs = self.roles["score_pack"]["legs"]
        self.seen_minimums.append({k: v["minimum"] for k, v in legs.items()})
        below = any(
            v["minimum"] is not None and self.legs[k] < v["minimum"]
            for k, v in legs.items()
        )
        total = (
            None
            if below or not all(self.gate_values.values())
            else 0.5 * self.legs["A"] + 0.5 * self.legs["D"]
        )
        return {**self.legs, "total": total, "gates": dict(self.gate_values)}


def test_a_grade_can_carry_its_own_leg_minimums_and_the_pack_is_restored_after():
    fake = _MinimumGraded({"A": 0.7, "D": 0.4})
    regrader = _regrader(fake)
    registered = regrader.graded.roles["score_pack"]
    plain = regrader.grade([[1.0]], "e")
    assert plain["status"] == "NOT_SCORED"  # below the registered 0.9 minimums
    lifted = regrader.grade([[1.0]], "e", minimums={"A": None, "D": None})
    assert lifted["status"] == "SCORED" and lifted["legs"] == {"A": 0.7, "D": 0.4}
    assert fake.seen_minimums[-1] == {"A": None, "D": None}
    assert regrader.graded.roles["score_pack"] is registered  # restored
    assert registered["legs"]["A"]["minimum"] == 0.9  # never mutated
    with pytest.raises(reads.ReadRefused, match="minimum_for_an_unknown_leg"):
        regrader.grade([[1.0]], "e", minimums={"Z": 0.1})


def test_the_minimums_of_a_rule_set_are_the_baselines_legs_under_it_and_it_then_sits_on_them():
    fake = _MinimumGraded({"A": 0.7, "D": 0.4})
    regrader = _regrader(fake)
    minimums, failure = reads.baseline_minimums(regrader, [[1.0]], None, None)
    assert failure is None and minimums == {"A": 0.7, "D": 0.4}
    on_them = regrader.grade([[1.0]], "b", minimums=minimums)
    assert on_them["status"] == "SCORED"  # a model exactly on the minimums meets them
    below = _MinimumGraded({"A": 0.69, "D": 0.4})
    assert (
        _regrader(below).grade([[1.0]], "x", minimums=minimums)["status"]
        == "NOT_SCORED"
    )


def test_a_baseline_that_still_fails_a_gate_under_the_rule_set_is_reported_by_gate_name():
    fake = _MinimumGraded(
        {"A": 0.7, "D": 0.4}, gates={"physics_pool": False, "native_valid": True}
    )
    minimums, failure = reads.baseline_minimums(_regrader(fake), [[1.0]], None, None)
    assert minimums is None
    assert failure == {"status": "NOT_SCORED", "failed_gates": ["physics_pool"]}


class _ScoringGraded(_MinimumGraded):
    """A graded set that scores with the REAL `dual_score.score` on the score pack it holds at call time, as calibration_grade
    does: so a substituted pack that is not its own registration is refused exactly where the F08 what-if crashed.
    """

    def graded(self, *, infer, entry_id):
        from test_dual_score import fixture

        from carbon.scoring import dual_score

        self.adapter.measure(bank_rows=[], outputs=infer(None))
        pack = self.roles["score_pack"]
        self.seen_minimums.append({k: v["minimum"] for k, v in pack["legs"].items()})
        _body, benchmark = fixture()
        model = benchmark["models"][0]
        model["gates"] = {g: "PASS" for g in pack["hard_gates"]}
        model["measurements"] = {
            leg: {"status": "RESOLVED", "value": value, "unit": "1"}
            for leg, value in self.legs.items()
        }
        result = dual_score.score(benchmark, pack)["models"][0]
        return {**self.legs, "total": result["score"], "gates": dict(self.gate_values)}


def test_the_rederived_minimums_grade_end_to_end_through_dual_score_with_a_repinned_pack():
    fake = _ScoringGraded({"A": 0.7, "D": 0.4})
    regrader = _regrader(fake)
    registered = regrader.graded.roles["score_pack"]
    # the registered 0.9 minimums leave the baseline unscored, through the real scorer
    assert regrader.grade([[1.0]], "e")["status"] == "NOT_SCORED"
    minimums, failure = reads.baseline_minimums(regrader, [[1.0]], None, None)
    assert failure is None and minimums == {"A": 0.7, "D": 0.4}
    on_them = regrader.grade([[1.0]], "b", minimums=minimums)
    assert on_them["status"] == "SCORED" and on_them["total"] == pytest.approx(0.55)
    assert fake.seen_minimums[-1] == minimums
    assert regrader.graded.roles["score_pack"] is registered  # restored, never mutated
    # the pack the scorer saw was re-pinned, never the registered digest over changed minimums
    candidate = reads.candidate_score_pack(registered, minimums)
    assert candidate["pack_digest"] != registered["pack_digest"]
    assert (
        candidate["legs"]["A"]["minimum"] == 0.7
        and registered["legs"]["A"]["minimum"] == 0.9
    )


def test_the_old_substitution_is_what_dual_score_refuses():
    # the crash the TL hit: changed minimums under the registered digest
    from carbon.scoring import dual_score

    registered = _registered_pack(minimum=0.9)
    stale = copy.deepcopy(registered)
    stale["legs"]["A"]["minimum"] = 0.7
    from test_dual_score import fixture

    _body, benchmark = fixture()
    benchmark["models"][0]["gates"] = {"g": "PASS"}
    with pytest.raises(dual_score.DualScoreRefused, match="pack_digest"):
        dual_score.score(benchmark, stale)
    repinned = reads.candidate_score_pack(registered, {"A": 0.7})
    assert dual_score.score(benchmark, repinned)["models"][0]["status"]


def test_only_a_verified_pack_is_substituted_and_an_unregistrable_candidate_is_a_typed_failure():
    registered = _registered_pack(minimum=0.9)
    tampered = copy.deepcopy(registered)
    tampered["value_weight"] = 0.6  # its digest no longer matches its body
    with pytest.raises(
        reads.ReadRefused, match="registered_score_pack_is_not_its_own_registration"
    ):
        reads.candidate_score_pack(tampered, {"A": 0.7})
    with pytest.raises(reads.ReadRefused, match="minimum_for_an_unknown_leg"):
        reads.candidate_score_pack(registered, {"Z": 0.1})
    # a pack whose crown floor sits below the baseline's own legs under the set cannot be re-registered: PACK_REFUSED, no crash
    fake = _ScoringGraded({"A": 0.7, "D": 0.4})
    fake.roles["score_pack"] = _registered_pack(minimum=None, baseline_floor_total=0.5)
    minimums, failure = reads.baseline_minimums(_regrader(fake), [[1.0]], None, None)
    assert minimums is None
    assert failure == {
        "status": "PACK_REFUSED",
        "code": "pack_baseline_floor_below_minimums",
    }


# --- DV-CURVE-01: the shortcut anchor in the grade, D with degenerate targets dropped, the curve inputs -----------------


def test_a_grade_can_carry_shortcut_anchors_and_load_pool_is_restored_after():
    from carbon.scoring import pool_grader

    real = pool_grader.load_pool
    seen = {}

    class Anchored(_FakeGraded):
        def graded(self, *, infer, entry_id):
            seen["spec"] = pool_grader.load_pool({"probe": True})
            self.adapter.measure(bank_rows=[], outputs=infer(None))
            return {"A": 0.5, "D": 0.5, "total": 0.5, "gates": {"g": True}}

    import dataclasses as dc

    @dc.dataclass(frozen=True)
    class Spec:
        target_id: str
        s_low: float

    original = pool_grader.load_pool
    pool_grader.load_pool = lambda document: Spec("t1", -0.5)
    try:
        regrader = _regrader(Anchored())
        regrader.grade([[1.0]], "e", anchors={"t1": -0.2})
        assert seen["spec"] == Spec("t1", -0.2)
        regrader.grade([[1.0]], "e", anchors={"other": -0.2})
        assert seen["spec"] == Spec(
            "t1", -0.5
        )  # a target not anchored keeps its median s_low
    finally:
        pool_grader.load_pool = original
    assert pool_grader.load_pool is real


def test_d_drops_degenerate_targets_from_each_sets_mean_and_skips_an_emptied_set():
    basis = {"sets": [[{"d": 0.2}, {"d": 0.6}], [{"d": 0.9}]], "c": 0.8}
    order = [["a", "b"], ["c"]]
    assert reads.d_dropping(basis, order, set(), 0.8) == pytest.approx(
        (0.4 + 0.8) / 2
    )  # C caps the second set
    assert reads.d_dropping(basis, order, {"a"}, 0.8) == pytest.approx((0.6 + 0.8) / 2)
    assert reads.d_dropping(basis, order, {"c"}, 0.8) == pytest.approx(0.4)
    assert reads.d_dropping(basis, order, {"a", "b", "c"}, 0.8) is None


def test_the_curve_inputs_are_closed_and_explicit(tmp_path):
    coarse = tmp_path / "coarse.json"
    coarse.write_text(json.dumps({"t1": {"0": {"worst_dynamic_mm_per_n": 0.1}}}))
    good = {
        "budgets": [4, 8, 16],
        "walls": {"t_ref": 1767.6, "t_coarse": 120.0, "rung_records_sha256": "a" * 64},
        "coarse": str(coarse),
        "seed": 20261101,
        "class_floor_n": 3,
        "contenders": {},
    }
    path = tmp_path / "curve.json"
    path.write_text(json.dumps(good))
    curve = reads.load_curve(path)
    assert curve["coarse_by_target"] == {"t1": {0: {"worst_dynamic_mm_per_n": 0.1}}}
    for change, code in (
        ({"budgets": []}, "curve_budgets"),
        ({"walls": {"t_ref": 1.0, "t_coarse": 1.0}}, "curve_walls"),
        ({"class_floor_n": 0}, "curve_class_floor_n"),
        ({"extra": 1}, "curve_shape"),
    ):
        path.write_text(json.dumps({**good, **change}))
        with pytest.raises(reads.ReadRefused, match=code):
            reads.load_curve(path)
    with pytest.raises(
        reads.ReadRefused, match="baseline_predictions_null_refused_for_dvcurve"
    ):
        reads._needs_baseline({"baseline_predictions": None}, "dvcurve")


# --- ACC-NOISE-01: each A_gen point's atom from the very predictions the grader scored ------------------------------------


class _AgenGraded(_FakeGraded):
    """A graded set whose measure scores A_gen through the real `pool_grader.agen_accuracy`, as measure_pool does."""

    def __init__(self):
        super().__init__()
        self.scales = {"f": 2.0, "g": 0.5}
        from types import SimpleNamespace

        self.specs = [
            SimpleNamespace(
                target_id=f"t{j}",
                conditions={"target_id": f"t{j}", "fixed": {"c": float(j)}},
                outputs=("f", "g"),
                agen=(0, 2),
                designs=[[float(i)] for i in range(3)],
                truths=[{"f": float(i), "g": float(i * i)} for i in range(3)],
            )
            for j in range(2)
        ]
        self.seen_agen = []

    def graded(self, *, infer, entry_id):
        from carbon.scoring import pool_grader

        def predict(conditions, designs):
            j = conditions["fixed"]["c"]
            return [{"f": d[0] + 0.1 * j, "g": d[0] ** 2 - 0.3} for d in designs]

        self.seen_agen.append(
            pool_grader.agen_accuracy(self.specs, predict, self.scales)
        )
        # measure_pool's capture scores each target again, one at a time: never a second record
        for spec in self.specs:
            pool_grader.agen_accuracy([spec], predict, self.scales)
        return {"A": 0.5, "D": 0.5, "total": 0.5, "gates": {"g": True}}


def test_a_grade_records_each_agen_points_atom_and_leaves_the_grade_and_grader_unchanged():
    from carbon.scoring import pool_grader

    real = pool_grader.agen_accuracy
    fake = _AgenGraded()
    regrader = _regrader(fake)
    plain = regrader.grade([[1.0]], "e")
    sink = []
    recorded = regrader.grade([[1.0]], "e", agen_points=sink)
    assert (
        recorded["total"] == plain["total"] and fake.seen_agen[0] == fake.seen_agen[1]
    )
    assert pool_grader.agen_accuracy is real  # restored
    assert [(p["target_id"], p["design"]) for p in sink] == [
        ("t0", [0.0]), ("t0", [2.0]), ("t1", [0.0]), ("t1", [2.0])
    ]  # fmt: skip
    # each atom = the grader's benefit averaged over the outputs; their per-target means average to the grader's A_gen
    p = sink[3]
    want = (
        pool_grader.benefit(abs(2.1 - 2.0) / 2.0)
        + pool_grader.benefit(abs(3.7 - 4.0) / 0.5)
    ) / 2
    assert p["atom"] == pytest.approx(want, abs=1e-15)
    per_target = [
        (sink[0]["atom"] + sink[1]["atom"]) / 2,
        (sink[2]["atom"] + sink[3]["atom"]) / 2,
    ]
    assert sum(per_target) / 2 == pytest.approx(fake.seen_agen[1], abs=1e-15)


def test_a_point_scored_twice_differently_stops_the_record():
    from types import SimpleNamespace

    from carbon.scoring import pool_grader

    spec = SimpleNamespace(
        target_id="t",
        conditions={},
        outputs=("f",),
        agen=(0,),
        designs=[[1.0]],
        truths=[{"f": 1.0}],
    )
    sink = []
    recording = reads._recording_agen(pool_grader, sink)
    recording([spec], lambda c, d: [{"f": 1.0}], {"f": 1.0})
    recording(
        [spec], lambda c, d: [{"f": 1.0}], {"f": 1.0}
    )  # the same score again: still one record
    assert len(sink) == 1
    with pytest.raises(reads.ReadRefused, match="agen_point_scored_twice_differently"):
        recording([spec], lambda c, d: [{"f": 2.0}], {"f": 1.0})


# --- ACC-NOISE-01 accnoise mode: the inputs, the class source, the orchestration ------------------------------------------


def _rule_and_region(tmp_path):
    import hashlib

    rule = tmp_path / "rule.py"
    rule.write_text(
        "import hashlib, json\n"
        'RULE = "geometric-v1"\n'
        "class pc:\n"
        "    @staticmethod\n"
        "    def load_region(path, sha):\n"
        "        record = json.loads(open(path).read())\n"
        "        if hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()).hexdigest() != sha:\n"
        "            raise SystemExit('refused')\n"
        "        return record\n"
        "def klass(region, names, inputs):\n"
        "    return 'in_train' if inputs['x'] <= 1.0 else 'regime:inner_band'\n"
    )
    region = tmp_path / "region.json"
    record = {
        "base": {"x": [0.0, 1.0], "c": [0.0, 9.0]},
        "extended": {"x": [0.0, 2.0], "c": [0.0, 9.0]},
        "challenge": "c",
    }
    region.write_text(json.dumps(record))
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"classes": [{"class": "regime:inner_band"}]}))

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    region_sha = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "rule_path": str(rule),
        "rule_sha256": sha(rule),
        "region_path": str(region),
        "region_sha256": region_sha,
        "plan_params_path": str(params),
        "plan_params_sha256": sha(params),
    }


def _accnoise_doc(tmp_path, source, **over):
    import io

    import numpy as np

    rows = tmp_path / "kernel.npy"
    buf = io.BytesIO()
    np.save(buf, np.array([[0.0]]))
    rows.write_bytes(buf.getvalue())
    import hashlib

    doc = {
        "contenders": {
            "train_kernel": {
                "rows_npy": str(rows),
                "sha256": hashlib.sha256(rows.read_bytes()).hexdigest(),
            },
            "operator": None,
            "down_formula": None,
        },
        "class_source": source,
        "class_floor_n": 1,
        "other_ood_enters": False,
        "seed": 5,
        **over,
    }
    path = tmp_path / "accnoise.json"
    path.write_text(json.dumps(doc))
    return path


def test_the_accnoise_inputs_and_the_class_source_are_checked(tmp_path):
    source = _rule_and_region(tmp_path)
    doc = reads.load_accnoise(_accnoise_doc(tmp_path, source))
    klass, region, allowed, ids = reads._class_source(doc["class_source"])
    assert klass(region, ["x"], {"x": 1.5}) == "regime:inner_band" and allowed == {
        "in_train",
        "regime:inner_band",
    }
    assert set(ids) == {"rule_sha256", "region_sha256", "plan_params_sha256"}
    with pytest.raises(reads.ReadRefused, match="accnoise_region_sha256_mismatch"):
        reads._class_source({**source, "region_sha256": "0" * 64})
    with pytest.raises(reads.ReadRefused, match="rule_file_sha256_mismatch"):
        reads._class_source({**source, "rule_sha256": "0" * 64})
    with pytest.raises(reads.ReadRefused, match="accnoise_plan_params_changed"):
        reads._class_source({**source, "plan_params_sha256": "0" * 64})
    for over, code in (
        ({"class_floor_n": 0}, "accnoise_class_floor_n"),
        ({"other_ood_enters": "no"}, "accnoise_other_ood_enters"),
        (
            {
                "contenders": {
                    "train_kernel": None,
                    "operator": None,
                    "down_formula": None,
                }
            },
            "accnoise_contenders",
        ),
    ):
        with pytest.raises(reads.ReadRefused, match=code):
            reads.load_accnoise(_accnoise_doc(tmp_path, source, **over))


def test_the_accnoise_mode_regrades_every_contender_and_reports_the_ruled_verdict(
    tmp_path, monkeypatch
):
    import numpy as np

    source = _rule_and_region(tmp_path)
    path = _accnoise_doc(tmp_path, source)
    graded_roles = []

    class FakeRegrader:
        def __init__(self, config):
            self.graded = SimpleNamespace(
                base_rows=np.array([[0.0]]),
                bank={"pool": {"design_names": ["x"], "sets": []}, "inputs": [[0.0]]},
            )

        def sets_and_classes(self):
            return {"t1": "in_train", "t2": "extended_shell"}, [["t1"], ["t2"]]

        def rows_of(self, pair):
            return [[0.0]]

        def grade(self, rows, entry_id, *, classes, agen_points):
            graded_roles.append(entry_id)
            atom = {
                "accnoise:crown": 0.9,
                "accnoise:baseline": 0.7,
                "accnoise:train_kernel": 0.8,
            }[entry_id]
            for tid, x in (("t1", 0.5), ("t1", 1.5), ("t2", 1.6), ("t2", 1.8)):
                agen_points.append(
                    {
                        "target_id": tid,
                        "conditions": {"fixed": {"c": 1.0}},
                        "design": [x],
                        "atom": atom,
                    }
                )
            return {
                "basis": {
                    "a_bank": 0.95,
                    "a_rule": {"kind": "weighted", "weight": 0.25},
                }
            }

    monkeypatch.setattr(reads, "Regrader", FakeRegrader)
    monkeypatch.setattr(reads, "read_bodies", lambda store: [])
    entry = {"hotkey": "h", "recipe_digest": "r", "pair": "p"}
    monkeypatch.setattr(reads, "enumerate_entries", lambda *a: ([entry], {}))
    scored = {
        "record": {},
        "status": "SCORED",
        "regraded_total": 0.5,
        "hotkey": "h",
        "recipe": "r",
    }
    monkeypatch.setattr(reads, "measured_entries", lambda *a, **k: [scored])
    monkeypatch.setattr(reads, "_check_regrade_matches", lambda g: None)
    monkeypatch.setattr(reads, "_check_composition", lambda g: None)
    config = {
        "challenge": "c",
        "version": "v",
        "store": "s",
        "task_roots": [],
        "margin_n": 1.0,
        "baseline_predictions": "b",
    }
    monkeypatch.setattr(reads, "_needs_baseline", lambda c, r: None)
    (tmp_path / "cfg.json").write_text(json.dumps(config))
    out = reads.run_accnoise(config, tmp_path / "cfg.json", path)
    assert graded_roles == [
        "accnoise:crown",
        "accnoise:baseline",
        "accnoise:train_kernel",
    ]
    assert (
        out["scratch_only"] is True and out["contenders"]["operator"] == "not available"
    )
    crown = out["contenders"]["crown"]
    assert crown["a_in"] == 0.95 and crown["a_gen_balanced"] == pytest.approx(0.9)
    assert (
        out["verdict"] == "min"
    )  # every atom equal within a contender: zero spread < margin 1.0
    assert out["per_class"]["crown"]["regime:inner_band"]["n"] == 3
    assert "points" not in json.dumps(out)  # aggregates only


def test_the_class_bootstrap_of_a_set_with_no_targets_is_unresolved_not_a_crash():
    # TL 3 Nov 09:46: at a DV-CURVE budget where every target was dropped, the bootstrap took the mean of an empty set
    record = _targets_record()
    for emptied in (
        {**record, "targets": [[], []]},  # every target dropped
        {**record, "targets": [record["targets"][0], []]},  # one set emptied
        {**record, "targets": []},
    ):
        out = reads.class_bootstrap(emptied, resamples=50)
        assert out["unresolved"] == "set_without_targets"
        assert out["class_mean_sd"] is None and out["total_sd"] is None
        assert out["resamples"] == 0 and out["seed"] == reads.SEED
        assert out["targets_per_set"] == [len(t) for t in emptied["targets"]]
    # a record with targets in every set is bootstrapped as before (no unresolved key)
    assert "unresolved" not in reads.class_bootstrap(record, resamples=50)
