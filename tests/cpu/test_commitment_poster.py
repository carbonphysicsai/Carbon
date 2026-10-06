"""The Launchpad's commitment flow (COMMITMENT-POSTER-01 L1-L7).

The chain is a fake; the signer is the real `carbon_miner_signer` on a real
socket, holding a public development key, with SYNTHETIC pins (see
`test_miner_signer_commit`). The miner at the terminal is played by the test.
"""

import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import submission
from test_miner_signer_commit import (
    DIGEST,
    _Asked,
    _call,
    _parts,
    _request,
    _server,
    short_dir,  # noqa: F401 - fixture
)

from carbon.battery.compile import compile_recipe
from carbon.battery.daemon import commitment_digest
from carbon.chain import commitment_poster as cp
from carbon.chain.commitments import CommitmentUnavailable
from carbon.chain.external_signer import (
    SignerCode,
    SignerFailure,
    connect_signer,
    request_commitment,
    signatures_obtained,
)

OTHER = "sha256:" + "f" * 64


class FakeChain:
    """Reads, prepares like the SDK (same parts), and broadcasts once each."""

    def __init__(self, on_chain=None, fees=((900, 100),), head=7_200):
        self.on_chain, self.fees, self.head = on_chain, list(fees), head
        self.outcome, self.read_down = "FINALIZED", False
        self.broadcasts, self.prepared = [], []

    def read(self, hotkey):
        if self.read_down:
            raise CommitmentUnavailable("down")
        return self.on_chain

    def prepare(self, hotkey, netuid, digest, period):
        assert period == cp.ERA_PERIOD == 128
        unsigned = _request(digest=digest, current=self.head)["unsigned"]
        extra, additional = _parts(current=self.head)
        payload = "0x" + (_call(digest) + extra + additional).hex()
        self.prepared.append(digest)
        return {
            "unsigned": {**unsigned, "payload": payload, "payload_json": {}},
            "payload": payload,
        }

    def estimate(self, hotkey, netuid, digest):
        fee = self.fees.pop(0) if len(self.fees) > 1 else self.fees[0]
        return (
            None if fee is None else {"partial_fee_rao": fee[0], "deposit_rao": fee[1]}
        )

    def broadcast(self, prepared, signature):
        self.broadcasts.append(signature)
        if self.outcome == "RAISE":
            raise OSError("connection lost")
        block = self.head + 2
        if self.outcome == "FINALIZED":
            self.on_chain = {"digest": self.prepared[-1], "block": block}
            return {"outcome": "FINALIZED", "block": block, "fee_rao": 1_000}
        if self.outcome == "FINALIZED_UNSEEN":
            return {"outcome": "FINALIZED", "block": block, "fee_rao": 1_000}
        return {"outcome": self.outcome, "block": block, "error": "SpaceLimitExceeded"}

    def finalized_block(self):
        return self.head


@pytest.fixture
def signer(short_dir):  # noqa: F811
    asked = _Asked()
    server = _server(short_dir, confirm=asked).bind()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = connect_signer(server.hotkey, socket_path=server.socket_path)
    held = SimpleNamespace(asked=asked, requests=[], ss58_address=client.ss58_address)

    def sign(request):
        held.requests.append(request)
        return request_commitment(client, request)

    held.sign = sign
    yield held
    server.close()
    thread.join(timeout=0.1)  # a daemon thread blocked in accept


def _with(signer, tmp_path, chain):
    return cp.CommitmentPoster(
        hotkey=signer.ss58_address, chain=chain, sign=signer.sign, state_dir=tmp_path
    )


def _never(request):
    raise AssertionError("the signer must not be asked")


# L1 ---------------------------------------------------------------------------


def test_the_launchpad_digest_is_the_daemons_expected_digest():
    sub = submission("hk1")
    _, recipe = compile_recipe(sub.strategy)
    expected = commitment_digest(
        sub.strategy["challenge_id"], sub.contract_digest, recipe.strategy_hash
    )
    assert cp.expected_digest(sub.strategy, sub.contract_digest) == expected
    assert len(expected) == 71 and cp.DIGEST.fullmatch(expected)


# L2-L6 -----------------------------------------------------------------------


