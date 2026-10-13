"""Synthetic motor pilot wiring and failure-boundary regressions only."""

import json
import os

import numpy as np
import pytest

from carbon.design_search import tasks
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import motor_10p12s_kit as mk
from carbon.development_comparison import motor_pilot as mp
from carbon.development_comparison import motor_pilot_fixture as fixture
from carbon.development_comparison import motor_pilot_kit as pk


def reseal(docs):
    export = docs["export"]
    export.pop("export_digest")
    export["export_digest"] = ca.sha256(ca.canonical(export))
    for role in ("policy", "reference", "costs", "cheap"):
        docs[role]["export_digest"] = export["export_digest"]
    docs["cheap"]["predictions"]["export_digest"] = export["export_digest"]
    pins = {
        k: ca.sha256(v if k == "train" else ca.canonical(v)) for k, v in docs.items()
    }
    for role in ("policy", "reference"):
        docs[role]["domain_digest"] = pins["domain"]
    docs["cheap"]["train_digest"] = pins["train"]
    return {
        k: ca.sha256(v if k == "train" else ca.canonical(v)) for k, v in docs.items()
    }


def task_seal(task):
    task.pop("task_digest")
    task["task_digest"] = tasks.digest(task)


def test_composite_wraps_the_existing_skew_once_and_keeps_peak_separate():
    kit = pk.kit({0: fixture.geometry(1)})
    row = {"condition": pk.CONDITION, "action": {"design": 0, "skew_deg": 4}}
    queries = kit.row_queries(row)
    assert [(q["j_a_mm2"], q["gamma_deg"]) for q in queries] == [
        (10, 10),
        (10, 0),
        (10, -10),
        (15, 10),
        (15, 0),
        (15, -10),
        (0, 0),
    ]
    curves = [
        {o: float(v) for o, v in zip(mk.OUTPUTS, np.arange(48) * (i + 1))}
        for i in range(7)
    ]
    got = kit.row_values(row, curves)
    expected = np.mean(
        [np.roll(np.arange(48) * (i + 1), -s) for i, s in zip(range(3), (-8, 0, 8))],
        axis=0,
    )
    assert [got[f"holding_t{i:02d}"] for i in range(48)] == pytest.approx(expected)
    base = mk.kit({0: fixture.geometry(1)})
    for role, part, condition in (
        ("holding", curves[:3], "J10-g0"),
        ("peak", curves[3:6], "J15-g0"),
    ):
        metrics = base.row_values({**row, "condition": condition}, part + [curves[6]])
        assert got[f"{role}_mean_nm"] == metrics["mean_nm"]
        assert got[f"{role}_ripple_fraction"] == metrics["ripple_fraction"]
    assert got["cogging_nm"] == np.ptp([got[f"cogging_t{i:02d}"] for i in range(48)])


def test_dry_run_all_arms_all_seeds_counts_unsafe_peak_and_never_promotes():
    result = fixture.dry_run()
    assert result["scope"] == "SYNTHETIC_FIXTURE"
    assert result["real_pilot_executed"] is False
    assert result["reference_solves"] == 0
    assert result["thresholds"] == "HUMAN_INPUT"
    assert [r["seed"] for r in result["reports"]] == [0, 1, 2]
    for row in result["reports"]:
        assert row["receipt"]["stand_in"] is True
        assert any(v["false_feasible"] is True for v in row["input"]["learning"])
        assert row["report"]["qualification"] == "UNDECIDED"
        assert len(row["report"]["advantage_and_headroom"]) == 2
        assert {j["cluster_id"] for j in row["input"]["panel"]["jobs"]} == {
            "synthetic-shared-geometry-bank"
        }
        assert row["curve_diagnostics"]["peak"]["covered_signed_samples"] == 6 * 48
        job = row["input"]["panel"]["jobs"][0]
        assert len(job["candidates"]) == 2  # six skew actions, two paid geometry panels
        assert job["solver_order"] == ["geometry-0", "geometry-1"]
        assert job["candidates"][0]["reference"]["status"] == "INFEASIBLE"
        assert job["candidates"][1]["reference"]["status"] == "FEASIBLE"


