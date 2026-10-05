"""The motor Q1 fixture panel: recomputed in full and checked against the
committed result. Public data and the counted replay only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.motor import q1_panel

REPOSITORY = Path(__file__).resolve().parents[2]
COMMITTED = (
    REPOSITORY / "docs/development/evidence/motor-q1-fixture-panel-v1/result.json"
)


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return q1_panel.run(REPOSITORY, tmp_path_factory.mktemp("q1"))


#: Floats recompute to this relative tolerance across environments (BLAS and
#: CPU differences move practice scores by about 1e-13). Everything that is
#: not a float must match exactly.
FLOAT_REL_TOL = 1e-9


def _same(a, b, path="result"):
    if isinstance(a, float) or isinstance(b, float):
        assert isinstance(a, (int, float)) and isinstance(b, (int, float)), path
        assert a == pytest.approx(b, rel=FLOAT_REL_TOL, abs=0.0), path
    elif isinstance(a, dict):
        assert isinstance(b, dict) and set(a) == set(b), path
        for key in a:
            _same(a[key], b[key], f"{path}.{key}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]")
    else:
        assert a == b, path


def test_the_committed_result_recomputes(result):
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    _same(json.loads(json.dumps(result, sort_keys=True)), committed)


def test_controls_behave_as_constructed(result):
    rows = result["members"]
    krr, shifted = rows["learned-krr-v1"], rows["phase-shifted"]
    # Same mean and peak-to-peak: identical decision, worse pointwise score.
    assert shifted["selection"] == krr["selection"]
    assert shifted["regret"] == krr["regret"]
    assert shifted["practice_score"] > krr["practice_score"]
    # Zero ripple everywhere: a tie-determined, unsafe selection.
    assert rows["flat"]["decision"]["tie_determined"] is True
    assert rows["flat"]["decision"]["false_feasible"] is True
    assert rows["analytic-v1"]["decision"]["tie_determined"] is True


def test_divergence_flags_better_scores_with_worse_decisions(result):
    fired = {
        c["member"]
        for c in result["alignment"]["conditions"]
        if c["condition"] == "SCORE_VALUE_DIVERGENCE"
    }
    assert fired == {"analytic-v1", "flat", "saturation-blind"}
    assert "learned-krr-v1" not in fired
