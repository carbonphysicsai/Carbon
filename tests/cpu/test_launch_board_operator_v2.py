"""The launch-board operator's v2 boards (BOARD V2 GAP; the Validator's two conditions).

Claims: (1) without ``"board": "v2"`` the operator's run is the v1 run: it asks the receiver
for the v1 king document only and writes byte-identical v1 boards (pinned against the bytes
the pre-v2 operator wrote for the same inputs); (2) with ``"board": "v2"`` it fetches the v2
king document, reads the crown changes and the exact best totals from the receiver's pool
store and ledger READ-ONLY, and writes a v2 board in the true order whose bytes, the run's
output and the out directory carry no exact total; a crown that moved between the reads, a
group-readable pool store or a row with no exact total is refused and nothing is published;
a v2 config must name each pool store and contract digest, and a v1 config names neither.
"""

from __future__ import annotations

import datetime
import hashlib
import http.server
import json
import os
import sqlite3
import sys
import threading
import types
from pathlib import Path

import pytest

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import koth_registry
from carbon.challenge_validator import launch_board as lb
from carbon.challenge_validator.feed_file import write_feed
from carbon.challenge_validator.ladder_store import LadderStore
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.registry.model import ChallengeKey
from carbon.scoring import grade_feedback as gf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import launch_board_operator as operator

MOTOR = {
    "id": "electric-motor-magnetics",
    "version": "1.4",
    "exam_version_label": "motor-exam-1",
}
COOLING = {
    "id": "chip-cold-plate",
    "version": "1.4",
    "exam_version_label": "cooling-exam-1",
}
KING = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
OTHER = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"
GATES = ("native_motor_valid",)
EXAM = "sha256:" + "b" * 64
CONTRACT = "sha256:" + "c" * 64
NOW = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)
SEED = bytes(range(32))
#: The exact totals: finer than any step, so a leak is visible as these digits.
KING_EXACT = 0.70123456789
OTHER_EXACT = 0.61234567891
#: sha256 of the v1 Motor board `_v1_fixture` writes, as the operator BEFORE the v2 wiring
#: (main e1dc7d88ae2a6adb3dba652ebfbf77d365f53ea9) wrote it: v1 stays byte-identical.
V1_GOLDEN = "4d7c3fd0000e4e1b24b9884b7b817ac14e6481181977f577670367b65daca9d8"


class _Door:
    """A stand-in for the receiver's public king door: v1 and v2 documents at their own
    paths, and every path asked for."""

    def __init__(self):
        self.documents = {}  # path -> document (absent: 404)
        self.asked = []
        door = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                door.asked.append(self.path)
                document = door.documents.get(self.path)
                if document is None:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'{"refused":"koth_unpublished"}')
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(document).encode())

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
def door():
    server = _Door()
    yield server
    server.stop()