def test_a_post_is_signed_once_broadcast_once_and_read_back(signer, tmp_path):
    chain = FakeChain()
    before = signatures_obtained()
    result = _with(signer, tmp_path, chain).post(DIGEST)
    assert result["code"] == "commitment_committed" and result["block"] == 7_202
    assert len(chain.broadcasts) == 1 and signatures_obtained() == before + 1
    assert [expected for _, expected in signer.asked.prompts] == [DIGEST[-8:]]
    (request,) = signer.requests
    assert set(request) == {"netuid", "digest", "unsigned", "fee"}
    row = json.loads((tmp_path / f"commitment-{signer.ss58_address}.json").read_text())
    assert row["state"] == "COMMITTED" and row["digest"] == DIGEST
    text = json.dumps(row)
    assert "key_file" not in text and "password" not in text and "signature" not in text


def test_a_digest_already_on_chain_is_not_reposted(tmp_path):
    chain = FakeChain(on_chain={"digest": DIGEST, "block": 40})
    before = signatures_obtained()
    poster = cp.CommitmentPoster(
        hotkey="5" + "C" * 47, chain=chain, sign=_never, state_dir=tmp_path
    )
    result = poster.post(DIGEST)
    assert result["code"] == "commitment_already_on_chain" and result["block"] == 40
    assert chain.broadcasts == [] and chain.prepared == []
    assert signatures_obtained() == before


def test_a_stale_commitment_is_offered_a_recommit_and_recommitted(signer, tmp_path):
    """D6 (the Carbon Validator's freshness rule): the digest is on chain but
    older than the hotkey's previous admission. The Launchpad offers to
    recommit; accepting posts the same digest again in a new tempo."""
    chain = FakeChain(on_chain={"digest": DIGEST, "block": 40})
    poster = _with(signer, tmp_path, chain)

    class Stale(Exception):
        code = "commitment_stale"

    answers = [Stale(), {"status": "evaluation_queued"}]

    def submit():
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    first = cp.commit_then_submit(poster, DIGEST, submit)
    assert first["submitted"] is False and first["code"] == "commitment_stale"
    assert first["offer"]["action"] == "recommit" and first["offer"]["digest"] == DIGEST
    assert chain.broadcasts == []  # nothing posted until the offer is taken
    again = cp.commit_then_submit(poster, DIGEST, submit, recommit=True)
    assert again["submitted"] is True
    assert again["commitment"]["code"] == "commitment_committed"
    assert chain.on_chain == {"digest": DIGEST, "block": 7_202}
    assert len(chain.broadcasts) == 1


def test_a_recommit_in_the_same_tempo_is_refused_by_the_signer(signer, tmp_path):
    chain = FakeChain()
    poster = _with(signer, tmp_path, chain)
    assert poster.post(DIGEST)["code"] == "commitment_committed"
    chain.head += 10
    result = poster.post(DIGEST, recommit=True)
    assert result["code"] == "signer_refused:ALREADY_COMMITTED_THIS_TEMPO"
    assert len(chain.broadcasts) == 1


def test_other_intake_refusals_are_not_swallowed(tmp_path):
    chain = FakeChain(on_chain={"digest": DIGEST, "block": 40})
    poster = cp.CommitmentPoster(
        hotkey="5" + "C" * 47, chain=chain, sign=_never, state_dir=tmp_path
    )

    class Refused(Exception):
        code = "commitment_required"

    def submit():
        raise Refused()

    with pytest.raises(Refused):
        cp.commit_then_submit(poster, DIGEST, submit)


def test_nothing_is_submitted_until_the_commitment_is_final(signer, tmp_path):
    chain = FakeChain()
    chain.outcome = "RAISE"
    submitted = []
    result = cp.commit_then_submit(
        _with(signer, tmp_path, chain), DIGEST, lambda: submitted.append(1)
    )
    assert result["submitted"] is False and submitted == []
    assert result["commitment"]["code"] == "commitment_ambiguous"


