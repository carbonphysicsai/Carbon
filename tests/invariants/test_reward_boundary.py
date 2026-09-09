"""Reward policy cannot grade, disclose private evidence or sign chain actions."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant
ROOT = Path(__file__).resolve().parents[2]


def test_reward_engine_does_not_own_science_or_signing():
    forbidden = ("bittensor", "carbon.scoring", "carbon.seeding", "carbon.traineval")
    for path in (ROOT / "carbon/rewards").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(forbidden)
            if isinstance(node, ast.Import):
                assert not any(alias.name.startswith(forbidden) for alias in node.names)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("eval", "exec")
    source = (ROOT / "carbon/rewards/ledger.py").read_text(encoding="utf-8")
    assert "_resolve_accepted_fixture(" in source
    assert '"SYNTHETIC_ONLY"' in source
    assert 'receipts.context.network != "localnet"' in source


def test_reward_public_time_methods_do_not_accept_activation_from_callers():
    tree = ast.parse((ROOT / "carbon/rewards/ledger.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in (
            "register",
            "open_batch",
            "close_batch",
            "project",
            "release_scorecard",
        ):
            assert not {"now", "timestamp", "activation_ms", "time_ms"}.intersection(
                arg.arg for arg in node.args.args
            )


def test_scientific_owners_do_not_consume_reward_policy():
    for directory in ("scoring", "traineval", "fees", "cards"):
        for path in (ROOT / "carbon" / directory).glob("*.py"):
            assert "carbon.rewards" not in path.read_text(encoding="utf-8")