@pytest.mark.parametrize(
    "change,reason",
    [
        ("peak_curve", "ELEVEN_HOLDING_PEAK_COGGING"),
        ("train_peak", "COMPLETE_TRAIN_ROLES"),
        ("relax_peak", "BUYER_LIMIT_RELAXATION"),
        ("missing_peak_limit", "ALL_HARD_BUYER_LIMITS"),
        ("wrong_curve", "SIGNED_REFERENCE_OBSERVER_MISMATCH"),
        ("linear_acceptance", "PIN_OR_OWNER_INPUT_MISSING"),
        ("bad_image", "MOTOR_REFERENCE_APPLICABILITY"),
        ("partial_cost", "COMPLETE_ELEVEN_SWEEP_COST"),
        ("fake_cheap", "CHEAP_SIGNED_CURVE_OBSERVER_MISMATCH"),
        ("prefix", "REGISTERED_ATTEMPT_CAP"),
        ("P", "P_Q_W_HOLD"),
        ("order", "COMPLETE_PRECOMMITTED_SOLVER_ORDER"),
        ("cluster", "SHARED_PHYSICAL_BANK_CLUSTER"),
    ],
)
def test_missing_reference_or_policy_is_a_hold_before_fitting(change, reason):
    docs, pins = fixture.documents()
    if change == "peak_curve":
        docs["domain"]["curves"]["0"].pop()
    elif change == "train_peak":
        docs["train"] = b"\n".join(docs["train"].splitlines()[:-1]) + b"\n"
    elif change in ("relax_peak", "missing_peak_limit"):
        task = docs["export"]["questions"][0]["task"]
        limit = next(v for v in task["limits"] if v["quantity"] == "peak_mean_nm")
        if change == "relax_peak":
            limit["value"] = 10
        else:
            task["limits"].remove(limit)
        task_seal(task)
    elif change == "wrong_curve":
        docs["export"]["questions"][0]["reference"][0]["values"]["peak_t01"] += 0.3
    elif change == "linear_acceptance":
        docs["reference"]["adequacy_receipt"] = "ACCEPTED_LINEAR_DISCRETISATION_ONLY"
    elif change == "bad_image":
        docs["reference"]["image_digest"] = "sha256:" + "a" * 64
    elif change == "partial_cost":
        docs["costs"]["reference"][0]["raw_sweeps"] = 6
    elif change == "fake_cheap":
        docs["cheap"]["predictions"]["rows"][0]["values"]["peak_mean_nm"] += 1
    elif change == "prefix":
        docs["costs"]["new_sweep_attempts"] = 7
    elif change == "P":
        docs["policy"]["question_law"]["P"] = "HUMAN_INPUT"
    elif change == "order":
        docs["policy"]["solver_orders"]["fixture-question-0"].pop()
    elif change == "cluster":
        entry = docs["export"]["questions"][1]
        entry["support_case"] = "different-cluster-for-same-bank"
        entry["task"]["identity"]["reference_bank"] = entry["support_case"]
        task_seal(entry["task"])
    pins = reseal(docs)
    with pytest.raises(mp.PilotHold, match=reason):
        mp.execute(
            docs,
            pins,
            fixture=True,
            trainer=lambda *a, **k: pytest.fail("fit happened before HOLD"),
        )


def test_train_and_all_skew_siblings_of_held_geometry_are_disjoint():
    docs, _pins = fixture.documents()
    records = [json.loads(line) for line in docs["train"].splitlines()]
    for r in records[:11]:
        r["inputs"].update(docs["domain"]["geometry"]["0"])
    docs["train"] = ("\n".join(json.dumps(r) for r in records) + "\n").encode("utf-8")
    with pytest.raises(mp.PilotHold, match="WHOLE_GEOMETRY"):
        mp.prepare(docs, reseal(docs), fixture=True)


