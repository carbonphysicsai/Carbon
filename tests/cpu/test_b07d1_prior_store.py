from __future__ import annotations

from dataclasses import replace

import pytest
from b07d_fixtures import digest, prior_fixture, public_pack

from carbon import research
from carbon.prior_compat import project_v2_to_v1_private


def test_pack_identity_store_history_and_private_projection(tmp_path):
    _, registry, pack = prior_fixture()
    store = research.PriorPackStore(tmp_path / "prior.sqlite", registry)
    ref = store.store_pack(pack)
    assert store.read_pack(ref) == pack
    assert store.read_pack_bytes(ref) == research.canonical_bytes(pack)
    projection = project_v2_to_v1_private(pack)
    assert projection.receipt.source_prior_pack_ref == ref
    assert projection.receipt.output_hash.startswith("sha256:")
    assert len(projection.published_prior.directives) == 1


def test_claimed_ref_predecessor_and_origin_laundering_fail_closed(tmp_path):
    _, registry, pack = prior_fixture()
    store = research.PriorPackStore(tmp_path / "prior.sqlite", registry)
    with pytest.raises(research.PriorStoreError) as failure:
        store.store_pack(
            pack,
            research.PriorPackRef(pack.challenge_key, pack.channel, 0, digest("f")),
        )
    assert (
        failure.value.code is research.ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID
    )

    with pytest.raises(ValueError):
        replace(pack, channel=research.PriorChannel.PUBLIC)

    malicious = replace(
        pack,
        predecessor_pack_ref=research.PriorPackRef(
            pack.challenge_key,
            pack.channel,
            0,
            research.prior_pack_ref(pack).content_hash,
        ),
    )
    with pytest.raises(research.PriorStoreError):
        store.store_pack(malicious)


def test_none_found_must_bind_exact_search_scope_and_cutoff(tmp_path):
    _, registry, pack = prior_fixture()
    item = pack.items[0]
    bad = replace(
        pack,
        items=(
            replace(
                item,
                counterevidence_and_applicability=research.CounterevidenceNoneFound(
                    registry.search_scopes[0].ref, 9
                ),
            ),
        ),
    )
    with pytest.raises(research.PriorStoreError) as failure:
        research.PriorPackStore(tmp_path / "prior.sqlite", registry).store_pack(bad)
    assert failure.value.code is research.ResearchServiceErrorCode.DISCLOSURE_REJECTED


def test_policy_pair_cannot_be_promoted_by_a_pack_label(tmp_path):
    _, registry, pack = prior_fixture()
    promoted = replace(
        pack,
        items=(
            replace(
                pack.items[0],
                evidence=replace(
                    pack.items[0].evidence,
                    epistemic_type=research.EpistemicType.CAUSAL_CANDIDATE,
                ),
            ),
        ),
    )
    with pytest.raises(research.PriorStoreError) as failure:
        research.PriorPackStore(tmp_path / "prior.sqlite", registry).store_pack(
            promoted
        )
    assert failure.value.code is research.ResearchServiceErrorCode.DISCLOSURE_REJECTED


class _Verifier:
    def verify_publication(self, receipt, signature):
        return signature.key_ref == "production_verifier_fixture"

    def verify_withdrawal(self, pack_ref, authorization_ref):
        return authorization_ref == "owner_withdrawal_fixture"


def test_authorized_public_history_and_withdrawal_preserve_audit_bytes(tmp_path):
    _, registry, fixture_pack = prior_fixture()
    pack = public_pack(fixture_pack)
    store = research.PriorPackStore(
        tmp_path / "prior.sqlite", registry, public_verifier=_Verifier()
    )
    ref = research.prior_pack_ref(pack)
    transition = store._transition_digest(
        pack.challenge_key,
        pack.channel,
        0,
        research.PriorPreviousIndexGenesis(),
        ref,
        (ref,),
    )
    receipt = research.PriorPublicationReceipt(
        pack.challenge_key,
        pack.channel,
        0,
        ref,
        pack.prior_policy_bundle_ref,
        ("gauntlet_fixture",),
        ("owner_approval_fixture",),
        digest("a"),
        digest("a"),
        pack.activation_epoch,
        research.PriorPreviousIndexGenesis(),
        transition,
    )
    signed = research.SignedPublicPublication(
        receipt,
        receipt.to_ref(),
        research.SignatureEnvelope("production_verifier_fixture", b"verified"),
    )
    snapshot_ref = store.import_public_release(pack, signed, expected_previous=None)
    assert store.read_pack(ref) == pack
    withdrawal_ref = store.withdraw_public(
        ref,
        authorization_ref="owner_withdrawal_fixture",
        expected_previous=snapshot_ref,
    )
    assert store.read_snapshot(withdrawal_ref).active_prior_pack_ref is None
    with pytest.raises(research.PriorStoreError):
        store.read_pack(ref)
    assert store.read_pack(ref, audit=True) == pack
