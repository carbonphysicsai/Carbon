"""Toy-only winnability replay tests; no physics, training, or solver runs."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from carbon.design_search import budget_registration as br
from carbon.design_search import equal_budget as eb
from carbon.design_search import winnability_pilot as wp

ROOT = Path(__file__).resolve().parents[2]


def _input():
    registration = json.loads(
        (
            ROOT
            / "docs/development/challenge_pipeline/equal-budget-registration-v1.json"
        ).read_text()
    )
    registered = br.validate(registration)
    jobs = []
    for index in range(4):
        jobs.append(
            {
                "job_id": f"toy-{index}",
                "cluster_id": f"cluster-{index // 2}",
                "solver_order": ["a", "b", "c"],
                "screen_cost": {
                    "model": {"wall_s": 100, "core_s": 100},
                    "baseline": {"wall_s": 100, "core_s": 100},
                },
                "candidates": [
                    {
                        "design_id": design,
                        "reference": {"status": "FEASIBLE", "value": value},
                        "solve_cost": {"wall_s": 20000, "core_s": 50000},
                        "planning_bound": {"wall_s": 20000, "core_s": 50000},
                        "screen_rank": {"model": model_rank, "baseline": baseline_rank},
                    }
                    for design, value, model_rank, baseline_rank in (
                        ("a", 3, 2, 0),
                        ("b", 2, 1, 1),
                        ("c", 1, 0, 2),
                    )
                ],
            }
        )
    panel = eb.seal(
        {
            "schema": eb.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "challenge": "motor",
            "source_digest": "sha256:" + "a" * 64,
            "decision_rule_id": "toy-decision-v1",
            "objective": {"direction": "min", "unit": "toy-seconds"},
            "cost_basis": "ASSUMPTION",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "budgets": [
                registered.cap("motor", tier).time_compute for tier in br.TIERS
            ],
            "jobs": jobs,
            "registrations": {
                "solver_search": "toy-adaptive-v1",
                "model_screen": "toy-l0-v1",
                "baseline_screen": "toy-cheap-v1",
                "cost_plan": registered.registration_id,
            },
        }
    )
    return {
        "schema": wp.SCHEMA,
        "evidence_class": "DEVELOPMENT_PUBLIC",
        "panel": panel,
        "registration": registration,
        "methods": {
            "model": "PLAIN_L0_MLP",
            "cheap": "STRONGEST_APPLICABLE_CHEAP",
            "solver": "REGISTERED_ADAPTIVE_SOLVER",
        },
        "question_law": {
            "P": "toy-P-v1",
            "Q": "toy-Q-v1",
            "w": "toy-w-v1",
            "panel_use": "PUBLIC_HELDOUT",
        },
        "preparation_cost": {
            "model": {"wall_s": 1000, "core_s": 1000},
            "baseline": {"wall_s": 200, "core_s": 200},
        },
        "served_decisions": [1, 10, 100],
        "cost_record_digest": "sha256:" + "b" * 64,
        "learning_unit": "toy-error-units",
        "learning": [
            {
                "job_id": f"toy-{index}",
                "cluster_id": f"cluster-{index // 2}",
                "stratum": "toy-interior",
                "reference_status": "FEASIBLE_EXISTS",
                "pointwise_error": 0.1,
                "decision_agreement": index % 2 == 0,
                "false_feasible": False,
                "missed_feasible": False,
                "abstained": False,
            }
            for index in range(4)
        ],
    }


def test_three_arms_charge_preparation_and_replay_deterministically():
    source = _input()
    report = wp.evaluate(source, bootstrap_replicates=100, confidence=0.95, seed=7)
    assert report == wp.evaluate(
        source, bootstrap_replicates=100, confidence=0.95, seed=7
    )
    assert report["qualification"] == "UNDECIDED"
    assert report["thresholds"] == "HUMAN_INPUT"
    assert report["learnable"]["toy-interior"]["decision_agreement_fraction"] == 0.5
    first = report["advantage_and_headroom"][0]
    assert first["equal_budget"]["status"] == "OK"
    assert first["equal_budget"]["independent_clusters"] == 2
    assert (
        first["model_vs_cheap"][0]["paired"]["paired_model_minus_cheap_improvement"]
        == 1
    )
    assert first["model_vs_cheap"][0]["paired_bootstrap_ci"] == [1, 1]
    assert (
        first["equal_budget"]["curves"][0]["estimates"]["model_then_solver"][
            "mean_regret_conditional"
        ]
        == 0
    )
    assert (
        report["advantage_and_headroom"][0]["equal_budget"]["panel_digest"]
        != report["advantage_and_headroom"][1]["equal_budget"]["panel_digest"]
    )


def test_public_role_cost_and_registration_fail_closed():
    source = _input()
    for mutation in (
        lambda s: s.update(evidence_class="HIDDEN"),
        lambda s: s["question_law"].update(panel_use="EXAM"),
        lambda s: s["preparation_cost"].pop("baseline"),
        lambda s: s["methods"].update(model="TUNED_LEVEL4"),
        lambda s: s["panel"]["registrations"].update(cost_plan="wrong"),
    ):
        bad = copy.deepcopy(source)
        mutation(bad)
        with pytest.raises((wp.WinnabilityError, eb.EqualBudgetError)):
            wp.evaluate(bad, bootstrap_replicates=100, confidence=0.95, seed=7)


def test_reference_unresolved_is_not_a_candidate_failure():
    source = _input()
    body = copy.deepcopy(source["panel"])
    body.pop("panel_digest")
    body["jobs"][0]["candidates"][0]["reference"] = {
        "status": "UNRESOLVED",
        "value": None,
    }
    source["panel"] = eb.seal(body)
    source["learning"][0]["reference_status"] = "UNRESOLVED"
    source["learning"][0]["pointwise_error"] = None
    source["learning"][0]["decision_agreement"] = None
    source["learning"][0]["false_feasible"] = None
    source["learning"][0]["missed_feasible"] = None
    source["learning"][0]["abstained"] = None
    # A feasible alternative exists, but the incomplete bank still blocks replay.
    report = wp.evaluate(source, bootstrap_replicates=100, confidence=0.95, seed=7)
    assert (
        report["advantage_and_headroom"][0]["equal_budget"]["status"]
        == "UNRESOLVED_PANEL"
    )
    assert report["advantage_and_headroom"][0]["model_vs_cheap"] == []
    assert report["learnable"]["toy-interior"]["unresolved_count"] == 1
    source["learning"][0]["false_feasible"] = True
    with pytest.raises(wp.WinnabilityError, match="unresolved references"):
        wp.evaluate(source, bootstrap_replicates=100, confidence=0.95, seed=7)


def test_battery_retro_checks_public_digests_and_keeps_missing_costs(tmp_path):
    root = tmp_path / "public"
    (root / "experiment-predictions").mkdir(parents=True)
    reference = b"public toy reference\n"
    (root / "ev4-decision-references.jsonl").write_bytes(reference)
    manifest = []
    for name in ("mlp-s0.json.gz", "mlp-s1.json.gz", "mlp-s2.json.gz"):
        content = name.encode()
        (root / "experiment-predictions" / name).write_bytes(content)
        manifest.append(
            {
                "file": name,
                "folder": "experiment-predictions",
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    one = {
        "offered_questions": ["q"],
        "known_opportunity_questions": ["q"],
        "by_budget": {
            cap: {
                "per_member": {"mlp-s0": {"gain": 1, "attempts": int(cap)}},
                "fixed_solver_alone": {"gain": 0},
                "cheap_public_exact_cache_gain": 2,
            }
            for cap in wp.CAPS
        },
    }
    res07 = {
        "schema": wp.RES07_SCHEMA,
        "inventory": {
            "public_reference_sha256": hashlib.sha256(reference).hexdigest(),
            "bundle_manifest": manifest,
        },
        "verified_workflow_sensitivity": {family: one for family in wp.FAMILIES},
        "additional_cached_baselines_and_checks": {
            "by_family": {
                family: {
                    "by_budget": {
                        cap: {"cached_D_maps": {"bilinear_D_clamped": {"gain": 1.5}}}
                        for cap in wp.CAPS
                    }
                }
                for family in wp.FAMILIES
            }
        },
        "fresh_member_summary": {
            "mlp-s0": {
                family: {"offered": 1, "observed_unsafe": 0, "kinds": {}}
                for family in wp.FAMILIES
            }
        },
    }
    report = wp.battery_ev4_retrospective(res07, root)
    assert report["advantage"] == "INDETERMINATE_UNMATCHED_COMPLETE_COST"
    assert "adaptive competitor unmeasured" in report["solver_method_status"]
    assert report["families"]["nominal"]["caps"]["3"]["cheap_bilinear_gain_u"] == 1.5
    (root / "experiment-predictions" / "mlp-s1.json.gz").write_bytes(b"mutated")
    with pytest.raises(wp.WinnabilityError, match="digest"):
        wp.battery_ev4_retrospective(res07, root)