def test_numeric_json_spelling_cannot_bypass_geometry_holdout_or_diversity():
    docs, _pins = fixture.documents()
    g = {
        "magnet_mm": 2,
        "coverage": 0.7,
        "airgap_mm": 0.45,
        "tooth_frac": 0.25,
        "opening_frac": 0.05,
        "slot_bottom_mm": 37,
    }
    assert mp.geometry_key(g) == mp.geometry_key({k: float(v) for k, v in g.items()})
    # This is a physical TRAIN geometry despite its differently spelled integers.
    docs["domain"]["geometry"]["0"] = g
    with pytest.raises(mp.PilotHold, match="WHOLE_GEOMETRY"):
        mp.prepare(docs, reseal(docs), fixture=True)
    docs["domain"]["geometry"]["1"] = {k: float(v) for k, v in g.items()}
    with pytest.raises(mp.PilotHold, match="DUPLICATE_PHYSICAL_GEOMETRY"):
        mp.prepare(docs, reseal(docs), fixture=True)


def test_fixture_inputs_refused_by_public_path():
    docs, pins = fixture.documents()
    with pytest.raises(mp.PilotHold, match="DOMAIN_REQUIRED"):
        mp.prepare(docs, pins)


def test_a_trainer_stand_in_cannot_claim_a_public_pilot():
    docs, pins = fixture.documents()
    with pytest.raises(mp.PilotHold, match="FIXED_CPU_TRAINER"):
        mp.execute(docs, pins, trainer=fixture.stand_in)


def test_reference_band_overlap_stays_unresolved_without_model_failure():
    docs, _pins = fixture.documents()
    task = docs["export"]["questions"][0]["task"]
    for v in task["limits"]:
        if v["quantity"] == "peak_mean_nm":
            v["band"] = 0.2
    task_seal(task)
    result = mp.execute(docs, reseal(docs), fixture=True, trainer=fixture.stand_in)
    row = result["reports"][0]["input"]["learning"][0]
    assert row["reference_status"] == "UNRESOLVED"
    assert row["pointwise_error"] is None and row["false_feasible"] is None


def bundle(tmp_path):
    docs, _pins = fixture.documents()
    body = {"schema": mp.SCHEMA, "scope": "PUBLIC_DEVELOPMENT", "sources": {}}
    for role, doc in docs.items():
        data = doc if role == "train" else ca.canonical(doc)
        name = role + (".jsonl" if role == "train" else ".json")
        (tmp_path / name).write_bytes(data)
        body["sources"][role] = {"path": name, "sha256": ca.sha256(data)}
    mp.write(tmp_path / "bundle.json", body)
    return tmp_path / "bundle.json", body


def test_load_checks_exact_bytes_and_public_path_before_reading(tmp_path):
    path, body = bundle(tmp_path)
    docs, pins = mp.load(path)
    mp.prepare(docs, pins, fixture=True)
    (tmp_path / "train.jsonl").write_bytes(b"changed")
    with pytest.raises(mp.PilotHold, match="SOURCE_PIN_MISMATCH"):
        mp.load(path)
    body["sources"]["train"]["path"] = "../absent.jsonl"
    mp.write(path, body)
    with pytest.raises(mp.PilotHold, match="PUBLIC_RELATIVE"):
        mp.load(path)


def test_sealed_manifest_refused_before_file_access(tmp_path):
    with pytest.raises(mp.PilotHold, match="PUBLIC_LOCAL"):
        mp.load(tmp_path / "sealed" / "does-not-exist.json")


def test_acquisition_count_units_and_sealed_separation():
    plan = mp.acquisition_plan()
    assert sum(j["raw_sweep_jobs"] for j in plan["public_jobs"]) == 308
    assert sum(j["field_systems"] for j in plan["public_jobs"]) == 308 * 48
    assert plan["new_attempt_prefix"]["field_systems"] == 4 * 48 + 2 * 96
    assert plan["corpus_standard_only_allocated_cpu_h"] == pytest.approx(369.6)
    assert plan["fresh_corpus_fits_56_cpu_h_pilot_cap"] is False
    assert plan["sealed_half"]["jobs"] is None
    assert plan["sealed_half"]["mount_in_public_worker"] is False
    assert plan["memory"]["measured_peak_rss_bytes"] is None
    assert len(plan["commands"]) == 11


