"""A smoke practice of a direct graph recipe (audit finding on graph smoke).

Claims tested:

1. A graph recipe's smoke truncation caps its training steps at the one cap
   every smoke practice uses (`battery.smoke_practice.SMOKE_STEPS`), split
   evenly over ensemble members, records the cut, and the cut is still a
   recipe its adapter resolves.
2. A recipe at or under the cap, and a malformed one, run as they are.
3. A catalog recipe, or a graph on an adapter the hook does not serve, is
   refused `smoke_practice_unavailable` before anything is recorded.
4. Through the research executor a smoke practice of a graph recipe runs the
   practice with the truncated recipe and keeps only a typed SMOKE result:
   the original recipe, no score or output rows, never official, outside the
   full-practice provenances; a PASSED one supports the freeze, a FAILED one
   and one of another recipe do not.
5. The default practice is unchanged.
6. A smoke run that stops at a resource limit ends as the candidate-failure
   refusal (`practice_candidate_failed`), never FAILED_INFRA.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from carbon.battery import smoke_practice as battery_smoke
from carbon.development_session import graph_adapters
from carbon.development_session import graph_smoke_practice as graph_smoke
from carbon.development_session import research_campaign as rc
from carbon.development_session import smoke_practice as smoke
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_carrier import (
    MINER_FAILURE_SCHEMA,
    MinerProgramFailure,
)
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_tasks import PublicResearchExecutor
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.research import DirectPracticeTaskSpecV1
from carbon.research.durable import _NoRetry
from carbon.research.records import InfrastructureExecutionFailure

OWNER = "miner"
V2 = ("f08-ribbed-bracket", "1.5")
V1 = ("f08-ribbed-bracket", "1.4")
SUBMISSION = "sha256:" + "a" * 64


def recipe(version=V2, steps=None, members=None, train=None):
    configuration = {"training": {} if steps is None else {"steps": steps}}
    if train is not None:
        configuration["training"].update(train)
    if members is not None:
        configuration["ensemble"] = {"members": members}
    return graph_adapters.graph_recipe(
        *version, SUBMISSION, configuration=configuration
    )


def steps_of(strategy):
    return strategy["procedure"]["configuration"]


def test_the_cap_is_the_one_every_smoke_practice_uses():
    assert battery_smoke.SMOKE_STEPS == 2000
    cut, record = graph_smoke.truncate(recipe(steps=20000))
    assert steps_of(cut)["training"]["steps"] == battery_smoke.SMOKE_STEPS
    assert record == {
        "field": graph_smoke.FIELD,
        "steps_requested": 20000,
        "steps_run": battery_smoke.SMOKE_STEPS,
    }
    # The cut is still a recipe its adapter resolves, and the original is unchanged.
    from carbon.development_session.construction_recipe import ConstructionRecipe

    module = graph_adapters.for_version(*V2)
    assert module.training_settings(ConstructionRecipe.from_dict(cut))
    assert steps_of(recipe(steps=20000))["training"]["steps"] == 20000


def test_members_share_the_cap_evenly():
    members = [
        {"outputs": [0, 1, 2, 3]},
        {"outputs": [4, 5, 6], "training": {"steps": 9000}},
    ]
    cut, record = graph_smoke.truncate(recipe(steps=5000, members=members))
    config = steps_of(cut)
    assert config["training"]["steps"] == 1000
    assert config["ensemble"]["members"][1]["training"]["steps"] == 1000
    assert (record["steps_requested"], record["steps_run"]) == (14000, 2000)
    from carbon.development_session.construction_recipe import ConstructionRecipe

    graph_adapters.for_version(*V2).training_settings(ConstructionRecipe.from_dict(cut))


def test_the_older_adapter_is_served_with_its_own_floor():
    cut, record = graph_smoke.truncate(recipe(V1, steps=50000))
    assert steps_of(cut)["training"]["steps"] == 2000
    assert record["steps_requested"] == 50000


def test_a_recipe_within_the_cap_and_a_malformed_one_run_as_they_are():
    for steps in (None, 512, 2000):
        value = recipe(steps=steps)
        assert graph_smoke.truncate(value)[0] is value
    odd = recipe(steps=True)
    cut, record = graph_smoke.truncate(odd)
    assert cut is odd and record["steps_run"] is None


def test_unserved_recipes_are_refused_before_anything_is_recorded():
    catalog = recipe()
    catalog["source"] = {"kind": "catalog"}
    for bad in (catalog, {"challenge": {"id": "x", "version": "1"}}, None, []):
        with pytest.raises(smoke.SmokeUnavailable) as refused:
            smoke.direct_hook(bad)
        assert refused.value.code == "smoke_practice_unavailable"


# ---- the executor.


def ledger_at(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    return CampaignLedger(tmp_path / "campaign", clock=lambda: 1000)


class DirectFixture:
    """The direct practice callback with a fixture training run."""

    construction_mode = "direct"

    def __init__(self, ledger, *, raises=None, finite=True):
        self.ledger, self.raises, self.finite = ledger, raises, finite
        self.sent = []

    def __call__(self, identity, strategy):
        self.sent.append(strategy)
        if self.raises is not None:
            raise self.raises
        result = {
            "schema": "carbon.f08.direct-practice.v1",
            "provenance": "F08_PUBLIC_PRACTICE",
            "recipe": strategy,
            "summary": {
                "n_cases": 12,
                "score": 0.25,
                "aggregate_error": 0.25 if self.finite else float("inf"),
            },
            "fit": {"state_digest": "sha256:" + "b" * 64},
            "practice_dual": {"total": 0.9},
        }
        ResearchWorkspace(self.ledger, OWNER).put(
            "trial-" + digest(identity.encode())[7:23] + "-f08-direct-practice.json",
            canonical(result),
        )
        return result


def execute(ledger, practice, strategy, identity, *, smoke_mode):
    if smoke_mode:
        smoke.record_request(
            ledger, OWNER, identity, strategy, {"id": "c", "version": "1"}
        )
    executor = PublicResearchExecutor(
        ledger=ledger, owner=OWNER, image=None, public_material=None, practice=practice
    )
    task = "rtsk_" + digest(identity.encode())[7:71]
    executor.request_resolver = lambda _task: SimpleNamespace(
        task_spec=DirectPracticeTaskSpecV1("carbon.direct-practice.v1", strategy),
        idempotency_key=identity,
    )
    attempt = SimpleNamespace(task_id=SimpleNamespace(value=task))
    return executor, attempt, task


def stored(ledger, task):
    with ledger.db() as db:
        row = db.execute(
            "SELECT body FROM research_results WHERE owner=? AND task=?", (OWNER, task)
        ).fetchone()
    return json.loads(row[0])


def trial_files(ledger):
    return [
        json.loads(ResearchWorkspace(ledger, OWNER).get(item["name"]))
        for item in ResearchWorkspace(ledger, OWNER).inventory()
        if item["name"].startswith("trial-")
    ]


def test_a_smoke_practice_runs_truncated_and_keeps_only_the_smoke_result(tmp_path):
    ledger = ledger_at(tmp_path)
    practice = DirectFixture(ledger)
    strategy = recipe(steps=20000)
    executor, attempt, task = execute(ledger, practice, strategy, "s1", smoke_mode=True)
    executor._execute(attempt)
    # The practice ran the truncated recipe; the result names the original.
    assert steps_of(practice.sent[0])["training"]["steps"] == 2000
    result = stored(ledger, task)
    assert set(result) <= smoke.RESULT_FIELDS
    assert result["outcome"] == "SMOKE" and result["status"] == "PASSED"
    assert result["provenance"] == smoke.SMOKE_PROVENANCE
    assert result["provenance"] not in rc.practice_provenances()
    assert result["recipe"] == strategy
    assert result["smoke"]["truncated"] is True
    assert result["official_eligible"] is False and result["final_exam"] is False
    assert result["scientific_qualification"] is False
    assert "summary" not in result and "practice_dual" not in result
    # The trial file in the workspace holds the smoke result, never the full one.
    assert all(f["outcome"] == "SMOKE" for f in trial_files(ledger))
    # The freeze accepts it, for this recipe only.
    assert rc.trial_supports_selection(ledger, OWNER, strategy)
    assert not rc.trial_supports_selection(ledger, OWNER, recipe(steps=20001))


def test_a_failed_smoke_does_not_support_the_freeze(tmp_path):
    ledger = ledger_at(tmp_path)
    strategy = recipe(steps=20000)
    executor, attempt, task = execute(
        ledger, DirectFixture(ledger, finite=False), strategy, "s2", smoke_mode=True
    )
    executor._execute(attempt)
    assert stored(ledger, task)["status"] == "FAILED"
    assert not rc.trial_supports_selection(ledger, OWNER, strategy)


def test_the_default_practice_is_unchanged(tmp_path):
    ledger = ledger_at(tmp_path)
    practice = DirectFixture(ledger)
    strategy = recipe(steps=20000)
    executor, attempt, task = execute(
        ledger, practice, strategy, "f1", smoke_mode=False
    )
    executor._execute(attempt)
    assert practice.sent == [strategy]
    assert stored(ledger, task)["summary"]["score"] == 0.25


# ---- the resource limit.


def wall_failure():
    return MinerProgramFailure(
        {
            "schema": MINER_FAILURE_SCHEMA,
            "failure_code": "DEADLINE",
            "observation": "WORKER_WALL_LIMIT_REACHED",
            "limit": {"kind": "wall", "seconds": 600},
        }
    )


def test_a_smoke_run_at_its_limit_ends_as_the_typed_refusal_not_infrastructure(
    tmp_path,
):
    ledger = ledger_at(tmp_path)
    strategy = recipe(steps=20000)
    practice = DirectFixture(ledger, raises=wall_failure())
    executor, attempt, task = execute(ledger, practice, strategy, "s3", smoke_mode=True)
    outcome = _NoRetry(executor).execute(attempt)
    assert type(outcome) is not InfrastructureExecutionFailure
    result = stored(ledger, task)
    assert result["outcome"] == "MINER_PROGRAM_FAILED"
    assert result["limit"] == {"kind": "wall", "seconds": 600}
    assert result["nothing_scored"] is True
    # Nothing counts as a smoke result, so nothing unlocks the freeze.
    assert not rc.trial_supports_selection(ledger, OWNER, strategy)

    # The practice path turns that answer into the typed refusal.
    async def call(name, args, identity):
        return {
            "terminal_task": {"state": "SUCCEEDED"},
            "public_result": result,
        }

    value = SimpleNamespace(
        manifest={
            "construction_mode": "direct",
            "challenge": {"id": "c", "version": "1"},
        },
        ledger=ledger,
        owner=OWNER,
        composition=SimpleNamespace(executor=SimpleNamespace(practice=practice)),
        sdk=SimpleNamespace(call=call),
        campaign=None,
    )
    with pytest.raises(rc.PracticeNotRun) as refused:
        asyncio.run(
            rc.practice_recipe(
                value,
                strategy=strategy,
                hypothesis="h",
                expected_effect="e",
                identity="s4",
                mode="smoke",
            )
        )
    assert refused.value.code == rc.PRACTICE_CANDIDATE_FAILED
    assert refused.value.code != rc.PRACTICE_COULD_NOT_RUN


def test_the_practice_path_records_smoke_for_a_graph_and_refuses_a_catalog(tmp_path):
    ledger = ledger_at(tmp_path)
    sent = []

    async def call(name, args, identity):
        sent.append(identity)
        return {"terminal_task": {"state": "SUCCEEDED"}}

    value = SimpleNamespace(
        manifest={
            "construction_mode": "direct",
            "challenge": {"id": "c", "version": "1"},
        },
        ledger=ledger,
        owner=OWNER,
        composition=SimpleNamespace(
            executor=SimpleNamespace(practice=SimpleNamespace(seconds=600))
        ),
        sdk=SimpleNamespace(call=call),
        campaign=None,
    )
    graph = recipe(steps=20000)
    asyncio.run(
        rc.practice_recipe(
            value,
            strategy=graph,
            hypothesis="h",
            expected_effect="e",
            identity="s5",
            mode="smoke",
        )
    )
    assert sent == ["s5"] and smoke.requested(ledger, OWNER, "s5") is not None
    catalog = recipe()
    catalog["source"] = {"kind": "catalog"}
    with pytest.raises(rc.OperationRefused, match="smoke_practice_unavailable"):
        asyncio.run(
            rc.practice_recipe(
                value,
                strategy=catalog,
                hypothesis="h",
                expected_effect="e",
                identity="s6",
                mode="smoke",
            )
        )
    assert smoke.requested(ledger, OWNER, "s6") is None