def test_a_returned_call_other_than_the_prepared_one_is_not_broadcast(tmp_path):
    chain = FakeChain()

    def sign(request):
        return {"signature": b"\x00" * 64, "call": b"\x07\x06", "fee_ceiling_rao": 2000}

    poster = cp.CommitmentPoster(
        hotkey="5" + "C" * 47, chain=chain, sign=sign, state_dir=tmp_path
    )
    assert poster.post(DIGEST)["code"] == "commitment_call_mismatch"
    assert chain.broadcasts == []
    assert poster.record()["state"] == "NOT_SENT"


def test_a_signature_over_anything_else_is_not_broadcast(tmp_path):
    chain = FakeChain()

    def sign(request):
        call = bytes.fromhex(request["unsigned"]["call_data"][2:])
        return {"signature": b"\x01" * 64, "call": call, "fee_ceiling_rao": 2000}

    poster = cp.CommitmentPoster(
        hotkey="5" + "C" * 47,
        chain=chain,
        sign=sign,
        state_dir=tmp_path,
        verify=lambda payload, signature, hotkey: False,
    )
    assert poster.post(DIGEST)["code"] == "commitment_signature_invalid"
    assert chain.broadcasts == []


def test_a_fee_that_rose_after_confirmation_is_not_broadcast(signer, tmp_path):
    chain = FakeChain(fees=[(900, 100), (1_900, 200)])
    result = _with(signer, tmp_path, chain).post(DIGEST)
    assert result["code"] == "commitment_fee_over_ceiling"
    assert len(signer.asked.prompts) == 1 and chain.broadcasts == []


def test_an_unknown_fee_refuses_before_the_signer_is_asked(tmp_path):
    chain = FakeChain(fees=[None])
    poster = cp.CommitmentPoster(
        hotkey="5" + "C" * 47, chain=chain, sign=_never, state_dir=tmp_path
    )
    assert poster.post(DIGEST)["code"] == "commitment_fee_unknown"


def test_a_refusal_at_the_terminal_broadcasts_nothing(signer, tmp_path):
    signer.asked.answer = False
    chain = FakeChain()
    result = _with(signer, tmp_path, chain).post(DIGEST)
    assert result["code"] == "signer_refused:NOT_CONFIRMED"
    assert chain.broadcasts == []


def test_a_signer_that_is_not_running_is_a_closed_code(tmp_path):
    def sign(request):
        raise SignerFailure(SignerCode.NOT_RUNNING)

    poster = cp.CommitmentPoster(
        hotkey="5" + "C" * 47, chain=FakeChain(), sign=sign, state_dir=tmp_path
    )
    assert poster.post(DIGEST)["code"] == "signer_not_running"
    assert poster.record()["state"] == "REFUSED"


# B10: never resent ------------------------------------------------------------


def test_an_unknown_outcome_is_reconciled_by_reading_and_never_resent(signer, tmp_path):
    chain = FakeChain()
    chain.outcome = "RAISE"
    poster = _with(signer, tmp_path, chain)
    assert poster.post(DIGEST)["code"] == "commitment_ambiguous"
    assert len(chain.broadcasts) == 1
    # A restart, while the signature's era is still live: nothing new.
    restarted = _with(signer, tmp_path, chain)
    chain.head += 100
    pending = restarted.post(DIGEST)
    assert pending["code"] == "commitment_ambiguous" and pending["pending"] == DIGEST
    assert len(chain.broadcasts) == 1 and len(signer.asked.prompts) == 1
    # The chain shows it landed after all: settled, still not resent.
    chain.on_chain = {"digest": DIGEST, "block": 7_203}
    assert restarted.post(DIGEST)["code"] == "commitment_committed"
    assert len(chain.broadcasts) == 1


def test_an_expired_unknown_outcome_allows_a_new_request(signer, tmp_path):
    chain = FakeChain()
    chain.outcome = "RAISE"
    poster = _with(signer, tmp_path, chain)
    assert poster.post(DIGEST)["code"] == "commitment_ambiguous"
    chain.head += 128 + 360  # past the era, and into another tempo
    chain.outcome = "FINALIZED"
    assert poster.post(DIGEST)["code"] == "commitment_committed"
    assert len(chain.broadcasts) == 2


