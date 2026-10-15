"""Artificial producer-shaped fixtures; no physics, fits or hidden material."""

from __future__ import annotations

import copy
import hashlib
import json
import random

import pytest

from carbon.design_search import tasks
from scripts.dev.score_lab import candidates, owner_v3_n1 as n1
from scripts.dev.score_lab import owner_v3_panel_export as producer
from tests.cpu.test_score_lab_owner_v3_panel_export import fixture as producer_fixture


def row(name="leg", *, role="LEG", mutate=None, omit=None):
    args = producer_fixture(mutate=mutate, omit=omit)
    task = args["registered"]
    task["task_id"] = "toy-n1-" + name
    task["task_digest"] = tasks.digest(
        {k: v for k, v in task.items() if k != "task_digest"}
    )
    args["manifest"]["task_digest"] = task["task_digest"]
    args["expected_manifest_digest"] = tasks.digest(args["manifest"])
    evidence = producer.build(**args)
    draw = {
        "population": "P",
        "role": role,
        "outer_weight": 1,
        "bank_cluster": args["expected_plan_digest"],
        "task": task,
    }
    return {"draw": draw, "evidence": evidence}


@pytest.fixture(scope="module")
def leg():
    return row()


def bindings(rows):
    return {
        r["draw"]["task"]["task_digest"]: {
            k: r["evidence"].receipt[k]
            for k in ("plan_digest", "source_pins_digest", "manifest_digest")
        }
        for r in rows
    }


def predictions(rows, *, error=0):
    result = {}
    for r in rows:
        panels = copy.deepcopy(r["evidence"].references)
        for panel in panels:
            for key, values in panel["values"].items():
                # Missing toy references do not prevent a model from supplying
                # its original complete input-only prediction panel.
                if values is None:
                    values = {
                        "minutes": 91.0,
                        "charging_t_max_c": 35.0,
                        "plating_min_v": 0.01,
                        "v_max_v": 4.1,
                        "q30_over_q1": 1.0,
                    }
                    panel["values"][key] = values
                values["minutes"] += error
        result[r["draw"]["task"]["task_digest"]] = panels
    return result


def score(rows, prediction=None, **kwargs):
    return n1.score_leg(
        rows,
        predictions(rows) if prediction is None else prediction,
        producer_bindings=bindings(rows),
        expected_registration_digest=n1.REGISTRATION_SHA256,
        scope="SYNTHETIC_FIXTURE",
        **kwargs,
    )


def commitment(r, panels):
    task = r["draw"]["task"]
    table = {p["index_value"]: p["values"] for p in panels}
    action_ids = {
        i["index_value"]: {tasks.digest(a): c for c, a in i["task"]["actions"].items()}
        for i in task["indices"]
    }
    return tasks.run_indexed_optimizer(
        task,
        lambda b, a, c: table[b][(action_ids[b][tasks.digest(a)], c["id"])],
        model_id="toy-only",
    )["commitment"]


def value(r, prediction):
    qid = r["draw"]["task"]["task_digest"]
    return n1.judge_values(
        [r],
        {qid: commitment(r, prediction[qid])},
        producer_bindings=bindings([r]),
        expected_registration_digest=n1.REGISTRATION_SHA256,
        scope="SYNTHETIC_FIXTURE",
    )


def test_exact_approved_registration_and_scalar_units():
    reg = n1.registration(expected_sha256=n1.REGISTRATION_SHA256)
    assert (
        reg["proposal_sha256"]
        == "9080e7601070ca7e54082275654d410ecb91fbbcf4602017d1f55e51989038b4"
    )
    assert reg["scales"]["v_max_v"]["floor"] == 0.05
    assert reg["scales"]["plating_min_v"]["unit"] == "V"
    assert reg["scales"]["minutes"]["population_sd"] == 16.252337997898938
    assert reg["stage_c_or_d_adoption"] is False
    assert reg["old_inforce_gates"] == "UNMEASURED"


