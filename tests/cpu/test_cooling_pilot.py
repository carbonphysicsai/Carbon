"""Cooling pilot contracts on synthetic data only; no solver or provider."""

import json

import numpy as np
import pytest

from carbon.challenge_pipeline import cooling_readiness as cr
from carbon.design_search import tasks
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import cooling_kit as ck
from carbon.development_comparison import cooling_pilot as worker
from carbon.development_comparison import cooling_pilot_fixture as fixture


def reseal_export(docs):
    body = {k: v for k, v in docs["export"].items() if k != "export_digest"}
    docs["export"]["export_digest"] = ca.sha256(ca.canonical(body))
    for role in ("policy", "reference", "cheap", "costs"):
        docs[role]["export_digest"] = docs["export"]["export_digest"]
    docs["cheap"]["predictions"]["export_digest"] = docs["export"]["export_digest"]


def rehash_train(docs, records):
    docs["train"] = b"\n".join(ca.canonical(r) for r in records) + b"\n"
    docs["cheap"]["train_sha256"] = ca.sha256(docs["train"])
    return pins(docs)


def pins(docs):
    return {
        k: ca.sha256(v if isinstance(v, bytes) else ca.canonical(v))
        for k, v in docs.items()
    }


def retask(docs, update):
    for entry in docs["export"]["questions"]:
        update(entry["task"])
        body = {k: v for k, v in entry["task"].items() if k != "task_digest"}
        entry["task"]["task_digest"] = tasks.digest(body)
    reseal_export(docs)


def test_kit_reads_only_action_and_frozen_service_and_derives_hydraulics():
    reg = fixture.registration()
    kit = ck.kit_from_bytes(ca.canonical(reg))
    row = {"action": fixture.action(0.3), "condition": "fixture-uniform"}
    inputs = kit.row_inputs(row)
    assert kit.domain(inputs)
    assert np.isfinite(ca.Network(kit)._x([inputs])).all()
    raw = {"peak_case_c": 80.0, "cell_pressure_drop_pa": 1000.0}
    result = kit.row_values(row, [raw])
    assert result["peak_case_c"] == 80
    assert result["half_cell_hydraulic_power_w"] == pytest.approx(
        1000 * result["half_cell_flow_m3_s"]
    )
    assert not kit.domain({**inputs, "flow_lpm_per_kw": 2})
    assert not kit.domain({**inputs, "service": "unregistered-map"})
    assert not kit.domain({**inputs, "channel_width_mm": 0.31})


def test_dry_run_uses_three_seeds_shared_cluster_and_complete_panel_cost():
    result = fixture.dry_run()
    assert result["scope"] == "SYNTHETIC_FIXTURE"
    assert not result["real_training_executed"]
    assert result["reference_solves"] == 0
    assert result["thresholds"] == "HUMAN_INPUT"
    assert [r["seed"] for r in result["reports"]] == [0, 1, 2]
    first = result["reports"][0]
    jobs = first["input"]["panel"]["jobs"]
    assert len({j["cluster_id"] for j in jobs}) == 1
    assert jobs[0]["candidates"][0]["solve_cost"] == {"wall_s": 30, "core_s": 60}
    for assumption in first["report"]["advantage_and_headroom"]:
        assert all(
            row["paired_bootstrap_ci"] is None for row in assumption["model_vs_cheap"]
        )
    prep = first["input"]["preparation_cost"]
    assert prep["baseline"] == {"wall_s": 25, "core_s": 50}
    assert prep["model"]["core_s"] > 50
    assert len(first["pointwise_by_service"]) == 3
    assert all(s["reference_rows"] == 3 for s in first["pointwise_by_service"].values())


def test_fixture_cannot_enter_public_run_and_public_inventory_is_enforced():
    docs, pinset = fixture.documents()
    with pytest.raises(worker.PilotHold, match="FIXTURE_PROMOTION"):
        worker.prepare(docs, pinset)
    docs["registration"]["scope"] = "PUBLIC_DEVELOPMENT"
    body = {k: v for k, v in docs["registration"].items() if k != "digest"}
    docs["registration"] = cr.seal(body)
    with pytest.raises(worker.PilotHold):
        worker.prepare(docs, pins(docs))


