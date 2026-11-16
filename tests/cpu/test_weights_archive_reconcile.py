"""Reconcile-only reads through an archive endpoint (116 epoch 26433, 15 Nov): explicit doubles, no network."""

import asyncio
import inspect
import json
from types import SimpleNamespace

import pytest
from test_net1_chain_adapter import BLOCK, GENESIS, context, installed_sdk
from test_reward_ledger import run
from test_validator_setup_weights import config

from carbon.chain.publication import PublicationFailure
from carbon.validator_setup import weights
from carbon.validator_setup.bundle import SetupRefused

ARCHIVE = "wss://archive.fixture.invalid:443"
OTHER = "0x" + "c" * 64


def reveal_events():
    return [
        {
            "event": {
                "module_id": "SubtensorModule",
                "event_id": "TimelockedWeightsRevealed",
                "attributes": (1, "validator"),
            }
        }
    ]


class Pinned:
    """The pinned node past its state window: it still names blocks, but serves no history."""

    def __init__(self):
        self.calls = []

    async def block_hash(self, number):
        self.calls.append(("block_hash", number))
        return GENESIS if number == 0 else BLOCK

    async def events(self, _block_hash):
        raise AssertionError(
            "pinned node must not be asked for events when an archive is configured"
        )

    async def find_extrinsic(self, *_args):
        raise AssertionError(
            "pinned node must not serve history when an archive is configured"
        )

    async def query(self, *_args, **_kwargs):
        raise AssertionError(
            "pinned node must not serve history when an archive is configured"
        )


class Archive:
    def __init__(self, genesis=GENESIS, block=BLOCK):
        self.genesis, self.block, self.reads = genesis, block, []

    async def block_hash(self, number):
        return self.genesis if number == 0 else self.block

    async def events(self, block_hash):
        self.reads.append(("events", block_hash))
        return reveal_events()

    async def find_extrinsic(self, tx_hash, block_hash):
        self.reads.append(("find_extrinsic", block_hash))
        return SimpleNamespace(block_hash=block_hash, success=True)

    async def query(self, module, name, params, block_hash=None):
        self.reads.append((name, block_hash))
        if name == "Weights":
            return [[0, 65535], [31, 21845]]
        return [7, 8]


def backend(archive=None, endpoint=ARCHIVE):
    installed_sdk()
    from carbon.chain.sdk_weights import BittensorPublicationBackend

    value = BittensorPublicationBackend(
        context(), "validator", None, archive_endpoint=endpoint
    )
    value.client, value.substrate = object(), Pinned()
    if archive is not None:
        value.archive_client, value.archive = object(), archive
    return value


def test_reveal_transaction_and_readback_are_read_from_the_archive_at_the_pinned_block_hash():
    archive = Archive()
    value = backend(archive)
    assert run(value.revealed("validator", 105)) is True
    observed = run(value.transaction("0x" + "d" * 64, 105))
    assert (observed.success, observed.block, observed.block_hash) == (True, 105, BLOCK)
    snapshot = SimpleNamespace(finalized_block=105, block_hash=BLOCK)
    row, last = run(value.weight_row(snapshot, 1))
    assert row == [[0, 65535], [31, 21845]] and last == 8
    assert {block_hash for _, block_hash in archive.reads} == {BLOCK}
    # the pinned node named genesis + the block every time
    assert ("block_hash", 105) in value.substrate.calls and (
        "block_hash",
        0,
    ) in value.substrate.calls


@pytest.mark.parametrize(
    "archive",
    [Archive(genesis=OTHER), Archive(block=OTHER)],
    ids=["archive-genesis-differs", "archive-block-hash-differs"],
)
def test_an_archive_on_another_chain_or_fork_is_never_read(archive):
    value = backend(archive)
    with pytest.raises(PublicationFailure, match="REVEAL_OBSERVATION_UNAVAILABLE"):
        run(value.revealed("validator", 105))
    with pytest.raises(
        PublicationFailure, match="TRANSACTION_RECONCILIATION_UNAVAILABLE"
    ):
        run(value.transaction("0x" + "d" * 64, 105))
    assert archive.reads == []
    with pytest.raises(PublicationFailure, match="ARCHIVE_CHAIN_MISMATCH"):
        run(value._history(105))


