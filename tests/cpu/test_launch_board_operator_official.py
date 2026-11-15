"""The operator's v3 board under official-score crowns (owner 14 Nov; `crown_official`): a king crowned on his OFFICIAL
grade has no rebuild mean, so the board shows him STABLE instead of refusing ``king_unmeasured`` (the 116 Motor 1.8 board
stuck at its last pre-crown file); a version without the rule refuses exactly as before; a malformed registry refuses.
"""

# ruff: noqa: F811
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "dev"))

import launch_board_operator as operator
from test_launch_board_operator_v2 import (  # noqa: F401 - the fixtures and helpers
    COOLING,
    EXAM,
    KING,
    KING_EXACT,
    _board_bytes,
    _v2_fixture,
    door,
    frozen,
)

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import crown_official
from carbon.challenge_validator import launch_board as lb

REAL = crown_official.registered


def _registry(tmp_path, monkeypatch, versions):
    path = tmp_path / "crown_official_score.json"
    path.write_text(
        json.dumps({"schema": crown_official.SCHEMA, "versions": versions}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        crown_official,
        "registered",
        lambda challenge_id, version: REAL(challenge_id, version, path=path),
    )


def _official(tmp_path, monkeypatch, margin=0.0129):
    _registry(
        tmp_path,
        monkeypatch,
        {f"{COOLING['id']} {COOLING['version']}": {"margin": margin}},
    )


def _v3(tmp_path, door):
    config, pool = _v2_fixture(tmp_path, door)
    config["board"] = "v3"
    return config, pool


def test_an_official_score_king_with_no_rebuild_mean_is_shown_stable(
    tmp_path, door, frozen, monkeypatch
):
    _official(tmp_path, monkeypatch)
    config, _pool = _v3(tmp_path / "b", door)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE", row
    board = json.loads(_board_bytes(config, COOLING))
    assert board["schema"] == lb.SCHEMA_V3
    assert board["king"]["stability"] == "STABLE"
    assert lb.verify(board, board["validator"]["feed_key"]) == board


def test_the_official_crowns_own_record_or_an_old_unstable_one_does_not_change_it(
    tmp_path, door, frozen, monkeypatch
):
    _official(tmp_path, monkeypatch)
    config, pool = _v3(tmp_path / "b", door)
    store = PoolStore(pool)
    # an earlier seed-fragile rebuild record of the same king (before the switch) and the official crown's record
    store.record_crown_average("m-king", EXAM, {"statuses": ["OK", "FAILED_INFRA"]})
    os.chmod(pool, 0o600)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE", row
    assert json.loads(_board_bytes(config, COOLING))["king"]["stability"] == "STABLE"


def test_a_version_without_the_rule_still_refuses_an_unmeasured_king(
    tmp_path, door, frozen, monkeypatch
):
    _registry(tmp_path, monkeypatch, {"other-challenge 9.9": {"margin": 0.01}})
    config, _pool = _v3(tmp_path / "b", door)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "REFUSED" and row["code"] == "king_unmeasured"


def test_a_malformed_registry_refuses(tmp_path, door, frozen, monkeypatch):
    _registry(
        tmp_path,
        monkeypatch,
        {f"{COOLING['id']} {COOLING['version']}": {"margin": "0.0129"}},
    )
    config, _pool = _v3(tmp_path / "b", door)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "REFUSED" and row["code"] == "crown_official_invalid"


def test_the_repo_registry_names_motor_18_only():
    assert operator.official_score({"id": "electric-motor-magnetics", "version": "1.8"})
    assert not operator.official_score(COOLING)


def test_the_boards_score_to_beat_is_the_doors_for_an_official_score_version(
    tmp_path, door, frozen, monkeypatch
):
    """V2B 15 Nov: under official-score crowns the door's v2 king page (built by the receiver's own king view, with its
    `_crown_bar` and `_page_noise`) and the board carry the SAME score to beat, under the original single-grade id
    (`koth_public.TO_BEAT_RULE`: the guaranteed bound, the step-floored king total + step + margin, rounded up), never
    below the real bar (the exact official total + the margin)."""
    import types

    from carbon.challenge_validator import crown_average, direct_receiver
    from carbon.challenge_validator import koth_public as kp

    margin = 0.0129
    _official(tmp_path, monkeypatch, margin)
    monkeypatch.setattr(
        crown_official,
        "ACTIVE",
        {
            "challenge": COOLING["id"],
            "version": COOLING["version"],
            "margin": margin,
            "digest": "sha256:" + "0" * 64,
        },
    )
    monkeypatch.setattr(crown_average, "ACTIVE", None)
    config, pool = _v3(tmp_path / "b", door)
    challenge = types.SimpleNamespace(
        challenge_id=COOLING["id"], version=COOLING["version"]
    )
    view = kp.PoolKingView(
        open_store=lambda: PoolStore(pool),
        epoch_of=lambda submission_id: 12,
        exam_version_label=COOLING["exam_version_label"],
        rebuild_noise_of=lambda: direct_receiver._page_noise(challenge),
        crown_bar_of=lambda challenge_id: direct_receiver._crown_bar(
            "unused", challenge_id
        ),
    )
    status, served = kp.serve_v2(view, challenge)
    assert status == 200, served
    assert served["king"]["hotkey"] == KING and served["margin"] == margin
    assert served["to_beat_rule"] == kp.TO_BEAT_RULE  # never the averaged id
    assert served["to_beat"] >= KING_EXACT + margin - 1e-12
    door.documents[kp.PATH + COOLING["id"] + kp.V2_SUFFIX] = served
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE", row
    board = json.loads(_board_bytes(config, COOLING))
    assert board["king"]["to_beat"] == served["to_beat"]
    assert board["king"]["to_beat_rule"] == kp.TO_BEAT_RULE
    assert board["king"]["stability"] == "STABLE"
    assert lb.verify(board, board["validator"]["feed_key"]) == board
