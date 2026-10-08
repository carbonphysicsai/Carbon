"""Toy shapes for every producer panel adapter, without Challenge physics."""

from __future__ import annotations

import json

import pytest

from carbon.design_search import (
    controls,
    diversity,
    indexed,
    power_accumulation,
    producer_panels,
    tasks,
)
from carbon.design_search.__main__ import main


def _subtask(case, support, band):
    registered = tasks.task(
        f"{case}-{band}",
        identity={
            "challenge": "toy-panel-challenge",
            "contract_version": "v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "toy-panel.v1",
                "variables": [
                    {"name": "choice", "type": "integer", "min": 0, "max": 1, "step": 1}
                ],
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": 2,
            "seed": 17,
            "observer_version": "toy-panel-observer.v1",
            "reference_bank": support,
        },
        conditions=[{"id": "condition", "stratum": "only"}],
        strata={"only": {"p": 1, "q": 1, "w": 1}},
        candidates=["safe", "unsafe"],
        actions={"safe": {"choice": 0}, "unsafe": {"choice": 1}},
        objective={
            "quantity": "cost",
            "unit": "toy-unit",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[{"quantity": "margin", "unit": "toy-unit", "op": ">=", "value": 0}],
    )
    reference = [
        {
            "candidate": "safe",
            "condition": "condition",
            "values": {"cost": 1.0, "margin": 1.0},
        },
        {
            "candidate": "unsafe",
            "condition": "condition",
            "values": {"cost": 0.0, "margin": -0.1},
        },
    ]
    return registered, reference


def _export(family, *, indexed_decision=False):
    case = "PRIVATE-T3-CASE"
    support = "PRIVATE-T3-BANK"
    if indexed_decision:
        indices = []
        reference = []
        for band in (5, 15):
            subtask, panel = _subtask(case, support, band)
            indices.append({"index_value": band, "buyer_weight": 0.5, "task": subtask})
            reference.append({"index_value": band, "panel": panel})
        registered = indexed.indexed_task(
            case,
            index_axis="toy-band",
            indices=indices,
            query_budget=4,
            value_equivalence={
                "quantity": "cost",
                "unit": "toy-unit",
                "tolerance": 0,
                "rule": indexed.EQUIVALENCE_RULE,
            },
        )
    else:
        registered, reference = _subtask(case, support, "plain")
    law = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA_V2,
            "population_status": "UNREGISTERED",
            "kind": "grid",
            "draw_model": "iid_with_replacement",
            "batch_size": 1,
            "bins": [{"case": case, "q_mass": 1.0}],
            "mass_l1_error_bound": 0.0,
        }
    )
    return producer_panels.seal_export(
        {
            "schema": producer_panels.EXPORT_SCHEMA,
            "sealed": True,
            "family": family,
            "challenge_id": "toy-panel-challenge",
            "exposure_unit": "per_question_draws",
            "exposure": [{"case": case, "limit": 2, "used": 0}],
            "questions": [
                {
                    "case": case,
                    "support_case": support,
                    "task": registered,
                    "reference": reference,
                    "close_call": False,
                    "refinement_demand": False,
                }
            ],
            "laws": [law],
        }
    )


def _controls():
    return controls.register_controls(
        [
            {
                "schema": controls.CONTROL_SCHEMA,
                "name": "toy-edge",
                "kind": "edge_optimist",
                "severity": {"margin": {"value": 0.2, "unit": "toy-unit"}},
                "limit_quantities": ["margin"],
            }
        ]
    )


def _design_bank_snapshot(family):
    export = _export(family, indexed_decision=family == "battery-v3")
    questions = []
    for row in export["questions"]:
        reference_key = "per_index" if family == "battery-v3" else "panel"
        questions.append(
            {
                "case_id": row["case"],
                "inputs": {
                    "task": row["task"],
                    "task_digest": row["task"]["task_digest"],
                    "draw": {"protected": "PRIVATE-DRAW-PREIMAGE"},
                },
                "reference": {"status": "OK", reference_key: row["reference"]},
                "support_case": row["support_case"],
                "close_call": row["close_call"],
                "refinement_demand": row["refinement_demand"],
            }
        )
    return producer_panels.seal_design_bank_snapshot(
        {
            "schema": producer_panels.DESIGN_BANK_SNAPSHOT_SCHEMA,
            "sealed": True,
            "family": family,
            "challenge_id": export["challenge_id"],
            "exposure_unit": export["exposure_unit"],
            "exposure": [
                {
                    "case_id": row["case"],
                    "limit": row["limit"],
                    "used": row["used"],
                }
                for row in export["exposure"]
            ],
            "cases": questions,
            "laws": export["laws"],
        }
    )


