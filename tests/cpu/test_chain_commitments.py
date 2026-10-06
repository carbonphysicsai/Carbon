"""The read-only on-chain commitment reader (OD-7; VALIDATOR-14).

The chain read is injected (no network). The admission check runs on battery's
real daemon fixtures through `deployment.evaluate`.
"""

import asyncio
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    backend,  # noqa: F401 - fixture
    make,
    refs,  # noqa: F401 - fixture
    submission,
)

from carbon.battery import deployment
from carbon.battery.compile import compile_recipe
from carbon.battery.daemon import commitment_digest
from carbon.chain.commitments import ChainCommitmentReader, CommitmentUnavailable
from carbon.chain.models import ChainContext, ChainFailure, FailureCode

CONTEXT = ChainContext(
    network="testnet",
    endpoint="wss://test.finney.opentensor.ai:443",
    provider="opentensor",
    genesis_hash="0x" + "a" * 64,
    netuid=567,
)
DIGEST = "sha256:" + "b" * 64


def reader(answer):
    async def fetch(context, hotkey):
        assert context is CONTEXT
        if isinstance(answer, Exception):
            raise answer
        return answer(hotkey) if callable(answer) else answer

    async def fetch_all(context):
        # The listing D6's cross-hotkey priority reads: hk1's commitment only.
        if isinstance(answer, Exception):
            raise answer
        value = answer("hk1") if callable(answer) else answer
        return [] if value is None else [("hk1", value[0], value[1])]

    return ChainCommitmentReader(CONTEXT, fetch=fetch, fetch_all=fetch_all)


def test_a_digest_commitment_is_read_with_its_block():
    assert reader((DIGEST, 123)).read("hk1") == {"digest": DIGEST, "block": 123}


@pytest.mark.parametrize(
    "answer", [None, ("not a digest", 5), ("sha256:" + "B" * 64, 5), (7, 5)]
)
def test_no_commitment_or_a_non_digest_reads_as_none(answer):
    assert reader(answer).read("hk1") is None


@pytest.mark.parametrize(
    "failure", [ChainFailure(FailureCode.UNAVAILABLE), OSError("down"), KeyError()]
)
def test_a_chain_failure_is_infrastructure(failure):
    with pytest.raises(CommitmentUnavailable):
        reader(failure).read("hk1")


def test_a_malformed_block_is_infrastructure():
    with pytest.raises(CommitmentUnavailable):
        reader((DIGEST, -1)).read("hk1")


def test_it_can_be_called_from_inside_an_event_loop():
    async def intake():
        return reader((DIGEST, 9)).read("hk1")

    assert asyncio.run(intake()) == {"digest": DIGEST, "block": 9}


def test_the_deployment_refuses_a_malformed_reader_configuration():
    good = {
        "network": "testnet",
        "endpoint": "wss://test.finney.opentensor.ai:443",
        "provider": "opentensor",
        "genesis_hash": "0x" + "a" * 64,
        "netuid": 567,
    }
    assert type(deployment._commitment_reader({"commitment_reader": good})) is (
        ChainCommitmentReader
    )
    assert deployment._commitment_reader({}) is None
    for bad in (
        {**good, "extra": 1},
        {k: v for k, v in good.items() if k != "netuid"},
        {**good, "endpoint": "http://plain"},
        {**good, "genesis_hash": "zz"},
        "testnet",
    ):
        with pytest.raises(deployment.EvaluationUnavailable) as refused:
            deployment._commitment_reader({"commitment_reader": bad})
        assert refused.value.code == "evaluation_config_commitment_reader"


def _expected(sub):
    _, recipe = compile_recipe(sub.strategy)
    return commitment_digest(
        sub.strategy["challenge_id"], sub.contract_digest, recipe.strategy_hash
    )


@pytest.mark.parametrize(
    ("answer", "outcome"),
    [
        ("match", "ADMITTED"),
        ("mismatch", "commitment_required"),
        ("missing", "commitment_required"),
        ("down", "commitment_reader_unavailable"),
    ],
)
def test_admission_through_the_deployment(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
    answer,
    outcome,
):
    sub = submission("hk1")
    chain = {
        "match": (_expected(sub), 40),
        "mismatch": (DIGEST, 40),
        "missing": None,
        "down": ChainFailure(FailureCode.UNAVAILABLE),
    }[answer]
    target = make(
        tmp_path, refs, backend, require_commitment=True, commitments=reader(chain)
    )
    target.lock_path = str(tmp_path / "state.sqlite3.lock")
    target.readonly = False
    if outcome == "ADMITTED":
        result = deployment.evaluate(target, sub)
        assert result["state"] != "INVALID_CONSTRUCTION"
        binding = target.store.submission(result["submission_id"])["binding"]
        assert binding["commitment"] == {"digest": _expected(sub), "block": 40}
        return
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.evaluate(target, sub)
    assert refused.value.code == outcome
    # Nothing is recorded against the miner either way.
    assert target.store.pending_submissions() == []


def test_holders_lists_every_hotkey_showing_a_digest_earliest_first():
    rows = [
        ("hkB", DIGEST, 140),
        ("hkA", DIGEST, 100),
        ("hkC", "sha256:" + "c" * 64, 90),
        ("hkD", None, 80),  # a sealed timelocked commitment shows no content
    ]

    async def fetch_all(context):
        return rows

    found = ChainCommitmentReader(CONTEXT, fetch_all=fetch_all).holders(DIGEST)
    assert found == [("hkA", 100), ("hkB", 140)]


@pytest.mark.parametrize(
    "failure", [ChainFailure(FailureCode.UNAVAILABLE), RuntimeError("x")]
)
def test_a_holders_failure_is_infrastructure(failure):
    async def fetch_all(context):
        raise failure

    with pytest.raises(CommitmentUnavailable):
        ChainCommitmentReader(CONTEXT, fetch_all=fetch_all).holders(DIGEST)
