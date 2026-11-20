"""Carbon Evidence Catalog v0 (`scripts/dev/evidence_catalog.py`): the join, its class discipline and its read-only
sources, on a synthetic receiver state (fake task-record decoders; no door, worker, model or hidden value)."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import evidence_catalog as cec  # noqa: E402

HOTKEY = "5" + "H" * 47
TASK = "rtsk_" + "a" * 64
RERUN = "rtsk_" + "b" * 64
COPY = "rtsk_" + "c" * 64
RECIPE = "sha256:" + "d" * 64
PREDICTIONS_B64 = "UFJFRElDVElPTlM" * 40
TRACEBACK = "Traceback (most recent call last): secret-tail"


def _view(state, created, refusal=None, infra=None):
    return json.dumps(
        {
            "challenge_id": "electric-motor-magnetics",
            "version": "1.8",
            "state": state,
            "created_s": created,
            "updated_s": created + 10,
            "recipe_digest": RECIPE,
            "refusal_code": refusal,
            "infra_class": infra,
            "completed_s": created + 9,
        }
    ).encode()


DECODERS = (
    lambda raw: json.loads(bytes(raw)),
    lambda raw: json.loads(bytes(raw))["recipe"],
)


def _sqlite(path, script, rows=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(script)
    for sql, values in rows:
        db.executemany(sql, values)
    db.commit()
    db.close()


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "receiver" / "state"
    _sqlite(
        root / "attempts.sqlite3",
        """
        CREATE TABLE attempts(seq INTEGER PRIMARY KEY, at_ns INTEGER, kind TEXT, code TEXT, hotkey TEXT,
            contract_digest TEXT, receipt TEXT, submission_sha256 TEXT, submission_id TEXT, state TEXT);
        CREATE TABLE recipe_task_intents(contract_digest TEXT, submission_id TEXT, hotkey TEXT, request_sha256 TEXT);
        CREATE TABLE recipe_copy_digests(submission_id TEXT PRIMARY KEY, recipe_digest TEXT);
        CREATE TABLE recipe_copies(submission_id TEXT PRIMARY KEY, first_id TEXT, challenge_id TEXT,
            challenge_version TEXT, exam_key TEXT, recipe_digest TEXT, recorded_ns INTEGER);
        CREATE TABLE exam_graded(id INTEGER PRIMARY KEY, hotkey TEXT, challenge_id TEXT, challenge_version TEXT,
            exam_key TEXT, kind TEXT, epoch INTEGER, submission_id TEXT, state TEXT, status TEXT,
            reserved_ns INTEGER, settled_ns INTEGER, cpu_seconds REAL, lane_seconds REAL);
        CREATE TABLE gate_failures_v1(submission_id TEXT, exam_key TEXT, failures TEXT);
        CREATE TABLE exam_requeues(submission_id TEXT PRIMARY KEY, attempt INTEGER, queued_ns INTEGER,
            reserved_ns INTEGER);
        """,
        [
            (
                "INSERT INTO attempts(at_ns, kind, hotkey, submission_id) VALUES(?,?,?,?)",
                [
                    (100, "OUTCOME", HOTKEY, TASK),
                    (200, "OUTCOME", HOTKEY, RERUN),
                    (300, "OUTCOME", HOTKEY, COPY),
                ],
            ),
            (
                "INSERT INTO recipe_task_intents VALUES(?,?,?,?)",
                [("c", TASK, HOTKEY, "sha256:" + "e" * 64)],
            ),
            (
                "INSERT INTO recipe_copy_digests VALUES(?,?)",
                [(TASK, RECIPE), (COPY, RECIPE)],
            ),
            (
                "INSERT INTO recipe_copies VALUES(?,?,?,?,?,?,?)",
                [(COPY, RERUN, "m", "1.8", "k", RECIPE, 1)],
            ),
            (
                "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, kind, epoch, "
                "submission_id, state, status, reserved_ns, settled_ns, cpu_seconds, lane_seconds) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        HOTKEY,
                        "m",
                        "1.8",
                        "k1",
                        "GRADED",
                        7,
                        RERUN,
                        "COUNTED",
                        "SCORED",
                        1,
                        2,
                        30.0,
                        490.0,
                    )
                ],
            ),
            ("INSERT INTO gate_failures_v1 VALUES(?,?,?)", [(RERUN, "k1", "[]")]),
            ("INSERT INTO exam_requeues VALUES(?,?,?,?)", [(RERUN, 2, 5, None)]),
        ],
    )
    evidence = {
        "state_digest": "sha256:" + "1" * 64,
        "predictions_raw_base64": PREDICTIONS_B64,
        "build_device": "gpu",
        "inference_receipt": {
            "predictions_digest": "sha256:" + "2" * 64,
            "inputs_digest": "sha256:" + "3" * 64,
        },
        "build_receipt": {
            "fit": {
                "train_loss": 0.125,
                "member_losses": [0.1, 0.15],
                "steps": 3000,
                "train_cases": 194,
                "trainer_sha256": "sha256:" + "4" * 64,
            }
        },
        "timed_receipt": {
            "measurement": {"per_call_s": 0.012, "timing_s": {"inference": 0.01}}
        },
    }
    _sqlite(
        root / "owners" / "o1" / "tasks" / "direct-tasks.sqlite3",
        """
        CREATE TABLE direct_tasks(id TEXT PRIMARY KEY, request BLOB, view BLOB, cancellation TEXT);
        CREATE TABLE direct_evidence(id TEXT PRIMARY KEY, body BLOB);
        CREATE TABLE direct_infra_diagnosis(id TEXT PRIMARY KEY, body BLOB);
        """,
        [
            (
                "INSERT INTO direct_tasks VALUES(?,?,?,?)",
                [
                    (
                        TASK,
                        json.dumps({"recipe": {"ops": ["mlp"]}}).encode(),
                        _view("FAILED_INFRA", 1000.0, infra="INTERNAL"),
                        None,
                    ),
                    (
                        RERUN,
                        json.dumps({"recipe": {"ops": ["mlp"]}}).encode(),
                        _view("SUCCEEDED", 900.0),
                        None,
                    ),
                    (COPY, b"{}", _view("CANCELLED", 1100.0), "mcp-cancel-" + COPY),
                ],
            ),
            (
                "INSERT INTO direct_evidence VALUES(?,?)",
                [(RERUN, json.dumps(evidence).encode())],
            ),
            (
                "INSERT INTO direct_infra_diagnosis VALUES(?,?)",
                [
                    (
                        TASK,
                        json.dumps(
                            {
                                "failed_stage": "build",
                                "reason_code": "reconstruction.worker.runtime.failed",
                                "tail": "x" * 50,
                                "traceback": TRACEBACK,
                            }
                        ).encode(),
                    )
                ],
            ),
        ],
    )
    grade = root / "auto-grade"
    (grade / "markers").mkdir(parents=True)
    (grade / "markers" / (RERUN + ".json")).write_text(
        json.dumps({"state": "GRADED", "code": None})
    )
    (grade / "requeued").mkdir()
    (grade / "requeued" / "build-retries.jsonl").write_text(
        json.dumps({"from_task": TASK, "new_task": RERUN}) + "\n"
    )
    evaluation = grade / "artifacts" / (RERUN + ".evaluation")
    evaluation.mkdir(parents=True)
    (evaluation / "predictions.json").write_text("[[1.0]]")
    _sqlite(
        tmp_path / "pool.sqlite3",
        """
        CREATE TABLE models(model_id TEXT PRIMARY KEY, recipe_digest TEXT, seed INTEGER, state_digest TEXT,
            state BLOB, reconstruction TEXT);
        CREATE TABLE finals(final_id TEXT PRIMARY KEY, challenger TEXT, incumbent TEXT, finalist TEXT, frozen TEXT,
            state TEXT, outcome TEXT);
        CREATE TABLE incumbent(id INTEGER PRIMARY KEY, model_id TEXT, reason TEXT, since REAL);
        CREATE TABLE events(sequence INTEGER PRIMARY KEY, at REAL, kind TEXT, body TEXT);
        """,
        [
            (
                "INSERT INTO models VALUES(?,?,?,?,?,?)",
                [(RERUN, RECIPE, 0, "sha256:" + "1" * 64, b"STATEBLOB", "r")],
            ),
            (
                "INSERT INTO finals VALUES(?,?,?,?,?,?,?)",
                [("f1", RERUN, "king", None, "{}", "DONE", "kept")],
            ),
            ("INSERT INTO incumbent VALUES(?,?,?,?)", [(1, "king", "crowned", 5.0)]),
            (
                "INSERT INTO events VALUES(?,?,?,?)",
                [(1, 6.0, "crown", '{"score": 0.987654}')],
            ),
        ],
    )
    out = tmp_path / "cec"
    out.mkdir(mode=0o700)
    key = tmp_path / "owner.key"
    key.write_bytes(os.urandom(32))
    if os.name == "posix":
        os.chmod(out, 0o700)
        os.chmod(key, 0o600)
    return root, out, key, tmp_path / "pool.sqlite3"


def _digests(root):
    return {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(root).rglob("*"))
        if p.is_file()
    }


def test_one_row_per_submission_joins_recipe_build_grade_case_files_and_crown(state):
    root, out, key, pool = state
    counts = cec.build(root, out, key, pool_store=pool, decoders=DECODERS)
    db = sqlite3.connect(out / cec.CATALOG_NAME)
    row = dict(
        zip(
            [
                d[0]
                for d in db.execute(
                    "SELECT * FROM submissions WHERE submission_id=?", (RERUN,)
                ).description
            ],
            db.execute(
                "SELECT * FROM submissions WHERE submission_id=?", (RERUN,)
            ).fetchone(),
        )
    )
    assert (
        row["task_state"] == "SUCCEEDED"
        and row["rerun_of"] == TASK
        and row["recipe_digest"] == RECIPE
    )
    assert row["owner"].startswith("o:") and row["admitted_ns"] == 200
    failed = db.execute(
        "SELECT infra_class, failure_stage, failure_reason FROM submissions WHERE submission_id=?",
        (TASK,),
    ).fetchone()
    assert failed == ("INTERNAL", "build", "reconstruction.worker.runtime.failed")
    assert db.execute(
        "SELECT cancel_kind, copy_of FROM submissions WHERE submission_id=?", (COPY,)
    ).fetchone() == ("mcp-cancel-", RERUN)
    assert db.execute("SELECT recipe_json, first_seen_s FROM recipes").fetchone() == (
        '{"ops":["mlp"]}',
        900.0,
    )
    built = db.execute(
        "SELECT train_loss, steps, member_losses, per_call_s FROM builds"
    ).fetchone()
    assert built == (0.125, 3000, "[0.1,0.15]", 0.012)
    assert db.execute("SELECT status, lane_seconds FROM grades").fetchone() == (
        "SCORED",
        490.0,
    )
    assert db.execute("SELECT state FROM markers").fetchone() == ("GRADED",)
    assert (
        db.execute("SELECT relpath FROM objects")
        .fetchone()[0]
        .endswith(".evaluation/predictions.json")
    )
    assert db.execute("SELECT kind FROM crown_events").fetchone() == ("crown",)
    assert db.execute("SELECT model_id FROM crown_incumbent").fetchone() == ("king",)
    assert counts["submissions"] == 3 and counts["builds"] == 1
    db.close()


def test_never_a_hotkey_a_prediction_payload_a_traceback_a_state_blob_or_an_event_body(
    state,
):
    root, out, key, pool = state
    cec.build(root, out, key, pool_store=pool, decoders=DECODERS)
    raw = (out / cec.CATALOG_NAME).read_bytes()
    for secret in (
        HOTKEY,
        PREDICTIONS_B64[:40],
        TRACEBACK,
        "x" * 50,
        "STATEBLOB",
        "0.987654",
    ):
        assert secret.encode() not in raw


def test_the_sources_are_read_only_and_the_catalog_is_swapped_in_owner_only(state):
    root, out, key, pool = state
    before = _digests(root.parent.parent)
    cec.build(root, out, key, pool_store=pool, decoders=DECODERS)
    cec.build(
        root, out, key, pool_store=pool, decoders=DECODERS
    )  # a rebuild replaces it atomically
    after = {
        p: d for p, d in _digests(root.parent.parent).items() if out not in p.parents
    }
    assert after == {p: d for p, d in before.items() if out not in p.parents}
    assert [p.name for p in out.iterdir()] == [
        cec.CATALOG_NAME
    ]  # no temporary left behind
    if os.name == "posix":
        assert (out / cec.CATALOG_NAME).stat().st_mode & 0o077 == 0


def test_refusals_before_anything_is_written(state, tmp_path):
    root, out, key, pool = state
    with pytest.raises(cec.CatalogRefused, match="catalog_state_root_invalid"):
        cec.build(tmp_path / "nowhere", out, key, decoders=DECODERS)
    with pytest.raises(cec.CatalogRefused, match="catalog_out_inside_state"):
        inside = root / "cec"
        inside.mkdir(mode=0o700)
        if os.name == "posix":
            os.chmod(inside, 0o700)
        cec.build(root, inside, key, decoders=DECODERS)
    short = tmp_path / "short.key"
    short.write_bytes(b"k" * 8)
    if os.name == "posix":
        os.chmod(short, 0o600)
    with pytest.raises(cec.CatalogRefused, match="catalog_owner_key_short"):
        cec.build(root, out, short, decoders=DECODERS)
    if os.name == "posix":
        os.chmod(out, 0o755)
        with pytest.raises(cec.CatalogRefused, match="catalog_out_not_owner_only"):
            cec.build(root, out, key, decoders=DECODERS)
    assert not (out / cec.CATALOG_NAME).exists()