def test_complete_native_call_and_grouped_form_with_unequal_weights(leg):
    result = score([leg], predictions([leg], error=2))
    assert result["status"] == "MEASURED_DEVELOPMENT_DIAGNOSTIC"
    assert result["included_questions"] == 1
    assert result["relevance_weight_range"][0] < result["relevance_weight_range"][1]
    assert (
        result["arithmetic"]["absolute_error_residual"]
        <= result["arithmetic"]["operation_count_bound"]
    )
    assert result["scores"][n1.N1] == 1 / (1 + result["native_weighted_error"])
    assert len(result["case_contributions"][n1.N1]) == 1  # NOT sixty independent cases
    assert leg["draw"]["task"]["indices"][0]["buyer_weight"] == 0
    assert result["official_eligible"] is False
    assert result["job"] == "battery-v3-job-dev-v1"
    assert result["prediction_digest"] != score([leg])["prediction_digest"]


@pytest.mark.parametrize("seed", range(12))
def test_grouping_preserves_full_source_randomized_toy_inputs(seed):
    rng = random.Random(seed)
    reg = n1.registration(expected_sha256=n1.REGISTRATION_SHA256)
    native, namespace = n1._source(reg)
    refs, preds, parent = {}, {}, {}
    for q in range(3):
        for band in range(5):
            bid = f"q{q}:b{band}"
            parent[bid] = f"q{q}"
            refs[bid], preds[bid] = {}, {}
            for a in range(12):
                margins = {"x": rng.uniform(-2, 3), "y": rng.uniform(-1, 2)}
                ref = {
                    "objective": rng.uniform(5, 60),
                    "margins": margins,
                    "status": (
                        "FEASIBLE"
                        if all(v >= 0 for v in margins.values())
                        else "INFEASIBLE"
                    ),
                }
                refs[bid][str(a)] = ref
                preds[bid][str(a)] = {
                    "objective": ref["objective"] + rng.uniform(-3, 3),
                    "margins": {
                        k: v + rng.uniform(-0.5, 0.5) for k, v in margins.items()
                    },
                }
    md = {
        "sense": "min",
        "scale": {"objective": 4.0, "x": 0.5, "y": 2.0},
        "near_band": 0.1,
        "knobs": {
            "optimum_band": 0.1,
            "physics": {"mode": "OFF"},
            "neighbourhood_weight": 0,
        },
        "neighbours": [],
    }
    result = n1._reduce(preds, refs, md, parent, native, namespace)
    expected = native(preds, refs, md)
    assert result["scores"][n1.N1] == expected["score"]
    assert sum(result["case_contributions"][n1.N1].values()) / 3 == pytest.approx(
        expected["detail"]["weighted_error"], rel=2e-14
    )
    error = (
        sum(
            namespace["_case_error"](preds[b][a], r, md["scale"])
            for b, acts in refs.items()
            for a, r in acts.items()
        )
        / 180
    )
    assert result["scores"][n1.CONTROL] == 1 / (1 + error)


def test_missing_prediction_cannot_improve_denominator(leg):
    pred = predictions([leg])
    qid = leg["draw"]["task"]["task_digest"]
    pred[qid][0]["values"].pop(next(iter(pred[qid][0]["values"])))
    result = score([leg], pred)
    assert result["status"] == "CANDIDATE_UNAVAILABLE"
    assert result["scores"] == {n1.N1: None, n1.CONTROL: None}
    assert result["reason"] == "PREDICTION_ACTION_COVERAGE"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, 10**400])
def test_nonfinite_or_untyped_prediction_withholds_whole_member(leg, bad):
    pred = predictions([leg])
    first = next(iter(next(iter(pred.values()))[0]["values"].values()))
    first["plating_min_v"] = bad
    assert score([leg], pred)["status"] == "CANDIDATE_UNAVAILABLE"


