"""SHORTCUT PANEL TRAINER: every member fits a smooth function in range, the sparse search recovers an exact power law, the
choice is deterministic and never reads the query, and the CLI writes the files its record names. Synthetic data only.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

TOOLS = Path(__file__).resolve().parents[2] / "scripts/dev/exam_reads"
sys.path.insert(0, str(TOOLS))

import shortcut_panel as sp


def _smooth(X):
    return np.stack(
        [
            1.0 + 2.0 * X[:, 0] - X[:, 1] ** 2 + 0.5 * X[:, 0] * X[:, 2],
            np.sin(X[:, 1]) + X[:, 2],
        ],
        axis=1,
    )


def _data(n=120, nq=60, d=3, seed=0):
    rng = np.random.default_rng(seed)
    return rng.uniform(-1, 1, (n, d)), rng.uniform(-1, 1, (nq, d))


@pytest.mark.parametrize(
    "member,limit",
    [
        ("gp", 0.05),
        ("poly_ridge", 0.05),
        ("rbf_ridge", 0.1),
        ("gbm", 0.45),
        ("knn", 0.5),
        ("sparse_physics", 0.5),
    ],
)
def test_member_fits_a_smooth_function_in_range(member, limit):
    X, Q = _data()
    Y = _smooth(X)
    pred, record = sp.fit_predict(member, X, Y, Q, seed=0)
    truth = _smooth(Q)
    assert pred.shape == truth.shape and pred.dtype == np.float64
    rel = np.sqrt(((pred - truth) ** 2).mean(axis=0)) / truth.std(axis=0)
    assert (rel < limit).all(), (member, rel)
    assert (
        record["member"] == member and record["seed"] == 0 and record["cv_folds"] == 5
    )
    assert np.isfinite(record["cv_score"])
    json.dumps(record, allow_nan=False)


def test_sparse_physics_recovers_an_exact_power_law():
    rng = np.random.default_rng(1)
    X = rng.uniform(0.5, 2.0, (80, 2))
    Q = rng.uniform(0.5, 4.0, (30, 2))
    pred, record = sp.fit_predict(
        "sparse_physics", X, 3.0 * X[:, :1] ** 2 / X[:, 1:], Q, seed=3
    )
    selected = record["hyperparameters"]["selected_terms"][0]
    assert selected["space"] == "log"
    terms = {t["term"]: t["coef"] for t in selected["terms"]}
    assert set(terms) == {"1", "log(x0)", "log(x1)"}
    assert terms["1"] == pytest.approx(np.log(3.0), abs=1e-6)
    assert terms["log(x0)"] == pytest.approx(2.0, abs=1e-6) and terms[
        "log(x1)"
    ] == pytest.approx(-1.0, abs=1e-6)
    np.testing.assert_allclose(pred[:, 0], 3.0 * Q[:, 0] ** 2 / Q[:, 1], rtol=1e-6)


def test_cv_picks_a_degree_above_one_for_a_quadratic():
    X, Q = _data(n=80, d=2)
    Y = (X[:, 0] ** 2 + X[:, 0] * X[:, 1])[:, None]
    pred, record = sp.fit_predict("poly_ridge", X, Y, Q, seed=0)
    assert record["hyperparameters"]["degree"] > 1
    np.testing.assert_allclose(
        pred, (Q[:, 0] ** 2 + Q[:, 0] * Q[:, 1])[:, None], atol=1e-3
    )


@pytest.mark.parametrize("member", sp.MEMBER_NAMES)
def test_deterministic_and_query_independent(member):
    X, Q = _data(n=50, nq=10)
    Y = _smooth(X)
    first = sp.fit_predict(member, X, Y, Q, seed=7)
    again = sp.fit_predict(member, X, Y, Q, seed=7)
    np.testing.assert_array_equal(first[0], again[0])
    assert first[1] == again[1]
    # a different query (values and row count) leaves the record, and the shared rows' predictions, unchanged
    other = np.vstack([Q[:5], np.random.default_rng(9).uniform(-3, 3, (4, 3))])
    changed = sp.fit_predict(member, X, Y, other, seed=7)
    assert json.dumps(first[1], sort_keys=True) == json.dumps(
        changed[1], sort_keys=True
    )
    np.testing.assert_allclose(first[0][:5], changed[0][:5], rtol=1e-12, atol=1e-12)


def test_kernel_members_subsample_above_the_row_cap(monkeypatch):
    monkeypatch.setattr(sp, "MAX_KERNEL_ROWS", 40)
    X, Q = _data(n=60, nq=5)
    _, record = sp.fit_predict("rbf_ridge", X, _smooth(X), Q, seed=2)
    assert record["n_train"] == 60 and record["n_rows_used"] == 40
    _, other = sp.fit_predict("knn", X, _smooth(X), Q, seed=2)
    assert other["n_rows_used"] == 60


def test_refusals():
    X, Q = _data(n=30, nq=5)
    Y = _smooth(X)
    bad = X.copy()
    bad[3, 1] = np.nan
    cases = [
        (bad, Y, Q),
        (X, np.where(np.arange(30)[:, None] == 2, np.inf, Y), Q),
        (X, Y, np.where(np.arange(5)[:, None] == 1, np.nan, Q)),
        (X, Y[:-1], Q),
        (X, Y, Q[:, :2]),
        (X[:4], Y[:4], Q),
    ]
    for args in cases:
        with pytest.raises(sp.Refused):
            sp.fit_predict("knn", *args, seed=0)
    with pytest.raises(sp.Refused):
        sp.fit_predict("magic", X, Y, Q, seed=0)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.mark.parametrize("keys", [("inputs", "targets"), ("X", "Y")])
def test_cli_writes_files_with_matching_hashes(tmp_path, keys):
    X, Q = _data(n=40, nq=7)
    train, query, out = tmp_path / "train.npz", tmp_path / "query.npy", tmp_path / "out"
    np.savez(train, **{keys[0]: X.astype(np.float32), keys[1]: _smooth(X)})
    np.save(query, Q)
    assert (
        sp.main(
            [
                "fit",
                "--train",
                str(train),
                "--query",
                str(query),
                "--members",
                "poly_ridge,knn",
                "--seed",
                "4",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    record = json.loads((out / "panel-record.json").read_text(encoding="utf-8"))
    assert (
        record["schema"] == "carbon.exam-reads.shortcut-panel.v1"
        and record["seed"] == 4
    )
    assert record["train_sha256"] == _sha(train) and record["query_sha256"] == _sha(
        query
    )
    assert set(record["members"]) == {"poly_ridge", "knn"}
    for name, rec in record["members"].items():
        rows = np.load(out / f"{name}.npy")
        assert rows.dtype == np.float64 and rows.shape == (7, 2)
        assert rec["rows_sha256"] == _sha(out / f"{name}.npy") and rec["member"] == name


def test_cli_refuses_a_train_file_without_known_keys(tmp_path):
    np.savez(tmp_path / "t.npz", a=np.zeros((9, 2)), b=np.zeros((9, 1)))
    np.save(tmp_path / "q.npy", np.zeros((2, 2)))
    code = sp.main(
        [
            "fit",
            "--train",
            str(tmp_path / "t.npz"),
            "--query",
            str(tmp_path / "q.npy"),
            "--out",
            str(tmp_path / "o"),
        ]
    )
    assert code == 2


# ---------------------------------------------------------------- strong-config


def _panel_dir(tmp_path, nq=7):
    rng = np.random.default_rng(3)
    X = rng.uniform(-1, 1, (40, 3))
    np.savez(tmp_path / "t.npz", inputs=X, targets=_smooth(X))
    np.save(tmp_path / "q.npy", rng.uniform(-1, 1, (nq, 3)))
    out = tmp_path / "panel"
    sp.run_panel(
        tmp_path / "t.npz", tmp_path / "q.npy", ["knn", "sparse_physics"], 0, out
    )
    np.save(tmp_path / "eng.npy", np.zeros((nq, 2)))
    np.save(tmp_path / "def.npy", np.ones((nq, 2)))
    return out


def _config_args(tmp_path):
    return [
        "strong-config",
        "--panel-dir",
        str(tmp_path / "panel"),
        "--query",
        str(tmp_path / "q.npy"),
        "--extra",
        f"eng:engineer_shortcut:{tmp_path / 'eng.npy'}",
        "--default",
        f"def:{tmp_path / 'def.npy'}",
        "--draws",
        "5",
        "--seed",
        "2",
        "--out",
        str(tmp_path / "strong.json"),
    ]


def test_strong_config_loads_with_load_strong(tmp_path):
    _panel_dir(tmp_path)
    assert sp.main(_config_args(tmp_path)) == 0
    import q3_q8_whatif as reads

    document = reads.load_strong(tmp_path / "strong.json")
    kinds = {e["name"]: e["kind"] for e in document["panel"]}
    assert kinds == {
        "knn": "generic_fit",
        "sparse_physics": "physics_regression",
        "eng": "engineer_shortcut",
    }
    for entry in document["panel"] + [document["default_model"]]:
        assert entry["sha256"] == _sha(entry["rows_npy"])
    assert document["ceiling"] == {"draws": 5, "seed": 2}
    assert b"\r" not in (tmp_path / "strong.json").read_bytes()


def _refused(tmp_path, capsys, expect, args=None):
    assert sp.main(args or _config_args(tmp_path)) == 2
    assert expect in capsys.readouterr().err
    assert not (tmp_path / "strong.json").exists()


def test_strong_config_refuses_an_existing_out_path(tmp_path, capsys):
    _panel_dir(tmp_path)
    (tmp_path / "strong.json").write_text("keep", encoding="utf-8")
    assert sp.main(_config_args(tmp_path)) == 2
    assert "out_path_exists" in capsys.readouterr().err
    assert (tmp_path / "strong.json").read_text(encoding="utf-8") == "keep"


def test_strong_config_refuses_a_row_count_mismatch(tmp_path, capsys):
    _panel_dir(tmp_path)
    np.save(tmp_path / "eng.npy", np.zeros((6, 2)))
    _refused(tmp_path, capsys, "row_count_differs_from_query:eng")


def test_strong_config_refuses_a_changed_member_rows_file(tmp_path, capsys):
    _panel_dir(tmp_path)
    np.save(tmp_path / "panel" / "knn.npy", np.zeros((7, 2)))
    _refused(tmp_path, capsys, "rows_sha256_differs_from_panel_record:knn")


def test_strong_config_refuses_a_different_query(tmp_path, capsys):
    _panel_dir(tmp_path)
    np.save(tmp_path / "q.npy", np.zeros((7, 3)))
    _refused(tmp_path, capsys, "query_sha256_differs_from_panel_record")


def test_strong_config_refuses_a_repeated_name(tmp_path, capsys):
    _panel_dir(tmp_path)
    args = _config_args(tmp_path)
    args[args.index("--extra") + 1] = f"knn:previous_king:{tmp_path / 'eng.npy'}"
    _refused(tmp_path, capsys, "name_repeats:knn", args)
    args = _config_args(tmp_path)
    args[args.index("--default") + 1] = f"eng:{tmp_path / 'def.npy'}"
    _refused(tmp_path, capsys, "name_repeats:eng", args)
