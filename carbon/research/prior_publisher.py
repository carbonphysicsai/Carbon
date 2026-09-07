"""B-07D2 deterministic synthetic-only PriorPack fixture publisher."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from carbon.registry import ChallengeKey, validate_canonical_identifier

from .canonical import canonical_bytes
from .errors import ResearchServiceErrorCode
from .model import (
    CounterevidenceEntries,
    CounterevidenceFinding,
    CounterevidenceNoneFound,
    PriorPack,
    PriorPublicationClass,
)
from .prior_store import (
    DeterministicTestOnlySigner,
    PriorPackStore,
    PriorStoreError,
    SignedTestOnlyAuthorization,
    TestOnlyPriorAuthorizationReceipt,
    prior_pack_ref,
)
from .refs import (
    PriorChannel,
    PriorIndexSnapshotRef,
    PublicAggregatePublicationRef,
    PublicEstimandRef,
)


class SyntheticFinding(str, Enum):
    SUPPORT = "SUPPORT"
    NULL = "NULL"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class SyntheticRecordClass(str, Enum):
    FIXTURE = "FIXTURE"
    MOCK = "MOCK"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class SyntheticPriorRecord:
    """A deliberately separate fixture record, never an ExperimentRecord."""

    record_id: str
    challenge_key: ChallengeKey
    surface_id: str
    public_estimand_ref: PublicEstimandRef
    lineage_id: str
    joint_cell_id: str
    evidence_epoch: int
    finding: SyntheticFinding
    effect_value: float
    fixture_only: bool
    eligible: bool
    poisoned: bool = False
    private_canary: str | None = None
    record_class: SyntheticRecordClass = SyntheticRecordClass.FIXTURE
    rights_eligible: bool = True
    stale: bool = False
    identifying: bool = False
    public_context_id: str = "fixture_context"
    public_backbone_id: str = "basic_backbone"
    public_provenance_ref: PublicAggregatePublicationRef | None = None

    def __post_init__(self) -> None:
        if type(self) is not SyntheticPriorRecord:
            raise TypeError("synthetic record subclasses are rejected")
        for value, name in (
            (self.record_id, "record_id"),
            (self.surface_id, "surface_id"),
            (self.lineage_id, "lineage_id"),
            (self.joint_cell_id, "joint_cell_id"),
        ):
            validate_canonical_identifier(value, name)
        if type(self.finding) is not SyntheticFinding:
            raise TypeError("finding must use the fixture enum")
        if type(self.record_class) is not SyntheticRecordClass:
            raise TypeError("record_class must use the fixture enum")
        for value, name in (
            (self.public_context_id, "public_context_id"),
            (self.public_backbone_id, "public_backbone_id"),
        ):
            validate_canonical_identifier(value, name)
        if (
            type(self.public_estimand_ref) is not PublicEstimandRef
            or self.public_estimand_ref.challenge_key != self.challenge_key
            or type(self.public_provenance_ref) is not PublicAggregatePublicationRef
            or self.public_provenance_ref.challenge_key != self.challenge_key
        ):
            raise ValueError("synthetic public refs have a Challenge mismatch")
        if type(self.evidence_epoch) is not int or self.evidence_epoch < 0:
            raise ValueError("evidence epoch must be nonnegative")
        if type(self.effect_value) is not float:
            raise TypeError("fixture effect must be an exact float")
        if any(
            type(value) is not bool
            for value in (
                self.fixture_only,
                self.eligible,
                self.poisoned,
                self.rights_eligible,
                self.stale,
                self.identifying,
            )
        ):
            raise TypeError("fixture eligibility flags must be exact booleans")


@dataclass(frozen=True, slots=True)
class SyntheticEvidenceSnapshot:
    challenge_key: ChallengeKey
    snapshot_id: str
    records: tuple[SyntheticPriorRecord, ...]

    def __post_init__(self) -> None:
        validate_canonical_identifier(self.snapshot_id, "snapshot_id")
        if type(self.records) is not tuple or not self.records:
            raise ValueError("a synthetic snapshot requires records")
        if len(self.records) > 4_096:
            raise ValueError("synthetic snapshot exceeds the fixture record bound")
        if any(type(item) is not SyntheticPriorRecord for item in self.records):
            raise TypeError("snapshot accepts exact synthetic records only")
        if any(item.challenge_key != self.challenge_key for item in self.records):
            raise ValueError("synthetic record Challenge mismatch")
        identities = tuple(item.record_id for item in self.records)
        if identities != tuple(sorted(identities)) or len(set(identities)) != len(
            identities
        ):
            raise ValueError("synthetic records must be sorted and unique")


@dataclass(frozen=True, slots=True)
class FixturePublishingPolicy:
    minimum_joint_cell_size: int
    maximum_lineage_influence: int
    minimum_lag_epochs: int
    maximum_related_releases: int
    maximum_version_difference: int
    fixture_only: bool = True
    activation_window_epochs: int = 1

    def __post_init__(self) -> None:
        if not self.fixture_only:
            raise ValueError("B-07D2 policy is fixture-only")
        if any(
            type(value) is not int or value < 1
            for value in (
                self.minimum_joint_cell_size,
                self.maximum_lineage_influence,
                self.minimum_lag_epochs,
                self.maximum_related_releases,
                self.maximum_version_difference,
                self.activation_window_epochs,
            )
        ):
            raise ValueError("fixture policy bounds must be positive integers")


@dataclass(frozen=True, slots=True)
class CoarsenedSyntheticAssociation:
    surface_id: str
    public_estimand_ref: PublicEstimandRef
    public_context_id: str
    public_backbone_id: str
    public_provenance_ref: PublicAggregatePublicationRef
    finding: SyntheticFinding
    effect_band: str
    support_band: str
    lineage_diversity_band: str


@dataclass(frozen=True, slots=True)
class SyntheticEvidenceSummary:
    challenge_key: ChallengeKey
    snapshot_id: str
    evidence_cutoff_epoch: int
    associations: tuple[CoarsenedSyntheticAssociation, ...]
    private_cohort_ids: tuple[str, ...]


class SyntheticPackBuilder(Protocol):
    def build(
        self,
        snapshot: SyntheticEvidenceSummary,
        *,
        publication_sequence: int,
        activation_epoch: int,
    ) -> PriorPack: ...


@dataclass(frozen=True, slots=True)
class FixtureGauntletReport:
    candidate_hash: str
    structural_passed: bool
    redaction_passed: bool
    canary_passed: bool
    poisoning_passed: bool
    differencing_passed: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.structural_passed,
                self.redaction_passed,
                self.canary_passed,
                self.poisoning_passed,
                self.differencing_passed,
            )
        )


class StructuralFixtureAuthorizer(Protocol):
    """B-07R-D8 seam: authority must bind the already-tested candidate hash."""

    def authorize(
        self,
        report: FixtureGauntletReport,
        receipt: TestOnlyPriorAuthorizationReceipt,
        signer: DeterministicTestOnlySigner,
    ) -> SignedTestOnlyAuthorization: ...


class ExactHashFixtureAuthorizer:
    """Deterministic test implementation of the delegated structural seam."""

    def __init__(self, authorization_id: str) -> None:
        validate_canonical_identifier(authorization_id, "authorization_id")
        self._authorization_id = authorization_id

    def authorize(
        self,
        report: FixtureGauntletReport,
        receipt: TestOnlyPriorAuthorizationReceipt,
        signer: DeterministicTestOnlySigner,
    ) -> SignedTestOnlyAuthorization:
        if (
            not report.passed
            or report.candidate_hash != receipt.prior_pack_ref.content_hash
        ):
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        ref = receipt.to_ref(self._authorization_id)
        return SignedTestOnlyAuthorization(
            self._authorization_id,
            receipt,
            ref,
            signer.sign(_receipt_signing_bytes(receipt)),
        )


def _receipt_signing_bytes(receipt: TestOnlyPriorAuthorizationReceipt) -> bytes:
    # The store and this authorizer intentionally bind the exact same private record.
    from .prior_store import _canonical_internal

    return _canonical_internal(receipt)


class SyntheticPriorPublisher:
    """Build, inspect, authorize, and atomically commit TEST_ONLY releases."""

    def __init__(
        self,
        store: PriorPackStore,
        builder: SyntheticPackBuilder,
        authorizer: StructuralFixtureAuthorizer,
        signer: DeterministicTestOnlySigner,
        policy: FixturePublishingPolicy,
        *,
        ledger_key: str,
    ) -> None:
        validate_canonical_identifier(ledger_key, "ledger_key")
        self._store = store
        self._builder = builder
        self._authorizer = authorizer
        self._signer = signer
        self._policy = policy
        self._ledger_key = ledger_key

    def publish(
        self,
        snapshot: SyntheticEvidenceSnapshot,
        *,
        publication_sequence: int,
        activation_epoch: int,
        expires_at_micros: int,
        fixture_suite_id: str,
        expected_previous: PriorIndexSnapshotRef | None,
    ) -> PriorIndexSnapshotRef:
        eligible = self._eligible_snapshot(snapshot, activation_epoch)
        summary = self._coarsen(eligible)
        pack = self._builder.build(
            summary,
            publication_sequence=publication_sequence,
            activation_epoch=activation_epoch,
        )
        if (
            type(pack) is not PriorPack
            or pack.challenge_key != snapshot.challenge_key
            or pack.channel is not PriorChannel.TEST_ONLY_FIXTURE
            or pack.publication_class is not PriorPublicationClass.TEST_ONLY
            or pack.evidence_cutoff_epoch != summary.evidence_cutoff_epoch
            or pack.evidence_cutoff_epoch + self._policy.minimum_lag_epochs
            >= pack.activation_epoch
            or activation_epoch % self._policy.activation_window_epochs != 0
            or not self._summary_matches_pack(summary, pack)
        ):
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        ref = prior_pack_ref(pack)
        candidate = canonical_bytes(pack)
        revision, ledger_digest, state_json = self._store.disclosure_ledger_state(
            self._ledger_key
        )
        next_state, delta, differencing_ok = self._next_ledger(
            json.loads(state_json), pack, summary, revision
        )
        forbidden_text = {
            value.encode("utf-8")
            for record in snapshot.records
            for value in (
                record.record_id,
                record.lineage_id,
                record.joint_cell_id,
                record.private_canary,
            )
            if value
        }
        forbidden_effects = {
            struct.pack(">d", record.effect_value) for record in snapshot.records
        }
        report = FixtureGauntletReport(
            ref.content_hash,
            structural_passed=pack == self._store_round_trip(pack),
            redaction_passed=not any(
                token in candidate for token in forbidden_text | forbidden_effects
            ),
            canary_passed=not any(
                record.private_canary and record.private_canary.encode() in candidate
                for record in snapshot.records
            ),
            poisoning_passed=not any(record.poisoned for record in eligible.records),
            differencing_passed=differencing_ok
            and self._counterevidence_preserved(summary, pack),
        )
        if not report.passed:
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        self._store.store_pack(pack, ref)
        receipt = TestOnlyPriorAuthorizationReceipt(
            snapshot.challenge_key, ref, fixture_suite_id, expires_at_micros
        )
        signed = self._authorizer.authorize(report, receipt, self._signer)
        return self._store.commit_fixture_release(
            signed,
            self._signer,
            ledger_key=self._ledger_key,
            expected_ledger_digest=ledger_digest,
            next_ledger_state_json=json.dumps(
                next_state, sort_keys=True, separators=(",", ":")
            ),
            ledger_delta_json=json.dumps(delta, sort_keys=True, separators=(",", ":")),
            expected_previous=expected_previous,
        )

    def _store_round_trip(self, pack: PriorPack) -> PriorPack:
        from .canonical import load_canonical

        return load_canonical(canonical_bytes(pack), PriorPack)

    def _eligible_snapshot(
        self, snapshot: SyntheticEvidenceSnapshot, activation_epoch: int
    ) -> SyntheticEvidenceSnapshot:
        candidates = tuple(
            item
            for item in snapshot.records
            if item.fixture_only
            and item.eligible
            and item.record_class is SyntheticRecordClass.FIXTURE
            and item.rights_eligible
            and not item.stale
            and not item.identifying
            and item.evidence_epoch + self._policy.minimum_lag_epochs < activation_epoch
        )
        cell_counts: dict[str, int] = {}
        lineage_counts: dict[str, int] = {}
        for item in candidates:
            cell_counts[item.joint_cell_id] = cell_counts.get(item.joint_cell_id, 0) + 1
        selected: list[SyntheticPriorRecord] = []
        for item in candidates:
            if cell_counts[item.joint_cell_id] < self._policy.minimum_joint_cell_size:
                continue
            count = lineage_counts.get(item.lineage_id, 0)
            if count >= self._policy.maximum_lineage_influence:
                continue
            lineage_counts[item.lineage_id] = count + 1
            selected.append(item)
        if not selected:
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        # Material null/negative/mixed/out-of-scope records survive eligibility.
        material = {
            SyntheticFinding.NULL,
            SyntheticFinding.NEGATIVE,
            SyntheticFinding.MIXED,
            SyntheticFinding.OUT_OF_SCOPE,
        }
        if any(item.finding in material for item in candidates) and not any(
            item.finding in material for item in selected
        ):
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        return SyntheticEvidenceSnapshot(
            snapshot.challenge_key, snapshot.snapshot_id, tuple(selected)
        )

    @staticmethod
    def _coarsen(snapshot: SyntheticEvidenceSnapshot) -> SyntheticEvidenceSummary:
        groups: dict[tuple[object, ...], list[SyntheticPriorRecord]] = {}
        for item in snapshot.records:
            key = (
                item.surface_id,
                item.public_estimand_ref,
                item.public_context_id,
                item.public_backbone_id,
                item.public_provenance_ref,
                item.finding.value,
            )
            groups.setdefault(key, []).append(item)
        associations: list[CoarsenedSyntheticAssociation] = []
        for key, records in sorted(groups.items(), key=lambda item: repr(item[0])):
            mean = sum(item.effect_value for item in records) / len(records)
            effect_band = (
                "negative" if mean < 0.0 else "positive" if mean > 0.0 else "null"
            )
            support_band = (
                "small"
                if len(records) < 4
                else "medium" if len(records) < 16 else "large"
            )
            diversity = len({item.lineage_id for item in records})
            diversity_band = "single" if diversity == 1 else "multiple"
            associations.append(
                CoarsenedSyntheticAssociation(
                    *key[:5],
                    SyntheticFinding(key[5]),
                    effect_band,
                    support_band,
                    diversity_band,
                )
            )
        return SyntheticEvidenceSummary(
            snapshot.challenge_key,
            snapshot.snapshot_id,
            max(item.evidence_epoch for item in snapshot.records),
            tuple(associations),
            tuple(sorted({item.joint_cell_id for item in snapshot.records})),
        )

    @staticmethod
    def _summary_matches_pack(
        summary: SyntheticEvidenceSummary, pack: PriorPack
    ) -> bool:
        for association in summary.associations:
            matching = tuple(
                item
                for item in pack.items
                if item.intervention.surface_id == association.surface_id
                and association.public_context_id in item.scope.context_refs
                and association.public_backbone_id in item.scope.backbone_refs
                and association.public_estimand_ref
                in {outcome.public_estimand_ref for outcome in item.expected_outcomes}
                and association.public_provenance_ref
                in item.provenance.public_aggregate_publication_refs
            )
            if not matching:
                return False
        return True

    @staticmethod
    def _counterevidence_preserved(
        summary: SyntheticEvidenceSummary, pack: PriorPack
    ) -> bool:
        expected = {
            SyntheticFinding.NULL: CounterevidenceFinding.NULL,
            SyntheticFinding.NEGATIVE: CounterevidenceFinding.NEGATIVE,
            SyntheticFinding.MIXED: CounterevidenceFinding.MIXED,
            SyntheticFinding.OUT_OF_SCOPE: CounterevidenceFinding.OUT_OF_SCOPE,
        }
        required = {
            expected[item.finding]
            for item in summary.associations
            if item.finding in expected
        }
        observed: set[CounterevidenceFinding] = set()
        for item in pack.items:
            counter = item.counterevidence_and_applicability
            if type(counter) is CounterevidenceNoneFound and required:
                return False
            if type(counter) is CounterevidenceEntries:
                observed.update(entry.finding for entry in counter.entries)
        return required <= observed

    def _next_ledger(
        self,
        state: dict[str, object],
        pack: PriorPack,
        summary: SyntheticEvidenceSummary,
        revision: int,
    ) -> tuple[dict[str, object], dict[str, object], bool]:
        prior_releases = list(state.get("related_releases", []))
        exposed = sorted(
            {item.item_id for item in pack.items}
            | {
                outcome.public_estimand_ref.content_digest
                for item in pack.items
                for outcome in item.expected_outcomes
            }
            | {context for item in pack.items for context in item.scope.context_refs}
        )
        previous = set(state.get("last_exposed", []))
        difference = len(previous.symmetric_difference(exposed)) if previous else 0
        next_releases = [*prior_releases, prior_pack_ref(pack).content_hash]
        ok = (
            len(next_releases) <= self._policy.maximum_related_releases
            and difference <= self._policy.maximum_version_difference
        )
        dimensions = dict(state.get("dimensions", {}))
        accounted = {
            *("field:" + item.item_id for item in pack.items),
            *(
                "estimand:" + outcome.public_estimand_ref.content_digest
                for item in pack.items
                for outcome in item.expected_outcomes
            ),
            *(
                "scope:" + context
                for item in pack.items
                for context in item.scope.context_refs
            ),
            *("cohort:" + cohort for cohort in summary.private_cohort_ids),
            *(
                "provenance:" + ref.content_digest
                for item in pack.items
                for ref in item.provenance.public_aggregate_publication_refs
            ),
        }
        for value in sorted(accounted):
            dimensions[value] = int(dimensions.get(value, 0)) + 1
        next_state = {
            "revision": revision + 1,
            "dimensions": dimensions,
            "related_releases": next_releases,
            "last_exposed": exposed,
        }
        delta = {
            "release": prior_pack_ref(pack).content_hash,
            "exposed": exposed,
            "difference": difference,
        }
        return next_state, delta, ok


class PublicPriorSourceClass(str, Enum):
    BOOTSTRAP_CURATED_PUBLIC = "BOOTSTRAP_CURATED_PUBLIC"
    LEARNED_QUALIFIED_OFFICIAL = "LEARNED_QUALIFIED_OFFICIAL"


@dataclass(frozen=True, slots=True)
class FuturePublicPipelineSpec:
    source_class: PublicPriorSourceClass
    requires_scientific_acceptance: bool = True
    requires_security_acceptance: bool = True
    requires_owner_publication_approval: bool = True

    def activate(self) -> None:
        """Wave B specifies both branches but grants neither an activation route."""

        raise PriorStoreError(ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE)


__all__ = (
    "CoarsenedSyntheticAssociation",
    "ExactHashFixtureAuthorizer",
    "FixtureGauntletReport",
    "FixturePublishingPolicy",
    "FuturePublicPipelineSpec",
    "PublicPriorSourceClass",
    "StructuralFixtureAuthorizer",
    "SyntheticEvidenceSnapshot",
    "SyntheticEvidenceSummary",
    "SyntheticFinding",
    "SyntheticPackBuilder",
    "SyntheticPriorPublisher",
    "SyntheticPriorRecord",
    "SyntheticRecordClass",
)
