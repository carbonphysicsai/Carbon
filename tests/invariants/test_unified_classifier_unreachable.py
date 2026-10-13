"""The public classifier and contract factory cannot reach development compilers."""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant
ROOT = Path(__file__).resolve().parents[2]


def test_unified_public_libraries_cannot_reach_variant_compiler():
    spec = importlib.util.spec_from_file_location(
        "_unified_variant_walk",
        ROOT / "tests/invariants/test_development_variants_unreachable.py",
    )
    walk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(walk)
    surfaces = (
        "carbon/construction/unified.py",
        "carbon/battery/unified_contract.py",
        "carbon/development_ladder/unified_shadow.py",
    )
    assert not walk.reach(surfaces=surfaces)
