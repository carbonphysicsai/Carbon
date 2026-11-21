"""Motor Specialist Bank PATH A v0 (`scripts/dev/bank_features.py`): the allow-list reader refuses every
hidden-derived catalog table and column by name (BANK contract rule 1), the output carries none of them, and the
recipe features / lineage come from the version's own graph adapter. Synthetic catalog only: no door, worker,
model, hidden value or GPUYard file.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import bank_features as bank  # noqa: E402
import evidence_catalog as cec  # noqa: E402

MOTOR, VERSION = "electric-motor-magnetics", "1.8"
HIDDEN = "HIDDEN-SENTINEL-must-never-leave"
OWNER_A, OWNER_B = "p" + "a" * 63, "p" + "b" * 63
R1, R2, R3 = ("sha256:" + c * 64 for c in "123")
G1, G2 = ("sha256:" + c * 64 for c in "ef")
HIDDEN_TABLES = (
    "grades",
    "markers",
    "gate_failures",
    "requeues",
    "pool_models",
    "crown_finals",
    "crown_incumbent",
    "crown_events",
    "objects",
)


def _recipe(graph, knobs):
    return {"source": {"kind": "graph", "submission_digest": graph}, "knobs": knobs}


def _fake_resolve(doc, challenge_id, version):
    """A stand-in for the adapter: one member whose knobs are the doc's, defaults lr 0.002 / steps 60."""
    if doc.get("knobs") is None:
        return (
            "graph_v2_training_value_invalid",
            "graph",
            doc["source"]["submission_digest"],
            None,
            None,
        )
    defaults = {"learning_rate": 0.002, "steps": 60}
    settings = {
        "train_fraction": 1.0,
        "output_weights": [1.0] * 8,
        "batch_size": 8,
        "ensemble": [
            {
                "outputs": list(range(8)),
                "weight": 1.0,
                "training": {**defaults, **doc["knobs"]},
            }
        ],
    }
    return None, "graph", doc["source"]["submission_digest"], settings, defaults


def _catalog(path, extra_column=False, schema=cec.SCHEMA):
    db = sqlite3.connect(path)
    db.executescript(cec.DDL)
    if extra_column:
        db.execute("ALTER TABLE builds ADD COLUMN score REAL")
    db.execute("INSERT INTO meta VALUES('schema', ?)", (schema,))
    recipes = [
        (R1, _recipe(G1, {})),
        (R2, _recipe(G1, {"learning_rate": 0.001})),
        (R3, _recipe(G2, None)),
    ]
    for i, (digest, doc) in enumerate(recipes):
        text = json.dumps(doc)
        db.execute(
            "INSERT INTO recipes VALUES(?,?,?,?,?,?)",
            (digest, MOTOR, VERSION, 100.0 + i, len(text), text),
        )
    subs = [
        ("rtsk_a1", OWNER_A, R1, 1),
        ("rtsk_a2", OWNER_A, R2, 2),
        ("rtsk_a3", OWNER_A, R3, 3),
        ("rtsk_b1", OWNER_B, R1, 1),
    ]
    for sid, owner, digest, ns in subs:
        db.execute(
            "INSERT INTO submissions(submission_id, challenge_id, version, owner, recipe_digest, request_sha256,"
            " admitted_ns, task_state, failure_reason) VALUES(?,?,?,?,?,?,?,?,?)",
            (sid, MOTOR, VERSION, owner, digest, HIDDEN, ns, "SUCCEEDED", HIDDEN),
        )
    db.execute(
        "INSERT INTO builds(submission_id, state_digest, train_loss, steps, practice_predictions_digest)"
        " VALUES('rtsk_a1', ?, 0.5, '[60]', ?)",
        (HIDDEN, HIDDEN),
    )
    for table in HIDDEN_TABLES:
        cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
        values = [HIDDEN if i else "rtsk_a1" for i in range(len(cols))]
        if table == "crown_events":
            values[0] = 1
        db.execute(f"INSERT INTO {table} VALUES({','.join('?' * len(cols))})", values)
    db.commit()
    db.close()


