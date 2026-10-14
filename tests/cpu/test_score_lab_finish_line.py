"""Readiness can fail even with all artifacts present; no hidden-file reader."""

import copy
import hashlib
import json
import statistics
from pathlib import Path

import pytest

from carbon.battery.value import score_proof
from scripts.dev.score_lab import finish_line as fl
from scripts.dev.score_lab.core import LabRefused, canonical_sha


def fixture(tmp_path):
    directory = tmp_path / "Business/research/fixture"
    directory.mkdir(parents=True)
    path = directory / "receipt.json"
    path.write_bytes(
        b'{"schema":"toy-receipt","complete":true,"mask":[1,2],"numeric":1}\n'
    )
    artifact = {
        "path": "Business/research/fixture/receipt.json",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "schema": "toy-receipt",
    }
    stages = []
    for name in sorted(fl.REQUIRED_STAGES):
        stages.append(
            {
                "id": name,
                "owner": "Fixture only",
                "owner_ticket": "TOY",
                "minimum_action": "Supply toy receipt",
                "validation": "Typed complete field",
                "readiness_predicate": "All explicit fixture checks pass",
                "depends_on": [],
                "checks": [
                    {
                        "artifact": "toy",
                        "pointer": ["complete"],
                        "op": "equals",
                        "expected": True,
                    }
                ],
            }
        )
    return {
        "schema": fl.SCHEMA,
        "scope": "PUBLIC_AND_SYNTHETIC_DEVELOPMENT",
        "artifacts": {"toy": artifact},
        "stages": stages,
        "final_holdout": {
            "custodian": "Fixture custodian",
            "commitment_sha256": "0" * 64,
            "reveal_policy": "Never read by readiness",
        },
    }, path


def test_positive_fixture_does_not_grant_selection_or_qualification(tmp_path):
    manifest, _ = fixture(tmp_path)
    result = fl.assess(manifest, tmp_path)
    assert result["status"] == "REGISTERED_RESEARCH_INPUTS_PRESENT"
    assert result["scientific_qualification"] is False
    assert result["rule_selection"] is None
    assert result["final_holdout_content_read"] is False


