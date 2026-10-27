"""The counted grade of a NEW submission on a SEALED/POOL pack (GPU_REBUILD_RULINGS section 11).

A sealed/pool pack's case bank is its own canonical bank, not the task's practice query, so
`--retain-task` could never match them (`evaluation_pack_registered_material_mismatch`, valV3
2026-10-27). One counted flow: retain (binds the state), reserve the exam-cap slot for the miner's
own submission, infer the retained state over the pack's bank, then the dual measurement, pool
grade and KOTH, with the slot consumed by the grade. A development pack is unchanged and a
regrade stays uncounted.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from test_exam_cap import EXAM, HOTKEY, MOTOR, Clock, _adapter, _record, make_cap

from carbon.challenge_kit import physical_pack
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.scoring import sealed_batch_source

CONTRACT = "sha256:" + "c" * 64


@pytest.fixture
def cap(tmp_path):
    return make_cap(tmp_path, Clock())


def _pack(digest):
    return SimpleNamespace(private={"case_bank": {"sha256": digest}})


def _development_digest(challenge, version):
    kit = sealed_batch_source._kit(challenge)
    bank = physical_pack.development_bank(challenge, version)
    return "sha256:" + hashlib.sha256(kit.private_roles(bank)["case_bank"]).hexdigest()


def test_a_pack_is_sealed_when_its_manifest_pins_another_bank_than_the_development_one():
    challenge, version = "electric-motor-magnetics", "1.4"
    development = _development_digest(challenge, version)
    wanted = {"challenge": challenge, "version": version}
    assert not sealed_batch_source.is_sealed(selected_pack=_pack(development), **wanted)
    assert sealed_batch_source.is_sealed(
        selected_pack=_pack("sha256:" + "9" * 64), **wanted
    )
    # A pack that pins no case bank is never read as the development pack.
    with pytest.raises(sealed_batch_source.SealedBankRefused):
        sealed_batch_source.is_sealed(
            selected_pack=SimpleNamespace(private={}), **wanted
        )
    # A Challenge with no sealed kit has no sealed pack.
    assert not sealed_batch_source.is_sealed(
        challenge="inert-dual-software-fixture",
        version="1",
        selected_pack=_pack("sha256:" + "9" * 64),
    )


def _grade_calls(monkeypatch, sealed):
    calls = {"plain": [], "counted": []}
    monkeypatch.setattr(retention, "_pack_is_sealed_bank", lambda adapter: sealed)
    monkeypatch.setattr(
        retention,
        "_retain_selected_pack_evaluation",
        lambda *args, **kwargs: calls["plain"].append((args, kwargs)) or {"plain": 1},
    )
    monkeypatch.setattr(
        retention,
        "_counted_bank_grade",
        lambda *args, **kwargs: calls["counted"].append((args, kwargs))
        or {"counted": 1},
    )
    return calls


@pytest.mark.parametrize("sealed", [False, True])
def test_the_pack_kind_from_its_manifest_chooses_the_flow(monkeypatch, sealed):
    calls = _grade_calls(monkeypatch, sealed)
    bound = {"evaluation_pack_digest": "sha256:" + "p" * 64}
    result = retention._grade_selected_pack(
        SimpleNamespace(),
        "rtsk_a",
        bound,
        {"inputs.npz": b""},
        {},
        pool_store="STORE",
        artifact_directory="A",
        entry_directory="E",
    )
    assert result == ({"counted": 1} if sealed else {"plain": 1})
    assert bool(calls["counted"]) is sealed and bool(calls["plain"]) is not sealed
    if sealed:
        ((_, kwargs),) = calls["counted"]
        assert kwargs["pool_store"] == "STORE"
        assert kwargs["artifact_directory"] == "A" and kwargs["entry_directory"] == "E"


def test_a_receiver_with_no_pack_keeps_the_plain_path(monkeypatch):
    calls = _grade_calls(monkeypatch, True)  # even a "sealed" answer is not asked
    retention._grade_selected_pack(
        SimpleNamespace(),
        "rtsk_a",
        {"evaluation_pack_digest": None},
        {},
        {},
        pool_store=None,
        artifact_directory="A",
        entry_directory="E",
    )
    assert calls["plain"] and not calls["counted"]


def _counted(adapter, submission_id, monkeypatch, regrade):
    monkeypatch.setattr(retention, "regrade_retained_entry", regrade)
    return retention._counted_bank_grade(
        adapter,
        submission_id,
        {"entry_id": "sha256:origin", "evaluation_pack_digest": "sha256:" + "p" * 64},
        pool_store="STORE",
        artifact_directory="A",
        entry_directory="E",
    )


def _rows(cap):
    with cap.ledger._db() as db:
        return db.execute(
            "SELECT submission_id, kind, state, hotkey, epoch FROM exam_graded "
            "ORDER BY id"
        ).fetchall()


def test_the_counted_grade_takes_the_slot_before_any_inference(cap, monkeypatch):
    _record(cap, CONTRACT, "rtsk_a", 360 * 5)
    _record(cap, CONTRACT, "rtsk_b", 360 * 5 + 7)  # the same 360-block epoch
    adapter = _adapter(cap, CONTRACT)
    inferred = []

    def regrade(adapter, entry_id, **kwargs):
        inferred.append((entry_id, kwargs))
        return {
            "entry_id": "sha256:bank",
            "regrade_of": entry_id,
            "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY",
            "ladder_feedback_state": "RECORDED",
            "koth_comparison": {"outcome": "X"},
            "graded_row": {"never": "kept"},
        }

    first = _counted(adapter, "rtsk_a", monkeypatch, regrade)
    ((entry_id, kwargs),) = inferred
    assert entry_id == "sha256:origin" and kwargs["counted"] is True
    assert kwargs["pool_store"] == "STORE" and "promotion" not in kwargs
    assert first["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY"
    assert first["bank_grade_entry_id"] == "sha256:bank"
    assert first["koth_comparison"] == {"outcome": "X"}
    assert "graded_row" not in first and "regrade_of" not in first
    assert (
        first["entry_id"] == "sha256:origin"
    )  # the retained origin entry stays the result
    # The slot is a GRADED one for the miner's own submission, in its signed epoch.
    assert _rows(cap) == [("rtsk_a", "GRADED", "RESERVED", HOTKEY, 5)]

    # A second submission in the same epoch is refused BEFORE any inference is spent.
    second = _counted(adapter, "rtsk_b", monkeypatch, regrade)
    assert second["private_evaluation_state"] == "UNAVAILABLE"
    assert second["private_evaluation_reason"] == "epoch_limit_reached"
    assert len(inferred) == 1
    assert [row[0] for row in _rows(cap)] == ["rtsk_a"]


def test_a_failed_bank_grade_gives_the_slot_back(cap, monkeypatch):
    _record(cap, CONTRACT, "rtsk_a", 360 * 5)
    adapter = _adapter(cap, CONTRACT)

    def regrade(*_args, **_kwargs):
        raise retention.RetentionUnavailable("regrade_inference_infra")

    with pytest.raises(retention.RetentionUnavailable, match="regrade_inference_infra"):
        _counted(adapter, "rtsk_a", monkeypatch, regrade)
    assert _rows(cap) == [("rtsk_a", "GRADED", "RELEASED", HOTKEY, 5)]
    # The slot is free again: the same submission can be graded once the cause is gone.
    graded = _counted(
        adapter, "rtsk_a", monkeypatch, lambda *a, **k: {"entry_id": "sha256:bank"}
    )
    assert graded["bank_grade_entry_id"] == "sha256:bank"
    assert _rows(cap)[0][2] == "RESERVED"


def test_a_counted_regrade_object_is_graded_under_the_miners_own_submission(cap):
    """The retention core keys the slot by the ORIGIN submission and its signed block;
    an uncounted regrade keeps its own identity and bypasses the cap."""
    _record(cap, CONTRACT, "rtsk_a", 360 * 5)
    adapter = _adapter(cap, CONTRACT)
    result = {"evaluation_pack_digest": "sha256:" + "p" * 64}
    evidence = {"inference_operation": "op", "inference_image_id": "sha256:" + "i" * 64}

    def run(regrade):
        return retention._retain_selected_pack_evaluation(
            adapter, "rtsk_regrade", result, {"inputs.npz": b""}, evidence, regrade
        )

    counted = retention._Regrade(
        HOTKEY, None, "rtsk_a", "sha256:origin", None, False, True
    )
    # The fixture pack cannot be graded, so the evaluation is unavailable and its slot returned;
    # what this pins is WHOSE slot it was.
    assert run(counted)["private_evaluation_state"] == "UNAVAILABLE"
    assert _rows(cap) == [("rtsk_a", "GRADED", "RELEASED", HOTKEY, 5)]

    plain = retention._Regrade(
        HOTKEY, None, "rtsk_a", "sha256:origin", None, False, False
    )
    assert run(plain)["private_evaluation_state"] == "UNAVAILABLE"
    assert _rows(cap)[1] == ("rtsk_regrade", "REGRADE", "RELEASED", HOTKEY, 0)


def test_an_exhausted_allowance_is_refused_before_inference_for_the_counted_flow(
    cap, monkeypatch
):
    """The same cap that refuses an ordinary retention refuses the counted flow."""
    first = (HOTKEY, MOTOR[0], MOTOR[1], EXAM)
    cap.reserve(
        hotkey=first[0],
        challenge_id=first[1],
        challenge_version=first[2],
        exam_key=first[3],
        submission_id="rtsk_prior",
        block=360 * 5,
    )
    _record(cap, CONTRACT, "rtsk_a", 360 * 5)
    adapter = _adapter(cap, CONTRACT)
    result = _counted(adapter, "rtsk_a", monkeypatch, pytest.fail)
    assert result["private_evaluation_reason"] == "epoch_limit_reached"