@pytest.mark.parametrize("family", producer_panels.FAMILIES)
def test_all_eight_family_adapters_accept_complete_registered_toy_panels(family):
    export = _export(family, indexed_decision=family == "battery-v3")
    bank, grid, continuous, good = producer_panels.adapt_export(export)
    assert bank["sealed"] is True
    assert ("indexed_power_cases" in bank) == (family == "battery-v3")
    assert grid["kind"] == "grid"
    assert continuous is None
    assert len(good["cases"]) == 1


@pytest.mark.parametrize("family", producer_panels.FAMILIES)
def test_design_bank_record_shape_adapts_without_draw_preimage_leak(family):
    snapshot = _design_bank_snapshot(family)
    bank, grid, _, _ = producer_panels.adapt_export(snapshot)
    assert grid["kind"] == "grid"
    assert bank["case_exposure"][0]["limit"] == 2
    result = producer_panels.panel_power_report(
        snapshot,
        _controls(),
        power_accumulation.register_accumulation(
            exposure_unit="per_question_draws", max_windows=2
        ),
        alpha=0.05,
        power_target=0.8,
        simulation_seed=3,
        replicates=10,
        max_questions=1,
    )
    assert "PRIVATE-DRAW-PREIMAGE" not in json.dumps(result)
    assert "PRIVATE-T3" not in json.dumps(result)


def test_design_bank_non_ok_or_malformed_reference_fails_closed():
    snapshot = _design_bank_snapshot("motor")
    snapshot["cases"][0]["reference"] = {"status": "UNRESOLVED"}
    resealed = producer_panels.seal_design_bank_snapshot(
        {key: value for key, value in snapshot.items() if key != "snapshot_digest"}
    )
    with pytest.raises(tasks.TaskError, match="complete OK"):
        producer_panels.adapt_export(resealed)


def test_battery_v3_requires_indexed_and_f02_can_register_indexed_schedule():
    with pytest.raises(tasks.TaskError, match="indexed"):
        producer_panels.adapt_export(_export("battery-v3"))
    bank, _, _, _ = producer_panels.adapt_export(_export("f02", indexed_decision=True))
    assert "indexed_power_cases" in bank


def test_incomplete_or_tampered_reference_never_enters_power():
    export = _export("motor")
    export["questions"][0]["reference"].pop()
    with pytest.raises(tasks.TaskError, match="sealed registered"):
        producer_panels.adapt_export(export)
    resealed = producer_panels.seal_export(
        {key: value for key, value in export.items() if key != "export_digest"}
    )
    with pytest.raises(tasks.TaskError, match="incomplete"):
        producer_panels.adapt_export(resealed)


@pytest.mark.parametrize("family", ("motor", "battery-v3"))
def test_report_and_cli_emit_aggregates_only(tmp_path, capsys, family):
    export = _export(family, indexed_decision=family == "battery-v3")
    accumulation = power_accumulation.register_accumulation(
        exposure_unit="per_question_draws", max_windows=2
    )
    report = producer_panels.panel_power_report(
        export,
        _controls(),
        accumulation,
        alpha=0.05,
        power_target=0.8,
        simulation_seed=3,
        replicates=20,
        max_questions=2,
    )
    assert report["family"] == family
    grid = report["power"]["laws"]["grid"]
    assert (grid["aggregate"]["P"] if family == "battery-v3" else grid["P"]) is None
    assert "sealed_bank_cross_batch" in report["power"]
    assert "PRIVATE-T3" not in json.dumps(report)
    paths = []
    for name, body in (
        ("export", export),
        ("controls", _controls()),
        ("accumulation", accumulation),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        paths.append(path)
    main(
        [
            "power-report",
            "--panel-export",
            str(paths[0]),
            "--controls",
            str(paths[1]),
            "--accumulation",
            str(paths[2]),
            "--alpha",
            "0.05",
            "--power-target",
            "0.8",
            "--simulation-seed",
            "3",
            "--replicates",
            "20",
            "--max-questions",
            "2",
        ]
    )
    rendered = capsys.readouterr().out
    assert "PRIVATE-T3" not in rendered
    assert json.loads(rendered) == report
