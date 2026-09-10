"""Publication must retain explicit local authority and the SDK's signing policy."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant
ROOT = Path(__file__).resolve().parents[2]


def test_publication_imports_do_not_construct_sdk_clients_or_access_keys():
    program = """
import socket,sys
def forbidden(*args,**kwargs): raise AssertionError('import attempted network')
socket.create_connection=forbidden
import carbon.chain.publisher,carbon.chain.sdk_weights
assert 'bittensor' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_sdk_policy_execute_and_no_retry_remain_the_publication_path():
    source = (ROOT / "carbon/chain/sdk_weights.py").read_text(encoding="utf-8")
    assert "await client.execute(" in source and "retries=0" in source
    assert "allowed_netuids=[self.context.netuid]" in source
    assert "max_spend_tao=0" in source
    assert "allow_raw_calls=True" not in source
    assert "fallback_endpoints=[]" in source and "retry_forever=False" in source
    assert source.index("await check_integers(uids, values, preflight)") < source.index(
        "result = await _build_timelocked("
    )
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec")


def test_scientific_and_disclosure_owners_do_not_consume_publication_authority():
    for directory in ("scoring", "traineval", "cards", "fees"):
        for path in (ROOT / "carbon" / directory).glob("*.py"):
            assert "carbon.chain" not in path.read_text(encoding="utf-8")
