"""Transport may authenticate identity but cannot import evaluation authority."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant
ROOT = Path(__file__).resolve().parents[2]


def test_transport_does_not_import_evaluator_or_sdk():
    forbidden = (
        "bittensor",
        "carbon.scoring",
        "carbon.evaluation",
        "carbon.traineval",
        "carbon.cards.store",
        "carbon.fees.store",
        "carbon.seeding",
    )
    for path in (ROOT / "carbon/transport").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(
                name == prefix or name.startswith(prefix + ".")
                for name in names
                for prefix in forbidden
            )


def test_scientific_owners_do_not_depend_on_transport():
    for directory in ("scoring", "evaluation", "traineval", "cards", "fees"):
        for path in (ROOT / "carbon" / directory).glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "carbon.transport" not in source
