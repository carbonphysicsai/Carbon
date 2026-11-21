"""Motor Specialist Bank PATH A v1 (`scripts/dev/bank_graph_features.py`): graph-level COUNTS from each task's
retained envelope, found by the hashed task id, digest-checked against its owner's row, parsed by the door's own
staging parser; no constant value, document, input name or owner directory name reaches the bank file or stdout.
Synthetic state and documents only.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import bank_features
import bank_graph_features as graphs

from carbon.level4 import staging, submission

SECRET = b"FITTED-CONSTANT-VALUE-SENTINEL"
INPUT_NAME = "secret_input_name_sentinel"
OWNER_DIR = "owner_dir_name_sentinel"
OPS = frozenset({"add", "mul"})


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _forward(extra_op="add"):
    return {
        "schema": "carbon.development.level4-graph.v0",
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {
                        "value": 0,
                        "name": INPUT_NAME,
                        "dtype": "float64",
                        "shape": [1, 8],
                    },
                    {
                        "value": 5,
                        "name": "params/0",
                        "dtype": "float64",
                        "shape": [3, 4],
                    },
                ],
                "constants": [
                    {
                        "value": 1,
                        "dtype": "float64",
                        "shape": [2, 3],
                        "bytes": 48,
                        "data": base64.b64encode(SECRET).decode(),
                    }
                ],
                "nodes": [
                    {"op": "add", "in": [0, 1], "out": [{"value": 2}], "params": {}},
                    {"op": "mul", "in": [2, 2], "out": [{"value": 3}], "params": {}},
                    {"op": extra_op, "in": [3, 3], "out": [{"value": 4}], "params": {}},
                ],
                "outputs": [4],
            },
            "helper": {"inputs": [], "constants": [], "nodes": [], "outputs": []},
        },
    }


def _envelope(forward):
    fwd = _canon(forward)
    init_spec = _canon({"parameters": [{"input": "params/0"}, {"input": "params/1"}]})
    files = {submission.name(fwd): fwd, submission.name(init_spec): init_spec}
    manifest = _canon(
        {
            "documents": {
                "forward": submission.name(fwd),
                "init_spec": submission.name(init_spec),
            }
        }
    )
    return _canon(staging.envelope(manifest, files))


def _task(i):
    return "rtsk_" + format(i, "064x")


@pytest.fixture
def world(tmp_path):
    state = tmp_path / "state"
    owner = state / "owners" / OWNER_DIR
    sources = owner / "ledger" / "direct-task-sources"
    sources.mkdir(parents=True)
    (owner / "tasks").mkdir()
    envelopes = {
        _task(1): _envelope(_forward()),
        _task(2): _envelope(_forward("secret_op_name")),
        _task(3): _envelope(_forward()),  # digest row will not match
        _task(4): b"{not json",
    }
    rows = []
    for sid, raw in envelopes.items():
        (sources / (hashlib.sha256(sid.encode()).hexdigest() + ".json")).write_bytes(
            raw
        )
        digest = (
            "sha256:" + hashlib.sha256(raw if sid != _task(3) else b"other").hexdigest()
        )
        rows.append((sid, b"", digest))
    rows.append((_task(6), b"", "sha256:" + "0" * 64))  # a row with no file
    db = sqlite3.connect(owner / "tasks" / "direct-tasks.sqlite3")
    db.execute(
        "CREATE TABLE direct_task_sources(id TEXT PRIMARY KEY, body BLOB, digest TEXT)"
    )
    db.executemany("INSERT INTO direct_task_sources VALUES(?,?,?)", rows)
    db.commit()
    db.close()
    bank_dir = tmp_path / "bank"
    bank_dir.mkdir(mode=0o700)
    bank = bank_dir / bank_features.BANK_NAME
    db = sqlite3.connect(bank)
    db.executescript(bank_features.DDL)
    db.executemany(
        "INSERT INTO meta VALUES(?,?)",
        [
            ("schema", bank_features.SCHEMA),
            ("challenge_id", "electric-motor-magnetics"),
            ("version", "1.8"),
        ],
    )
    for i in (1, 2, 3, 4, 5, 6):
        db.execute(
            "INSERT INTO outcomes(submission_id, recipe_digest) VALUES(?,?)",
            (_task(i), "sha256:" + str(i) * 64),
        )
    db.commit()
    db.close()
    if os.name == "posix":
        os.chmod(bank, 0o600)
    return bank, state


def test_counts_per_role_from_each_digest_checked_envelope(world):
    bank, state = world
    counts = graphs.build(bank, state, ops=OPS)
    assert counts["recipes_with_graph"] == 2
    assert (
        counts["missing_file"] == 2
    )  # tasks 5 and 6: no file (6 has a row), never inferred
    assert counts["missing_row"] == 0
    assert counts["refused"] == {"digest_mismatch": 1, "envelope_invalid": 1}
    assert counts["op_totals"] == {"add": 3, "mul": 2, "other": 1}
    db = sqlite3.connect(bank)
    rows = {
        (r[0][-1], r[1]): r[2:]
        for r in db.execute(
            "SELECT recipe_digest, role, graphs, nodes, constants, constant_elements, constant_bytes, inputs,"
            " outputs, parameters, ops FROM graph_features"
        )
    }
    assert rows[("1", "forward")] == (
        2,
        3,
        1,
        6,
        48,
        2,
        1,
        0,
        json.dumps({"add": 2, "mul": 1}),
    )
    # the entry graph's trained-array input: counted with its elements, its name never kept
    assert db.execute(
        "SELECT param_inputs, param_elements FROM graph_features"
        " WHERE role='forward' AND recipe_digest=?",
        ("sha256:" + "1" * 64,),
    ).fetchone() == (1, 12)
    assert rows[("1", "init_spec")][7] == 2
    assert json.loads(rows[("2", "forward")][8]) == {"add": 1, "mul": 1, "other": 1}
    db.close()


def test_no_value_document_name_or_owner_dir_leaves_the_envelope(world):
    bank, state = world
    counts = graphs.build(bank, state, ops=OPS)
    blob = bank.read_bytes()
    for secret in (
        SECRET,
        base64.b64encode(SECRET),
        INPUT_NAME.encode(),
        OWNER_DIR.encode(),
        b"secret_op_name",
    ):
        assert secret not in blob
    text = json.dumps(counts)
    for secret in (INPUT_NAME, OWNER_DIR, "secret_op_name", "rtsk_", "sha256:"):
        assert secret not in text


def test_the_state_is_only_read(world):
    bank, state = world
    before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
    graphs.build(bank, state, ops=OPS)
    after = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
    assert before == after


def test_a_rerun_replaces_the_table(world):
    bank, state = world
    graphs.build(bank, state, ops=OPS)
    graphs.build(bank, state, ops=OPS)
    db = sqlite3.connect(bank)
    assert db.execute("SELECT COUNT(*) FROM graph_features").fetchone()[0] == 4
    db.close()


def test_an_unknown_bank_file_or_a_missing_state_is_refused(world, tmp_path):
    bank, state = world
    with pytest.raises(graphs.BankRefused, match="state_owners_missing"):
        graphs.build(bank, tmp_path / "nowhere", ops=OPS)
    other = tmp_path / "other.sqlite3"
    db = sqlite3.connect(other)
    db.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)")
    db.execute("INSERT INTO meta VALUES('schema','carbon.evidence-catalog.v0')")
    db.commit()
    db.close()
    if os.name == "posix":
        os.chmod(other, 0o600)
    with pytest.raises(graphs.BankRefused, match="bank_file_unknown"):
        graphs.build(other, state, ops=OPS)


@pytest.mark.skipif(os.name != "posix", reason="owner-only modes are POSIX")
def test_a_bank_file_others_can_read_is_refused(world):
    bank, state = world
    os.chmod(bank, 0o644)
    with pytest.raises(graphs.BankRefused, match="bank_file_not_owner_only"):
        graphs.build(bank, state, ops=OPS)


def test_the_motor_18_served_allowlist_names_its_ops():
    ops = graphs.served_ops("electric-motor-magnetics", "1.8")
    assert ops and all(isinstance(o, str) for o in ops)
    with pytest.raises(graphs.BankRefused, match="adapter_unregistered"):
        graphs.served_ops("no-such-challenge", "0.0")