def test_legacy_plate_peak_cannot_be_relabelled_as_TIM2_truth():
    docs, _ = fixture.documents()
    docs["export"]["questions"][0]["reference"][0]["values"]["peak_case_c"] -= 5
    reseal_export(docs)
    with pytest.raises(worker.PilotHold, match="OBSERVER_MISMATCH"):
        worker.prepare(docs, pins(docs), fixture=True)


def test_train_labels_need_independent_colocated_observations():
    docs, _ = fixture.documents()
    records = [json.loads(r) for r in docs["train"].splitlines()]
    records[0]["outputs"]["peak_case_c"] -= 5
    pinset = rehash_train(docs, records)
    with pytest.raises(worker.PilotHold, match="TRAIN_TIM2_OBSERVER_MISMATCH"):
        worker.prepare(docs, pinset, fixture=True)


def test_whole_geometry_disjointness_includes_all_sibling_maps():
    docs, _ = fixture.documents()
    records = [json.loads(r) for r in docs["train"].splitlines()]
    reg = docs["registration"]
    for record in records[:3]:
        record["inputs"].update(fixture.action(0.2))
        raw = fixture.observation(reg, fixture.action(0.2), record["inputs"]["service"])
        observed = cr.observe(
            reg, fixture.action(0.2), record["inputs"]["service"], **raw
        )
        record["observation"] = raw
        record["outputs"] = {k: observed[k] for k in ck.OUTPUTS}
    pinset = rehash_train(docs, records)
    with pytest.raises(worker.PilotHold, match="WHOLE_GEOMETRY"):
        worker.prepare(docs, pinset, fixture=True)


@pytest.mark.parametrize(
    "role,key", [("reference", "observations"), ("costs", "reference")]
)
def test_missing_map_or_cost_is_reference_hold(role, key):
    docs, _ = fixture.documents()
    docs[role][key].pop()
    with pytest.raises(worker.PilotHold, match="COMPLETE|INCOMPLETE"):
        worker.prepare(docs, pins(docs), fixture=True)


def test_map_or_observer_drift_fails_closed():
    docs, _ = fixture.documents()
    docs["reference"]["observations"][0]["faces"][0]["q_w_m2"] += 1
    with pytest.raises(ValueError, match="frozen"):
        worker.prepare(docs, pins(docs), fixture=True)


def test_uncertainty_cannot_be_removed_and_hard_limit_cannot_be_relaxed():
    docs, _ = fixture.documents()
    retask(docs, lambda t: t["limits"][0].update(band=0))
    with pytest.raises(worker.PilotHold, match="UNCERTAINTY"):
        worker.prepare(docs, pins(docs), fixture=True)
    docs, _ = fixture.documents()
    retask(docs, lambda t: t["limits"][0].update(value=86))
    with pytest.raises(worker.PilotHold, match="HARD_LIMIT_RELAXED"):
        worker.prepare(docs, pins(docs), fixture=True)


def test_none_feasible_questions_are_retained_without_redraw():
    docs, _ = fixture.documents()
    retask(docs, lambda t: t["limits"][0].update(value=1))
    result = worker.execute(docs, pins(docs), fixture=True, trainer=fixture.trainer)
    learning = result["reports"][0]["input"]["learning"]
    assert len(learning) == 2
    assert all(r["reference_status"] == "NONE_FEASIBLE" for r in learning)
    assert all(r["decision_agreement"] for r in learning)


