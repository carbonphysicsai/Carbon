"""Cooling's committed practice equivalence margin (OWNER-GRAPHITE-TEST-WAVE-06 §1).

The full measurement refits the KRR 122 times, which is too slow for CI, so
the committed result is checked instead: it must bind today's public pool
files, its margins must recompute from its recorded seed scores, and it must
still match the registered families.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

import pytest

from carbon.cold_plate import contracts

REPOSITORY = Path(__file__).resolve().parents[2]
RESULT = (
    REPOSITORY
    / "docs/development/evidence/cold-plate-equivalence-margin-v1/result.json"
)
POOLS = REPOSITORY / "docs/development/evidence/cold-plate-pools-v1"


@pytest.fixture(scope="module")
def result():
    return json.loads(RESULT.read_text(encoding="utf-8"))


def _sha256(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_result_binds_the_current_public_pools(result):
    for name, key in (
        ("train.jsonl", "train_sha256"),
        ("practice.jsonl", "practice_sha256"),
        ("baselines.json", "baselines_sha256"),
    ):
        assert result["inputs"][key] == _sha256(POOLS / name), name
    baselines = json.loads((POOLS / "baselines.json").read_text(encoding="utf-8"))
    assert result["full_train_practice"]["score"] == pytest.approx(
        baselines["scores"]["practice"]["learned"]["score"], abs=1e-12
    )


def test_margins_recompute_from_the_recorded_seed_scores(result):
    def margin(scores):
        return 2 * statistics.stdev(scores) / statistics.fmean(scores)

    bootstrap = result["bootstrap"]
    assert bootstrap["with_replacement"] is True
    assert bootstrap["seeds"] == len(bootstrap["practice_scores"]) == 30
    assert bootstrap["score"]["margin_rel"] == pytest.approx(
        margin(bootstrap["practice_scores"])
    )
    for fraction, row in result["subsample_sensitivity"].items():
        assert row["score"]["margin_rel"] == pytest.approx(
            margin(row["practice_scores"])
        ), fraction
    assert result["literal_battery_rule_on_cooling"]["margin_rel"] == 0.0
    assert result["equivalence_margin_rel"] == bootstrap["score"]["margin_rel"]


def test_no_stochastic_family_is_registered_so_bootstrap_stands(result):
    families = [
        name
        for name, _ in contracts.rebuildable_families(contracts.COLD_PLATE_CHALLENGE)
    ]
    # If a stochastic family is registered, the max rule needs the OD-2
    # analogue, and the margin must be remeasured before it is used.
    assert families == result["stochastic_recipes"]["registered_families"]
    assert result["stochastic_recipes"]["stochastic_families"] == []