def test_finite_raw_values_with_overflow_are_not_measured(leg):
    pred = predictions([leg])
    next(iter(next(iter(pred.values()))[0]["values"].values()))["q30_over_q1"] = 1e308
    result = score([leg], pred)
    assert result["status"] == "NUMERICAL_UNAVAILABLE"
    assert all(v is None for v in result["scores"].values())


def test_leg_and_value_never_pool_or_read_value_labels(leg):
    value_row = {"draw": {**leg["draw"], "role": "VALUE"}, "evidence": object()}
    with pytest.raises(tasks.TaskError, match="one population and one role"):
        score([value_row], {})


def test_p_and_q_never_pool(leg):
    q = {"draw": {**leg["draw"], "population": "Q"}, "evidence": object()}
    with pytest.raises(tasks.TaskError, match="one population and one role"):
        n1.score_leg(
            [leg, q],
            {},
            producer_bindings={},
            expected_registration_digest=n1.REGISTRATION_SHA256,
            scope="SYNTHETIC_FIXTURE",
        )


def test_fixture_evidence_cannot_be_relabeled_public(leg):
    with pytest.raises(tasks.TaskError, match="bindings differ"):
        n1.score_leg(
            [leg],
            predictions([leg]),
            producer_bindings=bindings([leg]),
            expected_registration_digest=n1.REGISTRATION_SHA256,
        )


def test_raw_producer_flag_or_wrong_independent_binding_refused(leg):
    raw = {"draw": leg["draw"], "evidence": {"calibration_pass": True}}
    with pytest.raises(tasks.TaskError, match="constructed producer evidence"):
        n1.score_leg(
            [raw],
            {},
            producer_bindings=bindings([leg]),
            expected_registration_digest=n1.REGISTRATION_SHA256,
            scope="SYNTHETIC_FIXTURE",
        )
    wrong = bindings([leg])
    next(iter(wrong.values()))["manifest_digest"] = "sha256:" + "0" * 64
    with pytest.raises(tasks.TaskError, match="prebound producer"):
        n1.score_leg(
            [leg],
            predictions([leg]),
            producer_bindings=wrong,
            expected_registration_digest=n1.REGISTRATION_SHA256,
            scope="SYNTHETIC_FIXTURE",
        )


@pytest.mark.parametrize(
    "mutation", ["near_band", "scales", "physics_mode", "native_source_sha256"]
)
def test_registration_changes_require_new_binding(tmp_path, monkeypatch, mutation):
    raw = json.loads((n1.DIRECTORY / "registration.json").read_bytes())
    raw[mutation] = "changed"
    (tmp_path / "registration.json").write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(n1, "DIRECTORY", tmp_path)
    with pytest.raises(tasks.TaskError, match="registration digest"):
        n1.registration(expected_sha256=n1.REGISTRATION_SHA256)


def test_native_source_drift_cannot_enter_adapter(tmp_path, monkeypatch, leg):
    path = tmp_path / "candidate.py.txt"
    path.write_bytes(candidates.REGISTERED_SOURCE.read_bytes() + b"\n# changed\n")
    monkeypatch.setattr(candidates, "REGISTERED_SOURCE", path)
    with pytest.raises(ValueError, match="registered_candidates_digest"):
        score([leg])


def test_whole_question_common_mask_and_offered_prediction_coverage(leg):
    unresolved = row(
        "unresolved",
        omit=lambda j: ":eval:" in j["case_id"]
        and j["t_amb_c"] == 5
        and j["mesh"] == 40,
    )
    offered = [leg, unresolved]
    a = score(offered, predictions(offered, error=1))
    b = score(offered, predictions(offered, error=3))
    assert a["reference_masks"] == b["reference_masks"]
    assert (a["included_questions"], a["excluded_questions"]) == (1, 1)
    assert len(a["case_contributions"][n1.N1]) == 1
    alone = score([unresolved])
    assert (
        alone["status"] == "REFERENCE_UNRESOLVED"
        and alone["candidate_penalty"] is False
    )
    pred = predictions(offered)
    pred.pop(unresolved["draw"]["task"]["task_digest"])
    assert score(offered, pred)["status"] == "CANDIDATE_UNAVAILABLE"


