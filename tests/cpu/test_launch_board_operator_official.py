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
