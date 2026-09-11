"""C-EA1 journal, PostgreSQL catalogue, encryption, and object-store adapters."""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .model import (
    AEAD_ALGORITHM,
    ArchiveCode,
    ArchiveFailure,
    ArtifactRecord,
    ArtifactState,
    canonical_bytes,
    content_digest,
    validate_artifact_name,
    validate_digest,
    validate_token,
)

CATALOGUE_SCHEMA_VERSION = "carbon.evidence-archive.postgresql.v1"
JOURNAL_SCHEMA_VERSION = "carbon.evidence-archive.journal.v1"
POSTGRES_IMAGE = (
    "postgres:17.11-bookworm@"
    "sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0"
)

MIGRATION_001 = """
CREATE TABLE IF NOT EXISTS cea1_schema_meta (
  singleton smallint PRIMARY KEY CHECK (singleton = 1),
  schema_version text NOT NULL,
  migration_checksum text NOT NULL
);
CREATE TABLE IF NOT EXISTS cea1_admission (
  archive_entry_id text PRIMARY KEY,
  tenant_id text NOT NULL,
  binding_json text NOT NULL,
  binding_digest text NOT NULL,
  reserved_objects bigint NOT NULL CHECK (reserved_objects > 0),
  reserved_bytes bigint NOT NULL CHECK (reserved_bytes > 0),
  active boolean NOT NULL DEFAULT true,
  finalized boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS cea1_entry (
  archive_entry_id text PRIMARY KEY REFERENCES cea1_admission(archive_entry_id),
  capture_profile_digest text NOT NULL,
  manifest_identity text NOT NULL UNIQUE,
  entry_json text NOT NULL,
  entry_digest text NOT NULL
);
CREATE TABLE IF NOT EXISTS cea1_artifact (
  archive_entry_id text NOT NULL REFERENCES cea1_entry(archive_entry_id),
  artifact_name text NOT NULL,
  artifact_json text NOT NULL,
  artifact_digest text NOT NULL,
  object_key text,
  PRIMARY KEY (archive_entry_id, artifact_name),
  UNIQUE (object_key)
);
CREATE TABLE IF NOT EXISTS cea1_event (
  sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  archive_entry_id text NOT NULL,
  event_kind text NOT NULL,
  event_json text NOT NULL,
  event_digest text NOT NULL
);
CREATE TABLE IF NOT EXISTS cea1_outbox (
  event_id text PRIMARY KEY,
  archive_entry_id text NOT NULL,
  event_kind text NOT NULL,
  payload_json text NOT NULL,
  payload_digest text NOT NULL
);
CREATE TABLE IF NOT EXISTS cea1_consumer_effect (
  consumer_id text NOT NULL,
  event_id text NOT NULL REFERENCES cea1_outbox(event_id),
  effect_digest text NOT NULL,
  PRIMARY KEY (consumer_id, event_id)
);
CREATE TABLE IF NOT EXISTS cea1_acknowledgement (
  acknowledgement_ref text PRIMARY KEY,
  archive_entry_id text NOT NULL REFERENCES cea1_entry(archive_entry_id),
  acknowledgement_json text NOT NULL,
  acknowledgement_digest text NOT NULL
);
CREATE TABLE IF NOT EXISTS cea1_artifact_availability (
  sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  archive_entry_id text NOT NULL REFERENCES cea1_entry(archive_entry_id),
  artifact_name text NOT NULL,
  availability_state text NOT NULL,
  reason_ref text NOT NULL,
  event_digest text NOT NULL
);
CREATE TABLE IF NOT EXISTS cea1_orphan (
  object_key text PRIMARY KEY,
  quarantine_ref text NOT NULL,
  observed_digest text NOT NULL
);
""".strip()
MIGRATION_001_CHECKSUM = content_digest(
    "carbon.evidence-archive.migration.v1", MIGRATION_001.encode("utf-8")
)


@dataclass(frozen=True, slots=True)
class CapacityLimits:
    max_active_entries: int = 8
    max_objects: int = 64
    max_bytes: int = 2 * 1024 * 1024
    max_spool_bytes: int = 3 * 1024 * 1024

    def __post_init__(self) -> None:
        values = (
            self.max_active_entries,
            self.max_objects,
            self.max_bytes,
            self.max_spool_bytes,
        )
        if any(type(value) is not int or value < 1 for value in values):
            raise ArchiveFailure(ArchiveCode.INVALID)


