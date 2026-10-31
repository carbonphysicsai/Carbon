"""The receiver's signed launch-board feed (OWNER-DASHBOARD-LIVE-SWITCH-01):
``GET /carbon/v1/feed/<challenge_id>`` on a direct-intake receiver.

Claims: the door serves the operator-signed launch board file only when it verifies (the
signature under the launch-board domain, the closed shape, this Challenge, the pinned
key when configured); the dashboard's own reader accepts what the door serves; a board
signed by the dashboard's fixture key is never served; a tampered, extended, oversized,
foreign-Challenge or unreadable file is a typed 503, and no configured file is a 404;
the board carries no field outside the allow-list; and the receiver's configuration
names a file and a public key only, never a private key."""

from __future__ import annotations

import datetime
import json
import os
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_intake as di
from carbon.challenge_validator import direct_receiver as receiver
from carbon.challenge_validator import launch_board as lb
from carbon.challenge_validator import launch_board_file as lbf
from carbon.challenge_validator.score_feed import FeedKey
from carbon.dashboard import feed, fixtures, launch
from carbon.registry.model import ChallengeKey

CHALLENGE = ChallengeKey("electric-motor-magnetics", "1.5")
KING = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
OTHER = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"
NOW = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)
PATH = di.FEED_PATH + CHALLENGE.challenge_id


def _king_document(challenge=CHALLENGE):
    return {
        "schema": "carbon.koth.public.v1",
        "challenge_id": challenge.challenge_id,
        "challenge_version": challenge.version,
        "exam_version_label": "motor-exam-1",
        "king": {"hotkey": KING, "total": 0.64, "since_epoch": 7},
        "margin": 0.02,
        "to_beat": 0.66,
        "baseline_total": None,
    }


def _rows():
    scored = {"status": "IMPROVED", "gate_names": []}
    failed = {"status": "GATE_FAILED", "gate_names": ["native_motor_valid"]}
    return [(KING, {"total": 0.64}, scored), (OTHER, None, failed)]


def _board(signer, challenge=CHALLENGE):
    return lb.build(
        king_document=_king_document(challenge),
        rows=_rows(),
        network="testnet",
        key=signer,
        version=3,
        now=NOW,
    )


def _signer():
    return lb.LaunchBoardKey(os.urandom(32))


def _write(path, board):
    path.write_text(json.dumps(board), encoding="utf-8")
    return path


def _intake(reader=None):
    """The minimum `DirectRecipeIntake` the route reads."""
    intake = SimpleNamespace(challenge=CHALLENGE, koth_view=None, board_feed=reader)
    intake._board = lambda: di.DirectRecipeIntake._board(intake)
    intake._koth = lambda path: di.DirectRecipeIntake._koth(intake, path)
    intake.public = lambda: di.DirectRecipeIntake.public(intake)
    return intake


def _get(intake, path=PATH):
    return di.DirectRecipeIntake.route(intake, "GET", path, {}, b"")


def test_a_verified_board_is_served_and_the_dashboard_reader_accepts_it(tmp_path):
    signer = _signer()
    board = _board(signer)
    file = _write(tmp_path / "board.json", board)
    answer = _get(
        _intake(lambda: lbf.read_board(file, CHALLENGE.challenge_id, signer.public_key))
    )
    assert answer.status == 200 and answer.body == board
    # the Worker's own reader, pinned to the key out of band, takes what the door serves
    trust = feed.Trust(keys=frozenset({signer.public_key}))
    projected = launch.project(answer.body, trust)
    assert projected is not None
    with pytest.raises(launch.LaunchRefused):
        launch.project(answer.body, feed.Trust(keys=frozenset({"0" * 64})))


def test_only_the_closed_allow_list_is_public(tmp_path):
    board = _board(_signer())
    assert set(board) == lb.FIELDS
    text = json.dumps(board)
    for word in ("seed", "case", "pool", "recipe", "model", "submission", "target"):
        assert word not in text
    assert set(board["ladder"][0]) == lb.LADDER_FIELDS
    assert set(board["challenge"]) == lb.CHALLENGE_FIELDS


def test_no_configured_board_is_404_and_only_its_own_challenge_is_routed(tmp_path):
    assert _get(_intake(None)).status == 404
    assert _get(_intake(None)).body == {"refused": "feed_not_served"}
    assert _get(_intake(lambda: None), di.FEED_PATH + "other-challenge").status == 404
    assert _get(_intake(lambda: None), PATH + "/extra").status == 404
    # a POST to the feed path is not a read of the feed
    assert (
        di.DirectRecipeIntake.route(_intake(lambda: None), "POST", PATH, {}, b"").status
        == 404
    )


def test_an_unreadable_or_unverified_board_is_a_typed_503(tmp_path):
    answer = _get(_intake(lambda: None))
    assert answer.status == 503 and answer.body == {"refused": "feed_unavailable"}


def test_the_fixture_key_is_refused(tmp_path):
    fixture = lb.LaunchBoardKey(fixtures._SEED)
    assert fixture.public_key == lbf.fixture_public_key()
    assert fixtures.fixture_public_key() == lbf.fixture_public_key()
    board = _board(fixture)
    assert (
        lb.verify(board, fixture.public_key) == board
    )  # a valid signature, by the fixture key
    file = _write(tmp_path / "board.json", board)
    assert lbf.read_board(file, CHALLENGE.challenge_id) is None
    assert lbf.read_board(file, CHALLENGE.challenge_id, fixture.public_key) is None


