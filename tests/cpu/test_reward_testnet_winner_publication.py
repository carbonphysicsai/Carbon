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


# -- the same rule on mainnet; the owner-coldkey switch by network ---------------------


def owner_coldkey_miner(ctx, block=925):
    """The standard snapshot plus a miner whose coldkey is the subnet owner's
    (Carbon's own miner) and whose hotkey is not an owner hotkey."""
    base = snapshot(ctx, block=block)
    member = type(base.participants[0])(2, "carbon-miner-hotkey", "owner-coldkey", 3)
    return dataclasses.replace(base, participants=base.participants + (member,))


def test_testnet_pays_a_winner_whose_coldkey_is_the_owners(tmp_path):
    issuer, backend, publisher = composed(
        tmp_path,
        source=lambda: promotion("carbon-miner-hotkey"),
        state=owner_coldkey_miner(chain()),
    )
    assert publisher.ALLOW_OWNER_COLDKEY_WINNER is True
    publish(issuer, backend, publisher)
    assert backend.executions == 1


def mainnet():
    from test_battery_od4a_dispatch import TESTNET_GENESIS

    from carbon.chain import ChainContext

    genesis = TESTNET_GENESIS[:2] + "f" * (len(TESTNET_GENESIS) - 2)
    return ChainContext(
        "finney", "wss://finney.example.invalid:443", "finney-fixture", genesis, 99
    )


def mainnet_policy(tmp_path):
    """A synthetic finney policy (netuid 99, a fixture value): the registered
    rule, renamed and pinned in a copy of the registry."""
    import hashlib
    import json
    import shutil

    copy = tmp_path / "weight_policies"
    shutil.copytree(wd.POLICY_DIR, copy)
    document = json.loads((copy / f"{POLICY.version}.json").read_text())
    document.update(
        version="mainnet-fixture",
        network="finney",
        netuid=99,
        authority=wd.MAINNET_AUTHORITY,
    )
    (copy / "mainnet-fixture.json").write_text(json.dumps(document))
    registry = json.loads((copy / "registry.json").read_text())
    registry["versions"]["mainnet-fixture"] = (
        "sha256:" + hashlib.sha256(wd._canonical(document)).hexdigest()
    )
    (copy / "registry.json").write_text(json.dumps(registry))
    return wd.load_policy("mainnet-fixture", directory=copy)


def mainnet_composed(tmp_path, **kwargs):
    policy = mainnet_policy(tmp_path / "policy")
    auth = authorization(
        context=mainnet(), policy_digest=policy.digest, authority=wd.MAINNET_AUTHORITY
    )
    return composed(
        tmp_path,
        auth=auth,
        policy=policy,
        state=kwargs.pop("state", None) or snapshot(mainnet(), block=925),
        **kwargs,
    )


def test_mainnet_runs_the_same_rule(tmp_path):
    issuer, backend, publisher = mainnet_composed(tmp_path)
    assert publisher.ALLOW_OWNER_COLDKEY_WINNER is False
    state, _ = asyncio.run(backend.observe())
    ref = issuer.issue(state)
    assert ref.identity.startswith("mainnet-winner-mainnet-fixture-e")
    intent = issuer.resolve(ref, state)["intent"]
    assert (intent["stage"], intent["maturity"], intent["authority"]) == (
        "PUBLIC_MAINNET",
        "MAINNET_OWNER_AUTHORIZED",
        wd.MAINNET_AUTHORITY,
    )
    asyncio.run(publisher.publish(ref))
    assert backend.executions == 1


def test_mainnet_refuses_a_winner_whose_coldkey_is_the_owners(tmp_path):
    issuer, backend, publisher = mainnet_composed(
        tmp_path,
        source=lambda: promotion("carbon-miner-hotkey"),
        state=owner_coldkey_miner(mainnet()),
    )
    with pytest.raises(PublicationFailure) as refused:
        publish(issuer, backend, publisher)
    assert str(refused.value) == "OWNER_ASSOCIATED_WINNER_WOULD_BURN"
    assert backend.executions == 0


def test_an_authority_never_crosses_networks(tmp_path):
    # The testnet record never authorizes mainnet.
    with pytest.raises(twp.WinnerPublicationRefused):
        authorization(context=mainnet())
    # A mainnet authorization with the testnet policy is not for this network.
    with pytest.raises(twp.WinnerPublicationRefused) as refused:
        composed(
            tmp_path,
            auth=authorization(context=mainnet(), authority=wd.MAINNET_AUTHORITY),
            state=snapshot(mainnet(), block=925),
        )
    assert str(refused.value) == "POLICY_NOT_FOR_THIS_NETWORK"


# --- preview: the operator's look before signing -----------------------------------


def test_preview_shows_the_targets_run_publishes_and_writes_nothing(tmp_path):
    issuer, backend, publisher = composed(tmp_path)
    state, _ = asyncio.run(backend.observe())
    seen = twp.preview(issuer, state)
    assert seen["signed"] is False
    assert seen["records"][BATTERY]["hotkey"] == "miner-hotkey"
    assert seen["records"][BATTERY]["eligible"] is True
    # Nothing was recorded: no ledger line, no stored intent, nothing signed.
    assert issuer.ledger.records() == []
    with issuer.receipts.transaction() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM testnet_winner_intent_v1"
        ).fetchone() == (0,)
    assert backend.signed == 0
    # The publication that follows pays exactly the previewed targets.
    result = publish(issuer, backend, publisher)
    assert seen["targets"] == issuer._targets(
        state, issuer._records(state, observe=False)
    )
    assert result["document"]["plan"]["q12"] == [[0, Q12 - Q12 // 3], [1, Q12 // 3]]


def test_preview_with_no_incumbent_burns_everything(tmp_path):
    issuer, backend, _ = composed(tmp_path, source=lambda: None)
    state, _ = asyncio.run(backend.observe())
    seen = twp.preview(issuer, state)
    assert seen["records"][BATTERY] is None
    assert seen["targets"]["winners"] == [] and seen["targets"]["burn"] == Q12


def test_preview_reuses_a_recorded_promotion_and_its_clock(tmp_path):
    issuer, backend, publisher = composed(tmp_path)
    publish(issuer, backend, publisher)
    recorded = issuer.ledger.records(BATTERY)
    state, _ = asyncio.run(backend.observe())
    seen = twp.preview(issuer, state)
    assert seen["records"][BATTERY]["clock_ms"] == recorded[0]["clock_ms"]
    assert issuer.ledger.records(BATTERY) == recorded
