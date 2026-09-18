"""Real gateway/domain services over stdio using explicit engineering grants.

Only external host, registration observation and signing are fixtures. Public
discovery, recipe compilation, material tasks, persistence and grant/control
checks execute their real implementations. No paid provider or numerical worker
is invoked; this is interoperability evidence, not scientific execution evidence.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests" / "cpu")]

from carbon.development_session.profile import CHALLENGE, canonical
from carbon.development_session.research_admission import (
    MANIFEST,
    PROFILE,
    SCHEMA,
    Admission,
)
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    CampaignLedger,
)
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.miner_mcp import standard_cli

PREFIX = "carbon_research_v2__"


def private_write(path, value):
    path.write_bytes(canonical(value))
    path.chmod(0o600)


def fixture_connection(root):
    from test_c08_authenticated_miner_mcp import (
        CONTEXT,
        NOW,
        _Adapter,
        _snapshot,
        _Verifier,
    )

    from carbon.transport.gateway import AuthenticatedGateway
    from carbon.transport.store import ReceiptJournal

    snapshot = _snapshot()
    gateway = AuthenticatedGateway(
        CONTEXT,
        CHALLENGE,
        "validator",
        _Adapter(snapshot),
        _Verifier(),
        ReceiptJournal(root / "transport.sqlite3", CONTEXT),
        clock_ns=lambda: NOW,
    )

    async def observe():
        return snapshot

    return SimpleNamespace(
        service=SimpleNamespace(gateway=gateway),
        check_registration=observe,
        chain_context=CONTEXT,
        publisher="validator",
        miner_key=object(),
    )


class FixtureSigner:
    def __init__(self, key):
        pass

    def sign(self, body, **kwargs):
        from test_c08_authenticated_miner_mcp import _headers

        return _headers(body, time.time_ns())


def unavailable_practice(*args):
    raise ValueError("engineering test has no numerical worker")


def prepare(root, monkeypatch):
    import carbon.chain.auth
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS

    monkeypatch.setattr(carbon.chain.auth, "BittensorMessageSigner", FixtureSigner)
    root.chmod(0o700)
    campaign = root / "campaign"
    campaign.mkdir(mode=0o700)
    connection = fixture_connection(campaign)
    owner = asyncio.run(standard_cli._requester(connection))
    runtime = {
        "implementation": {"revision": "f" * 40},
        "images": ["fixture-cpu", "fixture-analysis"],
    }
    grant = {
        "schema": SCHEMA,
        "status": "APPROVED",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "grant_id": "mcp-stdio-fixture",
        "campaign_id": "mcp-stdio-campaign",
        "root": str(campaign),
        "principal": "operator-alice",
        "miner_identity": "fixture-miner",
        "profile": PROFILE,
        "runtime": runtime,
        "provider": "openai-responses",
        "account_ref": "no-paid-calls-fixture",
        "campaign_count": 1,
        "ceilings": CEILINGS,
        "elapsed_seconds": ELAPSED_SECONDS,
        "expires_unix": time.time() + 3600,
        "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
        "retry_allowance": 0,
    }
    grant_file = root / "grant.json"
    private_write(grant_file, grant)
    admission = Admission.load(grant_file)
    manifest = {
        "schema": MANIFEST,
        "campaign_id": grant["campaign_id"],
        "authority": grant["authority"],
        "principal": grant["principal"],
        "owner": owner,
        "runtime": runtime,
        "grant": admission.binding(),
        "ceilings": CEILINGS,
        "elapsed_seconds": ELAPSED_SECONDS,
        "implementation": runtime["implementation"],
        "images": runtime["images"],
        "objective": "test-only",
        "sampling": "test-only",
        "control": "test-only",
        "selection": "test-only",
        "replica_policy": "test-only",
        "provider": "test-only",
    }
    ledger = CampaignLedger(campaign, admission=admission)
    ledger.freeze(manifest)
    private_write(campaign / "campaign-manifest.json", manifest)
    composition = make_research_service(
        root=campaign / "research-tasks",
        ledger=ledger,
        owner=owner,
        image=SimpleNamespace(),
        public_material=PublicMaterial(None),
        practice=unavailable_practice,
    )
    composition.tasks.close()
    profile = {
        "schema": "carbon.launchpad.runner-profile.v1",
        "profile_id": "fixture-profile",
        "principal": grant["principal"],
        "grant_file": str(grant_file),
        "account_ref": grant["account_ref"],
        "enabled": True,
        "paths": {name: str(root / (name + ".json")) for name in PATH_FIELDS},
        "accepted_revision": runtime["implementation"]["revision"],
    }
    path = root / "profile.json"
    private_write(path, profile)
    return path, ledger, owner


def serve_fixture(path):
    import carbon.chain.auth
    from carbon.development_session import research_tools

    carbon.chain.auth.BittensorMessageSigner = FixtureSigner
    research_tools.BittensorMessageSigner = FixtureSigner
    standard_cli._runtime = lambda profile: (
        fixture_connection(profile.root),
        SimpleNamespace(),
        SimpleNamespace(),
        profile.root,
    )
    standard_cli._science = lambda *args: (PublicMaterial(None), unavailable_practice)
    raise SystemExit(standard_cli.main(["--configuration", str(path)]))


def parameters(path):
    from mcp.client.stdio import StdioServerParameters

    return StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve-fixture", str(path)],
        cwd=REPOSITORY,
    )


def test_actual_gateway_public_workflow_and_restart_over_stdio(tmp_path, monkeypatch):
    from mcp import Client

    path, ledger, owner = prepare(tmp_path, monkeypatch)
    task_id = None
    request = {
        "operation_id": "real-gateway-public-task-0001",
        "kind": "workspace",
        "strategy": None,
        "action": "public_material",
        "arguments": {"name": "objective"},
        "hypothesis": "Read the existing public objective",
        "expected_effect": "Plan a valid bounded recipe",
    }

    async def exercise():
        nonlocal task_id
        async with Client(parameters(path), read_timeout_seconds=30) as client:
            result = await client.call_tool(
                PREFIX + "get_challenge_info",
                {"operation_id": "real-gateway-discovery-0001"},
            )
            assert not result.is_error
            assert result.structured_content["payload"]["reply"]["status"] == "OK"
            proposed = await client.call_tool(
                PREFIX + "compile_strategy",
                {
                    "operation_id": "real-gateway-compile-0001",
                    "strategy": {
                        "schema_version": "1.0",
                        "challenge_id": "burgers-dynamics-v1",
                        "backbone": "fno",
                        "parameters": {"steps": 512, "enforce_mean": True},
                    },
                },
            )
            assert not proposed.is_error
            assert proposed.structured_content["payload"]["reply"]["status"] == "OK"
            started = await client.call_tool(PREFIX + "start_research_task", request)
            assert not started.is_error
            body = started.structured_content["payload"]
            assert body["terminal_task"]["state"] == "SUCCEEDED"
            assert (
                body["public_result"]["result"]["document"]["score_rule"]["id"]
                == "burgers-development-balanced-v2"
            )
            task_id = body["terminal_task"]["task_id"]["value"]
            status = await client.call_tool(
                PREFIX + "get_research_result",
                {
                    "operation_id": "real-gateway-status-0001",
                    "task_id": task_id,
                    "poll_sequence": 0,
                },
            )
            assert not status.is_error
            assert (
                status.structured_content["payload"]["terminal_task"]["state"]
                == "SUCCEEDED"
            )
        async with Client(parameters(path), read_timeout_seconds=30) as client:
            replay = await client.call_tool(PREFIX + "start_research_task", request)
            assert not replay.is_error
            assert (
                replay.structured_content["payload"]["terminal_task"]["task_id"][
                    "value"
                ]
                == task_id
            )

    asyncio.run(exercise())
    status = ledger.status(owner=owner)
    assert status["used"]["provider_attempts"] == 0
    assert status["used"]["provider_nanodollars"] == 0
    assert status["used"]["numerical_milliseconds"] == 0
    assert status["used"]["research_trials"] == 0
    from carbon.development_session.research_control import CampaignControl

    assert CampaignControl(ledger).status()["state"] == "INTERRUPTED"


@pytest.mark.parametrize(
    "failure", ["disabled", "not_granted", "expired", "missing_campaign", "unresolved"]
)
def test_missing_authority_or_reconciliation_fails_closed(
    tmp_path, monkeypatch, failure, capsys
):
    path, ledger, owner = prepare(tmp_path, monkeypatch)
    profile = json.loads(path.read_bytes())
    if failure == "disabled":
        private_write(path, {**profile, "enabled": False})
    elif failure in {"not_granted", "expired"}:
        grant_path = Path(profile["grant_file"])
        grant = json.loads(grant_path.read_bytes())
        grant.update(
            {"status": "REQUESTED_NOT_GRANTED"}
            if failure == "not_granted"
            else {"expires_unix": 1}
        )
        private_write(grant_path, grant)
    elif failure == "missing_campaign":
        (ledger.root / "campaign-manifest.json").unlink()
    else:
        from carbon.development_session.research_control import CampaignControl

        ledger.generation = CampaignControl(ledger).acquire()
        ledger.reserve(
            "uncertain-fixture",
            owner=owner,
            phase="research",
            request={},
            resources={"research_trials": 1},
        )
    monkeypatch.setattr(
        standard_cli,
        "_runtime",
        lambda *_: pytest.fail("unavailable admission reached runtime"),
    )
    assert standard_cli.main(["--configuration", str(path)]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert str(tmp_path) not in output.err
    assert "Carbon MCP unavailable" in output.err


def test_cli_help_does_not_require_secrets_or_runtime(capsys):
    with pytest.raises(SystemExit) as error:
        standard_cli.main(["--help"])
    assert error.value.code == 0
    assert "--configuration" in capsys.readouterr().out


@pytest.mark.parametrize("change", ["profile", "grant", "generation", "elapsed"])
def test_established_connection_rechecks_authority_on_each_call(
    tmp_path, monkeypatch, change
):
    from carbon.development_session.research_control import CampaignControl

    path, ledger, _owner = prepare(tmp_path, monkeypatch)
    profile = standard_cli.load_profile(path)
    control = CampaignControl(ledger)
    ledger.generation = control.acquire()
    bound = standard_cli._AdmittedConnection(
        fixture_connection(ledger.root), profile, ledger, control
    )
    asyncio.run(bound.check_registration())
    if change == "profile":
        private_write(path, {**profile.document, "enabled": False})
    elif change == "grant":
        private_write(
            profile.admission.path,
            {**profile.admission.document, "status": "REQUESTED_NOT_GRANTED"},
        )
    elif change == "generation":
        control.acquire()
    else:
        with ledger.db() as db:
            db.execute(
                "UPDATE campaign SET started=? WHERE id=1",
                (time.time() - ELAPSED_SECONDS - 1,),
            )
    with pytest.raises(ValueError):
        asyncio.run(bound.check_registration())


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--serve-fixture":
        raise SystemExit("explicit isolated test profile required")
    serve_fixture(Path(sys.argv[2]))
