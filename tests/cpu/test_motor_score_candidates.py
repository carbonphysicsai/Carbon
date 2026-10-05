"""SR-M1: the registered motor score candidates, recomputed without the
bootstrap and checked against the committed result."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.motor import score_candidates

REPOSITORY = Path(__file__).resolve().parents[2]
COMMITTED = (
    REPOSITORY / "docs/development/evidence/motor-score-candidates-v1/result.json"
)
TICKET = REPOSITORY / ".agent/tickets/SR-M1_motor_score_candidates.md"


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return score_candidates.run(REPOSITORY, tmp_path_factory.mktemp("sr"), bootstraps=0)


def test_candidates_are_the_registered_ones():
    text = TICKET.read_text(encoding="utf-8")
    for name in score_candidates.COMPONENT_SETS:
        assert f"| {name} |" in text, name


def test_frozen_rule_is_reproduced_exactly(result):
    registered = json.loads(
        (
            REPOSITORY / "docs/development/evidence/motor-pools-v1/baselines.json"
        ).read_text(encoding="utf-8")
    )["scores"]["practice"]
    check = result["frozen_rule_check"]
    assert check["analytic-v1"] == registered["closed_form"]["score"]
    assert check["learned-krr-v1"] == registered["learned"]["score"]


def test_point_estimates_match_the_committed_result(result):
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    for panel in ("fixture_panel", "widened_panel"):
        for name, row in result[panel].items():
            stored = committed[panel][name]
            assert row["kendall_tau_b"] == pytest.approx(stored["kendall_tau_b"])
            assert row["spearman_rho"] == pytest.approx(stored["spearman_rho"])
            assert row["divergence_count"] == stored["divergence_count"]
            assert row["scores"] == pytest.approx(stored["scores"])
