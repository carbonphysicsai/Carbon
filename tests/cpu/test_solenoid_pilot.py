"""Toy data only: no training, reference solver, native acceptance or spend."""

import copy
import json
import os

import pytest

from carbon.agent_campaign import pod_jobs
from carbon.design_search import equal_budget as eb
from carbon.design_search import solenoid_budget as budget
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import solenoid_kit as kit
from carbon.development_comparison import solenoid_pilot as pilot
from carbon.development_comparison import solenoid_pilot_fixture as fixture


def test_real_family_route_is_isolated_representative_proposal():
    assert eb.CHALLENGE_ROUTES[kit.FAMILY]["validator"] is budget.validate
    assert eb.CHALLENGE_ROUTES[kit.FAMILY]["representative"] is True
    assert eb.CHALLENGE_ROUTES[kit.FAMILY]["registration_required"] is True
    assert ca.kits()[kit.FAMILY] is kit.kit_from_bytes
    proposal = budget.proposal()
    parsed = budget.validate(proposal)
    assert parsed.cap(kit.FAMILY, "base").solver_evaluations == 12
    changed = copy.deepcopy(proposal)
    changed["challenge_budgets"]["motor"] = {}
    with pytest.raises(ValueError, match="exact representative"):
        budget.validate(changed)


def test_full_curve_kit_needs_buyer_and_domain_inputs():
    docs, _pins = fixture.documents()
    configured = kit.kit_from_bytes(ca.canonical(docs["domain"]))
    assert len(configured.targets) == 135
    assert len(configured.observables) == 136
    assert configured.model_id != "motor"
    assert configured.domain({**{n: b[0] for n, b in kit.COORDS}, "stratum": "hot"})
    bad = copy.deepcopy(docs["domain"])
    bad["anchor_digest"] = "HUMAN_INPUT"
    with pytest.raises(ca.ArmRefused, match="ABSOLUTE_INPUT"):
        kit.kit_from_bytes(ca.canonical(bad))
    bad = copy.deepcopy(docs["domain"])
    bad["force_targets_n"]["hot"] = None
    with pytest.raises(ca.ArmRefused, match="TARGETS"):
        kit.kit_from_bytes(ca.canonical(bad))


def test_three_arm_standin_keeps_geometry_cluster_and_full_conditions():
    result = fixture.dry_run()
    assert result["schema"] == pilot.FIXTURE
    assert result["real_pilot_executed"] is False
    assert result["reference_solves"] == 0 and result["customer_result"] is False
    assert result["aggregate_fit_cpu_s"] == 3
    for run in result["reports"]:
        assert run["report"]["qualification"] == "UNDECIDED"
        assert run["input"]["learning_unit"] == "N"
        for j in run["input"]["panel"]["jobs"]:
            assert all(c["solve_cost"]["core_s"] == 30 for c in j["candidates"])
        assert run["input"]["preparation_cost"]["model"]["core_s"] == pytest.approx(
            26.7
        )
        for curve in run["report"]["advantage_and_headroom"]:
            assert curve["equal_budget"]["status"] == "OK"
            assert curve["equal_budget"]["evidence_scope"] == "REPRESENTATIVE"
            assert curve["equal_budget"]["independent_clusters"] == 1


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda d: d["reference"].update(formulation="motor-A_z"), "AXISYMMETRIC"),
        (
            lambda d: d["reference"].update(native_acceptance_receipt="HUMAN_INPUT"),
            "OWNER_INPUT",
        ),
        (lambda d: d["cheap"].update(method="linear-no-fringing"), "STRONGEST"),
        (lambda d: d["cheap"].update(calibration_role="HELDOUT"), "STRONGEST"),
        (
            lambda d: d["cheap"]["predictions"].update(scope="PUBLIC_DEVELOPMENT"),
            "FIXTURE",
        ),
        (lambda d: d["costs"].update(new_field_attempts=2953), "CAP_EXCEEDED"),
        (lambda d: d["costs"]["reference"][0].update(field_states=26), "27_STATE"),
        (lambda d: d["costs"]["reference"].pop(), "INCOMPLETE"),
        (lambda d: d["policy"]["question_law"].update(w="HUMAN_INPUT"), "P_Q_W"),
    ],
)
def test_missing_material_stops_before_fitting(mutate, reason):
    docs, pins = fixture.documents()
    mutate(docs)
    with pytest.raises(pilot.PilotHold, match=reason):
        pilot.execute(
            docs,
            pins,
            fixture=True,
            trainer=lambda *a, **k: pytest.fail("must refuse before fit"),
        )