@pytest.fixture
def paths(tmp_path):
    src = tmp_path / "cec"
    src.mkdir()
    catalog = src / cec.CATALOG_NAME
    _catalog(catalog)
    out = tmp_path / "bank"
    out.mkdir(mode=0o700)
    if os.name == "posix":
        os.chmod(out, 0o700)
    return catalog, out


@pytest.mark.parametrize("table", HIDDEN_TABLES)
def test_every_hidden_derived_table_is_refused_by_name(paths, table):
    reader = bank.BankReader(paths[0])
    try:
        with pytest.raises(bank.BankRefused, match="table_not_allowed"):
            reader.rows(table, ("submission_id",))
    finally:
        reader.close()


@pytest.mark.parametrize(
    "table,column",
    [
        ("builds", "state_digest"),
        ("builds", "practice_predictions_digest"),
        ("submissions", "request_sha256"),
        ("submissions", "failure_reason"),
        ("recipes", "bytes"),
    ],
)
def test_a_column_outside_the_allow_list_is_refused_in_select_and_where(
    paths, table, column
):
    reader = bank.BankReader(paths[0])
    try:
        with pytest.raises(bank.BankRefused, match="column_not_allowed"):
            reader.rows(table, (column,))
        allowed = bank.ALLOWED[table][0]
        with pytest.raises(bank.BankRefused, match="column_not_allowed"):
            reader.rows(table, (allowed,), (column,), ("x",))
    finally:
        reader.close()


def test_the_allow_list_names_no_hidden_derived_table():
    assert not set(bank.ALLOWED) & set(HIDDEN_TABLES)
    assert set(bank.ALLOWED) == set(bank.EXPECTED)
    for table, columns in bank.ALLOWED.items():
        assert set(columns) <= bank.EXPECTED[table], table


def test_the_expected_columns_are_the_catalog_s_own(tmp_path):
    db = sqlite3.connect(tmp_path / "c.sqlite3")
    db.executescript(cec.DDL)
    for table, expected in bank.EXPECTED.items():
        assert {
            r[1] for r in db.execute(f"PRAGMA table_info({table})")
        } == expected, table
    db.close()


def test_schema_drift_or_an_unknown_catalog_is_refused_before_anything_is_written(
    tmp_path,
):
    out = tmp_path / "bank"
    out.mkdir(mode=0o700)
    drift = tmp_path / "drift.sqlite3"
    _catalog(drift, extra_column=True)
    with pytest.raises(bank.BankRefused, match="catalog_schema_drift"):
        bank.build(drift, out, MOTOR, VERSION, resolve=_fake_resolve)
    other = tmp_path / "other.sqlite3"
    _catalog(other, schema="carbon.evidence-catalog.v9")
    with pytest.raises(bank.BankRefused, match="catalog_schema_unknown"):
        bank.build(other, out, MOTOR, VERSION, resolve=_fake_resolve)
    with pytest.raises(bank.BankRefused, match="catalog_missing"):
        bank.build(
            tmp_path / "absent.sqlite3", out, MOTOR, VERSION, resolve=_fake_resolve
        )
    assert list(out.iterdir()) == []


