"""Testnet 567 winner-weight publication (VALIDATOR-14; NOT SECURITY REVIEWED).

No public transaction happens here. The chain backend, snapshot and runtime
capabilities are the battery OD-4a tests' doubles. Each refusal is paired with
the authorized case passing through the same path.
"""

import asyncio
import dataclasses
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_od4a_dispatch import SPEC, Backend, chain, snapshot

from carbon.chain.publication import PublicationFailure
from carbon.rewards import testnet_winner_publication as twp
from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import Q12
from carbon.transport.store import ReceiptJournal

POLICY = wd.load_policy()
BATTERY = POLICY.challenges[0]
RECORD = "e" * 64


def authorization(**changes):
    values = {
        "authority_record_digest": RECORD,
        "policy_digest": POLICY.digest,
        "context": chain(),
        "publisher_hotkey": "owner-hotkey",
        "expected_runtime_spec": SPEC,
        "valid_from_block": 900,
        "valid_through_block": 2000,
    }
    values.update(changes)
    return twp.StandingAuthorization(**values)


def promotion(hotkey="miner-hotkey", model="m1"):
    return {"model_id": model, "hotkey": hotkey, "previous": None, "kind": we.FIRST}


def composed(tmp_path, *, source=promotion, state=None, auth=None, policy=POLICY):
    auth = auth or authorization()
    receipts = ReceiptJournal(tmp_path / "publication.sqlite3", auth.context)
    ledger = we.WinnerLedger(tmp_path / "winners.jsonl")
    sources = {} if source is None else {BATTERY: source}
    issuer = twp.TestnetWinnerIntentIssuer(receipts, auth, policy, ledger, sources)
    backend = Backend(state or snapshot(chain(), block=925))
    return issuer, backend, twp.TestnetWinnerPublisher(issuer, backend)


def publish(issuer, backend, publisher):
    state, _ = asyncio.run(backend.observe())
    return asyncio.run(publisher.publish(issuer.issue(state)))


def test_the_winner_gets_its_challenges_share_and_the_rest_burns(tmp_path):
    issuer, backend, publisher = composed(tmp_path)
    result = publish(issuer, backend, publisher)
    assert result["state"] == "ROW_VERIFIED"
    # UID 0 burns; UID 1 is the miner.
    assert result["document"]["plan"]["q12"] == [[0, Q12 - Q12 // 3], [1, Q12 // 3]]
    assert backend.executions == backend.signed == 1
    # One publication per epoch: the same epoch returns the recorded outcome.
    assert publish(issuer, backend, publisher) == result
    assert backend.executions == 1


def test_with_no_winner_everything_burns(tmp_path):
    issuer, backend, publisher = composed(tmp_path, source=None)
    result = publish(issuer, backend, publisher)
    assert result["document"]["plan"]["q12"] == [[0, Q12]]


def test_a_winner_not_in_the_snapshot_is_not_paid(tmp_path):
    issuer, backend, publisher = composed(
        tmp_path, source=lambda: promotion("unregistered-hotkey")
    )
    assert publish(issuer, backend, publisher)["document"]["plan"]["q12"] == [[0, Q12]]


def test_an_owner_associated_winner_is_refused_by_the_shared_compiler(tmp_path):
    issuer, backend, publisher = composed(
        tmp_path, source=lambda: promotion("owner-hotkey")
    )
    with pytest.raises(PublicationFailure) as refused:
        publish(issuer, backend, publisher)
    assert str(refused.value) == "OWNER_ASSOCIATED_WINNER_WOULD_BURN"
    assert backend.executions == 0


def test_outside_the_standing_window_nothing_is_published(tmp_path):
    issuer, backend, publisher = composed(
        tmp_path, auth=authorization(valid_through_block=920)
    )
    with pytest.raises(twp.WinnerPublicationRefused) as refused:
        publish(issuer, backend, publisher)
    assert str(refused.value) == "STANDING_AUTHORIZATION_OUTSIDE_WINDOW"
    assert backend.executions == 0


def test_only_the_authorized_policy_is_served(tmp_path):
    with pytest.raises(twp.WinnerPublicationRefused) as refused:
        composed(tmp_path, auth=authorization(policy_digest="sha256:" + "0" * 64))
    assert str(refused.value) == "POLICY_NOT_AUTHORIZED"


@pytest.mark.parametrize(
    "changes",
    [
        {"context": chain(netuid=1)},
        {"authority_record_digest": "not-a-digest"},
        {"valid_from_block": 10, "valid_through_block": 5},
        {"authority": "OWNER-SOMETHING-ELSE"},
    ],
)
def test_a_malformed_standing_authorization_is_refused(changes):
    with pytest.raises(twp.WinnerPublicationRefused):
        authorization(**changes)


def test_targets_that_changed_since_issue_are_refused(tmp_path):
    issuer, backend, publisher = composed(tmp_path)
    state, _ = asyncio.run(backend.observe())
    ref = issuer.issue(state)
    # A new promotion lands before publication: the issued targets are stale.
    issuer.ledger.observe(
        POLICY,
        BATTERY,
        {
            "model_id": "m2",
            "hotkey": "unregistered",
            "previous": "m1",
            "previous_hotkey": "miner-hotkey",
            "kind": we.FINAL,
            "nomination_overdue": False,
        },
        {},
        state.timestamp_ms,
    )
    with pytest.raises(twp.WinnerPublicationRefused) as refused:
        asyncio.run(publisher.publish(ref))
    assert str(refused.value) == "TARGETS_CHANGED_REISSUE_NEXT_EPOCH"
    assert backend.executions == 0


def test_the_publisher_must_be_the_authorized_hotkey(tmp_path):
    issuer, backend, _ = composed(tmp_path)
    backend.publisher = "other-hotkey"
    with pytest.raises(twp.WinnerPublicationRefused) as refused:
        twp.TestnetWinnerPublisher(issuer, backend)
    assert str(refused.value) == "PUBLISHER_NOT_AUTHORIZED"


def test_a_different_policy_version_is_not_this_authorization(tmp_path):
    other = dataclasses.replace(POLICY, digest="sha256:" + "1" * 64)
    with pytest.raises(twp.WinnerPublicationRefused):
        composed(tmp_path, policy=other)


def test_the_standing_file_binds_the_owner_records_bytes(tmp_path):
    import hashlib
    import json

    record = tmp_path / "OWNER-TESTNET-WEIGHTS-01.md"
    record.write_text("the owner's words")
    standing = tmp_path / "standing.json"
    standing.write_text(
        json.dumps(
            {
                "authority_record": record.name,
                "policy_digest": POLICY.digest,
                "publisher_hotkey": "owner-hotkey",
                "expected_runtime_spec": SPEC,
                "valid_from_block": 900,
                "valid_through_block": 2000,
            }
        )
    )
    standing.chmod(0o600)
    loaded = twp.load_standing(standing, chain())
    assert loaded.authority_record_digest == (
        hashlib.sha256(b"the owner's words").hexdigest()
    )
    standing.chmod(0o644)
    with pytest.raises(twp.WinnerPublicationRefused):
        twp.load_standing(standing, chain())
