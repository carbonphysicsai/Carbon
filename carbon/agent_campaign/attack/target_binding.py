"""Operator-only public Constructor target pins; no execution authority.

Capture a bounded, independently pinned v3 export through no-follow directory
descriptors. Metadata reconstruction uses the captured bytes, never the source
again. Loading a target does not attest a worker, an attack or mainnet parity.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from carbon.development_session.profile import canonical, digest

SCHEMA = "carbon.graphite.public-target-binding.v1"
MODE = "public_target_v1"
PIN_SCHEMA = "carbon.graphite.target-session-pin.v1"
RUNTIME_UNAVAILABLE = "target_verification_backend_unavailable"
FILE_BYTES = 8 << 20  # Same per-file ceiling as the existing L4 envelope.
MANIFEST_BYTES = 1 << 20
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_PRIVATE_PARTS = frozenset(
    {
        ".git",
        ".carbon",
        ".claude",
        "ledger",
        "sealed",
        "holdout",
        "private",
        "attacker",
        "attacker-dry-run",
        "constructor",
    }
)
_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "proposal_id",
        "run_id",
        "files",
        "contract_digest",
        "record_sequence",
        "recipe_digest",
        "artifact",
        "authority_granted",
        "official_eligible",
    }
)


class TargetRefused(ValueError):
    """A closed refusal code, never source paths, bytes or exception text."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _sha(value):
    if type(value) is not str or not _SHA.fullmatch(value):
        raise TargetRefused("target_digest_invalid")
    return value


def _json(raw):
    def pairs(values):
        out = {}
        for key, value in values:
            if key in out:
                raise TargetRefused("target_json_duplicate_key")
            out[key] = value
        return out

    def invalid(_value):
        raise TargetRefused("target_json_nonfinite")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError) as failure:
        if isinstance(failure, TargetRefused):
            raise
        raise TargetRefused("target_json_invalid") from None


def _read(fd, name, limit):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with contextlib.ExitStack() as cleanup:
        opened = os.open(name, flags, dir_fd=fd)
        cleanup.callback(os.close, opened)
        before = os.fstat(opened)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise TargetRefused("target_file_not_regular_single_link")
        if before.st_size > limit:
            raise TargetRefused("target_file_over_bound")
        chunks, size = [], 0
        while chunk := os.read(opened, min(65536, limit + 1 - size)):
            size += len(chunk)
            if size > limit:
                raise TargetRefused("target_file_over_bound")
            chunks.append(chunk)
        after = os.fstat(opened)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise TargetRefused("target_file_changed_during_capture")
        return b"".join(chunks)


def _directory(path, cleanup):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise TargetRefused("target_directory_absolute_required")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current = os.open(path.anchor, flags)
    cleanup.callback(os.close, current)
    for part in path.parts[1:]:
        current = os.open(part, flags, dir_fd=current)
        cleanup.callback(os.close, current)
    return current


def _submission_scope(raw, adapter):
    from carbon.level4 import submission

    manifest = _json(raw)
    if (
        type(manifest) is not dict
        or manifest.get("schema") != submission.SCHEMA
        or manifest.get("challenge") != adapter.challenge_id
        or manifest.get("level") != adapter.level
    ):
        raise TargetRefused("target_submission_scope_mismatch")


