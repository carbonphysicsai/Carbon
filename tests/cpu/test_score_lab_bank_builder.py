"""OPT-16 toy producer plan; no Challenge data, solver or sealed material."""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts.dev.score_lab import bank, bank_builder
from scripts.dev.score_lab.__main__ import main
from scripts.dev.score_lab.core import LabRefused


def _sha(value):
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _fixture():
    definition = json.dumps({"id": "VALUE-METRIC-V2", "revision": 2}).encode()
    policy = {
        "schema": bank_builder.COST,
        "reference_policy_digest": _sha("reference-policy"),
        "coarse_cpu_s": 10,
        "coarse_wall_s": 5,
        "refinement": {
            "margin_quantity": "toy_margin",
            "margin_unit": "toy_unit",
            "margin_window": [-0.002, 0.003],
            "fine_rung": "toy-fine",
            "trigger_rung": "toy-trigger",
            "fine_cpu_s": 100,
            "fine_wall_s": 50,
            "trigger_fraction": 0.1,
            "trigger_cpu_s": 20,
            "trigger_wall_s": 10,
        },
    }
    law = _sha("law")
    pop = _sha("P")
    weights = _sha("w")
    draws = {
        "schema": bank_builder.DRAWS,
        "question_law_digest": law,
        "population_digest": pop,
        "weights_digest": weights,
        "draw_role": "P",
        "drawer_seed_commitment": _sha("drawer"),
        "contexts": [
            {
                "question_id": f"q-{block}-{task}",
                "block_id": f"block-{block}",
                "task": task,
                "context": {"toy_load": block},
                "physical_context": {"toy_load": block},
                "conditions": [
                    {"id": "cold", "value": {"toy_ambient": 1}},
                    {"id": "warm", "value": {"toy_ambient": 2}},
                ],
                "fallback_action": "b",
                "weight": 1.0,
            }
            for block in range(4)
            for task in ("target", "neighbour")
        ],
    }
    registration = {
        "schema": bank_builder.REGISTRATION,
        "definition_digest": "sha256:" + hashlib.sha256(definition).hexdigest(),
        "question_law_digest": law,
        "population_digest": pop,
        "proposal_digest": _sha("Q"),
        "weights_digest": weights,
        "image_digest": _sha("image"),
        "overlay_lock_digest": _sha("overlay"),
        "mms_acceptance_digest": _sha("mms"),
        "validity_envelope_digest": _sha("validity"),
        "reference_policy_digest": _sha("reference-policy"),
        "cost_policy_digest": bank_builder.digest(policy),
        "block_independence_digest": _sha("independent_blocks"),
        "draws_digest": bank_builder.digest(draws),
        "split_seed_commitment": _sha("split"),
        "objective_aggregation": "worst_case",
        "objective_sense": "minimize",
        "reference_status_rule": {
            "id": "toy-reference",
            "margin_quantity": "toy_margin",
            "margin_unit": "toy_unit",
            "coarse_rung": "toy-coarse",
            "feasible_direction": "positive",
            "fine_rung": "toy-fine",
            "coarse_window": [-0.002, 0.003],
            "bands": {"toy-coarse": [-0.002, 0.003], "toy-fine": [0.0, 0.002]},
        },
        "train_separation": {"status": "PASS", "evidence_digest": _sha("TRAIN")},
        "cheap_arm_registration": {
            "status": "FROZEN_BEFORE_DRAW",
            "evidence_digest": _sha("cheap"),
        },
        "neighbour_declarations": [{"id": "neighbour", "kind": "toy_shift"}],
        "actions": [
            {"id": "a", "value": {"toy_design": 1}},
            {"id": "b", "value": {"toy_design": 2}},
        ],
        "alpha": 0.5,
    }
    return definition, registration, draws, policy


