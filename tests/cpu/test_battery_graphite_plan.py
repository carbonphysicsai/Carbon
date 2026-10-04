"""A battery campaign's Graphite run plan and its preparation (slice S3).

OWNER-GRAPHITE-MINER-01: a new Graphite campaign freezes everything an
autonomous plan freezes plus the miner edition's `graphite` block and the
engine's limits and compaction rules; the autonomous and agent-less plans are
unchanged byte for byte, and a recorded autonomous campaign still prepares
and runs as it did.

Fixtures: image identities, the host doctor, keys and the connection are
stand-ins (as in `test_battery_research_images`), and the literature slice's
modules are `test_graphite_miner_driver`'s fixtures; the ledger, the manifest
freeze and the plan are real. Engineering evidence only.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from test_graphite_miner_driver import CHALLENGE_REF, PACK_DIGEST, install_literature
from test_miner_launchpad_runner import HOTKEY, registered

from carbon.agent_campaign.graphite.miner import driver
from carbon.agent_campaign.graphite.miner import edition as editions
from carbon.battery import campaign as battery
from carbon.development_session import miner_guidance
from carbon.development_session.model_provider import (
    ENGY_DEFAULT_MODEL,
    select,
)
from carbon.development_session.product_campaign import AGENTS, ProductLaunch
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent import RESERVATION_NANO
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    PARALLEL_CALLS_V2,
)
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_tools import TOOLS_RULE

BUDGET = {
    "ceilings": {
        "provider_attempts": 24,
        "provider_nanodollars": 24 * RESERVATION_NANO,
        "research_trials": 4,
    }
}
#: The autonomous plan for `BUDGET` under the pinned default selection, as
#: the base commit (9bfd9add) froze it, computed from that commit's module.
AUTONOMOUS_PLAN_DIGEST = (
    "sha256:df4c17f175827bad53e8ba856cff17292014574c44cd06399abb5e7a6b489629"
)


def block(**fields):
    return editions.graphite_block(
        editions.launch_fields(fields),
        curation_digest="sha256:" + "c" * 64,
        pack_digest=PACK_DIGEST,
        private_snapshot_digest="sha256:" + "d" * 64,
    )


def test_a_graphite_plan_freezes_the_block_and_the_engine_rules():
    frozen = block(
        mode="FULL",
        research_share=0.25,
        hunt={"queries": ["fast charge ageing"]},
        limits={"calls_per_epoch": 200, "trials_per_epoch": 20, "planner_calls": 30},
    )
    plan = battery.provider_plan("graphite", BUDGET, None, graphite=frozen)
    assert set(plan) == {
        "agent",
        "policy",
        "model",
        "epochs",
        "ceilings",
        "evaluator_access",
        "parallel_calls",
        "miner_guidance",
        "research_tools",
        "limits",
        "compaction",
        "graphite",
    }
    assert plan["agent"] == "graphite" and plan["policy"] == editions.AGENT_POLICY
    assert plan["evaluator_access"] is False and plan["epochs"] == 2
    assert plan["ceilings"] == {
        "provider_attempts": 24,
        "provider_nanodollars": 24 * RESERVATION_NANO,
    }
    assert plan["parallel_calls"] == PARALLEL_CALLS_V2
    assert plan["miner_guidance"] == miner_guidance.RULE
    assert plan["research_tools"] == TOOLS_RULE
    assert plan["compaction"] == editions.COMPACTION_V1
    assert plan["limits"] == {
        "plan": {
            "schema": editions.LIMITS_SCHEMA,
            "calls_per_epoch": 30,
            "trials_per_epoch": 20,
        },
        "build": {
            "schema": editions.LIMITS_SCHEMA,
            "calls_per_epoch": 200,
            "trials_per_epoch": 20,
        },
    }
    assert plan["graphite"] == frozen
    assert frozen == {
        "edition": editions.EDITION_ID,
        "edition_digest": editions.EDITION.digest,
        "mode": "FULL",
        "research_share": 0.25,
        "plan_digest": None,
        "hunt": {"queries": ["fast charge ageing"], "max_records": 200},
        "curation_digest": "sha256:" + "c" * 64,
        "literature": {
            "pack_digest": PACK_DIGEST,
            "private_snapshot_digest": "sha256:" + "d" * 64,
        },
        "limits": {"calls_per_epoch": 200, "planner_calls": 30, "trials_per_epoch": 20},
        "escalation": [],
    }
    # No per-epoch count unless the miner set one: only the ceilings bind.
    generous = battery.provider_plan("graphite", BUDGET, None, graphite=block())
    assert "max_provider_calls_per_epoch" not in generous
    assert generous["limits"]["build"]["calls_per_epoch"] is None
    assert generous["limits"]["plan"]["trials_per_epoch"] is None
    assert generous["graphite"]["mode"] == "FULL"
    assert generous["graphite"]["research_share"] == 0.1


def test_a_graphite_plan_needs_finite_ceilings_its_block_and_this_edition():
    with pytest.raises(ValueError, match="finite provider_attempts"):
        battery.provider_plan("graphite", {}, None, graphite=block())
    with pytest.raises(ValueError, match="launch block"):
        battery.provider_plan("graphite", BUDGET, None)
    with pytest.raises(ValueError, match="shape"):
        battery.provider_plan("graphite", BUDGET, None, graphite={"mode": "FULL"})
    stale = {**block(), "edition_digest": "sha256:" + "0" * 64}
    with pytest.raises(editions.EditionUnknown):
        battery.provider_plan("graphite", BUDGET, None, graphite=stale)
    with pytest.raises(ValueError, match="not runnable"):
        battery.provider_plan(
            "graphite", BUDGET, None, graphite={**block(), "escalation": ["x"]}
        )
    with pytest.raises(ValueError, match="only a Graphite campaign"):
        battery.provider_plan("autonomous", BUDGET, None, graphite=block())


def test_a_graphite_plan_records_the_miners_model_selection():
    chosen = select(
        provider_id="engy-anthropic",
        model_id=ENGY_DEFAULT_MODEL,
        credential={"kind": "file", "reference": "unset"},
    )
    budget = {
        "ceilings": {
            "provider_attempts": 10,
            "provider_nanodollars": 10 * chosen.reservation_nano,
        }
    }
    plan = battery.provider_plan("graphite", budget, chosen, graphite=block())
    assert plan["model"] == ENGY_DEFAULT_MODEL
    assert plan["model_selection"] == chosen.record()


def test_the_autonomous_and_agentless_plans_are_unchanged():
    plan = battery.provider_plan("autonomous", BUDGET)
    assert digest(canonical(plan)) == AUTONOMOUS_PLAN_DIGEST
    assert plan["agent"] == "autonomous"
    assert plan["max_provider_calls_per_epoch"] == 48
    assert plan["max_research_trials_per_epoch"] == 8
    assert "graphite" not in plan and "limits" not in plan
    assert battery.provider_plan("none", None) == {"agent": "none", "model_calls": 0}


def test_graphite_is_a_launch_agent_and_autonomous_still_builds():
    assert AGENTS == ("none", "autonomous", "graphite")
    for agent in AGENTS:
        launch = ProductLaunch(
            campaign_id="cmp-agent-" + agent,
            principal="alice",
            miner=registered(),
            runtime={"implementation": "fixture", "images": ["fixture"]},
            budget=BUDGET,
            agent=agent,
            challenge=dict(CHALLENGE_REF),
        )
        assert launch.manifest_fields()["agent"] == agent
    with pytest.raises(ValueError, match="agent is one of"):
        ProductLaunch(
            campaign_id="cmp-agent-x",
            principal="alice",
            miner=registered(),
            runtime={"implementation": "fixture", "images": ["fixture"]},
            budget=BUDGET,
            agent="carbon-autonomous",
        )


def test_manifest_document_freezes_the_graphite_block():
    launch = ProductLaunch(
        campaign_id="cmp-graphite-manifest",
        principal="alice",
        miner=registered(),
        runtime={"implementation": "fixture", "images": ["a", "b"]},
        budget=BUDGET,
        agent="graphite",
        challenge=dict(CHALLENGE_REF),
    )
    frozen = block(mode="RESEARCH")
    manifest = battery.manifest_document(
        launch,
        owner="owner",
        implementation="fixture",
        images=["a", "b"],
        graphite=frozen,
    )
    assert manifest["agent"] == "graphite"
    assert manifest["provider"]["graphite"] == frozen
    with pytest.raises(ValueError, match="launch block"):
        battery.manifest_document(
            launch, owner="owner", implementation="fixture", images=["a", "b"]
        )


# --- prepare_battery -------------------------------------------------------------


@pytest.fixture
def host(tmp_path, monkeypatch):
    """Everything prepare_battery touches outside the campaign, as fixtures
    (the stand-ins `test_battery_research_images` uses)."""
    import carbon.chain.external_signer
    from carbon.development_session import (
        agent,
        research_campaign,
        research_image,
        research_tools,
        service,
    )
    from carbon.development_testnet import operator
    from carbon.reconstruction.worker import docker_runtime

    tmp_path.chmod(0o700)
    literature = install_literature(monkeypatch)
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    public = tmp_path / "miner-public.json"
    public.write_bytes(
        canonical({"netuid": 567, "hotkey": HOTKEY, "key_file": "unused-fixture"})
    )
    public.chmod(0o600)
    key = tmp_path / "provider-key"
    key.write_bytes(b"fixture-key")
    key.chmod(0o600)
    monkeypatch.setattr(research_campaign, "accepted_implementation", lambda _: "impl")
    monkeypatch.setattr(research_campaign, "verify_current_worker", lambda *_: None)

    async def requester(_):
        return "miner-requester"

    monkeypatch.setattr(research_campaign, "requester", requester)
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda _: SimpleNamespace(image_id="sha256:" + "a" * 64),
    )
    monkeypatch.setattr(
        docker_runtime, "doctor", lambda **_: SimpleNamespace(eligible=True)
    )
    analysis = SimpleNamespace(
        image_id="sha256:" + "b" * 64, parent_image="sha256:" + "a" * 64
    )
    monkeypatch.setattr(research_image, "load_analysis_image", lambda _: analysis)
    monkeypatch.setattr(research_image, "verify_image", lambda _: None)
    monkeypatch.setattr(
        operator,
        "load_config",
        lambda _: SimpleNamespace(netuid=567, context=None, publisher_hotkey="pub"),
    )
    monkeypatch.setattr(carbon.chain.external_signer, "miner_signer", lambda *_: None)
    monkeypatch.setattr(service, "LocalMinerConnection", lambda *_: None)
    monkeypatch.setattr(agent, "ResponsesTransport", lambda *_: None)
    monkeypatch.setattr(
        battery,
        "compose",
        lambda **_: (SimpleNamespace(tasks=None, executor=None), None),
    )
    monkeypatch.setattr(research_tools, "ResearchMinerTools", lambda **kw: kw)
    runtime = {
        "implementation": "impl",
        "images": ["sha256:" + "a" * 64, "sha256:" + "b" * 64],
    }

    def args(command, agent="graphite", policy=AUTONOMOUS, graphite=None):
        return SimpleNamespace(
            root=root,
            command=command,
            accepted_revision="fixture",
            image_manifest=public,
            analysis_image_manifest=public,
            operator_config=public,
            miner_public=public,
            api_key_file=key,
            agent_policy=policy,
            graphite=graphite if graphite is not None else {"mode": "RESEARCH"},
            graphite_library=tmp_path / "graphite-library",
            product=ProductLaunch(
                campaign_id="cmp-graphite-prepare",
                principal="alice",
                miner=registered(),
                runtime=runtime,
                budget=BUDGET,
                agent=agent,
                challenge=dict(CHALLENGE_REF),
            ),
        )

    def prepare(command, **kw):
        return asyncio.run(
            battery.prepare_battery(
                args(command, **kw), ledger=CampaignLedger(root), campaign=None
            )
        )

    return SimpleNamespace(root=root, prepare=prepare, literature=literature)


def test_a_graphite_launch_freezes_its_plan_and_launch_record(host):
    prepared = host.prepare("run", graphite={"mode": "RESEARCH", "hunt": {}})
    frozen = json.loads((host.root / "campaign-manifest.json").read_bytes())
    assert frozen["agent"] == "graphite" and prepared.agent == "graphite"
    plan = frozen["provider"]
    assert plan["agent"] == "graphite" and plan["graphite"]["mode"] == "RESEARCH"
    assert plan["graphite"]["hunt"] == {"queries": [], "max_records": 200}
    assert plan["graphite"]["literature"]["pack_digest"] == PACK_DIGEST
    record = json.loads(driver.launch_path(host.root).read_bytes())
    assert record["block_digest"] == digest(canonical(plan["graphite"]))
    assert driver.frozen_launch(host.root, plan["graphite"]) == record
    # A resume keeps the frozen plan; the launch fields are not read again.
    again = host.prepare("resume", graphite={"mode": "BUILD"})
    assert again.manifest == frozen
    # The miner edition's own policy names it too.
    host.prepare("resume", policy=editions.AGENT_POLICY)
    with pytest.raises(ValueError, match="autonomous policy"):
        host.prepare("resume", policy=None)


def test_a_graphite_launch_is_refused_by_code_before_its_manifest(host):
    from carbon.development_session.research_campaign import OperationRefused

    with pytest.raises(OperationRefused) as refused:
        host.prepare("run", graphite={"mode": "BUILD", "plan": "sha256:" + "9" * 64})
    assert refused.value.code == "plan_not_found"
    assert not (host.root / "campaign-manifest.json").exists()


def test_an_autonomous_campaign_prepares_as_it_did(host):
    prepared = host.prepare("run", agent="autonomous")
    frozen = json.loads((host.root / "campaign-manifest.json").read_bytes())
    assert frozen["provider"] == battery.provider_plan("autonomous", BUDGET)
    assert digest(canonical(frozen["provider"])) == AUTONOMOUS_PLAN_DIGEST
    assert prepared.agent == "autonomous"
    assert not driver.launch_path(host.root).exists()
    with pytest.raises(ValueError, match="autonomous policy"):
        host.prepare("resume", agent="autonomous", policy=editions.AGENT_POLICY)
