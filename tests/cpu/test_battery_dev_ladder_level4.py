"""The development ladder's Level 4 slot (VALIDATOR-25 slice 4).

OWNER-LEVEL4-TESTNET-RUNS-01: Level 4 runs on testnet through the ladder only.
The staging envelope travels as signed `battery_level4_part` calls (one signed
message is capped at 64 KiB), held owner-only by submission digest; a
`battery_submit` naming an incomplete envelope is answered
`level4_envelope_incomplete` and never counted; the ladder's compiler admits a
Level 4 variant only through the Level 4 checks over the assembled envelope,
and refuses by code while those checks are not available.
"""

from __future__ import annotations

import base64
import math
from types import SimpleNamespace

import pytest

from carbon.battery import intake as ib
from carbon.battery.level4_parts import (
    MAX_PARTS,
    PART_BYTES,
    Level4Parts,
    PartRefused,
)

MINER_C = "5E49MhzFLBv35AbSPgtwrutCd6yvDm6GK9EC5ocmJ3Czb48N"
OTHER = "5DWznJMnCeoevFSwsck7LXdYBWAbiw1G1qrxnghqSHqQj2qr"
SUBMISSION = "sha256:" + "ab" * 32


@pytest.fixture
def parts(tmp_path):
    return Level4Parts(tmp_path / "parts", {MINER_C})


def test_the_part_bounds_cover_the_owners_largest_submission():
    from carbon.level4.intake import BOUNDS

    envelope = 4 * (BOUNDS["submission_bytes"] + BOUNDS["manifest_bytes"]) / 3
    assert math.ceil(envelope / PART_BYTES) < MAX_PARTS
    # One part, base64-encoded with its fields, fits a signed message.
    from carbon.transport.models import MAX_BODY

    assert 4 * PART_BYTES / 3 + 2048 < MAX_BODY


def test_parts_are_idempotent_and_assemble_in_order(parts):
    assert parts.envelope(SUBMISSION) is None
    parts.put(MINER_C, SUBMISSION, 1, 2, b"world")
    assert not parts.complete(SUBMISSION)
    held = parts.put(MINER_C, SUBMISSION, 0, 2, b"hello ")
    assert held == {"held": [0, 1], "parts": 2}
    assert parts.put(MINER_C, SUBMISSION, 0, 2, b"hello ") == held  # a resend
    assert parts.envelope(SUBMISSION) == b"hello world"


@pytest.mark.parametrize(
    ("args", "code"),
    [
        ((OTHER, SUBMISSION, 0, 1, b"x"), "ladder_hotkey_not_listed"),
        ((MINER_C, "ab" * 32, 0, 1, b"x"), "level4_part_malformed"),
        ((MINER_C, SUBMISSION, 1, 1, b"x"), "level4_part_malformed"),
        ((MINER_C, SUBMISSION, 0, MAX_PARTS + 1, b"x"), "level4_part_malformed"),
        ((MINER_C, SUBMISSION, 0, 1, b"x" * (PART_BYTES + 1)), "level4_part_malformed"),
    ],
)
def test_a_malformed_or_foreign_part_is_refused(parts, args, code):
    with pytest.raises(PartRefused) as refused:
        parts.put(*args)
    assert refused.value.code == code


def test_other_bytes_or_another_count_are_refused(parts):
    parts.put(MINER_C, SUBMISSION, 0, 2, b"a")
    for args, code in (
        ((0, 2, b"b"), "level4_part_conflict"),
        ((1, 3, b"c"), "level4_parts_mismatch"),
    ):
        with pytest.raises(PartRefused) as refused:
            parts.put(MINER_C, SUBMISSION, *args)
        assert refused.value.code == code


def intake_with(parts):
    intake = object.__new__(ib.BatteryIntake)
    intake.level4_parts = parts
    return intake


def test_the_intake_holds_parts_and_answers_which_it_holds(parts):
    intake = intake_with(parts)
    data = base64.b64encode(b"envelope").decode()
    answer = intake._level4(
        MINER_C,
        "battery_level4_part",
        {"submission": SUBMISSION, "part": 0, "parts": 1, "data": data},
    )
    assert answer.status == 200 and answer.body["held"] == [0]
    status = intake._level4(
        MINER_C, "battery_level4_status", {"submission": SUBMISSION}
    )
    assert status.body == {"submission": SUBMISSION, "held": [0], "parts": 1}
    conflict = intake._level4(
        MINER_C,
        "battery_level4_part",
        {"submission": SUBMISSION, "part": 0, "parts": 1, "data": "eA=="},
    )
    assert (conflict.status, conflict.body) == (
        409,
        {"refused": "level4_part_conflict"},
    )
    assert intake_with(None)._level4(MINER_C, "battery_level4_status", {}).body == {
        "refused": "level4_not_served"
    }


def test_a_submit_with_an_incomplete_envelope_is_answered_never_counted(parts):
    intake = intake_with(parts)
    strategy = {"parameters": {"composition_graphs": SUBMISSION}}
    level4 = SimpleNamespace(strategy=strategy)
    assert intake._level4_incomplete(level4).body == {
        "refused": "level4_envelope_incomplete"
    }
    parts.put(MINER_C, SUBMISSION, 0, 1, b"envelope")
    assert intake._level4_incomplete(level4) is None
    assert (
        intake._level4_incomplete(SimpleNamespace(strategy={"parameters": {}})) is None
    )
    assert intake_with(None)._level4_incomplete(level4) is None


def test_the_compiler_refuses_level4_until_its_checks_exist(parts, monkeypatch):
    from carbon.battery import level4
    from carbon.development_ladder import operate
    from carbon.reconstruction import development_variants as dv

    variant = SimpleNamespace(level=4, widened=())
    monkeypatch.setattr(dv, "registered", lambda digest: variant)
    monkeypatch.setattr(dv, "compile_development", lambda s, v: "compiled")
    strategy = {"parameters": {"composition_graphs": SUBMISSION}}
    monkeypatch.delattr(level4, "admit_envelope", raising=False)
    with pytest.raises(operate.LadderRefused) as refused:
        operate.compile_variant(strategy, "d", parts)
    assert refused.value.code == "ladder_level_4_checks_unavailable"
    seen = []
    monkeypatch.setattr(
        level4,
        "admit_envelope",
        lambda s, envelope, loss_override: seen.append((envelope, loss_override)),
        raising=False,
    )
    with pytest.raises(operate.LadderRefused) as refused:
        operate.compile_variant(strategy, "d", parts)
    assert refused.value.code == "level4_envelope_incomplete"
    parts.put(MINER_C, SUBMISSION, 0, 1, b"envelope")
    assert operate.compile_variant(strategy, "d", parts) == "compiled"
    assert seen == [(b"envelope", None)]
