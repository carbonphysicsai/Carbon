"""Chain observations cannot introduce SDK or signing authority into science."""

import ast
from pathlib import Path

from carbon.chain import BittensorReader, ReadOnlyChainAdapter

ROOT = Path(__file__).resolve().parents[2]


def test_sdk_imports_remain_inside_chain():
    violations = []
    for path in (ROOT / "carbon").rglob("*.py"):
        if "chain" in path.relative_to(ROOT / "carbon").parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            if any(
                name == "bittensor" or name.startswith("bittensor.") for name in modules
            ):
                violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_public_reader_surface_has_no_mutations():
    assert {
        name for name in vars(ReadOnlyChainAdapter) if not name.startswith("_")
    } == {"observe"}
    assert {name for name in vars(BittensorReader) if not name.startswith("_")} == {
        "capture"
    }
