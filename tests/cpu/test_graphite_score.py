"""Carbon's side of a Graphite selection (CHALLENGE-PROTOCOL-04 slice 4).

Real battery compile, rebuild and exam scoring through the in-process backend,
on a bounded slice of the development scoring set. A selection Carbon cannot
check, compile or rebuild identically is refused with a typed reason, as a
finding where it is a reproduced fail-open, and is never scored.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import score as scoring
from carbon.development_session.research_loop import candidate_record

REPOSITORY = Path(__file__).resolve().parents[2]
pytest.importorskip("numpy")


def _strategy(backbone, **parameters):
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY_CHALLENGE,
        "backbone": backbone,
        "parameters": parameters,
    }


KNN6 = _strategy("knn", neighbours=6)
KNN5 = _strategy("knn", neighbours=5)


@pytest.fixture(scope="module")
def backend():
    from carbon.battery.worker import DirectBackend

    return DirectBackend(REPOSITORY)


@pytest.fixture(scope="module")
def small_scoring():
    from carbon.battery.value import scoring as value_scoring

    store, case_ids, identity = value_scoring.scoring_set(REPOSITORY)
    return store, case_ids[:24], {**identity, "bounded_for_test": 24}


def _selection(strategy=KNN6):
    return candidate_record(strategy, "practiced and eligible", False)


def test_a_selection_is_checked_rebuilt_twice_and_scored(backend, small_scoring):
    report = scoring.score_selection(
        _selection(), backend=backend, repository=REPOSITORY, scoring=small_scoring
    )
    assert report["schema"] == scoring.SCHEMA
    assert report["rebuild"]["clean_rebuild_identical"] is True
    assert report["rebuild"]["seed"] == scoring.DEVELOPMENT_SEED
    assert report["rule"] == "control-exam-v1"
    assert report["candidate"]["eligible"] in (True, False)
    assert report["margin"] is None and report["incumbent"] is None
    assert report["authority"] == {"grade": False, "evaluator": False, "reward": False}
    again = scoring.score_selection(
        _selection(), backend=backend, repository=REPOSITORY, scoring=small_scoring
    )
    assert again["rebuild"]["state_sha256"] == report["rebuild"]["state_sha256"]


def test_an_incumbent_is_compared_case_by_case_without_a_margin(backend, small_scoring):
    report = scoring.score_selection(
        _selection(),
        backend=backend,
        repository=REPOSITORY,
        incumbent=KNN5,
        scoring=small_scoring,
    )
    counts = report["comparison"]
    assert set(counts) == {"candidate_better", "candidate_worse", "tied"}
    assert sum(counts.values()) <= len(small_scoring[1])
    assert report["incumbent"] is not None and report["margin"] is None


@pytest.mark.parametrize(
    ("change", "code", "finding"),
    [
        (
            lambda s: {**s, "contract_digest": "sha256:" + "0" * 64},
            "selection_contract_not_current",
            True,
        ),
        (
            lambda s: {**s, "strategy_hash": "sha256:" + "1" * 64},
            "selection_plan_mismatch",
            True,
        ),
        (
            lambda s: {**s, "strategy": _strategy("knn", neighbours=6, made_up=1)},
            "selection_does_not_compile",
            True,
        ),
        (
            lambda s: {**s, "strategy": {**s["strategy"], "challenge_id": "burgers"}},
            "not_a_battery_selection",
            False,
        ),
    ],
)
def test_a_selection_carbon_cannot_check_or_compile_is_refused(
    backend, small_scoring, change, code, finding
):
    with pytest.raises(scoring.SelectionRefused) as refused:
        scoring.score_selection(
            change(_selection()),
            backend=backend,
            repository=REPOSITORY,
            scoring=small_scoring,
        )
    assert refused.value.code == code and refused.value.finding is finding


def test_an_unrecorded_contract_change_refuses_every_selection(
    backend, small_scoring, monkeypatch
):
    monkeypatch.setattr(
        scoring.expansion_record, "unrecorded", lambda root: {"battery": "live differs"}
    )
    with pytest.raises(scoring.SelectionRefused, match="unrecorded_contract_change"):
        scoring.score_selection(
            _selection(), backend=backend, repository=REPOSITORY, scoring=small_scoring
        )


def test_a_rebuild_that_does_not_reproduce_is_a_finding(small_scoring):
    class Drifting:
        def __init__(self):
            self.identity = {"kind": "TEST_ONLY"}
            self.n = 0

        def reconstruct(self, label, recipe, seed):
            self.n += 1
            return bytes([self.n]), {}

        def infer(self, label, state, inputs):
            raise AssertionError("never scored")

    with pytest.raises(scoring.SelectionRefused) as refused:
        scoring.score_selection(
            _selection(),
            backend=Drifting(),
            repository=REPOSITORY,
            scoring=small_scoring,
        )
    assert refused.value.code == "clean_rebuild_differs" and refused.value.finding


def test_a_selection_is_read_from_its_session(tmp_path):
    epoch = tmp_path / "ledger" / "epoch-1"
    with pytest.raises(scoring.SelectionRefused, match="no_selection"):
        scoring.load_selection(tmp_path)
    epoch.mkdir(parents=True)
    (epoch / "selected-recipe.json").write_text(json.dumps(_selection()))
    assert scoring.load_selection(tmp_path)["status"] == "SELECTED"