def test_unresolved_reference_blocks_advantage_without_candidate_failure():
    docs, _ = fixture.documents()
    peak = max(
        r["values"]["peak_case_c"] for r in docs["export"]["questions"][0]["reference"]
    )
    retask(docs, lambda t: t["limits"][0].update(value=peak))
    result = worker.execute(docs, pins(docs), fixture=True, trainer=fixture.trainer)
    report = result["reports"][0]
    assert any(
        r["reference_status"] == "UNRESOLVED" for r in report["input"]["learning"]
    )
    assert all(
        r["equal_budget"]["status"] != "OK"
        for r in report["report"]["advantage_and_headroom"]
    )


def test_bundle_pins_and_public_path_guards(tmp_path):
    docs, _ = fixture.documents()
    manifest = {"schema": worker.SCHEMA, "scope": "PUBLIC_DEVELOPMENT", "sources": {}}
    for role, value in docs.items():
        raw = value if isinstance(value, bytes) else ca.canonical(value)
        name = role + (".jsonl" if role == "train" else ".json")
        (tmp_path / name).write_bytes(raw)
        manifest["sources"][role] = {"path": name, "sha256": ca.sha256(raw)}
    path = tmp_path / "bundle.json"
    path.write_bytes(ca.canonical(manifest))
    loaded, _ = worker.load(path, ca.sha256(path.read_bytes()))
    assert loaded["registration"]["scope"] == "SYNTHETIC_FIXTURE"
    with pytest.raises(worker.PilotHold, match="FIXTURE_PROMOTION"):
        worker.prepare(loaded, pins(loaded))
    manifest["sources"]["train"]["path"] = "sealed/not-read.jsonl"
    path.write_bytes(ca.canonical(manifest))
    with pytest.raises(worker.PilotHold, match="PUBLIC_RELATIVE"):
        worker.load(path, ca.sha256(path.read_bytes()))


def test_cli_reports_typed_hold_and_does_not_overwrite(tmp_path, capsys):
    out = tmp_path / "result.json"
    assert worker.main(["dry-run", "--out", str(out)]) == 0
    original = out.read_bytes()
    assert worker.main(["dry-run", "--out", str(out)]) == 2
    assert out.read_bytes() == original
    assert not json.loads(capsys.readouterr().out.splitlines()[-1])["candidate_failure"]


def test_bundle_ancestor_symlink_is_refused_before_read(tmp_path):
    real = tmp_path / "public"
    real.mkdir()
    linked = tmp_path / "link"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(worker.PilotHold, match="PUBLIC_LOCAL_BUNDLE"):
        worker.load(linked / "not-read.json", "sha256:" + "1" * 64)


def test_stand_in_cannot_be_injected_into_public_execution():
    docs, pinset = fixture.documents()
    with pytest.raises(worker.PilotHold, match="STAND_IN"):
        worker.execute(docs, pinset, trainer=fixture.trainer)


def test_reference_job_plan_keeps_bulk_and_protected_work_separate(tmp_path):
    out = tmp_path / "jobs.json"
    assert worker.main(["data-plan", "--out", str(out)]) == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert sum(row["jobs"] for row in plan["public_jobs"]) == 92
    assert plan["timing_and_memory"]["cpu_seconds_per_coarse_solve_low_base_high"] == [
        1620,
        3240,
        4860,
    ]
    assert plan["protected_half"]["jobs"] is None
    assert not plan["protected_half"]["included_in_this_worker"]
    assert not plan["existing_PKT09_bounded_topup"]["cold_generation_fits_this_cap"]


def test_real_kit_uses_shared_network_without_recipe_override():
    # A small numerical diagnostic of the new scaling/reduction, not a pilot.
    docs, pinset = fixture.documents()
    kit, _export, train, *_ = worker.prepare(docs, pinset, fixture=True)
    network = ca.Network(kit, settings={"steps": 2, "width": 4, "depth": 1})
    network.fit(train, seed=0)
    row = {"action": fixture.action(0.3), "condition": "fixture-uniform"}
    prediction = network.predict([kit.row_inputs(row)])[0]
    assert set(prediction) == set(ck.OUTPUTS)
    assert all(np.isfinite(v) for v in prediction.values())
    assert set(kit.row_values(row, [prediction])) == set(ck.OBSERVABLES)