@pytest.fixture
def frozen(monkeypatch):
    """The board's clock at `NOW`, so two builds of the same inputs are the same bytes."""

    class _Clock(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(
        lb, "datetime", types.SimpleNamespace(datetime=_Clock, UTC=datetime.UTC)
    )


def _root(tmp_path):
    root = tmp_path / "validator"
    root.mkdir(mode=0o700, parents=True)
    os.chmod(root, 0o700)
    key = root / "FEED.key"
    fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(SEED)
    return root, key


def _config(tmp_path, door, challenges, **extra):
    root, key = _root(tmp_path)
    return {
        "schema": operator.CONFIG_SCHEMA,
        "network": "testnet",
        "ledger": str(root / "attempts.sqlite3"),
        "receiver_url": door.url,
        "key": str(key),
        "out": str(tmp_path / "boards"),
        "challenges": challenges,
        **extra,
    }, root


def _record(root, challenge, hotkey, total):
    LadderStore(AttemptLedger(root / "attempts.sqlite3")).record(
        hotkey,
        ChallengeKey(challenge["id"], challenge["version"]),
        EXAM,
        {
            "artifact_digest": "sha256:" + "a" * 64,
            "status": "SCORED_DEVELOPMENT_CANDIDATE",
            "score": total,
            "legs": {"A": total, "D": total},
            "gates": {g: "PASS" for g in GATES},
            "components": {"x": total},
        },
        exam_version=challenge["exam_version_label"],
        gates=GATES,
        rebuild_noise=None,
    )


def _board_bytes(config, challenge):
    return (Path(config["out"]) / (operator.slug_of(challenge) + ".json")).read_bytes()


# --- (1) v1 is byte-identical -------------------------------------------------------------


def _v1_fixture(tmp_path, door, **extra):
    """A graded Motor door with a v1 king: the operator's v1 board bytes."""
    config, root = _config(tmp_path, door, [MOTOR], **extra)
    _record(root, MOTOR, OTHER, 0.3)
    _record(root, MOTOR, KING, 0.64)
    door.documents[kp.PATH + MOTOR["id"]] = {
        "schema": "carbon.koth.public.v1",
        "challenge_id": MOTOR["id"],
        "challenge_version": MOTOR["version"],
        "exam_version_label": MOTOR["exam_version_label"],
        "king": {"hotkey": KING, "total": 0.64, "since_epoch": 7},
        "margin": 0.02,
        "to_beat": 0.66,
        "baseline_total": None,
    }
    (row,) = operator.run_once(config, version=7)
    assert row["state"] == "WROTE"
    return config, _board_bytes(config, MOTOR)


def test_the_v1_run_writes_the_same_bytes_as_before_the_v2_wiring(
    tmp_path, door, frozen
):
    _, written = _v1_fixture(tmp_path, door)
    assert hashlib.sha256(written).hexdigest() == V1_GOLDEN
    document = json.loads(written)
    assert document["schema"] == lb.SCHEMA and set(document) == lb.FIELDS
    assert "to_beat_rule" not in document["king"]
    # only the v1 king document was asked for
    assert door.asked == [kp.PATH + MOTOR["id"]]


def test_board_v1_named_is_the_same_run_as_board_unnamed(tmp_path, door, frozen):
    _, unnamed = _v1_fixture(tmp_path / "a", door)
    door.asked.clear()
    _, named = _v1_fixture(tmp_path / "b", door, board="v1")
    assert named == unnamed
    assert door.asked == [kp.PATH + MOTOR["id"]]


def test_the_v1_bytes_are_the_plain_v1_build_of_the_same_inputs(tmp_path, door, frozen):
    config, written = _v1_fixture(tmp_path, door)
    challenge = type(
        "C", (), {"challenge_id": MOTOR["id"], "version": MOTOR["version"]}
    )()
    expected = tmp_path / "expected.json"
    write_feed(
        expected,
        lb.build_from_ledger(
            ledger=config["ledger"],
            challenge=challenge,
            exam_key="latest",
            king_document=door.documents[kp.PATH + MOTOR["id"]],
            network="testnet",
            key=lb.LaunchBoardKey(SEED),
            version=7,
        ),
    )
    assert expected.read_bytes() == written


# --- (2) v2, with the exact totals operator-side only ---------------------------------------


def _pool(root, *, mode=0o600):
    """The receiver's pool store: OTHER crowned first, then KING; one scored private
    evaluation each; the ledger's signed receipts put them in epochs 10 and 12."""
    path = root / "pool.sqlite3"
    store = PoolStore(path)
    with store.transaction() as db:
        for op, model, hotkey, total in (
            ("op-other", "m-other", OTHER, OTHER_EXACT),
            ("op-king", "m-king", KING, KING_EXACT),
        ):
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?)",
                (
                    op,
                    "private_evaluation.v1",
                    "BOUND_DEVELOPMENT_ONLY",
                    json.dumps(
                        {
                            "submission_id": model,
                            "owner": {"hotkey": hotkey, "request_digest": "d"},
                            "evidence": {
                                "challenge": COOLING["id"],
                                "evaluation_version": COOLING["exam_version_label"],
                                "model_p": {
                                    "total_score": total,
                                    "score_status": "SCORED_DEVELOPMENT_CANDIDATE",
                                },
                            },
                        }
                    ),
                ),
            )
        store._set_incumbent(db, "m-other", "first", expected=None)
        store._set_incumbent(db, "m-king", "crowned", expected="m-other")
    os.chmod(path, mode)
    ledger = AttemptLedger(root / "attempts.sqlite3")
    with ledger._db() as db:
        for model, block in (("m-other", 3600), ("m-king", 4320)):
            db.execute(
                "INSERT INTO attempts(at_ns, kind, contract_digest, receipt,"
                " submission_sha256, submission_id) VALUES(?,?,?,?,?,?)",
                (1, "OUTCOME", CONTRACT, json.dumps({"block": block}), "s", model),
            )
    return path


