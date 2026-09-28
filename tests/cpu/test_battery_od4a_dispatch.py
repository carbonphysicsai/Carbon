"""Battery OD-4a dispatch adapter (NOT REVIEWED; no public transaction here).

The property under test is structural: the adapter cannot dispatch an intent
the owner did not approve. Each refusal is paired with the approved case
passing through the same path, so a refusal cannot pass by being unreachable.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.battery import od4a, od4a_dispatch, signing
from carbon.battery.od4a_dispatch import (
    ApprovedPublication,
    BatteryAllBurnIntentIssuer,
    BatteryAllBurnPublisher,
    BatteryAllBurnWeightIntent,
    DispatchRefused,
)
from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.publication import RuntimeCapabilities
from carbon.chain.publisher import TransactionObservation
from carbon.development_testnet import (
    DevelopmentTestnetFailure,
    DevelopmentTestnetPublisher,
    DevelopmentTransactionAuthorization,
)
from carbon.development_testnet.operator import DEFAULT_ENDPOINT, TESTNET_GENESIS
from carbon.rewards.core import Q12
from carbon.transport.store import ReceiptJournal

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
EXPIRES = "2026-10-02T00:00:00Z"
SPEC = 471
SURFACE = "sha256:" + "d" * 64


def run(value):
    return asyncio.run(value)


def chain(netuid=567):
    return ChainContext(
        "testnet", DEFAULT_ENDPOINT, "bittensor-official-test", TESTNET_GENESIS, netuid
    )


def snapshot(ctx, *, block=1000, owner_uid=0):
    members = sorted(
        [
            Participant(owner_uid, "owner-hotkey", "owner-coldkey", 1),
            Participant(1 - owner_uid, "miner-hotkey", "miner-coldkey", 2),
        ],
        key=lambda member: member.uid,
    )
    return MetagraphSnapshot(
        ctx, block, "0x" + f"{block:064x}", block * 12, tuple(members)
    )


def capabilities(state):
    return RuntimeCapabilities(
        state.snapshot_id,
        SPEC,
        1,
        2,
        "Burn",
        "owner-coldkey",
        "owner-hotkey",
        ("owner-hotkey",),
        1,
        65535,
        0,
        0,
        0,
        False,
        True,
        True,
    )


@pytest.fixture
def key(tmp_path, monkeypatch):
    """A test service key, trusted for the test only; the real pin is restored
    by monkeypatch, and one test checks the real pin refuses this key."""
    service = signing.ServiceKey.create(tmp_path / "service.key")
    monkeypatch.setattr(od4a_dispatch, "TRUSTED_SERVICE_PUBLIC_KEY", service.public_key)
    monkeypatch.setattr(od4a_dispatch, "TRUSTED_SERVICE_KEY_ID", service.key_id)
    return service


def intent_from(key, reason="Phase A: all emission burned (OD-4a)"):
    return key.sign(
        "weight_intent", signing.all_burn_intent(pool_version=0, reason=reason)
    )


def probe(block=900, surface=SURFACE, spec=SPEC):
    return {
        "status": "COMPATIBLE_USED_SURFACE",
        "surface_digest": surface,
        "spec_version": spec,
        "context": {
            "genesis_hash": TESTNET_GENESIS,
            "finalized_block": block,
            "finalized_hash": "0x" + "f" * 64,
        },
    }


def request_for(intent, *, netuid=567):
    operator = {
        "context": {
            "network": "testnet",
            "endpoint": DEFAULT_ENDPOINT,
            "chain_id": "bittensor-official-test",
            "genesis_hash": TESTNET_GENESIS,
            "netuid": netuid,
        },
        "publisher": {"hotkey": "owner-hotkey"},
    }
    return od4a.build_request(
        operator=operator,
        probe=probe(),
        intent=intent,
        sequence=3,
        start_after=20,
        window=600,
        expires_utc=EXPIRES,
    )


def approval_for(request, **changes):
    record = {
        "schema": od4a_dispatch.APPROVAL_SCHEMA,
        "authorization_id": request["authorization_id"],
        "request_digest": request["request_digest"],
        "valid_from_block": request["valid_from_block"],
        "valid_through_block": request["valid_through_block"],
        "owner_statement": "fixture approval; not an owner record",
        **changes,
    }
    return json.dumps(record, sort_keys=True).encode()


def authorization_for(request, approval_bytes, **changes):
    values = {
        "authorization_id": request["authorization_id"],
        "authority_record_digest": "sha256:"
        + hashlib.sha256(approval_bytes).hexdigest(),
        "context": chain(),
        "publisher_hotkey": "owner-hotkey",
        "expected_runtime_spec": SPEC,
        "valid_from_block": request["valid_from_block"],
        "valid_through_block": request["valid_through_block"],
        "source_intent_digest": request["source_intent"]["digest"],
        **changes,
    }
    return DevelopmentTransactionAuthorization(**values)


def approved_parts(key):
    intent = intent_from(key)
    request = request_for(intent)
    approval = approval_for(request)
    return {
        "request": request,
        "approval_bytes": approval,
        "intent": intent,
        "probe": probe(),
        "authorization": authorization_for(request, approval),
        "now": NOW,
    }


class Backend:
    """Records execution; a real chain call never happens in these tests."""

    def __init__(self, state):
        self.context = state.context
        self.publisher = "owner-hotkey"
        self.state = state
        self.executions = 0
        self.signed = 0
        self.tx_hash = "0x" + "a" * 64
        self.tx_block = None
        self.row = []

    async def observe(self):
        return self.state, capabilities(self.state)

    async def execute(self, plan, integer_guard, call_checked, before_sign, dispatch):
        self.executions += 1
        uids = [uid for uid, _ in plan.integers]
        values = [value for _, value in plan.integers]
        preflight = SimpleNamespace(
            uid=plan.publisher_uid,
            min_allowed_weights=1,
            max_weight_limit=65535,
            commit_reveal=False,
        )
        await integer_guard(uids, values, preflight)
        call = SimpleNamespace(data=b"checked-battery-all-burn", spec_version=SPEC)
        await call_checked(call, {})
        await before_sign(call, self.publisher)
        self.signed += 1
        await dispatch(self.tx_hash)
        self.state = snapshot(self.context, block=self.state.finalized_block + 1)
        self.tx_block = self.state.finalized_block
        self.row = [list(item) for item in plan.integers]

    async def transaction(self, tx_hash, block):
        if tx_hash == self.tx_hash and block == self.tx_block:
            return TransactionObservation(True, block, self.state.block_hash)
        return None

    async def revealed(self, publisher, block):
        return False

    async def weight_row(self, state, uid):
        return self.row, self.tx_block


def composed(tmp_path, approved, *, state=None, clock=lambda: NOW):
    receipts = ReceiptJournal(tmp_path / "publication.sqlite3", approved.context)
    issuer = BatteryAllBurnIntentIssuer(receipts, approved)
    request = approved  # the window below sits inside the request's window
    state = state or snapshot(chain(), block=920 + 5)
    backend = Backend(state)
    publisher = BatteryAllBurnPublisher(
        issuer, backend, request.authorization, clock=clock
    )
    return issuer, backend, publisher


# -- the approved case: the positive control for every refusal below --------


def test_the_approved_intent_publishes_once_as_the_all_burn_row(tmp_path, key):
    approved = ApprovedPublication.verify(**approved_parts(key))
    issuer, backend, publisher = composed(tmp_path, approved)
    ref = issuer.issue()
    result = run(publisher.publish(ref))
    assert result["state"] == "ROW_VERIFIED"
    assert result["document"]["plan"]["q12"] == [[0, Q12]]
    assert result["tracking"]["stored_row"] == [[0, 65535]]
    assert backend.executions == backend.signed == 1
    # One dispatch: the same approval yields the same reference, and a second
    # publish returns the recorded outcome without executing again.
    assert issuer.issue() == ref
    assert run(publisher.publish(issuer.issue())) == result
    assert backend.executions == 1


# -- 2.4: structurally unable to dispatch an unapproved intent ---------------


def test_a_validly_signed_but_unapproved_intent_is_refused(key):
    parts = approved_parts(key)
    other = intent_from(key, reason="Phase A: a different, unapproved intent")
    assert signing.verify(other) and signing._is_all_burn(other["payload"])
    with pytest.raises(DispatchRefused, match="INTENT_NOT_APPROVED"):
        ApprovedPublication.verify(**{**parts, "intent": other})


def test_a_tampered_intent_is_refused(key):
    parts = approved_parts(key)
    tampered = json.loads(json.dumps(parts["intent"]))
    tampered["payload"]["reason"] = "edited after signing"
    with pytest.raises(DispatchRefused, match="INTENT_NOT_TRUSTED_ALL_BURN"):
        ApprovedPublication.verify(**{**parts, "intent": tampered})


def test_a_self_consistent_intent_from_an_untrusted_key_is_refused(
    tmp_path, key, monkeypatch
):
    parts = approved_parts(key)
    # Specimen: the same parts verify while this key is trusted...
    assert ApprovedPublication.verify(**parts).intent_digest
    # ...and are refused under the real pinned key, although the signature is
    # perfectly valid for its own embedded key.
    monkeypatch.undo()
    assert signing.verify(parts["intent"])
    with pytest.raises(DispatchRefused, match="INTENT_NOT_TRUSTED_ALL_BURN"):
        ApprovedPublication.verify(**parts)


def test_approval_exists_only_by_verification():
    with pytest.raises(TypeError, match="only from verify"):
        ApprovedPublication(authorization_id="OD4A-BATTERY-0003")
    with pytest.raises(DispatchRefused, match="APPROVED_PUBLICATION_REQUIRED"):
        BatteryAllBurnIntentIssuer(None, {"intent_digest": "anything"})


def test_an_altered_journal_row_cannot_carry_another_intent(tmp_path, key):
    approved = ApprovedPublication.verify(**approved_parts(key))
    issuer, backend, publisher = composed(tmp_path, approved)
    ref = issuer.issue()
    with issuer.receipts.transaction() as db:
        body = json.loads(
            db.execute("SELECT body FROM battery_od4a_intent_v1").fetchone()[0]
        )
        body["source_intent"] = intent_from(key, reason="swapped in the journal")
        db.execute(
            "UPDATE battery_od4a_intent_v1 SET body=?",
            (json.dumps(body, sort_keys=True),),
        )
    with pytest.raises(DispatchRefused, match="UNKNOWN_OR_ALTERED_BATTERY_INTENT"):
        run(publisher.publish(ref))
    forged = BatteryAllBurnWeightIntent(ref.identity, "0" * 64)
    with pytest.raises(DispatchRefused, match="UNKNOWN_OR_ALTERED_BATTERY_INTENT"):
        run(publisher.publish(forged))
    assert backend.executions == 0


# -- the approval, authorization and request must bind to each other ---------


@pytest.mark.parametrize(
    "change, code",
    [
        (
            lambda p: {
                "approval_bytes": approval_for(
                    p["request"], request_digest="sha256:" + "0" * 64
                )
            },
            "APPROVAL_DOES_NOT_NAME_THIS_REQUEST",
        ),
        (
            lambda p: {
                "authorization": replace(p["authorization"], source_intent_digest=None)
            },
            "AUTHORIZATION_NOT_BOUND_TO_APPROVAL",
        ),
        (
            lambda p: {
                "authorization": replace(
                    p["authorization"], authority_record_digest="sha256:" + "1" * 64
                )
            },
            "AUTHORIZATION_NOT_BOUND_TO_APPROVAL",
        ),
        (
            lambda p: {
                "authorization": replace(
                    p["authorization"],
                    valid_through_block=p["authorization"].valid_through_block + 1,
                )
            },
            "AUTHORIZATION_NOT_BOUND_TO_APPROVAL",
        ),
        (
            lambda p: {"request": {**p["request"], "valid_through_block": 10**9}},
            "REQUEST_DIGEST_MISMATCH",
        ),
        (
            lambda p: {"probe": probe(surface="sha256:" + "e" * 64)},
            "RUNTIME_PROBE_CHANGED",
        ),
        (lambda p: {"probe": probe(spec=SPEC + 1)}, "RUNTIME_PROBE_CHANGED"),
        (
            lambda p: {"now": datetime(2026, 10, 2, tzinfo=UTC)},
            "REQUEST_EXPIRED",
        ),
        (lambda p: {"probe": None}, "DISPATCH_NEEDS_TIME_AND_PROBE"),
    ],
)
def test_every_binding_is_required(key, change, code):
    parts = approved_parts(key)
    assert ApprovedPublication.verify(**parts)  # specimen: unchanged parts pass
    with pytest.raises(DispatchRefused, match=code):
        ApprovedPublication.verify(**{**parts, **change(parts)})


def test_testnet_567_only(key):
    intent = intent_from(key)
    request = request_for(intent)
    # od4a refuses to build a request for another subnet...
    with pytest.raises(od4a.RequestRefused):
        request_for(intent, netuid=568)
    # ...and a request edited to another subnet, re-digested, is refused here.
    moved = {
        k: v
        for k, v in request.items()
        if k not in ("request_digest", "operator_config_fragment")
    }
    moved["context"] = {**moved["context"], "netuid": 568}
    moved["request_digest"] = od4a._digest(moved)
    parts = approved_parts(key)
    with pytest.raises(DispatchRefused, match="TESTNET_567_ONLY"):
        ApprovedPublication.verify(**{**parts, "request": moved})


def test_the_c_w1_path_refuses_a_battery_authorization_and_the_reverse(tmp_path, key):
    approved = ApprovedPublication.verify(**approved_parts(key))
    issuer, backend, _ = composed(tmp_path, approved)
    with pytest.raises(DevelopmentTestnetFailure, match="SCOPE_MISMATCH"):
        DevelopmentTestnetPublisher(issuer, backend, approved.authorization)
    unbound = replace(approved.authorization, source_intent_digest=None)
    with pytest.raises(DispatchRefused, match="AUTHORIZATION_NOT_BOUND_TO_APPROVAL"):
        BatteryAllBurnPublisher(issuer, backend, unbound)


# -- dispatch-time rechecks ---------------------------------------------------


def test_expiry_is_rechecked_just_before_signing(tmp_path, key):
    approved = ApprovedPublication.verify(**approved_parts(key))
    times = iter([NOW, NOW + timedelta(days=2)])  # expires between stages
    _, backend, publisher = composed(tmp_path, approved, clock=lambda: next(times))
    issuer = publisher.issuer
    result = run(publisher.publish(issuer.issue()))
    assert result["state"] == "FAILED_BEFORE_SIGNING"
    assert result["tracking"]["reason"] == "REQUEST_EXPIRED"
    assert backend.executions == 1 and backend.signed == 0


def test_a_row_other_than_uid_0_is_refused(tmp_path, key):
    approved = ApprovedPublication.verify(**approved_parts(key))
    state = snapshot(chain(), block=925, owner_uid=1)
    issuer, backend, publisher = composed(tmp_path, approved, state=state)
    with pytest.raises(DispatchRefused, match="ROW_NOT_APPROVED_ALL_BURN"):
        run(publisher.publish(issuer.issue()))
    assert backend.executions == 0


def test_the_block_window_is_inherited(tmp_path, key):
    approved = ApprovedPublication.verify(**approved_parts(key))
    late = snapshot(chain(), block=approved.authorization.valid_through_block + 1)
    issuer, backend, publisher = composed(tmp_path, approved, state=late)
    with pytest.raises(DevelopmentTestnetFailure, match="AUTHORIZATION_EXPIRED"):
        run(publisher.publish(issuer.issue()))
    assert backend.executions == 0


def _called(source):
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            names.add(
                func.attr
                if isinstance(func, ast.Attribute)
                else getattr(func, "id", None)
            )
    return names


def test_signing_boundaries_are_untouched_and_unused():
    # 2.1 and 2.2: winner_intent() still raises and sign() still refuses a
    # non-all-burn intent; the adapter calls neither and loads no key.
    with pytest.raises(PermissionError):
        signing.winner_intent()
    forbidden = {"winner_intent", "sign", "ServiceKey", "load", "create"}
    # Specimen: the same scan finds each call where it is present.
    assert forbidden <= _called(
        "signing.winner_intent(); k.sign(1, 2); ServiceKey(b''); ServiceKey.load(p); ServiceKey.create(p)"
    )
    adapter = Path(od4a_dispatch.__file__).read_text()
    assert not forbidden & _called(adapter)