def test_a_wrong_pinned_key_or_another_key_is_refused(tmp_path):
    signer, other = _signer(), _signer()
    file = _write(tmp_path / "board.json", _board(signer))
    assert lbf.read_board(file, CHALLENGE.challenge_id) is not None
    assert lbf.read_board(file, CHALLENGE.challenge_id, signer.public_key) is not None
    assert lbf.read_board(file, CHALLENGE.challenge_id, other.public_key) is None


def test_a_tampered_extended_or_foreign_board_is_refused(tmp_path):
    signer = _signer()
    board = _board(signer)
    name = CHALLENGE.challenge_id

    def refused(document):
        return lbf.read_board(_write(tmp_path / "t.json", document), name) is None

    assert not refused(board)
    # a changed value under the signature
    tampered = json.loads(json.dumps(board))
    tampered["ladder"][0]["total"] = 0.99
    assert refused(tampered)
    # a field outside the allow-list, even correctly re-signed by the real key
    extra = {k: v for k, v in board.items() if k != "signature"}
    extra["recipe"] = "x"
    extra["signature"] = signer.sign(extra)
    assert refused(extra)
    # a finer field inside a ladder row
    deep = json.loads(json.dumps({k: v for k, v in board.items() if k != "signature"}))
    deep["ladder"][0]["case_losses"] = [0.1]
    deep["signature"] = signer.sign(deep)
    assert refused(deep)
    # another Challenge's board
    foreign = _board(signer, ChallengeKey("chip-cold-plate", "1.6"))
    assert refused(foreign)
    # not a board
    assert refused([]) and refused({"schema": lb.SCHEMA})


def test_a_total_finer_than_the_ladder_step_is_refused(tmp_path):
    signer = _signer()
    name = CHALLENGE.challenge_id
    good = _board(signer)
    assert lbf.read_board(_write(tmp_path / "ok.json", good), name) is not None

    def resigned(mutate):
        body = json.loads(
            json.dumps({k: v for k, v in good.items() if k != "signature"})
        )
        mutate(body)
        body["signature"] = signer.sign(body)
        return _write(tmp_path / "fine.json", body)

    # a ladder total off the step (0.64 is on the 0.02 grid; 0.6437 is not), correctly signed
    finer = resigned(lambda b: b["ladder"][0].update(total=0.6437))
    assert lbf.read_board(finer, name) is None
    # the king's total off the step
    king = resigned(lambda b: b["king"]["king"].update(total=0.6437))
    assert lbf.read_board(king, name) is None


def test_the_boards_own_time_is_served_unchanged_so_the_dashboard_can_show_stale(
    tmp_path,
):
    signer = _signer()
    board = _board(signer)
    served = lbf.read_board(_write(tmp_path / "b.json", board), CHALLENGE.challenge_id)
    assert served["generated_at"] == "2027-01-15T08:00:00Z" and served["version"] == 3


def test_unreadable_garbled_and_oversized_files_are_refused(tmp_path):
    name = CHALLENGE.challenge_id
    assert lbf.read_board(tmp_path / "missing.json", name) is None
    garbled = tmp_path / "garbled.json"
    garbled.write_bytes(b"\xff\xfe not json")
    assert lbf.read_board(garbled, name) is None
    big = tmp_path / "big.json"
    big.write_text(" " * (lbf.MAX_BYTES + 1), encoding="utf-8")
    assert lbf.read_board(big, name) is None


def test_the_door_never_holds_a_signing_key():
    import inspect

    source = inspect.getsource(lbf)
    assert "LaunchBoardKey" not in source and ".sign(" not in source
    # it loads no key file; the fixture key is derived only to be refused, and never signs
    assert ".load(" not in source and "key_file" not in source


def test_the_feed_key_class_is_the_scores_so_one_pinned_key_serves_both():
    assert issubclass(lb.LaunchBoardKey, FeedKey)


def _config(tmp_path, **extra):
    return {
        "schema": receiver.SCHEMA,
        "root": str(tmp_path / "receiver"),
        "runner_profile": str(tmp_path / "profile.json"),
        "host": "127.0.0.1",
        "port": 8767,
        "receiver_hotkey": KING,
        "lifetime_seconds": 30,
        "measure_query": True,
        **extra,
    }


@pytest.mark.parametrize(
    "extra",
    [
        {"launch_board": "relative/board.json"},
        {"launch_board": None},
        {"launch_board_key": "a" * 64},  # a key without a file
    ],
)
def test_the_configuration_refuses_a_relative_file_or_a_key_alone(
    tmp_path, monkeypatch, extra
):
    cfg = _config(tmp_path, **extra)
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    with pytest.raises(ValueError):
        receiver.load_config(tmp_path / "config.json")


@pytest.mark.parametrize("key", ["A" * 64, "a" * 63, "g" * 64, 5, None])
def test_the_configuration_refuses_a_malformed_public_key(tmp_path, monkeypatch, key):
    cfg = _config(
        tmp_path, launch_board=str(tmp_path / "board.json"), launch_board_key=key
    )
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    with pytest.raises(ValueError):
        receiver.load_config(tmp_path / "config.json")


def test_the_configuration_accepts_a_board_file_and_a_public_key(tmp_path, monkeypatch):
    cfg = _config(
        tmp_path,
        launch_board=str(tmp_path / "board.json"),
        launch_board_key="a" * 64,
    )
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    assert receiver.load_config(tmp_path / "config.json") == cfg