def _v2_king():
    return kp.document_v2(
        challenge_id=COOLING["id"],
        challenge_version=COOLING["version"],
        exam_version_label=COOLING["exam_version_label"],
        king={"hotkey": KING, "total": KING_EXACT, "since_epoch": 12},
        rebuild_noise=koth_registry.rebuild_noise(COOLING["id"]),
        baseline_total=None,
    )


def _v2_fixture(tmp_path, door, *, mode=0o600, king=None):
    root, _ = _root(tmp_path)
    challenge = {
        **COOLING,
        "pool_store": str(root / "pool.sqlite3"),
        "contract_digest": CONTRACT,
    }
    config = {
        "schema": operator.CONFIG_SCHEMA,
        "network": "testnet",
        "ledger": str(root / "attempts.sqlite3"),
        "receiver_url": door.url,
        "key": str(root / "FEED.key"),
        "out": str(tmp_path / "boards"),
        "challenges": [challenge],
        "board": "v2",
    }
    _record(root, COOLING, OTHER, OTHER_EXACT)
    _record(root, COOLING, KING, KING_EXACT)
    pool = _pool(root, mode=mode)
    door.documents[kp.PATH + COOLING["id"] + kp.V2_SUFFIX] = (
        _v2_king() if king is None else king
    )
    return config, pool