def test_features_outcomes_and_lineage_carry_no_hidden_value(paths):
    catalog, out = paths
    counts = bank.build(catalog, out, MOTOR, VERSION, resolve=_fake_resolve)
    path = out / bank.BANK_NAME
    assert HIDDEN.encode() not in path.read_bytes()
    db = sqlite3.connect(path)
    tables = {
        r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert tables == {"meta", "recipe_features", "member_knobs", "outcomes", "lineage"}
    assert counts["recipes"] == 3
    assert counts["refused_by_adapter"] == {"graph_v2_training_value_invalid": 1}
    assert counts["nondefault_knobs"] == {"learning_rate": 1}
    assert counts["outcomes"] == 4 and counts["outcomes_with_build"] == 1
    assert counts["owners"] == 2 and counts["lineage_edges"] == 2
    knobs = dict(db.execute("SELECT recipe_digest, nondefault FROM member_knobs"))
    assert json.loads(knobs[R1]) == [] and json.loads(knobs[R2]) == ["learning_rate"]
    lineage = {
        r[0]: r[1:]
        for r in db.execute(
            "SELECT submission_id, seq, prev_recipe_digest, same_recipe,"
            " graph_changed, changed_knobs FROM lineage"
        )
    }
    assert lineage["rtsk_a1"] == (0, None, None, None, None)
    assert lineage["rtsk_a2"] == (1, R1, 0, 0, json.dumps(["learning_rate"]))
    # the next recipe was refused by the adapter: its graph change is known, its knob change is not
    assert lineage["rtsk_a3"] == (2, R2, 0, 1, None)
    assert lineage["rtsk_b1"] == (0, None, None, None, None)
    built = db.execute(
        "SELECT train_loss, steps FROM outcomes WHERE submission_id='rtsk_a1'"
    ).fetchone()
    assert built == (0.5, "[60]")
    db.close()


def test_the_catalog_is_opened_read_only_and_the_output_never_lands_beside_it(
    paths, tmp_path
):
    catalog, out = paths
    before = catalog.read_bytes()
    bank.build(catalog, out, MOTOR, VERSION, resolve=_fake_resolve)
    assert catalog.read_bytes() == before
    reader = bank.BankReader(catalog)
    try:
        with pytest.raises(sqlite3.OperationalError):
            reader._db.execute("DELETE FROM recipes")
    finally:
        reader.close()
    beside = catalog.parent
    if os.name == "posix":
        os.chmod(beside, 0o700)
    with pytest.raises(bank.BankRefused, match="out_dir_is_catalog_dir"):
        bank.build(catalog, beside, MOTOR, VERSION, resolve=_fake_resolve)


@pytest.mark.skipif(os.name != "posix", reason="owner-only modes are POSIX")
def test_an_output_dir_others_can_read_is_refused(paths):
    catalog, out = paths
    os.chmod(out, 0o755)
    with pytest.raises(bank.BankRefused, match="out_dir_not_owner_only"):
        bank.build(catalog, out, MOTOR, VERSION, resolve=_fake_resolve)
    os.chmod(out, 0o700)
    bank.build(catalog, out, MOTOR, VERSION, resolve=_fake_resolve)
    assert os.stat(out / bank.BANK_NAME).st_mode & 0o077 == 0


def test_stdout_is_counts_only(paths, capsys, monkeypatch):
    catalog, out = paths
    monkeypatch.setattr(bank, "_resolve", _fake_resolve)
    rc = bank.main(
        [
            "--catalog",
            str(catalog),
            "--out",
            str(out),
            "--challenge-id",
            MOTOR,
            "--version",
            VERSION,
        ]
    )
    text = capsys.readouterr().out
    assert rc == 0
    for forbidden in ("sha256:", "rtsk_", OWNER_A, OWNER_B, HIDDEN):
        assert forbidden not in text


def test_the_real_motor_18_adapter_resolves_a_default_and_a_changed_recipe():
    from carbon.development_session import graph_adapters

    graph = "sha256:" + "0" * 64
    default = graph_adapters.graph_recipe(MOTOR, VERSION, graph)
    changed = graph_adapters.graph_recipe(
        MOTOR, VERSION, graph, configuration={"training": {"learning_rate": 0.001}}
    )
    code, kind, digest, settings, defaults = bank._resolve(default, MOTOR, VERSION)
    assert (code, kind, digest) == (None, "graph", graph)
    assert len(settings["ensemble"]) == 1
    member = settings["ensemble"][0]["training"]
    assert not [k for k in member if member[k] != defaults[k]]
    code, _, _, settings, defaults = bank._resolve(changed, MOTOR, VERSION)
    member = settings["ensemble"][0]["training"]
    assert code is None and [k for k in member if member[k] != defaults[k]] == [
        "learning_rate"
    ]
    bad = graph_adapters.graph_recipe(
        MOTOR, VERSION, graph, configuration={"training": {"learning_rate": "fast"}}
    )
    code, _, _, settings, _ = bank._resolve(bad, MOTOR, VERSION)
    assert settings is None and code.endswith("training_value_invalid")
