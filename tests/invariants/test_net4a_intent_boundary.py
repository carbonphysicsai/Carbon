"""Local fixture intent authority is nominal and cannot bypass later owners."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant


def test_intent_boundary_has_no_sdk_signing_or_second_evaluator():
    source = (
        Path(__file__).resolve().parents[2] / "carbon/rewards/intents.py"
    ).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(
                ("bittensor", "carbon.scoring", "carbon.traineval", "carbon.seeding")
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
        ):
            assert isinstance(node.func.value, ast.Name) and node.func.value.id == "db"
    for forbidden in (".sign(", "accepted=True", 'stage="LIVE"'):
        assert forbidden not in source
    assert "C2_REAL_ELIGIBILITY_ISSUER_UNAVAILABLE" in source
    assert "OPTIONAL_TREASURY_ISSUER_UNAVAILABLE" in source
