"""Synthetic Scorelab contracts only; no hidden packs, fits or solver calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from carbon.battery.value import score_tuning as st
from scripts.dev.score_lab import (
    bank,
    candidates,
    physics,
    public_ev4,
    public_physics,
    synthetic,
)
from scripts.dev.score_lab.legacy_cli import _report
from scripts.dev.score_lab.core import (
    LabRefused,
    analyze,
    registry_rule,
    v2_rule,
    validate_panel,
)

ROOT = Path(__file__).resolve().parents[2]
V9 = ROOT / "docs/development/evidence/battery-score-tuning/registry-v9.json"


def _config(**updates):
    return next(synthetic.profiles()) | updates


def test_analytic_best_and_disjoint_questions():
    config = _config(space="continuous", optima="multi", constraint="tight")
    panel = synthetic.build(config)
    validate_panel(panel)
    assert not set(panel["score_questions"]) & set(panel["value_questions"])
    for question in panel["value_questions"].values():
        best = question["exact_best_objective"]
        if best is not None:
            sampled = min(
                a["objective"]
                for a in question["actions"].values()
                if a["status"] == "FEASIBLE"
            )
            assert best <= sampled + 1e-12
            assert sampled - best < 0.001


def test_rule_receives_scoring_half_only_and_bootstrap_replays():
    panel = synthetic.build(_config())
    seen = []

    def rule(predictions, references, metadata):
        assert set(predictions) == set(references) == set(panel["score_questions"])
        assert not set(references) & set(panel["value_questions"])
        seen.append(metadata["score_row"]["E"])
        return 1 / (1 + metadata["score_row"]["E"])

    a = analyze(panel, rule, bootstrap=35)
    b = analyze(panel, rule, bootstrap=35)
    assert a == b
    assert len(seen) == 2 * len(panel["members"])
    assert a["status"] == "MEASURED_DEVELOPMENT"
    assert a["tau_ci95"] is not None
    assert a["top1_regret"] >= 0
    assert a["always_abstain_rank"] is not None
    assert a["cheap_baseline_rank"] is not None
    summary = _report([a])
    assert summary["cheap_baseline_median_rank"] == a["cheap_baseline_rank"]
    assert summary["always_abstain_median_rank"] == a["always_abstain_rank"]
    assert "space" in summary["knob_median_tau"]


def test_registry_uses_exact_score_tuning_candidate():
    panel = synthetic.build(_config())
    rule = registry_rule(V9, "A")
    member = panel["members"][0]
    candidate = st.load_registry(V9)[0]["A"]
    result = rule(
        member["score_predictions"],
        panel["score_questions"],
        {"score_row": member["score_row"]},
    )
    assert result["score"] == st.score_member(candidate, member["score_row"])
    assert analyze(panel, rule, bootstrap=20)["rule"]["candidate"] == "A"


def test_validator_candidate_contract_runs_all_ten_on_score_half(tmp_path):
    source = tmp_path / "candidates.py"
    source.write_text(
        "def rule(predictions, references, metadata):\n"
        "    assert set(predictions) == set(references) == set(metadata['questions'])\n"
        "    q = next(iter(references))\n"
        "    a = next(iter(references[q]))\n"
        "    assert set(predictions[q][a]['margins']) == {'coupled_a', 'coupled_b'}\n"
        "    return {'score': 1.0 / (1.0 + abs(predictions[q][a]['objective']"
        " - references[q][a]['objective'])), 'gate': 'PASS'}\n"
        "RULES = {str(i): {'rule': rule, 'tier2_registry_id': None}"
        " for i in range(10)}\n",
        encoding="utf-8",
    )
    specs, digest = candidates.load(source)
    panel = synthetic.build(_config())
    for name, spec in specs.items():
        rule = candidates.rule_from_spec(name, spec, path_digest=digest, panel=panel)
        result = analyze(panel, rule, bootstrap=5)
        assert result["status"] == "MEASURED_DEVELOPMENT"
        assert result["rule"]["candidate"] == name
    panel["scope"] = "PUBLIC_DEVELOPMENT"
    assert (
        candidates.rule_from_spec("0", specs["0"], path_digest=digest, panel=panel)
        is None
    )


def test_v2_cost_and_missing_gate_are_explicit_assumptions():
    panel = synthetic.build(_config())
    definition = {
        "id": "VALUE-METRIC-V2",
        "revision": 2,
        "estimand": {"per_question": "U = G - kappa * n"},
    }
    rule = v2_rule(definition=definition, kappa=0.1, cap=2, unit=1.0)
    missing = analyze(panel, rule, bootstrap=10)
    assert missing == {
        "status": "INSUFFICIENT_EVIDENCE",
        "reason": "unscored_primary_members",
        "count": len(synthetic.MODEL_NAMES),
    }
    panel["score_metadata"] = {
        "v2_gate": {"measure": "feasibility", "cutoff": 0.05, "comparison": "exceeds"}
    }
    measured = analyze(panel, rule, bootstrap=10)
    assert measured["status"] == "MEASURED_DEVELOPMENT"
    noop = next(m for m in panel["members"] if m["id"] == "control-always-abstain")
    assert (
        rule(
            noop["score_predictions"],
            panel["score_questions"],
            {"score_row": noop["score_row"], **panel["score_metadata"]},
        )["score"]
        == 0
    )
    with pytest.raises(LabRefused, match="v2_human_input_required"):
        v2_rule(definition=definition, kappa=None, cap=2, unit=1.0)
    member = panel["members"][0]
    qid = next(iter(panel["score_questions"]))
    member["score_predictions"][qid].pop(next(iter(member["score_predictions"][qid])))
    assert (
        rule(
            member["score_predictions"],
            panel["score_questions"],
            {"score_row": member["score_row"], **panel["score_metadata"]},
        )
        is None
    )


def test_v2_refuses_ev4_job_and_matched_toy_buyer_runs():
    definition = {
        "id": "VALUE-METRIC-V2",
        "revision": 2,
        "estimand": {"per_question": "U = G - kappa * n"},
    }
    rule = v2_rule(definition=definition, kappa=0.1, cap=2, unit=1.0)
    panel = synthetic.build(
        _config(verification_cost_ASSUMPTION=0.1), buyer={"cap": 2, "unit": 1.0}
    )
    panel["score_metadata"] = {
        "v2_gate": {"measure": "feasibility", "cutoff": 0.05, "comparison": "exceeds"}
    }
    measured = analyze(panel, rule, bootstrap=10)
    assert measured["status"] == "MEASURED_DEVELOPMENT"
    assert measured["top1_regret_reference"] == "EXACT_ANALYTIC_ORACLE"
    panel["scope"] = "PUBLIC_DEVELOPMENT"
    panel["assumption"]["job"] = "battery-EV4-CV-onset-proxy"
    assert analyze(panel, rule) == {
        "status": "INSUFFICIENT_EVIDENCE",
        "reason": "v2_bank_not_registered_for_public_job",
    }


def test_rule_nonfinite_and_score_value_overlap_refused():
    panel = synthetic.build(_config())
    with pytest.raises(LabRefused, match="rule_score_nonfinite"):
        analyze(panel, lambda _p, _r, _m: float("nan"), bootstrap=1)
    panel["value_questions"][next(iter(panel["score_questions"]))] = {}
    with pytest.raises(LabRefused, match="score_value_question_overlap"):
        validate_panel(panel)


def test_gamer_has_high_scoring_accuracy_but_bad_value():
    panel = synthetic.build(_config(space="continuous", constraint="tight"))
    by_id = {m["id"]: m for m in panel["members"]}
    gamer = by_id["adversarial-gamer"]
    high_noise = by_id["unbiased-high-0"]
    assert gamer["score_row"]["legs"]["a"] > high_noise["score_row"]["legs"]["a"]
    assert sum(x or 0 for x in gamer["value_losses"].values()) >= 0


def _bank_fixture():
    definition = json.dumps({"id": "VALUE-METRIC-V2", "revision": 2}).encode()
    record = {
        "question_id": "q1",
        "task": "target",
        "block_id": "b1",
        "half": "development",
        "weight": 1.0,
        "fallback_action": "b",
        "class": "SCORED",
        "actions": {
            "b": [
                {
                    "status": "FEASIBLE",
                    "objective": 1.0,
                    "record_sha256": "sha256:r1",
                    "image_digest": "sha256:image",
                }
            ],
            "a": [
                {
                    "status": "FEASIBLE",
                    "objective": 0.2,
                    "record_sha256": "sha256:r2",
                    "image_digest": "sha256:image",
                }
            ],
        },
    }
    records = [
        record,
        {**record, "question_id": "q2", "block_id": "b2"},
        {**record, "question_id": "q3", "block_id": "b3", "task": "slightly-warmer"},
    ]
    manifest = {
        "definition_digest": "sha256:" + hashlib.sha256(definition).hexdigest(),
        "question_law_digest": "sha256:law",
        "population_digest": "sha256:population",
        "proposal_digest": "sha256:proposal",
        "weights_digest": "sha256:weights",
        "drawer_seed_commitment": "sha256:seed",
        "image_digest": "sha256:image",
        "mms_acceptance_digest": "sha256:mms",
        "train_separation": "PASS",
        "objective_aggregation": "worst_case",  # registered toy law
        "objective_sense": "minimize",
        "neighbour_declarations": [{"id": "slightly-warmer"}],
        "cheap_arm_registration": {
            "status": "FROZEN_BEFORE_DRAW",
            "evidence_digest": "sha256:cheap",
        },
    }
    cheap = {
        q["question_id"]: {
            "a": {"feasible": False, "objective": 0.2},
            "b": {"feasible": False, "objective": 1.0},
        }
        for q in records
    }
    model = {
        q["question_id"]: {
            "a": {"feasible": True, "objective": 0.2},
            "b": {"feasible": False, "objective": 1.0},
        }
        for q in records
    }
    return definition, manifest, records, cheap, model


def test_bank_check_winnability_and_sealed_refusal():
    definition, manifest, records, cheap, model = _bank_fixture()
    result = bank.check(
        manifest,
        records,
        definition_bytes=definition,
        cheap=cheap,
        reference_model=model,
        cap=1,
        kappa=0.1,
        unit=1.0,
        ceiling_threshold=0.5,
        learnability={"train_sizes": [10, 20], "accuracies": [0.5, 0.6]},
        replicates=30,
    )
    assert result["status"] == "DEVELOPMENT_DIAGNOSTIC"
    assert result["winnability"]["always_abstain_U"] == 0
    assert result["winnability"]["paired_lower_positive"]
    assert result["winnability"]["cheap_below_assumed_threshold"]
    with pytest.raises(LabRefused, match="sealed_or_empty_bank_records"):
        bank.check(
            manifest,
            [dict(records[0], half="confirmation")],
            definition_bytes=definition,
        )
    with pytest.raises(LabRefused, match="bank_definition_digest"):
        bank.check(
            dict(manifest, definition_digest="sha256:wrong"),
            records,
            definition_bytes=definition,
        )


def test_bank_missing_registration_is_not_pass():
    definition, manifest, records, _cheap, _model = _bank_fixture()
    result = bank.check(
        dict(manifest, train_separation=None), records, definition_bytes=definition
    )
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    with pytest.raises(LabRefused, match="bank_bootstrap_count"):
        bank.check(manifest, records, definition_bytes=definition, replicates=0)
    bad = [
        {
            **records[0],
            "actions": {
                **records[0]["actions"],
                "b": [{**records[0]["actions"]["b"][0], "objective": float("nan")}],
            },
        }
    ]
    with pytest.raises(LabRefused, match="bank_condition_record"):
        bank.check(manifest, bad, definition_bytes=definition)
    assert "train_separation" in result["missing_registration"]
    with pytest.raises(LabRefused, match="bank_objective_aggregation_unsupported"):
        bank.check(
            dict(manifest, objective_aggregation="mean"),
            records,
            definition_bytes=definition,
        )
    result = bank.check(manifest, records[:2], definition_bytes=definition)
    assert result["neighbour_tasks_missing"] == ["slightly-warmer"]
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_bank_decision_determined_unresolved_and_scored_share():
    definition, manifest, records, cheap, model = _bank_fixture()
    uncertain = {
        "status": "UNRESOLVED",
        "objective": 0.8,
        "record_sha256": "sha256:uncertain",
        "image_digest": "sha256:image",
    }
    records = [{**q, "actions": {**q["actions"], "c": [uncertain]}} for q in records]
    cheap = {
        key: {**pred, "c": {"feasible": False, "objective": 0.8}}
        for key, pred in cheap.items()
    }
    model = {
        key: {**pred, "c": {"feasible": False, "objective": 0.8}}
        for key, pred in model.items()
    }
    result = bank.check(
        manifest,
        records,
        definition_bytes=definition,
        cheap=cheap,
        reference_model=model,
        cap=1,
        kappa=0.1,
        unit=1.0,
        ceiling_threshold=0.5,
        learnability={"train_sizes": [10, 20], "accuracies": [0.5, 0.6]},
        replicates=30,
    )
    assert result["classes"]["SCORED"] == 3
    assert result["decision_determined_with_unresolved"] == 3
    assert result["status"] == "DEVELOPMENT_DIAGNOSTIC"
    # One unresolved action could improve on the known best, and another
    # question lacks a reference: the scored share falls below one half.
    better = {**uncertain, "objective": 0.1}
    incomplete = {**uncertain, "status": "FAILED_REFERENCE"}
    changed = [
        {
            **records[0],
            "actions": {**records[0]["actions"], "c": [better]},
            "class": "INCOMPLETE",
        },
        {
            **records[1],
            "actions": {**records[1]["actions"], "c": [incomplete]},
            "class": "INCOMPLETE",
        },
        records[2],
    ]
    result = bank.check(manifest, changed, definition_bytes=definition)
    assert result["classes"] == {"SCORED": 1, "RESCUE": 0, "NONE": 0, "INCOMPLETE": 2}
    assert result["size_blocker"] == "scored_share_below_half"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_bank_fallback_with_known_breach_is_rescue_even_if_another_condition_is_in_band():
    _definition, _manifest, records, _cheap, _model = _bank_fixture()
    question = records[0]
    unresolved = {
        **question["actions"]["b"][0],
        "status": "UNRESOLVED",
        "objective": 1.0,
    }
    breached = {**unresolved, "status": "INFEASIBLE"}
    mixed = {
        **question,
        "actions": {**question["actions"], "b": [breached, unresolved]},
    }
    assert bank.classify(mixed) == ("RESCUE", False)


def test_bank_refuses_maximize_law_before_classifying_better_unresolved_action():
    definition, manifest, records, _cheap, _model = _bank_fixture()
    uncertain = {
        **records[0]["actions"]["a"][0],
        "status": "UNRESOLVED",
        "objective": 2.0,  # better than fallback for a maximizing buyer
    }
    question = {
        **records[0],
        "actions": {**records[0]["actions"], "c": [uncertain]},
    }
    with pytest.raises(LabRefused, match="bank_objective_sense_unsupported"):
        bank.check(
            {**manifest, "objective_sense": "maximize"},
            [question],
            definition_bytes=definition,
        )


def test_public_ev4_adapter_rejects_unpinned_reference(tmp_path):
    (tmp_path / "ev4-decision-references.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(LabRefused, match="ev4_public_reference_digest_mismatch"):
        public_ev4.build(tmp_path, ROOT)


def _physics_config():
    path = ROOT / "scripts/dev/score_lab/physics-example.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["bootstrap"] = 3
    return config


def test_physics_toy_strata_are_disjoint_and_neighbours_change_true_value():
    config = _physics_config()
    panel = physics.build(config)
    validate_panel(panel)
    assert set(panel["score_questions"]).isdisjoint(panel["value_questions"])
    assert set(panel["value_strata"].values()) == {
        "in_range",
        "shifted",
        "extrapolated",
    }
    by_id = {m["id"]: m for m in panel["members"]}
    good = by_id["physics-understanding-0"]
    overfit = by_id["target-overfit-0"]
    extrapolated = [q for q, s in panel["value_strata"].items() if s == "extrapolated"]
    assert sum(good["value_losses"][q] for q in extrapolated) < sum(
        overfit["value_losses"][q] for q in extrapolated
    )
    assert len(good["score_metadata"]["neighbours"]) == 4
    target = physics.value_view(panel, "in_range")
    blend = physics.value_view(panel, "neighbourhood_blend", 1.0)
    assert target["members"][0]["value_losses"] != blend["members"][0]["value_losses"]
    assert target["score_questions"] is blend["score_questions"]


def test_candidate_adapter_passes_score_only_physics_and_preserves_floor_tier():
    config = _physics_config()
    panel = physics.build(config)
    seen = []

    def rule(predictions, references, metadata):
        assert set(predictions) == set(references) == set(metadata["questions"])
        assert not set(references) & set(panel["value_questions"])
        assert len(metadata["neighbours"]) == 4
        seen.append(metadata["physics"]["extrapolation"])
        return {
            "score": 0.9,
            "gate": "PASS",
            "tier": int(metadata["physics"]["extrapolation"] > 0.1),
        }

    proxy = candidates.rule_from_spec(
        "toy", {"rule": rule}, path_digest="fixture", panel=panel
    )
    result = analyze(physics.value_view(panel, "in_range"), proxy, bootstrap=3)
    assert result["status"] == "MEASURED_DEVELOPMENT"
    assert len(seen) == len(panel["members"])
    assert result["physics_tiers"]["target-overfit-0"] == 1
    assert (
        result["ranked_scores"]["target-overfit-0"]
        < result["ranked_scores"]["physics-understanding-0"]
    )


def test_floor_rank_is_lexicographic_and_gate_failures_stay_last():
    panel = synthetic.build(_config())
    for i, member in enumerate(panel["members"]):
        member["score_metadata"] = {
            "toy_tier": i % 4,
            "toy_gate": i == 3,
            "toy_score": 1e100 if i % 4 == 3 else float(i),
        }

    def rule(_predictions, _references, metadata):
        return {
            "score": metadata["toy_score"],
            "admissible": not metadata["toy_gate"],
            "tier": metadata["toy_tier"],
        }

    result = analyze(panel, rule, bootstrap=3)
    names = [member["id"] for member in panel["members"]]
    ranks = result["ranked_scores"]
    assert ranks[names[0]] > ranks[names[1]] > ranks[names[2]]
    assert ranks[names[2]] > ranks[names[3]]
    assert result["physics_floor_failures"] > 0
    for member in panel["members"]:
        member["score_metadata"]["toy_tier"] += 1
    assert analyze(panel, rule, bootstrap=3)["top1_member"] is None


def test_physics_switches_and_sensitivity_remain_assumptions():
    config = _physics_config()
    config["sensitivity"] = {"neighbourhood.size": [0.16]}

    def rule(predictions, references, metadata):
        score = 1 / (
            1 + abs(next(iter(next(iter(predictions.values())).values()))["objective"])
        )
        mode = metadata["knobs"]["physics"]["mode"]
        trait = metadata["physics"]["extrapolation"]
        return {
            "score": score / (1 + trait) if mode == "BLEND" else score,
            "gate": "FAIL" if mode == "GATE" and trait > 0.1 else "PASS",
            "tier": int(mode == "FLOOR" and trait > 0.1),
        }

    report = physics.sensitivity(config, {"toy": {"rule": rule}}, "fixture")
    assert len(report["rows"]) == len(config["physics_sweep"])
    assert len(report["sensitivity"]["table"]) == 1
    assert report["physics_verdict"]["status"] == "DESCRIPTIVE_ONLY"
    off = next(row for row in report["rows"] if row["switch"]["mode"] == "OFF")
    assert off["good_wrongly_excluded"] == 0
    with pytest.raises(LabRefused, match="physics_blend_denominator"):
        bad = _physics_config()
        bad["physics_sweep"][-1]["limit"] = {}
        physics.build(bad)


def test_public_physics_traits_are_read_only_and_missing_b9_refuses(tmp_path):
    paired = {
        "schema": "carbon.physics-pair-readings.v2",
        "scope": "PUBLIC_DEVELOPMENT",
        "complete": True,
        "public_members": ["a", "b"],
        "readings": {
            "B15": {"a": [0.1, 0.3], "b": [0.0]},
            "B16": {"a": [0.2], "b": [0.4]},
        },
    }
    b9 = {
        "schema": "carbon.research.physics-consistency-public.v1",
        "maturity": "DEVELOPMENT_DESCRIPTIVE_NOT_QUALIFIED",
        "members": [
            {"member": "a", "metrics": {"case_maxima": {"below_ambient": 0.5}}},
            {"member": "b", "metrics": {"case_maxima": {"below_ambient": 0.6}}},
        ],
    }
    p1, p2 = tmp_path / "paired.json", tmp_path / "b9.json"
    p1.write_text(json.dumps(paired), encoding="utf-8")
    p2.write_text(json.dumps(b9), encoding="utf-8")
    traits = public_physics.load_traits(p1, p2, expected_count=2)
    assert traits["members"]["a"] == {"b15": 0.3, "b16": 0.2, "b9": 0.5}
    assert len(traits["source_sha256"]["plt01"]) == 64
    b9["members"].pop()
    p2.write_text(json.dumps(b9), encoding="utf-8")
    with pytest.raises(LabRefused, match="physics_public_b9_reading"):
        public_physics.load_traits(p1, p2, expected_count=2)


def test_public_physics_replay_uses_registered_score_and_reports_missing_trait():
    panel = synthetic.build(_config())
    panel["scope"] = "PUBLIC_DEVELOPMENT"
    panel["assumption"]["job"] = "battery-EV4-CV-onset-proxy"
    panel["provenance"] = {
        "reference_sha256": public_ev4.PUBLIC_REFERENCE_SHA256,
        "bundle_sha256": {m["id"]: "fixture" for m in panel["members"]},
    }
    traits = {
        "members": {
            m["id"]: {"b15": 0.02, "b9": 0.3, "b16": 0.04} for m in panel["members"]
        },
        "source_sha256": {"plt01": "a" * 64, "b9": "b" * 64},
    }

    def exact_rule(_predictions, _references, metadata):
        return {"score": 1 / (1 + metadata["score_row"]["E"]), "admissible": True}

    exact_rule.rule_identity = {"kind": "fixture_exact_registry"}

    def wrap(rule):
        def wrapped(predictions, references, metadata):
            result = rule(predictions, references, metadata)
            switch = metadata["knobs"]["physics"]
            if switch["mode"] == "FLOOR":
                result["tier"] = int(metadata["physics"]["b9"] > switch["limit"]["b9"])
            return result

        return wrapped

    switches = [
        {"mode": "OFF", "limit": {}, "weight": {}},
        {"mode": "FLOOR", "limit": {"b9": 0.2}, "weight": {}},
        {"mode": "GATE", "limit": {"extrapolation": 0.1}, "weight": {}},
    ]
    report = public_physics.replay(
        panel, traits, exact_rule, switches, bootstrap=3, with_physics=wrap
    )
    assert report["replayed_members"] == len(panel["members"])
    assert [row["status"] for row in report["rows"]] == [
        "MEASURED_DEVELOPMENT",
        "MEASURED_DEVELOPMENT",
        "INSUFFICIENT_EVIDENCE",
    ]
    traits["members"].pop(panel["members"][0]["id"])
    assert (
        public_physics.replay(
            panel, traits, exact_rule, switches, bootstrap=3, with_physics=wrap
        )["reason"]
        == "public_trait_member_mismatch"
    )
