"""The campaign host a no-agent journey runs on, where compute is unavailable.

Shared by the browser smoke and the stdio journey test, so the two doors are
exercised against the same host. Real: the RunnerAdapter, the operations table
and its gates, the launch thread and control settling, research_campaign's
freeze and submit, the ledger and the projection. Fixture, because neither a
browser smoke nor a CPU test has Docker images, keys or compute: preparing the
campaign, the practice trial's training and the final exam. The records written
are the same kinds the agent path writes, by the same functions. Nothing here
runs a scientific campaign or reaches a chain.
"""

from __future__ import annotations

import json

HOTKEY = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"


def journey_host(root, *, patch=setattr):
    """`patch(target, name, value)` installs each fixture. A process of its own
    (the smoke, a stdio server) uses plain setattr; a test runner passes
    pytest's monkeypatch.setattr so nothing outlives the test."""
    return _journey_host(root, patch)


def _journey_host(root, patch):
    """The real campaign host, over real campaign records, with no agent.

    Real: the RunnerAdapter, the operations table and its gates, the launch
    thread and control settling, research_campaign's freeze and submit, the
    ledger and the projection. Fixture, because a smoke has no Docker images,
    keys or compute: preparing the campaign, the practice trial's training and
    the final exam. The records written are the same kinds the agent path
    writes, by the same functions.
    """
    from types import SimpleNamespace

    from carbon.chain.models import MetagraphSnapshot, Participant
    from carbon.challenge_registry.campaigns import campaign_for
    from carbon.development_session import research_campaign, research_rewards
    from carbon.development_session.chain_onboarding import (
        PublicAddress,
        RegisteredMiner,
        carbon_testnet_context,
    )
    from carbon.development_session.profile import canonical, digest
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS, RunnerAdapter

    campaigns = root / "campaigns"
    campaigns.mkdir(mode=0o700)
    runtime = {
        "implementation": {"revision": "a" * 40},
        "images": ["sha256:" + "d" * 64],
    }
    cfg = {
        "profile_id": "journey-profile",
        "principal": "alice",
        "campaigns_root": str(campaigns),
        "runtime": runtime,
        "accepted_revision": "a" * 40,
        "paths": {name: str(root / (name + ".json")) for name in PATH_FIELDS},
    }

    def registration(_cfg):
        return RegisteredMiner(
            MetagraphSnapshot(
                context=carbon_testnet_context(),
                finalized_block=100,
                block_hash="0x" + "cd" * 32,
                timestamp_ms=1,
                participants=(
                    Participant(
                        uid=0, hotkey=HOTKEY, coldkey="5" + "C" * 47, registered_at=1
                    ),
                ),
            ),
            PublicAddress(HOTKEY),
        )

    class Training:
        """The practice trial's training, as a fixture: it records a result
        the freeze rule reads, exactly where a real trial records one."""

        def __init__(self, ledger):
            self.ledger = ledger

        async def call(self, name, arguments, identity):
            recipe = json.loads(arguments["strategy_json"])
            body = canonical(
                {
                    "provenance": "REAL_JAX_PUBLIC_PRACTICE",
                    "recipe": recipe,
                    "completed_steps": 8,
                    "worker_seconds": 1.5,
                    "diagnostics": {"descriptive_score": 0.5},
                }
            )
            with self.ledger.db() as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS research_results(owner TEXT NOT NULL,task TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(owner,task))"
                )
                db.execute(
                    "INSERT INTO research_results VALUES(?,?,?,?)",
                    ("miner-requester", identity, body, digest(body)),
                )
            return {"status": "SUCCEEDED", "identity": identity}

    async def prepare(args, *, ledger=None):
        manifest_path = args.root / "campaign-manifest.json"
        if not manifest_path.exists():
            manifest = {
                **args.product.manifest_fields(),
                "owner": "miner-requester",
                "implementation": runtime["implementation"],
                "images": runtime["images"],
                "objective": "UI ENGINEERING FIXTURE",
                "sampling": "fixture",
                "control": "fixture",
                "selection": "fixture",
                "replica_policy": "three",
                "provider": {"model": "fixture-model"},
            }
            manifest_path.write_bytes(canonical(manifest))
            ledger.freeze(manifest)
        manifest = json.loads(manifest_path.read_bytes())
        return research_campaign.PreparedCampaign(
            args=args,
            ledger=ledger,
            owner="miner-requester",
            manifest=manifest,
            seeds={},
            role_root=None,
            data=None,
            image=None,
            key=None,
            config=None,
            composition=SimpleNamespace(tasks=SimpleNamespace(close=lambda: None)),
            sdk=Training(ledger),
            task=None,
            grant=None,
            agent_policy=None,
            campaign=campaign_for(None),
        )

    async def final_epoch(args, ledger, owner, epoch, strategy, *_):
        return (
            {
                "disposition": "UI_FIXTURE_NOT_EVALUATED",
                "scores": {},
                "mandatory_failures": [],
            },
            "fixture-ref",
        )

    patch(research_campaign, "prepare", prepare)
    patch(research_campaign, "final_epoch", final_epoch)
    patch(research_campaign, "report", lambda *_, **__: None)
    patch(research_rewards, "update_simulation", lambda *_, **__: None)
    host = RunnerAdapter(
        root / "runner.sqlite3", principal="alice", registration=registration
    )
    host.configured = lambda: cfg
    host.preflight = lambda: {
        "available": True,
        "profile": "journey-profile",
        "status": "ENGINEERING_FIXTURE_ONLY",
        "runtime_revision": "fixture-runtime-no-execution",
    }
    return host