def test_a_dispatch_failure_and_an_unseen_commitment_are_reported(signer, tmp_path):
    chain = FakeChain()
    chain.outcome = "FAILED"
    result = _with(signer, tmp_path, chain).post(DIGEST)
    assert (
        result["code"] == "commitment_failed"
        and result["error"] == "SpaceLimitExceeded"
    )
    chain = FakeChain(head=7_200 + 360)
    chain.outcome = "FINALIZED_UNSEEN"
    assert _with(signer, tmp_path / "b", chain).post(OTHER)["code"] == (
        "commitment_not_observed"
    )


def test_an_unreadable_chain_posts_nothing(tmp_path):
    chain = FakeChain()
    chain.read_down = True
    poster = cp.CommitmentPoster(
        hotkey="5" + "C" * 47, chain=chain, sign=_never, state_dir=tmp_path
    )
    assert poster.post(DIGEST)["code"] == "commitment_reader_unavailable"
    assert poster.plan(DIGEST)["code"] == "commitment_reader_unavailable"


def test_a_malformed_digest_is_refused_before_anything(tmp_path):
    poster = cp.CommitmentPoster(
        hotkey="5" + "C" * 47, chain=FakeChain(), sign=_never, state_dir=tmp_path
    )
    for bad in (DIGEST.upper(), DIGEST + "\n", None):
        assert poster.post(bad)["code"] == "commitment_bad_digest"
        assert poster.start(bad)["code"] == "commitment_bad_digest"


# L2 and D10 --------------------------------------------------------------------


def test_the_plan_warns_that_a_post_replaces_the_current_commitment(tmp_path):
    chain = FakeChain(on_chain={"digest": OTHER, "block": 9})
    poster = cp.CommitmentPoster(
        hotkey="5" + "C" * 47, chain=chain, sign=_never, state_dir=tmp_path
    )
    plan = poster.plan(DIGEST, queued=[OTHER, DIGEST])
    assert plan["current"] == OTHER and plan["needed"] is True
    assert "replaces" in plan["warning"] and plan["queued_other_digests"] == [OTHER]
    assert poster.plan(OTHER)["needed"] is False


def test_an_agent_can_request_but_only_the_terminal_confirms(signer, tmp_path):
    release = threading.Event()

    def at_terminal(expected):
        release.wait(5)
        return True

    signer.asked.answer = at_terminal
    chain = FakeChain()
    poster = _with(signer, tmp_path, chain)
    started = poster.start(DIGEST)
    assert started["result"] == "human_action_required"
    assert started["action"] == "confirm_commitment"
    assert started["confirm_with"] == DIGEST[-8:]
    assert "cannot confirm" in started["instruction"]
    assert poster.start(DIGEST)["code"] == "commitment_in_flight"
    assert poster.status()["in_flight"] is True
    release.set()
    for _ in range(200):
        if not poster.status()["in_flight"]:
            break
        threading.Event().wait(0.02)
    assert poster.status()["last"]["state"] == "COMMITTED"
    # What reached the signer carried no confirmation of any kind.
    (request,) = signer.requests
    assert set(request) == {"netuid", "digest", "unsigned", "fee"}
    assert "confirm" not in json.dumps(request)


def test_timing_holds_at_twelve_second_blocks():
    """Standard localnet, testnet and mainnet all run 12-second blocks: the
    finality wait fits well inside the era, and the era is the SDK default
    capped at one 360-block tempo (counted in blocks, so block time does not
    move the cap). The round trip accepts only the standard profile."""
    from carbon.chain.localnet import runtime_profile
    from carbon_miner_signer import commitment as cm

    record = json.loads(cm.RECORD_PATH.read_text())
    _, standard = runtime_profile("standard")
    assert standard["nominal_block_seconds"] == str(cp.BLOCK_SECONDS) == "12"
    assert cp.ERA_PERIOD == record["era"]["max_period"] == 128
    assert record["era"]["max_period"] <= record["network"]["tempo_blocks"] == 360
    assert cp.FINALITY_SECONDS < cp.ERA_PERIOD * cp.BLOCK_SECONDS
    script = (REPOSITORY / "scripts/dev/commitment_localnet_roundtrip.py").read_text()
    assert 'PROFILE = "standard"' in script and '"fast"' not in script
    assert 'profile["expected_genesis"]' in script