def test_missing_changed_and_false_receipts_are_distinct(tmp_path):
    manifest, path = fixture(tmp_path)
    path.write_bytes(b'{"schema":"toy-receipt","complete":false}\n')
    result = fl.assess(manifest, tmp_path)
    first = manifest["stages"][0]["id"]
    assert "ARTIFACT_DIGEST_MISMATCH" in result["stages"][first]["blockers"]
    manifest["artifacts"]["toy"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    manifest["ready"] = True
    result = fl.assess(manifest, tmp_path)
    assert "EVIDENCE_PREDICATE_NOT_MET" in result["stages"][first]["blockers"]
    path.unlink()
    assert (
        "MISSING_ARTIFACT" in fl.assess(manifest, tmp_path)["stages"][first]["blockers"]
    )


def test_absent_predicates_and_dependencies_do_not_pass(tmp_path):
    manifest, _ = fixture(tmp_path)
    first, second = manifest["stages"][:2]
    first["checks"] = []
    second["depends_on"] = [first["id"]]
    result = fl.assess(manifest, tmp_path)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert "dependency:" + first["id"] in result["stages"][second["id"]]["blockers"]
    second["depends_on"] = ["not-a-stage"]
    with pytest.raises(LabRefused, match="readiness_dependency_order"):
        fl.assess(manifest, tmp_path)


@pytest.mark.parametrize(
    "path",
    [
        "../hidden.json",
        "C:/hidden.json",
        "codex-queue/inputs/holdout.json",
        "Business/research/../../hidden.json",
        "Business/research/code.py",
    ],
)
def test_external_and_nonreceipt_sources_refused_before_read(tmp_path, path):
    manifest, _ = fixture(tmp_path)
    manifest["artifacts"]["toy"]["path"] = path
    with pytest.raises(LabRefused, match="readiness_public_receipt_path"):
        fl.assess(manifest, tmp_path)


def test_holdout_accepts_only_commitment_no_path(tmp_path):
    manifest, _ = fixture(tmp_path)
    manifest["final_holdout"]["path"] = "do-not-open.json"
    with pytest.raises(LabRefused, match="readiness_custody_only_no_content"):
        fl.assess(manifest, tmp_path)


def test_omitting_blocked_stage_cannot_manufacture_readiness(tmp_path):
    manifest, _ = fixture(tmp_path)
    manifest["stages"].pop()
    with pytest.raises(LabRefused, match="readiness_stage_identity"):
        fl.assess(manifest, tmp_path)


def test_types_missing_fields_and_owner_are_checked(tmp_path):
    manifest, _ = fixture(tmp_path)
    first = manifest["stages"][0]
    first["checks"] = [
        {"artifact": "toy", "pointer": ["numeric"], "op": "equals", "expected": True}
    ]
    assert not fl.assess(manifest, tmp_path)["stages"][first["id"]]["ready"]
    first["checks"][0]["pointer"] = ["absent"]
    assert (
        "REQUIRED_FIELD_MISSING"
        in fl.assess(manifest, tmp_path)["stages"][first["id"]]["blockers"]
    )
    first["owner"] = ""
    with pytest.raises(LabRefused, match="readiness_unowned_gap"):
        fl.assess(manifest, tmp_path)


@pytest.mark.parametrize(
    "value", ["HUMAN_INPUT", "UNKNOWN", "TBD", {"law": None}, ["UNMEASURED"]]
)
def test_placeholder_is_not_present_evidence(value):
    assert not fl._predicate(value, {"op": "nonempty"})


def test_capacity_alias_and_dominance_are_real_counterexamples():
    result = fl.capacity_witnesses(
        {"good": [1, 1], "alias": [1, 1], "worse": [2, 2]},
        {"good": 3, "alias": 2, "worse": 1},
    )
    assert len(result["exact_feature_aliases"]) == 1
    assert len(result["monotone_order_reversals"]) == 2
    assert not result["fitted"]
    corrected = fl.capacity_witnesses(
        {"good": [3, 3], "alias": [2, 2], "worse": [1, 1]},
        {"good": 3, "alias": 2, "worse": 1},
    )
    assert (
        not corrected["exact_feature_aliases"]
        and not corrected["monotone_order_reversals"]
    )


def test_capacity_requires_same_complete_finite_members():
    with pytest.raises(LabRefused, match="capacity_members"):
        fl.capacity_witnesses({"a": [1], "b": [2]}, {"a": 1})
    with pytest.raises(LabRefused, match="capacity_finite_complete_features"):
        fl.capacity_witnesses({"a": [None], "b": [2]}, {"a": 1, "b": 2})


def test_measurement_ceiling_reuses_existing_method_and_refuses_missing():
    losses = [[1, 2, 3], [2, 3, 5], [4, 5, 6]]
    result = fl.measurement_ceiling(losses, bootstrap=10, seed=42)
    assert result["estimate"] == score_proof.value_ceiling(losses, n_boot=10, seed=42)
    partial = copy.deepcopy(losses)
    partial[0][0] = None
    with pytest.raises(LabRefused, match="ceiling_common_complete_mask"):
        fl.measurement_ceiling(partial, bootstrap=10, seed=42)
    with pytest.raises(LabRefused, match="ceiling_explicit_bootstrap"):
        fl.measurement_ceiling(losses, bootstrap=0, seed=42)


def test_real_manifest_cannot_mistake_public_metadata_for_complete_real_inputs():
    root = Path(__file__).resolve().parents[2]
    path = (
        root
        / "Business/research/score-lab-campaign-01/finish-line/READINESS_MANIFEST.json"
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    result = fl.assess(manifest, root)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    for name in (
        "job_contract",
        "cohort",
        "paired_score_inputs",
        "references",
        "final_holdout",
    ):
        assert not result["stages"][name]["ready"]
    assert any(
        check["observed"] is False
        for check in result["stages"]["job_contract"]["checks"]
    )
    assert not any(
        "ARTIFACT_DIGEST_MISMATCH" in stage["blockers"]
        for stage in result["stages"].values()
    )


def test_diagnostic_requires_all_profiles_and_exact_plan_binding():
    plan = {"profiles": [{}, {}]}
    with pytest.raises(LabRefused, match="combined_diagnostic_profile_coverage"):
        fl.combined_diagnostics(plan, [{"profile_index": 0}], seed=42)
    cells = [
        {"profile_index": i, "plan_sha256": "wrong", "component_index": 0}
        for i in range(2)
    ]
    with pytest.raises(LabRefused, match="combined_diagnostic_binding"):
        fl.combined_diagnostics(plan, cells, seed=42)


def test_diagnostic_replays_true_toy_value_and_detects_changed_saved_value():
    root = Path(__file__).resolve().parents[2]
    config = json.loads(
        (root / "scripts/dev/score_lab/physics-example.json").read_text(
            encoding="utf-8"
        )
    )
    config["bootstrap"] = 2
    plan = {"profiles": [{"config": config}], "value_scopes": ["in_range"]}
    panel = fl.physics.build(config)
    view = fl.physics.value_view(panel, "in_range")
    common = sorted(
        q
        for q in view["value_questions"]
        if all(m["value_losses"][q] is not None for m in view["members"])
    )
    values = {
        m["id"]: -statistics.fmean(m["value_losses"][q] for q in common)
        for m in view["members"]
    }
    # These are declared fixture features; no actual candidate scorer is claimed.
    scores = {
        m["id"]: {"score": float(i), "admissible": True, "tier": 0}
        for i, m in enumerate(panel["members"])
    }
    outcome = {"common_mask_sha256": canonical_sha(common), "value_by_member": values}
    cell = {
        "profile_index": 0,
        "component_index": 0,
        "plan_sha256": canonical_sha(plan),
        "panel_sha256": canonical_sha(panel),
        "rows": [
            {
                "candidate": f"TOY-ABLATION/{leg}/NO-GATE",
                "physics_index": 0,
                "scores": copy.deepcopy(scores),
                "outcomes": {"in_range": copy.deepcopy(outcome)},
            }
            for leg in ("A", "Q")
        ],
    }
    result = fl.combined_diagnostics(plan, [cell], seed=42)
    assert len(result["rows"]) == 1
    assert result["rows"][0]["monotone_a_q_capacity"]["members"] == 6
    member = panel["members"][0]["id"]
    cell["rows"][0]["outcomes"]["in_range"]["value_by_member"][member] += 1
    with pytest.raises(LabRefused, match="combined_diagnostic_value_identity"):
        fl.combined_diagnostics(plan, [cell], seed=42)
    cell["rows"][0]["scores"][member] = None
    withheld = fl.combined_diagnostics(plan, [cell], seed=42)
    assert withheld["rows"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert withheld["rows"][0]["monotone_a_q_capacity"] is None
