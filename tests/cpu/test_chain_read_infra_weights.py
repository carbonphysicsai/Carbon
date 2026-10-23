"""A weights run whose chain read fails sets no weights (12h S4 receipt).

The testnet weights run (`testnet_winner_publication run`) reads the chain
through its own SDK connection (`sdk_weights.BittensorPublicationBackend`),
not the shared reader. With the endpoint refusing the read as the public RPC
did (the SDK's RpcPolicyError, HTTP 429 at connect), the run:
- never reaches the publisher's publish or the backend's execute, so no
  set_weights call is built, signed or sent;
- ends closed, with a typed status and no provider text.
The real backend runs over the installed SDK with its RPC substrate patched
to refuse; the issuer, wallet and publisher's journal are stand-ins, because
nothing past the refused read may run.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.chain import sdk_weights
from carbon.rewards import testnet_winner_publication as twp

bt = pytest.importorskip("bittensor")


def _context():
    from carbon.chain.models import ChainContext

    return ChainContext(
        "testnet", "wss://test.chain.invalid:443", "public-rpc", "0x" + "cd" * 32, 567
    )


class RefusingSubstrate:
    """The SDK's RPC substrate, refusing at connect as the public RPC did."""

    connects = 0

    def __init__(self, *args, **kwargs):
        pass

    async def connect(self):
        RefusingSubstrate.connects += 1
        raise bt.RpcPolicyError(
            "RPC endpoint rate limited this source (HTTP 429): PRIVATE",
            status_code=429,
            retry_after="60",
            policy="ws_upgrade_60s/10s",
            reason="rate_exceeded",
        )

    async def block_hash(self, block):  # pragma: no cover - never reached
        raise AssertionError("read past a refused connect")


class Client:
    def __init__(self, *args, **kwargs):
        pass

    async def close(self):
        pass


def test_a_weights_run_with_a_refused_chain_read_sets_no_weights(
    monkeypatch, capsys, tmp_path
):
    calls = {"publish": 0, "execute": 0}
    monkeypatch.setattr(bt, "RpcSubstrate", RefusingSubstrate)
    monkeypatch.setattr(bt, "Client", Client)
    monkeypatch.setattr(sdk_weights, "require_sdk", lambda: None)

    async def execute(self, *args, **kwargs):
        calls["execute"] += 1

    monkeypatch.setattr(sdk_weights.BittensorPublicationBackend, "execute", execute)
    config = SimpleNamespace(context=_context(), publisher_hotkey="5Publisher")
    monkeypatch.setattr(
        "carbon.development_testnet.operator.load_config", lambda _path: config
    )
    monkeypatch.setattr("carbon.development_testnet.operator._wallet", lambda _c: None)
    monkeypatch.setattr(
        twp, "_issuer", lambda args, config, journal: SimpleNamespace(issue=None)
    )

    class Publisher:
        def __init__(self, issuer, backend):
            self.journal = SimpleNamespace(pending=lambda: None)

        async def publish(self, intent):
            calls["publish"] += 1

    monkeypatch.setattr(twp, "TestnetWinnerPublisher", Publisher)
    argv = ["run"] + [
        part
        for name in ("config", "standing", "journal", "ledger")
        for part in ("--" + name, str(tmp_path / name))
    ]
    assert twp.main(argv) == 2
    out = capsys.readouterr().out
    assert json.loads(out) == {"status": "FAILED_CLOSED"}
    assert "PRIVATE" not in out and "429" not in out
    # The read was tried and refused; nothing past it ran.
    assert RefusingSubstrate.connects >= 1
    assert calls == {"publish": 0, "execute": 0}


def test_the_backend_refuses_typed_before_any_execute(monkeypatch):
    monkeypatch.setattr(bt, "RpcSubstrate", RefusingSubstrate)
    monkeypatch.setattr(bt, "Client", Client)
    monkeypatch.setattr(sdk_weights, "require_sdk", lambda: None)
    import asyncio

    backend = sdk_weights.BittensorPublicationBackend(
        _context(), "5Publisher", None, network="testnet"
    )
    with pytest.raises(sdk_weights.PublicationFailure) as failure:
        asyncio.run(backend.observe())
    assert str(failure.value) == "ENDPOINT_UNAVAILABLE_OR_GENESIS_MISMATCH"
    assert backend.client is None
