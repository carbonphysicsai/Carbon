from __future__ import annotations

import sqlite3

import pytest
from b07d_fixtures import (
    FixtureBuilder,
    digest,
    prior_fixture,
    public_pack,
    synthetic_snapshot,
)

from carbon import research


def _published(tmp_path):
    fixture, registry, pack = prior_fixture()
    store = research.PriorPackStore(tmp_path / "prior.sqlite", registry)
    store.initialize_disclosure_ledger("fixture_disclosure")
    publisher = research.SyntheticPriorPublisher(
        store,
        FixtureBuilder(pack),
        research.ExactHashFixtureAuthorizer("fixture_authorization"),
        research.DeterministicTestOnlySigner("fixture_key", b"secret"),
        research.FixturePublishingPolicy(2, 1, 1, 3, 10),
        ledger_key="fixture_disclosure",
    )
    snapshot_ref = publisher.publish(
        synthetic_snapshot(pack.challenge_key),
        publication_sequence=0,
        activation_epoch=12,
        expires_at_micros=100,
        fixture_suite_id="fixture_suite",
        expected_previous=None,
    )
    return fixture, store, store.read_snapshot(snapshot_ref).active_prior_pack_ref


def test_fixture_provider_is_nominal_exact_ref_only_and_bytes_are_equal(tmp_path):
    _, store, ref = _published(tmp_path)
    provider = research.StaticTestOnlyPriorProvider.for_test_fixture(
        store, now_micros=lambda: 99
    )
    request = research.GetPriorRequest(
        ref.challenge_key, research.ExactPriorSelector(ref)
    )
    first = provider.get_prior(request)
    second = provider.get_prior(request)
    assert research.canonical_bytes(first.prior_pack) == research.canonical_bytes(
        second.prior_pack
    )
    assert first.lookup_status is research.PriorLookupStatus.ACTIVE
    with pytest.raises(research.PriorStoreError):
        provider.get_prior(
            research.GetPriorRequest(
                ref.challenge_key, research.ActivePriorSelector(ref.channel)
            )
        )
    with pytest.raises(TypeError):
        research.StaticTestOnlyPriorProvider(store, object(), now_micros=lambda: 0)


def test_expired_fixture_and_public_crossing_fail_closed(tmp_path):
    _, store, ref = _published(tmp_path)
    expired = research.StaticTestOnlyPriorProvider.for_test_fixture(
        store, now_micros=lambda: 100
    )
    request = research.GetPriorRequest(
        ref.challenge_key, research.ExactPriorSelector(ref)
    )
    with pytest.raises(research.PriorStoreError) as failure:
        expired.get_prior(request)
    assert (
        failure.value.code
        is research.ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID
    )
    with pytest.raises(research.PriorStoreError):
        research.StaticPublicPriorProvider(store).get_prior(request)


def test_missing_persistent_ledger_blocks_previously_authorized_fixture(tmp_path):
    _, store, ref = _published(tmp_path)
    with sqlite3.connect(store.database_path) as connection:
        connection.execute("DELETE FROM disclosure_ledger_state")
    provider = research.StaticTestOnlyPriorProvider.for_test_fixture(
        store, now_micros=lambda: 0
    )
    with pytest.raises(research.PriorStoreError) as failure:
        provider.get_prior(
            research.GetPriorRequest(
                ref.challenge_key, research.ExactPriorSelector(ref)
            )
        )
    assert failure.value.code is research.ResearchServiceErrorCode.DISCLOSURE_REJECTED