def test_fixture_train_cannot_enter_public_worker():
    docs, pins = fixture.documents()
    with pytest.raises(pilot.PilotHold, match="PROMOTION"):
        pilot.execute(docs, pins, trainer=lambda *a, **k: pytest.fail("must refuse"))


def test_tiny_real_trainer_uses_full_curve_targets_when_jax_available():
    pytest.importorskip(
        "jax", reason="canonical JAX environment exercises actual tiny network"
    )
    docs, pins = fixture.documents()
    configured = kit.kit_from_bytes(ca.canonical(docs["domain"]))
    train = ca.load_train(configured, docs["train"], pins["train"])
    view = copy.deepcopy(docs["export"])
    for e in view["questions"]:
        for r in e["reference"]:
            r["values"] = {key: 0.0 for key in kit.OBSERVABLES}
    predicted, receipt = ca.run(
        configured,
        view,
        train,
        scope="SYNTHETIC_FIXTURE",
        settings={"steps": 2, "width": 4, "depth": 1},
    )
    assert len(predicted["rows"]) == 9
    assert all(len(r["values"]) == 136 for r in predicted["rows"])
    assert receipt["train"]["fixture"] is True


def test_geometry_holdout_excludes_same_geometry_in_other_stratum():
    docs, pins = fixture.documents()
    record = json.loads(docs["train"].splitlines()[0])
    record["inputs"].update(docs["export"]["questions"][0]["task"]["actions"]["S0"])
    docs["train"] += ca.canonical(record) + b"\n"
    pins["train"] = ca.sha256(docs["train"])
    with pytest.raises(pilot.PilotHold, match="WHOLE_GEOMETRY"):
        pilot.execute(docs, pins, fixture=True, trainer=fixture.trainer)


def test_data_plan_keeps_84_curves_and_all_virtual_work_attempts():
    plan = pilot.acquisition_plan()
    assert plan["status"] == "PROPOSED_HOLD"
    assert len(plan["designs"]) == 28
    primary = [r for r in plan["tuples"] if r["rung"] == "primary"]
    assert len(primary) == 84
    assert len(plan["tuples"]) + plan["failed_curve_allowance"] == 104
    assert sum(r["field_states"] for r in plan["tuples"]) + 4 * 27 == 2952
    train = {
        ca.canonical(d["coordinates"]) for d in plan["designs"] if d["role"] == "TRAIN"
    }
    held = {
        ca.canonical(d["coordinates"])
        for d in plan["designs"]
        if d["role"] == "PUBLIC_HELDOUT"
    }
    assert len(train) == 16 and len(held) == 12 and not train.intersection(held)
    assert set(plan["holds"].values()) == {"HUMAN_INPUT"}
    assert plan["automatic_redraws"] is False


def write_bundle(tmp_path):
    docs, _pins = fixture.documents()
    sources = {}
    for role, doc in docs.items():
        path = tmp_path / (role + (".jsonl" if role == "train" else ".json"))
        data = doc if isinstance(doc, bytes) else ca.canonical(doc)
        path.write_bytes(data)
        sources[role] = {"path": path.name, "sha256": ca.sha256(data)}
    bundle = tmp_path / "bundle.json"
    bundle.write_bytes(
        ca.canonical(
            {"schema": pilot.SCHEMA, "scope": "PUBLIC_DEVELOPMENT", "sources": sources}
        )
    )
    return bundle


def test_input_pins_and_paths_are_checked(tmp_path):
    bundle = write_bundle(tmp_path)
    pilot.load(bundle)
    (tmp_path / "train.jsonl").write_bytes(b"changed")
    with pytest.raises(pilot.PilotHold, match="PIN_OR_SIZE"):
        pilot.load(bundle)


@pytest.mark.skipif(
    os.name != "posix", reason="Linux fcntl launcher validator; canonical CI covers"
)
def test_existing_launcher_controls_allocation_to_termination_cash(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(pod_jobs, "run", lambda *a, **k: pytest.fail("no provider"))
    spec = pilot.pod_spec(write_bundle(tmp_path), "a" * 40)
    validated = pod_jobs.load_spec(spec)
    assert validated.economics()["worst_case_usd"] <= 36.40
    assert spec["minutes"] + pod_jobs.EXPORT_MINUTES <= 1800
    assert spec["image"] == "study" and spec["compute"]["kind"] == "cpu"


def test_cli_standin_and_plan_are_not_real_execution(tmp_path):
    out = tmp_path / "standin.json"
    assert pilot.main(["dry-run", "--out", str(out)]) == 0
    assert json.loads(out.read_bytes())["scope"] == "SYNTHETIC_FIXTURE"
    assert pilot.main(["data-plan", "--out", str(out)]) == 0
    assert json.loads(out.read_bytes())["runtime_id_activated"] is False
