"""Static and nominal boundaries for the B-E4 engineering harness."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from carbon.gauntlet import (
    GauntletPreregistration,
    GauntletRecord,
    GauntletStatus,
    RunIdentity,
)

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.invariant
def test_gauntlet_has_no_official_or_protected_data_dependency() -> None:
    files = tuple((ROOT / "carbon/gauntlet").glob("*.py"))
    imported = set()
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
    assert not any(
        name.startswith(
            ("carbon.generators", "carbon.evaluation.assets", "carbon.scoring")
        )
        for name in imported
    )


@pytest.mark.invariant
def test_gauntlet_records_do_not_define_a_utility_or_security_verdict() -> None:
    fields = set(GauntletRecord.__dataclass_fields__)
    assert "utility_passed" not in fields
    assert "leakage_passed" not in fields
    assert "security_qualified" not in fields
    assert "production_qualified" not in fields


@pytest.mark.invariant
def test_reserved_inputs_default_missing_and_v2_pins_are_nominal() -> None:
    preregistration = GauntletPreregistration()
    assert not preregistration.is_complete
    assert preregistration.missing_inputs
    assert "prior_pack_ref" in RunIdentity.__dataclass_fields__
    assert "test_only_authorization_ref" in RunIdentity.__dataclass_fields__
    assert "authorization_verified" not in RunIdentity.__dataclass_fields__
    assert "QUALIFYING_EXECUTION_RECORDED" not in GauntletStatus.__members__
