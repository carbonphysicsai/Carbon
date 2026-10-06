"""A development score variant applied to hidden-pool scores, operator-side
(the hidden-pool variant gate the Test Lead approved; VALIDATOR-09 and 13).

A run under `--score-variant` gets the variant's result on every hidden score
beside the rule's own. That result has the same legs, gate and score as the
practice variant, over the hidden pool's cases. The run's report ranks under
it: closest to 1 best, a gate FAIL last. The result exists only on a
development deployment (which never sets weights) and only in operator
records. The agent's view never carries it.

Fixture variants in a test registry; battery's daemon fixtures (published
PyBaMM references, `DirectBackend`). No pod, chain, network or spend. Not a
security audit (AGENTS.md §13).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_dev_submit import base_digest, key, service, signed  # noqa: F401
from test_battery_validator_daemon import backend, refs  # noqa: F401 - fixtures
from test_graphite_hidden_score import TEMPO, deployment, knn
from test_graphite_phase3_score_variant import (  # noqa: F401 - fixture
    VERSION,
    registry,
    resolved,
)

from carbon.agent_campaign.graphite import hidden_score
from carbon.battery import dev_submit as ds


@pytest.fixture
def target(tmp_path, refs, backend):  # noqa: F811
    built = deployment(tmp_path / "hidden", refs, backend)
    built.development_only = True
    return built


def pool(target, score_variant, run_id="run-v"):
    return hidden_score.HiddenPool(
        target, run_id=run_id, clock=lambda: TEMPO + 5, score_variant=score_variant
    )


def test_a_hidden_score_carries_the_variants_result_operator_side(
    registry, target  # noqa: F811
):
    view, record = pool(target, resolved()).submit("proposal", knn(7))
    assert view["state"] == "SCORED"
    assert "score_variant" not in str(view)
    result = record["score_variant"]
    assert result["score_variant"] == VERSION
    assert set(result) >= {"score", "gate", "label", "practice_value_contract"}
    assert result["gate"] in ("PASS", "FAIL")
    # Without a variant, nothing is added.
    _view, plain = pool(target, None, run_id="run-plain").submit("proposal", knn(9))
    assert plain["score_variant"] is None


def test_the_variant_needs_a_development_deployment(registry, target):  # noqa: F811
    target.development_only = False
    with pytest.raises(hidden_score.HiddenPoolRefused) as refused:
        pool(target, resolved())
    assert refused.value.code == "hidden_score_variant_needs_development_deployment"


def record(sid, score, gate, version="1"):
    return {
        "submission_id": sid,
        "proposal_id": sid,
        "kind": "proposal",
        "replay": "REPRODUCED",
        "rotation_overdue": False,
        "level": 0,
        "pool_version": int(version),
        "aggregate": {"eligible": True, "score": 0.1},
        "score_variant": {"score_variant": VERSION, "score": score, "gate": gate},
    }


def test_the_report_ranks_under_the_variant_with_a_gate_fail_last():
    """Per pool version and device class, as the primary ranking is."""
    from carbon.battery.rebuild_identity import device_class

    records = [
        record("low", 0.40, "PASS"),
        record("failed", 0.95, "FAIL"),
        record("high", 0.80, "PASS"),
        record("none", None, "PASS"),
    ]
    by_class = hidden_score.report(records)["score_variant"]["1"]
    assert list(by_class) == [device_class(records[0])]
    ranked = by_class[device_class(records[0])]
    assert ranked["score_variant"] == VERSION
    assert [r["submission_id"] for r in ranked["ranking"]] == [
        "high",
        "low",
        "none",
        "failed",
    ]


def test_a_report_without_a_variant_has_no_variant_ranking():
    plain = record("a", None, None)
    plain["score_variant"] = None
    assert hidden_score.report([plain])["score_variant"] == {}


# -- through the hidden host's door ---------------------------------------------------------


def test_the_door_applies_the_runs_variant(
    tmp_path, registry, target, key  # noqa: F811
):
    door = service(tmp_path, target, key)
    view = door.handle(signed(key, score_variant=VERSION))
    assert view["state"] == "SCORED"
    [path] = list((tmp_path / "operator" / "run-1").glob("*.json"))
    assert json.loads(path.read_text())["score_variant"]["score_variant"] == VERSION


def test_the_door_refuses_an_unregistered_variant(
    tmp_path, registry, target, key  # noqa: F811
):
    door = service(tmp_path, target, key)
    with pytest.raises(ds.DevSubmitRefused) as refused:
        door.handle(signed(key, score_variant="no-such-variant"))
    assert refused.value.code.startswith("score_variant")


def test_the_remote_pool_names_the_variant_in_its_signed_request(key):  # noqa: F811
    sent = []

    def post(url, body):
        sent.append(body)
        return {"view": {"state": "SCORED"}}

    remote = ds.RemoteHiddenPool(
        "http://127.0.0.1:1",
        key,
        run_id="r",
        challenge_id="battery-fastcharge-ageing-development-v1",
        contract_digest=base_digest(),
        score_variant=VERSION,
        post=post,
    )
    remote.submit("proposal", knn(7))
    body = json.loads(sent[0])["body"]
    assert body["score_variant"] == VERSION
    assert ds.verify(json.loads(sent[0]), key.public_key)["score_variant"] == VERSION


def test_only_the_runners_flag_sets_the_variant_never_the_agents_strategy(
    tmp_path, key  # noqa: F811
):
    """The variant is fixed when the runner builds the pool from its own
    `--score-variant`. Whatever the agent puts in its strategy stays inside
    the strategy; the signed request's `score_variant` is the runner's."""
    from carbon.agent_campaign.graphite import phase3
    from carbon.challenge_validator.scoring import scoring_for

    sent = []

    def post(url, body):
        sent.append(json.loads(body))
        return {"view": {"state": "SCORED"}}

    factory = phase3.hidden_remote_factory(
        "http://127.0.0.1:1",
        tmp_path / "submitter.key",
        scoring_for("battery-fastcharge-ageing-development-v1"),
        None,
        post=post,
        score_variant=None,
    )
    hostile = {
        **knn(7),
        "score_variant": "attacker-chosen",
        "parameters": {"neighbours": 7, "score_variant": "attacker-chosen"},
    }
    factory("run-x").submit("proposal", hostile)
    body = sent[0]["body"]
    assert "score_variant" not in body
    assert body["strategy"] == hostile  # only ever inside the strategy
