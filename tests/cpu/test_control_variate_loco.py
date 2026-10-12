"""CONTROL-VARIATE-PREDICT-01: the METHOD-ONLY leave-one-out fit (numpy only)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from scripts.dev.control_variate import loco_fit_on_pairs as loco


def _data():
    rng = np.random.default_rng(7)
    x = rng.uniform(size=(40, 3))
    y = np.stack([1.0 + 2.0 * x[:, 0] - x[:, 1], 3.0 * x[:, 2] ** 2], 1)
    return x, y


def test_ridge_recovers_a_quadratic_out_of_sample():
    x, y = _data()
    pred = loco.holdout("ridge", x, y, list(range(len(x))))
    assert np.abs(pred - y).max() < 0.1


def test_every_method_is_deterministic_and_leaves_the_case_out():
    x, y = _data()
    for method in ("krr", "knn", "ridge"):
        a = loco.holdout(method, x, y, list(range(len(x))))
        b = loco.holdout(method, x, y, list(range(len(x))))
        assert np.array_equal(a, b)
    # a held-out case never sees its own label: shifting one label moves
    # that case's prediction by nothing
    y2 = y.copy()
    y2[0] += 100.0
    p = loco.holdout("krr", x, y, list(range(len(x))))
    p2 = loco.holdout("krr", x, y2, list(range(len(x))))
    assert np.array_equal(p[0], p2[0])


def test_group_holdout_removes_the_whole_group():
    x, y = _data()
    groups = [i % 4 for i in range(len(x))]
    y2 = y.copy()
    y2[[i for i, g in enumerate(groups) if g == 0]] += 50.0
    p = loco.holdout("knn", x, y, groups)
    p2 = loco.holdout("knn", x, y2, groups)
    zero = [i for i, g in enumerate(groups) if g == 0]
    assert np.array_equal(p[zero], p2[zero])


def test_rho_is_one_when_the_rungs_differ_by_a_constant_and_skips_constants():
    rng = np.random.default_rng(1)
    coarse = rng.normal(size=(60, 2))
    fine = coarse + 0.001
    preds = {
        "a": coarse + rng.normal(scale=0.1, size=coarse.shape),
        "b": coarse + rng.normal(scale=0.3, size=coarse.shape),
    }
    fine[:, 1] = 4.2  # a constant reference: no rho
    coarse[:, 1] = 4.2
    report = loco.rho_report(preds, coarse, fine, ("m", "const"))
    assert report["m"]["rho"] > 0.99
    assert report["const"]["rho"] is None


def test_a_manifest_digest_mismatch_refuses(tmp_path):
    (tmp_path / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema": "carbon.two-rung-pairs.v1",
                "scope": "PUBLIC_DEVELOPMENT (x)",
                "files": {
                    "battery-pairs.jsonl": {"rows": 0, "sha256": "0" * 64},
                    "motor-pairs.jsonl": {"rows": 0, "sha256": "0" * 64},
                },
            }
        )
    )
    (tmp_path / "battery-pairs.jsonl").write_text("")
    (tmp_path / "motor-pairs.jsonl").write_text("")
    with pytest.raises(SystemExit, match="DIGEST MISMATCH"):
        loco.load(tmp_path)
