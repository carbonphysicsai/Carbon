"""The launch board (OWNER-DASHBOARD-01): a validator's signed, closed standing of one
launch Challenge, read by the dashboard and projected to board.v2.

Claims: the writer builds from the Ladder's own best/latest documents (read-only from
the receiver's ledger) and the king document and signs under its own domain; the
reader pins the key out of band, refuses any other key, domain, extra field,
section below the total, unrounded value, fixture trust or tampered count; the
projection shows rounded totals and counts only, PRE_FIRST_RELEASE before a graded
hotkey and LIVE after; nothing finer than the Ladder step and no case, target, pool or
seed field can appear."""

from __future__ import annotations

import datetime
import json
import os
import sqlite3

import pytest

from carbon.challenge_validator import launch_board as lb
from carbon.challenge_validator.ladder_store import LadderStore, board_rows
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.challenge_validator.score_feed import FeedKey
from carbon.dashboard import board_v2, build, feed
from carbon.registry.model import ChallengeKey

CHALLENGE = ChallengeKey("electric-motor-magnetics", "1.4")
EXAM = "sha256:" + "e" * 64
GATES = ("native_motor_valid", "complete_fixed_coverage")
KING = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
OTHER = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"
THIRD = "5HGjWAeFDfFCWGSSAdJNNnvVcMB5dAPa3QCVq4NJTfYfmfZZ"
NOW = 1_800_000_000


def _scored(total):
    return {
        "artifact_digest": "sha256:" + "a" * 64,
        "status": "SCORED_DEVELOPMENT_CANDIDATE",
        "score": total,
        "legs": {"A": total, "D": total},
        "gates": {g: "PASS" for g in GATES},
        "components": {"robust_fidelity_benefit": total},
    }


def _gate_failed():
    return {
        "artifact_digest": "sha256:" + "b" * 64,
        "status": "MANDATORY_GATE_FAILED",
        "score": None,
        "legs": {},
        "gates": {GATES[0]: "FAIL", GATES[1]: "PASS"},
        "components": {},
    }


@pytest.fixture
def receiver(tmp_path):
    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    path = root / "attempts.sqlite3"
    return LadderStore(AttemptLedger(path)), path


def _record(store, hotkey, graded, exam=EXAM):
    return store.record(
        hotkey,
        CHALLENGE,
        exam,
        graded,
        exam_version="motor-exam-1",
        gates=GATES,
        rebuild_noise=None,
    )


def _king_document(king=True, noise=0.02):
    return {
        "schema": "carbon.koth.public.v1",
        "challenge_id": CHALLENGE.challenge_id,
        "challenge_version": CHALLENGE.version,
        "exam_version_label": "motor-exam-1",
        "king": ({"hotkey": KING, "total": 0.64, "since_epoch": 7} if king else None),
        "margin": noise,
        "to_beat": 0.66 if king else None,
        "baseline_total": None if king else 0.3,
    }


def _board(rows, king=True, version=1):
    signer = lb.LaunchBoardKey(os.urandom(32))
    board = lb.build(
        king_document=_king_document(king),
        rows=rows,
        network="testnet",
        key=signer,
        version=version,
        now=datetime.datetime.fromtimestamp(NOW, datetime.UTC),
    )
    return board, feed.Trust(keys=frozenset({signer.public_key}))


