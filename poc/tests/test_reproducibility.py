"""T5 — Same strategy + seeds → stable score within tolerance."""

from pathlib import Path

from poc.validator.run_once import run_once

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def test_reproducible_combined(tmp_path):
    kwargs = dict(
        strategy_path=str(FIXTURES / "strategy_data_only.json"),
        local_nonce=42,
        run_id="repro",
        fast=True,
    )
    c1 = run_once(**kwargs, artifacts_dir=tmp_path / "a")
    c2 = run_once(**kwargs, artifacts_dir=tmp_path / "b")
    # Seeds must match
    assert c1["seeds"]["train"] == c2["seeds"]["train"]
    assert c1["seeds"]["eval"] == c2["seeds"]["eval"]
    # Combined within loose tolerance (FD training has RNG in batch index)
    # With fixed local_nonce and numpy state, should be close
    s1 = c1["score"]["combined"]
    s2 = c2["score"]["combined"]
    assert abs(s1 - s2) < 0.15 or (s1 == 0.0 and s2 == 0.0)
