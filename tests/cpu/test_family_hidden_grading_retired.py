"""Every hidden family adapter refuses a new graded run (OWNER-FULL-EXAM-BANK-01,
stage 1 conformance).

The windowed hidden path may not produce a new graded score; a submission already
graded keeps its stored outcome. This walks every `FamilyHiddenImport` subclass the
validator package defines, so a family added later without the guard fails here."""

from __future__ import annotations

import pkgutil
from types import SimpleNamespace

import pytest

import carbon.challenge_validator as package
from carbon.challenge_validator import (  # noqa: F401  (imported for their subclasses)
    cooling_hidden,
    f02_hidden,
    f08_hidden,
    family_hidden,
    motor_hidden,
)
from carbon.challenge_validator.interface import Admitted, Unavailable


def _subclasses():
    found, queue = [], list(family_hidden.FamilyHiddenImport.__subclasses__())
    while queue:
        cls = queue.pop()
        found.append(cls)
        queue.extend(cls.__subclasses__())
    return sorted(found, key=lambda cls: cls.__name__)


FAMILIES = _subclasses()


IMPORTED = {
    "cooling_hidden",
    "f02_hidden",
    "f08_hidden",
    "family_hidden",
    "motor_hidden",
}


def test_every_hidden_family_module_is_imported_above():
    """A family module added later must be added to the static imports, or this
    walk would not see its adapter."""
    modules = {
        info.name
        for info in pkgutil.iter_modules(package.__path__)
        if info.name.endswith("_hidden")
    }
    assert modules == IMPORTED


def test_the_conformance_walk_finds_the_hidden_family_adapters():
    assert FAMILIES, "no FamilyHiddenImport subclass found"
    assert "MotorHiddenAdapter" in {cls.__name__ for cls in FAMILIES}


@pytest.mark.parametrize("cls", FAMILIES, ids=lambda cls: cls.__name__)
def test_a_family_adapter_replays_history_and_refuses_new_grading(cls):
    assert cls.GRADING_RETIRED is True
    adapter = object.__new__(cls)
    submission = Admitted(
        hotkey="hk",
        receipt={"sequence": 1, "digest": "d" * 64, "block": 1200},
        challenge_id="c",
        challenge_version="1.0",
        strategy={},
        contract_digest="sha256:" + "a" * 64,
    )
    stored = {}
    adapter.store = SimpleNamespace(
        submission=lambda submission_id: stored.get(submission_id)
    )
    adapter._submission_id = lambda item: "sub-1"
    # A new submission: refused with the typed code.
    with pytest.raises(Unavailable) as retired:
        adapter.evaluate(submission)
    assert retired.value.code == cls.RETIRED == "windowed_grading_retired"
    # One already graded here: its stored outcome replays.
    stored["sub-1"] = {"outcome": {"state": "SCORED"}}
    assert adapter.evaluate(submission) == {"state": "SCORED"}
