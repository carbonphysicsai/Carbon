"""Efficiency ledger row 8 (live 116, 20 Nov 2026): ~11 built tasks at any time (89% of the day) had an unreadable
allowance group, so each graded ALONE (`auto_grade._claim_scan`: ``group_unknown``). The door's own ledger records the
one authenticated owner of every submitted task (`AttemptLedger.owned_outcome`); the claim's group read now falls back
to it before opening a provider. Ambiguous or absent ownership stays unknown, as before. Synthetic ids only.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, exam_cap
from carbon.challenge_validator.interface import Unavailable

A, B, C = ("rtsk_" + c * 64 for c in "abc")
CONTRACT = "sha256:" + "c" * 64


@pytest.fixture(autouse=True)
def _per_hotkey(monkeypatch):
    monkeypatch.setattr(
        exam_cap, "GROUPING", None
    )  # the live door: no allowance_groups block


def _grader(owned, *, provider=None):
    def owner(task):
        raise Unavailable("direct_provider_owner_set_aside")

    asked = []

    def owned_outcome(contract, task):
        asked.append(contract)
        value = owned.get(task)
        if isinstance(value, BaseException):
            raise value
        return value

    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(
            contract_digest=CONTRACT,
            ledger=SimpleNamespace(owned_outcome=owned_outcome),
            owner=owner,
            provider_for=provider,
        )
    )
    return grader, asked


def test_a_task_whose_provider_view_is_silent_takes_its_group_from_the_ledger():
    grader, asked = _grader({A: "5HotkeyA"})
    assert grader._allowance_group(A) == "h:5HotkeyA"
    assert asked == [CONTRACT]  # read under this door's contract only


def test_unknown_or_ambiguous_ledger_ownership_stays_unknown():
    # owned_outcome answers None for no owner AND for two owners (fails closed); a raising ledger is doubt
    grader, _ = _grader({B: None, C: OSError("locked")})
    assert grader._allowance_group(B) is None
    assert grader._allowance_group(C) is None


def test_the_providers_own_key_view_still_answers_first():
    provider = SimpleNamespace(hotkey_of=lambda task: "5FromProvider")
    grader, asked = _grader({A: "5HotkeyA"}, provider=provider)
    assert grader._allowance_group(A) == "h:5FromProvider"
    assert asked == []  # the ledger is not read when the providers know the owner


def test_the_owner_step_is_unchanged_a_set_aside_owner_is_still_unreadable():
    # the ledger fallback orders the claim only: `_owner_of` (who may take a round) still opens nothing new
    grader, _ = _grader({A: "5HotkeyA"})
    assert grader._owner_of(A) is None