@dataclass(frozen=True, slots=True, repr=False)
class KeyMaterial:
    key_id: str
    key_bytes: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "key_id", validate_token(self.key_id))
        if type(self.key_bytes) is not bytes or len(self.key_bytes) != 32:
            raise ArchiveFailure(ArchiveCode.INVALID)


@dataclass(frozen=True, slots=True)
class EncryptedEnvelope:
    key_id: str
    algorithm: str
    nonce_hex: str
    ciphertext: bytes


class ObjectStore(Protocol):
    def put_immutable(self, object_key: str, body: bytes) -> bool: ...

    def get(self, object_key: str) -> bytes: ...

    def list_keys(self, tenant_id: str) -> tuple[str, ...]: ...

    def quarantine(self, object_key: str) -> str: ...


def _associated_data(
    *, entry_id: str, artifact_name: str, plaintext_digest: str, key_id: str
) -> bytes:
    return canonical_bytes(
        {
            "schema_version": "carbon.evidence-archive.aead.v1",
            "archive_entry_id": validate_digest(entry_id),
            "artifact_name": validate_artifact_name(artifact_name),
            "plaintext_digest": validate_digest(plaintext_digest),
            "key_id": validate_token(key_id),
        }
    )


def encrypt_artifact(
    plaintext: bytes,
    *,
    entry_id: str,
    artifact_name: str,
    plaintext_digest: str,
    key: KeyMaterial,
    nonce: bytes | None = None,
) -> EncryptedEnvelope:
    if type(plaintext) is not bytes or not plaintext:
        raise ArchiveFailure(ArchiveCode.INVALID)
    nonce = os.urandom(12) if nonce is None else nonce
    if type(nonce) is not bytes or len(nonce) != 12:
        raise ArchiveFailure(ArchiveCode.INVALID)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        ciphertext = AESGCM(key.key_bytes).encrypt(
            nonce,
            plaintext,
            _associated_data(
                entry_id=entry_id,
                artifact_name=artifact_name,
                plaintext_digest=plaintext_digest,
                key_id=key.key_id,
            ),
        )
    except ArchiveFailure:
        raise
    except Exception:  # noqa: BLE001 - crypto failures share a stable boundary.
        raise ArchiveFailure(ArchiveCode.INTEGRITY) from None
    return EncryptedEnvelope(key.key_id, AEAD_ALGORITHM, nonce.hex(), ciphertext)


def decrypt_artifact(
    envelope: EncryptedEnvelope,
    *,
    entry_id: str,
    artifact_name: str,
    plaintext_digest: str,
    key: KeyMaterial,
) -> bytes:
    if envelope.key_id != key.key_id or envelope.algorithm != AEAD_ALGORITHM:
        raise ArchiveFailure(ArchiveCode.KEY_UNAVAILABLE)
    try:
        nonce = bytes.fromhex(envelope.nonce_hex)
        if len(nonce) != 12:
            raise ValueError
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        plaintext = AESGCM(key.key_bytes).decrypt(
            nonce,
            envelope.ciphertext,
            _associated_data(
                entry_id=entry_id,
                artifact_name=artifact_name,
                plaintext_digest=plaintext_digest,
                key_id=key.key_id,
            ),
        )
    except ArchiveFailure:
        raise
    except Exception:  # noqa: BLE001
        raise ArchiveFailure(ArchiveCode.INTEGRITY) from None
    if content_digest("carbon.evidence-artifact.v1", plaintext) != plaintext_digest:
        raise ArchiveFailure(ArchiveCode.INTEGRITY)
    return plaintext


def derive_object_key(
    tenant_id: str, entry_id: str, artifact_name: str, plaintext_digest: str
) -> str:
    tenant = validate_token(tenant_id)
    entry = validate_digest(entry_id)[7:]
    artifact = validate_artifact_name(artifact_name)
    digest = validate_digest(plaintext_digest)[7:]
    return f"v1/{tenant}/{entry}/{artifact}/{digest}.bin"


