"""Phase 3's hidden-pool option (VALIDATOR-13 follow-up): `--hidden-deployment`.

A session given a hidden pool scores each construction on it through the real
validator. The checks happen before anything is spent: Level 0 only, the
deployment loads writable, and its rule seals hidden results. The end-to-end
session uses scripted pods and a recording stand-in pool; the factory's
refusals use battery's daemon fixtures.
"""

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from graphite_phase3_fixtures import SCORING, propose, steps, text, variant
from test_battery_validator_daemon import (
    backend,  # noqa: F401 - fixture
    refs,  # noqa: F401 - fixture
)
from test_graphite_hidden_score import deployment
from test_graphite_phase3 import proposals, session, tool_outputs

from carbon.agent_campaign.graphite import phase3
from carbon.agent_campaign.graphite.pods import ScriptedPods


class RecordingPool:
    challenge_id = SCORING.challenge_id

    def __init__(self, run_id):
        self.run_id, self.calls = run_id, []

    def submit(self, kind, strategy):
        self.calls.append(kind)
        view = {"state": "SCORED", "evidence": "DEVELOPMENT_HIDDEN_POOL"}
        return view, {"submission_id": "bsub-" + kind, "replay": "REPRODUCED"}


def test_a_session_with_a_hidden_pool_scores_every_construction_on_it(tmp_path):
    pools = []

    def factory(run_id):
        pools.append(RecordingPool(run_id))
        return pools[-1]

    script = [propose(variant(width=128)), text("done")]
    result, graphite, _control = session(
        tmp_path, script, ScriptedPods(steps=steps(1.0, 0.4)), hidden=factory
    )
    assert result["provider_state"] == "succeeded"
    records = proposals(graphite)
    assert {"baseline", "proposal"} <= {r["kind"] for r in records}
    scored = [r for r in records if r["status"] == "SCORED"]
    assert scored and all(r["hidden"]["state"] == "SCORED" for r in scored)
    assert {"baseline", "proposal"} <= {c for pool in pools for c in pool.calls}
    # The agent's feedback carries only the miner-visible view.
    [feedback] = [
        o for o in tool_outputs(graphite.model) if o.get("kind") == "proposal"
    ]
    assert feedback["hidden"] == {
        "state": "SCORED",
        "evidence": "DEVELOPMENT_HIDDEN_POOL",
    }
    assert "submission_id" not in json.dumps(feedback)


def test_without_the_option_nothing_is_submitted(tmp_path):
    script = [propose(variant(width=128)), text("done")]
    _result, graphite, _control = session(
        tmp_path, script, ScriptedPods(steps=steps(1.0, 0.4))
    )
    assert all("hidden" not in r for r in proposals(graphite))


def _config(directory, rule):
    path = directory / "deployment.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.battery.validator-deployment.v1",
                "state": str(directory / "state.sqlite3"),
                "private_root": str(directory / "root.bin"),
                "journal": str(directory / "journal.jsonl"),
                "work": str(directory / "work"),
                "backend": "direct",
                "rule": rule,
                "require_commitment": False,
            }
        )
    )
    path.chmod(0o600)
    return path


def test_a_sealed_rule_v2_deployment_serves_one_pool_per_run(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    deployment(tmp_path / "hidden", refs, backend)
    factory = phase3.hidden_pool_factory(
        _config(tmp_path / "hidden", "v2"), SCORING, None, clock=lambda: 400
    )
    pool = factory("run-7")
    assert (pool.run_id, pool.challenge_id) == ("run-7", SCORING.challenge_id)
    assert pool.identity("proposal") == "graphite-dev:run-7:constructor"


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        ("variant", "hidden_pool_is_level_0_only"),
        ("missing", "hidden_evaluation_input_missing"),
    ],
)
def test_the_option_is_refused_before_anything_is_spent(tmp_path, capsys, setup, code):
    variant_arg = object() if setup == "variant" else None
    with pytest.raises(phase3.RunnerRefused):
        phase3.hidden_pool_factory(
            tmp_path / "nowhere.json", SCORING, variant_arg, clock=lambda: 1
        )
    assert json.loads(capsys.readouterr().out)["reason_code"] == code


def test_a_finalized_block_clock_reads_none_when_the_chain_is_down(monkeypatch):
    from carbon.chain.models import ChainContext, ChainFailure, FailureCode
    from carbon.chain.sdk import BittensorReader

    async def down(self, context):
        raise ChainFailure(FailureCode.UNAVAILABLE)

    monkeypatch.setattr(BittensorReader, "capture", down)
    context = ChainContext(
        "testnet", "wss://test.finney.opentensor.ai:443", "p", "0x" + "a" * 64, 567
    )
    assert phase3.finalized_block_clock(context)() is None
