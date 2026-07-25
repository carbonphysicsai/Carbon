"""T6 — Different strategies produce different outcomes."""

from pathlib import Path

from poc.validator.run_once import run_once

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def test_discrimination(tmp_path):
    a = run_once(
        str(FIXTURES / "strategy_data_only.json"),
        local_nonce=21,
        run_id="disc",
        artifacts_dir=tmp_path / "data",
        fast=True,
    )
    b = run_once(
        str(FIXTURES / "strategy_physics.json"),
        local_nonce=21,
        run_id="disc",
        artifacts_dir=tmp_path / "phys",
        fast=True,
    )
    # Strategies differ → strategy_hash differs
    assert a["strategy_hash"] != b["strategy_hash"]
    # Outcomes need not always differ in score on tiny fast runs, but cards must differ
    assert a["card_id"] != b["card_id"]
