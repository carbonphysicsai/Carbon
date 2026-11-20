"""Live 116, 20 Nov 2026 14:09:50Z (rtsk_bcd73dfd): a grade that had COUNTED during a receiver stop failed in its Ladder
step, whose owner lookup opened a provider (refused while stopping), and its marker said FAILED. The Ladder's owner is
read without opening a provider first, and its own failure only names itself."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.interface import Unavailable


def _never_opens(task):
    raise Unavailable("direct_receiver_stopping")


def test_the_ladder_owner_comes_from_the_receivers_keys_then_the_ledger():
    adapter = SimpleNamespace(
        provider_for=SimpleNamespace(hotkey_of=lambda task: "5Keys"),
        ledger=SimpleNamespace(owned_outcome=lambda contract, task: "5Ledger"),
        contract_digest="sha256:" + "c" * 64,
        owner=_never_opens,
    )
    assert retention._ladder_owner(adapter, "rtsk_x") == "5Keys"
    adapter.provider_for = SimpleNamespace(hotkey_of=lambda task: None)
    assert retention._ladder_owner(adapter, "rtsk_x") == "5Ledger"


def test_a_stopping_receiver_never_fails_the_grade_in_its_ladder_step():
    adapter = SimpleNamespace(
        provider_for=SimpleNamespace(hotkey_of=lambda task: None),
        ledger=SimpleNamespace(owned_outcome=lambda contract, task: None),
        contract_digest="sha256:" + "c" * 64,
        owner=_never_opens,
    )
    state = retention._record_ladder(
        adapter, "rtsk_x", exam_key="k", exam_version="v", gates={}, graded={}
    )
    assert state == "UNAVAILABLE: direct_receiver_stopping"


def test_any_other_runtime_error_is_raised_as_before():
    def broken(task):
        raise RuntimeError("not a typed refusal")

    adapter = SimpleNamespace(
        provider_for=SimpleNamespace(hotkey_of=lambda task: None),
        ledger=SimpleNamespace(owned_outcome=lambda contract, task: None),
        contract_digest="sha256:" + "c" * 64,
        owner=broken,
    )
    with pytest.raises(RuntimeError, match="not a typed refusal"):
        retention._record_ladder(
            adapter, "rtsk_x", exam_key="k", exam_version="v", gates={}, graded={}
        )
