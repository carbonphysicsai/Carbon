"""A campaign may be prepared more than once: every manual practice, freeze
and submit, and every resume, prepares it again. Each preparation's bootstrap
call must be admitted by the campaign's own receipt journal.

Found in the live battery journey (Launchpad H, 2026-09-29): a manual
campaign's first practice was refused TRANSPORT_CONFLICT inside the runner,
which recorded only INTERRUPTED.
"""

import asyncio
import time
from types import SimpleNamespace

import pytest
from test_c08_authenticated_miner_mcp import (
    CONTEXT,
    NOW,
    _Adapter,
    _headers,
    _snapshot,
    _Verifier,
)

from carbon.development_session import research_campaign
from carbon.development_session.profile import CHALLENGE
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import TransportFailure
from carbon.transport.store import ReceiptJournal


class Signer:
    def __init__(self, key):
        pass

    def sign(self, body, **kwargs):
        return _headers(body, time.time_ns())


def connection(root):
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


def test_a_campaign_can_be_prepared_again(tmp_path, monkeypatch):
    monkeypatch.setattr(research_campaign, "BittensorMessageSigner", Signer)
    live = connection(tmp_path)
    first = asyncio.run(research_campaign.requester(live))
    second = asyncio.run(research_campaign.requester(live))
    assert first == second


def test_a_reused_bootstrap_request_is_refused_by_the_journal(tmp_path, monkeypatch):
    """Specimen: the same journal refuses a second bootstrap under one fixed
    request id, which is exactly what every re-preparation used to send."""
    monkeypatch.setattr(research_campaign, "BittensorMessageSigner", Signer)
    monkeypatch.setattr(
        research_campaign.uuid, "uuid4", lambda: SimpleNamespace(hex="fixed")
    )
    live = connection(tmp_path)
    asyncio.run(research_campaign.requester(live))
    with pytest.raises(TransportFailure):
        asyncio.run(research_campaign.requester(live))