def _capture(public_root, name, expected_manifest, delivery):
    # The public root is trusted operator configuration, never a miner field.
    # A path/name or a claimed public/executed flag cannot mint runtime evidence.
    if os.name != "posix" or os.open not in os.supports_dir_fd:
        raise TargetRefused("target_secure_filesystem_intake_unavailable")
    if type(name) is not str or not _NAME.fullmatch(name):
        raise TargetRefused("target_bundle_name_invalid")
    root = Path(public_root)
    if not root.is_absolute():
        raise TargetRefused("target_public_root_absolute_required")
    if any(part.lower() in _PRIVATE_PARTS or part == ".." for part in root.parts):
        raise TargetRefused("target_source_not_public_import")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with contextlib.ExitStack() as cleanup:
        current = _directory(root, cleanup)
        folder = os.open(name, flags, dir_fd=current)
        cleanup.callback(os.close, folder)
        raw = _read(folder, "manifest.json", MANIFEST_BYTES)
        if digest(raw) != expected_manifest:
            raise TargetRefused("target_manifest_digest_mismatch")
        manifest = _json(raw)
        if type(manifest) is not dict or set(manifest) != _MANIFEST_KEYS:
            raise TargetRefused("target_manifest_shape_invalid")
        if (
            manifest["schema"] != delivery.BUNDLE_SCHEMA
            or manifest["authority_granted"] is not False
            or manifest["official_eligible"] is not False
        ):
            raise TargetRefused("target_public_v3_bundle_required")
        names = {*delivery.FILES, delivery.LEVEL4_ENVELOPE}
        files = manifest["files"]
        if type(files) is not dict or set(files) != names:
            raise TargetRefused("target_bundle_file_inventory_invalid")
        if set(os.listdir(folder)) != names | {"manifest.json"}:
            raise TargetRefused("target_bundle_file_inventory_invalid")
        captured = {"manifest.json": raw}
        for filename in sorted(names):
            _sha(files[filename])
            body = _read(folder, filename, FILE_BYTES)
            if digest(body) != files[filename]:
                raise TargetRefused("target_bundle_file_digest_mismatch")
            captured[filename] = body
        return manifest, captured


@dataclass(frozen=True, slots=True, init=False)
class TargetBinding:
    """Validated immutable public bytes/pins, not a trusted worker receipt."""

    _pin: bytes
    _files: tuple

    def __init__(self):
        raise TargetRefused("target_binding_requires_validated_intake")

    def record(self):
        return _json(self._pin)

    @property
    def pin(self):
        return digest(self._pin)

    def file(self, name):
        for filename, body in self._files:
            if filename == name:
                return body
        raise TargetRefused("target_captured_file_unavailable")

    def strategy(self):
        return _json(self.file("strategy.json"))

    def recipe(self):
        return _json(self.file("recipe.json"))

    def workspace(self):
        from carbon.level4 import staging

        _, manifest, files = staging.from_envelope(
            _json(self.file("level4-envelope.json"))
        )
        return staging.workspace(manifest, files)


def require(value, adapter):
    if type(value) is not TargetBinding:
        raise TargetRefused("target_binding_requires_validated_intake")
    try:
        pin = value.record()
        if (
            pin["schema"] != SCHEMA
            or pin["challenge_id"] != adapter.challenge_id
            or pin["level"] != adapter.level
            or pin["variant_digest"] != adapter.contract_digest
        ):
            raise TargetRefused("target_adapter_binding_mismatch")
    except (AttributeError, KeyError, TypeError):
        raise TargetRefused("target_binding_requires_validated_intake") from None
    return value