def test_alignment_is_deterministic_structural_only_and_resolver_pins(tmp_path):
    fixture, store, ref = _published(tmp_path)
    provider = research.StaticTestOnlyPriorProvider.for_test_fixture(
        store, now_micros=lambda: 0
    )
    alignment = research.DeterministicPriorAlignmentProvider(
        provider, fixture["catalog"]
    )
    request = research.InspectPriorAlignmentRequest(
        ref.challenge_key,
        {
            "schema_version": "1.0",
            "backbone": "basic_backbone",
            "strategy_backbone": "basic_backbone",
            "parameters": {},
        },
        ref,
    )
    assert alignment.inspect_prior_alignment(
        request
    ) == alignment.inspect_prior_alignment(request)
    assert (
        alignment.inspect_prior_alignment(request).status
        is research.PriorAlignmentStatus.ALIGNED
    )
    resolution = research.StaticPriorResolver(provider).resolve_prior(
        research.GetPriorRequest(ref.challenge_key, research.ExactPriorSelector(ref))
    )
    assert resolution.prior_pack_ref == ref
    assert resolution.index_snapshot_ref is not None


class _Verifier:
    def verify_publication(self, receipt, signature):
        return True

    def verify_withdrawal(self, pack_ref, authorization_ref):
        return True


def test_public_provider_supports_authorized_active_and_exact_reads(tmp_path):
    _, registry, fixture_pack = prior_fixture()
    pack = public_pack(fixture_pack)
    store = research.PriorPackStore(
        tmp_path / "public.sqlite", registry, public_verifier=_Verifier()
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
        ("gauntlet",),
        ("owner_approval",),
        digest("a"),
        digest("a"),
        pack.activation_epoch,
        research.PriorPreviousIndexGenesis(),
        transition,
    )
    store.import_public_release(
        pack,
        research.SignedPublicPublication(
            receipt,
            receipt.to_ref(),
            research.SignatureEnvelope("public_key", b"verified"),
        ),
        expected_previous=None,
    )
    provider = research.StaticPublicPriorProvider(store)
    exact = provider.get_prior(
        research.GetPriorRequest(pack.challenge_key, research.ExactPriorSelector(ref))
    )
    active = provider.get_prior(
        research.GetPriorRequest(
            pack.challenge_key,
            research.ActivePriorSelector(research.PriorChannel.PUBLIC),
        )
    )
    assert exact.prior_pack == active.prior_pack == pack
    assert type(active.authorization) is research.PublicPriorAuthorization


def test_active_read_retries_whole_snapshot_once_then_returns_typed_race(
    tmp_path, monkeypatch
):
    _, registry, fixture_pack = prior_fixture()
    pack = public_pack(fixture_pack)
    store = research.PriorPackStore(
        tmp_path / "public.sqlite", registry, public_verifier=_Verifier()
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
        ("gauntlet",),
        ("owner_approval",),
        digest("a"),
        digest("a"),
        pack.activation_epoch,
        research.PriorPreviousIndexGenesis(),
        transition,
    )
    stable = store.import_public_release(
        pack,
        research.SignedPublicPublication(
            receipt,
            receipt.to_ref(),
            research.SignatureEnvelope("public_key", b"verified"),
        ),
        expected_previous=None,
    )
    moved = research.PriorIndexSnapshotRef(
        stable.challenge_key,
        stable.channel,
        stable.index_sequence,
        content_digest=digest("f"),
    )
    observations = iter((stable, moved, stable, moved))
    monkeypatch.setattr(
        research.PriorPackStore,
        "current_snapshot_ref",
        lambda self, key, channel: next(observations),
    )
    with pytest.raises(research.PriorStoreError) as failure:
        research.StaticPublicPriorProvider(store).get_prior(
            research.GetPriorRequest(
                pack.challenge_key,
                research.ActivePriorSelector(research.PriorChannel.PUBLIC),
            )
        )
    assert failure.value.code is research.ResearchServiceErrorCode.PRIOR_INDEX_CHANGED


def test_unknown_public_challenge_and_pack_fail_without_fallback(tmp_path):
    _, registry, pack = prior_fixture()
    store = research.PriorPackStore(tmp_path / "empty.sqlite", registry)
    provider = research.StaticPublicPriorProvider(store)
    with pytest.raises(research.PriorStoreError) as failure:
        provider.get_prior(
            research.GetPriorRequest(
                pack.challenge_key,
                research.ActivePriorSelector(research.PriorChannel.PUBLIC),
            )
        )
    assert failure.value.code is research.ResearchServiceErrorCode.REFERENCE_NOT_FOUND
