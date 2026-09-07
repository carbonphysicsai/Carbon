"""Static authority and leakage boundaries for B-07F."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "carbon/traineval/resolved_fixture.py"
A8_FILES = (
    ROOT / "carbon/traineval/model.py",
    ROOT / "carbon/traineval/service.py",
    ROOT / "carbon/traineval/stub.py",
)


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))


def _imports() -> set[str]:
    values: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
    return values


def test_b07f_has_no_store_dispatch_network_or_settlement_owner() -> None:
    forbidden = (
        "carbon.cards",
        "carbon.mcp",
        "carbon.leaderboard",
        "carbon.chain",
        "carbon.treasury",
        "carbon.settlement",
        "carbon.landscape",
        "carbon.qualification",
    )
    imports = _imports()
    assert not any(
        imported == prefix or imported.startswith(prefix + ".")
        for imported in imports
        for prefix in forbidden
    )


def test_b07f_uses_domain_owned_compiler_resource_and_score_paths() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "compile_strategy(" in source
    assert "assess_static_resources(" in source
    assert "self.__score_pack.fixture_score_input(" in source
    assert "ScoreEngine.score(" in source
    assert "SubmissionService(" not in source
    assert "ChallengeRegistry(" not in source
    assert "def submit(" not in source
    assert "def publish(" not in source


def test_b07f_cannot_accept_context_seed_mode_code_or_forecast() -> None:
    run_method = next(
        node
        for node in _tree().body
        if isinstance(node, ast.ClassDef)
        and node.name == "ResolvedPlanFixtureTrainEvalService"
        for node in node.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_fixture"
    )
    assert [argument.arg for argument in run_method.args.args] == ["self", "envelope"]
    identifiers = {node.id for node in ast.walk(_tree()) if isinstance(node, ast.Name)}
    for forbidden in (
        "MockContext",
        "MockEntropy",
        "OfficialContext",
        "OfficialEntropy",
        "QualificationContext",
        "QualificationEntropy",
        "raw_entropy",
        "official_seed",
        "participant_code",
        "caller_mode",
        "ResourceForecast",
        "quote_execution",
    ):
        assert forbidden not in identifiers


def test_b07f_branches_on_resolved_binding_not_raw_strategy_or_hash() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "policy.bindings" in source
    assert "surface.value" in source
    assert "envelope.strategy[" not in source
    assert "strategy_hash.value ==" not in source
    assert "fixture_sampling_level" in source
    assert "REGISTERED_LEVER_IGNORED" in source


def test_b07f_receipts_exclude_sensitive_and_authority_escalating_fields() -> None:
    tree = _tree()
    receipt_classes = {
        node.name: {
            item.target.id
            for item in node.body
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
        }
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name in {"FixtureReconstructionReceipt", "FixtureResultReceipt"}
    }
    fields = set().union(*receipt_classes.values())
    assert not fields.intersection(
        {
            "entropy",
            "seed",
            "seed_bytes",
            "training_observations",
            "heldout_observations",
            "raw_measurements",
            "filesystem_path",
            "scientifically_qualified",
            "production_authority",
            "leaderboard_authority",
            "frontier_authority",
            "settlement_authority",
        }
    )
    assert "TEST_ONLY_FIXTURE_NOT_QUALIFIED" in MODULE.read_text(encoding="utf-8")


def test_a8_legacy_modules_remain_unmodified_by_b07f_source() -> None:
    # The B-07F module is additive; these paths remain the separately owned A8
    # implementation and must not import or mention the new adapter.
    for path in A8_FILES:
        source = path.read_text(encoding="utf-8")
        assert "resolved_fixture" not in source
        assert "ResolvedPlanFixtureTrainEvalService" not in source