def _solved(planned):
    records = []
    jobs = {
        (j["question_id"], j["action_id"], j["condition_id"]): j["job_id"]
        for j in planned["requirements"]
    }
    for q in planned["questions"]:
        records.append(
            {
                **{
                    k: q[k]
                    for k in (
                        "question_id",
                        "block_id",
                        "task",
                        "half",
                        "weight",
                        "fallback_action",
                    )
                },
                "class": "SCORED",
                "actions": {
                    action: [
                        {
                            "condition_id": c["id"],
                            "job_id": jobs[q["question_id"], action, c["id"]],
                            "status": "FEASIBLE",
                            "objective": 0.5 if action == "a" else 1.0,
                            "record_sha256": _sha(
                                jobs[q["question_id"], action, c["id"]]
                            ),
                            "image_digest": planned["manifest"]["image_digest"],
                            "overlay_lock_digest": planned["manifest"][
                                "overlay_lock_digest"
                            ],
                            "margins": {"toy_margin": 0.1},
                            "coarse_margin": 0.1,
                            "reference_rule_id": "toy-reference",
                            "rung": "toy-coarse",
                            "band": [-0.002, 0.003],
                            "band_unit": "toy_unit",
                        }
                        for c in q["conditions"]
                    ]
                    for action in planned["action_ids"]
                },
            }
        )
    return records


def _check(planned, records, *, definition_bytes, **kwargs):
    _definition, registration, draws, _policy = _fixture()
    return bank_builder.check_solved(
        planned,
        records,
        registration=registration,
        draws=draws,
        definition_bytes=definition_bytes,
        split_seed="split",
        **kwargs,
    )


def _cost(planned, policy, coarse=None):
    definition, registration, draws, _policy = _fixture()
    return bank_builder.reference_cost(
        planned,
        policy,
        coarse,
        registration=registration,
        draws=draws,
        definition_bytes=definition,
        split_seed="split",
    )


def _winnability_inputs(records):
    predictions = {
        r["question_id"]: {
            "a": {"feasible": True, "objective": 0.5},
            "b": {"feasible": True, "objective": 1.0},
        }
        for r in records
        if r["half"] == "development"
    }
    cheap = {
        qid: {
            "a": {"feasible": False, "objective": 0.5},
            "b": {"feasible": True, "objective": 1.0},
        }
        for qid in predictions
    }
    return {
        "cheap": cheap,
        "reference_model": predictions,
        "cap": 1,
        "kappa": 0.1,
        "unit": 1.0,
        "ceiling_threshold": 0.5,
        "learnability": {"train_sizes": [10, 20], "accuracies": [0.5, 0.6]},
        "replicates": 30,
    }


def test_plan_enumerates_every_action_condition_and_splits_whole_blocks():
    definition, registration, draws, _policy = _fixture()
    planned = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )
    replay = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )
    assert replay == planned
    assert planned["scope"] == "PRODUCER_ONLY"
    assert len(planned["questions"]) == 8
    assert len(planned["requirements"]) == 32
    assert (
        len(planned["jobs"]) == 16
    )  # target and requirement-only neighbour reuse solves
    assert len({j["job_id"] for j in planned["jobs"]}) == 16
    assert {j["role"] for j in planned["jobs"]} == {"HELDOUT_REFERENCE"}
    by_block = {}
    for q in planned["questions"]:
        by_block.setdefault(q["block_id"], set()).add(q["half"])
    assert all(len(halves) == 1 for halves in by_block.values())
    assert planned["manifest"]["confirmation_blocks"] == 2
    assert planned["manifest"]["minimum_confirmation_blocks"] == 1
    assert (
        planned["manifest"]["reference_policy_digest"]
        == registration["reference_policy_digest"]
    )
    assert (
        planned["manifest"]["block_independence_digest"]
        == registration["block_independence_digest"]
    )
    assert planned["manifest"]["split_seed_commitment"] == _sha("split")
    assert "split" not in planned["manifest"].values()


