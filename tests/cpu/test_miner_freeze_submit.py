"""A miner's freeze and submit: the same records and rules as the agent's.

Against a real campaign ledger. The final exam itself (independent
reconstruction and comparison) is replaced here by a fixture returning
feedback; its real path is covered by the final-epoch service test. What is
pinned: the practice rule, one candidate per epoch, the two committed final
epochs, the agent-selects refusal, and that a miner's record is the agent's.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from carbon.development_session import research_campaign as campaign
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_loop import candidate_record
from scripts.dev.miner_launchpad.journey_fixture import reference_burgers_campaign
from scripts.dev.miner_launchpad.operations import OPERATIONS
from scripts.dev.miner_launchpad.runner import RunnerAdapter

STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"width": 16},
}
OTHER = {**STRATEGY, "parameters": {"width": 32}}


def prepared(tmp_path, monkeypatch, *, agent="none", practiced=(STRATEGY,)):
    tmp_path.mkdir(parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    ledger = CampaignLedger(tmp_path / "campaign", clock=lambda: 1000)
    with ledger.db() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_results(owner TEXT NOT NULL,task TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(owner,task))"
        )
        for index, recipe in enumerate(practiced):
            body = canonical(
                {"provenance": "REAL_JAX_PUBLIC_PRACTICE", "recipe": recipe}
            )
            db.execute(
                "INSERT INTO research_results VALUES(?,?,?,?)",
                ("miner", f"task-{index}", body, digest(body)),
            )
    manifest = {"owner": "miner"}
    if agent is not None:
        manifest["agent"] = agent
    (ledger.root / "campaign-manifest.json").write_bytes(canonical(manifest))
    monkeypatch.setattr(campaign, "report", lambda *_, **__: None)
    submitted = []

    async def final_epoch(args, ledger, owner, epoch, strategy, *_):
        submitted.append((epoch, strategy))
        return {"disposition": "COMPARED", "scores": {}, "mandatory_failures": []}, (
            "ref"
        )

    monkeypatch.setattr(campaign, "final_epoch", final_epoch)
    import carbon.development_session.research_rewards as rewards

    monkeypatch.setattr(rewards, "update_simulation", lambda *_, **__: None)
    value = campaign.PreparedCampaign(
        args=SimpleNamespace(),
        ledger=ledger,
        owner="miner",
        manifest=manifest,
        seeds={},
        role_root=None,
        data=None,
        image=None,
        key=None,
        config=None,
        composition=SimpleNamespace(tasks=SimpleNamespace(close=lambda: None)),
        sdk=None,
        task=None,
        grant=None,
        agent_policy=None,
        campaign=reference_burgers_campaign(),
    )
    return value, submitted


def run(coroutine):
    return asyncio.run(coroutine)


def test_a_miner_freezes_the_same_record_the_agent_selects(tmp_path, monkeypatch):
    value, _ = prepared(tmp_path, monkeypatch)
    result = run(
        campaign.freeze_candidate(value, strategy=STRATEGY, reason="practiced best")
    )
    folder = value.ledger.root / "epoch-1"
    written = json.loads((folder / "selected-recipe.json").read_bytes())
    assert written == candidate_record(STRATEGY, "practiced best", False)
    assert result == {"epoch": 1, "selection": written}
    outcome = json.loads((folder / "outcome.json").read_bytes())
    assert outcome["selected_by"] == "miner" and outcome["chain_transactions"] == 0


def test_a_recipe_without_a_practice_result_is_refused_and_nothing_written(
    tmp_path, monkeypatch
):
    value, _ = prepared(tmp_path, monkeypatch)
    with pytest.raises(campaign.OperationRefused, match="practice_result_required"):
        run(campaign.freeze_candidate(value, strategy=OTHER, reason="untested"))
    assert not (value.ledger.root / "epoch-1" / "selected-recipe.json").exists()


def test_one_candidate_per_epoch_until_it_is_submitted(tmp_path, monkeypatch):
    value, submitted = prepared(tmp_path, monkeypatch, practiced=(STRATEGY, OTHER))
    with pytest.raises(campaign.OperationRefused, match="freeze_a_candidate_first"):
        run(campaign.submit_frozen(value))
    run(campaign.freeze_candidate(value, strategy=STRATEGY, reason="first"))
    with pytest.raises(campaign.OperationRefused, match="awaits_submission"):
        run(campaign.freeze_candidate(value, strategy=OTHER, reason="second"))
    assert run(campaign.submit_frozen(value))["epoch"] == 1
    assert submitted == [(1, STRATEGY)]
    assert (value.ledger.root / "epoch-1" / "permitted-final-feedback.json").exists()
    assert not (value.ledger.root / "campaign-complete.json").exists()


def test_the_two_committed_final_exams_complete_the_campaign(tmp_path, monkeypatch):
    value, submitted = prepared(tmp_path, monkeypatch, practiced=(STRATEGY, OTHER))
    for recipe in (STRATEGY, OTHER):
        run(campaign.freeze_candidate(value, strategy=recipe, reason="practiced"))
        run(campaign.submit_frozen(value))
    assert [epoch for epoch, _ in submitted] == [1, 2]
    assert (value.ledger.root / "campaign-complete.json").exists()
    with pytest.raises(campaign.OperationRefused, match="final_exams_used"):
        run(campaign.freeze_candidate(value, strategy=STRATEGY, reason="third"))


def test_the_agent_selects_in_an_autonomous_campaign(tmp_path, monkeypatch):
    value, _ = prepared(tmp_path, monkeypatch, agent="autonomous")
    with pytest.raises(campaign.OperationRefused, match="agent_selects"):
        run(campaign.freeze_candidate(value, strategy=STRATEGY, reason="mine"))
    # Specimen: a campaign frozen before the choice existed is the agent's.
    legacy, _ = prepared(tmp_path / "legacy", monkeypatch, agent=None)
    assert legacy.agent == "autonomous"
    with pytest.raises(campaign.OperationRefused, match="agent_selects"):
        run(campaign.freeze_candidate(legacy, strategy=STRATEGY, reason="mine"))


@pytest.mark.parametrize("name", list(OPERATIONS))
def test_the_campaign_host_implements_every_operation_in_the_table(name):
    assert callable(getattr(RunnerAdapter, name + "_admitted", None)), name


def test_the_early_answer_and_the_freeze_share_one_checker(tmp_path, monkeypatch):
    value, _ = prepared(tmp_path, monkeypatch)
    root = value.ledger.root
    assert campaign.freeze_refusal(root, OTHER) == "practice_result_required"
    assert campaign.freeze_refusal(root, STRATEGY) is None
    run(campaign.freeze_candidate(value, strategy=STRATEGY, reason="first"))
    assert campaign.freeze_refusal(root, STRATEGY) == "candidate_awaits_submission"
