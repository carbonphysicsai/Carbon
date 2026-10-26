"""The launch-board operator script (OWNER-DASHBOARD-01, valV3 step 6).

Claims: with no ledger and no king document the four launch boards are the empty,
dashboard-accepted state; once results are recorded the next run shows them, on the
exam of the most recent result; the receiver's king document is fetched, closed and
checked; an unreachable receiver leaves the last board in place and fails the run; the
upload command gets the file and name only; a bad config or a group-readable key is
refused with a code and no board; the systemd units name the script and config.
"""

from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from carbon.challenge_validator import launch_board as lb
from carbon.challenge_validator.ladder_store import LadderStore
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.challenge_validator.score_feed import FeedKey
from carbon.dashboard import feed
from carbon.registry.model import ChallengeKey

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "dev" / "launch_board_operator.py"
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import launch_board_operator as operator

CHALLENGES = [
    {
        "id": "electric-motor-magnetics",
        "version": "1.4",
        "exam_version_label": "motor-exam-1",
    },
    {"id": "chip-cold-plate", "version": "1.4", "exam_version_label": "cooling-exam-1"},
    {"id": "f08-ribbed-bracket", "version": "1.5", "exam_version_label": "f08-exam-1"},
    {"id": "f02", "version": "2.4", "exam_version_label": "f02-exam-2"},
]
KING = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
OTHER = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"
GATES = ("native_motor_valid",)
EXAM_OLD = "sha256:" + "a" * 64
EXAM_NEW = "sha256:" + "b" * 64


class _Receiver:
    """A stand-in for the receiver's public king door."""

    def __init__(self):
        self.documents = {}  # challenge id -> document (absent: 404)
        receiver = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                challenge = self.path.rsplit("/", 1)[-1]
                document = receiver.documents.get(challenge)
                if document is None:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'{"refused":"koth_unpublished"}')
                    return
                body = json.dumps(document).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                return

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def receiver():
    server = _Receiver()
    yield server
    server.stop()


@pytest.fixture
def setup(tmp_path, receiver):
    root = tmp_path / "validator"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    key_path = root / "FEED.key"
    signer = FeedKey.create(key_path)
    config = {
        "schema": operator.CONFIG_SCHEMA,
        "network": "testnet",
        "ledger": str(root / "attempts.sqlite3"),
        "receiver_url": receiver.url,
        "key": str(key_path),
        "out": str(tmp_path / "boards"),
        "challenges": CHALLENGES,
    }
    path = tmp_path / "boards.config.json"
    path.write_text(json.dumps(config))
    trust = feed.Trust(keys=frozenset({signer.public_key}))
    return config, path, trust, root


def _scored(total):
    return {
        "artifact_digest": "sha256:" + "a" * 64,
        "status": "SCORED_DEVELOPMENT_CANDIDATE",
        "score": total,
        "legs": {"A": total, "D": total},
        "gates": {g: "PASS" for g in GATES},
        "components": {"x": total},
    }


def _record(root, challenge, hotkey, total, exam):
    store = LadderStore(AttemptLedger(root / "attempts.sqlite3"))
    store.record(
        hotkey,
        ChallengeKey(challenge["id"], challenge["version"]),
        exam,
        _scored(total),
        exam_version=challenge["exam_version_label"],
        gates=GATES,
        rebuild_noise=None,
    )


def _king(challenge, total=0.64):
    return {
        "schema": "carbon.koth.public.v1",
        "challenge_id": challenge["id"],
        "challenge_version": challenge["version"],
        "exam_version_label": challenge["exam_version_label"],
        "king": {"hotkey": KING, "total": total, "since_epoch": 7},
        "margin": 0.02,
        "to_beat": round(total + 0.02, 2),
        "baseline_total": None,
    }


def _read(config, challenge):
    name = operator.slug_of(challenge) + ".json"
    return json.loads((Path(config["out"]) / name).read_text())


def test_before_any_grade_every_board_is_the_empty_state_the_dashboard_accepts(setup):
    config, _, trust, _ = setup
    rows = operator.run_once(config)
    assert [r["state"] for r in rows] == ["WROTE"] * 4
    for challenge in CHALLENGES:
        document = _read(config, challenge)
        assert document["counts"]["graded"] == 0 and document["king"]["king"] is None
        board = feed.project(document, trust)
        assert board["released_count"] == 0
        assert (
            document["challenge"]["exam_version_label"]
            == challenge["exam_version_label"]
        )


def test_results_show_on_the_next_run_on_the_exam_of_the_latest_result(setup, receiver):
    config, _, trust, root = setup
    motor = CHALLENGES[0]
    _record(root, motor, OTHER, 0.3, EXAM_OLD)
    _record(root, motor, KING, 0.64, EXAM_NEW)
    receiver.documents[motor["id"]] = _king(motor)
    rows = operator.run_once(config)
    assert rows[0]["state"] == "WROTE" and rows[0]["graded"] == 1
    document = _read(config, motor)
    assert [r["hotkey"] for r in document["ladder"]] == [KING]  # the new exam only
    assert document["king"]["king"]["hotkey"] == KING
    assert feed.project(document, trust)["incumbent"]["hotkey"] == KING
    # the other three are still empty
    assert [r["graded"] for r in rows] == [1, 0, 0, 0]


def test_an_explicit_exam_key_wins_over_the_latest(setup, receiver):
    config, _path, _trust, root = setup
    motor = CHALLENGES[0]
    _record(root, motor, OTHER, 0.3, EXAM_OLD)
    _record(root, motor, KING, 0.64, EXAM_NEW)
    receiver.documents[motor["id"]] = _king(motor)
    config["challenges"] = [{**motor, "exam_key": EXAM_OLD}]
    (row,) = operator.run_once(config)
    assert row["graded"] == 1
    assert [r["hotkey"] for r in _read(config, motor)["ladder"]] == [OTHER]


