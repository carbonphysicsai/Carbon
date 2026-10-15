"""SYNTHETIC_FIXTURE records only; never a measured solver/adequacy claim."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from carbon.design_search import indexed, tasks
from scripts.dev.score_lab import owner_v3 as owner
from scripts.dev.score_lab import owner_v3_numerics as numerics
from scripts.dev.score_lab import owner_v3_panel_export as producer

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "Business/research/score-lab-campaign-01/acquisition-v1"


def _record(job, plan):
    # Deliberately artificial constant trajectories. The complete shape tests
    # extraction/custody contracts, not physical correctness or reference value.
    phase = {"t_max_c": 35.0, "plating_min_v": 0.01, "v_max_v": 4.1}
    minutes = 40 + int(job["c1"] * 100) + job["h_multiplier"]
    return {
        **job,
        "case_id": "original:" + job["case_id"],
        "schema": "carbon.battery.feasibility02-record.v1",
        "fixture": True,
        "status": "OK",
        "solver_provenance": {
            "schema": "carbon.battery.solver-provenance.v1",
            "solver_image": "ghcr.io/carbonphysicsai/carbon-determinism-study@"
            + plan["image_digest"],
            "overlay_lock": "scripts/dev/exam_design/locks/battery-overlay.lock.json",
            "overlay_lock_sha256": "sha256:" + plan["overlay_sha256"],
            "pybamm": "26.8.0.0",
        },
        "initial_rest": {"t_start_s": 0, "t_end_s": 120, "t_max_c": 30.0},
        "per_cycle": [
            {"cycle": cycle, "phases": {p: dict(phase) for p in producer.PHASES}}
            for cycle in range(1, 31)
        ],
        "capacity_all_ah": [1.0] * 30,
        "q30_over_q1": 1.0,
        "whole_programme": {"v_max_v": 4.1, "t_max_c": 35.0},
        "soc_clock": {"status": "REACHED", "minutes": minutes, "time_s": minutes * 60},
        "core_s": 0.0,
        "wall_s": 0.0,
    }


def fixture(*, mutate=None, omit=None, refinement=False, prune=False):
    plan = json.loads((REGISTRATION / "acquisition.json").read_text(encoding="utf-8"))
    pins = json.loads((REGISTRATION / "source-pins.json").read_text(encoding="utf-8"))
    for path in (producer.EXPORTER, producer.NUMERICS):
        pins["files"][path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    plan_digest, pins_digest = tasks.digest(plan), tasks.digest(pins)
    stages = {
        name: owner.acquisition_inputs(plan, expected_digest=plan_digest, stage=name)[
            "jobs"
        ]
        for name in (
            "calibration-pilot",
            "calibration-rest",
            "evaluation",
            "refinement",
        )
    }
    menu = {
        f"p{p}-h{h}": {"c1": c1, "c2": c2, "switch_v": sv, "cooling": h}
        for p, (c1, c2, sv) in enumerate(plan["fallback_evaluation"]["profiles"])
        for h in plan["cooling"]
    }
    if prune:
        menu.pop(next(iter(menu)))
    grammar = {
        "schema": tasks.GRAMMAR_SCHEMA,
        "version": "synthetic-owner-v3-menu",
        "variables": [
            {"name": "c1", "type": "number", "min": 0.25, "max": 2.0, "step": 0.01},
            {"name": "c2", "type": "number", "min": 0.25, "max": 2.0, "step": 0.01},
            {
                "name": "switch_v",
                "type": "number",
                "min": 4.0,
                "max": 4.15,
                "step": 0.05,
            },
            {"name": "cooling", "type": "integer", "min": 1, "max": 4, "step": 1},
        ],
        "rules": [],
    }
    # Cooling must stay numerical for the real kit. Its integer grammar can
    # represent 3, but the finite registered menu contains only 1, 2 and 4.
    indices = []
    for band, weight in zip(owner.BANDS, [0, 0.1, 0.5, 0.3, 0.1]):
        task = tasks.task(
            f"synthetic-owner-v3-T{band}",
            identity={
                "challenge": "SYNTHETIC_FIXTURE",
                "contract_version": owner.JOB,
                "action_grammar": grammar,
                "optimizer": {"class": "exhaustive", "version": "v1"},
                "query_budget": len(menu),
                "seed": 0,
                "observer_version": producer.OBSERVER,
                "reference_bank": plan_digest,
            },
            conditions=[{"id": f"T{band}", "stratum": f"T{band}"}],
            strata={f"T{band}": {"p": 1, "q": 1, "w": 1}},
            candidates=list(menu),
            actions=menu,
            objective={
                "quantity": "minutes",
                "unit": "min",
                "sense": "min",
                "aggregate": "worst",
            },
            limits=[
                {"quantity": "charging_t_max_c", "unit": "C", "op": "<=", "value": 45},
                {"quantity": "plating_min_v", "unit": "V", "op": ">=", "value": 0},
                {"quantity": "v_max_v", "unit": "V", "op": "<=", "value": 4.2},
                {"quantity": "q30_over_q1", "unit": "1", "op": ">=", "value": 0.99},
            ],
        )
        indices.append({"index_value": band, "buyer_weight": weight, "task": task})
    registered = indexed.indexed_task(
        "synthetic-owner-v3-five-bands",
        index_axis="ambient_c",
        indices=indices,
        query_budget=len(menu) * 5,
        value_equivalence={
            "quantity": "minutes",
            "unit": "min",
            "tolerance": 0.5,
            "rule": indexed.EQUIVALENCE_RULE,
        },
    )
    refinement_jobs = stages["refinement"][:1] if refinement else []
    manifest = {
        "schema": producer.SCHEMA,
        "scope": "SYNTHETIC_FIXTURE",
        "role": "HELDOUT_REFERENCE",
        "task_digest": registered["task_digest"],
        "plan_digest": plan_digest,
        "source_pins_digest": pins_digest,
        "policy_digest": tasks.digest(numerics.POLICY),
        "observer": {
            "id": producer.OBSERVER,
            "clock": plan["clock"],
            "cycles": 30,
            "soc0": 0.1,
            "initial_state": "FRESH",
            "source_files": {p: pins["files"][p] for p in producer.SOURCES},
        },
        "refinement_job_ids": [j["case_id"] for j in refinement_jobs],
        "chunks": [],
    }
    raw_chunks = {}
    for name, role, jobs in (
        (
            "cal",
            "PUBLIC_CALIBRATION",
            stages["calibration-pilot"] + stages["calibration-rest"],
        ),
        ("eval", "PUBLIC_EVALUATION", stages["evaluation"] + refinement_jobs),
    ):
        records, mappings = [], []
        for job in jobs:
            if omit and omit(job):
                continue
            record = _record(job, plan)
            if mutate:
                mutate(record, job)
            records.append(json.dumps(record, sort_keys=True))
            mappings.append(
                {
                    "line": len(records),
                    "job_id": job["case_id"],
                    "case_id": record["case_id"],
                }
            )
        raw_chunks[name] = ("\n".join(records) + "\n").encode()
        manifest["chunks"].append(
            {
                "id": name,
                "role": role,
                "sha256": "sha256:" + hashlib.sha256(raw_chunks[name]).hexdigest(),
                "source_commit": "9" * 40,
                "source_files": dict(manifest["observer"]["source_files"]),
                "rows": mappings,
            }
        )
    return {
        "registered": registered,
        "plan": plan,
        "expected_plan_digest": plan_digest,
        "source_pins": pins,
        "expected_source_pins_digest": pins_digest,
        "manifest": manifest,
        "expected_manifest_digest": tasks.digest(manifest),
        "raw_chunks": raw_chunks,
    }


def _build(args):
    return producer.build(**args)


def _validate(evidence, registered, *, scope="SYNTHETIC_FIXTURE"):
    return producer.validate_for(
        evidence, registered, evidence.references, evidence.enclosures, scope=scope
    )


def test_full_registered_calibration_and_all_actions_are_bound():
    args = fixture()
    before_truth = producer.prediction_view(
        args["registered"], scope="SYNTHETIC_FIXTURE"
    )
    evidence = _build(args)
    receipt = _validate(evidence, args["registered"])
    assert (
        receipt["calibration"]["status"]
        == "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
    )
    assert receipt["calibration"]["expected_case_count"] == 15
    assert len(receipt["per_job"]) == 165
    assert len(receipt["per_evaluation"]) == 60
    assert all(len(p["values"]) == 12 for p in evidence.references)
    assert [p["index_value"] for p in evidence.references] == list(owner.BANDS)
    assert args["registered"]["indices"][0]["buyer_weight"] == 0
    assert evidence.prediction_view == before_truth
    assert receipt["prediction_view_digest"] == before_truth["export_digest"]
    assert receipt["method"]["policy_digest"] == tasks.digest(numerics.POLICY)
    assert receipt["qualification"] is False


def test_prediction_view_is_truth_free_and_not_a_solved_panel():
    args = fixture()
    view = producer.prediction_view(args["registered"], scope="SYNTHETIC_FIXTURE")
    assert view["schema"] == producer.CANDIDATE_VIEW
    assert view["export_digest"] == tasks.digest(
        {k: v for k, v in view.items() if k != "export_digest"}
    )
    for panel in view["questions"][0]["reference"]:
        assert len(panel["panel"]) == 12
        for row in panel["panel"]:
            assert set(row) == {"candidate", "condition", "observables"}
            assert set(row["observables"]) == numerics.QUANTITIES


def test_copies_do_not_mutate_validated_evidence():
    args = fixture()
    evidence = _build(args)
    receipt = evidence.receipt
    receipt["scope"] = "PUBLIC_DEVELOPMENT"
    refs = evidence.references
    next(iter(refs[0]["values"].values()))["minutes"] = -10
    assert evidence.receipt["scope"] == "SYNTHETIC_FIXTURE"
    assert _validate(evidence, args["registered"])["scope"] == "SYNTHETIC_FIXTURE"
    with pytest.raises(AttributeError):
        evidence._seal = "altered"
    with pytest.raises(tasks.TaskError, match="build"):
        producer.ValidatedEvidence()


@pytest.mark.parametrize("raw", [{"calibration_pass": True}, True, None])
def test_raw_dict_or_flag_cannot_be_used_as_evidence(raw):
    args = fixture()
    with pytest.raises(tasks.TaskError, match="validated producer"):
        producer.validate_for(raw, args["registered"], [], [])


def test_fixture_cannot_enter_public_consumer():
    args = fixture()
    evidence = _build(args)
    binding = {
        k: evidence.receipt[k]
        for k in ("plan_digest", "source_pins_digest", "manifest_digest")
    }
    with pytest.raises(tasks.TaskError, match="bindings differ"):
        owner.judge(
            args["registered"],
            {},
            evidence.references,
            evidence.enclosures,
            scope="PUBLIC_DEVELOPMENT",
            producer_evidence=evidence,
            producer_binding=binding,
        )
    with pytest.raises(tasks.TaskError, match="validated producer"):
        owner.judge(
            args["registered"],
            {},
            evidence.references,
            evidence.enclosures,
            scope="PUBLIC_DEVELOPMENT",
            producer_evidence={"calibration_pass": True},
            producer_binding=binding,
        )
    binding["manifest_digest"] = "sha256:" + "0" * 64
    with pytest.raises(tasks.TaskError, match="prebound producer"):
        owner.judge(
            args["registered"],
            {},
            evidence.references,
            evidence.enclosures,
            scope="SYNTHETIC_FIXTURE",
            producer_evidence=evidence,
            producer_binding=binding,
        )


@pytest.mark.parametrize("what", ["manifest", "chunk", "source", "clock"])
def test_registration_and_source_bytes_are_enforced(what):
    args = fixture()
    if what == "manifest":
        args["manifest"]["calibration_pass"] = True
    elif what == "chunk":
        args["raw_chunks"]["cal"] += b"\n"
    elif what == "source":
        args["manifest"]["chunks"][0]["source_files"][producer.SOURCES[0]] = "0" * 64
        args["expected_manifest_digest"] = tasks.digest(args["manifest"])
    else:
        args["manifest"]["observer"]["clock"] = "CV onset"
        args["expected_manifest_digest"] = tasks.digest(args["manifest"])
    with pytest.raises(tasks.TaskError):
        _build(args)


@pytest.mark.parametrize(
    "field,value", [("soc0", 0.2), ("c1", 1.255), ("rung", 0), ("refined", True)]
)
def test_foreign_input_or_mesh_is_rejected(field, value):
    def mutate(record, job):
        if job["rung"] == 1:
            record[field] = value

    with pytest.raises(tasks.TaskError):
        _build(fixture(mutate=mutate))


@pytest.mark.parametrize("field", ["solver_image", "overlay_lock_sha256", "pybamm"])
def test_solver_provenance_drift_is_rejected(field):
    def mutate(record, _job):
        record["solver_provenance"][field] = "foreign"

    with pytest.raises(tasks.TaskError, match="solver image"):
        _build(fixture(mutate=mutate))


def test_missing_rung_uses_only_exact_pinned_source_refined_policy():
    def mutate(record, job):
        if job["rung"] != 3:
            record.pop("rung")

    args = fixture(mutate=mutate)
    evidence = _build(args)
    assert (
        _validate(evidence, args["registered"])["calibration"]["status"]
        == "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
    )
    assert {r["source"]["rung_basis"] for r in evidence.receipt["per_job"]} == {
        "PINNED_SOURCE_REFINED",
        "EXPLICIT_RUNG",
    }


def test_failed_not_reached_and_zero_weight_rows_are_preserved():
    def mutate(record, job):
        if (
            job["case_id"].startswith("scorelab-v3:eval:")
            and job["t_amb_c"] == 5
            and job["h_multiplier"] == 1
        ):
            if job["rung"] == 1:
                record["status"] = "REFERENCE_SOLVER_FAILED"
            else:
                record["soc_clock"] = {"status": "NOT_REACHED", "soc_end": 0.7}

    args = fixture(mutate=mutate)
    evidence = _build(args)
    receipt = _validate(evidence, args["registered"])
    assert len(receipt["per_job"]) == 165
    assert {r["state"] for r in receipt["per_job"]} >= {
        "REFERENCE_SOLVER_FAILED",
        "NOT_REACHED",
        "EXTRACTED",
    }
    assert len(evidence.references[0]["values"]) == 12
    assert evidence.references[0]["values"][("p0-h1", "T5")]["minutes"] is None
    assert evidence.enclosures[0]["candidates"]["p0-h1"] == {}
    mask = owner.reference_mask(
        args["registered"], evidence.references, evidence.enclosures
    )
    assert mask["included"] is False
    assert any(r[0] == 5 for r in mask["reasons"])


def test_all_failed_evaluation_rows_keep_the_entire_offered_bank():
    def mutate(record, job):
        if job["case_id"].startswith("scorelab-v3:eval:"):
            record["status"] = "FAILED_INFRA"

    args = fixture(mutate=mutate)
    evidence = _build(args)
    _validate(evidence, args["registered"])
    assert len(evidence.receipt["per_job"]) == 165
    assert sum(r["state"] == "FAILED_INFRA" for r in evidence.receipt["per_job"]) == 120
    assert sum(len(p["values"]) for p in evidence.references) == 60
    assert all(
        all(v is None for v in values.values())
        for p in evidence.references
        for values in p["values"].values()
    )
    assert (
        owner.reference_mask(
            args["registered"], evidence.references, evidence.enclosures
        )["included"]
        is False
    )


def test_empty_inputs_report_missing_calibration_and_all_offered_jobs():
    args = fixture(omit=lambda _job: True)
    evidence = _build(args)
    assert len(evidence.receipt["per_job"]) == 165
    assert {r["state"] for r in evidence.receipt["per_job"]} == {"MISSING"}
    assert len(evidence.receipt["calibration"]["missing_cases"]) == 15
    with pytest.raises(tasks.TaskError, match="complete compatible"):
        _validate(evidence, args["registered"])


@pytest.mark.parametrize(
    "failure", ["missing", "failed", "short_programme", "calibration_disagreement"]
)
def test_partial_or_inadequate_calibration_never_releases(failure):
    def target(job):
        return (
            job["case_id"].startswith("scorelab-v3:cal:")
            and job["t_amb_c"] == 5
            and job["h_multiplier"] == 1
            and job["rung"] == 3
        )

    def mutate(record, job):
        if target(job):
            if failure == "failed":
                record["status"] = "REFERENCE_SOLVER_FAILED"
            elif failure == "short_programme":
                record["per_cycle"].pop()
            elif failure == "calibration_disagreement":
                record["per_cycle"][0]["phases"]["cc1"]["t_max_c"] = 60

    args = fixture(mutate=mutate, omit=target if failure == "missing" else None)
    evidence = _build(args)
    assert len(evidence.receipt["per_job"]) == 165
    assert (
        evidence.receipt["calibration"]["status"]
        != "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
    )
    with pytest.raises(tasks.TaskError, match="complete compatible"):
        _validate(evidence, args["registered"])


def test_registered_refinement_requires_actual_rung_and_no_fallback():
    args = fixture(
        refinement=True,
        omit=lambda job: job["case_id"].startswith("scorelab-v3:eval:")
        and job["rung"] == 3,
    )
    evidence = _build(args)
    _validate(evidence, args["registered"])
    assert len(evidence.receipt["per_job"]) == 166
    assert evidence.enclosures[0]["candidates"]["p0-h1"] == {}
    assert evidence.references[0]["values"][("p0-h1", "T5")]["minutes"] is None


def test_pruned_menu_cannot_turn_unknown_actions_into_an_easier_bank():
    with pytest.raises(tasks.TaskError, match="every offered action"):
        _build(fixture(prune=True))


@pytest.mark.parametrize("changed", ["references", "enclosures", "limits"])
def test_consumer_cannot_replace_bound_points_intervals_or_requirements(changed):
    args = fixture()
    evidence = _build(args)
    refs, intervals, registered = (
        evidence.references,
        evidence.enclosures,
        copy.deepcopy(args["registered"]),
    )
    if changed == "references":
        refs[0]["values"][("p0-h1", "T5")]["minutes"] += 1
    elif changed == "enclosures":
        intervals[0]["candidates"]["p0-h1"]["minutes"][1] += 1
    else:
        registered["indices"][0]["task"]["limits"][0]["value"] = 46
    with pytest.raises(tasks.TaskError):
        producer.validate_for(
            evidence, registered, refs, intervals, scope="SYNTHETIC_FIXTURE"
        )
