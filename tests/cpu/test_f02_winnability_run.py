"""Toy-only wiring and refusal diagnostics, no training or reference solves."""

import copy
import json
import os

import pytest

from carbon.agent_campaign import pod_jobs
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import f02_pilot as pilot
from carbon.development_comparison import f02_pilot_fixture as fixture


def test_tiny_standin_runs_all_three_seeds_and_opt12():
    result = fixture.dry_run()
    assert result["schema"] == pilot.FIXTURE
    assert result["scope"] == "SYNTHETIC_FIXTURE"
    assert result["real_pilot_executed"] is False
    assert result["customer_result"] is False
    assert result["reference_solves"] == 0
    assert result["aggregate_fit_cpu_s"] == 3
    assert [r["seed"] for r in result["reports"]] == [0, 1, 2]
    for item in result["reports"]:
        assert item["report"]["qualification"] == "UNDECIDED"
        assert item["report"]["thresholds"] == "HUMAN_INPUT"
        assert item["input"]["preparation_cost"]["model"]["core_s"] == pytest.approx(
            26.7
        )
        assert item["input"]["preparation_cost"]["baseline"]["core_s"] == 35
        for curve in item["report"]["advantage_and_headroom"]:
            assert curve["equal_budget"]["status"] == "OK"
            assert curve["equal_budget"]["independent_clusters"] == 1
            assert all(
                c["paired_bootstrap_ci"] is None for c in curve["model_vs_cheap"]
            )
            assert {"solver_alone", "model_then_solver", "baseline_then_solver"} <= set(
                curve["equal_budget"]["curves"][0]["estimates"]
            )


def test_trainer_does_not_receive_reference_and_objective_is_known():
    docs, pins = fixture.documents()
    result = pilot.execute(docs, pins, fixture=True, trainer=fixture.trainer)
    # The stand-in deliberately predicts -999 J. It must never set the objective.
    panel = result["reports"][0]["input"]["panel"]
    assert all(
        c["reference"]["value"] > 0
        for j in panel["jobs"]
        for c in j["candidates"]
        if c["reference"]["status"] == "FEASIBLE"
    )
    assert result["reports"][0]["report"]["learning_unit"] == "K"


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda d: d["cheap_screen"].update(method="one-node-RC"), "SPATIAL_ROM"),
        (lambda d: d["cheap_screen"].update(calibration_role="HELDOUT"), "TRAIN_ONLY"),
        (
            lambda d: d["cheap_screen"].update(train_sha256="sha256:" + "f" * 64),
            "TRAIN_ONLY",
        ),
        (
            lambda d: d["cheap_screen"]["predictions"].update(
                scope="PUBLIC_DEVELOPMENT"
            ),
            "FIXTURE_PROMOTION",
        ),
        (lambda d: d["cheap_screen"].update(source_digests=[]), "ACQUISITION"),
        (lambda d: d["policy"].update(frozen_before_heldout=False), "PREDECLARED"),
        (lambda d: d["policy"]["question_law"].update(P="HUMAN_INPUT"), "P_Q_W"),
        (
            lambda d: d["reference_receipt"].update(image_digest="sha256:" + "a" * 64),
            "REFERENCE_FAMILY",
        ),
        (lambda d: d["reference_receipt"].update(convergence=None), "DIGEST"),
        (
            lambda d: d["costs"]["preparation"]["model"].update(core_s=None),
            "NOT_MEASURED",
        ),
        (lambda d: d["costs"].update(acquisition_sources=[]), "ACQUISITION_COST"),
        (lambda d: d["costs"]["reference"].pop(), "COMPLETE_REFERENCE_COST"),
    ],
)
def test_missing_or_incompatible_material_holds_before_a_report(mutation, reason):
    docs, pins = fixture.documents()
    mutation(docs)
    with pytest.raises(pilot.PilotHold, match=reason):
        pilot.execute(docs, pins, fixture=True, trainer=fixture.trainer)


def test_public_run_rejects_fixture_train_before_training():
    docs, pins = fixture.documents()
    with pytest.raises(pilot.PilotHold, match="PUBLIC_DATA"):
        pilot.execute(docs, pins, trainer=lambda *a, **k: pytest.fail("must not fit"))


def test_physical_overlap_ignores_ids_and_refinement_rungs():
    docs, pins = fixture.documents()
    e = docs["export"]["questions"][0]
    row = e["reference"][0]
    training = json.loads(docs["train"].splitlines()[0])
    training["case_id"] = "different-name-and-rung"
    training["inputs"] = {
        **pilot.context(row["condition"]),
        **e["task"]["actions"][row["candidate"]],
    }
    docs["train"] += ca.canonical(training) + b"\n"
    pins["train"] = ca.sha256(docs["train"])
    with pytest.raises(pilot.PilotHold, match="OVERLAP"):
        pilot.execute(docs, pins, fixture=True, trainer=fixture.trainer)


