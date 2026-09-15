"""C-W1-D1 DEVELOPMENT testnet composition; no public transaction occurs here."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest
from c10_fixtures import sha
from test_c07_development_orchestration import _owners, _run_stages, _signer, _values
from test_c08_authenticated_miner_mcp import (
    _composition,
    _real_request,
    _requester,
    _submit,
)
from test_mcp_skeleton import CHALLENGE_KEY

from carbon import audit
from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.publication import RuntimeCapabilities
from carbon.chain.publisher import TransactionObservation
from carbon.development_testnet import (
    DevelopmentTestnetEvidence,
    DevelopmentTestnetFailure,
    DevelopmentTestnetIntentIssuer,
    DevelopmentTestnetProfile,
    DevelopmentTestnetPublisher,
    DevelopmentTransactionAuthorization,
    LocalRetentionEvidence,
)
from carbon.miner_mcp import BindMode
from carbon.orchestration import reconstruction_outcome_digest
from carbon.reconstruction import (
    development_replicate_digest,
    freeze_development_repeat_plan,
)
from carbon.rewards.core import Q12, RewardFailure
from carbon.rewards.intents import TestnetWinnerWeightIntent as OfficialTestnetIntent
from carbon.transport.store import ReceiptJournal


def run(value):
    return asyncio.run(value)


def context() -> ChainContext:
    return ChainContext(
        "testnet",
        "wss://test.finney.opentensor.ai:443",
        "bittensor-official-test",
        "0x" + "8" * 64,
        77,
    )


def snapshot(ctx: ChainContext, *, block=100, timestamp=8) -> MetagraphSnapshot:
    return MetagraphSnapshot(
        ctx,
        block,
        "0x" + f"{block:064x}",
        timestamp,
        (
            Participant(0, "owner-hotkey", "owner-coldkey", 1),
            Participant(1, "publisher-hotkey", "publisher-coldkey", 2),
        ),
    )


def source(fixture) -> DevelopmentTestnetEvidence:
    return DevelopmentTestnetEvidence(
        fixture.primary_result.account,
        fixture.primary_result.ledger_reference,
        fixture.transport_receipt,
        LocalRetentionEvidence(sha("local-evidence-set"), sha("export-manifest"), 4096),
    )


def authenticated_fixture(tmp_path, *, request_name="submit-1", transport_context=None):
    (tmp_path / "c08").mkdir(parents=True)
    options = {} if transport_context is None else {"context": transport_context}
    state, _, _, orchestrator, associations, miner = _composition(
        tmp_path / "c08", **options
    )
    submitted = _submit(miner, state, request=request_name)
    request_root = tmp_path / "request"
    request = _real_request(
        request_root,
        _requester(miner, submitted.transport_receipt),
        submitted.mcp_result.status.submission_id.value,
    )
    _, repeat, receipts, prediction, reference, measurement = _values(request_root)
    replicas = []
    for replica in repeat.replicas:
        prior = replica.binding.replicate_identity
        identity = replace(
            prior,
            challenge_key=CHALLENGE_KEY,
            construction_plan_ref=replace(
                prior.construction_plan_ref, challenge_key=CHALLENGE_KEY
            ),
            policy_ref=replace(prior.policy_ref, challenge_key=CHALLENGE_KEY),
            resource_class_ref=replace(
                prior.resource_class_ref, challenge_key=CHALLENGE_KEY
            ),
        )
        binding = replace(replica.binding, replicate_identity=identity)
        identity = replace(
            identity,
            replicate_digest=development_replicate_digest(
                binding=binding,
                execution_ref=replica.execution_ref,
                randomness_digest=replica.randomness_digest,
                training_data_digest=repeat.training_data_digest,
                request_digest=repeat.request_digest,
            ),
        )
        replicas.append(
            replace(replica, binding=replace(binding, replicate_identity=identity))
        )
    repeat = freeze_development_repeat_plan(
        plan_id=repeat.plan_id,
        construction_plan_digest=repeat.construction_plan_digest,
        training_data_digest=repeat.training_data_digest,
        request_digest=repeat.request_digest,
        replicas=tuple(replicas),
    )
    request = replace(
        request,
        evidence=replace(
            request.evidence,
            repeat_plan_digest=repeat.plan_digest,
            reconstruction_outcome_digest=reconstruction_outcome_digest(
                repeat, receipts
            ),
        ),
    )
    handle = miner.bind_orchestration(
        submitted.transport_receipt,
        request,
        worker_id="development-testnet-worker",
        claim_id="development-testnet-claim",
        mode=BindMode.START,
    )
    _run_stages(
        orchestrator, handle, repeat, receipts, prediction, reference, measurement
    )
    complete = orchestrator.finalize_complete(
        handle,
        receipt_id="development-testnet-c07-receipt",
        signer=_signer(),
        evidence_index=audit.FrozenEvidenceIndex(
            frozenset(request.evidence.required_evidence_digests())
        ),
        result_owners=_owners(),
        started_at_micros=2_000,
        finished_at_micros=3_000,
        verified_at_micros=3_100,
    )
    miner.record_outcome(complete.account)
    return SimpleNamespace(
        primary_result=complete,
        ledger=orchestrator.evidence_ledger,
        associations=associations,
        transport_receipt=submitted.transport_receipt,
    )


def issuer(tmp_path):
    fixture = authenticated_fixture(tmp_path)
    ctx = context()
    receipts = ReceiptJournal(tmp_path / "chain.sqlite3", ctx)
    profile = DevelopmentTestnetProfile(ctx, 458)
    return (
        fixture,
        DevelopmentTestnetIntentIssuer(
            receipts, fixture.ledger, fixture.associations, profile
        ),
        snapshot(ctx),
    )


def capabilities(state):
    return RuntimeCapabilities(
        state.snapshot_id,
        458,
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


def authorization(state):
    return DevelopmentTransactionAuthorization(
        "owner-public-testnet-demo-1",
        sha("owner-transaction-record"),
        state.context,
        "publisher-hotkey",
        458,
        state.finalized_block,
        state.finalized_block + 8,
    )


def test_active_signed_public_development_evidence_issues_only_all_burn(tmp_path):
    fixture, service, state = issuer(tmp_path)
    ref = service.issue("development-testnet-1", source(fixture), snapshot=state)
    resolved = service.resolve(ref, state)
    assert resolved["intent"]["stage"] == "PUBLIC_TESTNET_DEVELOPMENT"
    assert resolved["intent"]["scientific_disposition"] == "UNRESOLVED_UNQUALIFIED"
    assert resolved["projection"]["targets"] == {
        "challenges": [],
        "winners": [],
        "burn": Q12,
    }
    assert resolved["intent"]["source"]["development_receipt_network_eligible"] is False
    assert resolved["intent"]["source"]["authenticated_request"] == {
        "body_digest": "sha256:"
        + fixture.associations.journal.resolve(fixture.transport_receipt).body_digest,
        "coldkey": "cold",
        "hotkey": "miner",
        "receipt_digest": "sha256:" + fixture.transport_receipt.digest,
        "receipt_sequence": fixture.transport_receipt.sequence,
        "uid": 1,
    }
    assert resolved["intent"]["source"]["local_retention"] == {
        "archive_acknowledgement": None,
        "evidence_set_digest": sha("local-evidence-set"),
        "export_manifest_digest": sha("export-manifest"),
        "host_loss_recoverable": False,
        "policy_id": "carbon:development-testnet:local-review-export:v1",
        "retained_bytes": 4096,
        "storage_scope": "BOUNDED_LOCAL_OPERATOR_STORAGE",
    }


def test_replay_converges_conflict_revocation_and_staleness_fail_closed(tmp_path):
    fixture, service, state = issuer(tmp_path)
    evidence = source(fixture)
    ref = service.issue("development-testnet-1", evidence, snapshot=state)
    assert service.issue("development-testnet-1", evidence, snapshot=state) == ref
    with pytest.raises(DevelopmentTestnetFailure, match="CONFLICTING"):
        service.issue(
            "development-testnet-1",
            replace(
                evidence,
                local_retention=replace(evidence.local_retention, retained_bytes=4097),
            ),
            snapshot=state,
        )
    with pytest.raises(DevelopmentTestnetFailure, match="STALE_OR_CONFLICTING"):
        service.resolve(ref, snapshot(state.context, timestamp=68))
    fixture.ledger.revoke(
        fixture.primary_result.ledger_reference.receipt_id, sha("revoked")
    )
    with pytest.raises(DevelopmentTestnetFailure, match="INELIGIBLE"):
        service.issue("development-testnet-2", evidence, snapshot=state)


def test_official_intent_and_source_authority_remain_unavailable(tmp_path):
    fixture, service, state = issuer(tmp_path)
    service.issue("development-testnet-1", source(fixture), snapshot=state)
    receipt = fixture.primary_result.signed_receipt.receipt
    assert receipt.network_eligible is False
    assert receipt.archive_acknowledged is False
    assert receipt.score_eligible is False
    with pytest.raises(RewardFailure, match="C2_REAL_ELIGIBILITY"):
        OfficialTestnetIntent()


class Backend:
    def __init__(self, service, state):
        self.context = state.context
        self.publisher = "publisher-hotkey"
        self.state = state
        self.caps = capabilities(state)
        self.executions = 0
        self.tx_hash = "0x" + "a" * 64
        self.tx_block = None
        self.row = []

    async def observe(self):
        return self.state, replace(self.caps, snapshot_id=self.state.snapshot_id)

    async def execute(
        self, plan, integer_guard, call_checked, before_sign, before_dispatch
    ):
        self.executions += 1
        uids = [uid for uid, _ in plan.integers]
        values = [value for _, value in plan.integers]
        preflight = SimpleNamespace(
            uid=1,
            min_allowed_weights=1,
            max_weight_limit=65535,
            commit_reveal=False,
        )
        await integer_guard(uids, values, preflight)
        call = SimpleNamespace(data=b"checked-development-all-burn", spec_version=458)
        await call_checked(call, {})
        await before_sign(call, self.publisher)
        await before_dispatch(self.tx_hash)
        self.state = snapshot(
            self.context,
            block=self.state.finalized_block + 1,
            timestamp=self.state.timestamp_ms + 1,
        )
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


def test_checked_testnet_publisher_reuses_journal_guards_and_verifies_row(tmp_path):
    fixture, service, state = issuer(tmp_path)
    ref = service.issue("development-testnet-1", source(fixture), snapshot=state)
    backend = Backend(service, state)
    publisher = DevelopmentTestnetPublisher(service, backend, authorization(state))
    result = run(publisher.publish(ref))
    assert result["state"] == "ROW_VERIFIED"
    assert (
        service.resolve(ref, backend.state)["intent"]["maturity"] == "DEVELOPMENT_ONLY"
    )
    assert result["document"]["plan"]["q12"] == [[0, Q12]]
    assert result["tracking"]["stored_row"] == [[0, 65535]]
    assert backend.executions == 1
    assert run(publisher.publish(ref)) == result
    assert backend.executions == 1


def test_transaction_authorization_is_required_expires_and_has_one_effect(tmp_path):
    fixture, service, state = issuer(tmp_path)
    ref = service.issue("development-testnet-1", source(fixture), snapshot=state)
    backend = Backend(service, state)
    with pytest.raises(DevelopmentTestnetFailure, match="AUTHORIZATION_REQUIRED"):
        DevelopmentTestnetPublisher(service, backend, None)
    expired = replace(
        authorization(state),
        valid_from_block=state.finalized_block - 2,
        valid_through_block=state.finalized_block - 1,
    )
    publisher = DevelopmentTestnetPublisher(service, backend, expired)
    with pytest.raises(DevelopmentTestnetFailure, match="AUTHORIZATION_EXPIRED"):
        run(publisher.publish(ref))

    approved = DevelopmentTestnetPublisher(service, backend, authorization(state))
    assert run(approved.publish(ref))["state"] == "ROW_VERIFIED"
    second = service.issue("development-testnet-2", source(fixture), snapshot=state)
    with pytest.raises(DevelopmentTestnetFailure, match="AUTHORIZATION_CONSUMED"):
        run(
            DevelopmentTestnetPublisher(service, backend, authorization(state)).publish(
                second
            )
        )


def test_local_retention_rejects_archive_or_host_loss_claims():
    evidence = LocalRetentionEvidence(
        sha("local-evidence-set"), sha("export-manifest"), 1
    )
    assert evidence.host_loss_recoverable is False
    assert evidence.archive_acknowledgement is None
    with pytest.raises(DevelopmentTestnetFailure, match="INVALID_LOCAL_RETENTION"):
        LocalRetentionEvidence(
            sha("local-evidence-set"),
            sha("export-manifest"),
            1,
            host_loss_recoverable=True,
        )


def test_authenticated_request_cannot_be_cross_associated(tmp_path):
    fixture, service, state = issuer(tmp_path / "first")
    other = authenticated_fixture(tmp_path / "second", request_name="submit-other")
    crossed = replace(
        source(fixture), authenticated_request_receipt=other.transport_receipt
    )
    with pytest.raises(DevelopmentTestnetFailure, match="AUTHENTICATED_SOURCE"):
        service.issue("crossed-development-testnet", crossed, snapshot=state)