def _snapshot(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        return [
            db.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()
            for t in ("operations", "incumbent", "events")
        ]


def test_the_v2_board_has_the_crown_changes_and_the_true_order(tmp_path, door, frozen):
    config, _ = _v2_fixture(tmp_path, door)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE" and row["board"] == "v2"
    assert row["crown_changes"] == 2 and row["graded"] == 2
    assert door.asked == [kp.PATH + COOLING["id"] + kp.V2_SUFFIX]
    document = json.loads(_board_bytes(config, COOLING))
    assert lb.verify(document, lb.LaunchBoardKey(SEED).public_key) == document
    assert document["schema"] == lb.SCHEMA_V2
    assert document["king"]["to_beat_rule"] == kp.TO_BEAT_RULE
    noise = koth_registry.rebuild_noise(COOLING["id"])["value"]
    assert document["crown_changes"] == [
        {
            "from_hotkey": OTHER,
            "to_hotkey": KING,
            "since_epoch": 12,
            "total": lb.floor9(gf.floor_to_step(KING_EXACT, noise)),
        },
        {
            "from_hotkey": None,
            "to_hotkey": OTHER,
            "since_epoch": 10,
            "total": lb.floor9(gf.floor_to_step(OTHER_EXACT, noise)),
        },
    ]
    assert [(r["hotkey"], r["rank"]) for r in document["ladder"]] == [
        (KING, 1),
        (OTHER, 2),
    ]
    assert document["ladder"][0]["total"] == document["king"]["king"]["total"]


def test_no_exact_total_leaves_the_operator_process(tmp_path, door, frozen, capsys):
    config, pool = _v2_fixture(tmp_path, door)
    before = _snapshot(pool)
    path = tmp_path / "boards.config.json"
    path.write_text(json.dumps(config))
    assert operator.main(["run", "--config", str(path)]) == 0
    printed = capsys.readouterr()
    rows = json.dumps(operator.run_once(config, version=9))
    written = _board_bytes(config, COOLING).decode()
    for exact in (KING_EXACT, OTHER_EXACT):
        for shown in _shown(exact):
            assert shown not in written
            assert shown not in printed.out and shown not in printed.err
            assert shown not in rows
    # nothing but the board is written, and the pool store is unchanged
    assert [p.name for p in Path(config["out"]).iterdir()] == [
        operator.slug_of(COOLING) + ".json"
    ]
    assert _snapshot(pool) == before


def _shown(exact):
    """The forms an exact total could leak as: its repr, and its first 7 decimals."""
    return (repr(exact), str(exact)[:9])


@pytest.mark.parametrize("case", ["moved", "group_readable"])
def test_a_refusal_names_a_code_and_no_exact_total(tmp_path, door, frozen, case):
    # (a ladder row with no exact total is no longer a refusal: see
    # test_a_ladder_row_with_no_exact_total_keeps_its_floored_order)
    king = None
    if case == "moved":
        king = {**_v2_king()}
        king["king"] = {**king["king"], "hotkey": OTHER}
    config, _ = _v2_fixture(
        tmp_path, door, king=king, mode=0o640 if case == "group_readable" else 0o600
    )
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "REFUSED" and set(row) == {
        "challenge",
        "version",
        "file",
        "state",
        "code",
    }
    text = json.dumps(row) + str(operator.OperatorRefused(row["code"]))
    for exact in (KING_EXACT, OTHER_EXACT):
        assert not any(shown in text for shown in _shown(exact))


def test_the_pool_store_is_opened_read_only(tmp_path):
    root, _ = _root(tmp_path)
    pool = _pool(root)
    store = operator.ReadOnlyPoolStore(pool)
    assert store.incumbent()["model_id"] == "m-king"
    with store.db() as db, pytest.raises(sqlite3.OperationalError):
        db.execute("DELETE FROM incumbent")
    with store.db() as db, pytest.raises(sqlite3.OperationalError):
        db.execute("CREATE TABLE IF NOT EXISTS x(y)")
    assert not hasattr(store, "transaction") and not hasattr(store, "record")


def test_the_borrowed_readers_run_select_statements_only(tmp_path, monkeypatch):
    """`events`, `incumbent`, `incumbent_standing` and `private_evaluation_bodies` over
    the read-only store issue nothing but SELECTs: no writer, no schema statement, no
    journal-mode change."""
    root, _ = _root(tmp_path)
    pool = _pool(root)
    seen = []
    opened = operator._readonly

    def traced(path):
        connection = opened(path)
        connection.set_trace_callback(seen.append)
        return connection

    monkeypatch.setattr(operator, "_readonly", traced)
    store = operator.ReadOnlyPoolStore(pool)
    store.events("incumbent")
    store.incumbent_standing(store.incumbent()["model_id"])
    store.private_evaluation_bodies()
    assert seen and all(s.lstrip().upper().startswith("SELECT") for s in seen)


def test_a_missing_pool_store_is_never_created(tmp_path):
    root, _ = _root(tmp_path)
    store = operator.ReadOnlyPoolStore(root / "pool.sqlite3")
    with pytest.raises(OSError):
        store.incumbent()
    assert list(root.iterdir()) == [root / "FEED.key"]


def test_a_symlinked_pool_store_is_refused(tmp_path, door, frozen):
    config, pool = _v2_fixture(tmp_path, door)
    real = pool.with_name("real.sqlite3")
    pool.rename(real)
    pool.symlink_to(real)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "REFUSED" and row["code"] == "pool_store_not_owner_only"


def test_a_wal_pool_store_reads_without_writing_its_database_file(tmp_path):
    """The receiver keeps its pool store in WAL mode. A read-only open of it, with its
    -wal/-shm closed away (the receiver stopped), still reads, and the database file's
    bytes do not change (SQLite may leave empty -wal/-shm sidecars, never a database).
    """
    root, _ = _root(tmp_path)
    pool = _pool(root)
    with sqlite3.connect(pool) as db:
        assert db.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    before = pool.read_bytes()
    assert operator.ReadOnlyPoolStore(pool).incumbent()["model_id"] == "m-king"
    assert pool.read_bytes() == before


def test_a_crown_that_moved_between_the_reads_is_refused(tmp_path, door, frozen):
    king = {**_v2_king()}
    # the door still names the old king
    king["king"] = {**king["king"], "hotkey": OTHER}
    config, _ = _v2_fixture(tmp_path, door, king=king)
    (row,) = operator.run_once(config, version=9)
    assert row == {**row, "state": "REFUSED", "code": "king_moved_during_run"}
    assert not (Path(config["out"]) / (operator.slug_of(COOLING) + ".json")).exists()


def test_a_group_readable_pool_store_is_refused(tmp_path, door, frozen):
    config, _ = _v2_fixture(tmp_path, door, mode=0o640)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "REFUSED" and row["code"] == "pool_store_not_owner_only"


def test_a_ladder_row_with_no_exact_total_keeps_its_floored_order(
    tmp_path, door, frozen
):
    # graded on the ladder but with no pool evaluation, so no exact total: the board is written, that row is ordered
    # by its own floored total (as on v1), and no exact total is invented for it
    config, _ = _v2_fixture(tmp_path, door)
    third = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
    _record(Path(config["ledger"]).parent, COOLING, third, 0.5)  # no pool evaluation
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE" and row["board"] == "v2"
    document = json.loads(_board_bytes(config, COOLING))
    assert lb.verify(document, lb.LaunchBoardKey(SEED).public_key) == document
    noise = koth_registry.rebuild_noise(COOLING["id"])["value"]
    assert [(r["hotkey"], r["rank"], r["total"]) for r in document["ladder"]] == [
        (KING, 1, document["king"]["king"]["total"]),
        (OTHER, 2, lb.floor9(gf.floor_to_step(OTHER_EXACT, noise))),
        (third, 3, lb.floor9(gf.floor_to_step(0.5, noise))),
    ]
    text = _board_bytes(config, COOLING).decode()
    for exact in (KING_EXACT, OTHER_EXACT):
        assert repr(exact) not in text


def test_before_any_pool_store_the_v2_board_is_the_empty_one(tmp_path, door, frozen):
    root, _ = _root(tmp_path)
    config = {
        "schema": operator.CONFIG_SCHEMA,
        "network": "testnet",
        "ledger": str(root / "attempts.sqlite3"),
        "receiver_url": door.url,
        "key": str(root / "FEED.key"),
        "out": str(tmp_path / "boards"),
        "challenges": [
            {
                **COOLING,
                "pool_store": str(root / "pool.sqlite3"),
                "contract_digest": CONTRACT,
            }
        ],
        "board": "v2",
    }
    (row,) = operator.run_once(config, version=9)  # the door answers 404
    assert row["state"] == "WROTE" and row["crown_changes"] == 0
    document = json.loads(_board_bytes(config, COOLING))
    assert document["schema"] == lb.SCHEMA_V2 and document["ladder"] == []
    assert document["king"]["king"] is None
    assert not (root / "pool.sqlite3").exists()  # never created


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(board="v3"),
        lambda c: c["challenges"][0].pop("pool_store"),
        lambda c: c["challenges"][0].pop("contract_digest"),
        lambda c: c["challenges"][0].update(pool_store="relative/pool.sqlite3"),
        lambda c: c["challenges"][0].update(contract_digest="c" * 64),
        lambda c: (c.pop("board"), None),  # a v1 config names no pool store
    ],
)
def test_a_v2_config_names_each_pool_store_and_contract(tmp_path, door, change):
    config, _ = _v2_fixture(tmp_path, door)
    change(config)
    path = tmp_path / "boards.config.json"
    path.write_text(json.dumps(config))
    with pytest.raises(operator.OperatorRefused):
        operator.load_config(path)