def validate_object_key(object_key: object, tenant_id: str) -> str:
    if type(object_key) is not str or len(object_key) > 512:
        raise ArchiveFailure(ArchiveCode.INVALID)
    parts = object_key.split("/")
    if (
        len(parts) != 5
        or parts[0] != "v1"
        or parts[1] != validate_token(tenant_id)
        or not re_full_hex(parts[2])
        or validate_artifact_name(parts[3]) != parts[3]
        or not parts[4].endswith(".bin")
        or not re_full_hex(parts[4][:-4])
    ):
        raise ArchiveFailure(ArchiveCode.DENIED)
    return object_key


def re_full_hex(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


class HttpImmutableObjectStore:
    """Narrow adapter for the disposable C-EA1 local object service."""

    def __init__(self, endpoint: str, tenant_id: str, *, timeout: float = 5.0) -> None:
        parsed = urllib.parse.urlsplit(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ArchiveFailure(ArchiveCode.DENIED)
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ArchiveFailure(ArchiveCode.INVALID)
        self.endpoint = endpoint.rstrip("/")
        self.tenant_id = validate_token(tenant_id)
        self.timeout = timeout

    def _request(self, method: str, path: str, body: bytes | None = None) -> bytes:
        request = urllib.request.Request(
            self.endpoint + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/octet-stream"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                raise ArchiveFailure(ArchiveCode.CONFLICT) from None
            if exc.code in {400, 403, 404, 413}:
                raise ArchiveFailure(ArchiveCode.DENIED) from None
            raise ArchiveFailure(ArchiveCode.STORE) from None
        except (OSError, urllib.error.URLError):
            raise ArchiveFailure(ArchiveCode.STORE) from None

    def put_immutable(self, object_key: str, body: bytes) -> bool:
        validate_object_key(object_key, self.tenant_id)
        if type(body) is not bytes or not body:
            raise ArchiveFailure(ArchiveCode.INVALID)
        result = self._request(
            "PUT", "/objects/" + urllib.parse.quote(object_key, safe="/"), body
        )
        return result == b"created"

    def get(self, object_key: str) -> bytes:
        validate_object_key(object_key, self.tenant_id)
        return self._request(
            "GET", "/objects/" + urllib.parse.quote(object_key, safe="/")
        )

    def list_keys(self, tenant_id: str) -> tuple[str, ...]:
        if validate_token(tenant_id) != self.tenant_id:
            raise ArchiveFailure(ArchiveCode.DENIED)
        raw = self._request(
            "GET", "/inventory/" + urllib.parse.quote(tenant_id, safe="")
        )
        try:
            values = json.loads(raw)
            if type(values) is not list or any(
                type(value) is not str for value in values
            ):
                raise ValueError
            return tuple(validate_object_key(value, self.tenant_id) for value in values)
        except (ValueError, json.JSONDecodeError, ArchiveFailure):
            raise ArchiveFailure(ArchiveCode.INTEGRITY) from None

    def quarantine(self, object_key: str) -> str:
        validate_object_key(object_key, self.tenant_id)
        raw = self._request(
            "POST", "/quarantine/" + urllib.parse.quote(object_key, safe="/")
        )
        return validate_token(raw.decode("ascii"))


class StageJournal:
    """Bounded encrypted local spool retained until archive acknowledgement."""

    def __init__(self, path: Path, limits: CapacityLimits) -> None:
        self.path = Path(path)
        self.limits = limits
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._transaction() as db:
                db.executescript("""
                CREATE TABLE IF NOT EXISTS cea1_journal_meta (
                  singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cea1_journal_admission (
                  archive_entry_id TEXT PRIMARY KEY,
                  admission_json TEXT NOT NULL,
                  admission_digest TEXT NOT NULL,
                  reserved_objects INTEGER NOT NULL,
                  reserved_bytes INTEGER NOT NULL,
                  active INTEGER NOT NULL CHECK(active IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS cea1_journal_artifact (
                  archive_entry_id TEXT NOT NULL,
                  artifact_name TEXT NOT NULL,
                  plaintext_digest TEXT NOT NULL,
                  plaintext_size INTEGER NOT NULL,
                  key_id TEXT NOT NULL,
                  algorithm TEXT NOT NULL,
                  nonce_hex TEXT NOT NULL,
                  ciphertext BLOB NOT NULL,
                  PRIMARY KEY(archive_entry_id, artifact_name)
                );
                CREATE TABLE IF NOT EXISTS cea1_journal_event (
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  archive_entry_id TEXT NOT NULL,
                  event_kind TEXT NOT NULL,
                  event_digest TEXT NOT NULL
                );
                """)
                db.execute(
                    "INSERT OR IGNORE INTO cea1_journal_meta VALUES (1,?)",
                    (JOURNAL_SCHEMA_VERSION,),
                )
                row = db.execute(
                    "SELECT schema_version FROM cea1_journal_meta WHERE singleton=1"
                ).fetchone()
                if row != (JOURNAL_SCHEMA_VERSION,):
                    raise ArchiveFailure(ArchiveCode.STORE)
                for event_kind, event_digest in db.execute(
                    "SELECT event_kind,event_digest FROM cea1_journal_event"
                ):
                    if (
                        content_digest(
                            "carbon.evidence-archive.journal-event.v1",
                            event_kind.encode("ascii"),
                        )
                        != event_digest
                    ):
                        raise ArchiveFailure(ArchiveCode.INTEGRITY)
        except sqlite3.Error:
            raise ArchiveFailure(ArchiveCode.STORE) from None

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db: sqlite3.Connection | None = None
        try:
            db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            if db.in_transaction:
                db.execute("COMMIT")
        except ArchiveFailure:
            if db is not None and db.in_transaction:
                db.execute("ROLLBACK")
            raise
        except sqlite3.Error:
            if db is not None and db.in_transaction:
                db.execute("ROLLBACK")
            raise ArchiveFailure(ArchiveCode.STORE) from None
        finally:
            if db is not None:
                db.close()

    def reserve(
        self, entry_id: str, admission: bytes, objects: int, byte_count: int
    ) -> bool:
        validate_digest(entry_id)
        if (
            type(objects) is not int
            or type(byte_count) is not int
            or objects < 1
            or byte_count < 1
            or objects > self.limits.max_objects
            or byte_count > self.limits.max_bytes
            or byte_count > self.limits.max_spool_bytes
        ):
            raise ArchiveFailure(ArchiveCode.CAPACITY)
        digest = content_digest("carbon.evidence-archive.admission.v1", admission)
        with self._transaction() as db:
            old = db.execute(
                "SELECT admission_digest,reserved_objects,reserved_bytes FROM cea1_journal_admission WHERE archive_entry_id=?",
                (entry_id,),
            ).fetchone()
            if old is not None:
                if old != (digest, objects, byte_count):
                    raise ArchiveFailure(ArchiveCode.CONFLICT)
                return False
            active = db.execute(
                "SELECT count(*),coalesce(sum(reserved_objects),0),coalesce(sum(reserved_bytes),0) FROM cea1_journal_admission WHERE active=1"
            ).fetchone()
            if (
                active[0] + 1 > self.limits.max_active_entries
                or active[1] + objects > self.limits.max_objects
                or active[2] + byte_count > self.limits.max_spool_bytes
            ):
                raise ArchiveFailure(ArchiveCode.CAPACITY)
            db.execute(
                "INSERT INTO cea1_journal_admission VALUES (?,?,?,?,?,1)",
                (entry_id, admission.decode("utf-8"), digest, objects, byte_count),
            )
            self._event(db, entry_id, "ADMITTED")
            return True

    @staticmethod
    def _event(db: sqlite3.Connection, entry_id: str, kind: str) -> None:
        digest = content_digest(
            "carbon.evidence-archive.journal-event.v1", kind.encode("ascii")
        )
        db.execute(
            "INSERT INTO cea1_journal_event(archive_entry_id,event_kind,event_digest) VALUES (?,?,?)",
            (entry_id, kind, digest),
        )

    def put_envelope(
        self,
        entry_id: str,
        artifact_name: str,
        plaintext_digest: str,
        plaintext_size: int,
        envelope: EncryptedEnvelope,
    ) -> bool:
        with self._transaction() as db:
            old = db.execute(
                "SELECT plaintext_digest,plaintext_size,key_id,algorithm,nonce_hex,ciphertext FROM cea1_journal_artifact WHERE archive_entry_id=? AND artifact_name=?",
                (entry_id, artifact_name),
            ).fetchone()
            candidate = (
                plaintext_digest,
                plaintext_size,
                envelope.key_id,
                envelope.algorithm,
                envelope.nonce_hex,
                envelope.ciphertext,
            )
            if old is not None:
                if old != candidate:
                    raise ArchiveFailure(ArchiveCode.CONFLICT)
                return False
            db.execute(
                "INSERT INTO cea1_journal_artifact VALUES (?,?,?,?,?,?,?,?)",
                (entry_id, artifact_name, *candidate),
            )
            self._event(db, entry_id, "ARTIFACT_STAGED")
            return True

    def envelope(
        self, entry_id: str, artifact_name: str
    ) -> tuple[str, int, EncryptedEnvelope] | None:
        with self._transaction() as db:
            row = db.execute(
                "SELECT plaintext_digest,plaintext_size,key_id,algorithm,nonce_hex,ciphertext FROM cea1_journal_artifact WHERE archive_entry_id=? AND artifact_name=?",
                (entry_id, artifact_name),
            ).fetchone()
        if row is None:
            return None
        return row[0], row[1], EncryptedEnvelope(row[2], row[3], row[4], row[5])

    def release(self, entry_id: str) -> None:
        with self._transaction() as db:
            changed = db.execute(
                "UPDATE cea1_journal_admission SET active=0 WHERE archive_entry_id=? AND active=1",
                (entry_id,),
            ).rowcount
            if changed:
                self._event(db, entry_id, "ACKNOWLEDGED_RELEASE")

    def active_count(self) -> int:
        with self._transaction() as db:
            return int(
                db.execute(
                    "SELECT count(*) FROM cea1_journal_admission WHERE active=1"
                ).fetchone()[0]
            )


def _load_psycopg():
    try:
        import psycopg

        return psycopg
    except ImportError:
        raise ArchiveFailure(ArchiveCode.STORE) from None


class PostgresCatalogue:
    """PostgreSQL metadata/outbox owner with exact migration checks."""

    def __init__(self, dsn: str, limits: CapacityLimits) -> None:
        if type(dsn) is not str or not dsn.startswith("postgresql://"):
            raise ArchiveFailure(ArchiveCode.INVALID)
        self.dsn = dsn
        self.limits = limits

    @contextmanager
    def transaction(self):
        psycopg = _load_psycopg()
        try:
            with psycopg.connect(self.dsn) as connection:  # noqa: SIM117
                with connection.transaction():
                    yield connection
        except ArchiveFailure:
            raise
        except Exception:  # noqa: BLE001
            raise ArchiveFailure(ArchiveCode.STORE) from None

    def migrate(self) -> None:
        with self.transaction() as connection:  # noqa: SIM117
            with connection.cursor() as cursor:
                cursor.execute(MIGRATION_001)
                cursor.execute(
                    "INSERT INTO cea1_schema_meta VALUES (1,%s,%s) ON CONFLICT (singleton) DO NOTHING",
                    (CATALOGUE_SCHEMA_VERSION, MIGRATION_001_CHECKSUM),
                )
                cursor.execute(
                    "SELECT schema_version,migration_checksum FROM cea1_schema_meta WHERE singleton=1"
                )
                if cursor.fetchone() != (
                    CATALOGUE_SCHEMA_VERSION,
                    MIGRATION_001_CHECKSUM,
                ):
                    raise ArchiveFailure(ArchiveCode.STORE)
        self.verify_schema()

    def verify_schema(self) -> None:
        with self.transaction() as connection:  # noqa: SIM117
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_version,migration_checksum FROM cea1_schema_meta WHERE singleton=1"
                )
                if cursor.fetchone() != (
                    CATALOGUE_SCHEMA_VERSION,
                    MIGRATION_001_CHECKSUM,
                ):
                    raise ArchiveFailure(ArchiveCode.STORE)
                cursor.execute(
                    "SELECT to_regclass('public.cea1_entry'),to_regclass('public.cea1_outbox'),to_regclass('public.cea1_artifact')"
                )
                if cursor.fetchone() != (
                    "cea1_entry",
                    "cea1_outbox",
                    "cea1_artifact",
                ):
                    raise ArchiveFailure(ArchiveCode.STORE)

    def reserve(
        self,
        entry_id: str,
        tenant_id: str,
        binding: bytes,
        objects: int,
        byte_count: int,
    ) -> bool:
        binding_digest = content_digest("carbon.evidence-archive.admission.v1", binding)
        with self.transaction() as connection:  # noqa: SIM117
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(43454131)")
                cursor.execute(
                    "SELECT binding_digest,reserved_objects,reserved_bytes FROM cea1_admission WHERE archive_entry_id=%s",
                    (entry_id,),
                )
                old = cursor.fetchone()
                if old is not None:
                    if old != (binding_digest, objects, byte_count):
                        raise ArchiveFailure(ArchiveCode.CONFLICT)
                    return False
                cursor.execute(
                    "SELECT count(*),coalesce(sum(reserved_objects),0),coalesce(sum(reserved_bytes),0) FROM cea1_admission WHERE active=true"
                )
                active_entries, active_objects, active_bytes = cursor.fetchone()
                if (
                    active_entries + 1 > self.limits.max_active_entries
                    or active_objects + objects > self.limits.max_objects
                    or active_bytes + byte_count > self.limits.max_bytes
                ):
                    raise ArchiveFailure(ArchiveCode.CAPACITY)
                cursor.execute(
                    "INSERT INTO cea1_admission VALUES (%s,%s,%s,%s,%s,%s,true,false)",
                    (
                        entry_id,
                        tenant_id,
                        binding.decode("utf-8"),
                        binding_digest,
                        objects,
                        byte_count,
                    ),
                )
                self._event(
                    cursor,
                    entry_id,
                    "ADMITTED",
                    {"objects": objects, "bytes": byte_count},
                )
                return True

    @staticmethod
    def _event(cursor, entry_id: str, kind: str, body: dict[str, object]) -> None:
        encoded = canonical_bytes(body).decode("utf-8")
        digest = content_digest("carbon.evidence-archive.event.v1", encoded.encode())
        cursor.execute(
            "INSERT INTO cea1_event(archive_entry_id,event_kind,event_json,event_digest) VALUES (%s,%s,%s,%s)",
            (entry_id, kind, encoded, digest),
        )

    def release_reservation(self, entry_id: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE cea1_admission SET active=false WHERE archive_entry_id=%s",
                (entry_id,),
            )

    def relation_source(self, entry_id: str) -> tuple[str, str, int] | None:
        validate_digest(entry_id)
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT binding_json,binding_digest FROM cea1_admission WHERE archive_entry_id=%s",
                (entry_id,),
            ).fetchone()
        if row is None:
            return None
        encoded = row[0].encode("utf-8")
        if content_digest("carbon.evidence-archive.admission.v1", encoded) != row[1]:
            raise ArchiveFailure(ArchiveCode.INTEGRITY)
        try:
            source = json.loads(encoded)["entry"]["source"]
            return (
                validate_token(source["tenant_id"]),
                validate_token(source["submission_id"]),
                int(source["attempt_number"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ArchiveFailure):
            raise ArchiveFailure(ArchiveCode.INTEGRITY) from None

    def finalize(
        self,
        entry_id: str,
        profile_digest: str,
        entry_payload: bytes,
        manifest_identity: str,
        artifacts: tuple[ArtifactRecord, ...],
        manifest_payload: bytes,
    ) -> bool:
        entry_digest = content_digest(
            "carbon.evidence-archive.entry-state.v1", entry_payload
        )
        with self.transaction() as connection:  # noqa: SIM117
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT entry_digest,manifest_identity FROM cea1_entry WHERE archive_entry_id=%s",
                    (entry_id,),
                )
                old = cursor.fetchone()
                if old is not None:
                    if old != (entry_digest, manifest_identity):
                        raise ArchiveFailure(ArchiveCode.CONFLICT)
                    return False
                cursor.execute(
                    "INSERT INTO cea1_entry VALUES (%s,%s,%s,%s,%s)",
                    (
                        entry_id,
                        profile_digest,
                        manifest_identity,
                        entry_payload.decode(),
                        entry_digest,
                    ),
                )
                for artifact in artifacts:
                    payload = canonical_bytes(artifact_record_payload(artifact))
                    cursor.execute(
                        "INSERT INTO cea1_artifact VALUES (%s,%s,%s,%s,%s)",
                        (
                            entry_id,
                            artifact.name,
                            payload.decode(),
                            content_digest(
                                "carbon.evidence-archive.artifact-record.v1", payload
                            ),
                            artifact.object_key,
                        ),
                    )
                event_payload = {
                    "manifest_identity": manifest_identity,
                    "manifest_digest": content_digest(
                        "carbon.evidence-archive.manifest-row.v1", manifest_payload
                    ),
                }
                self._event(cursor, entry_id, "CATALOGUE_COMMITTED", event_payload)
                outbox_payload = canonical_bytes(event_payload)
                event_id = content_digest(
                    "carbon.evidence-archive.outbox.v1", outbox_payload
                )
                cursor.execute(
                    "INSERT INTO cea1_outbox VALUES (%s,%s,%s,%s,%s)",
                    (
                        event_id,
                        entry_id,
                        "ARCHIVE_CATALOGUED",
                        outbox_payload.decode(),
                        content_digest(
                            "carbon.evidence-archive.outbox-payload.v1", outbox_payload
                        ),
                    ),
                )
                cursor.execute(
                    "UPDATE cea1_admission SET finalized=true WHERE archive_entry_id=%s",
                    (entry_id,),
                )
                return True

    def object_keys(self, tenant_id: str) -> tuple[str, ...]:
        validate_token(tenant_id)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT a.object_key FROM cea1_artifact a JOIN cea1_admission d USING(archive_entry_id) WHERE d.tenant_id=%s AND a.object_key IS NOT NULL",
                (tenant_id,),
            ).fetchall()
        return tuple(row[0] for row in rows)

    def verify_commit(
        self,
        entry_id: str,
        entry_payload: bytes,
        manifest_identity: str,
        artifacts: tuple[ArtifactRecord, ...],
    ) -> bool:
        with self.transaction() as connection:
            entry = connection.execute(
                "SELECT entry_json,entry_digest,manifest_identity FROM cea1_entry WHERE archive_entry_id=%s",
                (entry_id,),
            ).fetchone()
            rows = connection.execute(
                "SELECT artifact_name,artifact_json,artifact_digest FROM cea1_artifact WHERE archive_entry_id=%s ORDER BY artifact_name",
                (entry_id,),
            ).fetchall()
        if entry is None:
            return False
        if entry != (
            entry_payload.decode(),
            content_digest("carbon.evidence-archive.entry-state.v1", entry_payload),
            manifest_identity,
        ):
            raise ArchiveFailure(ArchiveCode.INTEGRITY)
        expected = {
            artifact.name: canonical_bytes(artifact_record_payload(artifact))
            for artifact in artifacts
        }
        if len(rows) != len(expected):
            raise ArchiveFailure(ArchiveCode.INTEGRITY)
        for name, encoded, digest in rows:
            expected_payload = expected.get(name)
            if (
                expected_payload is None
                or encoded != expected_payload.decode()
                or digest
                != content_digest(
                    "carbon.evidence-archive.artifact-record.v1", expected_payload
                )
            ):
                raise ArchiveFailure(ArchiveCode.INTEGRITY)
        return True

    def record_acknowledgement(
        self, entry_id: str, payload: bytes, ref: str, *, release: bool
    ) -> bool:
        digest = content_digest(
            "carbon.evidence-archive.acknowledgement-row.v1", payload
        )
        with self.transaction() as connection:  # noqa: SIM117
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT acknowledgement_digest FROM cea1_acknowledgement WHERE acknowledgement_ref=%s",
                    (ref,),
                )
                old = cursor.fetchone()
                if old is not None:
                    if old != (digest,):
                        raise ArchiveFailure(ArchiveCode.CONFLICT)
                    return False
                cursor.execute(
                    "INSERT INTO cea1_acknowledgement VALUES (%s,%s,%s,%s)",
                    (ref, entry_id, payload.decode(), digest),
                )
                self._event(
                    cursor, entry_id, "ACKNOWLEDGED", {"acknowledgement_ref": ref}
                )
                if release:
                    cursor.execute(
                        "UPDATE cea1_admission SET active=false WHERE archive_entry_id=%s",
                        (entry_id,),
                    )
                return True

    def append_availability(
        self,
        entry_id: str,
        artifact_name: str,
        state: ArtifactState,
        reason_ref: str,
    ) -> None:
        if state not in {
            ArtifactState.MISSING,
            ArtifactState.WITHDRAWN,
            ArtifactState.UNAVAILABLE_KEY,
        }:
            raise ArchiveFailure(ArchiveCode.INVALID)
        entry_id = validate_digest(entry_id)
        artifact_name = validate_artifact_name(artifact_name)
        reason_ref = validate_token(reason_ref)
        payload = canonical_bytes(
            {
                "archive_entry_id": entry_id,
                "artifact_name": artifact_name,
                "availability_state": state.value,
                "reason_ref": reason_ref,
            }
        )
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT 1 FROM cea1_artifact WHERE archive_entry_id=%s AND artifact_name=%s",
                (entry_id, artifact_name),
            ).fetchone()
            if row is None:
                raise ArchiveFailure(ArchiveCode.STATE)
            connection.execute(
                "INSERT INTO cea1_artifact_availability(archive_entry_id,artifact_name,availability_state,reason_ref,event_digest) VALUES (%s,%s,%s,%s,%s)",
                (
                    entry_id,
                    artifact_name,
                    state.value,
                    reason_ref,
                    content_digest("carbon.evidence-archive.availability.v1", payload),
                ),
            )

    def latest_availability(self, entry_id: str) -> dict[str, ArtifactState]:
        entry_id = validate_digest(entry_id)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT DISTINCT ON (artifact_name) artifact_name,availability_state FROM cea1_artifact_availability WHERE archive_entry_id=%s ORDER BY artifact_name,sequence DESC",
                (entry_id,),
            ).fetchall()
        try:
            return {name: ArtifactState(state) for name, state in rows}
        except ValueError:
            raise ArchiveFailure(ArchiveCode.INTEGRITY) from None

    def outbox(self) -> tuple[tuple[str, str, str], ...]:
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT event_id,event_kind,payload_json FROM cea1_outbox ORDER BY event_id"
            ).fetchall()
        return tuple(rows)

    def consume(self, consumer_id: str, event_id: str, payload: str) -> bool:
        consumer_id = validate_token(consumer_id)
        event_id = validate_digest(event_id)
        effect_digest = content_digest(
            "carbon.evidence-archive.consumer-effect.v1", payload.encode()
        )
        with self.transaction() as connection:  # noqa: SIM117
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload_json,payload_digest FROM cea1_outbox WHERE event_id=%s",
                    (event_id,),
                )
                source = cursor.fetchone()
                if source is None or source != (
                    payload,
                    content_digest(
                        "carbon.evidence-archive.outbox-payload.v1", payload.encode()
                    ),
                ):
                    raise ArchiveFailure(ArchiveCode.CONFLICT)
                cursor.execute(
                    "INSERT INTO cea1_consumer_effect VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    (consumer_id, event_id, effect_digest),
                )
                return cursor.rowcount == 1

    def record_orphan(self, object_key: str, quarantine_ref: str, body: bytes) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO cea1_orphan VALUES (%s,%s,%s) ON CONFLICT (object_key) DO NOTHING",
                (
                    object_key,
                    quarantine_ref,
                    content_digest("carbon.evidence-archive.orphan.v1", body),
                ),
            )

    def health_counts(self) -> tuple[int, int, int, int]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT "
                "(SELECT count(*) FROM cea1_admission WHERE active=true),"
                "(SELECT count(*) FROM cea1_entry),"
                "(SELECT count(*) FROM cea1_outbox),"
                "(SELECT count(*) FROM cea1_orphan)"
            ).fetchone()
        return tuple(int(value) for value in row)


def artifact_record_payload(value: ArtifactRecord) -> dict[str, object]:
    return {
        "name": value.name,
        "requirement": value.requirement.value,
        "state": value.state.value,
        "plaintext_digest": value.plaintext_digest,
        "plaintext_size": value.plaintext_size,
        "object_key": value.object_key,
        "key_id": value.key_id,
        "algorithm": value.algorithm,
        "nonce_hex": value.nonce_hex,
    }