def load(public_root, name, expected_manifest, adapter, *, repository):
    """Capture an operator-vetted public export; compile metadata only."""
    expected_manifest = _sha(expected_manifest)
    if adapter.level != 4:
        raise TargetRefused("target_level_unavailable")
    # Refuse unsupported hosts before importing POSIX Graphite components.
    if os.name != "posix" or os.open not in os.supports_dir_fd:
        raise TargetRefused("target_secure_filesystem_intake_unavailable")
    from carbon.agent_campaign.graphite import delivery
    from carbon.level4 import staging
    from carbon.reconstruction.artifact_identity import build_identity

    from . import knowledge

    try:
        manifest, captured = _capture(public_root, name, expected_manifest, delivery)
        strategy = _json(captured["strategy.json"])
        recipe = _json(captured["recipe.json"])
        envelope = _json(captured[delivery.LEVEL4_ENVELOPE])
        for body in captured.values():
            if knowledge.sealed(body.decode("utf-8")) or knowledge.held_out(
                body.decode("utf-8")
            ):
                raise TargetRefused("target_material_not_public")
        submission, raw_manifest, _ = staging.from_envelope(envelope)
        _submission_scope(raw_manifest, adapter)
        from carbon.battery.level4 import FIELD

        development = recipe.get("development") if type(recipe) is dict else None
        challenge = recipe.get("challenge") if type(recipe) is dict else None
        if (
            type(strategy) is not dict
            or strategy.get("challenge_id") != adapter.challenge_id
            or type(challenge) is not dict
            or set(challenge) != {"id", "version"}
            or challenge["id"] != adapter.challenge_id
            or type(development) is not dict
            or development.get("level") != adapter.level
            or development.get("variant_digest") != adapter.contract_digest
            or (strategy.get("parameters") or {}).get(FIELD) != submission
        ):
            raise TargetRefused("target_construction_binding_mismatch")
        _sha(manifest["contract_digest"])
        _sha(manifest["artifact"])
        if (
            recipe.get("contract_digest") != manifest["contract_digest"]
            or build_identity(recipe) != manifest["artifact"]
        ):
            raise TargetRefused("target_build_identity_mismatch")
        with tempfile.TemporaryDirectory(prefix="carbon-public-target-") as scratch:
            for filename, body in captured.items():
                (Path(scratch) / filename).write_bytes(body)
            checked = delivery.clean_rebuild(Path(scratch), repository=repository)
        if checked["status"] != "REBUILT":
            raise TargetRefused("target_metadata_rebuild_mismatch")
        pin = canonical(
            {
                "schema": SCHEMA,
                "manifest_digest": expected_manifest,
                "challenge_id": adapter.challenge_id,
                "challenge": challenge,
                "level": adapter.level,
                "contract_digest": manifest["contract_digest"],
                "variant_digest": adapter.contract_digest,
                "submission_digest": submission,
                "build_artifact": manifest["artifact"],
            }
        )
        value = object.__new__(TargetBinding)
        object.__setattr__(value, "_pin", pin)
        object.__setattr__(value, "_files", tuple(sorted(captured.items())))
        return require(value, adapter)
    except TargetRefused:
        raise
    except Exception:  # noqa: BLE001 - never echo untrusted bytes or paths
        raise TargetRefused("target_intake_or_rebuild_unavailable") from None


def session_pin(store, number, target, *, resume, adapter):
    """Freeze targeted versus legacy mode before dispatch; no target drift."""
    if type(number) is not int or number < 1:
        raise TargetRefused("target_session_number_invalid")
    if target is not None:
        require(target, adapter)
    elif not os.path.lexists(Path(store) / "target-pins"):
        return  # Unchanged legacy roots need no new directory or pin file.
    record = {
        "schema": PIN_SCHEMA,
        "mode": "family" if target is None else MODE,
        "target": None if target is None else target.record(),
    }
    if os.name != "posix" or os.open not in os.supports_dir_fd:
        if target is None and not (Path(store) / "target-pins").exists():
            return
        raise TargetRefused("target_secure_filesystem_intake_unavailable")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    name = f"session-{number}.json"
    try:
        with contextlib.ExitStack() as cleanup:
            root = _directory(Path(store).absolute(), cleanup)
            try:
                folder = os.open("target-pins", flags, dir_fd=root)
            except FileNotFoundError:
                if target is None:
                    return
                if resume:
                    raise TargetRefused("target_session_pin_missing") from None
                os.mkdir("target-pins", 0o700, dir_fd=root)
                folder = os.open("target-pins", flags, dir_fd=root)
            cleanup.callback(os.close, folder)
            try:
                previous = _json(_read(folder, name, MANIFEST_BYTES))
            except FileNotFoundError:
                previous = None
            if previous is not None:
                if previous != record:
                    raise TargetRefused("target_session_pin_changed")
                return
            if target is None:
                return  # Historical family sessions have no target pin.
            if resume:
                raise TargetRefused("target_session_pin_missing")
            opened = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=folder,
            )
            cleanup.callback(os.close, opened)
            body = canonical(record)
            while body:
                count = os.write(opened, body)
                if count <= 0:
                    raise TargetRefused("target_session_pin_write_failed")
                body = body[count:]
            os.fsync(opened)
    except TargetRefused:
        raise
    except (OSError, ValueError):
        raise TargetRefused("target_session_pin_unavailable_or_linked") from None


def scope(target, adapter):
    require(target, adapter)
    return {
        "mode": MODE,
        "target_pin": target.pin,
        "target": target.record(),
        "runtime_verification": "UNAVAILABLE",
    }
