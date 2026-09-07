from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest
from b07d_fixtures import FixtureBuilder, prior_fixture, synthetic_snapshot

from carbon import research


def _publisher(tmp_path):
    _, registry, pack = prior_fixture()
    store = research.PriorPackStore(tmp_path / "prior.sqlite", registry)
    store.initialize_disclosure_ledger("fixture_disclosure")
    signer = research.DeterministicTestOnlySigner(
        "fixture_signing_key", b"fixture-secret"
    )
    publisher = research.SyntheticPriorPublisher(
        store,
        FixtureBuilder(pack),
        research.ExactHashFixtureAuthorizer("fixture_authorization"),
        signer,
        research.FixturePublishingPolicy(2, 1, 1, 3, 10),
        ledger_key="fixture_disclosure",
    )
    return store, publisher, pack


def test_synthetic_candidate_checks_authorization_and_atomic_persistent_commit(
    tmp_path,
):
    store, publisher, pack = _publisher(tmp_path)
    snapshot_ref = publisher.publish(
        synthetic_snapshot(pack.challenge_key),
        publication_sequence=0,
        activation_epoch=12,
        expires_at_micros=1_000_000,
        fixture_suite_id="fixture_suite",
        expected_previous=None,
    )
    snapshot = store.read_snapshot(snapshot_ref)
    assert snapshot.active_prior_pack_ref is not None
    assert type(snapshot.index_authorization) is research.FixturePriorAuthorization
    reopened = research.PriorPackStore(store.database_path, store._registry)
    assert reopened.disclosure_ledger_state("fixture_disclosure")[0] == 1
    assert (
        reopened.current_snapshot_ref(pack.challenge_key, pack.channel) == snapshot_ref
    )


def test_poisoning_lag_and_ledger_race_fail_without_receipt_or_index(tmp_path):
    store, publisher, pack = _publisher(tmp_path)
    poisoned = synthetic_snapshot(pack.challenge_key)
    poisoned = replace(
        poisoned,
        records=(replace(poisoned.records[0], poisoned=True), poisoned.records[1]),
    )
    with pytest.raises(research.PriorStoreError):
        publisher.publish(
            poisoned,
            publication_sequence=0,
            activation_epoch=12,
            expires_at_micros=1_000_000,
            fixture_suite_id="fixture_suite",
            expected_previous=None,
        )
    assert store.current_snapshot_ref(pack.challenge_key, pack.channel) is None
    assert store.disclosure_ledger_state("fixture_disclosure")[0] == 0


def test_future_public_branches_are_specified_but_unavailable():
    for source in research.PublicPriorSourceClass:
        with pytest.raises(research.PriorStoreError) as failure:
            research.FuturePublicPipelineSpec(source).activate()
        assert (
            failure.value.code
            is research.ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE
        )


@pytest.mark.parametrize(
    "change",
    (
        {"record_class": research.SyntheticRecordClass.MOCK},
        {"rights_eligible": False},
        {"stale": True},
        {"identifying": True},
    ),
)
def test_ineligible_classes_cannot_produce_a_fixture_release(tmp_path, change):
    store, publisher, pack = _publisher(tmp_path)
    snapshot = synthetic_snapshot(pack.challenge_key)
    snapshot = replace(
        snapshot,
        records=tuple(replace(item, **change) for item in snapshot.records),
    )
    with pytest.raises(research.PriorStoreError):
        publisher.publish(
            snapshot,
            publication_sequence=0,
            activation_epoch=12,
            expires_at_micros=1_000_000,
            fixture_suite_id="fixture_suite",
            expected_previous=None,
        )
    assert store.current_snapshot_ref(pack.challenge_key, pack.channel) is None


def test_material_counterevidence_cannot_be_replaced_by_none_found(tmp_path):
    _, registry, pack = prior_fixture()

    class SuppressingBuilder(FixtureBuilder):
        def build(self, snapshot, *, publication_sequence, activation_epoch):
            candidate = super().build(
                snapshot,
                publication_sequence=publication_sequence,
                activation_epoch=activation_epoch,
            )
            item = candidate.items[0]
            return replace(
                candidate,
                items=(
                    replace(
                        item,
                        counterevidence_and_applicability=research.CounterevidenceNoneFound(
                            registry.search_scopes[0].ref, 10
                        ),
                    ),
                ),
            )

    store = research.PriorPackStore(tmp_path / "prior.sqlite", registry)
    store.initialize_disclosure_ledger("fixture_disclosure")
    publisher = research.SyntheticPriorPublisher(
        store,
        SuppressingBuilder(pack),
        research.ExactHashFixtureAuthorizer("fixture_authorization"),
        research.DeterministicTestOnlySigner("fixture_key", b"secret"),
        research.FixturePublishingPolicy(2, 1, 1, 3, 10),
        ledger_key="fixture_disclosure",
    )
    with pytest.raises(research.PriorStoreError):
        publisher.publish(
            synthetic_snapshot(pack.challenge_key),
            publication_sequence=0,
            activation_epoch=12,
            expires_at_micros=1_000_000,
            fixture_suite_id="fixture_suite",
            expected_previous=None,
        )
    assert store.disclosure_ledger_state("fixture_disclosure")[0] == 0


def test_corrupt_persistent_ledger_fails_closed_before_authorization(tmp_path):
    store, publisher, pack = _publisher(tmp_path)
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            "UPDATE disclosure_ledger_state SET state_json = ? WHERE ledger_key = ?",
            ("{corrupt", "fixture_disclosure"),
        )
    with pytest.raises(research.PriorStoreError) as failure:
        publisher.publish(
            synthetic_snapshot(pack.challenge_key),
            publication_sequence=0,
            activation_epoch=12,
            expires_at_micros=1_000_000,
            fixture_suite_id="fixture_suite",
            expected_previous=None,
        )
    assert failure.value.code is research.ResearchServiceErrorCode.DISCLOSURE_REJECTED


def test_synthetic_snapshot_resource_bound_rejects_before_processing():
    _, _, pack = prior_fixture()
    snapshot = synthetic_snapshot(pack.challenge_key)
    with pytest.raises(ValueError):
        replace(snapshot, records=snapshot.records * 2_049)
