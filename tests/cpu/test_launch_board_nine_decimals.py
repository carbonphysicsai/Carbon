"""The launch board carries at most 9 decimals (the dashboard reader's limit), rounded so the page is never kinder.

Claims, with the REAL registered margins of the four launch Challenges: the producer rounds the margin and the score to
beat UP, the baseline and every total DOWN, to 9 decimals; a board with an unrounded value is refused by the producer's
own check, by the dashboard's reader and by the receiver's door; a real-shape board passes the producer check, the
dashboard `project` and the door's `read_board`; and the door's Ladder-step check is consistent with the rounding (it
allows exactly the 9-decimal floor of a step multiple, and nothing finer)."""

from __future__ import annotations

import datetime
import json
import os
from decimal import Decimal

import pytest

from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import koth_registry
from carbon.challenge_validator import launch_board as lb
from carbon.challenge_validator import launch_board_file as lbf
from carbon.challenge_validator.interface import digest
from carbon.dashboard import feed, launch
from carbon.scoring import grade_feedback as gf

KING = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
OTHER = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"
NOW = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)
#: Each launch Challenge's registered rebuild noise (`koth_rebuild_noise.json`) and a baseline total.
REAL = {
    "f08-ribbed-bracket": ("1.7", 0.006062541759314569, 0.4265294),
    "electric-motor-magnetics": ("1.5", 0.007923678234807158, 0.26),
    "f02": ("2.5", 0.04726369864563663, 0.3665),
    "chip-cold-plate": ("1.6", 0.01570813655321609, 0.37),
}
UNIT = Decimal(1).scaleb(-9)


@pytest.fixture(autouse=True)
def registered(monkeypatch):
    """The receiver's own registry holds exactly the real noise of each Challenge."""
    monkeypatch.setattr(
        koth_registry,
        "rebuild_noise",
        lambda challenge_id, **_: {
            "value": REAL[challenge_id][1],
            "measurement_digest": digest("noise"),
        },
    )


def _document(challenge, king_total=0.55, king=True):
    version, noise, baseline = REAL[challenge]
    return kp.document(
        challenge_id=challenge,
        challenge_version=version,
        exam_version_label="exam-1",
        king=(
            {"hotkey": KING, "total": king_total, "since_epoch": 7} if king else None
        ),
        rebuild_noise={"value": noise, "measurement_digest": digest("noise")},
        baseline_total=baseline,
    )


def _rows(challenge, king_total=0.55):
    stepped = gf.floor_to_step(king_total, REAL[challenge][1])
    scored = {"status": "IMPROVED", "gate_names": []}
    failed = {"status": "GATE_FAILED", "gate_names": ["native_motor_valid"]}
    return [(KING, {"total": stepped}, scored), (OTHER, None, failed)]


def _board(challenge, signer, king_total=0.55, king=True):
    return lb.build(
        king_document=_document(challenge, king_total=king_total, king=king),
        rows=_rows(challenge, king_total),
        network="testnet",
        key=signer,
        version=4,
        now=NOW,
    )


def _signer():
    return lb.LaunchBoardKey(os.urandom(32))


def _unsigned(board):
    return json.loads(json.dumps({k: v for k, v in board.items() if k != "signature"}))


def _shown(board):
    out = [row["total"] for row in board["ladder"] if row["total"] is not None]
    king = board["king"]
    out += [
        king[k] for k in ("margin", "to_beat", "baseline_total") if king[k] is not None
    ]
    if king["king"] is not None:
        out.append(king["king"]["total"])
    return out


def _write(tmp_path, name, board):
    path = tmp_path / name
    path.write_text(json.dumps(board), encoding="utf-8")
    return path


def test_the_raw_koth_document_really_is_unrounded():
    # the premise: today's documents carry 17-digit floats the dashboard refuses
    raw = _document("electric-motor-magnetics", king=False)
    assert not lb.on_nine(raw["margin"]) and not lb.on_nine(raw["to_beat"])
    with pytest.raises(launch.LaunchRefused, match="total_unrounded"):
        launch._digits([raw["margin"], raw["to_beat"]])


@pytest.mark.parametrize("challenge", sorted(REAL))
@pytest.mark.parametrize("king", [True, False])
def test_a_real_shape_board_passes_the_producer_the_dashboard_and_the_door(
    tmp_path, challenge, king
):
    signer = _signer()
    board = _board(challenge, signer, king=king)
    assert lb.check(board) == board
    assert all(lb.on_nine(value) for value in _shown(board))
    # the dashboard's own reader
    projected = launch.project(board, feed.Trust(keys=frozenset({signer.public_key})))
    assert projected["values"]["digits"] <= 9
    # the receiver's door
    assert lbf.read_board(_write(tmp_path, "b.json", board), challenge) == board


