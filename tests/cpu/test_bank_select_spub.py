"""Motor Specialist Bank S-PUB selection (`scripts/dev/bank_select_spub.py`): public-signal eligibility, strata by
structure presence, one recipe per owner per stratum by public train loss, small strata pooled, every eligible recipe
ranked (K is never applied here), stdout counts only. Synthetic bank file only.
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

import bank_features
import bank_graph_features
import bank_select_spub as spub

SOLVER = {"sin": 3, "cholesky": 2, "mul": 9}
PLAIN = {"add": 1}


def _d(i):
    return "sha256:" + format(i, "064x")


#  digest, owner, loss, state, infra, copy_of, device, parse_code, forward ops, steps, params
RECIPES = [
    (1, "A", 0.10, "SUCCEEDED", None, None, "GPU", None, SOLVER, 60, 4),
    (2, "A", 0.05, "SUCCEEDED", None, None, "GPU", None, SOLVER, 60, 4),
    (3, "B", 0.20, "SUCCEEDED", None, None, "CPU", None, SOLVER, 60, 4),
    (4, "C", 0.30, "SUCCEEDED", None, None, "GPU", None, SOLVER, 60, 4),
    (5, "D", 0.40, "SUCCEEDED", None, None, "GPU", None, PLAIN, 1, 0),
    (6, "E", 0.01, "FAILED", None, None, "GPU", None, SOLVER, 60, 4),
    (7, "F", 0.01, "SUCCEEDED", "box_lost", None, "GPU", None, SOLVER, 60, 4),
    (8, "G", 0.01, "SUCCEEDED", None, "rtsk_x", "GPU", None, SOLVER, 60, 4),
    (
        9,
        "H",
        None,
        None,
        None,
        None,
        None,
        "graph_v2_training_value_invalid",
        None,
        None,
        None,
    ),
    (10, "I", 0.01, "SUCCEEDED", None, None, "GPU", None, None, 60, 4),
]


@pytest.fixture
def bank(tmp_path):
    path = tmp_path / "bank.sqlite3"
    db = sqlite3.connect(path)
    db.executescript(bank_features.DDL)
    db.executescript(bank_graph_features.DDL)
    db.executemany(
        "INSERT INTO meta VALUES(?,?)",
        [
            ("schema", bank_features.SCHEMA),
            ("graph_features_schema", bank_graph_features.SCHEMA),
        ],
    )
    for i, owner, loss, state, infra, copy, device, code, ops, steps, params in RECIPES:
        db.execute(
            "INSERT INTO recipe_features(recipe_digest, parse_code, members, first_seen_s) VALUES(?,?,?,?)",
            (_d(i), code, None if code else 1, float(i)),
        )
        sid = f"rtsk_{i}"
        db.execute(
            "INSERT INTO outcomes(submission_id, recipe_digest, task_state, infra_class, copy_of, build_device,"
            " train_loss) VALUES(?,?,?,?,?,?,?)",
            (sid, _d(i), state, infra, copy, device, loss),
        )
        db.execute(
            "INSERT INTO lineage(submission_id, owner, seq) VALUES(?,?,0)", (sid, owner)
        )
        if steps is not None:
            db.execute(
                "INSERT INTO member_knobs(recipe_digest, member, knobs) VALUES(?,0,?)",
                (_d(i), json.dumps({"steps": steps})),
            )
        if ops is not None:
            db.execute(
                "INSERT INTO graph_features(recipe_digest, role, ops) VALUES(?,'forward',?)",
                (_d(i), json.dumps(ops)),
            )
            db.execute(
                "INSERT INTO graph_features(recipe_digest, role, parameters) VALUES(?,'init_spec',?)",
                (_d(i), params),
            )
    db.commit()
    db.close()
    if os.name == "posix":
        os.chmod(path, 0o600)
    return path


def test_public_eligibility_one_per_owner_ranking_and_pooling(bank):
    counts = spub.build(bank)
    assert counts["eligible"] == 5
    assert counts["ineligible"] == {
        "no_public_success": 3,
        "adapter_refused": 1,
        "no_graph": 1,
    }
    solver = "linsolve+trig|m1-sn-pn"
    assert counts["strata"] == {
        solver: {"eligible": 4, "ranked": 3, "cpu_built_ranked": 1},
        # the lone plain recipe pools into 'other' (V2 >= 3 rule)
        "other": {"eligible": 1, "ranked": 1, "cpu_built_ranked": 0},
    }
    db = sqlite3.connect(bank)
    rows = db.execute(
        "SELECT recipe_digest, stratum, rank, cpu_built FROM selection_spub ORDER BY stratum, rank"
    )
    assert [(r[0][-1], r[1], r[2], r[3]) for r in rows] == [
        ("2", solver, 0, 0),  # owner A's better recipe; A's other one is not ranked
        ("3", solver, 1, 1),
        ("4", solver, 2, 0),
        ("5", "other", 0, 0),
    ]
    assert (
        dict(db.execute("SELECT k, v FROM meta"))["selection_spub_caveat"]
        == spub.CAVEAT
    )
    db.close()


def test_stdout_is_counts_only_and_carries_the_caveat(bank, capsys):
    assert spub.main(["--bank", str(bank)]) == 0
    text = capsys.readouterr().out
    assert "not uncontaminated" in text
    for forbidden in ("sha256:", "rtsk_", '"A"', "0.05"):
        assert forbidden not in text


def test_a_rerun_replaces_the_table(bank):
    spub.build(bank)
    spub.build(bank)
    db = sqlite3.connect(bank)
    assert db.execute("SELECT COUNT(*) FROM selection_spub").fetchone()[0] == 4
    db.close()


def test_a_bank_file_without_graph_features_is_refused(tmp_path):
    path = tmp_path / "b.sqlite3"
    db = sqlite3.connect(path)
    db.executescript(bank_features.DDL)
    db.execute("INSERT INTO meta VALUES('schema', ?)", (bank_features.SCHEMA,))
    db.commit()
    db.close()
    if os.name == "posix":
        os.chmod(path, 0o600)
    with pytest.raises(spub.BankRefused, match="bank_file_incomplete"):
        spub.build(path)


@pytest.mark.parametrize(
    "ops,signature",
    [
        ({"add": 1}, "plain"),
        ({"fft": 1, "scan": 2}, "loops+spectral"),
        ({"dot_general": 4, "tanh": 2}, "learned"),
        ({"dot_general": 4}, "plain"),
        ({"cholesky": 0, "sin": 1}, "trig"),
    ],
)
def test_backbone_is_op_group_presence_only(ops, signature):
    assert spub.backbone(ops) == signature


def test_training_family_is_presence_only():
    assert spub.training_family(1, 1, 0) == "m1-s1-p0"
    assert spub.training_family(4, 200, 12) == "mn-sn-pn"
    assert spub.training_family(None, None, None) == "m1-s1-p0"


def test_the_selector_reads_no_hidden_derived_name():
    source = (ROOT / "scripts" / "dev" / "bank_select_spub.py").read_text(
        encoding="utf-8"
    )
    code = source.split('"""', 2)[2]
    for word in (
        "grade",
        "score",
        "crown",
        "gate_fail",
        "ladder",
        "marker",
        "pool_model",
    ):
        assert word not in code.lower()
