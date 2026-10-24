"""OWNER-PRACTICE-SHOWS-MINIMUMS-01: a practice result carries the version's registered
leg minimums beside its leg values, with the sealed grade's verdict (practice, never an
official status). Minimums come only from the registered score pack; none registered is
"NOT_YET_SET" and no verdict."""

from __future__ import annotations

import pytest
from test_practice_dual_v2 import (
    CASES,
    _power_law,
    _public,
    _rows,
    _truth_predict,
)

from carbon.challenge_registry import published_exam
from carbon.scoring import practice_dual, practice_grid

KIND = "f08"
VERSION = CASES[KIND][0]


def _doc():
    _adapter, public = _public(KIND, VERSION)
    _bank, rows, _names = _rows(KIND, VERSION)
    model = _power_law(KIND, VERSION, public)
    return practice_dual.feedback_v2(
        KIND, VERSION, _truth_predict(KIND, VERSION, rows, model)
    )


def _register(monkeypatch, **minimums):
    """Register leg minimums on the version's score pack (what a registered pack carries).
    The grid hands out a fresh versioned adapter per call, so one patched adapter is
    pinned for the practice grader."""
    adapter = practice_grid.adapter(KIND, VERSION)
    original = adapter.applied_pack

    def applied_pack(**kwargs):
        pack = original(**kwargs)
        for leg, minimum in minimums.items():
            pack["legs"][leg]["minimum"] = minimum
        return pack

    monkeypatch.setattr(adapter, "applied_pack", applied_pack)
    real = practice_grid.adapter
    monkeypatch.setattr(
        practice_grid,
        "adapter",
        lambda kind, version: (
            adapter if (kind, version) == (KIND, VERSION) else real(kind, version)
        ),
    )


def test_none_registered_is_not_yet_set_and_gives_no_verdict():
    doc = _doc()
    assert doc["eligible"] is True
    assert doc["minimums"] == {
        "source": "published_exam",
        "version": VERSION,
        "status": "NOT_YET_SET",
        "legs": {},
    }
    assert doc["status"] == "PRACTICE_SCORED" and doc["failed_legs"] == []


def test_the_not_yet_set_state_equals_the_published_exam_block():
    """The published exam says no leg minimum is registered; practice agrees."""
    block = published_exam.for_version("f08-ribbed-bracket", VERSION) or {}
    published = block.get("minimums", {"A": None, "D": None})
    assert published["A"] is None and published["D"] is None
    assert _doc()["minimums"]["legs"] == {}


def test_registered_and_met_leaves_the_status_unchanged(monkeypatch):
    base = _doc()
    _register(monkeypatch, A=0.0, D=0.0)
    doc = _doc()
    assert doc["minimums"]["status"] == "SET"
    assert doc["minimums"]["legs"] == {
        "A": {"minimum": 0.0, "value": base["accuracy"], "met": True},
        "D": {"minimum": 0.0, "value": base["design_value"], "met": True},
    }
    assert doc["status"] == base["status"] and doc["failed_legs"] == []
    assert doc["total"] == base["total"]


def test_one_leg_under_its_minimum_names_that_leg(monkeypatch):
    base = _doc()
    _register(monkeypatch, A=0.0, D=base["design_value"] + 0.01)
    doc = _doc()
    assert doc["status"] == "PRACTICE_BELOW_MINIMUM"
    assert doc["failed_legs"] == ["D"]
    assert doc["minimums"]["legs"]["A"]["met"] is True
    assert doc["minimums"]["legs"]["D"]["met"] is False
    # still a public-bank practice document with its numbers
    assert doc["bank"] == practice_dual.BANK_LABEL and doc["total"] == base["total"]


def test_equality_passes(monkeypatch):
    base = _doc()
    _register(monkeypatch, A=base["accuracy"], D=base["design_value"])
    doc = _doc()
    assert doc["status"] == "PRACTICE_SCORED" and doc["failed_legs"] == []


def test_a_gate_failure_outranks_a_minimum(monkeypatch):
    _register(monkeypatch, A=1.1, D=1.1)
    _adapter, public = _public(KIND, VERSION)
    _bank, rows, _names = _rows(KIND, VERSION)
    good = _truth_predict(KIND, VERSION, rows, _power_law(KIND, VERSION, public))

    def nonfinite(inputs):
        return [[float("nan")] * len(good(inputs)[0])] * len(inputs)

    nan = practice_dual.feedback_v2(KIND, VERSION, nonfinite)
    assert nan["eligible"] is False and nan["status"] == "GATE_FAILED"
    assert nan["failed_legs"] == []
    assert all(row["met"] is None for row in nan["minimums"]["legs"].values())


@pytest.mark.parametrize("latest", [False, True])
def test_a_below_minimum_practice_document_is_still_refused_by_ladder_and_koth(
    monkeypatch, latest
):
    from carbon.challenge_validator import ladder_store

    _register(monkeypatch, A=1.1, D=1.1)
    doc = _doc()
    assert doc["status"] == "PRACTICE_BELOW_MINIMUM"
    with pytest.raises(ladder_store.LadderStoreRefused):
        ladder_store.checked(doc, latest=latest)


def test_the_koth_comparator_refuses_a_practice_pack_with_minimums():
    from carbon.challenge_validator import koth_registry

    pack = {
        "scope": practice_dual.SCOPE,
        "pack_digest": "sha256:" + "0" * 64,
        "legs": {"A": {"minimum": 0.5}, "D": {"minimum": 0.5}},
        "value_weight": 0.5,
        "combination": "weighted_arithmetic_mean",
    }
    with pytest.raises(koth_registry.RegistryInvalid):
        koth_registry.comparator("f08-ribbed-bracket", pack, {})
    with pytest.raises(koth_registry.RegistryInvalid):
        koth_registry.comparator_for_set("f08-ribbed-bracket", [pack], [{}])


def test_no_official_status_code_is_written():
    assert _doc()["status"] not in {
        "IMPROVED",
        "NO_IMPROVEMENT",
        "GATE_FAILED_OFFICIAL",
        "NOT_SCORED",
    }
