"""Immutable PriorPack storage, authorization history, and offline projection.

This module owns B-07D1's private persistence and validation semantics.  It
consumes the B-07A/B-07S wire records from :mod:`carbon.research.model`; it does
not define another pack, pack reference, or serializer.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from carbon.construction.catalog import ParameterCatalog, catalog_entries_by_surface
from carbon.construction.model import ChoiceDomain
from carbon.construction.refs import ParameterCatalogRef
from carbon.registry import ChallengeKey, validate_canonical_identifier

from .canonical import canonical_bytes, canonical_digest, load_canonical
from .errors import ResearchServiceErrorCode
from .model import (
    CounterevidenceEntries,
    CounterevidenceNoneFound,
    EpistemicType,
    EvidenceOrigin,
    FixturePriorAuthorization,
    PriorGuidanceItem,
    PriorPack,
    PriorPublicationClass,
    PublicPriorAuthorization,
)
from .refs import (
    PriorChannel,
    PriorIndexSnapshotRef,
    PriorPackRef,
    PriorPolicyBundleRef,
    PriorPublicationReceiptRef,
    PublicAggregatePublicationRef,
    PublicEstimandRef,
    PublicSearchScopeRef,
    TestOnlyPriorAuthorizationReceiptRef,
)

_PACK_HASH_DOMAIN = b"carbon.prior-pack.v2\x00"
_INDEX_DOMAIN = b"carbon.prior-index-snapshot.v2\x00"
_TRANSITION_DOMAIN = b"carbon.prior-index-transition.v2\x00"
_PUBLIC_RECEIPT_DOMAIN = b"carbon.prior-publication-receipt.v2\x00"
_FIXTURE_RECEIPT_DOMAIN = b"carbon.test-only-prior-authorization.v2\x00"


class PriorStoreError(RuntimeError):
    """Closed failure from the private prior repository."""

    def __init__(self, code: ResearchServiceErrorCode) -> None:
        self.code = code
        super().__init__("Prior repository operation failed.")


class PriorLifecycle(str, Enum):
    STORED = "STORED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


@dataclass(frozen=True, slots=True)
class PublicEstimandDefinition:
    ref: PublicEstimandRef
    baseline_ref: str
    population_scope_ref: str
    directionality: str
    aggregation_functional: str
    measurement_unit: str
    resampling_unit: str
    uncertainty_method: str

    def __post_init__(self) -> None:
        if type(self) is not PublicEstimandDefinition:
            raise TypeError("estimand subclasses are rejected")
        for value, name in (
            (self.baseline_ref, "baseline_ref"),
            (self.population_scope_ref, "population_scope_ref"),
            (self.directionality, "directionality"),
            (self.aggregation_functional, "aggregation_functional"),
            (self.measurement_unit, "measurement_unit"),
            (self.resampling_unit, "resampling_unit"),
            (self.uncertainty_method, "uncertainty_method"),
        ):
            validate_canonical_identifier(value, name)


@dataclass(frozen=True, slots=True)
class PublicSearchScopeDefinition:
    ref: PublicSearchScopeRef
    estimand_refs: tuple[PublicEstimandRef, ...]
    context_refs: tuple[str, ...]
    evidence_cutoff_epoch: int

    def __post_init__(self) -> None:
        if type(self) is not PublicSearchScopeDefinition:
            raise TypeError("search-scope subclasses are rejected")
        if type(self.estimand_refs) is not tuple or not self.estimand_refs:
            raise ValueError("a search scope must name estimands")
        if type(self.context_refs) is not tuple or not self.context_refs:
            raise ValueError("a search scope must name contexts")
        for item in self.context_refs:
            validate_canonical_identifier(item, "context_ref")
        if type(self.evidence_cutoff_epoch) is not int or not (
            0 <= self.evidence_cutoff_epoch < 1 << 64
        ):
            raise ValueError("search-scope cutoff must be uint64")


@dataclass(frozen=True, slots=True)
class PriorValidationRegistry:
    """Exact public inputs against which a shared PriorPack is validated."""

    parameter_catalog: ParameterCatalog
    parameter_catalog_ref: ParameterCatalogRef
    prior_policy_bundle_ref: PriorPolicyBundleRef
    estimands: tuple[PublicEstimandDefinition, ...]
    search_scopes: tuple[PublicSearchScopeDefinition, ...]
    aggregate_publication_refs: tuple[PublicAggregatePublicationRef, ...]
    allowed_origin_epistemic_pairs: tuple[tuple[EvidenceOrigin, EpistemicType], ...]

    def __post_init__(self) -> None:
        if type(self) is not PriorValidationRegistry:
            raise TypeError("validation-registry subclasses are rejected")
        if type(self.parameter_catalog) is not ParameterCatalog:
            raise TypeError("parameter_catalog must use the exact B-02B type")
        if type(self.parameter_catalog_ref) is not ParameterCatalogRef:
            raise TypeError("parameter_catalog_ref must use the exact B-02B ref")
        if (
            self.parameter_catalog.challenge_key
            != self.prior_policy_bundle_ref.challenge_key
        ):
            raise ValueError("policy and catalog Challenges differ")
        if (
            self.parameter_catalog_ref.challenge_key
            != self.parameter_catalog.challenge_key
        ):
            raise ValueError("catalog ref has a Challenge mismatch")
        if len({item.ref for item in self.estimands}) != len(self.estimands):
            raise ValueError("estimand refs must be unique")
        if any(
            type(item) is not PublicEstimandDefinition
            or item.ref.challenge_key != self.parameter_catalog.challenge_key
            for item in self.estimands
        ):
            raise ValueError("estimand definitions have a Challenge mismatch")
        if len({item.ref for item in self.search_scopes}) != len(self.search_scopes):
            raise ValueError("search-scope refs must be unique")
        if any(
            type(item) is not PublicSearchScopeDefinition
            or item.ref.challenge_key != self.parameter_catalog.challenge_key
            or any(
                ref.challenge_key != self.parameter_catalog.challenge_key
                for ref in item.estimand_refs
            )
            for item in self.search_scopes
        ):
            raise ValueError("search-scope definitions have a Challenge mismatch")
        if len(set(self.aggregate_publication_refs)) != len(
            self.aggregate_publication_refs
        ):
            raise ValueError("aggregate publication refs must be unique")
        if not self.allowed_origin_epistemic_pairs or any(
            type(pair) is not tuple
            or len(pair) != 2
            or type(pair[0]) is not EvidenceOrigin
            or type(pair[1]) is not EpistemicType
            for pair in self.allowed_origin_epistemic_pairs
        ):
            raise ValueError("policy must supply exact origin/epistemic pairs")
        if len(set(self.allowed_origin_epistemic_pairs)) != len(
            self.allowed_origin_epistemic_pairs
        ):
            raise ValueError("origin/epistemic pairs must be unique")
        if any(
            type(ref) is not PublicAggregatePublicationRef
            or ref.challenge_key != self.parameter_catalog.challenge_key
            for ref in self.aggregate_publication_refs
        ):
            raise ValueError("aggregate publication refs have a Challenge mismatch")


def prior_pack_ref(pack: PriorPack) -> PriorPackRef:
    """Return the B-07S content reference for exact canonical pack bytes."""

    if type(pack) is not PriorPack:
        raise TypeError("pack must use the exact shared PriorPack type")
    return PriorPackRef(
        pack.challenge_key,
        pack.channel,
        pack.publication_sequence,
        canonical_digest(pack),
    )


def _ref_sort_key(value: object) -> bytes:
    return _canonical_internal(value)


def _require_sorted_unique(values: tuple[object, ...], name: str) -> None:
    keys = tuple(_ref_sort_key(item) for item in values)
    if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
        raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)


def _validate_item(item: PriorGuidanceItem, registry: PriorValidationRegistry) -> None:
    entries = catalog_entries_by_surface(registry.parameter_catalog)
    entry = entries.get(item.intervention.surface_id)
    if entry is None:
        raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    anchors = tuple(
        value
        for value in (
            item.intervention.baseline_ref,
            item.intervention.from_ref,
            item.intervention.to_ref,
        )
        if value is not None
    )
    if type(entry.domain) is ChoiceDomain and not set(anchors) <= set(
        entry.domain.allowed_ids
    ):
        raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_MISMATCH)

    outcomes = {outcome.public_estimand_ref for outcome in item.expected_outcomes}
    registered_estimands = {definition.ref for definition in registry.estimands}
    if not outcomes or not outcomes <= registered_estimands:
        raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    _require_sorted_unique(item.expected_outcomes, "expected_outcomes")
    _require_sorted_unique(item.scope.resource_class_refs, "resource_class_refs")
    for values in (item.scope.backbone_refs, item.scope.context_refs):
        if values != tuple(sorted(values)) or len(values) != len(set(values)):
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)

    counter = item.counterevidence_and_applicability
    if type(counter) is CounterevidenceEntries:
        _require_sorted_unique(counter.entries, "counterevidence")
        for contrary in counter.entries:
            if (
                contrary.public_estimand_ref not in outcomes
                or contrary.scope != item.scope
                or contrary.evidence_origin is not item.evidence.evidence_origin
            ):
                raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
    elif type(counter) is CounterevidenceNoneFound:
        scopes = {definition.ref: definition for definition in registry.search_scopes}
        definition = scopes.get(counter.public_search_scope_ref)
        if (
            definition is None
            or counter.evidence_cutoff_epoch != definition.evidence_cutoff_epoch
            or not outcomes <= set(definition.estimand_refs)
            or not set(item.scope.context_refs) <= set(definition.context_refs)
        ):
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
    else:  # defensive if a hostile object bypasses constructor validation
        raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)

    _require_sorted_unique(
        item.falsification.public_practice_test_refs, "practice_test_refs"
    )
    _require_sorted_unique(
        item.falsification.public_method_artifact_refs, "method_artifact_refs"
    )
    _require_sorted_unique(
        item.provenance.public_aggregate_publication_refs, "provenance"
    )
    if not set(item.provenance.public_aggregate_publication_refs) <= set(
        registry.aggregate_publication_refs
    ):
        raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)


def validate_prior_pack(pack: PriorPack, registry: PriorValidationRegistry) -> None:
    """Enforce B-07D1 authority, evidence, applicability, and identity rules."""

    if type(pack) is not PriorPack or type(registry) is not PriorValidationRegistry:
        raise TypeError("exact pack and validation registry are required")
    if (
        pack.challenge_key != registry.parameter_catalog.challenge_key
        or pack.parameter_catalog_ref != registry.parameter_catalog_ref
        or pack.prior_policy_bundle_ref != registry.prior_policy_bundle_ref
    ):
        raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    for item in pack.items:
        _validate_item(item, registry)
        if pack.publication_class is PriorPublicationClass.TEST_ONLY:
            allowed = {EvidenceOrigin.SYNTHETIC_TEST_FIXTURE}
        elif pack.publication_class is PriorPublicationClass.BOOTSTRAP_PUBLIC:
            allowed = {EvidenceOrigin.CURATED_PUBLIC_SCIENCE}
        else:
            allowed = {
                EvidenceOrigin.CURATED_PUBLIC_SCIENCE,
                EvidenceOrigin.QUALIFIED_OFFICIAL_AGGREGATE,
            }
        origins = {item.evidence.evidence_origin}
        if type(item.counterevidence_and_applicability) is CounterevidenceEntries:
            origins.update(
                entry.evidence_origin
                for entry in item.counterevidence_and_applicability.entries
            )
        if not origins <= allowed:
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        pairs = {(item.evidence.evidence_origin, item.evidence.epistemic_type)}
        if type(item.counterevidence_and_applicability) is CounterevidenceEntries:
            pairs.update(
                (entry.evidence_origin, entry.epistemic_type)
                for entry in item.counterevidence_and_applicability.entries
            )
        if not pairs <= set(registry.allowed_origin_epistemic_pairs):
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)


@dataclass(frozen=True, slots=True)
class PriorPreviousIndexGenesis:
    pass


@dataclass(frozen=True, slots=True)
class PriorPreviousIndexSnapshot:
    previous_index_snapshot_ref: PriorIndexSnapshotRef


PriorPreviousIndex = PriorPreviousIndexGenesis | PriorPreviousIndexSnapshot


@dataclass(frozen=True, slots=True)
class PriorIndexSnapshot:
    schema_version: str
    challenge_key: ChallengeKey
    channel: PriorChannel
    index_sequence: int
    previous_index: PriorPreviousIndex
    active_prior_pack_ref: PriorPackRef | None
    index_authorization: PublicPriorAuthorization | FixturePriorAuthorization
    historical_prior_pack_refs: tuple[PriorPackRef, ...]
    transition_digest: str


@dataclass(frozen=True, slots=True)
class TestOnlyPriorAuthorizationReceipt:
    challenge_key: ChallengeKey
    prior_pack_ref: PriorPackRef
    fixture_suite_id: str
    expires_at_micros: int
    authority_ceiling: str = "NOT_UTILITY_QUALIFIED"

    def __post_init__(self) -> None:
        if type(self) is not TestOnlyPriorAuthorizationReceipt:
            raise TypeError("authorization receipt subclasses are rejected")
        validate_canonical_identifier(self.fixture_suite_id, "fixture_suite_id")
        if (
            self.prior_pack_ref.challenge_key != self.challenge_key
            or self.prior_pack_ref.channel is not PriorChannel.TEST_ONLY_FIXTURE
        ):
            raise ValueError("fixture authorization has a pack mismatch")
        if type(self.expires_at_micros) is not int or not (
            0 <= self.expires_at_micros < 1 << 63
        ):
            raise ValueError("fixture authorization expiry must be int64")
        if self.authority_ceiling != "NOT_UTILITY_QUALIFIED":
            raise ValueError("fixture authority ceiling cannot be raised")

    def to_ref(self, authorization_id: str) -> TestOnlyPriorAuthorizationReceiptRef:
        validate_canonical_identifier(authorization_id, "authorization_id")
        digest = _tagged_digest(_FIXTURE_RECEIPT_DOMAIN, self)
        return TestOnlyPriorAuthorizationReceiptRef(
            self.challenge_key, authorization_id, digest
        )


@dataclass(frozen=True, slots=True)
class PriorPublicationReceipt:
    challenge_key: ChallengeKey
    channel: PriorChannel
    publication_sequence: int
    prior_pack_ref: PriorPackRef
    prior_policy_bundle_ref: PriorPolicyBundleRef
    gauntlet_evidence_refs: tuple[str, ...]
    owner_approval_refs: tuple[str, ...]
    disclosure_ledger_expected_digest: str
    disclosure_ledger_committed_digest: str
    activation_epoch: int
    previous_index: PriorPreviousIndex
    proposed_transition_digest: str

    def __post_init__(self) -> None:
        if type(self) is not PriorPublicationReceipt:
            raise TypeError("publication receipt subclasses are rejected")
        if (
            self.channel is not PriorChannel.PUBLIC
            or self.prior_pack_ref.channel is not PriorChannel.PUBLIC
            or self.prior_pack_ref.challenge_key != self.challenge_key
            or self.prior_pack_ref.publication_sequence != self.publication_sequence
            or self.prior_policy_bundle_ref.challenge_key != self.challenge_key
        ):
            raise ValueError("publication receipt binding is invalid")
        for values in (self.gauntlet_evidence_refs, self.owner_approval_refs):
            if not values or values != tuple(sorted(values)):
                raise ValueError("publication receipt evidence must be sorted/nonempty")
            for value in values:
                validate_canonical_identifier(value, "receipt evidence ref")
        for value in (
            self.disclosure_ledger_expected_digest,
            self.disclosure_ledger_committed_digest,
            self.proposed_transition_digest,
        ):
            _validate_digest(value)

    def to_ref(self) -> PriorPublicationReceiptRef:
        return PriorPublicationReceiptRef(
            self.challenge_key,
            self.channel,
            self.publication_sequence,
            content_digest=_tagged_digest(_PUBLIC_RECEIPT_DOMAIN, self),
        )


@dataclass(frozen=True, slots=True)
class SignatureEnvelope:
    key_ref: str
    signature: bytes

    def __post_init__(self) -> None:
        validate_canonical_identifier(self.key_ref, "key_ref")
        if type(self.signature) is not bytes or not self.signature:
            raise ValueError("signature must be nonempty exact bytes")


class ProductionPriorSigner(Protocol):
    """Unimplemented production key/custody seam."""

    def sign(self, payload: bytes) -> SignatureEnvelope: ...


class PublicReceiptVerifier(Protocol):
    """Injected production verification/authority seam; no default exists."""

    def verify_publication(
        self, receipt: PriorPublicationReceipt, signature: SignatureEnvelope
    ) -> bool: ...

    def verify_withdrawal(
        self, pack_ref: PriorPackRef, authorization_ref: str
    ) -> bool: ...


class DeterministicTestOnlySigner:
    """Deterministic fixture signer with no production interpretation."""

    __slots__ = ("_key_ref", "_secret")

    def __init__(self, key_ref: str, fixture_secret: bytes) -> None:
        validate_canonical_identifier(key_ref, "key_ref")
        if type(fixture_secret) is not bytes or not fixture_secret:
            raise ValueError("fixture secret must be nonempty exact bytes")
        self._key_ref = key_ref
        self._secret = bytes(fixture_secret)

    def sign(self, payload: bytes) -> SignatureEnvelope:
        if type(payload) is not bytes:
            raise TypeError("fixture signer accepts exact bytes")
        signature = hashlib.sha256(
            b"carbon.test-only-prior-signature.v1\x00" + self._secret + payload
        ).digest()
        return SignatureEnvelope(self._key_ref, signature)

    def verify(self, payload: bytes, envelope: SignatureEnvelope) -> bool:
        return type(envelope) is SignatureEnvelope and envelope == self.sign(payload)


@dataclass(frozen=True, slots=True)
class SignedTestOnlyAuthorization:
    authorization_id: str
    receipt: TestOnlyPriorAuthorizationReceipt
    receipt_ref: TestOnlyPriorAuthorizationReceiptRef
    signature: SignatureEnvelope

    def __post_init__(self) -> None:
        if self.receipt.to_ref(self.authorization_id) != self.receipt_ref:
            raise ValueError("fixture authorization ref does not bind receipt")


@dataclass(frozen=True, slots=True)
class SignedPublicPublication:
    receipt: PriorPublicationReceipt
    receipt_ref: PriorPublicationReceiptRef
    signature: SignatureEnvelope

    def __post_init__(self) -> None:
        if self.receipt.to_ref() != self.receipt_ref:
            raise ValueError("public receipt ref does not bind receipt")


def _validate_digest(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError("digest must be canonical tagged SHA-256")
    return value


def _primitive(value: object) -> object:
    if value is None or type(value) in (str, int, float, bool):
        return value
    if type(value) is bytes:
        return {"bytes": value.hex()}
    if isinstance(value, Enum):
        return {"enum": type(value).__name__, "value": value.value}
    if type(value) is tuple:
        return [_primitive(item) for item in value]
    if is_dataclass(value):
        return {
            "type": type(value).__name__,
            "fields": {
                field.name: _primitive(getattr(value, field.name))
                for field in fields(value)
            },
        }
    raise TypeError(f"unsupported internal canonical value: {type(value).__name__}")


def _canonical_internal(value: object) -> bytes:
    return json.dumps(
        _primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _tagged_digest(domain: bytes, value: object) -> str:
    payload = value if type(value) is bytes else _canonical_internal(value)
    return "sha256:" + hashlib.sha256(domain + payload).hexdigest()


def _ref_payload(ref: PriorPackRef) -> str:
    return json.dumps(
        {
            "challenge_id": ref.challenge_key.challenge_id,
            "challenge_version": ref.challenge_key.version,
            "channel": ref.channel.value,
            "publication_sequence": ref.publication_sequence,
            "content_hash": ref.content_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _load_pack_ref(payload: str) -> PriorPackRef:
    value = json.loads(payload)
    return PriorPackRef(
        ChallengeKey(value["challenge_id"], value["challenge_version"]),
        PriorChannel(value["channel"]),
        value["publication_sequence"],
        value["content_hash"],
    )


class PriorPackStore:
    """SQLite-backed immutable pack/history store with atomic snapshot heads."""

    __slots__ = ("_lock", "_path", "_public_verifier", "_registry")

    def __init__(
        self,
        path: str | Path,
        validation_registry: PriorValidationRegistry,
        *,
        public_verifier: PublicReceiptVerifier | None = None,
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._registry = validation_registry
        self._public_verifier = public_verifier
        self._lock = threading.RLock()
        self._initialize()

    @property
    def database_path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30.0, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS prior_packs (
                    content_hash TEXT PRIMARY KEY,
                    challenge_id TEXT NOT NULL,
                    challenge_version TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    publication_sequence TEXT NOT NULL,
                    publication_class TEXT NOT NULL,
                    predecessor_hash TEXT,
                    payload BLOB NOT NULL,
                    lifecycle TEXT NOT NULL,
                    authorization_kind TEXT,
                    authorization_digest TEXT,
                    authorizing_snapshot_digest TEXT,
                    UNIQUE(challenge_id, challenge_version, channel, publication_sequence)
                );
                CREATE TABLE IF NOT EXISTS prior_snapshots (
                    content_digest TEXT PRIMARY KEY,
                    challenge_id TEXT NOT NULL,
                    challenge_version TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    index_sequence TEXT NOT NULL,
                    previous_digest TEXT,
                    active_pack_hash TEXT,
                    authorization_kind TEXT NOT NULL,
                    authorization_digest TEXT NOT NULL,
                    history_json TEXT NOT NULL,
                    transition_digest TEXT NOT NULL,
                    UNIQUE(challenge_id, challenge_version, channel, index_sequence)
                );
                CREATE TABLE IF NOT EXISTS prior_heads (
                    challenge_id TEXT NOT NULL,
                    challenge_version TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    snapshot_digest TEXT NOT NULL,
                    PRIMARY KEY(challenge_id, challenge_version, channel)
                );
                CREATE TABLE IF NOT EXISTS fixture_authorizations (
                    content_digest TEXT PRIMARY KEY,
                    authorization_id TEXT NOT NULL UNIQUE,
                    pack_hash TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    signature_key_ref TEXT NOT NULL,
                    signature BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS public_publications (
                    content_digest TEXT PRIMARY KEY,
                    pack_hash TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    signature_key_ref TEXT NOT NULL,
                    signature BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS prior_withdrawals (
                    pack_hash TEXT PRIMARY KEY,
                    authorization_ref TEXT NOT NULL,
                    withdrawal_snapshot_digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS disclosure_ledger_state (
                    ledger_key TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    state_digest TEXT NOT NULL,
                    state_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS disclosure_ledger_entries (
                    release_hash TEXT PRIMARY KEY,
                    ledger_key TEXT NOT NULL,
                    previous_digest TEXT NOT NULL,
                    committed_digest TEXT NOT NULL,
                    delta_json TEXT NOT NULL
                );
                """)

    def store_pack(
        self, pack: PriorPack, claimed_ref: PriorPackRef | None = None
    ) -> PriorPackRef:
        validate_prior_pack(pack, self._registry)
        ref = prior_pack_ref(pack)
        if claimed_ref is not None and claimed_ref != ref:
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
        payload = canonical_bytes(pack)
        if ref.content_hash.encode("ascii") in payload:
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
        predecessor = pack.predecessor_pack_ref
        if predecessor is not None and (
            predecessor.challenge_key != pack.challenge_key
            or predecessor.channel is not pack.channel
            or predecessor.publication_sequence >= pack.publication_sequence
            or predecessor.content_hash == ref.content_hash
        ):
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._validate_predecessor(connection, ref, predecessor)
                row = connection.execute(
                    "SELECT payload FROM prior_packs WHERE content_hash = ?",
                    (ref.content_hash,),
                ).fetchone()
                if row is not None:
                    if bytes(row[0]) != payload:
                        raise PriorStoreError(
                            ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID
                        )
                    connection.commit()
                    return ref
                connection.execute(
                    """INSERT INTO prior_packs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)""",
                    (
                        ref.content_hash,
                        ref.challenge_key.challenge_id,
                        ref.challenge_key.version,
                        ref.channel.value,
                        str(ref.publication_sequence),
                        pack.publication_class.value,
                        predecessor.content_hash if predecessor else None,
                        payload,
                        PriorLifecycle.STORED.value,
                    ),
                )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return ref

    def _validate_predecessor(
        self,
        connection: sqlite3.Connection,
        ref: PriorPackRef,
        predecessor: PriorPackRef | None,
    ) -> None:
        if predecessor is None:
            if ref.publication_sequence != 0:
                raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
            return
        row = connection.execute(
            "SELECT predecessor_hash FROM prior_packs WHERE content_hash = ?",
            (predecessor.content_hash,),
        ).fetchone()
        if row is None:
            raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
        seen = {ref.content_hash}
        current = predecessor.content_hash
        while current is not None:
            if current in seen:
                raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
            seen.add(current)
            found = connection.execute(
                "SELECT predecessor_hash FROM prior_packs WHERE content_hash = ?",
                (current,),
            ).fetchone()
            if found is None:
                raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
            current = found[0]

    def read_pack(self, ref: PriorPackRef, *, audit: bool = False) -> PriorPack:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload, lifecycle FROM prior_packs WHERE content_hash = ?",
                (ref.content_hash,),
            ).fetchone()
        if row is None or (row[1] == PriorLifecycle.WITHDRAWN.value and not audit):
            raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
        pack = load_canonical(bytes(row[0]), PriorPack)
        if prior_pack_ref(pack) != ref:
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
        validate_prior_pack(pack, self._registry)
        return pack

    def read_pack_bytes(self, ref: PriorPackRef, *, audit: bool = False) -> bytes:
        pack = self.read_pack(ref, audit=audit)
        return canonical_bytes(pack)

    def lifecycle(self, ref: PriorPackRef) -> PriorLifecycle:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT lifecycle FROM prior_packs WHERE content_hash = ?",
                (ref.content_hash,),
            ).fetchone()
        if row is None:
            raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
        return PriorLifecycle(row[0])

    def current_snapshot_ref(
        self, challenge_key: ChallengeKey, channel: PriorChannel
    ) -> PriorIndexSnapshotRef | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT h.snapshot_digest, s.index_sequence
                   FROM prior_heads h JOIN prior_snapshots s
                   ON s.content_digest = h.snapshot_digest
                   WHERE h.challenge_id = ? AND h.challenge_version = ? AND h.channel = ?""",
                (challenge_key.challenge_id, challenge_key.version, channel.value),
            ).fetchone()
        if row is None:
            return None
        return PriorIndexSnapshotRef(
            challenge_key, channel, int(row[1]), content_digest=row[0]
        )

    def read_snapshot(self, ref: PriorIndexSnapshotRef) -> PriorIndexSnapshot:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT previous_digest, active_pack_hash, authorization_kind,
                          authorization_digest, history_json, transition_digest,
                          index_sequence, challenge_id, challenge_version, channel
                   FROM prior_snapshots WHERE content_digest = ?""",
                (ref.content_digest,),
            ).fetchone()
        if row is None:
            raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
        if (
            int(row[6]) != ref.index_sequence
            or row[7] != ref.challenge_key.challenge_id
            or row[8] != ref.challenge_key.version
            or row[9] != ref.channel.value
        ):
            raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        previous: PriorPreviousIndex
        if row[0] is None:
            previous = PriorPreviousIndexGenesis()
        else:
            previous_row = self._snapshot_identity(row[0])
            previous = PriorPreviousIndexSnapshot(previous_row)
        history = tuple(_load_pack_ref(item) for item in json.loads(row[4]))
        active = next((item for item in history if item.content_hash == row[1]), None)
        if row[1] is not None and active is None:
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
        if row[2] == "PUBLIC":
            authorization = PublicPriorAuthorization(
                PriorPublicationReceiptRef(
                    ref.challenge_key,
                    ref.channel,
                    (
                        active.publication_sequence
                        if active
                        else history[-1].publication_sequence
                    ),
                    content_digest=row[3],
                )
            )
        else:
            auth_row = self._fixture_authorization_identity(row[3])
            authorization = FixturePriorAuthorization(auth_row)
        snapshot = PriorIndexSnapshot(
            "2.0",
            ref.challenge_key,
            ref.channel,
            ref.index_sequence,
            previous,
            active,
            authorization,
            history,
            row[5],
        )
        if self._snapshot_ref(snapshot) != ref:
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
        return snapshot

    def _snapshot_identity(self, digest: str) -> PriorIndexSnapshotRef:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT challenge_id, challenge_version, channel, index_sequence
                   FROM prior_snapshots WHERE content_digest = ?""",
                (digest,),
            ).fetchone()
        if row is None:
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
        return PriorIndexSnapshotRef(
            ChallengeKey(row[0], row[1]),
            PriorChannel(row[2]),
            int(row[3]),
            content_digest=digest,
        )

    def _fixture_authorization_identity(
        self, digest: str
    ) -> TestOnlyPriorAuthorizationReceiptRef:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT authorization_id, receipt_json FROM fixture_authorizations
                   WHERE content_digest = ?""",
                (digest,),
            ).fetchone()
        if row is None:
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        receipt = json.loads(row[1])
        return TestOnlyPriorAuthorizationReceiptRef(
            ChallengeKey(receipt["challenge_id"], receipt["challenge_version"]),
            row[0],
            digest,
        )

    def fixture_authorization(
        self, ref: TestOnlyPriorAuthorizationReceiptRef
    ) -> TestOnlyPriorAuthorizationReceipt:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT receipt_json FROM fixture_authorizations WHERE content_digest = ?",
                (ref.content_digest,),
            ).fetchone()
        if row is None:
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        value = json.loads(row[0])
        receipt = TestOnlyPriorAuthorizationReceipt(
            ChallengeKey(value["challenge_id"], value["challenge_version"]),
            _load_pack_ref(value["pack_ref"]),
            value["fixture_suite_id"],
            value["expires_at_micros"],
        )
        if receipt.to_ref(ref.authorization_id) != ref:
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        return receipt

    def initialize_disclosure_ledger(self, ledger_key: str) -> str:
        """Create an explicit empty persistent ledger, or verify its identity."""

        validate_canonical_identifier(ledger_key, "ledger_key")
        state_json = '{"dimensions":{},"related_releases":[],"revision":0}'
        digest = _tagged_digest(
            b"carbon.prior-disclosure-ledger.v1\x00", state_json.encode()
        )
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT revision, state_digest, state_json FROM disclosure_ledger_state WHERE ledger_key = ?",
                    (ledger_key,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO disclosure_ledger_state VALUES (?, 0, ?, ?)",
                        (ledger_key, digest, state_json),
                    )
                else:
                    observed_json = row[2]
                    observed_digest = _tagged_digest(
                        b"carbon.prior-disclosure-ledger.v1\x00",
                        observed_json.encode("utf-8"),
                    )
                    try:
                        observed_state = json.loads(observed_json)
                    except (TypeError, ValueError):
                        raise PriorStoreError(
                            ResearchServiceErrorCode.DISCLOSURE_REJECTED
                        ) from None
                    if (
                        row[1] != observed_digest
                        or observed_state.get("revision") != row[0]
                    ):
                        raise PriorStoreError(
                            ResearchServiceErrorCode.DISCLOSURE_REJECTED
                        )
                    digest = row[1]
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return digest

    def disclosure_ledger_state(self, ledger_key: str) -> tuple[int, str, str]:
        validate_canonical_identifier(ledger_key, "ledger_key")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT revision, state_digest, state_json FROM disclosure_ledger_state WHERE ledger_key = ?",
                (ledger_key,),
            ).fetchone()
        if row is None:
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        revision, digest, state_json = row
        if (
            _tagged_digest(
                b"carbon.prior-disclosure-ledger.v1\x00", state_json.encode("utf-8")
            )
            != digest
        ):
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        try:
            state = json.loads(state_json)
        except (TypeError, ValueError):
            raise PriorStoreError(
                ResearchServiceErrorCode.DISCLOSURE_REJECTED
            ) from None
        if state.get("revision") != revision:
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        return revision, digest, state_json

    def commit_fixture_release(
        self,
        signed: SignedTestOnlyAuthorization,
        signer: DeterministicTestOnlySigner,
        *,
        ledger_key: str,
        expected_ledger_digest: str,
        next_ledger_state_json: str,
        ledger_delta_json: str,
        expected_previous: PriorIndexSnapshotRef | None,
    ) -> PriorIndexSnapshotRef:
        """Atomically append disclosure state, receipt, and fixture snapshot."""

        receipt = signed.receipt
        ref = receipt.prior_pack_ref
        if not signer.verify(_canonical_internal(receipt), signed.signature):
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        if signed.receipt_ref != receipt.to_ref(signed.authorization_id):
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        if ref.channel is not PriorChannel.TEST_ONLY_FIXTURE:
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        try:
            next_state = json.loads(next_ledger_state_json)
            delta = json.loads(ledger_delta_json)
        except (TypeError, ValueError):
            raise PriorStoreError(
                ResearchServiceErrorCode.DISCLOSURE_REJECTED
            ) from None
        if type(next_state) is not dict or type(delta) is not dict:
            raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        next_json = json.dumps(next_state, sort_keys=True, separators=(",", ":"))
        delta_json = json.dumps(delta, sort_keys=True, separators=(",", ":"))
        next_digest = _tagged_digest(
            b"carbon.prior-disclosure-ledger.v1\x00", next_json.encode("utf-8")
        )
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                pack_row = connection.execute(
                    "SELECT publication_class, lifecycle FROM prior_packs WHERE content_hash = ?",
                    (ref.content_hash,),
                ).fetchone()
                if pack_row != (
                    PriorPublicationClass.TEST_ONLY.value,
                    PriorLifecycle.STORED.value,
                ):
                    raise PriorStoreError(
                        ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID
                    )
                ledger = connection.execute(
                    "SELECT revision, state_digest, state_json FROM disclosure_ledger_state WHERE ledger_key = ?",
                    (ledger_key,),
                ).fetchone()
                if ledger is None or ledger[1] != expected_ledger_digest:
                    raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
                try:
                    prior_state = json.loads(ledger[2])
                except (TypeError, ValueError):
                    raise PriorStoreError(
                        ResearchServiceErrorCode.DISCLOSURE_REJECTED
                    ) from None
                if (
                    prior_state.get("revision") != ledger[0]
                    or next_state.get("revision") != ledger[0] + 1
                ):
                    raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
                current = self._head_row(connection, ref.challenge_key, ref.channel)
                self._require_expected_head(current, expected_previous)
                history, index_sequence, previous = self._next_history(
                    connection, current, ref
                )
                connection.execute(
                    "INSERT INTO fixture_authorizations VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        signed.receipt_ref.content_digest,
                        signed.authorization_id,
                        ref.content_hash,
                        _fixture_receipt_json(receipt),
                        signed.signature.key_ref,
                        signed.signature.signature,
                    ),
                )
                transition = self._transition_digest(
                    ref.challenge_key,
                    ref.channel,
                    index_sequence,
                    previous,
                    ref,
                    history,
                )
                snapshot = PriorIndexSnapshot(
                    "2.0",
                    ref.challenge_key,
                    ref.channel,
                    index_sequence,
                    previous,
                    ref,
                    FixturePriorAuthorization(signed.receipt_ref),
                    history,
                    transition,
                )
                snapshot_ref = self._insert_snapshot(connection, snapshot)
                self._activate_pack(
                    connection,
                    ref,
                    signed.receipt_ref.content_digest,
                    snapshot_ref,
                    fixture=True,
                )
                connection.execute(
                    "INSERT INTO disclosure_ledger_entries VALUES (?, ?, ?, ?, ?)",
                    (
                        ref.content_hash,
                        ledger_key,
                        expected_ledger_digest,
                        next_digest,
                        delta_json,
                    ),
                )
                result = connection.execute(
                    "UPDATE disclosure_ledger_state SET revision = ?, state_digest = ?, state_json = ? WHERE ledger_key = ? AND state_digest = ?",
                    (
                        ledger[0] + 1,
                        next_digest,
                        next_json,
                        ledger_key,
                        expected_ledger_digest,
                    ),
                )
                if result.rowcount != 1:
                    raise PriorStoreError(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
                connection.commit()
                return snapshot_ref
            except BaseException:
                connection.rollback()
                raise

    def import_public_release(
        self,
        pack: PriorPack,
        signed: SignedPublicPublication,
        *,
        expected_previous: PriorIndexSnapshotRef | None,
    ) -> PriorIndexSnapshotRef:
        """Import an already-authorized public artifact through an injected verifier."""

        if (
            self._public_verifier is None
            or not self._public_verifier.verify_publication(
                signed.receipt, signed.signature
            )
        ):
            raise PriorStoreError(ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE)
        ref = self.store_pack(pack)
        receipt = signed.receipt
        if (
            pack.publication_class is PriorPublicationClass.TEST_ONLY
            or ref != receipt.prior_pack_ref
            or receipt.prior_policy_bundle_ref != pack.prior_policy_bundle_ref
            or receipt.activation_epoch != pack.activation_epoch
            or receipt.disclosure_ledger_expected_digest
            != receipt.disclosure_ledger_committed_digest
        ):
            raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = self._head_row(connection, pack.challenge_key, pack.channel)
                self._require_expected_head(current, expected_previous)
                history, index_sequence, previous = self._next_history(
                    connection, current, ref
                )
                if receipt.previous_index != previous:
                    raise PriorStoreError(
                        ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID
                    )
                transition = self._transition_digest(
                    ref.challenge_key,
                    ref.channel,
                    index_sequence,
                    previous,
                    ref,
                    history,
                )
                if transition != receipt.proposed_transition_digest:
                    raise PriorStoreError(
                        ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID
                    )
                connection.execute(
                    "INSERT INTO public_publications VALUES (?, ?, ?, ?, ?)",
                    (
                        signed.receipt_ref.content_digest,
                        ref.content_hash,
                        _public_receipt_json(receipt),
                        signed.signature.key_ref,
                        signed.signature.signature,
                    ),
                )
                snapshot = PriorIndexSnapshot(
                    "2.0",
                    ref.challenge_key,
                    ref.channel,
                    index_sequence,
                    previous,
                    ref,
                    PublicPriorAuthorization(signed.receipt_ref),
                    history,
                    transition,
                )
                snapshot_ref = self._insert_snapshot(connection, snapshot)
                self._activate_pack(
                    connection, ref, signed.receipt_ref.content_digest, snapshot_ref
                )
                connection.commit()
                return snapshot_ref
            except BaseException:
                connection.rollback()
                raise

    def withdraw_public(
        self,
        ref: PriorPackRef,
        *,
        authorization_ref: str,
        expected_previous: PriorIndexSnapshotRef,
    ) -> PriorIndexSnapshotRef:
        if (
            self._public_verifier is None
            or not self._public_verifier.verify_withdrawal(ref, authorization_ref)
        ):
            raise PriorStoreError(ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE)
        validate_canonical_identifier(authorization_ref, "withdrawal authorization")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = self._head_row(connection, ref.challenge_key, ref.channel)
                self._require_expected_head(current, expected_previous)
                snapshot = self.read_snapshot(expected_previous)
                if snapshot.active_prior_pack_ref != ref:
                    raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
                sequence = snapshot.index_sequence + 1
                previous = PriorPreviousIndexSnapshot(expected_previous)
                transition = self._transition_digest(
                    ref.challenge_key,
                    ref.channel,
                    sequence,
                    previous,
                    None,
                    snapshot.historical_prior_pack_refs,
                )
                # Withdrawal keeps the previous publication receipt as historical
                # authorization; the separate withdrawal record supplies audit proof.
                withdrawn = PriorIndexSnapshot(
                    "2.0",
                    ref.challenge_key,
                    ref.channel,
                    sequence,
                    previous,
                    None,
                    snapshot.index_authorization,
                    snapshot.historical_prior_pack_refs,
                    transition,
                )
                snapshot_ref = self._insert_snapshot(connection, withdrawn)
                connection.execute(
                    "UPDATE prior_packs SET lifecycle = ? WHERE content_hash = ?",
                    (PriorLifecycle.WITHDRAWN.value, ref.content_hash),
                )
                connection.execute(
                    "INSERT INTO prior_withdrawals VALUES (?, ?, ?)",
                    (ref.content_hash, authorization_ref, snapshot_ref.content_digest),
                )
                connection.commit()
                return snapshot_ref
            except BaseException:
                connection.rollback()
                raise

    def _head_row(
        self, connection: sqlite3.Connection, key: ChallengeKey, channel: PriorChannel
    ) -> tuple[str, int] | None:
        row = connection.execute(
            """SELECT h.snapshot_digest, s.index_sequence FROM prior_heads h
               JOIN prior_snapshots s ON s.content_digest = h.snapshot_digest
               WHERE h.challenge_id = ? AND h.challenge_version = ? AND h.channel = ?""",
            (key.challenge_id, key.version, channel.value),
        ).fetchone()
        return None if row is None else (row[0], int(row[1]))

    @staticmethod
    def _require_expected_head(
        current: tuple[str, int] | None, expected: PriorIndexSnapshotRef | None
    ) -> None:
        observed = current[0] if current else None
        wanted = expected.content_digest if expected else None
        if observed != wanted:
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_INDEX_CHANGED)

    def _next_history(
        self,
        connection: sqlite3.Connection,
        current: tuple[str, int] | None,
        ref: PriorPackRef,
    ) -> tuple[tuple[PriorPackRef, ...], int, PriorPreviousIndex]:
        if current is None:
            if ref.publication_sequence != 0:
                raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
            return (ref,), 0, PriorPreviousIndexGenesis()
        previous_ref = self._snapshot_identity(current[0])
        previous = self.read_snapshot(previous_ref)
        stored = connection.execute(
            "SELECT predecessor_hash FROM prior_packs WHERE content_hash = ?",
            (ref.content_hash,),
        ).fetchone()
        expected_predecessor = previous.historical_prior_pack_refs[-1]
        if (
            stored is None
            or stored[0] != expected_predecessor.content_hash
            or ref.publication_sequence != expected_predecessor.publication_sequence + 1
            or ref not in previous.historical_prior_pack_refs
            and ref.content_hash
            in {item.content_hash for item in previous.historical_prior_pack_refs}
        ):
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
        return (
            (*previous.historical_prior_pack_refs, ref),
            current[1] + 1,
            PriorPreviousIndexSnapshot(previous_ref),
        )

    @staticmethod
    def _transition_digest(
        key: ChallengeKey,
        channel: PriorChannel,
        sequence: int,
        previous: PriorPreviousIndex,
        active: PriorPackRef | None,
        history: tuple[PriorPackRef, ...],
    ) -> str:
        preimage = (key, channel, sequence, previous, active, history)
        return _tagged_digest(_TRANSITION_DOMAIN, preimage)

    @staticmethod
    def _snapshot_ref(snapshot: PriorIndexSnapshot) -> PriorIndexSnapshotRef:
        return PriorIndexSnapshotRef(
            snapshot.challenge_key,
            snapshot.channel,
            snapshot.index_sequence,
            content_digest=_tagged_digest(_INDEX_DOMAIN, snapshot),
        )

    def _insert_snapshot(
        self, connection: sqlite3.Connection, snapshot: PriorIndexSnapshot
    ) -> PriorIndexSnapshotRef:
        snapshot_ref = self._snapshot_ref(snapshot)
        previous_digest = (
            snapshot.previous_index.previous_index_snapshot_ref.content_digest
            if type(snapshot.previous_index) is PriorPreviousIndexSnapshot
            else None
        )
        authorization = snapshot.index_authorization.receipt_ref
        kind = (
            "PUBLIC"
            if type(snapshot.index_authorization) is PublicPriorAuthorization
            else "FIXTURE"
        )
        history_json = json.dumps(
            [_ref_payload(item) for item in snapshot.historical_prior_pack_refs],
            separators=(",", ":"),
        )
        connection.execute(
            """INSERT INTO prior_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_ref.content_digest,
                snapshot.challenge_key.challenge_id,
                snapshot.challenge_key.version,
                snapshot.channel.value,
                str(snapshot.index_sequence),
                previous_digest,
                (
                    snapshot.active_prior_pack_ref.content_hash
                    if snapshot.active_prior_pack_ref
                    else None
                ),
                kind,
                authorization.content_digest,
                history_json,
                snapshot.transition_digest,
            ),
        )
        connection.execute(
            """INSERT INTO prior_heads VALUES (?, ?, ?, ?)
               ON CONFLICT(challenge_id, challenge_version, channel)
               DO UPDATE SET snapshot_digest = excluded.snapshot_digest""",
            (
                snapshot.challenge_key.challenge_id,
                snapshot.challenge_key.version,
                snapshot.channel.value,
                snapshot_ref.content_digest,
            ),
        )
        return snapshot_ref

    @staticmethod
    def _activate_pack(
        connection: sqlite3.Connection,
        ref: PriorPackRef,
        authorization_digest: str,
        snapshot_ref: PriorIndexSnapshotRef,
        *,
        fixture: bool = False,
    ) -> None:
        connection.execute(
            """UPDATE prior_packs SET lifecycle = ?
               WHERE challenge_id = ? AND challenge_version = ? AND channel = ?
               AND lifecycle = ?""",
            (
                PriorLifecycle.SUPERSEDED.value,
                ref.challenge_key.challenge_id,
                ref.challenge_key.version,
                ref.channel.value,
                PriorLifecycle.ACTIVE.value,
            ),
        )
        result = connection.execute(
            """UPDATE prior_packs SET lifecycle = ?, authorization_kind = ?,
                      authorization_digest = ?, authorizing_snapshot_digest = ?
               WHERE content_hash = ? AND lifecycle = ?""",
            (
                PriorLifecycle.ACTIVE.value,
                "FIXTURE" if fixture else "PUBLIC",
                authorization_digest,
                snapshot_ref.content_digest,
                ref.content_hash,
                PriorLifecycle.STORED.value,
            ),
        )
        if result.rowcount != 1:
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)

    def authorization_for(
        self, ref: PriorPackRef
    ) -> tuple[
        PriorIndexSnapshotRef, PublicPriorAuthorization | FixturePriorAuthorization
    ]:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT authorization_kind, authorization_digest,
                          authorizing_snapshot_digest
                   FROM prior_packs WHERE content_hash = ?""",
                (ref.content_hash,),
            ).fetchone()
        if row is None or row[0] is None or row[2] is None:
            raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
        snapshot_ref = self._snapshot_identity(row[2])
        snapshot = self.read_snapshot(snapshot_ref)
        if ref not in snapshot.historical_prior_pack_refs:
            raise PriorStoreError(ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID)
        if row[0] == "FIXTURE":
            with self._connect() as connection:
                fixture_row = connection.execute(
                    "SELECT pack_hash FROM fixture_authorizations WHERE content_digest = ?",
                    (row[1],),
                ).fetchone()
                ledger_row = connection.execute(
                    "SELECT ledger_key FROM disclosure_ledger_entries WHERE release_hash = ?",
                    (ref.content_hash,),
                ).fetchone()
            if fixture_row != (ref.content_hash,) or ledger_row is None:
                raise PriorStoreError(
                    ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID
                )
            self.disclosure_ledger_state(ledger_row[0])
            authorization = FixturePriorAuthorization(
                self._fixture_authorization_identity(row[1])
            )
        else:
            with self._connect() as connection:
                publication = connection.execute(
                    "SELECT pack_hash FROM public_publications WHERE content_digest = ?",
                    (row[1],),
                ).fetchone()
            if publication != (ref.content_hash,):
                raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
            authorization = PublicPriorAuthorization(
                PriorPublicationReceiptRef(
                    ref.challenge_key,
                    ref.channel,
                    ref.publication_sequence,
                    content_digest=row[1],
                )
            )
        return snapshot_ref, authorization