def test_refinement_unresolved_is_not_a_candidate_failure():
    docs, pins = fixture.documents()
    body = copy.deepcopy(docs["export"])
    body.pop("export_digest")
    body["questions"][0]["reference"][0]["values"]["peak_top_c"] = 95.0
    from carbon.design_search import producer_panels

    new_export = producer_panels.seal_export(body)
    old = docs["export"]["export_digest"]
    docs["export"] = new_export
    new = new_export["export_digest"]
    for doc in (
        docs["policy"],
        docs["costs"],
        docs["cheap_screen"],
        docs["reference_receipt"],
        docs["cheap_screen"]["predictions"],
    ):
        assert doc["export_digest"] == old
        doc["export_digest"] = new
    docs["cheap_screen"]["policy_digest"] = ca.sha256(ca.canonical(docs["policy"]))
    pins["policy"] = docs["cheap_screen"]["policy_digest"]
    result = pilot.execute(docs, pins, fixture=True, trainer=fixture.trainer)
    source = result["reports"][0]["input"]
    assert source["learning"][0]["reference_status"] == "UNRESOLVED"
    assert source["learning"][0]["false_feasible"] is None
    assert (
        result["reports"][0]["report"]["advantage_and_headroom"][0]["equal_budget"][
            "status"
        ]
        == "UNRESOLVED_PANEL"
    )


def test_aggregate_fit_ceiling_cannot_select_a_lucky_replica():
    docs, pins = fixture.documents()

    def costly(*args, **kwargs):
        prediction, receipt = fixture.trainer(*args, **kwargs)
        receipt["cost"]["fit"]["fit_cpu_s"] = 8000
        return prediction, receipt

    with pytest.raises(pilot.PilotHold, match="CAP_EXCEEDED"):
        pilot.execute(docs, pins, fixture=True, trainer=costly)


def write_bundle(tmp_path):
    docs, _pins = fixture.documents()
    sources = {}
    for key, doc in docs.items():
        raw = doc if isinstance(doc, bytes) else ca.canonical(doc)
        path = tmp_path / (key + (".jsonl" if key == "train" else ".json"))
        path.write_bytes(raw)
        sources[key] = {"path": path.name, "sha256": ca.sha256(raw)}
    bundle = tmp_path / "bundle.json"
    bundle.write_bytes(
        ca.canonical(
            {"schema": pilot.SCHEMA, "scope": "PUBLIC_DEVELOPMENT", "sources": sources}
        )
    )
    return bundle


def test_loader_checks_every_pin_before_use_and_refuses_escape(tmp_path):
    bundle = write_bundle(tmp_path)
    pilot._load(bundle)
    (tmp_path / "train.jsonl").write_bytes(b"changed")
    with pytest.raises(pilot.PilotHold, match="PIN_OR_SIZE"):
        pilot._load(bundle)
    raw = json.loads(bundle.read_bytes())
    raw["sources"]["train"]["path"] = "../train.jsonl"
    bundle.write_bytes(ca.canonical(raw))
    with pytest.raises(pilot.PilotHold, match="LOCAL_PUBLIC"):
        pilot._load(bundle)


@pytest.mark.skipif(
    os.name != "posix",
    reason="launcher economic validator imports Linux fcntl; canonical CI exercises it",
)
def test_pod_spec_uses_existing_launcher_cap_and_never_launches(tmp_path, monkeypatch):
    bundle = write_bundle(tmp_path)
    monkeypatch.setattr(
        pod_jobs, "run", lambda *a, **k: pytest.fail("no provider call")
    )
    spec = pilot.pod_spec(bundle, "a" * 40)
    validated = pod_jobs.load_spec(spec)
    assert validated.economics()["worst_case_usd"] <= 10
    assert spec["compute"] == {"kind": "cpu", "flavor": "cpu5c", "vcpus": 32}
    assert spec["image"] == "study"
    assert spec["module"] == "carbon.development_comparison.f02_pilot"
    assert spec["minutes"] + pod_jobs.EXPORT_MINUTES <= 480


def test_command_dry_run_writes_separate_schema(tmp_path, capsys):
    out = tmp_path / "result.json"
    assert pilot.main(["dry-run", "--out", str(out)]) == 0
    assert "FIXTURE_WIRING_ONLY" in capsys.readouterr().out
    assert json.loads(out.read_bytes())["schema"] == pilot.FIXTURE