def test_without_an_archive_the_pinned_node_serves_every_read_as_before():
    installed_sdk()
    from carbon.chain.sdk_weights import BittensorPublicationBackend

    class Local(Archive):
        pass

    value = BittensorPublicationBackend(context(), "validator", None)
    local = Local()
    value.client, value.substrate = object(), local
    assert value.archive_endpoint is None
    assert run(value.revealed("validator", 105)) is True
    assert local.reads == [("events", BLOCK)]


@pytest.mark.parametrize(
    "endpoint", ["https://archive.invalid", "archive", 5, "wss://" + "a" * 600]
)
def test_malformed_archive_endpoints_refuse(endpoint):
    installed_sdk()
    from carbon.chain.sdk_weights import BittensorPublicationBackend

    with pytest.raises(PublicationFailure, match="INVALID_ARCHIVE_ENDPOINT"):
        BittensorPublicationBackend(
            context(), "validator", None, archive_endpoint=endpoint
        )


def test_archive_connection_refuses_on_its_own_genesis(monkeypatch):
    bt = installed_sdk()
    closed = []

    class Sub:
        def __init__(self, endpoint, **kwargs):
            assert endpoint == ARCHIVE and kwargs == {
                "fallback_endpoints": [],
                "archive_endpoints": [],
                "retry_forever": False,
            }

        async def connect(self):
            return None

        async def block_hash(self, number):
            return OTHER

    class Client:
        def __init__(self, endpoint, substrate):
            assert endpoint == ARCHIVE

        async def close(self):
            closed.append(True)

    monkeypatch.setattr(bt, "RpcSubstrate", Sub)
    monkeypatch.setattr(bt, "Client", Client)
    value = backend()
    with pytest.raises(
        PublicationFailure, match="ARCHIVE_UNAVAILABLE_OR_GENESIS_MISMATCH"
    ):
        run(value._start_archive())
    assert closed == [True] and value.archive is None


def test_signing_and_observation_never_see_the_archive():
    installed_sdk()
    from carbon.chain.sdk_weights import BittensorPublicationBackend

    for method in (
        BittensorPublicationBackend.observe,
        BittensorPublicationBackend.execute,
        BittensorPublicationBackend.start,
    ):
        source = inspect.getsource(method)
        assert "self.archive" not in source and "_history" not in source
        assert "archive_endpoints=[]" in source or "start" not in method.__name__


# --- the weights command's reconcile-only mode -------------------------------------------------------------------


def pause(parent, on=True):
    from carbon.challenge_validator import operator_pause

    if on:
        operator_pause.flag_path(parent).write_text(
            json.dumps({"weights_paused": True})
        )


def setup(tmp_path, monkeypatch, *, pending="dispatch-26433", settled=None):
    from carbon.chain import sdk_weights
    from carbon.rewards import testnet_winner_publication as publication

    path, _raw = config(tmp_path)
    parent = tmp_path / "journals"
    parent.mkdir(mode=0o700)
    journal = parent / "weights.sqlite3"
    journal.write_bytes(b"fixture-journal")
    seen = {}

    def forbidden(*args, **kwargs):
        raise AssertionError("reconcile-only must not open a wallet or publish")

    monkeypatch.setattr(sdk_weights, "open_operator_wallet", forbidden)
    monkeypatch.setattr(
        publication, "_issuer", lambda args, config, journal: "fixture-issuer"
    )

    class Backend:
        def __init__(
            self, context, publisher, wallet, *, network, archive_endpoint=None
        ):
            seen.update(context=context, wallet=wallet, archive=archive_endpoint)

        async def close(self):
            seen["closed"] = True

    class Journal:
        def __init__(self):
            self.state = "REVEAL_PENDING"

        def pending(self):
            return pending

        def get(self, identity):
            assert identity == pending
            return {"state": settled or self.state}

    class Publisher:
        def __init__(self, issuer, backend):
            self.journal = Journal()

        publish = forbidden

    async def settle(publisher):
        seen["settled"] = True
        return (
            None
            if settled
            else {"state": "REVEAL_PENDING", "reason": "FINALIZED_COMMIT_IS_NOT_REVEAL"}
        )

    monkeypatch.setattr(sdk_weights, "BittensorPublicationBackend", Backend)
    monkeypatch.setattr(publication, "TestnetWinnerPublisher", Publisher)
    monkeypatch.setattr(publication, "settle_pending", settle)
    args = SimpleNamespace(
        config=path, action="run", journal=journal, reconcile_archive_endpoint=ARCHIVE
    )
    return args, parent, seen


