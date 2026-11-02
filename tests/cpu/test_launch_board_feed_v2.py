"""The receiver's feed serves a v2 launch board (`launch_board_file.read_board`; Validator 11-01, the board v2 blocker).

Claims: a v2 board the operator writes is served by the door's feed route exactly as written, under the same checks as v1 (its closed
shape, its own Challenge, the pinned key, the signature under v2's own domain, every total on the Ladder step, now including each
crown change's); a v2 board with any extra key, an exact total or a crown-change total finer than the step is refused even when
correctly re-signed; a v2 body under a v1 signature, or relabelled v1, is refused; v1 reading is unchanged (the v1 tests stand).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_launch_board_operator_v2 as operator_tests
from test_launch_board_feed import (
    CHALLENGE,
    KING,
    NOW,
    OTHER,
    PATH,
    _get,
    _intake,
    _rows,
    _signer,
    _write,
)
from test_launch_board_operator_v2 import (  # the operator's own test fixtures
    door,  # noqa: F401 - fixture
    frozen,  # noqa: F401 - fixture
)

from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import koth_registry
from carbon.challenge_validator import launch_board as lb
from carbon.challenge_validator import launch_board_file as lbf
from carbon.challenge_validator.launch_board_file import read_board


def _v2_board(signer, *, changes=None):
    king = kp.document_v2(
        challenge_id=CHALLENGE.challenge_id,
        challenge_version=CHALLENGE.version,
        exam_version_label="motor-exam-1",
        king={"hotkey": KING, "total": 0.64, "since_epoch": 7},
        rebuild_noise=koth_registry.rebuild_noise(CHALLENGE.challenge_id),
        baseline_total=None,
    )
    return lb.build(
        king_document=king,
        rows=_rows(),
        network="testnet",
        key=signer,
        version=4,
        now=NOW,
        crown_changes=(
            [
                {
                    "from_hotkey": OTHER,
                    "to_hotkey": KING,
                    "since_epoch": 7,
                    "total": 0.64,
                },
                {
                    "from_hotkey": None,
                    "to_hotkey": OTHER,
                    "since_epoch": 3,
                    "total": 0.6,
                },
            ]
            if changes is None
            else changes
        ),
        exact_totals={KING: 0.64},
        rebuild_noise=koth_registry.rebuild_noise(CHALLENGE.challenge_id),
    )


def _resigned(signer, board, mutate):
    body = json.loads(json.dumps({k: v for k, v in board.items() if k != "signature"}))
    mutate(body)
    body["signature"] = signer.sign(body)
    return body


def test_a_v2_board_is_read_and_served_unchanged(tmp_path):
    signer = _signer()
    board = _v2_board(signer)
    assert board["schema"] == lb.SCHEMA_V2 and len(board["crown_changes"]) == 2
    file = _write(tmp_path / "board.json", board)
    assert read_board(file, CHALLENGE.challenge_id, signer.public_key) == board
    answer = _get(
        _intake(lambda: read_board(file, CHALLENGE.challenge_id, signer.public_key))
    )
    assert answer.status == 200 and answer.body == board
    # the same pinned-key and foreign-Challenge refusals as v1
    assert read_board(file, CHALLENGE.challenge_id, _signer().public_key) is None
    assert read_board(file, "chip-cold-plate") is None


def test_a_v2_board_with_an_extra_key_or_an_exact_total_is_refused_even_resigned(
    tmp_path,
):
    signer = _signer()
    board = _v2_board(signer)
    name = CHALLENGE.challenge_id
    for mutate in (
        lambda b: b.update(recipe="x"),
        lambda b: b.update(exact_totals={KING: 0.64123456789}),
        lambda b: b["ladder"][0].update(exact_total=0.64123456789),
        lambda b: b["crown_changes"][0].update(exact_total=0.64123456789),
        lambda b: b["king"].update(exact=0.64123456789),
    ):
        assert (
            read_board(
                _write(tmp_path / "x.json", _resigned(signer, board, mutate)), name
            )
            is None
        )


def test_a_v2_total_finer_than_the_step_is_refused_crown_changes_included(tmp_path):
    signer = _signer()
    board = _v2_board(signer)
    name = CHALLENGE.challenge_id
    assert read_board(_write(tmp_path / "ok.json", board), name) is not None
    for mutate in (
        lambda b: b["crown_changes"][1].update(
            total=0.6037
        ),  # 0.6 is on the 0.02 grid; 0.6037 is not
        lambda b: b["ladder"][0].update(total=0.6437),
        lambda b: b["king"]["king"].update(total=0.6437),
    ):
        assert (
            read_board(
                _write(tmp_path / "fine.json", _resigned(signer, board, mutate)), name
            )
            is None
        )


def test_a_v2_body_under_a_v1_signature_or_relabelled_v1_is_refused(tmp_path):
    signer = _signer()
    board = _v2_board(signer)
    name = CHALLENGE.challenge_id
    body = {k: v for k, v in board.items() if k != "signature"}
    # signed under v1's domain: v2's own domain is what verify checks
    v1_signed = {
        **body,
        "signature": signer._key.sign(
            lb.BOARD_DOMAIN + lb._canonical(body).encode()
        ).hex(),
    }
    assert read_board(_write(tmp_path / "a.json", v1_signed), name) is None
    # relabelled v1 and re-signed: crown_changes and the v2 king section are outside v1's closed shape
    relabelled = _resigned(signer, board, lambda b: b.update(schema=lb.SCHEMA))
    assert read_board(_write(tmp_path / "b.json", relabelled), name) is None
    # tampered under the signature
    tampered = json.loads(json.dumps(board))
    tampered["crown_changes"][0]["since_epoch"] = 8
    assert read_board(_write(tmp_path / "c.json", tampered), name) is None


def test_the_operators_v2_board_reaches_the_feed_as_written(
    tmp_path,
    door,  # noqa: F811
    frozen,  # noqa: F811
):
    config, _pool = operator_tests._v2_fixture(tmp_path, door)
    (row,) = operator_tests.operator.run_once(config, version=9)
    assert row["state"] == "WROTE" and row["board"] == "v2"
    challenge = operator_tests.COOLING
    file = Path(config["out"]) / (operator_tests.operator.slug_of(challenge) + ".json")
    written = file.read_bytes()
    key = lb.LaunchBoardKey(operator_tests.SEED).public_key
    served = lbf.read_board(file, challenge["id"], key)
    assert (
        served is not None
        and served["schema"] == lb.SCHEMA_V2
        and served == json.loads(written)
    )
    # the door's own route serves it (the receiver wires read_board exactly so: path, Challenge id, pinned key)
    intake = _intake(lambda: lbf.read_board(file, challenge["id"], key))
    intake.challenge = type(CHALLENGE)(challenge["id"], challenge["version"])
    answer = _get(intake, PATH.replace(CHALLENGE.challenge_id, challenge["id"]))
    assert answer.status == 200 and answer.body == json.loads(written)
    assert file.read_bytes() == written  # read-only
