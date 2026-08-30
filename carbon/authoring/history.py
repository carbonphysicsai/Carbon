"""Create-only exact-ref history for B-02A scientific authoring artifacts."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
import struct
from dataclasses import dataclass
from pathlib import Path

from .errors import AuthoringError
from .loading import (
    _ORIGIN_TOKEN,
    AuthoringOrigin,
    DraftOrigin,
    FixtureOrigin,
    LoadedAuthoringArtifact,
    RegisteredOrigin,
    load_authoring_bytes,
)
from .model import ApplicabilityBinding, ApplicabilityTag
from .primitives import MAX_CANONICAL_DOCUMENT_BYTES
from .refs import (
    CanonicalChallengeCaseRef,
    ChallengeScope,
    GlobalScope,
    InstanceDistributionContractRef,
    TopLevelObjectRef,
    is_top_level_ref,
    owner_ref,
    reconstruct_top_level_ref,
    require_owner_ref,
    top_level_ref_type,
)

_MAGIC = b"CARBON-B02A-HISTORY\x00\x01"
_REVOCATION_MAGIC = b"CARBON-B02A-REVOCATION\x00\x01"
_MAX_HISTORY_RECORD_BYTES = MAX_CANONICAL_DOCUMENT_BYTES + 8_388_608
_MAX_REVOCATION_RECORD_BYTES = 1_048_576
_MAX_METADATA_ITEMS = 65_535
_NO_FOLLOW = getattr(os, "O_NOFOLLOW", None)
_DIRECTORY = getattr(os, "O_DIRECTORY", None)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_SUPPORTS_DIR_FD_OPEN = os.open in os.supports_dir_fd
_SUPPORTS_DIR_FD_MKDIR = os.mkdir in os.supports_dir_fd
_SUPPORTS_DIR_FD_LINK = os.link in os.supports_dir_fd
_SUPPORTS_DIR_FD_UNLINK = os.unlink in os.supports_dir_fd
_SUPPORTS_NOFOLLOW_LINK = os.link in os.supports_follow_symlinks
_MAX_STAGING_NAME_ATTEMPTS = 16


class AuthoringHistoryError(AuthoringError):
    """Immutable history access failed without exposing protected content."""


class _Writer:
    __slots__ = ("data",)

    def __init__(self, magic: bytes) -> None:
        self.data = bytearray(magic)

    def u8(self, value: int) -> None:
        self.data.extend(struct.pack(">B", value))

    def u32(self, value: int) -> None:
        self.data.extend(struct.pack(">I", value))

    def blob(self, value: bytes) -> None:
        self.u32(len(value))
        self.data.extend(value)

    def text(self, value: str) -> None:
        if type(value) is not str:
            raise TypeError("history metadata text must be an exact string")
        self.blob(value.encode("utf-8", errors="strict"))

    def finish(self) -> bytes:
        return bytes(self.data)


class _Reader:
    __slots__ = ("data", "offset")

    def __init__(self, data: bytes, magic: bytes) -> None:
        if type(data) is not bytes or not data.startswith(magic):
            raise AuthoringHistoryError(
                "authoring.history_format_invalid",
                "Stored authoring history has an unknown format.",
            )
        self.data = data
        self.offset = len(magic)

    def _take(self, count: int) -> bytes:
        end = self.offset + count
        if count < 0 or end > len(self.data):
            raise AuthoringHistoryError(
                "authoring.history_truncated",
                "Stored authoring history is truncated.",
            )
        value = self.data[self.offset : end]
        self.offset = end
        return value

    def u8(self) -> int:
        return struct.unpack(">B", self._take(1))[0]

    def u32(self) -> int:
        return struct.unpack(">I", self._take(4))[0]

    def blob(self, *, maximum: int = _MAX_HISTORY_RECORD_BYTES) -> bytes:
        count = self.u32()
        if count > maximum:
            raise AuthoringHistoryError(
                "authoring.history_field_too_large",
                "Stored authoring history field exceeds its bound.",
            )
        return self._take(count)

    def text(self) -> str:
        try:
            return self.blob(maximum=65_535).decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise AuthoringHistoryError(
                "authoring.history_text_invalid",
                "Stored authoring history text is not strict UTF-8.",
            ) from exc

    def require_end(self) -> None:
        if self.offset != len(self.data):
            raise AuthoringHistoryError(
                "authoring.history_trailing_data",
                "Stored authoring history has trailing data.",
            )


def _write_challenge_scope(writer: _Writer, scope: object) -> None:
    if type(scope) is ChallengeScope:
        writer.u8(1)
        writer.text(scope.challenge_key.challenge_id)
        writer.text(scope.challenge_key.version)
    elif type(scope) is GlobalScope:
        writer.u8(2)
    else:
        raise AuthoringHistoryError(
            "authoring.history_scope_invalid",
            "History metadata contains an invalid owner-ref scope.",
        )


def _read_challenge_scope(reader: _Reader) -> ChallengeScope | GlobalScope:
    tag = reader.u8()
    if tag == 1:
        from carbon.registry import ChallengeKey

        return ChallengeScope(ChallengeKey(reader.text(), reader.text()))
    if tag == 2:
        return GlobalScope()
    raise AuthoringHistoryError(
        "authoring.history_scope_unknown",
        "History metadata contains an unknown owner-ref scope.",
    )


def _write_owner_ref(writer: _Writer, value: object) -> None:
    ref_kind = object.__getattribute__(value, "ref_kind")
    validated = require_owner_ref(value, ref_kind)
    writer.text(validated.ref_kind)
    _write_challenge_scope(writer, validated.scope_binding)
    writer.text(validated.object_id)
    writer.text(validated.object_version)
    writer.text(validated.content_digest)


def _read_owner_ref(reader: _Reader) -> object:
    kind = reader.text()
    scope = _read_challenge_scope(reader)
    return owner_ref(
        kind,
        scope_binding=scope,
        object_id=reader.text(),
        object_version=reader.text(),
        content_digest=reader.text(),
    )


def _write_owner_refs(writer: _Writer, values: tuple[object, ...]) -> None:
    if type(values) is not tuple or len(values) > _MAX_METADATA_ITEMS:
        raise AuthoringHistoryError(
            "authoring.history_owner_refs_invalid",
            "History owner-ref tuple is invalid or too large.",
        )
    writer.u32(len(values))
    for value in values:
        _write_owner_ref(writer, value)


def _read_owner_refs(reader: _Reader) -> tuple[object, ...]:
    count = reader.u32()
    if count > _MAX_METADATA_ITEMS:
        raise AuthoringHistoryError(
            "authoring.history_owner_refs_too_large",
            "History owner-ref tuple exceeds its bound.",
        )
    return tuple(_read_owner_ref(reader) for _ in range(count))


def _write_top_level_ref(writer: _Writer, value: TopLevelObjectRef) -> None:
    ref = reconstruct_top_level_ref(value)
    writer.text(ref.object_kind)
    writer.text(ref.challenge_key.challenge_id)
    writer.text(ref.challenge_key.version)
    writer.text(ref.object_id)
    writer.text(ref.object_version)
    writer.text(ref.schema_version)
    writer.text(ref.canonicalization_profile)
    writer.text(ref.content_digest)
    if type(ref) is InstanceDistributionContractRef:
        writer.u8(1)
        writer.text(ref.expected_population_role)
    elif type(ref) is CanonicalChallengeCaseRef:
        writer.u8(2)
        writer.text(ref.disclosure_class)
    else:
        writer.u8(0)


def _read_top_level_ref(reader: _Reader) -> TopLevelObjectRef:
    from carbon.registry import ChallengeKey

    object_kind = reader.text()
    challenge_key = ChallengeKey(reader.text(), reader.text())
    common = (
        challenge_key,
        reader.text(),
        reader.text(),
        reader.text(),
        reader.text(),
        reader.text(),
    )
    extension = reader.u8()
    ref_type = top_level_ref_type(object_kind)
    if ref_type is InstanceDistributionContractRef:
        if extension != 1:
            raise AuthoringHistoryError(
                "authoring.history_ref_extension_invalid",
                "Distribution history ref is missing its exact role.",
            )
        return InstanceDistributionContractRef(*common, reader.text())
    if ref_type is CanonicalChallengeCaseRef:
        if extension != 2:
            raise AuthoringHistoryError(
                "authoring.history_ref_extension_invalid",
                "Case history ref is missing its disclosure class.",
            )
        return CanonicalChallengeCaseRef(*common, reader.text())
    if extension != 0:
        raise AuthoringHistoryError(
            "authoring.history_ref_extension_unknown",
            "History ref has an unknown extension.",
        )
    return ref_type(*common)


def _ref_storage_key(value: TopLevelObjectRef) -> str:
    writer = _Writer(b"CARBON-B02A-REF-KEY\x00\x01")
    _write_top_level_ref(writer, value)
    return hashlib.sha256(writer.finish()).hexdigest()


def _write_origin(writer: _Writer, value: AuthoringOrigin) -> None:
    if type(value) is FixtureOrigin:
        writer.u8(1)
        _write_owner_ref(writer, value.fixture_registration_ref)
        _write_owner_refs(writer, value.source_provenance_refs)
    elif type(value) is DraftOrigin:
        writer.u8(2)
        _write_owner_ref(writer, value.draft_authority_ref)
        _write_owner_refs(writer, value.source_provenance_refs)
    elif type(value) is RegisteredOrigin:
        writer.u8(3)
        _write_owner_ref(writer, value.registration_ref)
        _write_owner_refs(writer, value.authority_evidence_refs)
        _write_owner_refs(writer, value.source_provenance_refs)
    else:
        raise AuthoringHistoryError(
            "authoring.history_origin_invalid",
            "History origin must be an exact capability-issued variant.",
        )


def _read_origin(reader: _Reader) -> AuthoringOrigin:
    tag = reader.u8()
    if tag == 1:
        return FixtureOrigin(
            _read_owner_ref(reader),
            _read_owner_refs(reader),
            _token=_ORIGIN_TOKEN,
        )
    if tag == 2:
        return DraftOrigin(
            _read_owner_ref(reader),
            _read_owner_refs(reader),
            _token=_ORIGIN_TOKEN,
        )
    if tag == 3:
        return RegisteredOrigin(
            _read_owner_ref(reader),
            _read_owner_refs(reader),
            _read_owner_refs(reader),
            _token=_ORIGIN_TOKEN,
        )
    raise AuthoringHistoryError(
        "authoring.history_origin_unknown",
        "History metadata contains an unknown origin variant.",
    )


def _write_qualification(writer: _Writer, value: ApplicabilityBinding[object]) -> None:
    if type(value) is not ApplicabilityBinding:
        raise AuthoringHistoryError(
            "authoring.history_qualification_invalid",
            "History qualification binding has the wrong exact type.",
        )
    writer.u8(1 if value.tag is ApplicabilityTag.BOUND else 2)
    _write_owner_ref(writer, value.value)


def _read_qualification(reader: _Reader) -> ApplicabilityBinding[object]:
    tag = reader.u8()
    value = _read_owner_ref(reader)
    if tag == 1:
        return ApplicabilityBinding.bound(
            require_owner_ref(value, "qualification_evidence_bundle")
        )
    if tag == 2:
        return ApplicabilityBinding.not_applicable(
            require_owner_ref(value, "applicability_reason")
        )
    raise AuthoringHistoryError(
        "authoring.history_qualification_unknown",
        "History metadata contains an unknown qualification branch.",
    )


@dataclass(frozen=True, slots=True)
class _StoredEnvelope:
    ref: TopLevelObjectRef
    supersedes: TopLevelObjectRef | None
    origin: AuthoringOrigin
    origin_evidence_ref: object
    source_provenance_refs: tuple[object, ...]
    audit_evidence_refs: tuple[object, ...]
    qualification_evidence: ApplicabilityBinding[object]
    payload: bytes


def _encode_envelope(
    artifact: LoadedAuthoringArtifact,
    supersedes: TopLevelObjectRef | None,
) -> bytes:
    writer = _Writer(_MAGIC)
    _write_top_level_ref(writer, artifact.expected_ref)
    if supersedes is None:
        writer.u8(0)
    else:
        writer.u8(1)
        _write_top_level_ref(writer, supersedes)
    _write_origin(writer, artifact.origin)
    _write_owner_ref(writer, artifact.origin_evidence_ref)
    _write_owner_refs(writer, artifact.source_provenance_refs)
    _write_owner_refs(writer, artifact.audit_evidence_refs)
    _write_qualification(writer, artifact.qualification_evidence)
    writer.blob(artifact.verified_bytes)
    result = writer.finish()
    if len(result) > _MAX_HISTORY_RECORD_BYTES:
        raise AuthoringHistoryError(
            "authoring.history_record_too_large",
            "Immutable authoring history record exceeds its bound.",
        )
    return result


def _decode_envelope(data: bytes) -> _StoredEnvelope:
    reader = _Reader(data, _MAGIC)
    ref = _read_top_level_ref(reader)
    predecessor_tag = reader.u8()
    if predecessor_tag == 0:
        predecessor = None
    elif predecessor_tag == 1:
        predecessor = _read_top_level_ref(reader)
    else:
        raise AuthoringHistoryError(
            "authoring.history_supersession_unknown",
            "History metadata contains an unknown supersession branch.",
        )
    envelope = _StoredEnvelope(
        ref=ref,
        supersedes=predecessor,
        origin=_read_origin(reader),
        origin_evidence_ref=require_owner_ref(
            _read_owner_ref(reader), "authoring_origin_evidence"
        ),
        source_provenance_refs=_read_owner_refs(reader),
        audit_evidence_refs=_read_owner_refs(reader),
        qualification_evidence=_read_qualification(reader),
        payload=reader.blob(maximum=MAX_CANONICAL_DOCUMENT_BYTES),
    )
    reader.require_end()
    return envelope


def _decode_revocation(data: bytes) -> tuple[TopLevelObjectRef, object]:
    reader = _Reader(data, _REVOCATION_MAGIC)
    target = _read_top_level_ref(reader)
    event = require_owner_ref(_read_owner_ref(reader), "authoring_revocation")
    reader.require_end()
    return target, event


def _predecessor_from_object(value: object) -> TopLevelObjectRef | None:
    binding = getattr(value, "supersedes", None)
    if type(binding) is not ApplicabilityBinding:
        raise AuthoringHistoryError(
            "authoring.history_supersession_binding_invalid",
            "Authored object lacks the exact supersession binding.",
        )
    if binding.tag is ApplicabilityTag.NOT_APPLICABLE:
        require_owner_ref(binding.value, "applicability_reason")
        return None
    if not is_top_level_ref(binding.value):
        raise AuthoringHistoryError(
            "authoring.history_supersession_ref_invalid",
            "Authored object supersession must bind an exact top-level ref.",
        )
    return reconstruct_top_level_ref(binding.value)


class AuthoringHistoryStore:
    """Append-only filesystem store with no `latest` or overwrite operation."""

    __slots__ = ("root",)

    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise TypeError("history root must be a pathlib.Path")
        root.mkdir(parents=True, exist_ok=True)
        metadata = root.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise AuthoringHistoryError(
                "authoring.history_root_invalid",
                "History root must be a non-symlink directory.",
            )
        self.root = root.resolve(strict=True)

    @staticmethod
    def _require_secure_io() -> None:
        if (
            _NO_FOLLOW is None
            or _DIRECTORY is None
            or not _SUPPORTS_DIR_FD_OPEN
            or not _SUPPORTS_DIR_FD_MKDIR
            or not _SUPPORTS_DIR_FD_LINK
            or not _SUPPORTS_DIR_FD_UNLINK
            or not _SUPPORTS_NOFOLLOW_LINK
        ):
            raise AuthoringHistoryError(
                "authoring.history_secure_io_unavailable",
                "This host cannot provide descriptor-relative no-follow history I/O.",
            )

    def _open_root(self) -> int:
        self._require_secure_io()
        try:
            return os.open(self.root, os.O_RDONLY | _DIRECTORY | _NO_FOLLOW)
        except OSError as exc:
            raise AuthoringHistoryError(
                "authoring.history_root_unreadable",
                "History root could not be opened securely.",
            ) from exc

    @staticmethod
    def _parts_for(ref: TopLevelObjectRef) -> tuple[str, ...]:
        exact = reconstruct_top_level_ref(ref)
        return (
            "records",
            exact.object_kind,
            exact.challenge_key.challenge_id,
            exact.challenge_key.version,
            exact.object_id,
            f"{exact.object_version}.b02a",
        )

    def _open_parent(self, parts: tuple[str, ...], *, create: bool) -> tuple[int, str]:
        current = self._open_root()
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=current)
                    except FileExistsError:
                        pass
                    except OSError as exc:
                        raise AuthoringHistoryError(
                            "authoring.history_directory_create_failed",
                            "History directory could not be created securely.",
                        ) from exc
                try:
                    following = os.open(
                        part,
                        os.O_RDONLY | _DIRECTORY | _NO_FOLLOW,
                        dir_fd=current,
                    )
                except OSError as exc:
                    if not create and exc.errno in {errno.ENOENT, errno.ENOTDIR}:
                        code = "authoring.history_missing"
                    elif exc.errno == errno.ELOOP:
                        code = "authoring.history_path_escape"
                    else:
                        code = "authoring.history_path_unreadable"
                    raise AuthoringHistoryError(
                        code,
                        "History path could not be traversed securely.",
                    ) from exc
                os.close(current)
                current = following
            return current, parts[-1]
        except Exception:
            os.close(current)
            raise

    def _read_file(
        self, parts: tuple[str, ...], *, maximum: int = _MAX_HISTORY_RECORD_BYTES
    ) -> bytes:
        parent, name = self._open_parent(parts, create=False)
        descriptor = -1
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | _NO_FOLLOW | _NONBLOCK,
                dir_fd=parent,
            )
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise AuthoringHistoryError(
                    "authoring.history_not_regular",
                    "History record must be a regular file.",
                )
            if metadata.st_size > maximum:
                raise AuthoringHistoryError(
                    "authoring.history_record_too_large",
                    "History record exceeds its configured bound.",
                )
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                data = stream.read(maximum + 1)
            if len(data) > maximum:
                raise AuthoringHistoryError(
                    "authoring.history_record_too_large",
                    "History record exceeds its configured bound.",
                )
            final_metadata = os.fstat(descriptor)
            stable_fields = (
                "st_dev",
                "st_ino",
                "st_mode",
                "st_size",
                "st_mtime_ns",
            )
            if len(data) != metadata.st_size or any(
                getattr(metadata, field) != getattr(final_metadata, field)
                for field in stable_fields
            ):
                raise AuthoringHistoryError(
                    "authoring.history_snapshot_changed",
                    "History record changed during its verified read.",
                )
            return data
        except FileNotFoundError as exc:
            raise AuthoringHistoryError(
                "authoring.history_missing",
                "Exact authoring history ref was not found.",
            ) from exc
        except AuthoringHistoryError:
            raise
        except OSError as exc:
            code = (
                "authoring.history_path_escape"
                if exc.errno == errno.ELOOP
                else "authoring.history_unreadable"
            )
            raise AuthoringHistoryError(
                code,
                "History record could not be read securely.",
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(parent)

    def _write_exclusive(self, parts: tuple[str, ...], data: bytes) -> None:
        parent, name = self._open_parent(parts, create=True)
        staging_parent, _ = self._open_parent(("staging", "unused"), create=True)
        descriptor = -1
        staging_name: str | None = None
        try:
            for _ in range(_MAX_STAGING_NAME_ATTEMPTS):
                candidate = f"pending-{os.urandom(16).hex()}.b02a"
                try:
                    descriptor = os.open(
                        candidate,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NO_FOLLOW,
                        0o600,
                        dir_fd=staging_parent,
                    )
                except FileExistsError:
                    continue
                staging_name = candidate
                break
            if staging_name is None:
                raise AuthoringHistoryError(
                    "authoring.history_staging_collision",
                    "A unique history staging record could not be allocated.",
                )

            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("history write made no progress")
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1

            try:
                os.link(
                    staging_name,
                    name,
                    src_dir_fd=staging_parent,
                    dst_dir_fd=parent,
                    follow_symlinks=False,
                )
            except FileExistsError:
                existing = self._read_file(parts, maximum=len(data) + 1)
                if existing != data:
                    raise AuthoringHistoryError(
                        "authoring.history_conflict",
                        "Logical identity/version already has different immutable bytes.",
                    )
            else:
                os.fsync(parent)
        except AuthoringHistoryError:
            raise
        except OSError as exc:
            raise AuthoringHistoryError(
                "authoring.history_write_failed",
                "History record could not be created securely.",
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if staging_name is not None:
                try:
                    os.unlink(staging_name, dir_fd=staging_parent)
                    os.fsync(staging_parent)
                except FileNotFoundError:
                    pass
                except OSError:
                    # Publication has already been decided. A leftover private
                    # staging inode is never interpreted as an authored record.
                    pass
            os.close(staging_parent)
            os.close(parent)

    def contains(self, ref: TopLevelObjectRef) -> bool:
        """Return whether one exact, fully verifiable ref exists.

        Presence is not inferred from an envelope header alone.  A corrupt
        payload cannot become a valid supersession predecessor merely because
        its exact path and duplicated header ref remain readable.
        """
        try:
            self.get(ref)
        except AuthoringHistoryError as exc:
            if exc.code == "authoring.history_missing":
                return False
            raise
        return True

    def _stored_envelope(self, ref: TopLevelObjectRef) -> _StoredEnvelope:
        exact = reconstruct_top_level_ref(ref)
        envelope = _decode_envelope(self._read_file(self._parts_for(exact)))
        if type(envelope.ref) is not type(exact) or envelope.ref != exact:
            raise AuthoringHistoryError(
                "authoring.history_ref_mismatch",
                "Stored record does not match the complete requested exact ref.",
            )
        return envelope

    def put(self, artifact: LoadedAuthoringArtifact) -> TopLevelObjectRef:
        """Create one immutable record, validating exact predecessor history."""
        if type(artifact) is not LoadedAuthoringArtifact:
            raise TypeError("artifact must be an exact LoadedAuthoringArtifact")
        # Re-enter the digest/parser/ref boundary so post-load tampering cannot be
        # persisted through a frozen-object bypass.
        fresh = load_authoring_bytes(
            artifact.expected_ref,
            artifact.verified_bytes,
            origin=artifact.origin,
            origin_evidence_ref=artifact.origin_evidence_ref,
            source_provenance_refs=artifact.source_provenance_refs,
            audit_evidence_refs=artifact.audit_evidence_refs,
            qualification_evidence=artifact.qualification_evidence,
        )
        predecessor = _predecessor_from_object(fresh.authored_object)
        if predecessor is not None:
            current = fresh.expected_ref
            if (
                type(predecessor) is not type(current)
                or predecessor.challenge_key != current.challenge_key
                or predecessor.object_id != current.object_id
                or predecessor.object_version == current.object_version
            ):
                raise AuthoringHistoryError(
                    "authoring.history_supersession_invalid",
                    "Supersession must bind a distinct same-kind Challenge/object predecessor.",
                )
            try:
                self.get(predecessor)
            except AuthoringHistoryError as exc:
                if exc.code != "authoring.history_missing":
                    raise
                raise AuthoringHistoryError(
                    "authoring.history_predecessor_missing",
                    "Exact supersession predecessor is absent from immutable history.",
                ) from exc
            seen = {fresh.expected_ref}
            cursor: TopLevelObjectRef | None = predecessor
            while cursor is not None:
                if cursor in seen:
                    raise AuthoringHistoryError(
                        "authoring.history_supersession_cycle",
                        "Supersession graph contains a cycle.",
                    )
                seen.add(cursor)
                cursor = _predecessor_from_object(self.get(cursor).authored_object)
        encoded = _encode_envelope(fresh, predecessor)
        self._write_exclusive(self._parts_for(fresh.expected_ref), encoded)
        return reconstruct_top_level_ref(fresh.expected_ref)

    def get(self, ref: TopLevelObjectRef) -> LoadedAuthoringArtifact:
        """Load the exact historical bytes/ref; never resolve an alias or latest."""
        envelope = self._stored_envelope(ref)
        loaded = load_authoring_bytes(
            envelope.ref,
            envelope.payload,
            origin=envelope.origin,
            origin_evidence_ref=envelope.origin_evidence_ref,
            source_provenance_refs=envelope.source_provenance_refs,
            audit_evidence_refs=envelope.audit_evidence_refs,
            qualification_evidence=envelope.qualification_evidence,
        )
        if _predecessor_from_object(loaded.authored_object) != envelope.supersedes:
            raise AuthoringHistoryError(
                "authoring.history_supersession_mismatch",
                "Stored supersession metadata differs from the verified authored object.",
            )
        return loaded

    @staticmethod
    def _revocation_parts(
        ref: TopLevelObjectRef, revocation_ref: object
    ) -> tuple[str, ...]:
        exact_revocation = require_owner_ref(revocation_ref, "authoring_revocation")
        ref_key = _ref_storage_key(ref)
        writer = _Writer(b"CARBON-B02A-REVOCATION-KEY\x00\x01")
        _write_owner_ref(writer, exact_revocation)
        event_key = hashlib.sha256(writer.finish()).hexdigest()
        return ("revocations", ref_key, f"{event_key}.rev")

    def register_revocation(
        self, ref: TopLevelObjectRef, revocation_ref: object
    ) -> None:
        """Record an immutable prospective block without rewriting history."""
        exact = reconstruct_top_level_ref(ref)
        if not self.contains(exact):
            raise AuthoringHistoryError(
                "authoring.history_revocation_target_missing",
                "Revocation target is absent from exact history.",
            )
        event = require_owner_ref(revocation_ref, "authoring_revocation")
        writer = _Writer(_REVOCATION_MAGIC)
        _write_top_level_ref(writer, exact)
        _write_owner_ref(writer, event)
        self._write_exclusive(self._revocation_parts(exact, event), writer.finish())

    def is_revoked(self, ref: TopLevelObjectRef) -> bool:
        """Return whether any immutable prospective revocation exists."""
        exact = reconstruct_top_level_ref(ref)
        ref_key = _ref_storage_key(exact)
        parts = ("revocations", ref_key, "placeholder")
        try:
            parent, _ = self._open_parent(parts, create=False)
        except AuthoringHistoryError as exc:
            if exc.code in {
                "authoring.history_path_unreadable",
                "authoring.history_missing",
            }:
                return False
            raise
        try:
            names = os.listdir(parent)
        except AuthoringHistoryError:
            raise
        except OSError as exc:
            raise AuthoringHistoryError(
                "authoring.history_revocation_unreadable",
                "Revocation history could not be read securely.",
            ) from exc
        finally:
            os.close(parent)

        for name in names:
            if type(name) is not str or not name.endswith(".rev"):
                raise AuthoringHistoryError(
                    "authoring.history_revocation_entry_invalid",
                    "Revocation directory contains an unexpected entry.",
                )
            data = self._read_file(
                ("revocations", ref_key, name),
                maximum=_MAX_REVOCATION_RECORD_BYTES,
            )
            stored_target, event = _decode_revocation(data)
            if type(stored_target) is not type(exact) or stored_target != exact:
                raise AuthoringHistoryError(
                    "authoring.history_revocation_target_mismatch",
                    "Revocation event does not bind the exact requested ref.",
                )
            expected_name = self._revocation_parts(exact, event)[-1]
            if name != expected_name:
                raise AuthoringHistoryError(
                    "authoring.history_revocation_name_mismatch",
                    "Revocation event filename does not bind its exact event ref.",
                )
        return bool(names)


__all__ = ["AuthoringHistoryError", "AuthoringHistoryStore"]
