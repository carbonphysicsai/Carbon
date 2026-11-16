"""The board names the bar's rule as it decides (owner 15 Nov, via the Lead): for a version that registers official-score
crowns, a door king page still under the averaged id is shown under the single-grade id, with the door's own score to beat
unchanged; any other version, and any other id, is passed through as it is."""

# ruff: noqa: F811
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "dev"))

import launch_board_operator as operator
from test_launch_board_operator_v2 import (  # noqa: F401 - the fixtures and helpers
    COOLING,
    KING,
    KING_EXACT,
    _board_bytes,
    _v2_fixture,
    door,
    frozen,
)

from carbon.challenge_validator import crown_official, koth_registry
from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import launch_board as lb
from carbon.scoring import grade_feedback as gf

REAL = crown_official.registered
MARGIN = 0.0129


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


def _averaged_king():
    """A door king page as a receiver before the official bar's id serves it: the averaged id over the official bar."""
    noise = {"value": MARGIN, "measurement_digest": "sha256:" + "0" * 64}
    return kp.document_v2(
        challenge_id=COOLING["id"],
        challenge_version=COOLING["version"],
        exam_version_label=COOLING["exam_version_label"],
        king={"hotkey": KING, "total": KING_EXACT, "since_epoch": 12},
        rebuild_noise=noise,
        baseline_total=None,
        crown_bar={"base": KING_EXACT, "margin": MARGIN},
    )


def _run(tmp_path, door, king):
    config, _pool = _v2_fixture(tmp_path / "b", door, king=king)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE", row
    board = json.loads(_board_bytes(config, COOLING))
    assert lb.verify(board, board["validator"]["feed_key"]) == board
    return board


def test_an_official_score_board_names_the_single_grade_rule_with_the_doors_number(
    tmp_path, door, frozen, monkeypatch
):
    _registry(
        tmp_path,
        monkeypatch,
        {f"{COOLING['id']} {COOLING['version']}": {"margin": MARGIN}},
    )
    served = _averaged_king()
    assert served["to_beat_rule"] == kp.TO_BEAT_RULE_AVERAGED
    board = _run(tmp_path, door, served)
    # the door's number is the floored bound, so it is named by the floored single-grade id, never the 16 Nov
    # `king_plus_margin` id (the exact total + margin), which is not how that number was made
    assert board["king"]["to_beat_rule"] == kp.TO_BEAT_RULE_FLOOR
    assert (
        board["king"]["to_beat"] == served["to_beat"]
    )  # the door's number, not recomputed
    # for this rule both ids give the same guaranteed bound
    # (the v2 page shows the king's total to 3 places since 16 Nov; the floored bound uses his step-floored total)
    floored = gf.floor_to_step(KING_EXACT, MARGIN)
    assert kp.to_beat_v2(floored, MARGIN) == served["to_beat"]


def test_any_other_version_keeps_the_doors_id(tmp_path, door, frozen, monkeypatch):
    _registry(tmp_path, monkeypatch, {"other-challenge 9.9": {"margin": MARGIN}})
    served = _averaged_king()
    board = _run(tmp_path, door, served)
    assert board["king"]["to_beat_rule"] == kp.TO_BEAT_RULE_AVERAGED
    assert board["king"]["to_beat"] == served["to_beat"]


def test_a_single_grade_door_page_is_passed_through(
    tmp_path, door, frozen, monkeypatch
):
    _registry(
        tmp_path,
        monkeypatch,
        {f"{COOLING['id']} {COOLING['version']}": {"margin": MARGIN}},
    )
    served = kp.document_v2(
        challenge_id=COOLING["id"],
        challenge_version=COOLING["version"],
        exam_version_label=COOLING["exam_version_label"],
        king={"hotkey": KING, "total": KING_EXACT, "since_epoch": 12},
        rebuild_noise=koth_registry.rebuild_noise(COOLING["id"]),
        baseline_total=None,
    )
    assert operator.official_rule(COOLING, served) is served
    board = _run(tmp_path, door, served)
    assert board["king"]["to_beat_rule"] == kp.TO_BEAT_RULE
