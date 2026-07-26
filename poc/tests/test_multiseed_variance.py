"""Multi-seed variance — strategy quality should not be a single lucky nonce."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from poc.validator.run_once import run_once

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"

# Soft ceiling on combined-score std across nonces (protocol path)
MAX_STD_COMBINED = 0.35


def test_multiseed_variance_bounded(tmp_path):
    nonces = [10, 20, 30]
    scores = []
    evals = []
    for n in nonces:
        card = run_once(
            str(FIXTURES / "strategy_data_only.json"),
            local_nonce=n,
            run_id=f"var_{n}",
            artifacts_dir=tmp_path / str(n),
            fast=True,
        )
        scores.append(float(card["score"]["combined"]))
        evals.append(float(card["metrics"]["eval_rel_l2"]))

    std_s = float(np.std(scores))
    std_e = float(np.std(evals))
    # Record for debugging
    assert len(scores) == 3
    assert std_s <= MAX_STD_COMBINED, f"combined std={std_s} scores={scores}"
    # eval rel_l2 should also not explode across seeds
    assert std_e < 1.0, f"eval_rel_l2 std={std_e} values={evals}"


def test_different_nonces_different_data_hashes(tmp_path):
    a = run_once(
        str(FIXTURES / "strategy_data_only.json"),
        local_nonce=1,
        run_id="h1",
        artifacts_dir=tmp_path / "a",
        fast=True,
    )
    b = run_once(
        str(FIXTURES / "strategy_data_only.json"),
        local_nonce=2,
        run_id="h2",
        artifacts_dir=tmp_path / "b",
        fast=True,
    )
    # Local mode: nonce enters role seed → different train hashes
    assert a["seeds"]["train_hash"] != b["seeds"]["train_hash"]