@pytest.mark.parametrize("challenge", sorted(REAL))
@pytest.mark.parametrize("king", [True, False])
def test_the_page_is_never_kinder_than_the_truth(challenge, king):
    raw = _document(challenge, king=king)
    shown = _board(challenge, _signer(), king=king)["king"]
    assert Decimal(repr(shown["margin"])) >= Decimal(repr(raw["margin"]))
    assert Decimal(repr(shown["to_beat"])) >= Decimal(repr(raw["to_beat"]))
    assert Decimal(repr(shown["margin"])) - Decimal(repr(raw["margin"])) < UNIT
    assert Decimal(repr(shown["to_beat"])) - Decimal(repr(raw["to_beat"])) < UNIT
    if raw["baseline_total"] is not None:
        assert Decimal(repr(shown["baseline_total"])) <= Decimal(
            repr(raw["baseline_total"])
        )
    if raw["king"] is not None:
        assert Decimal(repr(shown["king"]["total"])) <= Decimal(
            repr(raw["king"]["total"])
        )
        assert (
            Decimal(repr(raw["king"]["total"])) - Decimal(repr(shown["king"]["total"]))
            < UNIT
        )


def test_the_four_real_margins_round_up_exactly_as_expected():
    expected = {
        "f08-ribbed-bracket": 0.006062542,
        "electric-motor-magnetics": 0.007923679,
        "f02": 0.047263699,
        "chip-cold-plate": 0.015708137,
    }
    for challenge, margin in expected.items():
        assert lb.ceil9(REAL[challenge][1]) == margin
        assert lb.floor9(REAL[challenge][1]) == pytest.approx(margin - 1e-9, abs=1e-12)


def test_rounding_is_exact_and_idempotent():
    assert lb.ceil9(0.1) == 0.1 and lb.floor9(0.1) == 0.1
    assert lb.ceil9(0.1000000001) == 0.100000001
    assert lb.floor9(0.1999999999) == 0.199999999
    for value in (0.007923678234807158, 0.26792367823480717, 0.5, 1.0, 0.0):
        assert lb.floor9(lb.floor9(value)) == lb.floor9(value)
        assert lb.ceil9(lb.ceil9(value)) == lb.ceil9(value)
        assert lb.on_nine(lb.floor9(value)) and lb.on_nine(lb.ceil9(value))
    assert lb.ceil9(1.0) == 1.0  # never above 1


@pytest.mark.parametrize("where", ["margin", "to_beat", "baseline_total"])
def test_an_unrounded_bar_value_is_refused_by_all_three(tmp_path, where):
    signer = _signer()
    board = _unsigned(_board("f02", signer))
    board["king"][where] = 0.04726369864563663
    if where == "baseline_total":
        board["king"]["king"] = None
    board["signature"] = signer.sign(board)
    with pytest.raises(lb.BoardRefused):
        lb.check(board)
    with pytest.raises(launch.LaunchRefused):
        launch.project(board, feed.Trust(keys=frozenset({signer.public_key})))
    assert lbf.read_board(_write(tmp_path, "b.json", board), "f02") is None


@pytest.mark.parametrize("where", ["ladder", "king"])
def test_an_unrounded_total_is_refused_by_all_three(tmp_path, where):
    signer = _signer()
    board = _unsigned(_board("f02", signer))
    if where == "ladder":
        board["ladder"][0]["total"] = 0.4266192684736831
    else:
        board["king"]["king"]["total"] = 0.4266192684736831
    board["signature"] = signer.sign(board)
    with pytest.raises(lb.BoardRefused):
        lb.check(board)
    with pytest.raises(launch.LaunchRefused):
        launch.project(board, feed.Trust(keys=frozenset({signer.public_key})))
    assert lbf.read_board(_write(tmp_path, "b.json", board), "f02") is None


def test_the_doors_step_check_allows_exactly_the_nine_decimal_floor_of_a_step_multiple(
    tmp_path,
):
    signer = _signer()
    noise = REAL["f02"][1]
    grid = [gf.floor_to_step(0.1 + 0.047 * k, noise) for k in range(1, 9)]
    for g in grid:
        # a graded total just above the multiple: the Ladder floor lands exactly on it
        board = _board("f02", signer, king_total=g + 1e-6)
        assert board["king"]["king"]["total"] == lb.floor9(g)
        assert lbf.read_board(_write(tmp_path, "ok.json", board), "f02") is not None
    # a hair above or below the floored multiple, or a real step off the grid, is not on the grid
    base = lb.floor9(grid[2])
    for off in (1e-9, -1e-9, 1e-6, 0.01):
        shifted = round(base + off, 9)
        board = _unsigned(_board("f02", signer, king_total=grid[2] + 1e-6))
        board["king"]["king"]["total"] = shifted
        board["ladder"][0]["total"] = shifted
        board["signature"] = signer.sign(board)
        assert lbf.read_board(_write(tmp_path, "off.json", board), "f02") is None, off


def test_a_board_with_no_registered_noise_uses_the_eta_grid(tmp_path, monkeypatch):
    monkeypatch.setattr(koth_registry, "rebuild_noise", lambda challenge_id, **_: None)
    signer = _signer()
    board = lb.build(
        king_document={
            "schema": "carbon.koth.public.v1",
            "challenge_id": "f02",
            "challenge_version": "2.5",
            "exam_version_label": "exam-1",
            "king": {"hotkey": KING, "total": 0.64, "since_epoch": 1},
            "margin": None,
            "to_beat": None,
            "baseline_total": None,
        },
        rows=[(KING, {"total": 0.64}, {"status": "IMPROVED", "gate_names": []})],
        network="testnet",
        key=signer,
        version=1,
        now=NOW,
    )
    assert lbf.read_board(_write(tmp_path, "b.json", board), "f02") == board
