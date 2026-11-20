"""EVIDENCE-PRODUCER-STAGES-01: Data Collection's campaign stages, the f02
menu-v2 export, producer settlement and the #965 refinement plans."""

from __future__ import annotations

import hashlib
import itertools
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


def test_changed_feasibility_helper_pin_still_refuses(monkeypatch, tmp_path):
    monkeypatch.setattr(
        producer,
        "PINNED",
        {**producer.PINNED, "scripts/dev/battery/feasibility02.py": "0" * 64},
    )
    with pytest.raises(producer.Refused) as refused:
        _load(tmp_path, _context())
    assert refused.value.code == "HELPER_PIN_MISMATCH"


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


# -- comparison inputs (Test Lead 2026-10-12: Data Collection's (a)-(d)) ---------


def _f02_export(monkeypatch):
    ctx0 = next(f02_export.menu.contexts())[0]
    rungs = {(ctx0, 140.0, 20.0): {"mesh2": 95.2, "dt0.5": 95.1}}

    def peak(ctx, p, d):
        return 95.3 if (ctx, p, d) == (ctx0, 140.0, 20.0) else 60.0 + p * d / 41.0

    monkeypatch.setattr(
        f02_export.menu, "_observed", lambda root: _f02_observed(peak, rungs)
    )
    return f02_export.build("unused")[0]


def test_physical_rows_carry_exactly_the_kit_observables(monkeypatch):
    from carbon.development_comparison import cheap_baselines as cb
    from carbon.development_comparison.f02_kit import KIT

    export = _f02_export(monkeypatch)
    assert all(
        set(r["values"]) == set(KIT.observables) for r in cb._physical_rows(export)
    )


def test_the_candidate_view_holds_no_reference_value(monkeypatch):
    from scripts.dev.evidence_runs import comparison_inputs as ci

    export = _f02_export(monkeypatch)
    view = ci.candidate_view(export)
    assert view["export_digest"] == export["export_digest"] and view["family"] == "f02"
    for entry in view["export"]["questions"]:
        assert "settled" not in entry
        for row in entry["reference"]:
            assert set(row["values"]) == {"peak_top_c", "extra_energy_j"}
            assert set(row["values"].values()) == {0.0}


def test_plain_bindings_and_the_indexed_refusal(monkeypatch):
    from scripts.dev.evidence_runs import comparison_inputs as ci

    export = _f02_export(monkeypatch)
    bindings = ci.plain_bindings(export)
    assert (
        bindings["export_digest"] == export["export_digest"]
        and len(bindings["jobs"]) == 24
    )
    job = bindings["jobs"][0]
    assert job["case"] == export["questions"][0]["case"] and job["candidates"][
        "p80-d5"
    ] == {"plain": "p80-d5"}
    indexed = {
        **export,
        "questions": [
            {
                **export["questions"][0],
                "task": {"schema": tasks.INDEXED_SCHEMA, "indices": []},
                "reference": [],
            }
        ],
    }
    with pytest.raises(ValueError):
        ci.plain_bindings(indexed)


def test_the_f02_cost_ledger_carries_every_solve_with_measured_cpu(
    monkeypatch, tmp_path
):
    from scripts.dev.evidence_runs import comparison_inputs as ci

    export = _f02_export(monkeypatch)
    menu = f02_export.menu
    lines = []
    for ctx, _ in menu.contexts():
        for p in menu.PEAKS_W:
            for d in menu.ON_TIMES_S:
                for tag in ("primary",) + (
                    ("mesh2", "dt0.5") if (p, d) == (140.0, 20.0) else ()
                ):
                    lines.append({"case": menu.case_name(ctx, p, d, tag), "wall_s": 100.0, "outcome": "COMPLETED",
                                  "children_cpu": "1m30.000s 0m10.000s"})  # fmt: skip
    (tmp_path / "ledger.jsonl").write_bytes(
        "".join(json.dumps(x) + "\n" for x in lines).encode()
    )
    ledger = ci.cost_ledger_f02(export, tmp_path)
    assert len(ledger["rows"]) == 24 * 16
    near = next(r for r in ledger["rows"] if r["candidate"] == "p140-d20")
    assert [s["rung"] for s in near["solves"]] == ["primary", "mesh2", "dt0.5"]
    assert near["wall_s"] == 300.0 and near["core_s"] == 300.0


