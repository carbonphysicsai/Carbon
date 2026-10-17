"""Signed direct DEVELOPMENT transport against retained task records.

This exercises the real Bittensor signer/verifier and durable task projection.
It does not mount an HTTP listener or the Launchpad browser, and does not
replace an externally controlled miner key or a real reconstruction run.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import os
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.chain import MetagraphSnapshot, Participant
from carbon.chain.auth import (
    AuthCode,
    AuthFailure,
    BittensorHotkeyVerifier,
    BittensorMessageSigner,
)
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal
from tests.cpu._signer_harness import in_thread_signer

NOW = 100_000_000_000


def _sdk():
    if importlib.util.find_spec("bittensor") is None:
        if os.environ.get("CARBON_REQUIRE_CHAIN_SDK") == "1":
            pytest.fail("Installed SDK auth contract is required")
        pytest.skip("Installed SDK contract runs in canonical Linux")
    from bittensor.keyfiles import Keypair

    return Keypair


class _Adapter:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    async def observe(self, *, minimum_finalized_block):
        del minimum_finalized_block
        return self.snapshot


def _wire(context, snapshot, key, operation, request, index):
    call = research.ServiceCall(research.RESEARCH_NAMESPACE, operation, request)
    return message(
        context,
        snapshot.snapshot_id,
        key,
        session="direct-v3-user-door",
        request=f"direct-user-door-{index}",
        tool=research.RESEARCH_NAMESPACE,
        fields={
            "call_base64": base64.b64encode(research.canonical_bytes(call)).decode(
                "ascii"
            )
        },
    )


def _read(result):
    reply = research.load_canonical(
        base64.b64decode(result["protocol_reply_base64"]), research.ServiceReply
    )
    view = (
        research.load_canonical(
            base64.b64decode(result["terminal_observation_base64"]),
            research.DirectTaskViewV3,
        )
        if result["terminal_observation_base64"] is not None
        else None
    )
    return reply, view


def test_signed_gateway_reads_and_cancels_retained_direct_task(tmp_path, monkeypatch):
    """A genuine SDK signature reaches the same owner-bound durable view."""
    from carbon.chain import ChainContext

    keypair = _sdk()
    miner = keypair.create_from_uri("//Alice")
    validator = keypair.create_from_uri("//Bob")
    context = ChainContext("localnet", "ws://127.0.0.1:9944", "dev", "0x" + "1" * 64, 1)
    request, provider, discovery = _fixture(tmp_path, monkeypatch)
    snapshot = MetagraphSnapshot(
        context,
        10,
        "0x" + "2" * 64,
        NOW // 1_000_000,
        (
            Participant(0, validator.ss58_address, "validator-cold", 1),
            Participant(1, miner.ss58_address, "miner-cold", 2),
        ),
    )
    gateway = AuthenticatedGateway(
        context,
        request.challenge_key,
        validator.ss58_address,
        _Adapter(snapshot),
        BittensorHotkeyVerifier(),
        ReceiptJournal(tmp_path / "transport.sqlite3", context),
        clock_ns=lambda: NOW,
    )

    with in_thread_signer(miner, clock=lambda: NOW) as external:
        signer = BittensorMessageSigner(external)

        def signed(operation, request_body, index):
            wire = _wire(
                context,
                snapshot,
                request.challenge_key,
                operation,
                request_body,
                index,
            )
            return wire, signer.sign(
                wire,
                receiver=validator.ss58_address,
                nonce_ns=NOW + index,
            )

        probe, headers = signed(
            "get_challenge_info",
            research.GetChallengeInfoRequest(request.challenge_key),
            1,
        )
        owner = asyncio.run(gateway.receive(probe, headers)).requester.value
        tasks = provider(owner)
        try:
            service = research.LocalResearchService(
                research.DirectPublicResearchContext(discovery, discovery, tasks)
            )
            wrapper = AuthenticatedResearchService(gateway, {owner: service})
            composition = SimpleNamespace(service=service, tasks=tasks)

            # Existing durable record; observing it must not start construction.
            started = tasks.start_research_task(request)
            task_id = started.task.task_id
            cancelled = tasks.cancel_research_task(
                research.DirectCancelTaskRequestV3(
                    request.challenge_key, task_id, "retained-cancel-001"
                )
            )
            assert cancelled.task.state is research.DirectTaskStateV3.CANCELLED
            tasks.close()
            tasks = provider(owner)
            composition.tasks = tasks
            service = research.LocalResearchService(
                research.DirectPublicResearchContext(discovery, discovery, tasks)
            )
            composition.service = service
            wrapper = AuthenticatedResearchService(gateway, {owner: service})

            # A signed start with a false kit binding is refused before any
            # queued work or worker execution. It cannot borrow the retained
            # task's result merely because the requester and Challenge match.
            invalid = replace(request, resource_policy_digest="sha256:" + "0" * 64)
            start_wire, start_headers = signed("start_research_task", invalid, 2)
            result = asyncio.run(
                wrapper.supervised_call(
                    start_wire,
                    start_headers,
                    {owner: composition},
                    task_mode="start",
                )
            )
            reply, view = _read(result)
            assert reply.status is not research.ReplyStatus.OK
            assert view is None
            assert result["public_result"] is None
            assert tasks.queued_tasks() == ()

            observe, headers = signed(
                "get_research_result",
                research.DirectGetTaskRequestV3(request.challenge_key, task_id),
                3,
            )
            result = asyncio.run(
                wrapper.supervised_call(
                    observe, headers, {owner: composition}, task_mode="observe"
                )
            )
            reply, view = _read(result)
            assert reply.status is research.ReplyStatus.OK
            assert view.state is research.DirectTaskStateV3.CANCELLED
            assert view.task_id == task_id
            assert result["public_result"] is None
            assert result["requires_reconciliation"] is False
            assert result["official_eligible"] is False
            with pytest.raises(AuthFailure) as replay:
                asyncio.run(
                    wrapper.supervised_call(
                        observe,
                        headers,
                        {owner: composition},
                        task_mode="observe",
                    )
                )
            assert replay.value.code is AuthCode.REPLAY

            cancel, headers = signed(
                "cancel_research_task",
                research.DirectCancelTaskRequestV3(
                    request.challenge_key, task_id, "retained-cancel-001"
                ),
                4,
            )
            result = asyncio.run(
                wrapper.supervised_call(
                    cancel, headers, {owner: composition}, task_mode="cancel"
                )
            )
            reply, view = _read(result)
            assert reply.status is research.ReplyStatus.OK
            assert reply.result.disposition is research.CancellationDisposition.TOO_LATE
            assert view.state is research.DirectTaskStateV3.CANCELLED
            assert view.task_id == task_id
        finally:
            tasks.close()
