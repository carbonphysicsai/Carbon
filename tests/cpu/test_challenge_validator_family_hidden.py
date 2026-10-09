"""The import-only half of a family's validator (VALIDATOR-28 slice 3).

Motor's suite (`test_challenge_validator_motor_hidden.py`) is the parity
check: it imports, refuses, withdraws and scores through the shared mixin
unchanged. These tests pin motor's validator-side values, that the mixin
names its refusals by the family, that motor's implementation pin covers
the shared code, and that the mixin stays a validator module.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from carbon.challenge_validator import family_hidden
from carbon.challenge_validator import motor_hidden as hidden
from carbon.challenge_validator.family_hidden import FamilyHiddenImport
from carbon.challenge_validator.motor import MotorAdapterError


def test_motors_validator_uses_the_shared_import_with_its_own_values():
    assert issubclass(hidden.MotorHiddenAdapter, FamilyHiddenImport)
    family = hidden.MotorHiddenAdapter.hidden
    assert family.name == "motor"
    assert family.terminal == hidden.TERMINAL
    assert family.store_schema == hidden.STORE_SCHEMA
    assert family.evidence == hidden.EVIDENCE
    assert (family.window_blocks, family.window_scored) == (
        hidden.HOTKEY_WINDOW_BLOCKS,
        hidden.HOTKEY_WINDOW_SCORED,
    )
    assert family.check_document is hidden.check_document
    assert family.check_reference is hidden.check_reference


def test_an_import_only_refusal_is_named_by_the_family():
    class Toy(FamilyHiddenImport):
        hidden = dataclasses.replace(hidden.MOTOR_HIDDEN, name="toy")

    with pytest.raises(MotorAdapterError) as refused:
        Toy().open_pool()
    assert refused.value.code == "toy_hidden_import_only"
    assert Toy()._hotkey_window(725) == (720, 1080, 1)


def test_motors_implementation_pin_covers_the_shared_import(monkeypatch, tmp_path):
    before = hidden.hidden_implementation_digest()
    changed = tmp_path / "family_hidden.py"
    changed.write_text(Path(family_hidden.__file__).read_text() + "\n# changed\n")
    monkeypatch.setattr(family_hidden, "__file__", str(changed))
    assert hidden.hidden_implementation_digest() != before


def test_the_shared_import_imports_nothing_producer_side():
    tree = ast.parse(Path(family_hidden.__file__).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    producer_side = {"family_source", "motor_source", "producer", "battery_bank"}
    assert not {name.rsplit(".", 1)[-1] for name in names} & producer_side