def test_the_train_stage_needs_the_reference_candidate_view(tmp_path):
    context, vcpus, reuse = _load(tmp_path, _context())
    stage = producer.Stage(context, vcpus, reuse, tmp_path / "out")
    with pytest.raises(producer.Failed) as failed:
        stage.model_predictions(tmp_path / "train.jsonl")
    assert failed.value.code == "CANDIDATE_VIEW_REQUIRED"
    context, vcpus, reuse = _load(tmp_path, _context(family="motor"), threads="4")
    stage = producer.Stage(context, vcpus, reuse, tmp_path / "out")
    with pytest.raises(producer.Failed) as failed:
        stage.model_predictions(tmp_path / "train.jsonl")
    assert failed.value.code == "CANDIDATE_VIEW_REQUIRED"


def test_the_motor_reference_stage_is_registered_with_its_plan(tmp_path):
    from carbon.development_comparison import campaign_entrypoints as ce

    row = ce.ENTRYPOINTS["motor"]["reference"]
    assert (
        row["kind"] == "reference-panel"
        and ce.inspect(ROOT)["motor"]["reference"]
        == "REGISTERED_FILES_ONLY_IMAGE_NOT_CHECKED"
    )
    plan = json.loads((ROOT / row["plan"]).read_text())
    assert (
        len(plan["designs"]) == 24
        and len(plan["cases"]) == len({c["case_id"] for c in plan["cases"]}) == 230
    )
    context, _vcpus, reuse = _load(
        tmp_path, _context(family="motor", phase="reference"), threads="4"
    )
    assert (context["family"], context["phase"], reuse) == ("motor", "reference", [])


def _write_trace(case_dir, case, deck):
    """Synthetic solver output on the deck's own steps: the top maximum follows the
    extra power with a first-order lag above the context's initial temperature."""
    sizes, intervals = deck.time_steps(case)
    times, t = [0.0], 0.0
    for size, n in zip(sizes, intervals):
        for _ in range(n):
            t += size
            times.append(t)
    sched, temp, values = deck.schedule(case), case["initial_c"], []
    for i, ti in enumerate(times):
        if i:
            dt, tc = ti - times[i - 1], min(ti, deck.HORIZON_S)
            p = next(p0 + (p1 - p0) * (tc - t0) / (t1 - t0) for (t0, p0), (t1, p1) in itertools.pairwise(sched)
                     if t0 <= tc <= t1 and t1 > t0)  # fmt: skip
            temp += dt * (0.02 * (p - deck.BASE_W) - 0.05 * (temp - case["initial_c"]))
        values.append(temp)
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "scalars.dat").write_text(
        "".join(f"{a!r} {v + 273.15!r}\n" for a, v in zip(times, values))
    )
    (case_dir / "scalars.dat.names").write_text(
        "Variables in columns of matrix: scalars.dat\n   1: time\n   2: boundary max: temperature\n"
    )
    return max(
        (v + 273.15) - 273.15 for v in values
    )  # as the observer reads the Kelvin file


