from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_practice_has_no_official_score_card_submission_or_network_dependency():
    imports = set()
    for path in (ROOT / "carbon" / "practice").glob("*.py"):
        imports.update(_imports(path))
    forbidden = (
        "carbon.scoring",
        "carbon.cards",
        "carbon.fees",
        "carbon.mcp",
        "carbon.leaderboard",
        "carbon.chain",
        "carbon.traineval",
    )
    assert not any(
        module == prefix or module.startswith(prefix + ".")
        for module in imports
        for prefix in forbidden
    )


def test_practice_does_not_redefine_shared_wire_records():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "carbon" / "practice").glob("*.py")
    )
    assert "@wire_record" not in text
    assert "ScoreInput" not in text
    assert "ScoreEngine" not in text
    assert "FixtureOfficialContext" not in text
    assert "OfficialContext" not in text