def test_cli_dry_run_and_plan_are_no_execution(tmp_path, capsys):
    for cmd in ("dry-run", "data-plan"):
        assert mp.main([cmd, "--out", str(tmp_path / (cmd + ".json"))]) == 0
        assert json.loads(capsys.readouterr().out)["reference_solves"] == 0
    data = json.loads((tmp_path / "dry-run.json").read_text(encoding="utf-8"))
    assert not data["real_pilot_executed"]


def test_fit_cpu_cap_is_aggregate_across_public_seeds():
    docs, pins = fixture.documents()

    def slow(*args, **kwargs):
        pred, receipt = fixture.stand_in(*args, **kwargs)
        receipt["cost"]["fit"]["fit_cpu_s"] = 8000
        return pred, receipt

    with pytest.raises(mp.PilotHold, match="AGGREGATE_FIT_CAP"):
        mp.execute(docs, pins, fixture=True, trainer=slow)


@pytest.mark.skipif(os.name != "posix", reason="shared pod launcher requires Linux")
def test_pod_spec_refuses_fixture_bundle_before_launcher_dispatch(tmp_path):
    path, _ = bundle(tmp_path)
    with pytest.raises(mp.PilotHold):
        mp.pod_spec(path, "a" * 40, minutes=60, rate_ceiling=0.5, cap_usd=2)


def test_tiny_real_trainer_wiring_uses_only_masked_reference(monkeypatch):
    jax = pytest.importorskip("jax")
    docs, pins = fixture.documents()
    kit, export, train, *_ = mp.prepare(docs, pins, fixture=True)
    for e in export["questions"]:
        for r in e["reference"]:
            r["values"] = {k: 0.0 for k in pk.OBSERVABLES}
    original = ca.run

    def tiny(*args, **kwargs):
        assert jax.config.jax_default_device.platform == "cpu"
        return original(*args, **kwargs, settings={"steps": 1, "width": 8, "depth": 1})

    monkeypatch.setattr(ca, "run", tiny)
    pred, receipt = mp.cpu_trainer(
        kit,
        export,
        train,
        scope="SYNTHETIC_FIXTURE",
        seed=0,
        backend="jax",
        code={},
    )
    assert receipt["kit"] == kit.kit_id
    assert receipt["code"]["execution_platform"] == "cpu"
    assert receipt["cost"]["inference"]["model_queries"] == 6 * 7
    assert len(pred["rows"]) == 6
    assert all(set(r["values"]) == set(pk.OBSERVABLES) for r in pred["rows"])


@pytest.mark.skipif(
    os.name != "posix", reason="shared operator CPU placement requires Linux"
)
def test_pod_spec_uses_existing_guard_and_counts_export_tail(tmp_path, monkeypatch):
    from carbon.agent_campaign import pod_jobs

    path, _ = bundle(tmp_path)
    # Test specification mechanics only; fixture acceptance remains separately refused.
    monkeypatch.setattr(mp, "prepare", lambda *a: None)
    spec = mp.pod_spec(path, "a" * 40, minutes=60, rate_ceiling=0.5, cap_usd=2)
    assert spec["module"] == "carbon.development_comparison.motor_pilot"
    assert pod_jobs.load_spec(spec).minutes + pod_jobs.EXPORT_MINUTES <= 3840
    with pytest.raises(pod_jobs.SpecRefused):
        mp.pod_spec(path, "a" * 40, minutes=3800, rate_ceiling=1.2, cap_usd=77.2)
    with pytest.raises(mp.PilotHold, match="LIFECYCLE"):
        mp.pod_spec(path, "a" * 40, minutes=3840, rate_ceiling=0.5, cap_usd=40)
