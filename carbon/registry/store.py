"""Strict deterministic JSON persistence for exact-version challenge records."""

from __future__ import annotations

import json
import os
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised on non-POSIX platforms
    _fcntl = None

from carbon.registry.model import (
    ArtifactBinding,
    ChallengeKey,
    ChallengeRecord,
    QualificationEvidence,
    QualificationManifest,
)

_CORE_RECORD_FIELDS = {
    "allowed_backbones",
    "artifacts",
    "challenge_id",
    "qualification",
    "status",
    "version",
}
_OPTIONAL_RECORD_FIELDS = {
    "allowed_backend_profile_ids",
    "receipt_schema_version",
    "required_backend_profile_id",
}
_ARTIFACT_FIELDS = {"digest", "path"}
_MANIFEST_FIELDS = {"challenge_id", "challenge_version", "mode", "slots"}
_EVIDENCE_FIELDS = {
    "artifact_id",
    "backend_profile_ids",
    "receipt_schema_version",
    "reference",
    "state",
}

_NO_FOLLOW = getattr(os, "O_NOFOLLOW", None)
_DIRECTORY = getattr(os, "O_DIRECTORY", None)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_MAX_RECORD_BYTES = 1024 * 1024
_MAX_SCAN_DEPTH = 64
_SUPPORTS_DIR_FD_OPEN = os.open in os.supports_dir_fd
_SUPPORTS_DIR_FD_MKDIR = os.mkdir in os.supports_dir_fd
_SUPPORTS_DIR_FD_UNLINK = os.unlink in os.supports_dir_fd