def test_plan_refuses_unregistered_draws_and_insufficient_blocks():
    definition, registration, draws, _policy = _fixture()
    with pytest.raises(LabRefused, match="bank_split_seed_commitment"):
        bank_builder.plan(
            registration, draws, definition_bytes=definition, split_seed="different"
        )
    with pytest.raises(LabRefused, match="bank_draws_digest"):
        bank_builder.plan(
            registration,
            {**draws, "draw_role": "Q"},
            definition_bytes=definition,
            split_seed="split",
        )
    changed = {**registration, "alpha": 0.01}
    with pytest.raises(
        LabRefused, match="bank_confirmation_blocks_below_alpha_minimum"
    ):
        bank_builder.plan(
            changed, draws, definition_bytes=definition, split_seed="split"
        )
    q_draws = {**draws, "draw_role": "Q"}
    changed = {**registration, "draws_digest": bank_builder.digest(q_draws)}
    with pytest.raises(LabRefused, match="bank_draw_population_mismatch"):
        bank_builder.plan(
            changed, q_draws, definition_bytes=definition, split_seed="split"
        )
    with pytest.raises(LabRefused, match="bank_objective_sense_unsupported"):
        bank_builder.plan(
            {**registration, "objective_sense": "maximize"},
            draws,
            definition_bytes=definition,
            split_seed="split",
        )
    overlap = json.loads(json.dumps(draws))
    for row in overlap["contexts"]:
        if row["block_id"] == "block-1":
            row["physical_context"] = {"toy_load": 0}
    changed = {**registration, "draws_digest": bank_builder.digest(overlap)}
    with pytest.raises(LabRefused, match="bank_block_reference_case_overlap"):
        bank_builder.plan(
            changed, overlap, definition_bytes=definition, split_seed="split"
        )


def test_solved_checker_keeps_confirmation_values_out_of_report():
    definition, registration, draws, _policy = _fixture()
    planned = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )
    records = _solved(planned)
    report = _check(planned, records, definition_bytes=definition)
    assert report["status"] == "INSUFFICIENT_EVIDENCE"
    assert report["structural_ready"] is True
    assert report["class_counts"]["confirmation"] == {"SCORED": 4}
    assert report["scored_share"] == {"development": 1.0, "confirmation": 1.0}
    assert report["development_winnability"]["status"] == "INSUFFICIENT_EVIDENCE"
    text = json.dumps(report)
    assert "toy_ambient" not in text and "q-0-" not in text
    with pytest.raises(LabRefused, match="sealed_or_empty_bank_records"):
        bank.check(
            planned["manifest"],
            [r for r in records if r["half"] == "confirmation"],
            definition_bytes=definition,
        )
    broken = [dict(r) for r in records]
    broken[0] = {
        **broken[0],
        "half": "confirmation" if broken[0]["half"] == "development" else "development",
    }
    with pytest.raises(LabRefused, match="bank_solved_identity_mismatch"):
        _check(planned, broken, definition_bytes=definition)
    broken = [dict(r) for r in records]
    broken[0] = {**broken[0], "actions": {"a": broken[0]["actions"]["a"]}}
    with pytest.raises(LabRefused, match="bank_solved_action_coverage"):
        _check(planned, broken, definition_bytes=definition)
    broken = _solved(planned)
    first = broken[0]["actions"]["a"][0]
    first["job_id"] = _sha("wrong_job")
    with pytest.raises(LabRefused, match="bank_solved_reference_record"):
        _check(planned, broken, definition_bytes=definition)