def test_the_writer_reads_the_ladder_read_only_and_the_reader_projects_it(receiver):
    store, path = receiver
    _record(store, KING, _scored(0.64))
    _record(store, OTHER, _scored(0.5))
    _record(store, OTHER, _scored(0.52))  # inside the step: no improvement
    _record(store, THIRD, _gate_failed())
    before = path.read_bytes()
    rows = board_rows(path, CHALLENGE, EXAM)
    assert path.read_bytes() == before  # never writes
    board, trust = _board(rows)
    assert board["schema"] == lb.SCHEMA and set(board) == lb.FIELDS
    third = next(r for r in board["ladder"] if r["hotkey"] == THIRD)
    assert third["total"] is None and third["gate_names"] == [GATES[0]]
    assert [r["hotkey"] for r in board["ladder"]][:2] == [KING, OTHER]
    assert board["counts"] == {
        "graded": 3,
        "scored": 2,
        "gate_failed": 1,
        "not_scored": 0,
    }
    v2 = board_v2.project(feed.project(board, trust), NOW)
    assert v2["phase"] == "LIVE"
    assert v2["king"]["hotkey"] == KING and v2["king"]["value"] == 0.64
    assert v2["ranking_section"]["name"] == "total"
    entries = v2["eligible_leaderboard"]["entries"]
    assert [e["hotkey"] for e in entries] == [KING, OTHER]
    assert v2["launch"]["counts"]["graded"] == 3
    assert v2["launch"]["to_beat"] == 0.66 and v2["launch"]["margin"] == 0.02


def test_before_a_first_grade_the_board_says_so(receiver):
    _store, path = receiver
    LadderStore(AttemptLedger(path))  # the ledger exists, no grade yet
    board, trust = _board(board_rows(path, CHALLENGE, EXAM), king=False)
    assert board["ladder"] == [] and board["king"]["king"] is None
    v2 = board_v2.project(feed.project(board, trust), NOW)
    assert v2["phase"] == "PRE_FIRST_RELEASE"
    assert v2["king"] is None and v2["launch"]["baseline_total"] == 0.3
    assert v2["launch"]["counts"]["graded"] == 0


def test_the_site_builds_and_nothing_finer_than_the_step_or_a_case_can_appear(
    receiver, tmp_path
):
    store, path = receiver
    _record(store, KING, _scored(0.6431))
    board, trust = _board(board_rows(path, CHALLENGE, EXAM))
    build.build(tmp_path / "site", [board], trust, now=NOW)
    boards = list((tmp_path / "site" / "data" / "v2").glob("*.json"))
    assert len(boards) == 1
    shown = boards[0].read_text()
    for forbidden in ("seed", "case_id", "target_value", "0.6431"):
        assert forbidden not in shown, forbidden
    assert json.loads(shown)["phase"] == "LIVE"
    assert "0.64" in shown


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda d: d.update(extra=1), "board_fields"),
        (lambda d: d["ladder"][0].update(accuracy=0.5), "ladder_invalid"),
        (lambda d: d["king"].update(case_errors=[1]), "king_invalid"),
        (lambda d: d["counts"].update(graded=9), "counts_invalid"),
        (lambda d: d["labels"].append("FIXTURE"), "labels_invalid"),
        (lambda d: d["ladder"][0].update(total=1.5), "ladder_invalid"),
        (lambda d: d["ladder"][0].update(total=0.123456789123), "total_unrounded"),
        (lambda d: d["ladder"][0].update(gate_names=["x"]), "ladder_invalid"),
    ],
)
def test_the_reader_refuses_any_other_shape_whole(receiver, mutate, code):
    store, path = receiver
    _record(store, KING, _scored(0.64))
    _record(store, OTHER, _scored(0.5))
    signer = lb.LaunchBoardKey(os.urandom(32))
    board = lb.build(
        king_document=_king_document(),
        rows=board_rows(path, CHALLENGE, EXAM),
        network="testnet",
        key=signer,
        version=1,
    )
    trust = feed.Trust(keys=frozenset({signer.public_key}))
    mutate(board)
    # Re-sign the mutated body so the refusal is the reader's shape check.
    body = {k: v for k, v in board.items() if k != "signature"}
    board["signature"] = signer.sign(body)
    with pytest.raises(feed.FeedRefused) as refused:
        feed.project(board, trust)
    assert refused.value.code == code