def _public_receipt_json(receipt: PriorPublicationReceipt) -> str:
    return json.dumps(_primitive(receipt), sort_keys=True, separators=(",", ":"))


def _fixture_receipt_json(receipt: TestOnlyPriorAuthorizationReceipt) -> str:
    return json.dumps(
        {
            "challenge_id": receipt.challenge_key.challenge_id,
            "challenge_version": receipt.challenge_key.version,
            "pack_ref": _ref_payload(receipt.prior_pack_ref),
            "fixture_suite_id": receipt.fixture_suite_id,
            "expires_at_micros": receipt.expires_at_micros,
            "authority_ceiling": receipt.authority_ceiling,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


__all__ = (
    "DeterministicTestOnlySigner",
    "PriorIndexSnapshot",
    "PriorLifecycle",
    "PriorPackStore",
    "PriorPreviousIndex",
    "PriorPreviousIndexGenesis",
    "PriorPreviousIndexSnapshot",
    "PriorPublicationReceipt",
    "PriorStoreError",
    "PriorValidationRegistry",
    "ProductionPriorSigner",
    "PublicEstimandDefinition",
    "PublicReceiptVerifier",
    "PublicSearchScopeDefinition",
    "SignatureEnvelope",
    "SignedPublicPublication",
    "SignedTestOnlyAuthorization",
    "TestOnlyPriorAuthorizationReceipt",
    "prior_pack_ref",
    "validate_prior_pack",
)