def test_f02_materials_separate_grids_reproduce_the_export(monkeypatch, tmp_path):
    import numpy as np

    from carbon.development_comparison import portfolio_baselines as pb
    from scripts.dev.evidence_runs import comparison_inputs as ci

    menu, deck = f02_export.menu, f02_export.menu.deck
    sys.path.insert(0, str(ROOT / "scripts/dev/reference_packages/elmer"))
    import f02_baselines as fb

    root, base_root, observed, ledger = tmp_path / "menu", tmp_path / "base", {}, []
    for ctx, base in menu.contexts():
        for p in menu.PEAKS_W:
            for d in menu.ON_TIMES_S:
                case = {**base, "peak_w": p, "on_time_s": d}
                name = menu.case_name(ctx, p, d)
                peak = _write_trace(root / "cases" / name, case, deck)
                energy = sum((b - a) * ((pa + pb_) / 2 - deck.BASE_W)
                             for (a, pa), (b, pb_) in zip(deck.schedule(case), deck.schedule(case)[1:]))  # fmt: skip
                observed[name] = {"peak_top_c": peak, "extra_energy_j": energy}
                ledger.append({"case": name, "tag": "primary", "wall_s": 1.0, "children_cpu": "0m1.000s 0m0.000s",
                               "cgroup_memory_peak_bytes": "1000"})  # fmt: skip
    for name, case in fb.contexts():
        _write_trace(base_root / "cases" / name, case, deck)
    (root / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ledger))
    monkeypatch.setattr(menu, "_observed", lambda r: observed)
    export = f02_export.build("unused")[0]
    materials, chunks = ci.f02_materials(export, root, base_root)
    assert len(materials["rows"]) == 384 and materials["settings"]["lags"] == 128
    assert materials["materials_digest"] == pb.tasks.digest(
        {k: v for k, v in materials.items() if k != "materials_digest"}
    )
    reducers = materials["settings"]["reducers"]
    by_key = {(r["candidate"], r["condition"]): r for r in materials["rows"]}
    for row in [r for r in materials["rows"]][::37]:
        pb._validate_payload("f02", row["payload"], reducers)
        payload = row["payload"]
        energy = float(
            np.sum(np.asarray(payload["extra_power_w"])[:-1])
            * (payload["time_s"][1] - payload["time_s"][0])
        )
        want = observed[menu.case_name(row["condition"], *row["coordinates"])][
            "extra_energy_j"
        ]
        assert energy == pytest.approx(want, rel=1e-9, abs=1e-9)
        assert row["calibration_source_sha256"] != row["reference_source_sha256"]
    witness = [w for c in chunks for w in c["rows"]]
    assert len(witness) == 384 and len(chunks) == 4
    for w in witness:
        assert (
            max(w["top_c"])
            == w["peak_top_c"]
            == observed[
                menu.case_name(
                    w["condition"],
                    *by_key[(w["candidate"], w["condition"])]["coordinates"],
                )
            ]["peak_top_c"]
        )
    files = []
    for c in chunks:
        files.append(tmp_path / f"comparator-witness-{c['chunk']:03d}.json")
        files[-1].write_text(json.dumps(c))
    manifest = ci.witness_manifest(export["export_digest"], files)
    assert [c["order"] for c in manifest["chunks"]] == [0, 1, 2, 3]


def test_the_battery_stage_runner_stamps_image_and_lock_on_every_record(
    tmp_path, monkeypatch
):
    import types
    from concurrent.futures import ThreadPoolExecutor

    from carbon.battery import truth_env
    from scripts.dev.battery import feasibility02

    lock, lock_sha = truth_env.load_lock(producer.ROOT)
    version = truth_env.pinned_version(lock)
    monkeypatch.setitem(
        sys.modules, "pybamm", types.SimpleNamespace(__version__=version)
    )
    monkeypatch.setattr(feasibility02, "ProcessPoolExecutor", ThreadPoolExecutor)
    statuses = {"a": "OK", "b": "REFERENCE_SOLVER_FAILED"}
    monkeypatch.setattr(
        feasibility02,
        "solve_one",
        lambda job: {**job, "status": statuses[job["case_id"]]},
    )
    monkeypatch.chdir(producer.ROOT)
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"jobs": [{"case_id": "a"}, {"case_id": "b"}]}))
    records = tmp_path / "records.jsonl"
    feasibility02.solve(jobs, records, 1)
    rows = [json.loads(x) for x in records.read_text().splitlines()]
    assert [r["case_id"] for r in rows] == ["a", "b"]
    assert all(type(r["core_s"]) is float and r["core_s"] >= 0 for r in rows)
    for row in rows:
        assert row[truth_env.PROVENANCE_FIELD] == {
            "schema": "carbon.battery.solver-provenance.v1",
            "solver_image": truth_env.TRUTH_IMAGE["base_image"],
            "overlay_lock": "scripts/dev/exam_design/locks/battery-overlay.lock.json",
            "overlay_lock_sha256": "sha256:" + lock_sha,
            "pybamm": version,
        }
    # The image the stage's entrypoint row registers.
    registered = campaign_entrypoints.ENTRYPOINTS["battery-v3"]["reference"]
    assert rows[0][truth_env.PROVENANCE_FIELD]["solver_image"].endswith(
        "@" + registered["image_digest"]
    )
