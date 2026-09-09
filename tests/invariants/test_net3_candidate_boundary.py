"""Candidate transport cannot become a second scientific or signing authority."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant
ROOT = Path(__file__).resolve().parents[2]


def test_candidate_integration_calls_existing_owners_without_scoring_or_signing():
    source = (ROOT / "carbon/candidates/service.py").read_text(encoding="utf-8")
    for call in (
        ".submit(",
        ".admit_fixture(",
        ".run_fixture(",
        ".complete_and_publish(",
    ):
        assert call in source
    for forbidden in (
        "ScoreEngine",
        "accepted=True",
        "eval(",
        "exec(",
        "subprocess",
        "sign(",
        "seed_pin.evaluation_binding",
    ):
        assert forbidden not in source
    for path in (ROOT / "carbon/candidates").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in (
                    "bittensor",
                    "carbon.fees.store",
                    "carbon.cards.store",
                    "carbon.seeding",
                )


def test_scientific_owners_remain_independent_of_candidate_projection():
    for directory in ("fees", "scoring", "traineval", "cards"):
        for path in (ROOT / "carbon" / directory).glob("*.py"):
            assert "carbon.candidates" not in path.read_text(encoding="utf-8")