def test_a_board_is_trusted_only_under_its_own_key_and_domain(receiver):
    store, path = receiver
    _record(store, KING, _scored(0.64))
    board, trust = _board(board_rows(path, CHALLENGE, EXAM))
    other = feed.Trust(keys=frozenset({FeedKey(os.urandom(32)).public_key}))
    with pytest.raises(feed.FeedRefused) as refused:
        feed.project(board, other)
    assert refused.value.code == "signature_invalid"
    # A feed-domain signature of the same bytes is not a launch-board signature.
    signer = FeedKey(os.urandom(32))
    body = {k: v for k, v in board.items() if k != "signature"}
    wrong = {**body, "signature": signer.sign(body)}
    with pytest.raises(feed.FeedRefused):
        feed.project(wrong, feed.Trust(keys=frozenset({signer.public_key})))
    tampered = json.loads(json.dumps(board))
    tampered["ladder"][0]["total"] = 0.99
    with pytest.raises(feed.FeedRefused) as refused:
        feed.project(tampered, trust)
    assert refused.value.code == "signature_invalid"
    fixture = feed.Trust(keys=frozenset({feed.FIXTURE_PUBLIC_KEY}), fixture=True)
    with pytest.raises(feed.FeedRefused) as refused:
        feed.project(board, fixture)
    assert refused.value.code == "fixture_launch_board"


def test_other_exams_and_deleted_rows_are_not_on_the_board(receiver):
    store, path = receiver
    _record(store, KING, _scored(0.64))
    _record(store, OTHER, _scored(0.9), exam="sha256:" + "d" * 64)
    assert [h for h, _, _ in board_rows(path, CHALLENGE, EXAM)] == [KING]
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM ladder_feedback_v2 WHERE hotkey=?", (KING,))
    assert board_rows(path, CHALLENGE, EXAM) == []


def test_the_command_writes_a_board_the_reader_accepts(receiver, tmp_path):
    store, path = receiver
    _record(store, KING, _scored(0.64))
    key_path = tmp_path / "FEED.key"
    signer = FeedKey.create(key_path)
    king_path = tmp_path / "king.json"
    king_path.write_text(json.dumps(_king_document()))
    config = tmp_path / "board.config.json"
    config.write_text(
        json.dumps(
            {
                "schema": lb.CONFIG_SCHEMA,
                "network": "testnet",
                "ledger": str(path),
                "challenge": {
                    "id": CHALLENGE.challenge_id,
                    "version": CHALLENGE.version,
                },
                "exam_key": EXAM,
                "koth": str(king_path),
                "key": str(key_path),
            }
        )
    )
    out = tmp_path / "board.json"
    assert lb.main(["build", "--config", str(config), "--out", str(out)]) == 0
    document = json.loads(out.read_text())
    trust = feed.Trust(keys=frozenset({signer.public_key}))
    assert feed.project(document, trust)["incumbent"]["hotkey"] == KING
    assert lb.verify(document, signer.public_key)["counts"]["graded"] == 1


def test_the_pages_render_launch_boards_in_node(receiver, tmp_path):
    """The pages draw an empty board and a graded one, and disclose rounded totals
    and counts only (tests/cpu/dashboard_launch_check.cjs)."""
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    store, path = receiver
    empty, trust = _board(board_rows(path, CHALLENGE, EXAM), king=False)
    build.build(tmp_path / "empty", [empty], trust, now=NOW)
    _record(store, KING, _scored(0.64))
    _record(store, OTHER, _scored(0.5))
    _record(store, THIRD, _gate_failed())
    graded, trust = _board(board_rows(path, CHALLENGE, EXAM))
    build.build(tmp_path / "graded", [graded], trust, now=NOW)
    check = Path(__file__).with_name("dashboard_launch_check.cjs")
    phases = {}
    for name in ("empty", "graded"):
        result = subprocess.run(
            [node, str(check), str(tmp_path / name), str(NOW)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        phases[name] = json.loads(result.stdout)["phases"]
    assert phases == {"empty": ["PRE_FIRST_RELEASE"], "graded": ["LIVE"]}
