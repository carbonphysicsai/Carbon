"""The normal direct construction panel sends the actual user recipe through its offered session."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_direct_construction_browser_component():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = Path(__file__).with_name("direct_construction_browser_check.cjs")
    result = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "direct construction browser component passed"