def test_registered_rung_and_band_keep_coarse_in_window_decisions_unresolved():
    definition, registration, draws, _policy = _fixture()
    planned = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )
    records = _solved(planned)
    cell = records[0]["actions"]["a"][0]
    cell["coarse_margin"] = 0.0
    with pytest.raises(LabRefused, match="bank_reference_coarse_margin"):
        _check(planned, records, definition_bytes=definition)
    cell["margins"]["toy_margin"] = 0.0
    with pytest.raises(LabRefused, match="bank_in_window_unresolved_required"):
        _check(planned, records, definition_bytes=definition)
    cell["status"] = "UNRESOLVED"
    records[0]["class"] = "INCOMPLETE"
    result = _check(planned, records, definition_bytes=definition)
    assert (
        sum(rows.get("INCOMPLETE", 0) for rows in result["class_counts"].values()) == 1
    )
    cell["band"] = [0.0, 0.002]
    with pytest.raises(LabRefused, match="bank_reference_rung_band"):
        _check(planned, records, definition_bytes=definition)
    fresh = _solved(planned)
    fine = fresh[0]["actions"]["a"][0]
    fine.update(
        rung="toy-fine",
        band=[0.0, 0.002],
        coarse_margin=0.0,
        margins={"toy_margin": 0.001},
    )
    with pytest.raises(LabRefused, match="bank_reference_band_status"):
        _check(planned, fresh, definition_bytes=definition)
    broken = _solved(planned)
    match = next(
        r
        for r in broken
        if r["block_id"] == broken[0]["block_id"] and r["task"] != broken[0]["task"]
    )
    match["actions"]["a"][0]["record_sha256"] = _sha("different_solve")
    with pytest.raises(LabRefused, match="bank_reused_solve_digest_mismatch"):
        _check(planned, broken, definition_bytes=definition)
    broken = _solved(planned)
    del broken[0]["actions"]["a"][0]["margins"]
    with pytest.raises(LabRefused, match="bank_solved_reference_record"):
        _check(planned, broken, definition_bytes=definition)
    broken = _solved(planned)
    broken[0]["actions"]["a"][0]["status"] = "FAILED_REFERENCE"
    broken[0]["class"] = "INCOMPLETE"
    with pytest.raises(LabRefused, match="bank_solved_reference_record"):
        _check(planned, broken, definition_bytes=definition)
    broken = _solved(planned)
    broken[0]["actions"]["a"][0]["overlay_lock_digest"] = _sha("wrong_overlay")
    with pytest.raises(LabRefused, match="bank_solved_reference_record"):
        _check(planned, broken, definition_bytes=definition)


def test_every_settled_label_matches_its_registered_positive_feasible_band():
    definition, registration, draws, _policy = _fixture()
    planned = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )

    def records_with(status, margin, *, rung="toy-coarse"):
        rows = _solved(planned)
        for row in rows:
            for cell in row["actions"]["a"]:
                cell.update(
                    status=status,
                    objective=None if status == "INFEASIBLE" else 2.0,
                    margins={"toy_margin": margin},
                    coarse_margin=margin if rung == "toy-coarse" else 0.0,
                    rung=rung,
                    band=registration["reference_status_rule"]["bands"][rung],
                )
        return rows

    # A positive-feasible alternative cannot be removed, and an out-of-band
    # unknown cannot be admitted as decision-determined SCORED.
    for status, margin, rung in (
        ("UNRESOLVED", 0.1, "toy-coarse"),
        ("INFEASIBLE", 0.1, "toy-coarse"),
        ("UNRESOLVED", 0.002, "toy-fine"),
        ("INFEASIBLE", 0.001, "toy-fine"),
        ("FEASIBLE", 0.001, "toy-fine"),
    ):
        with pytest.raises(LabRefused, match="bank_reference_band_status"):
            _check(
                planned,
                records_with(status, margin, rung=rung),
                definition_bytes=definition,
            )

    # The declared edges and both rungs partition the toy margin as recorded.
    for status, margin, rung in (
        ("INFEASIBLE", -0.002, "toy-coarse"),
        ("UNRESOLVED", 0.0, "toy-coarse"),
        ("FEASIBLE", 0.003, "toy-coarse"),
        ("INFEASIBLE", 0.0, "toy-fine"),
        ("UNRESOLVED", 0.001, "toy-fine"),
        ("FEASIBLE", 0.002, "toy-fine"),
    ):
        report = _check(
            planned,
            records_with(status, margin, rung=rung),
            definition_bytes=definition,
        )
        assert report["overall_scored_share"] == 1.0


def test_solved_checker_blocks_below_half_scored_share():
    definition, registration, draws, _policy = _fixture()
    planned = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )
    records = _solved(planned)
    development = [r for r in records if r["half"] == "development"]
    confirmation = [r for r in records if r["half"] == "confirmation"]
    for row in [*development[:3], *confirmation[:2]]:
        row["actions"]["a"][0]["status"] = "FAILED_REFERENCE"
        row["actions"]["a"][0]["retry_exhausted"] = True
        row["class"] = "INCOMPLETE"
    result = _check(planned, records, definition_bytes=definition)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["scored_share"]["development"] == 0.25
    assert result["overall_scored_share"] == 0.375
    assert result["structural_ready"] is False
    assert (
        result["development_winnability"]["size_blocker"] == "scored_share_below_half"
    )