def test_an_unreachable_receiver_keeps_the_last_board_and_fails_the_run(
    setup, receiver, capsys
):
    config, path, _trust, _ = setup
    assert [r["state"] for r in operator.run_once(config)] == ["WROTE"] * 4
    before = (
        Path(config["out"]) / (operator.slug_of(CHALLENGES[0]) + ".json")
    ).read_text()
    receiver.stop()
    rows = operator.run_once(config)
    assert {r["state"] for r in rows} == {"REFUSED"}
    assert {r["code"] for r in rows} == {"receiver_unavailable"}
    after = (
        Path(config["out"]) / (operator.slug_of(CHALLENGES[0]) + ".json")
    ).read_text()
    assert after == before
    assert operator.main(["run", "--config", str(path)]) == 2
    assert "receiver_unavailable" in capsys.readouterr().out


def test_a_king_document_with_a_stray_field_is_refused_and_not_published(
    setup, receiver
):
    config, _, _, _ = setup
    motor = CHALLENGES[0]
    receiver.documents[motor["id"]] = {**_king(motor), "case_errors": [0.1]}
    rows = operator.run_once(config)
    assert rows[0]["state"] == "REFUSED" and rows[0]["code"] == "board_king"
    assert not (Path(config["out"]) / (operator.slug_of(motor) + ".json")).exists()
    assert [r["state"] for r in rows[1:]] == ["WROTE"] * 3


def test_another_challenges_answer_is_refused(setup, receiver):
    config, _, _, _ = setup
    motor = CHALLENGES[0]
    receiver.documents[motor["id"]] = _king(CHALLENGES[1])
    rows = operator.run_once(config)
    assert rows[0]["code"] == "receiver_answer_other_challenge"


def test_the_upload_command_gets_the_file_and_its_name_only(setup, tmp_path):
    config, _, _, _ = setup
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    config["upload_command"] = ["cp", "{file}", str(bucket) + "/valv3-{name}"]
    rows = operator.run_once(config)
    assert [r["state"] for r in rows] == ["UPLOADED"] * 4
    names = sorted(p.name for p in bucket.iterdir())
    assert names == sorted("valv3-" + operator.slug_of(c) + ".json" for c in CHALLENGES)
    config["upload_command"] = ["false"]
    assert {r["code"] for r in operator.run_once(config)} == {"upload_failed"}


def test_the_boards_name_no_key_and_the_run_prints_none(setup, capsys):
    config, path, _, _ = setup
    assert operator.main(["run", "--config", str(path)]) == 0
    out = capsys.readouterr().out
    key_bytes = Path(config["key"]).read_bytes().hex()
    assert key_bytes not in out
    for challenge in CHALLENGES:
        assert (
            key_bytes
            not in (
                Path(config["out"]) / (operator.slug_of(challenge) + ".json")
            ).read_text()
        )
    assert json.loads(out)["boards"][0]["state"] == "WROTE"


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(schema="other"),
        lambda c: c.update(extra=1),
        lambda c: c.update(network="devnet"),
        lambda c: c.update(challenges=[]),
        lambda c: c.update(challenges=[{"id": "x"}]),
        lambda c: c.update(upload_command="cp"),
        lambda c: c.update(receiver_url="ftp://x"),
    ],
)
def test_a_bad_config_is_refused_with_a_code_and_writes_nothing(setup, change, capsys):
    config, path, _, _ = setup
    change(config)
    path.write_text(json.dumps(config))
    assert operator.main(["run", "--config", str(path)]) == 2
    assert "refused" in capsys.readouterr().out
    assert not Path(config["out"]).exists()


def test_a_key_others_can_read_is_refused(setup, capsys):
    config, path, _, _ = setup
    os.chmod(config["key"], 0o644)
    assert operator.main(["run", "--config", str(path)]) == 2
    assert "feed_key_not_owner_only" in capsys.readouterr().out


def test_the_systemd_units_name_the_script_and_the_config_only(setup):
    _, path, _, _ = setup
    text = operator.systemd_units(path, every=300)
    assert (
        "launch_board_operator.py run --config" in text and str(path.resolve()) in text
    )
    assert "OnUnitActiveSec=300s" in text and "Type=oneshot" in text
    assert "FEED.key" not in text


def test_the_script_runs_as_a_command(setup):
    _, path, _, _ = setup
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "systemd", "--config", str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert done.returncode == 0 and "carbon-launch-board.timer" in done.stdout


def test_the_launch_board_command_still_builds_one_board(setup, receiver, tmp_path):
    """The single-Challenge command (`launch_board build`) is unchanged and takes
    "latest" as the exam key."""
    config, _, trust, root = setup
    motor = CHALLENGES[0]
    _record(root, motor, KING, 0.64, EXAM_NEW)
    king_path = tmp_path / "king.json"
    king_path.write_text(json.dumps(_king(motor)))
    cfg = tmp_path / "one.json"
    cfg.write_text(
        json.dumps(
            {
                "schema": lb.CONFIG_SCHEMA,
                "network": "testnet",
                "ledger": config["ledger"],
                "challenge": {"id": motor["id"], "version": motor["version"]},
                "exam_key": "latest",
                "koth": str(king_path),
                "key": config["key"],
            }
        )
    )
    out = tmp_path / "one-board.json"
    assert lb.main(["build", "--config", str(cfg), "--out", str(out)]) == 0
    assert (
        feed.project(json.loads(out.read_text()), trust)["incumbent"]["hotkey"] == KING
    )
