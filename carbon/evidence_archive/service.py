"""C-EA1 archive coordinator for the approved synthetic development profile."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from .model import (
    SCHEMA_VERSION,
    SYNTHETIC_PROFILE_ID,
    SYNTHETIC_TENANT_ID,
    AcknowledgementReason,
    AcknowledgementState,
    ArchiveAcknowledgement,
    ArchiveCode,
    ArchiveEntry,
    ArchiveFailure,
    ArtifactInput,
    ArtifactManifest,
    ArtifactRecord,
    ArtifactState,
    AttemptRelation,
    AttemptRelationKind,
    DependenceLink,
    EpistemicValue,
    EvidenceCaptureProfile,
    EvidenceCompleteness,
    ExecutionDisposition,
    QualificationOrigin,
    ScientificResultState,
    SourceBinding,
    SourceFailureClass,
    canonical_bytes,
    content_digest,
    derive_archive_entry_id,
)
from .storage import (
    KeyMaterial,
    ObjectStore,
    PostgresCatalogue,
    StageJournal,
    artifact_record_payload,
    decrypt_artifact,
    derive_object_key,
    encrypt_artifact,
)

SYNTHETIC_FIXTURE_PREFIX = b"CARBON_CEA1_SYNTHETIC_V1\n"
MAX_ARTIFACT_BYTES = 512 * 1024


class PersistenceStage(StrEnum):
    AFTER_CATALOGUE_RESERVATION = "AFTER_CATALOGUE_RESERVATION"
    AFTER_JOURNAL_ADMISSION = "AFTER_JOURNAL_ADMISSION"
    AFTER_JOURNAL_ARTIFACT = "AFTER_JOURNAL_ARTIFACT"
    AFTER_OBJECT_WRITE = "AFTER_OBJECT_WRITE"
    AFTER_OBJECT_VERIFICATION = "AFTER_OBJECT_VERIFICATION"
    AFTER_CATALOGUE_COMMIT = "AFTER_CATALOGUE_COMMIT"
    AFTER_AVAILABILITY_VERIFICATION = "AFTER_AVAILABILITY_VERIFICATION"
    AFTER_ACKNOWLEDGEMENT = "AFTER_ACKNOWLEDGEMENT"
    AFTER_CONSUMER_EFFECT = "AFTER_CONSUMER_EFFECT"


@dataclass(frozen=True, slots=True)
class Admission:
    entry: ArchiveEntry
    declared_objects: int
    declared_bytes: int


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    entry: ArchiveEntry
    manifest: ArtifactManifest
    completeness: EvidenceCompleteness
    acknowledgement: ArchiveAcknowledgement


@dataclass(frozen=True, slots=True)
class ArchiveHealth:
    schema_version: str
    catalogue_available: bool
    object_store_available: bool
    active_catalogue_reservations: int
    active_journal_reservations: int
    archived_entries: int
    outbox_events: int
    quarantined_objects: int


def _entry_payload(entry: ArchiveEntry) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "archive_entry_id": entry.archive_entry_id,
        "source": entry.source.payload(),
        "relation": {
            "kind": entry.relation.kind.value,
            "previous_archive_entry_id": entry.relation.previous_archive_entry_id,
        },
        "capture_profile_digest": entry.capture_profile_digest,
        "execution_disposition": entry.execution_disposition.value,
        "scientific_result_state": entry.scientific_result_state.value,
        "scientific_result_ref": entry.scientific_result_ref,
        "qualification_origin": entry.qualification_origin.value,
        "source_failure_class": entry.source_failure_class.value,
        "guidance_exposure": entry.guidance_exposure.value,
        "dependence_links": [
            {"kind": link.kind.value, "source_ref": link.source_ref}
            for link in entry.dependence_links
        ],
    }


def _acknowledgement(
    entry: ArchiveEntry,
    profile: EvidenceCaptureProfile,
    manifest: ArtifactManifest,
    state: AcknowledgementState,
    reason: AcknowledgementReason,
) -> ArchiveAcknowledgement:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "archive_entry_id": entry.archive_entry_id,
        "manifest_identity": manifest.content_identity,
        "capture_profile_digest": profile.digest,
        "durability_policy_ref": profile.durability_policy_ref,
        "custody_policy_ref": profile.custody_policy_ref,
        "state": state.value,
        "reason": reason.value,
        "synthetic_only": True,
        "eligible_for_real_finalization": False,
        "eligible_for_network_use": False,
    }
    return ArchiveAcknowledgement(
        acknowledgement_ref=content_digest(
            "carbon.evidence-archive.acknowledgement.v1", canonical_bytes(payload)
        ),
        archive_entry_id=entry.archive_entry_id,
        manifest_identity=manifest.content_identity,
        capture_profile_digest=profile.digest,
        durability_policy_ref=profile.durability_policy_ref,
        custody_policy_ref=profile.custody_policy_ref,
        state=state,
        reason=reason,
    )


def _ack_payload(value: ArchiveAcknowledgement) -> bytes:
    return canonical_bytes(
        {
            "schema_version": SCHEMA_VERSION,
            "acknowledgement_ref": value.acknowledgement_ref,
            "archive_entry_id": value.archive_entry_id,
            "manifest_identity": value.manifest_identity,
            "capture_profile_digest": value.capture_profile_digest,
            "durability_policy_ref": value.durability_policy_ref,
            "custody_policy_ref": value.custody_policy_ref,
            "state": value.state.value,
            "reason": value.reason.value,
            "synthetic_only": value.synthetic_only,
            "eligible_for_real_finalization": value.eligible_for_real_finalization,
            "eligible_for_network_use": value.eligible_for_network_use,
        }
    )


class EvidenceArchive:
    """No distributed transaction: replay converges across each durable stage."""

    def __init__(
        self,
        catalogue: PostgresCatalogue,
        journal: StageJournal,
        objects: ObjectStore,
        *,
        fault_hook: Callable[[PersistenceStage], None] | None = None,
    ) -> None:
        self.catalogue = catalogue
        self.journal = journal
        self.objects = objects
        self.fault_hook = fault_hook or (lambda stage: None)

    def _fault(self, stage: PersistenceStage) -> None:
        self.fault_hook(stage)

    def admit(
        self,
        source: SourceBinding,
        relation: AttemptRelation,
        profile: EvidenceCaptureProfile,
        *,
        execution_disposition: ExecutionDisposition,
        scientific_result_state: ScientificResultState,
        scientific_result_ref: str | None,
        declared_objects: int,
        declared_bytes: int,
        source_failure_class: SourceFailureClass = SourceFailureClass.NONE,
        guidance_exposure: EpistemicValue = EpistemicValue.UNKNOWN,
        dependence_links: tuple[DependenceLink, ...] = (),
    ) -> Admission:
        if (
            type(source) is not SourceBinding
            or source.tenant_id != SYNTHETIC_TENANT_ID
            or type(relation) is not AttemptRelation
            or type(profile) is not EvidenceCaptureProfile
            or profile.profile_id != SYNTHETIC_PROFILE_ID
            or profile.challenge_id != source.challenge_id
            or type(execution_disposition) is not ExecutionDisposition
            or type(scientific_result_state) is not ScientificResultState
        ):
            raise ArchiveFailure(ArchiveCode.DENIED)
        if relation.kind is AttemptRelationKind.INITIAL and source.attempt_number != 1:
            raise ArchiveFailure(ArchiveCode.CONFLICT)
        if (
            relation.kind is not AttemptRelationKind.INITIAL
            and source.attempt_number <= 1
        ):
            raise ArchiveFailure(ArchiveCode.CONFLICT)
        if relation.kind is not AttemptRelationKind.INITIAL:
            previous = self.catalogue.relation_source(
                relation.previous_archive_entry_id or ""
            )
            if previous != (
                source.tenant_id,
                source.submission_id,
                source.attempt_number - 1,
            ):
                raise ArchiveFailure(ArchiveCode.CONFLICT)
        entry_id = derive_archive_entry_id(source, relation, profile.digest)
        entry = ArchiveEntry(
            entry_id,
            source,
            relation,
            profile.digest,
            execution_disposition,
            scientific_result_state,
            scientific_result_ref,
            QualificationOrigin.FIXTURE,
            source_failure_class,
            guidance_exposure,
            dependence_links,
        )
        admission_payload = canonical_bytes(
            {
                "entry": _entry_payload(entry),
                "profile": profile.payload(),
                "declared_objects": declared_objects,
                "declared_bytes": declared_bytes,
            }
        )
        created = self.catalogue.reserve(
            entry_id,
            source.tenant_id,
            admission_payload,
            declared_objects,
            declared_bytes,
        )
        self._fault(PersistenceStage.AFTER_CATALOGUE_RESERVATION)
        try:
            self.journal.reserve(
                entry_id, admission_payload, declared_objects, declared_bytes
            )
        except Exception:
            if created:
                self.catalogue.release_reservation(entry_id)
            raise
        self._fault(PersistenceStage.AFTER_JOURNAL_ADMISSION)
        return Admission(entry, declared_objects, declared_bytes)

    @staticmethod
    def _validate_inputs(
        admission: Admission,
        profile: EvidenceCaptureProfile,
        artifacts: tuple[ArtifactInput, ...],
    ) -> dict[str, ArtifactInput]:
        if admission.entry.capture_profile_digest != profile.digest:
            raise ArchiveFailure(ArchiveCode.CONFLICT)
        if (
            type(artifacts) is not tuple
            or len(artifacts) != len(profile.artifact_rules)
            or len({artifact.name for artifact in artifacts}) != len(artifacts)
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)
        inputs = {artifact.name: artifact for artifact in artifacts}
        if set(inputs) != {rule.name for rule in profile.artifact_rules}:
            raise ArchiveFailure(ArchiveCode.INVALID)
        payloads = [
            artifact.payload for artifact in artifacts if artifact.payload is not None
        ]
        if (
            len(payloads) > admission.declared_objects
            or sum(len(payload) for payload in payloads) > admission.declared_bytes
            or any(len(payload) > MAX_ARTIFACT_BYTES for payload in payloads)
        ):
            raise ArchiveFailure(ArchiveCode.CAPACITY)
        source_expected = canonical_bytes(admission.entry.source.payload())
        profile_expected = canonical_bytes(profile.payload())
        for name, expected in (
            ("source_binding", source_expected),
            ("manifest_input", profile_expected),
        ):
            value = inputs[name]
            if value.state is ArtifactState.WRITTEN and value.payload != expected:
                raise ArchiveFailure(ArchiveCode.CONFLICT)
        for artifact in artifacts:
            if (
                artifact.payload is not None
                and artifact.name not in {"source_binding", "manifest_input"}
                and not artifact.payload.startswith(SYNTHETIC_FIXTURE_PREFIX)
            ):
                raise ArchiveFailure(ArchiveCode.DENIED)
        return inputs

    def archive(
        self,
        admission: Admission,
        profile: EvidenceCaptureProfile,
        artifacts: tuple[ArtifactInput, ...],
        key: KeyMaterial,
    ) -> ArchiveResult:
        inputs = self._validate_inputs(admission, profile, artifacts)
        entry = admission.entry
        records: list[ArtifactRecord] = []
        for rule in profile.artifact_rules:
            item = inputs[rule.name]
            if item.state is not ArtifactState.WRITTEN:
                records.append(
                    ArtifactRecord(
                        rule.name,
                        rule.requirement,
                        item.state,
                        None,
                        0,
                        None,
                        None,
                        None,
                        None,
                    )
                )
                continue
            assert item.payload is not None
            digest = content_digest("carbon.evidence-artifact.v1", item.payload)
            staged = self.journal.envelope(entry.archive_entry_id, rule.name)
            if staged is None:
                envelope = encrypt_artifact(
                    item.payload,
                    entry_id=entry.archive_entry_id,
                    artifact_name=rule.name,
                    plaintext_digest=digest,
                    key=key,
                )
                self.journal.put_envelope(
                    entry.archive_entry_id,
                    rule.name,
                    digest,
                    len(item.payload),
                    envelope,
                )
                staged = digest, len(item.payload), envelope
            if staged[0] != digest or staged[1] != len(item.payload):
                raise ArchiveFailure(ArchiveCode.CONFLICT)
            envelope = staged[2]
            self._fault(PersistenceStage.AFTER_JOURNAL_ARTIFACT)
            object_key = derive_object_key(
                entry.source.tenant_id, entry.archive_entry_id, rule.name, digest
            )
            self.objects.put_immutable(object_key, envelope.ciphertext)
            self._fault(PersistenceStage.AFTER_OBJECT_WRITE)
            persisted = self.objects.get(object_key)
            if persisted != envelope.ciphertext:
                raise ArchiveFailure(ArchiveCode.INTEGRITY)
            decrypt_artifact(
                envelope,
                entry_id=entry.archive_entry_id,
                artifact_name=rule.name,
                plaintext_digest=digest,
                key=key,
            )
            self._fault(PersistenceStage.AFTER_OBJECT_VERIFICATION)
            records.append(
                ArtifactRecord(
                    rule.name,
                    rule.requirement,
                    ArtifactState.VERIFIED,
                    digest,
                    len(item.payload),
                    object_key,
                    envelope.key_id,
                    envelope.algorithm,
                    envelope.nonce_hex,
                )
            )
        manifest_payload = canonical_bytes(
            {
                "schema_version": SCHEMA_VERSION,
                "archive_entry_id": entry.archive_entry_id,
                "capture_profile_digest": profile.digest,
                "artifacts": [artifact_record_payload(record) for record in records],
            }
        )
        manifest_identity = content_digest(
            "carbon.evidence-archive.manifest.v1", manifest_payload
        )
        manifest = ArtifactManifest(
            SCHEMA_VERSION,
            entry.archive_entry_id,
            profile.digest,
            tuple(records),
            manifest_identity,
        )
        entry_payload = canonical_bytes(_entry_payload(entry))
        self.catalogue.finalize(
            entry.archive_entry_id,
            profile.digest,
            entry_payload,
            manifest_identity,
            tuple(records),
            manifest_payload,
        )
        self._fault(PersistenceStage.AFTER_CATALOGUE_COMMIT)
        acknowledgement, completeness = self.verify_current(
            entry, profile, manifest, key
        )
        self._fault(PersistenceStage.AFTER_AVAILABILITY_VERIFICATION)
        self.catalogue.record_acknowledgement(
            entry.archive_entry_id,
            _ack_payload(acknowledgement),
            acknowledgement.acknowledgement_ref,
            release=(acknowledgement.state is AcknowledgementState.VERIFIED_DURABLE),
        )
        if acknowledgement.state is AcknowledgementState.VERIFIED_DURABLE:
            self.journal.release(entry.archive_entry_id)
        self._fault(PersistenceStage.AFTER_ACKNOWLEDGEMENT)
        return ArchiveResult(entry, manifest, completeness, acknowledgement)

    def verify_current(
        self,
        entry: ArchiveEntry,
        profile: EvidenceCaptureProfile,
        manifest: ArtifactManifest,
        key: KeyMaterial | None,
    ) -> tuple[ArchiveAcknowledgement, EvidenceCompleteness]:
        if (
            entry.source.tenant_id != SYNTHETIC_TENANT_ID
            or entry.capture_profile_digest != profile.digest
            or manifest.archive_entry_id != entry.archive_entry_id
            or manifest.capture_profile_digest != profile.digest
        ):
            return (
                _acknowledgement(
                    entry,
                    profile,
                    manifest,
                    AcknowledgementState.REJECTED,
                    AcknowledgementReason.SOURCE_BINDING_INVALID,
                ),
                EvidenceCompleteness.UNAVAILABLE,
            )
        manifest_payload = canonical_bytes(
            {
                "schema_version": SCHEMA_VERSION,
                "archive_entry_id": entry.archive_entry_id,
                "capture_profile_digest": profile.digest,
                "artifacts": [
                    artifact_record_payload(record) for record in manifest.artifacts
                ],
            }
        )
        expected_manifest = content_digest(
            "carbon.evidence-archive.manifest.v1", manifest_payload
        )
        if expected_manifest != manifest.content_identity:
            return (
                _acknowledgement(
                    entry,
                    profile,
                    manifest,
                    AcknowledgementState.REJECTED,
                    AcknowledgementReason.MANIFEST_NOT_VERIFIED,
                ),
                EvidenceCompleteness.UNAVAILABLE,
            )
        try:
            committed = self.catalogue.verify_commit(
                entry.archive_entry_id,
                canonical_bytes(_entry_payload(entry)),
                manifest.content_identity,
                manifest.artifacts,
            )
        except ArchiveFailure:
            committed = False
        if not committed:
            return (
                _acknowledgement(
                    entry,
                    profile,
                    manifest,
                    AcknowledgementState.REJECTED,
                    AcknowledgementReason.CATALOGUE_NOT_COMMITTED,
                ),
                EvidenceCompleteness.UNAVAILABLE,
            )
        rules = {rule.name: rule for rule in profile.artifact_rules}
        availability = self.catalogue.latest_availability(entry.archive_entry_id)
        for record in manifest.artifacts:
            rule = rules.get(record.name)
            if rule is None:
                return (
                    _acknowledgement(
                        entry,
                        profile,
                        manifest,
                        AcknowledgementState.REJECTED,
                        AcknowledgementReason.MANIFEST_NOT_VERIFIED,
                    ),
                    EvidenceCompleteness.UNAVAILABLE,
                )
            current_state = availability.get(record.name, record.state)
            if rule.is_required(entry.execution_disposition):
                if current_state in {ArtifactState.EXPECTED, ArtifactState.WRITTEN}:
                    return (
                        _acknowledgement(
                            entry,
                            profile,
                            manifest,
                            AcknowledgementState.PENDING,
                            AcknowledgementReason.REQUIRED_ARTIFACT_PENDING,
                        ),
                        EvidenceCompleteness.UNASSESSED,
                    )
                if current_state is not ArtifactState.VERIFIED:
                    reason = (
                        AcknowledgementReason.KEY_UNAVAILABLE
                        if current_state is ArtifactState.UNAVAILABLE_KEY
                        else AcknowledgementReason.REQUIRED_ARTIFACT_UNAVAILABLE
                    )
                    return (
                        _acknowledgement(
                            entry,
                            profile,
                            manifest,
                            AcknowledgementState.REJECTED,
                            reason,
                        ),
                        EvidenceCompleteness.UNAVAILABLE,
                    )
            if current_state is ArtifactState.VERIFIED:
                if key is None:
                    return (
                        _acknowledgement(
                            entry,
                            profile,
                            manifest,
                            AcknowledgementState.REJECTED,
                            AcknowledgementReason.KEY_UNAVAILABLE,
                        ),
                        EvidenceCompleteness.UNAVAILABLE,
                    )
                try:
                    assert record.object_key is not None
                    assert record.plaintext_digest is not None
                    staged = self.journal.envelope(entry.archive_entry_id, record.name)
                    if staged is None:
                        raise ArchiveFailure(ArchiveCode.INTEGRITY)
                    envelope = staged[2]
                    ciphertext = self.objects.get(record.object_key)
                    if ciphertext != envelope.ciphertext:
                        raise ArchiveFailure(ArchiveCode.INTEGRITY)
                    decrypt_artifact(
                        envelope,
                        entry_id=entry.archive_entry_id,
                        artifact_name=record.name,
                        plaintext_digest=record.plaintext_digest,
                        key=key,
                    )
                except ArchiveFailure as failure:
                    reason = (
                        AcknowledgementReason.KEY_UNAVAILABLE
                        if failure.code is ArchiveCode.KEY_UNAVAILABLE
                        else AcknowledgementReason.OBJECT_UNAVAILABLE
                    )
                    return (
                        _acknowledgement(
                            entry,
                            profile,
                            manifest,
                            AcknowledgementState.REJECTED,
                            reason,
                        ),
                        EvidenceCompleteness.UNAVAILABLE,
                    )
        self._fault(PersistenceStage.AFTER_AVAILABILITY_VERIFICATION)
        return (
            _acknowledgement(
                entry,
                profile,
                manifest,
                AcknowledgementState.VERIFIED_DURABLE,
                AcknowledgementReason.VERIFIED,
            ),
            EvidenceCompleteness.COMPLETE,
        )

    def record_unavailability(
        self,
        entry: ArchiveEntry,
        artifact_name: str,
        state: ArtifactState,
        reason_ref: str,
    ) -> None:
        """Append a later loss/withdrawal/key state without rewriting history."""

        self.catalogue.append_availability(
            entry.archive_entry_id, artifact_name, state, reason_ref
        )

    def consume_outbox(self, consumer_id: str, *, reverse: bool = False) -> int:
        events = self.catalogue.outbox()
        if reverse:
            events = tuple(reversed(events))
        applied = 0
        for event_id, _, payload in events:
            if self.catalogue.consume(consumer_id, event_id, payload):
                applied += 1
            self._fault(PersistenceStage.AFTER_CONSUMER_EFFECT)
        return applied

    def quarantine_orphans(self) -> tuple[str, ...]:
        tenant = SYNTHETIC_TENANT_ID
        known = set(self.catalogue.object_keys(tenant))
        quarantined: list[str] = []
        for object_key in self.objects.list_keys(tenant):
            if object_key in known:
                continue
            body = self.objects.get(object_key)
            quarantine_ref = self.objects.quarantine(object_key)
            self.catalogue.record_orphan(object_key, quarantine_ref, body)
            quarantined.append(quarantine_ref)
        return tuple(quarantined)

    def health(self) -> ArchiveHealth:
        """Return bounded counts and booleans only; never payload/key material."""

        try:
            active, entries, outbox, orphans = self.catalogue.health_counts()
            catalogue_available = True
        except ArchiveFailure:
            active = entries = outbox = orphans = 0
            catalogue_available = False
        try:
            self.objects.list_keys(SYNTHETIC_TENANT_ID)
            object_store_available = True
        except ArchiveFailure:
            object_store_available = False
        return ArchiveHealth(
            schema_version="carbon.evidence-archive.health.v1",
            catalogue_available=catalogue_available,
            object_store_available=object_store_available,
            active_catalogue_reservations=active,
            active_journal_reservations=self.journal.active_count(),
            archived_entries=entries,
            outbox_events=outbox,
            quarantined_objects=orphans,
        )
