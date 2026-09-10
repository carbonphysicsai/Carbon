"""Operator wrappers cannot supply scientific, public-network or treasury authority."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant


def test_operator_imports_construct_no_sdk_client_wallet_or_connection():
    source = "import sys,socket;socket.create_connection=lambda *a,**k: (_ for _ in ()).throw(AssertionError());import carbon.chain.operations;assert 'bittensor' not in sys.modules"
    result = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, check=False
    )
    assert result.returncode == 0


def test_operator_has_no_dynamic_factory_acceptance_or_unchecked_chain_path():
    root = Path(__file__).parents[2]
    text = (root / "carbon/chain/operations.py").read_text(encoding="utf-8-sig")
    for forbidden in (
        "import_module",
        "set_storage",
        "submit_call",
        "eval(",
        "exec(",
        "_complete_fixture(",
    ):
        assert forbidden not in text
    assert "restored_publisher" in text and "FixtureStubProfile" in text
    store = (root / "carbon/chain/operator_store.py").read_text(encoding="utf-8-sig")
    store = ast.unparse(ast.parse(store))
    assert "source.backup(target" in store and "os.link(temp, destination)" in store
    assert "DELETE FROM" not in store and "DROP TABLE" not in store
