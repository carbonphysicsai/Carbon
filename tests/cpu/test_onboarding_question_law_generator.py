import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import law, packet
from carbon.design_search import (
    diversity,
    indexed,
    power_accumulation,
    producer_panels,
    tasks,
)

ROOT = Path(__file__).resolve().parents[2]


def draft(family):
    return packet.generate(
        {
            "schema": packet.SCHEMA,
            "challenge": family,
            "buyer": "mock buyer",
            "decision": "complete action",
            "physics": "toy",
            "solver": "toy",
        },
        ROOT,
    )


def export(family="motor"):
    task = tasks.task(
        "toy-question",
        identity={
            "challenge": "toy-challenge",
            "contract_version": "v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "toy.v1",
                "variables": [
                    {"name": "choice", "type": "integer", "min": 0, "max": 1, "step": 1}
                ],
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": 2,
            "seed": 17,
            "observer_version": "toy.v1",
            "reference_bank": "toy-bank",
        },
        conditions=[{"id": "c", "stratum": "s"}],
        strata={"s": {"p": 1, "q": 1, "w": 1}},
        candidates=["good", "bad"],
        actions={"good": {"choice": 0}, "bad": {"choice": 1}},
        objective={
            "quantity": "time",
            "unit": "toy",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[{"quantity": "margin", "unit": "toy", "op": ">=", "value": 0}],
    )
    law_ = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA_V2,
            "population_status": "UNREGISTERED",
            "kind": "grid",
            "draw_model": "iid_with_replacement",
            "batch_size": 1,
            "bins": [{"case": "toy-question", "q_mass": 1}],
            "mass_l1_error_bound": 0,
        }
    )
    return producer_panels.seal_export(
        {
            "schema": producer_panels.EXPORT_SCHEMA,
            "sealed": True,
            "family": family,
            "challenge_id": "toy-challenge",
            "exposure_unit": "per_question_draws",
            "exposure": [{"case": "toy-question", "limit": 2, "used": 0}],
            "window_sampling": power_accumulation.register_window_sampling(
                case_strata=[{"case": "toy-question", "stratum": "s"}],
                quotas_by_k=[{"questions_per_batch": 1, "quotas": {"s": 1}}],
            ),
            "questions": [
                {
                    "case": "toy-question",
                    "support_case": "toy-bank",
                    "task": task,
                    "reference": [
                        {
                            "candidate": c,
                            "condition": "c",
                            "values": {"time": 1, "margin": m},
                        }
                        for c, m in [("good", 1), ("bad", -1)]
                    ],
                    "close_call": False,
                    "refinement_demand": False,
                }
            ],
            "laws": [law_],
        }
    )


@pytest.mark.parametrize(
    "family,path,k",
    [
        ("battery-v3", "battery-v3-round2.json", 8),
        ("motor", "motor-round2.json", 12),
        ("f02", "f02-round2.json", 8),
    ],
)
def test_historical_proposal_crosswalks(family, path, k):
    source = json.loads(
        (ROOT / "docs/development/challenge_pipeline/question-laws" / path).read_text(
            encoding="utf-8"
        )
    )
    generated = law.generate(draft(family), law_source=source)
    assert generated["k"] == {
        "status": "HUMAN_INPUT",
        "recommendation": k,
        "basis": "Power and exposure owner selects; a panel's batch size is not approval",
    }
    assert generated["source_proposal_crosswalk"]["P"]
    assert generated["source_proposal_crosswalk"]["Q"]
    assert generated["source_proposal_crosswalk"]["w"]
    assert generated["T2a"]["near_refinement_bands"] == 2
    assert generated["T2a"]["minimum_distinct_feasible"] == 5
    assert generated["T2a"]["minimum_distinct_infeasible"] == 5
    assert generated["startup_cost"]["eur"] is None
    assert generated["bank"]["threshold_variation_renews_exposure"] is False


def test_panel_aggregate_no_population_or_private_ids_inferred():
    generated = law.generate(draft("motor"), export=export())
    assert generated["panel_basis"]["questions_checked"] == 1
    assert generated["diversity"][0]["Q"]["expected_distinct_winners_per_batch"] == 1
    assert generated["diversity"][0]["P"] is None
    assert "toy-question" not in json.dumps(generated)
    assert "toy-bank" not in json.dumps(generated)
    assert generated["P"]["status"] == "HUMAN_INPUT"


def test_unsealed_or_cross_family_panel_is_refused():
    value = export()
    with pytest.raises(packet.DraftError):
        law.generate(draft("f02"), export=value)
    value["sealed"] = False
    with pytest.raises(packet.DraftError):
        law.generate(draft("motor"), export=value)
    with pytest.raises(packet.DraftError):
        law.generate(draft("motor"), law_source={"schema": "wrong"})


def test_no_source_no_panel_is_not_a_green():
    generated = law.generate(draft("f17"))
    assert generated["panel_basis"] is None and generated["diversity"] is None
    assert generated["T2a"]["measured"] == "NOT_ASSESSED_BY_DRAFTING"
    assert generated["k"]["recommendation"] is None


def test_five_band_indexed_battery_panel_keeps_complete_map():
    panel = export("battery-v3")
    entry = panel["questions"][0]
    indices = [
        {"index_value": b, "buyer_weight": 0.2, "task": entry["task"]}
        for b in (5, 15, 25, 35, 40)
    ]
    refs = [
        {"index_value": b, "panel": entry["reference"]} for b in (5, 15, 25, 35, 40)
    ]
    entry["task"] = indexed.indexed_task(
        "toy-question",
        index_axis="ambient_c",
        indices=indices,
        query_budget=10,
        value_equivalence={
            "quantity": "time",
            "unit": "toy",
            "tolerance": 0,
            "rule": indexed.EQUIVALENCE_RULE,
        },
    )
    entry["reference"] = refs
    panel = producer_panels.seal_export(
        {k: v for k, v in panel.items() if k != "export_digest"}
    )
    report = law.generate(draft("battery-v3"), export=panel)
    assert report["diversity"][0]["Q"]["status_mix"]["FEASIBLE_EXISTS"] == 1
    assert report["panel_basis"]["questions_checked"] == 1
