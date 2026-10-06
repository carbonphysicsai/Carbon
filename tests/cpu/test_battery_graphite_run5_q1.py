"""Graphite run-5 battery Q1 panel: registration and committed-result checks.

The 27 CPU rebuilds take about 25 minutes, so they are not rerun here. These
tests check the panel, the contract and the committed report's internal
consistency.
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.battery.compile import compile_recipe
from carbon.battery.value import contract as ct
from carbon.battery.value import panel
from carbon.design_search import score_value

REPOSITORY = Path(__file__).resolve().parents[2]
EVIDENCE = REPOSITORY / "docs/development/evidence/graphite-run5-q1"
CONTRACTS = REPOSITORY / "carbon/battery/value/contracts"


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_panel_rebuilds_exactly_graphite_s_pinned_recipes():
    pinned = {
        "graphite-run5-" + row["proposal_id"]: row
        for row in _json(EVIDENCE / "graphite-run5-members.json")
    }
    rows = panel.PANELS["graphite-run5"]
    assert len(rows) == 9
    for label, strategy, seeds in rows:
        # Run 5 was rebuilt under battery implementation 1.0, and recompiles
        # to its frozen digests under 1.0 from main (TORCH-GPU-01); the current
        # implementation names these recipes by other digests.
        _, recipe = compile_recipe(strategy, implementation="1.0")
        assert recipe.recipe_digest == pinned[label]["recipe_digest"], label
        _, current = compile_recipe(strategy)
        assert current.recipe_digest != pinned[label]["recipe_digest"], label
        assert seeds[0] == pinned[label]["seed"]
        assert seeds[1:] == ((seeds[0] + 1) % 2**32, (seeds[0] + 2) % 2**32)
    assert "ev5" in panel.ATTACK_PANELS and "graphite-run5" not in panel.ATTACK_PANELS


def test_contract_is_ev4_with_only_identity_changed():
    ev4 = _json(CONTRACTS / "ev4-charge-protocol-selection.v1.json")
    run5 = _json(CONTRACTS / "graphite-run5-charge-protocol-selection.v1.json")
    assert run5["panel"] == "graphite-run5" and run5["case_prefix"] == "ev4"
    for key in set(ev4) | set(run5):
        if key in ("contract_id", "panel", "authority"):
            continue
        assert ev4[key] == run5[key], key
    assert {k: v for k, v in ev4["authority"].items() if k != "record"} == {
        k: v for k, v in run5["authority"].items() if k != "record"
    }
    document, _ = ct.load(CONTRACTS / "graphite-run5-charge-protocol-selection.v1.json")
    assert document["panel"] in ct.PANELS


def test_committed_report_recomputes_its_alignment():
    report = _json(EVIDENCE / "q1-report.json")
    members = report["members"]

    def panel_of(names):
        return {
            m: {
                "score": -members[m]["cpu_practice_score"],
                "value": members[m]["development_decision_loss"],
                "eligible": members[m]["eligible"],
                "recipe": members[m]["recipe"],
                "kind": "GRAPHITE_RECONSTRUCTED",
            }
            for m in names
        }

    one = [m for m, row in members.items() if row["first_seed"]]
    # p-fa70c075f903 aliases p-69268f1b74ec (aliasing.json), so n = 8.
    assert len(one) == report["n_one_seed"] == 8 and len(members) == 27
    assert (
        score_value.alignment(panel_of(one), top_k=3)["kendall_tau_b"]
        == report["one_seed"]["kendall_tau_b"]
    )
    assert (
        score_value.alignment(panel_of(list(members)), top_k=3)["kendall_tau_b"]
        == report["three_seed"]["kendall_tau_b"]
    )
    assert report["mask"]["common_resolved"] + len(report["mask"]["excluded"]) == 12


def test_aliasing_is_recorded_with_digests():
    aliasing = _json(EVIDENCE / "aliasing.json")
    by_alias = {a["alias"]: a for a in aliasing}
    fa70 = by_alias["graphite-run5-p-fa70c075f903"]
    assert fa70["identical_predictions"] is True
    assert fa70["alias_prediction_digest"] == fa70["target_prediction_digest"]
    assert fa70["alias_recipe_digest"] != fa70["target_recipe_digest"]
    assert by_alias["graphite-run5-p-4fd7fb870d2b"]["identical_predictions"] is False


def test_conditions_report_is_consumable_and_digest_bound():
    import hashlib

    from carbon.challenge_readiness import admission

    report = _json(EVIDENCE / "conditions.json")
    assert report["schema"] == "carbon.admission-conditions.v1"
    for name, digest in report["evidence_sha256"].items():
        actual = "sha256:" + hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest()
        assert actual == digest, name
    kinds = [c["kind"] for c in report["conditions"]]
    assert kinds == [
        "PANEL_ANTI_ALIGNMENT",
        "SHARED_INFEASIBLE_DECISION",
        "NEAR_LIMIT_FALSE_ACCEPTANCE",
        "SEED_LUCK_PROMOTION",
    ]
    assert {c["condition"] for c in report["conditions"]} <= set(admission.CONDITIONS)


def test_defences_record_the_gate_and_rules():
    defences = _json(EVIDENCE / "defences.json")
    assert defences["gate"]["cutoff_bands"] == 2.0
    assert defences["gate"]["bundled_first_seed"]["verdict"] == "PASS"
    assert defences["sr2_rule"]["rule"] == "sr2-a0-r0.3-g0.6-m0.1"
    assert set(defences["tau_by_rule"]) == {
        "control-exam-v1/ungated",
        "control-exam-v1/gated",
        "sr2-a0-r0.3-g0.6-m0.1/ungated",
        "sr2-a0-r0.3-g0.6-m0.1/gated",
    }
