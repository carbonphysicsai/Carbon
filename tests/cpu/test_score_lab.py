"""Synthetic Scorelab contracts only; no hidden packs, fits or solver calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from carbon.battery.value import score_tuning as st
from scripts.dev.score_lab import bank, candidates, public_ev4, synthetic
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


def test_public_ev4_adapter_rejects_unpinned_reference(tmp_path):
    (tmp_path / "ev4-decision-references.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(LabRefused, match="ev4_public_reference_digest_mismatch"):
        public_ev4.build(tmp_path, ROOT)