class RegistryError(Exception):
    """Safe registry failure with stable code and JSON-style field path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(message)


class _DuplicateKeyError(ValueError):
    pass


class _InvalidConstantError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _reject_non_json_constant(value: str) -> None:
    del value
    raise _InvalidConstantError


def _reject_json_number(value: str) -> None:
    del value
    raise ValueError


def _object(value: object, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise RegistryError(
            "record.field_type", path, "Registry field has an invalid JSON type."
        )
    return value


def _array(value: object, path: str) -> list[Any]:
    if type(value) is not list:
        raise RegistryError(
            "record.field_type", path, "Registry field has an invalid JSON type."
        )
    return value


def _known_fields(value: dict[str, Any], allowed: set[str], path: str) -> None:
    if any(type(key) is not str for key in value) or not set(value).issubset(allowed):
        raise RegistryError(
            "record.field_unknown", path, "Registry object contains an unknown field."
        )


def _required_fields(value: dict[str, Any], required: set[str]) -> None:
    for field in sorted(required):
        if field not in value:
            raise RegistryError(
                "record.field_required",
                f"/{field}",
                "Required registry field is missing.",
            )


def _optional_string(value: object, path: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise RegistryError(
            "record.field_type", path, "Registry field has an invalid JSON type."
        )
    return value


def _parse_artifacts(value: object) -> dict[str, ArtifactBinding]:
    raw_artifacts = _object(value, "/artifacts")
    artifacts: dict[str, ArtifactBinding] = {}
    for artifact_id, raw_binding in raw_artifacts.items():
        if type(artifact_id) is not str:
            raise RegistryError(
                "record.field_type",
                "/artifacts",
                "Artifact identifiers must be strings.",
            )
        binding = _object(raw_binding, "/artifacts")
        _known_fields(binding, _ARTIFACT_FIELDS, "/artifacts")
        artifacts[artifact_id] = ArtifactBinding(
            path=_optional_string(binding.get("path"), "/artifacts/path"),
            digest=_optional_string(binding.get("digest"), "/artifacts/digest"),
        )
    return artifacts


def _parse_slots(value: object) -> dict[str, QualificationEvidence | None]:
    raw_slots = _object(value, "/qualification/slots")
    slots: dict[str, QualificationEvidence | None] = {}
    for slot, raw_evidence in raw_slots.items():
        if type(slot) is not str:
            raise RegistryError(
                "record.field_type",
                "/qualification/slots",
                "Qualification slot names must be strings.",
            )
        if raw_evidence is None:
            slots[slot] = None
            continue
        evidence = _object(raw_evidence, "/qualification/slots")
        _known_fields(evidence, _EVIDENCE_FIELDS, "/qualification/slots")
        slots[slot] = QualificationEvidence(
            state=_optional_string(evidence.get("state"), "/qualification/slots/state"),
            artifact_id=_optional_string(
                evidence.get("artifact_id"),
                "/qualification/slots/artifact_id",
            ),
            reference=_optional_string(
                evidence.get("reference"),
                "/qualification/slots/reference",
            ),
            backend_profile_ids=tuple(
                _array(
                    evidence.get("backend_profile_ids", []),
                    "/qualification/slots/backend_profile_ids",
                )
            ),
            receipt_schema_version=_optional_string(
                evidence.get("receipt_schema_version"),
                "/qualification/slots/receipt_schema_version",
            ),
        )
    return slots


def _parse_manifest(value: object) -> QualificationManifest | None:
    if value is None:
        return None
    manifest = _object(value, "/qualification")
    _known_fields(manifest, _MANIFEST_FIELDS, "/qualification")
    raw_slots = manifest.get("slots", {})
    return QualificationManifest(
        challenge_id=_optional_string(
            manifest.get("challenge_id"), "/qualification/challenge_id"
        ),
        challenge_version=_optional_string(
            manifest.get("challenge_version"),
            "/qualification/challenge_version",
        ),
        mode=_optional_string(manifest.get("mode"), "/qualification/mode"),
        slots=_parse_slots(raw_slots),
    )


def _record_from_object(value: object) -> ChallengeRecord:
    record = _object(value, "")
    _known_fields(record, _CORE_RECORD_FIELDS | _OPTIONAL_RECORD_FIELDS, "")
    _required_fields(record, _CORE_RECORD_FIELDS)
    try:
        challenge_id = record["challenge_id"]
        version = record["version"]
        status = record["status"]
        if type(challenge_id) is not str:
            raise RegistryError(
                "record.field_type",
                "/challenge_id",
                "Registry field has an invalid JSON type.",
            )
        if type(version) is not str:
            raise RegistryError(
                "record.field_type",
                "/version",
                "Registry field has an invalid JSON type.",
            )
        if type(status) is not str:
            raise RegistryError(
                "record.field_type",
                "/status",
                "Registry field has an invalid JSON type.",
            )
        return ChallengeRecord(
            challenge_id=challenge_id,
            version=version,
            status=status,
            allowed_backbones=tuple(
                _array(record["allowed_backbones"], "/allowed_backbones")
            ),
            artifacts=_parse_artifacts(record["artifacts"]),
            qualification=_parse_manifest(record["qualification"]),
            receipt_schema_version=_optional_string(
                record.get("receipt_schema_version"),
                "/receipt_schema_version",
            ),
            required_backend_profile_id=_optional_string(
                record.get("required_backend_profile_id"),
                "/required_backend_profile_id",
            ),
            allowed_backend_profile_ids=tuple(
                _array(
                    record.get("allowed_backend_profile_ids", []),
                    "/allowed_backend_profile_ids",
                )
            ),
        )
    except RegistryError:
        raise
    except (TypeError, ValueError) as exc:
        raise RegistryError(
            "record.invalid", "", "Registry record is invalid."
        ) from exc


def _evidence_object(evidence: QualificationEvidence | None) -> object:
    if evidence is None:
        return None
    return {
        "artifact_id": evidence.artifact_id,
        "backend_profile_ids": list(evidence.backend_profile_ids),
        "receipt_schema_version": evidence.receipt_schema_version,
        "reference": evidence.reference,
        "state": evidence.state,
    }


def _manifest_object(manifest: QualificationManifest | None) -> object:
    if manifest is None:
        return None
    return {
        "challenge_id": manifest.challenge_id,
        "challenge_version": manifest.challenge_version,
        "mode": manifest.mode,
        "slots": {
            slot: _evidence_object(evidence)
            for slot, evidence in manifest.slots.items()
        },
    }


def _record_object(record: ChallengeRecord) -> dict[str, object]:
    return {
        "allowed_backend_profile_ids": list(record.allowed_backend_profile_ids),
        "allowed_backbones": list(record.allowed_backbones),
        "artifacts": {
            artifact_id: {"digest": binding.digest, "path": binding.path}
            for artifact_id, binding in record.artifacts.items()
        },
        "challenge_id": record.challenge_id,
        "qualification": _manifest_object(record.qualification),
        "receipt_schema_version": record.receipt_schema_version,
        "required_backend_profile_id": record.required_backend_profile_id,
        "status": record.status,
        "version": record.version,
    }


def serialize_record(record: ChallengeRecord) -> str:
    """Serialize one record to stable, strict JSON with canonical key ordering."""
    if not isinstance(record, ChallengeRecord):
        raise TypeError("record must be a ChallengeRecord")
    return (
        json.dumps(
            _record_object(record),
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


class RegistryStore:
    """File-backed store with one atomically replaced JSON file per key."""

    def __init__(
        self,
        registry_root: str | os.PathLike[str],
        artifact_root: str | os.PathLike[str],
    ) -> None:
        requested_registry_root = Path(registry_root)
        try:
            requested_registry_root.mkdir(parents=True, exist_ok=True)
            resolved_registry_root = requested_registry_root.resolve(strict=True)
            resolved_artifact_root = Path(artifact_root).resolve(strict=True)
        except OSError as exc:
            raise RegistryError(
                "registry.root_invalid", "", "Configured registry roots are invalid."
            ) from exc
        if not resolved_registry_root.is_dir() or not resolved_artifact_root.is_dir():
            raise RegistryError(
                "registry.root_invalid", "", "Configured registry roots are invalid."
            )
        self._registry_root = resolved_registry_root
        self._artifact_root = resolved_artifact_root

        if (
            _NO_FOLLOW is None
            or _DIRECTORY is None
            or _fcntl is None
            or not _SUPPORTS_DIR_FD_OPEN
            or not _SUPPORTS_DIR_FD_MKDIR
            or not _SUPPORTS_DIR_FD_UNLINK
        ):
            raise RegistryError(
                "registry.secure_io_unavailable",
                "",
                "Secure descriptor-relative registry access is unavailable.",
            )

    @property
    def registry_root(self) -> Path:
        """Return the resolved trusted registry root."""
        return self._registry_root

    @property
    def artifact_root(self) -> Path:
        """Return the resolved trusted artifact root."""
        return self._artifact_root

    def _record_path(self, key: ChallengeKey) -> Path:
        return self._registry_root / key.challenge_id / f"{key.version}.json"

    def _open_root(self) -> int:
        assert _NO_FOLLOW is not None
        assert _DIRECTORY is not None
        try:
            return os.open(
                self._registry_root,
                os.O_RDONLY | _DIRECTORY | _NO_FOLLOW,
            )
        except OSError as exc:
            raise RegistryError(
                "registry.root_invalid", "", "Configured registry root is invalid."
            ) from exc

    def _open_relative_file(self, path: Path) -> int:
        assert _NO_FOLLOW is not None
        assert _DIRECTORY is not None
        try:
            parts = path.relative_to(self._registry_root).parts
        except ValueError as exc:
            raise RegistryError(
                "record.unreadable", "", "Challenge record could not be read."
            ) from exc
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise RegistryError(
                "record.unreadable", "", "Challenge record could not be read."
            )

        descriptor = self._open_root()
        try:
            for index, part in enumerate(parts):
                flags = os.O_RDONLY | _NO_FOLLOW
                if index < len(parts) - 1:
                    flags |= _DIRECTORY
                else:
                    flags |= _NONBLOCK
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
        except FileNotFoundError as exc:
            os.close(descriptor)
            raise RegistryError(
                "record.not_found", "", "Challenge record was not found."
            ) from exc
        except OSError as exc:
            os.close(descriptor)
            raise RegistryError(
                "record.unreadable", "", "Challenge record could not be read."
            ) from exc
        return descriptor

    def _open_challenge_directory(self, key: ChallengeKey) -> int:
        assert _NO_FOLLOW is not None
        assert _DIRECTORY is not None
        root_descriptor = self._open_root()
        try:
            try:
                os.mkdir(key.challenge_id, mode=0o700, dir_fd=root_descriptor)
            except FileExistsError:
                pass
            return os.open(
                key.challenge_id,
                os.O_RDONLY | _DIRECTORY | _NO_FOLLOW,
                dir_fd=root_descriptor,
            )
        except (OSError, NotImplementedError) as exc:
            raise RegistryError(
                "record.write_failed", "", "Challenge record could not be written."
            ) from exc
        finally:
            os.close(root_descriptor)

    @contextmanager
    def _key_lock(self, key: ChallengeKey) -> Iterator[None]:
        assert _NO_FOLLOW is not None
        assert _fcntl is not None
        root_descriptor = self._open_root()
        lock_descriptor = -1
        lock_name = f".{key.challenge_id}.{key.version}.lock"
        try:
            lock_descriptor = os.open(
                lock_name,
                os.O_RDWR | os.O_CREAT | _NO_FOLLOW | _NONBLOCK,
                0o600,
                dir_fd=root_descriptor,
            )
            if not stat.S_ISREG(os.fstat(lock_descriptor).st_mode):
                raise RegistryError(
                    "registry.lock_failed", "", "Challenge record lock failed."
                )
            _fcntl.flock(lock_descriptor, _fcntl.LOCK_EX)
            yield
        except RegistryError:
            raise
        except OSError as exc:
            raise RegistryError(
                "registry.lock_failed", "", "Challenge record lock failed."
            ) from exc
        finally:
            if lock_descriptor >= 0:
                try:
                    _fcntl.flock(lock_descriptor, _fcntl.LOCK_UN)
                finally:
                    os.close(lock_descriptor)
            os.close(root_descriptor)

    def _read_json(self, path: Path) -> object:
        descriptor = self._open_relative_file(path)

        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise RegistryError(
                    "record.not_regular_file",
                    "",
                    "Challenge record must be a regular file.",
                )
            if metadata.st_size > _MAX_RECORD_BYTES:
                raise RegistryError(
                    "record.too_large", "", "Challenge record exceeds the size limit."
                )
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                payload = stream.read(_MAX_RECORD_BYTES + 1)
            if len(payload) > _MAX_RECORD_BYTES:
                raise RegistryError(
                    "record.too_large", "", "Challenge record exceeds the size limit."
                )
            text = payload.decode("utf-8")
        except RegistryError:
            raise
        except (OSError, UnicodeError) as exc:
            raise RegistryError(
                "record.unreadable", "", "Challenge record could not be read."
            ) from exc
        finally:
            os.close(descriptor)

        try:
            return json.loads(
                text,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_non_json_constant,
                parse_float=_reject_json_number,
                parse_int=_reject_json_number,
            )
        except _DuplicateKeyError as exc:
            raise RegistryError(
                "json.duplicate_key", "", "Duplicate JSON object key is not allowed."
            ) from exc
        except (ValueError, RecursionError) as exc:
            raise RegistryError(
                "json.invalid", "", "Challenge record is not valid strict JSON."
            ) from exc

    def _load_path(
        self, path: Path, *, expected_key: ChallengeKey | None = None
    ) -> ChallengeRecord:
        record = _record_from_object(self._read_json(path))
        if expected_key is not None and record.key != expected_key:
            raise RegistryError(
                "record.key_mismatch",
                "",
                "Embedded challenge identity does not match its file location.",
            )
        return record

    def load(self, challenge_id: str, version: str) -> ChallengeRecord:
        """Load exactly one key and verify its embedded identity."""
        try:
            key = ChallengeKey(challenge_id, version)
        except ValueError as exc:
            raise RegistryError(
                "record.identity_invalid", "", "Challenge identity is invalid."
            ) from exc
        return self._load_path(self._record_path(key), expected_key=key)

    def _scan_json_paths(self) -> list[Path]:
        assert _NO_FOLLOW is not None
        assert _DIRECTORY is not None
        paths: list[Path] = []
        root_descriptor = self._open_root()
        root_identity = os.fstat(root_descriptor)

        def walk(descriptor: int, relative_parts: tuple[str, ...]) -> None:
            if len(relative_parts) > _MAX_SCAN_DEPTH:
                raise RegistryError(
                    "record.location_invalid",
                    "",
                    "Challenge record is outside the canonical layout.",
                )
            try:
                with os.scandir(descriptor) as entries:
                    ordered = sorted(entries, key=lambda entry: entry.name)
                    for entry in ordered:
                        relative = (*relative_parts, entry.name)
                        if entry.is_symlink():
                            raise RegistryError(
                                "registry.symlink_forbidden",
                                "",
                                "Registry entries must not be symbolic links.",
                            )
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.endswith(".json"):
                                paths.append(self._registry_root.joinpath(*relative))
                                continue
                            child_descriptor = os.open(
                                entry.name,
                                os.O_RDONLY | _DIRECTORY | _NO_FOLLOW,
                                dir_fd=descriptor,
                            )
                            try:
                                walk(child_descriptor, relative)
                            finally:
                                os.close(child_descriptor)
                        elif entry.name.endswith(".json"):
                            paths.append(self._registry_root.joinpath(*relative))
            except RegistryError:
                raise
            except OSError as exc:
                raise RegistryError(
                    "registry.scan_failed", "", "Registry scan could not complete."
                ) from exc

        try:
            walk(root_descriptor, ())
        finally:
            os.close(root_descriptor)

        verification_descriptor = self._open_root()
        try:
            verified_identity = os.fstat(verification_descriptor)
        finally:
            os.close(verification_descriptor)
        if (root_identity.st_dev, root_identity.st_ino) != (
            verified_identity.st_dev,
            verified_identity.st_ino,
        ):
            raise RegistryError(
                "registry.root_changed", "", "Configured registry root changed."
            )
        return paths

    def scan(self) -> tuple[ChallengeRecord, ...]:
        """Load all final JSON records and reject duplicate embedded keys."""
        paths = self._scan_json_paths()
        loaded: list[tuple[Path, ChallengeRecord]] = []
        seen: set[ChallengeKey] = set()
        for path in paths:
            record = self._load_path(path)
            if record.key in seen:
                raise RegistryError(
                    "registry.duplicate_key",
                    "",
                    "Registry scan found a duplicate ChallengeKey.",
                )
            seen.add(record.key)
            loaded.append((path, record))

        for path, record in loaded:
            relative = path.relative_to(self._registry_root)
            if len(relative.parts) != 2 or relative.suffix != ".json":
                raise RegistryError(
                    "record.location_invalid",
                    "",
                    "Challenge record is outside the canonical layout.",
                )
            try:
                location_key = ChallengeKey(relative.parent.name, relative.stem)
            except ValueError as exc:
                raise RegistryError(
                    "record.location_invalid",
                    "",
                    "Challenge record is outside the canonical layout.",
                ) from exc
            if record.key != location_key:
                raise RegistryError(
                    "record.key_mismatch",
                    "",
                    "Embedded challenge identity does not match its file location.",
                )
        return tuple(
            record for _, record in sorted(loaded, key=lambda item: item[1].key)
        )

    def _atomic_write(self, record: ChallengeRecord) -> None:
        assert _NO_FOLLOW is not None
        payload = serialize_record(record).encode("utf-8")
        if len(payload) > _MAX_RECORD_BYTES:
            raise RegistryError(
                "record.too_large", "", "Challenge record exceeds the size limit."
            )
        directory_descriptor = self._open_challenge_directory(record.key)
        descriptor = -1
        temporary_name: str | None = None
        try:
            temporary_name = f".{record.version}.{secrets.token_hex(16)}.tmp"
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NO_FOLLOW,
                0o600,
                dir_fd=directory_descriptor,
            )
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.close(descriptor)
            descriptor = -1
            os.replace(
                temporary_name,
                f"{record.version}.json",
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
            )
            temporary_name = None
            try:
                os.fsync(directory_descriptor)
            except OSError:
                pass
        except (OSError, NotImplementedError, TypeError) as exc:
            raise RegistryError(
                "record.write_failed", "", "Challenge record could not be written."
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=directory_descriptor)
                except OSError:
                    pass
            os.close(directory_descriptor)

    def save(self, record: ChallengeRecord) -> ChallengeRecord:
        """Persist a draft/fixture record; LIVE is activation-only and immutable."""
        if not isinstance(record, ChallengeRecord):
            raise TypeError("record must be a ChallengeRecord")
        if record.status == "live":
            raise RegistryError(
                "mutation.live_forbidden",
                "/status",
                "Ordinary save cannot persist LIVE status.",
            )

        with self._key_lock(record.key):
            try:
                existing = self.load(record.challenge_id, record.version)
            except RegistryError as exc:
                if exc.code != "record.not_found":
                    raise
            else:
                if existing.status == "live":
                    raise RegistryError(
                        "mutation.live_immutable",
                        "/status",
                        "An existing LIVE record is immutable through ordinary save.",
                    )
            self._atomic_write(record)
        return record
