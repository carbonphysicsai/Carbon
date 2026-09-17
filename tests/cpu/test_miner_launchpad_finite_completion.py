"""Orchestrator/ledger regressions only: external work is non-spending fixtures."""

import asyncio
from types import SimpleNamespace

import pytest

from carbon.development_session import research_campaign as campaign
from carbon.development_session import research_rewards
from carbon.development_session.profile import canonical
from carbon.development_session.research_admission import PROFILE, SCHEMA, Admission
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    CampaignLedger,
)


def setup_campaign(tmp_path, monkeypatch, epochs):
    root = tmp_path / "campaign"
    tmp_path.chmod(0o700)
    admission = None
    if epochs is not None:
        grant = {
            "schema": SCHEMA,
            "status": "APPROVED",
            "authority": "ENGINEERING_FIXTURE_ONLY",
            "grant_id": "fixture-grant",
            "campaign_id": "fixture-campaign",
            "root": str(root),
            "principal": "alice",
            "miner_identity": "fixture-miner",
            "profile": PROFILE,
            "runtime": {
                "implementation": "fixture",
                "images": ["trusted-fixture", "analysis-fixture"],
            },
            "provider": "openai-responses",
            "account_ref": "fixture-no-credential",
            "campaign_count": 1,
            "ceilings": {**CEILINGS, "epochs": epochs},
            "elapsed_seconds": ELAPSED_SECONDS,
            "expires_unix": 50000,
            "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
            "retry_allowance": 0,
        }
        path = tmp_path / "grant.json"
        path.write_bytes(canonical(grant))
        path.chmod(0o600)
        admission = Admission.load(path)
    meter = CampaignLedger(root, clock=lambda: 1000, admission=admission)
    if admission is not None:
        meter.generation = CampaignControl(meter).acquire()
    private = tmp_path / "private-fixture"
    private.write_bytes(
        canonical(
            {"netuid": 567, "hotkey": "fixture-miner", "key_file": "unused-fixture"}
        )
    )
    private.chmod(0o600)
    args = SimpleNamespace(
        root=root,
        command="run",
        principal="alice",
        accepted_revision="fixture",
        image_manifest=private,
        analysis_image_manifest=private,
        api_key_file=private,
        operator_config=private,
        miner_public=private,
        miner_password_file=private,
    )
    closed = []
    monkeypatch.setattr(campaign, "accepted_implementation", lambda _: "fixture")
    monkeypatch.setattr(
        campaign,
        "load_image_identity",
        lambda _: SimpleNamespace(image_id="trusted-fixture"),
    )
    monkeypatch.setattr(campaign, "verify_current_worker", lambda *_: None)
    monkeypatch.setattr(campaign, "doctor", lambda **_: SimpleNamespace(eligible=True))
    monkeypatch.setattr(
        campaign,
        "load_analysis_image",
        lambda _: SimpleNamespace(
            image_id="analysis-fixture", parent_image="trusted-fixture"
        ),
    )
    monkeypatch.setattr(campaign, "verify_image", lambda _: None)
    monkeypatch.setattr(campaign, "ResponsesTransport", lambda _: None)
    monkeypatch.setattr(
        campaign,
        "load_config",
        lambda _: SimpleNamespace(
            netuid=567, context=None, publisher_hotkey="fixture-publisher"
        ),
    )
    monkeypatch.setattr(campaign, "open_external_hotkey", lambda *_: None)
    monkeypatch.setattr(
        campaign,
        "LocalMinerConnection",
        lambda *_: SimpleNamespace(service=SimpleNamespace(gateway=None)),
    )

    async def requester(_):
        return "miner-requester"

    monkeypatch.setattr(campaign, "requester", requester)
    monkeypatch.setattr(campaign, "generate_roles", lambda *_, **__: root)
    monkeypatch.setattr(campaign, "PublicReferenceData", lambda **_: None)
    monkeypatch.setattr(campaign, "PublicMaterial", lambda _: None)
    monkeypatch.setattr(campaign, "PublicPractice", lambda **_: None)
    monkeypatch.setattr(
        campaign,
        "make_research_service",
        lambda **_: SimpleNamespace(
            service=None, tasks=SimpleNamespace(close=lambda: closed.append(True))
        ),
    )
    monkeypatch.setattr(campaign, "AuthenticatedResearchService", lambda *_: None)
    monkeypatch.setattr(campaign, "ResearchMinerTools", lambda **_: None)
    monkeypatch.setattr(campaign, "trial_supports_selection", lambda *_: True)
    monkeypatch.setattr(campaign, "report", lambda *_, **__: None)
    monkeypatch.setattr(research_rewards, "update_simulation", lambda *_, **__: None)
    return args, meter, closed