def test_zero_voltage_margin_reports_native_degeneracy_without_dropping_limit():
    def mutate(record, _job):
        record["whole_programme"]["v_max_v"] = 4.2
        for cycle in record["per_cycle"]:
            for phase in cycle["phases"].values():
                phase["v_max_v"] = 4.2

    r = row("zero-voltage", mutate=mutate)
    result = score([r], predictions([r], error=3))
    assert result["all_relevance_weights_one"] is True
    assert result["scores"][n1.N1] == result["scores"][n1.CONTROL]
    pred = predictions([r], error=3)
    for panel in next(iter(pred.values())):
        for point in panel["values"].values():
            point["v_max_v"] += 0.01
    changed = score([r], pred)
    assert changed["scores"][n1.N1] < result["scores"][n1.N1]


def test_none_feasible_remains_in_accuracy_bank():
    def mutate(record, _job):
        for cycle in record["per_cycle"]:
            for phase in cycle["phases"].values():
                phase["plating_min_v"] = -0.01

    r = row("none", mutate=mutate)
    result = score([r])
    assert result["status"] == "MEASURED_DEVELOPMENT_DIAGNOSTIC"
    assert result["included_questions"] == 1
    assert (
        next(iter(result["reference_masks"].values()))["reference_state"]
        == "NONE_FEASIBLE"
    )


def test_leg_selection_never_replaced_by_value_eligibility(leg):
    def unsafe_reference(record, job):
        if ":eval:" in job["case_id"] and job["t_amb_c"] == 5 and job["c1"] == 1.75:
            for cycle in record["per_cycle"]:
                for phase in cycle["phases"].values():
                    phase["plating_min_v"] = -0.01

    vr = row("value", role="VALUE", mutate=unsafe_reference)
    legs, values = {}, {}
    for i, member in enumerate(("a", "b", "c", "d")):
        legs[member] = score([leg], predictions([leg], error=i))
        pred = predictions([vr])
        if member == "a":
            for panel in next(iter(pred.values())):
                for point in panel["values"].values():
                    if point["plating_min_v"] < 0:
                        point["plating_min_v"], point["minutes"] = 0.01, 1
        values[member] = value(vr, pred)
    result = n1.alignment(
        legs, values, recipe_of={m: m for m in legs}, gamers=[], bootstrap=20, seed=7
    )
    assert result["rules"][n1.N1]["selection"]["selected"] == ["a", "b", "c"]
    assert result["rules"][n1.N1]["top3_mean_regret_min"] is None
    assert result["conditional_tau_members"] == ["b", "c", "d"]
    assert result["conditional_tau_exclusion_reasons"]["a"]
    assert result["rules"][n1.N1]["adversarial_screen"] == {
        "status": "UNMEASURED",
        "registered_gamer_members": [],
        "no_gamer_in_top_half": None,
    }
    assert result["all_member_outcome_summaries"]["a"]["infeasible_pick_count"] == 1
    assert result["stage_c_or_d_adoption"] is False


def test_registration_copies_have_exact_authorized_digests():
    reg = n1.registration(expected_sha256=n1.REGISTRATION_SHA256)
    assert reg["approval_original_receipt_sha256"] == (
        "91b83fe90c726de265d5ff58cc295d1ada0b339ae6383b9b42ccda2ad1c18623"
    )
    assert b"\r\n" not in (n1.DIRECTORY / "OWNER_APPROVAL.json").read_bytes()
    for file, key in (
        ("APPROVED_PROPOSAL.md", "proposal_sha256"),
        ("OWNER_APPROVAL.json", "approval_sha256"),
        ("TRAIN_SCALE_RECEIPT.json", "train_scale_receipt_sha256"),
    ):
        assert (
            hashlib.sha256((n1.DIRECTORY / file).read_bytes()).hexdigest() == reg[key]
        )