def test_exhausted_reference_failure_is_reported_with_sufficient_scored_share():
    definition, registration, draws, _policy = _fixture()
    planned = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )
    records = _solved(planned)
    row = next(r for r in records if r["half"] == "development")
    row["actions"]["a"][0]["status"] = "FAILED_REFERENCE"
    row["actions"]["a"][0]["retry_exhausted"] = True
    row["class"] = "INCOMPLETE"
    result = _check(
        planned,
        records,
        definition_bytes=definition,
        **_winnability_inputs(records),
    )
    assert result["scored_share"] == {"development": 0.75, "confirmation": 1.0}
    assert result["overall_scored_share"] == 0.875
    assert result["class_counts"]["development"]["INCOMPLETE"] == 1
    assert result["structural_ready"] is True
    assert result["status"] == "DEVELOPMENT_WINNABLE_DIAGNOSTIC"


def test_winnability_is_a_development_diagnostic_with_failure_path():
    definition, registration, draws, _policy = _fixture()
    planned = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )
    records = _solved(planned)
    inputs = _winnability_inputs(records)
    passing = _check(planned, records, definition_bytes=definition, **inputs)
    assert passing["status"] == "DEVELOPMENT_WINNABLE_DIAGNOSTIC"
    failing = _check(
        planned,
        records,
        definition_bytes=definition,
        **{**inputs, "cheap": inputs["reference_model"]},
    )
    assert failing["status"] == "DEVELOPMENT_NOT_WINNABLE_DIAGNOSTIC"
    assert (
        failing["development_winnability"]["winnability"]["paired_lower_positive"]
        is False
    )


def test_refinement_cost_uses_this_bank_composition_and_unit():
    definition, registration, draws, policy = _fixture()
    planned = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )
    unknown = _cost(planned, policy)
    assert unknown["refinement_status"] == "UNKNOWN_UNTIL_COARSE"
    assert unknown["total_cpu_hours"] is None
    coarse = {
        j["job_id"]: {
            "record_sha256": _sha(j["job_id"]),
            "image_digest": j["image_digest"],
            "overlay_lock_digest": j["overlay_lock_digest"],
            "reference_policy_digest": j["reference_policy_digest"],
            "margin_quantity": "toy_margin",
            "margin_unit": "toy_unit",
            "margin": 0.0 if i < 4 else 0.1,
        }
        for i, j in enumerate(planned["jobs"])
    }
    result = _cost(planned, policy, coarse)
    assert result["refinement_status"] == "BANK_COMPOSITION_MEASURED"
    assert result["in_window_share"] == 0.25  # own bank, not PDD's 7.3%
    assert result["fine_jobs"] == 4 and result["trigger_jobs"] == 1
    assert result["total_cpu_hours"] == pytest.approx((16 * 10 + 4 * 100 + 20) / 3600)
    wrong = dict(coarse)
    first = planned["jobs"][0]["job_id"]
    wrong[first] = {**wrong[first], "margin_unit": "wrong_unit"}
    with pytest.raises(LabRefused, match="bank_coarse_margin_record"):
        _cost(planned, policy, wrong)
    with pytest.raises(LabRefused, match="bank_coarse_coverage"):
        _cost(planned, policy, {first: coarse[first]})
    mismatched = {**policy, "reference_policy_digest": _sha("wrong-reference")}
    with pytest.raises(LabRefused, match="bank_cost_policy_identity"):
        _cost(planned, mismatched)