@pytest.mark.parametrize("epochs", [None, 0, 1, 2])
def test_frozen_epoch_bound_completes_without_overrun_and_terminal_resume_is_inert(
    tmp_path, monkeypatch, epochs
):
    args, meter, closed = setup_campaign(tmp_path, monkeypatch, epochs)
    observed, finals = [], []

    async def epoch(ledger, *, owner, epoch, **_):
        identity = "research-epoch-" + str(epoch)
        assert ledger.reserve(
            identity,
            owner=owner,
            phase="selection",
            request={"fixture": epoch},
            resources={"epochs": 1},
        )["dispatch"]
        ledger.finish(
            identity,
            owner=owner,
            state="SUCCEEDED",
            actual={"epochs": 1},
            result={"fixture": True},
        )
        (ledger.root / ("epoch-" + str(epoch))).mkdir()
        observed.append(epoch)
        return {"status": "SELECTED", "strategy": campaign.CONTROL}

    async def final(args, ledger, owner, epoch, *_):
        identity = "fixture-final-" + str(epoch)
        assert ledger.reserve(
            identity,
            owner=owner,
            phase="final",
            request={"fixture": epoch},
            resources={"final_replicas": 6},
        )["dispatch"]
        ledger.finish(
            identity,
            owner=owner,
            state="SUCCEEDED",
            actual={"final_replicas": 6},
            result={"fixture": True},
        )
        finals.append(epoch)
        return {
            "disposition": "REJECTED_MANDATORY",
            "scores": {},
            "mandatory_failures": {},
        }, None

    monkeypatch.setattr(campaign, "run_epoch", epoch)
    monkeypatch.setattr(campaign, "final_epoch", final)
    asyncio.run(campaign.execute(args, ledger=meter))
    expected = list(range(1, (2 if epochs is None else epochs) + 1))
    assert observed == finals == expected
    assert closed == [True]
    assert (meter.root / "campaign-complete.json").exists()
    status = meter.status(owner="miner-requester")
    assert status["used"]["epochs"] == len(expected)
    assert status["used"]["final_replicas"] == 6 * len(expected)
    assert all(op["actual"] is not None for op in status["operations"])
    frozen = (meter.root / "campaign-manifest.json").read_bytes()
    grant = meter.admission.path.read_bytes() if meter.admission else None
    args.command = "resume"
    asyncio.run(campaign.execute(args, ledger=meter))
    assert observed == finals == expected and closed == [True]
    assert meter.status(owner="miner-requester") == status
    assert (meter.root / "campaign-manifest.json").read_bytes() == frozen
    assert (meter.admission.path.read_bytes() if meter.admission else None) == grant


@pytest.mark.parametrize("outcome", ["STOPPED", "FAILED_INFRA"])
def test_epoch_limit_does_not_turn_stop_or_failed_final_into_more_work(
    tmp_path, monkeypatch, outcome
):
    args, meter, closed = setup_campaign(tmp_path, monkeypatch, 2)
    calls = []

    async def epoch(ledger, *, owner, **kwargs):
        identity = "research-epoch-" + str(kwargs["epoch"])
        assert ledger.reserve(
            identity,
            owner=owner,
            phase="selection",
            request={"fixture": True},
            resources={"epochs": 1},
        )["dispatch"]
        ledger.finish(
            identity,
            owner=owner,
            state="SUCCEEDED",
            actual={"epochs": 1},
            result={"fixture": True},
        )
        calls.append(kwargs["epoch"])
        return (
            {"status": "STOPPED"}
            if outcome == "STOPPED"
            else {"status": "SELECTED", "strategy": campaign.CONTROL}
        )

    async def final(args, ledger, owner, *_):
        assert ledger.reserve(
            "fixture-final",
            owner=owner,
            phase="final",
            request={"fixture": True},
            resources={"final_replicas": 3},
        )["dispatch"]
        raise RuntimeError("fixture independent evaluation infrastructure failure")

    monkeypatch.setattr(campaign, "run_epoch", epoch)
    monkeypatch.setattr(campaign, "final_epoch", final)
    if outcome == "FAILED_INFRA":
        with pytest.raises(RuntimeError, match="infrastructure failure"):
            asyncio.run(campaign.execute(args, ledger=meter))
        assert not (meter.root / "campaign-complete.json").exists()
        operation = next(
            op
            for op in meter.status(owner="miner-requester")["operations"]
            if op["id"] == "fixture-final"
        )
        assert operation["state"] == "RESERVED" and operation["actual"] is None
        assert meter.status(owner="miner-requester")["used"]["final_replicas"] == 3
    else:
        asyncio.run(campaign.execute(args, ledger=meter))
        assert (meter.root / "campaign-complete.json").exists()
    assert calls == [1] and closed == [True]
