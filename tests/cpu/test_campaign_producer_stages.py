"""EVIDENCE-PRODUCER-STAGES-01: Data Collection's campaign stages, the f02
menu-v2 export, producer settlement and the #965 refinement plans."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from carbon.design_search import producer_panels, tasks
from carbon.development_comparison import campaign_entrypoints
from carbon.development_comparison import evidence_campaign as campaign
from carbon.development_comparison.campaign_adapters import producer
from scripts.dev.evidence_runs import settlement

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/dev/battery"))

import middle_bands_refine as mbr

from scripts.dev.reference_packages.elmer import f02_export


def _context(**change):
    body = {
        "schema": campaign.SCHEMA + ".stage-context",
        "plan_digest": "sha256:" + "0" * 64,
        "entrypoint_registration_digest": campaign_entrypoints.digest(),
        "scope": "PUBLIC_DEVELOPMENT",
        "family": "f02",
        "phase": "train",
        "shard": 0,
        "shards": 1,
        "inputs": {},
        "prior": {},
        "prior_receipts": {},
    }
    return {**body, **change}


def _load(tmp_path, context, threads="4"):
    path = tmp_path / "context.json"
    path.write_text(json.dumps(context))
    return producer.load_context(path, environ={"OMP_NUM_THREADS": threads})


def test_contract_names_match_the_runner():
    assert producer.CONTEXT == campaign.SCHEMA + ".stage-context"
    assert producer.STAGE_RESULT == campaign.STAGE_RESULT
    assert "carbon.development_comparison.campaign_adapters.producer".startswith(
        "carbon.development_comparison.campaign_adapters."
    )


def test_pinned_helpers_match_their_files():
    for rel, pin in producer.PINNED.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == pin, rel


def test_a_registered_train_context_loads(tmp_path):
    context, vcpus, reuse = _load(tmp_path, _context())
    assert (context["family"], vcpus, reuse) == ("f02", 4, [])


@pytest.mark.parametrize(
    ("change", "threads", "code"),
    [
        ({"scope": "SYNTHETIC_FIXTURE"}, "4", "PUBLIC_DEVELOPMENT_ONLY"),
        ({"phase": "assemble"}, "4", "PHASE_NOT_PRODUCER"),
        ({"family": "f13"}, "4", "FAMILY_NOT_PRODUCER"),
        ({"shards": 2}, "4", "SHARDING_NOT_REGISTERED"),
        ({"entrypoint_registration_digest": "sha256:" + "1" * 64}, "4", "REGISTRATION_DIGEST_MISMATCH"),
        ({"family": "motor", "phase": "reference"}, "4", "ENTRYPOINT_NOT_REGISTERED"),
        ({"family": "battery-v3", "phase": "reference"}, "4", "REUSE_RECORDS_REQUIRED"),
        ({"inputs": {"x": {"path": "x", "sha256": "sha256:" + "0" * 64, "role": "PUBLIC_INPUT"}}}, "4",
         "UNREGISTERED_INPUT"),
        ({}, "1", "VCPU_ALLOTMENT_TOO_SMALL"),
        ({}, "", "VCPU_ALLOTMENT_REQUIRED"),
        ({"extra": 1}, "4", "STAGE_CONTEXT_INVALID"),
    ],
)  # fmt: skip
def test_unregistered_contexts_are_refused(tmp_path, change, threads, code):
    with pytest.raises(producer.Refused) as refused:
        _load(tmp_path, _context(**change), threads)
    assert refused.value.code == code


def test_battery_reuse_bundle_is_pinned_and_directory_bound(tmp_path):
    bundle = {"schema": producer.RECORDS, "family": "battery-v3", "chunk": 0,
              "records": [{"dir": "bfeas", "record": {"case_id": "x", "status": "OK"}}]}  # fmt: skip
    path = tmp_path / "reuse.json"
    path.write_text(json.dumps(bundle))
    pin = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    inputs = {
        "reuse_records_000": {
            "path": str(path),
            "sha256": pin,
            "role": "HELDOUT_REFERENCE",
        }
    }
    _, _, reuse = _load(
        tmp_path, _context(family="battery-v3", phase="reference", inputs=inputs)
    )
    assert reuse == [bundle]
    with pytest.raises(producer.Refused) as refused:
        bad = {**inputs["reuse_records_000"], "sha256": "sha256:" + "0" * 64}
        _load(
            tmp_path,
            _context(
                family="battery-v3",
                phase="reference",
                inputs={"reuse_records_000": bad},
            ),
        )
    assert refused.value.code == "INPUT_PIN_MISMATCH"
    bundle["records"][0]["dir"] = "../elsewhere"
    path.write_text(json.dumps(bundle))
    pin = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    inputs["reuse_records_000"]["sha256"] = pin
    with pytest.raises(producer.Refused) as refused:
        _load(tmp_path, _context(family="battery-v3", phase="reference", inputs=inputs))
    assert refused.value.code == "REUSE_RECORDS_INVALID"


def test_chunks_stay_under_the_bound_and_keep_order(monkeypatch):
    monkeypatch.setattr(producer, "CHUNK_BYTES", 200)
    rows = [{"dir": "d", "record": {"i": i, "pad": "x" * 40}} for i in range(12)]
    out = producer.chunks(rows, "reference-records", "motor")
    assert out[0][0] == "reference-records-000.json"
    assert [r for _, doc in out for r in doc["records"]] == rows
    assert all(len(json.dumps(doc["records"])) <= 400 for _, doc in out)


def test_train_document_requires_the_kit_canonical_bytes(tmp_path):
    rows = [{"schema": "s", "case_id": "a", "inputs": {"x": 1}, "outputs": {"y": 2.0}}]
    path = tmp_path / "train.jsonl"
    path.write_bytes(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
    )
    doc = producer.train_document("f02", path, "s", {"rows": 1})
    assert doc["records"] == rows
    assert doc["jsonl_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes((json.dumps(rows[0]) + "\n").encode())  # not sort_keys
    with pytest.raises(producer.Failed):
        producer.train_document("f02", path, "s", {})


def test_a_stage_receipt_passes_the_runner_check(tmp_path, monkeypatch):
    pytest.importorskip("resource")

    class FakeMeter:
        def __init__(self, image, run):
            self.parent, self.driver = "/carbon-stage-test", "cgroupfs"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return 1.5, 4096

    monkeypatch.setattr(producer, "Meter", FakeMeter)
    monkeypatch.setattr(producer.subprocess, "Popen", lambda *a, **k: None)
    context, vcpus, reuse = _load(tmp_path, _context())
    stage = producer.Stage(context, vcpus, reuse, tmp_path / "out")

    def fake_train(meter):
        stage.emit(
            "train.json", {"schema": producer.TRAIN, "records": []}, "PUBLIC_TRAIN"
        )

    stage.train = fake_train
    receipt = stage.execute()
    task = {"family": "f02", "phase": "train", "shard": 0}
    plan = {"plan_digest": context["plan_digest"], "scope": "PUBLIC_DEVELOPMENT"}
    checked = campaign._verified_receipt(task, tmp_path / "out", plan)
    assert checked == receipt and set(receipt["artifacts"]) == {
        "train",
        "stage-summary",
    }
    assert receipt["core_s"] >= 1.5 and receipt["peak_ram_bytes"] >= 4096


# -- settlement ---------------------------------------------------------------


def _one_limit_task(candidates):
    return tasks.task(
        "t",
        identity={"challenge": "c", "contract_version": "v", "action_grammar": None, "optimizer": None,
                  "query_budget": 1, "seed": 0, "observer_version": "o", "reference_bank": "b"},
        conditions=[{"id": "k", "stratum": "s"}], strata={"s": {"p": 1, "q": 1, "w": 1}},
        candidates=candidates, objective={"quantity": "e", "unit": "J", "sense": "max", "aggregate": "worst"},
        limits=[{"quantity": "t", "unit": "C", "op": "<=", "value": 95.0, "band": 0.5}],
    )  # fmt: skip


@pytest.mark.parametrize(
    ("values", "mode", "expected"),
    [
        ({"t": 95.3, "a.t": 95.2, "b.t": 95.4}, "all", False),
        ({"t": 94.8, "a.t": 94.7, "b.t": 94.9}, "all", True),
        ({"t": 94.8, "a.t": 95.1, "b.t": 94.9}, "all", None),
        ({"t": 94.8, "a.t": 95.4, "b.t": 94.6}, "all", None),
        ({"t": 95.2, "a.t": 94.9, "b.t": 94.8}, "finest_two", True),
        ({"t": 95.2, "a.t": 94.9}, "finest_two", None),
        ({"t": 95.2}, "finest_two", None),
        ({"t": 96.0}, "finest_two", "resolved"),
    ],
)
def test_settlement_needs_agreeing_rungs_inside_the_band(values, mode, expected):
    task = _one_limit_task(["x"])
    rows = [{"candidate": "x", "condition": "k", "values": {"e": 1.0, **values}}]
    out = settlement.verdicts(task, rows, ("a", "b"), mode)
    if expected == "resolved" or expected is None:
        assert out == []
    else:
        assert out == [{"candidate": "x", "feasible": expected}]


# -- f02 export -----------------------------------------------------------------


def _f02_observed(peak_for, rungs=None, drop=None):
    obs = {}
    for ctx, _ in f02_export.menu.contexts():
        for peak in f02_export.menu.PEAKS_W:
            for d in f02_export.menu.ON_TIMES_S:
                name = f02_export.menu.case_name(ctx, peak, d)
                if name == drop:
                    continue
                obs[name] = {
                    "peak_top_c": peak_for(ctx, peak, d),
                    "extra_energy_j": (peak - 20.0) * d,
                }
                for tag, value in (rungs or {}).get((ctx, peak, d), {}).items():
                    obs[f02_export.menu.case_name(ctx, peak, d, tag)] = {
                        "peak_top_c": value
                    }
    return obs


def test_f02_export_is_sealed_settled_and_accepted_by_main(monkeypatch):
    ctx0 = next(f02_export.menu.contexts())[0]
    rungs = {(ctx0, 140.0, 20.0): {"mesh2": 95.2, "dt0.5": 95.1}}

    def peak(ctx, p, d):
        if (ctx, p, d) == (ctx0, 140.0, 20.0):
            return 95.3  # in band, both rungs above: settled infeasible
        return 60.0 + p * d / 41.0  # no primary lands within the band

    monkeypatch.setattr(
        f02_export.menu, "_observed", lambda root: _f02_observed(peak, rungs)
    )
    export, summary = f02_export.build("unused")
    assert export["family"] == "f02" and export["refinement_rule"] == f02_export.RULE
    assert summary["questions"] == 24 and summary["unsettled_in_band"] == 0
    first = export["questions"][0]
    assert first["task"]["conditions"] == [{"id": ctx0, "stratum": ctx0}]
    assert (
        first["task"]["candidates"][0] == "p80-d5"
        and len(first["task"]["candidates"]) == 16
    )
    assert first["settled"] == [{"candidate": "p140-d20", "feasible": False}]
    assert (
        producer_panels.adapt_export(export)[0]["cases"][0]["state"]
        == "FEASIBLE_EXISTS"
    )


def test_f02_export_refuses_a_missing_primary(monkeypatch):
    ctx0 = next(f02_export.menu.contexts())[0]
    drop = f02_export.menu.case_name(ctx0, 80.0, 5.0)
    monkeypatch.setattr(
        f02_export.menu,
        "_observed",
        lambda root: _f02_observed(lambda *a: 70.0, drop=drop),
    )
    with pytest.raises(f02_export.Incomplete):
        f02_export.build("unused")


# -- #965 refinement plans --------------------------------------------------------


def _battery_record(case_id, row, t_max, plating):
    phase = {"t_max_c": t_max, "plating_min_v": plating}
    return {"case_id": case_id, "status": "OK", "c1": float(row["c1"]), "c2": float(row["c2"]),
            "switch_voltage_v": 4.0, "h_multiplier": float(row["cooling"]), "t_amb_c": float(row["ambient_c"]),
            "soc0": 0.1, "per_cycle": [{"phases": {p: dict(phase) for p in
                                                    ("cc1", "cc2", "cv", "rest_after_charge", "discharge",
                                                     "rest_after_discharge")}}],
            "initial_rest": {"t_max_c": 25.0}, "whole_programme": {"v_max_v": 4.2, "t_max_c": t_max},
            "q30_over_q1": 0.995, "soc_clock": {"status": "REACHED", "minutes": 30.0}}  # fmt: skip


def _write(runs, name, rows):
    (runs / name).mkdir(parents=True, exist_ok=True)
    (runs / name / "records.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )


def test_middle_band_rung_plans_follow_the_registered_windows(tmp_path):
    rows = mbr.tuples()[:4]
    runs = tmp_path / "runs"
    std = [
        _battery_record(f"t7:{rows[0]['id']}", rows[0], 45.4, 0.010),  # near thermal
        _battery_record(
            f"t7:{rows[1]['id']}", rows[1], 40.0, 0.020
        ),  # far from every window
        _battery_record(f"t7:{rows[2]['id']}", rows[2], 41.0, 0.003),  # near plating
    ]  # rows[3] has no standard record
    _write(runs, mbr.STAGE_A_DIR, std)
    body, summary = mbr.plan(runs, 2)
    assert [j["case_id"] for j in body["jobs"]] == [
        f"refined:t7:{rows[i]['id']}" for i in (0, 2)
    ]
    assert (
        rows[3]["id"] in summary["standard_absent"]
        and len(summary["standard_absent"]) == 297
    )
    assert all(j["refined"] and "rung" not in j for j in body["jobs"])
    r2 = [
        _battery_record(
            f"refined:t7:{rows[0]['id']}", rows[0], 44.9, 0.010
        ),  # straddles 45
        _battery_record(f"refined:t7:{rows[2]['id']}", rows[2], 41.0, 0.0031),  # agrees
    ]
    _write(runs, mbr.RUNG2_DIR, r2)
    assert mbr.plan(runs, 2)[0]["jobs"] == []
    body, summary = mbr.plan(runs, 3)
    assert [j["case_id"] for j in body["jobs"]] == [f"rung3:t7:{rows[0]['id']}"]
    assert body["jobs"][0]["rung"] == 3 and summary["rung3_candidates"] == 1


def test_the_runner_vcpus_field_must_match_the_environment_allotment(tmp_path):
    context, vcpus, _ = _load(tmp_path, _context(vcpus=4), threads="4")
    assert vcpus == 4 and context["vcpus"] == 4
    for bad in (8, "4", True):
        with pytest.raises(producer.Refused) as refused:
            _load(tmp_path, _context(vcpus=bad), threads="4")
        assert refused.value.code == "VCPU_CONTEXT_MISMATCH"
