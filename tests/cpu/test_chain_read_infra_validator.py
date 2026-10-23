"""The chain-read fix on the validator side (12h S4 receipt addition).

`carbon.chain.sdk.BittensorReader` is also the validator's reader (the score
feed's chain time, the receiver's registration read, the weights preview).
Through the score feed, the validator path that reads the chain at the
finalized head:
- a read the endpoint keeps refusing is a typed infrastructure failure
  (PROVIDER_RATE_LIMITED, `chain_read_failed_infra`), and the feed built
  without it changes no score, no standing, no king and no share - only its
  chain-time fields are null;
- a read refused twice and then served equals a single read, and so does the
  feed built from it.
No validator, receiver or intake file changes: the real reader runs over a
fake SDK whose endpoint refuses as the public RPC did (HTTP 429).
"""

from __future__ import annotations

import asyncio

import pytest
from test_chain_read_infra import FAKE_SDK, RpcPolicyError
from test_challenge_validator_battery_bank import adapter, run  # noqa: F401
from test_challenge_validator_score_feed import insert_scored, validator  # noqa: F401
from test_validator_feed_king import CROWNED, _record

from carbon.chain import sdk
from carbon.chain.adapter import translate
from carbon.chain.models import ChainContext, ChainFailure, FailureCode
from carbon.challenge_validator import canary
from carbon.challenge_validator import score_feed as sf
from scripts.dev.miner_launchpad import supervisor

CONTEXT = ChainContext(
    "testnet", "wss://test.chain.invalid:443", "public-rpc", "0x" + "cd" * 32, 567
)


class Endpoint:
    """Refuses the first `refusals` reads (HTTP 429), then serves."""

    def __init__(self, refusals):
        self.refusals = refusals
        self.calls = 0

    async def read(self, ctx, block):
        self.calls += 1
        if self.calls <= self.refusals:
            raise RpcPolicyError("rate limited: PRIVATE", retry_after="10")
        graph = {
            "netuid": 567,
            "num_uids": 1,
            "hotkeys": ["5King"],
            "coldkeys": ["5Cold"],
            "block_at_registration": [3],
        }
        return translate(ctx, block, "0x" + "ab" * 32, CROWNED + 1, graph)


@pytest.fixture
def endpoint(monkeypatch):
    """The real reader, over the fake SDK and an endpoint the test sets."""
    monkeypatch.setattr(sdk, "_shared", {})
    state = {"endpoint": None, "block": None}

    async def attempt(self, bt, ctx):
        return await state["endpoint"].read(ctx, state["block"])

    async def no_wait(self, seconds):
        await asyncio.sleep(0)

    monkeypatch.setattr(sdk.BittensorReader, "_sdk", lambda self: FAKE_SDK)
    monkeypatch.setattr(sdk.BittensorReader, "_attempt", attempt)
    monkeypatch.setattr(sdk.BittensorReader, "_sleep", no_wait)

    def use(refusals, block):
        monkeypatch.setattr(sdk, "_shared", {})
        state["endpoint"], state["block"] = Endpoint(refusals), block
        return state["endpoint"]

    return use


def standings(validator, monkeypatch, tmp_path):  # noqa: F811
    store, w = validator["store"], validator["windows"]
    monkeypatch.setattr(canary, "CANARY_HOTKEYS", ())
    insert_scored(store, "s1", "5Miner", [w["screening"]], score=0.25, block=101)
    insert_scored(store, "s2", "5King", [w["screening"]], score=0.5, block=102)
    monkeypatch.setattr(store, "finals_rows", list)
    monkeypatch.setattr(store, "incumbent", lambda: {"model_id": "m2"})
    winners = [_record("5King", None, "m2", kind="FIRST")]
    key = sf.FeedKey.create(tmp_path / "feed.key")
    blocks = [
        x["activate_block"]
        for x in (store.window(f) for f in store.batch_fingerprints())
        if x is not None
    ]

    def build(chain):
        return sf.build(
            validator["target"],
            key=key,
            hotkey="5Val",
            network="testnet",
            chain=chain,
            winners=winners,
        )

    return build, min(blocks) - 1


#: What a chain read may change in the feed: its chain-time fields (and the
#: signature and build time every new build has).
CHAIN_FIELDS = {"as_of_block", "network", "release", "signature", "generated_at"}


def scientific(feed):
    """Everything in the feed that is not chain time: scores, standings,
    exclusions, the version, and the king's identity and share policy."""
    kept = {k: v for k, v in feed.items() if k not in CHAIN_FIELDS | {"king"}}
    king = feed.get("king")
    if king is not None:
        kept["king"] = {
            k: king[k]
            for k in ("hotkey", "submission_id", "policy_digest", "crowned_utc_ms")
            if k in king
        }
    return kept


def test_a_refused_read_is_failed_infra_and_changes_no_score_or_king(
    validator, monkeypatch, tmp_path, endpoint  # noqa: F811
):
    build, block = standings(validator, monkeypatch, tmp_path)
    refusing = endpoint(refusals=99, block=block)
    # The reader's own answer: typed infrastructure, never UNSUPPORTED.
    with pytest.raises(ChainFailure) as failure:
        asyncio.run(sdk.BittensorReader().capture(CONTEXT))
    assert failure.value.code is FailureCode.RATE_LIMITED
    assert supervisor.chain_interruption_code(failure.value) == (
        "chain_read_failed_infra"
    )
    assert refusing.calls == sdk.BittensorReader._attempts
    # The score feed's read at the finalized head: absent, not raised.
    assert sf.chain_snapshot(CONTEXT) is None
    without = build(None)
    served = endpoint(refusals=0, block=block)
    with_chain = build(sf.chain_snapshot(CONTEXT))
    assert served.calls == 1
    assert without["as_of_block"] is None
    assert with_chain["as_of_block"]["number"] == block
    # Scores, standings, version and king are the same with or without it.
    assert scientific(without) == scientific(with_chain)
    assert without["version"] == with_chain["version"]
    assert [s["score"] for s in without["submissions"]] == [
        s["score"] for s in with_chain["submissions"]
    ]
    assert without["king"]["hotkey"] == with_chain["king"]["hotkey"] == "5King"
    assert sf.verify_feed(without) and sf.verify_feed(with_chain)


def test_a_retried_success_equals_a_single_read(
    validator, monkeypatch, tmp_path, endpoint  # noqa: F811
):
    build, block = standings(validator, monkeypatch, tmp_path)
    endpoint(refusals=0, block=block)
    once = sf.chain_snapshot(CONTEXT)
    retried_endpoint = endpoint(refusals=2, block=block)
    retried = sf.chain_snapshot(CONTEXT)
    assert retried_endpoint.calls == 3
    assert retried == once
    assert scientific(build(retried)) == scientific(build(once))
    assert build(retried)["as_of_block"] == build(once)["as_of_block"]
