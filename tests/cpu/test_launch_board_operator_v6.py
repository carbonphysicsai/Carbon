"""The operator's v6 run (owner 16 Nov: totals to 3 decimals, the posted bar = the crown rule's own).

Claims: ``"board": "v6"`` is the v5 run built from the receiver's v3 king page (``/carbon/v1/koth/<id>/v3``, the only
king route it asks): the king and each ladder row whose exact total is its own show it at 3 places (half up), the crown
changes too, under the v6 schema and domain, and the door serves the written board; a receiver that serves v1 but no v3
(a door before 16 Nov) is refused, never published as kingless; the v5 run is unchanged (it still asks v2).
"""

# ruff: noqa: F811
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "dev"))

import launch_board_operator as operator
from test_launch_board_operator_official import _official
from test_launch_board_operator_v2 import (  # noqa: F401 - the fixtures and helpers
    COOLING,
    KING,
    KING_EXACT,
    OTHER,
    OTHER_EXACT,
    _board_bytes,
    _v2_fixture,
    door,
    frozen,
)

from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import koth_registry
from carbon.challenge_validator import launch_board as lb
from carbon.challenge_validator import launch_board_file as lbf


def _v3_king():
    return kp.document_v3(
        challenge_id=COOLING["id"],
        challenge_version=COOLING["version"],
        exam_version_label=COOLING["exam_version_label"],
        king={"hotkey": KING, "total": KING_EXACT, "since_epoch": 12},
        rebuild_noise=koth_registry.rebuild_noise(COOLING["id"]),
        baseline_total=None,
    )


def _v6(tmp_path, door, monkeypatch):
    _official(tmp_path, monkeypatch)
    config, pool = _v2_fixture(tmp_path / "b", door)
    config["board"] = "v6"
    door.documents.pop(kp.PATH + COOLING["id"] + kp.V2_SUFFIX)
    door.documents[kp.PATH + COOLING["id"] + kp.V3_SUFFIX] = _v3_king()
    return config, pool


def test_the_v6_run_shows_three_places_from_the_v3_king_page(
    tmp_path, door, frozen, monkeypatch
):
    config, _ = _v6(tmp_path, door, monkeypatch)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE" and row["board"] == "v6", row
    assert door.asked == [kp.PATH + COOLING["id"] + kp.V3_SUFFIX]
    board = json.loads(_board_bytes(config, COOLING))
    assert board["schema"] == lb.SCHEMA_V6
    assert lb.verify(board, board["validator"]["feed_key"]) == board
    assert board["king"]["to_beat_rule"] == kp.TO_BEAT_RULE_EXACT
    assert board["king"]["king"]["total"] == kp.shown_total(KING_EXACT)
    rows = {r["hotkey"]: (r["rank"], r["total"]) for r in board["ladder"]}
    assert rows == {
        KING: (1, kp.shown_total(KING_EXACT)),
        OTHER: (2, kp.shown_total(OTHER_EXACT)),
    }
    assert [c["total"] for c in board["crown_changes"]] == [
        kp.shown_total(KING_EXACT),
        kp.shown_total(OTHER_EXACT),
    ]
    text = _board_bytes(config, COOLING).decode()
    assert repr(KING_EXACT) not in text and repr(OTHER_EXACT) not in text
    # the door serves what the operator wrote
    path = Path(config["out"]) / (operator.slug_of(COOLING) + ".json")
    assert lbf.read_board(path, COOLING["id"]) == board


def test_a_door_without_v3_is_refused_never_shown_kingless(
    tmp_path, door, frozen, monkeypatch
):
    config, _ = _v6(tmp_path, door, monkeypatch)
    door.documents.pop(kp.PATH + COOLING["id"] + kp.V3_SUFFIX)
    door.documents[kp.PATH + COOLING["id"]] = kp.document(
        challenge_id=COOLING["id"],
        challenge_version=COOLING["version"],
        exam_version_label=COOLING["exam_version_label"],
        king={"hotkey": KING, "total": KING_EXACT, "since_epoch": 12},
        rebuild_noise=koth_registry.rebuild_noise(COOLING["id"]),
        baseline_total=None,
    )
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "REFUSED" and row["code"] == "receiver_no_v3", row
    assert not (Path(config["out"]) / (operator.slug_of(COOLING) + ".json")).exists()


def test_the_v5_run_still_asks_v2(tmp_path, door, frozen, monkeypatch):
    _official(tmp_path, monkeypatch)
    config, _ = _v2_fixture(tmp_path / "b", door)
    config["board"] = "v5"
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE" and row["board"] == "v5", row
    assert door.asked == [kp.PATH + COOLING["id"] + kp.V2_SUFFIX]
    board = json.loads(_board_bytes(config, COOLING))
    assert board["schema"] == lb.SCHEMA_V5
    assert board["king"]["to_beat_rule"] == kp.TO_BEAT_RULE