def test_reconcile_only_settles_with_the_archive_and_no_wallet_and_never_publishes(
    tmp_path, monkeypatch
):
    args, parent, seen = setup(tmp_path, monkeypatch, settled="FINALIZED")
    pause(parent)
    result = asyncio.run(weights.execute(args))
    assert result == {
        "status": "SETTLED",
        "dispatch": "dispatch-26433",
        "state": None,
        "reason": None,
        "settled_row": "FINALIZED",
        "published": False,
    }
    assert (
        seen["archive"] == ARCHIVE
        and seen["wallet"] is None
        and seen["settled"]
        and seen["closed"]
    )
    # the journal keeps the pinned context: the operator config's own, endpoint included
    assert seen["context"].endpoint == "wss://public-fixture.invalid"


def test_reconcile_only_reports_still_pending(tmp_path, monkeypatch):
    args, parent, _seen = setup(tmp_path, monkeypatch)
    pause(parent)
    result = asyncio.run(weights.execute(args))
    assert result["status"] == "RECONCILE_PENDING" and result["published"] is False


def test_reconcile_only_with_nothing_pending_does_nothing(tmp_path, monkeypatch):
    args, parent, seen = setup(tmp_path, monkeypatch, pending=None)
    pause(parent)
    assert asyncio.run(weights.execute(args)) == {
        "status": "NOTHING_PENDING",
        "published": False,
    }
    assert "settled" not in seen and seen["closed"]


@pytest.mark.parametrize("case", ["unpaused", "preview", "no-journal"])
def test_reconcile_only_refusals_precede_issuer_backend_and_wallet(
    tmp_path, monkeypatch, case
):
    from carbon.rewards import testnet_winner_publication as publication

    args, parent, seen = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        publication,
        "_issuer",
        lambda *a: (_ for _ in ()).throw(AssertionError("issuer")),
    )
    expected = "ARCHIVE_RECONCILE_REQUIRES_WEIGHTS_PAUSE"
    if case != "unpaused":
        pause(parent)
    if case == "preview":
        args.action, expected = "preview", "ARCHIVE_RECONCILE_REQUIRES_RUN"
    if case == "no-journal":
        args.journal.unlink()
        expected = "ARCHIVE_RECONCILE_REQUIRES_EXISTING_JOURNAL"
    with pytest.raises(SetupRefused, match=expected):
        asyncio.run(weights.execute(args))
    assert seen == {}


def test_normal_run_is_unchanged_without_the_flag(tmp_path, monkeypatch):
    from carbon.challenge_validator import operator_pause

    args, parent, _seen = setup(tmp_path, monkeypatch)
    pause(parent)
    del args.reconcile_archive_endpoint
    with pytest.raises(SetupRefused, match=operator_pause.WEIGHTS_PAUSED):
        asyncio.run(weights.execute(args))


def test_cli_flag_parses_into_the_weights_command():
    from carbon.validator_setup import __main__ as cli

    source = inspect.getsource(cli.main)
    assert '"--reconcile-archive-endpoint"' in source