def test_consumers_replay_registered_plan_before_using_its_coverage_or_cost():
    definition, registration, draws, policy = _fixture()
    planned = bank_builder.plan(
        registration, draws, definition_bytes=definition, split_seed="split"
    )
    records = _solved(planned)
    reduced = {
        **planned,
        "action_ids": ["b"],
        "requirements": [r for r in planned["requirements"] if r["action_id"] == "b"],
    }
    with pytest.raises(LabRefused, match="bank_plan_content_mismatch"):
        _check(reduced, records, definition_bytes=definition)
    undercounted = {**planned, "jobs": planned["jobs"][:1]}
    with pytest.raises(LabRefused, match="bank_plan_content_mismatch"):
        _cost(undercounted, policy)
    with pytest.raises(LabRefused, match="bank_plan_content_mismatch"):
        _check(undercounted, records, definition_bytes=definition)
    altered_manifest = {
        **planned,
        "manifest": {**planned["manifest"], "confirmation_blocks": 1},
    }
    with pytest.raises(LabRefused, match="bank_plan_content_mismatch"):
        _check(altered_manifest, records, definition_bytes=definition)
    altered_split = {
        **planned,
        "questions": [
            {
                **planned["questions"][0],
                "half": (
                    "development"
                    if planned["questions"][0]["half"] == "confirmation"
                    else "confirmation"
                ),
            },
            *planned["questions"][1:],
        ],
    }
    with pytest.raises(LabRefused, match="bank_plan_content_mismatch"):
        _check(altered_split, records, definition_bytes=definition)
    duplicated = {
        **planned,
        "requirements": [*planned["requirements"], planned["requirements"][0]],
    }
    with pytest.raises(LabRefused, match="bank_plan_content_mismatch"):
        _check(duplicated, records, definition_bytes=definition)


def test_producer_cli_writes_jobs_but_prints_only_aggregates(tmp_path, capsys):
    definition, registration, draws, policy = _fixture()
    files = {
        "registration": registration,
        "draws": draws,
        "policy": policy,
    }
    for name, value in files.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    (tmp_path / "definition.json").write_bytes(definition)
    (tmp_path / "seed.txt").write_text("split\n", encoding="utf-8")
    planned = tmp_path / "plan.json"
    launcher = tmp_path / "launcher-jobs.json"
    assert (
        main(
            [
                "bank-plan",
                "--registration",
                str(tmp_path / "registration.json"),
                "--draws",
                str(tmp_path / "draws.json"),
                "--definition",
                str(tmp_path / "definition.json"),
                "--split-seed-file",
                str(tmp_path / "seed.txt"),
                "--out",
                str(planned),
                "--jobs-out",
                str(launcher),
            ]
        )
        == 0
    )
    assert len(json.loads(planned.read_text(encoding="utf-8"))["jobs"]) == 16
    launcher_rows = json.loads(launcher.read_text(encoding="utf-8"))
    assert launcher_rows["scope"] == "PRODUCER_WORKER_ONLY"
    assert len(launcher_rows["jobs"]) == 16
    assert "half" not in json.dumps(launcher_rows)
    assert "question_id" not in json.dumps(launcher_rows)
    assert "q-0" not in capsys.readouterr().out
    records = tmp_path / "records.jsonl"
    records.write_text(
        "\n".join(
            json.dumps(row)
            for row in _solved(json.loads(planned.read_text(encoding="utf-8")))
        )
        + "\n",
        encoding="utf-8",
    )
    assert (
        main(
            [
                "bank-solved-check",
                "--plan",
                str(planned),
                "--registration",
                str(tmp_path / "registration.json"),
                "--draws",
                str(tmp_path / "draws.json"),
                "--split-seed-file",
                str(tmp_path / "seed.txt"),
                "--records",
                str(records),
                "--definition",
                str(tmp_path / "definition.json"),
            ]
        )
        == 0
    )
    assert "q-0" not in capsys.readouterr().out
    assert (
        main(
            [
                "bank-cost",
                "--plan",
                str(planned),
                "--registration",
                str(tmp_path / "registration.json"),
                "--draws",
                str(tmp_path / "draws.json"),
                "--definition",
                str(tmp_path / "definition.json"),
                "--split-seed-file",
                str(tmp_path / "seed.txt"),
                "--policy",
                str(tmp_path / "policy.json"),
            ]
        )
        == 0
    )
    assert "UNKNOWN_UNTIL_COARSE" in capsys.readouterr().out
    assert "q-0" not in capsys.readouterr().out
