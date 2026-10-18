"""Pinned, validator-owned index of one Challenge's evaluation material.

The manifest is an operator-edited index, not a new score engine or case bank.
Its public and private roles are deliberately separate. A trusted caller pins
the exact manifest bytes at admission and verifies each artifact at use; a
changed or missing artifact is infrastructure unavailability, never a model
failure. This DEVELOPMENT interface grants no scientific or LIVE authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from carbon.challenge_validator.hidden_batch_store import references_digest
from carbon.challenge_validator.interface import digest as document_digest
from carbon.registry.digest import (
    ArtifactAccessError,
    digest_artifact,
    is_sha256_digest,
    read_verified_artifact_bytes,
)

SCHEMA = "carbon.challenge-evaluation-pack.v1"
MAX_MANIFEST_BYTES = 64 * 1024
PUBLIC_ROLES = frozenset(
    {
        "construction_kit",
        "interface",
        "train",
        "physics_contract",
        "accuracy_definition",
        "important_limit_definition",
        "design_objective",
    }
)
PRIVATE_ROLES = frozenset(
    {"case_bank", "reference_rows", "solver_evidence", "score_pack"}
)
INLINE_ROLES = PUBLIC_ROLES - {"train"}
UNAVAILABLE = "HUMAN_INPUT"


class EvaluationPackUnavailable(ValueError):
    """A stable, non-scientific refusal for missing or changed pack material."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _strict_json(payload: bytes) -> object:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EvaluationPackUnavailable("evaluation_pack.duplicate_key")
            result[key] = value
        return result

    def constant(_value):
        raise EvaluationPackUnavailable("evaluation_pack.nonfinite")

    try:
        if payload.startswith(b"\xef\xbb\xbf"):
            raise EvaluationPackUnavailable("evaluation_pack.bom")
        return json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=unique,
            parse_constant=constant,
        )
    except EvaluationPackUnavailable:
        raise
    except (UnicodeError, RecursionError, ValueError) as exc:
        raise EvaluationPackUnavailable("evaluation_pack.json") from exc


def _inline_bytes(value: object) -> bytes:
    if type(value) is not dict or not value:
        raise EvaluationPackUnavailable("evaluation_pack.inline_value")
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EvaluationPackUnavailable("evaluation_pack.inline_value") from exc


def _roles(value: object, names: frozenset[str], scope: str) -> dict:
    if type(value) is not dict or set(value) != names:
        raise EvaluationPackUnavailable("evaluation_pack." + scope + "_roles")
    normalized = {}
    for role, entry in value.items():
        if entry == UNAVAILABLE:
            normalized[role] = entry
            continue
        if (
            scope == "private"
            and role == "case_bank"
            and type(entry) is dict
            and entry.get("kind") == "hidden_batch_store"
        ):
            if set(entry) not in (
                {"kind"},
                {"kind", "fingerprint", "references_digest"},
            ) or (
                "fingerprint" in entry
                and (
                    not is_sha256_digest(entry["fingerprint"])
                    or not is_sha256_digest(entry["references_digest"])
                )
            ):
                raise EvaluationPackUnavailable("evaluation_pack.bank_entry")
            normalized[role] = entry
            continue
        if type(entry) is dict and "inline" in entry:
            if role not in INLINE_ROLES or set(entry) != {"inline", "sha256"}:
                raise EvaluationPackUnavailable("evaluation_pack.inline_entry")
            payload = _inline_bytes(entry["inline"])
            if not is_sha256_digest(entry["sha256"]) or not hmac.compare_digest(
                _digest_bytes(payload), entry["sha256"]
            ):
                raise EvaluationPackUnavailable("evaluation_pack.inline_digest")
            normalized[role] = {"inline_bytes": payload, "sha256": entry["sha256"]}
            continue
        if (
            type(entry) is not dict
            or set(entry) != {"path", "sha256"}
            or type(entry["path"]) is not str
            or not is_sha256_digest(entry["sha256"])
        ):
            raise EvaluationPackUnavailable("evaluation_pack." + scope + "_entry")
        # The shared artifact reader enforces relative path safety at access.
        # Reject malformed paths at admission too, without opening a file.
        path = entry["path"]
        if (
            not path
            or "\\" in path
            or ":" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or any(ord(char) < 32 or ord(char) == 127 for char in path)
        ):
            raise EvaluationPackUnavailable("evaluation_pack.artifact_path")
        normalized[role] = entry
    return normalized


def _digest_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class EvaluationPackSnapshot:
    """Exact admission identity and role pins; no mutable file contents cached."""

    manifest_digest: str
    challenge_id: str
    challenge_version: str
    pack_version: str
    public: Mapping[str, object]
    private: Mapping[str, object]

    def public_projection(self) -> dict:
        """Allow-listed metadata only; no private roles, paths or digest."""
        return {
            "schema": "carbon.challenge-evaluation-public.v1",
            "challenge": {"id": self.challenge_id, "version": self.challenge_version},
            "pack_version": self.pack_version,
            "roles": {
                name: (
                    {"status": "AVAILABLE", "sha256": value["sha256"]}
                    if value != UNAVAILABLE
                    else {"status": UNAVAILABLE}
                )
                for name, value in self.public.items()
            },
        }

    def missing_roles(self) -> dict[str, tuple[str, ...]]:
        """Report explicit unfinished data without treating it as a zero score."""
        return {
            "public": tuple(
                sorted(k for k, v in self.public.items() if v == UNAVAILABLE)
            ),
            "private": tuple(
                sorted(k for k, v in self.private.items() if v == UNAVAILABLE)
            ),
        }

    def run_bindings_required(self) -> tuple[str, ...]:
        """Name roles whose exact data identity is selected per run."""
        bank = self.private["case_bank"]
        return (
            ("case_bank",)
            if bank != UNAVAILABLE
            and bank.get("kind") == "hidden_batch_store"
            and "fingerprint" not in bank
            else ()
        )

    def verify_available(
        self, public_root: Path, private_root: Path, *, hidden_store=None
    ) -> dict[str, tuple[str, ...]]:
        """Check every supplied role at admission; missing roles stay explicit.

        The caller decides which roles a given evaluation requires and applies
        each artifact's existing semantic validator. This method checks only
        storage identity, not scientific adequacy or scoring readiness.
        """
        for roles, root in (
            (self.public, public_root),
            (self.private, private_root),
        ):
            for role, entry in roles.items():
                if entry == UNAVAILABLE:
                    continue
                if role == "case_bank" and entry.get("kind") == "hidden_batch_store":
                    if hidden_store is None:
                        raise EvaluationPackUnavailable(
                            "evaluation_pack.bank_store_unavailable"
                        )
                    if "fingerprint" in entry:
                        self.resolve_hidden_batch(hidden_store)
                    continue
                if "inline_bytes" in entry:
                    if not hmac.compare_digest(
                        _digest_bytes(entry["inline_bytes"]), entry["sha256"]
                    ):
                        raise EvaluationPackUnavailable("evaluation_pack.inline_digest")
                    continue
                try:
                    actual = digest_artifact(root, entry["path"])
                except ArtifactAccessError as exc:
                    raise EvaluationPackUnavailable(
                        "evaluation_pack." + exc.code
                    ) from exc
                if not hmac.compare_digest(actual, entry["sha256"]):
                    raise EvaluationPackUnavailable(
                        "evaluation_pack.artifact.digest_mismatch"
                    )
        return self.missing_roles()

    def read_role(self, root: Path, scope: str, role: str, *, max_bytes: int) -> bytes:
        """Read a pinned artifact, refusing edits after the run was admitted."""
        roles = (
            self.public
            if scope == "public"
            else self.private if scope == "private" else None
        )
        if roles is None or role not in roles:
            raise EvaluationPackUnavailable("evaluation_pack.role")
        entry = roles[role]
        if entry == UNAVAILABLE:
            raise EvaluationPackUnavailable("evaluation_pack.role_unavailable")
        if "inline_bytes" in entry:
            if type(max_bytes) is not int or max_bytes <= 0:
                raise EvaluationPackUnavailable(
                    "evaluation_pack.artifact.limit_invalid"
                )
            if len(entry["inline_bytes"]) > max_bytes:
                raise EvaluationPackUnavailable("evaluation_pack.artifact.too_large")
            return entry["inline_bytes"]
        if "path" not in entry:
            raise EvaluationPackUnavailable("evaluation_pack.role_requires_store")
        try:
            return read_verified_artifact_bytes(
                root, entry["path"], entry["sha256"], max_bytes=max_bytes
            )
        except ArtifactAccessError as exc:
            raise EvaluationPackUnavailable("evaluation_pack." + exc.code) from exc

    def read_json_role(
        self, root: Path, scope: str, role: str, *, max_bytes: int
    ) -> object:
        """Decode a verified JSON role without a second consumer parser.

        This checks JSON syntax only. Existing role-specific contracts still
        validate its meaning; Score Packs keep their exact-byte loader.
        """
        return _strict_json(self.read_role(root, scope, role, max_bytes=max_bytes))

    def resolve_hidden_batch(
        self,
        store,
        *,
        fingerprint: str | None = None,
        expected_references_digest: str | None = None,
    ) -> dict:
        """Resolve one immutable existing HiddenBatchStore batch and refs.

        The store location and access authority come from the validator, never
        this manifest or a miner. No database file is copied or hashed as a
        surrogate snapshot.
        """
        entry = self.private["case_bank"]
        if entry == UNAVAILABLE:
            raise EvaluationPackUnavailable("evaluation_pack.role_unavailable")
        if entry.get("kind") != "hidden_batch_store":
            raise EvaluationPackUnavailable("evaluation_pack.bank_kind")
        pinned_fingerprint = entry.get("fingerprint", fingerprint)
        pinned_references = entry.get("references_digest", expected_references_digest)
        if (
            not is_sha256_digest(pinned_fingerprint)
            or not is_sha256_digest(pinned_references)
            or (fingerprint is not None and fingerprint != pinned_fingerprint)
            or (
                expected_references_digest is not None
                and expected_references_digest != pinned_references
            )
        ):
            raise EvaluationPackUnavailable("evaluation_pack.bank_run_pin")
        try:
            batch = store.batch(pinned_fingerprint)
            references = store.references(pinned_fingerprint)
            if (
                batch["state"] != "COMPLETE"
                or batch["references_digest"] != pinned_references
                or batch["document"].get("challenge")
                != {"id": self.challenge_id, "version": self.challenge_version}
                or document_digest(batch["document"]) != pinned_fingerprint
                or references_digest(references) != pinned_references
            ):
                raise EvaluationPackUnavailable("evaluation_pack.bank_changed")
        except EvaluationPackUnavailable:
            raise
        except Exception as exc:
            raise EvaluationPackUnavailable("evaluation_pack.bank_unavailable") from exc
        return {"document": batch["document"], "references": references}


@dataclass(frozen=True)
class PreparedEvaluationPack:
    """Internal sealed bytes to retain write-once beside the run receipt."""

    draft_digest: str
    sealed_bytes: bytes
    snapshot: EvaluationPackSnapshot


def parse_pack(
    payload: bytes,
    *,
    expected_digest: str,
    challenge_id: str,
    challenge_version: str,
) -> EvaluationPackSnapshot:
    """Validate exact pinned bytes, identity and both closed role sets."""
    if type(payload) is not bytes or len(payload) > MAX_MANIFEST_BYTES:
        raise EvaluationPackUnavailable("evaluation_pack.size")
    if not is_sha256_digest(expected_digest):
        raise EvaluationPackUnavailable("evaluation_pack.expected_digest")
    actual = _digest_bytes(payload)
    if actual != expected_digest:
        raise EvaluationPackUnavailable("evaluation_pack.digest_mismatch")
    body = _strict_json(payload)
    if (
        type(body) is not dict
        or set(body) != {"schema", "challenge", "pack_version", "public", "private"}
        or body["schema"] != SCHEMA
    ):
        raise EvaluationPackUnavailable("evaluation_pack.schema")
    challenge = body["challenge"]
    if (
        type(challenge) is not dict
        or set(challenge) != {"id", "version"}
        or type(challenge["id"]) is not str
        or not challenge["id"]
        or type(challenge["version"]) is not str
        or not challenge["version"]
        or challenge["id"] != challenge_id
        or challenge["version"] != challenge_version
        or type(body["pack_version"]) is not str
        or not body["pack_version"]
    ):
        raise EvaluationPackUnavailable("evaluation_pack.identity")
    public = _roles(body["public"], PUBLIC_ROLES, "public")
    private = _roles(body["private"], PRIVATE_ROLES, "private")

    def freeze(roles):
        return MappingProxyType(
            {
                name: MappingProxyType(value) if type(value) is dict else value
                for name, value in roles.items()
            }
        )

    return EvaluationPackSnapshot(
        actual,
        challenge["id"],
        challenge["version"],
        body["pack_version"],
        freeze(public),
        freeze(private),
    )


def load_pack(
    root: Path,
    relative_path: str,
    *,
    expected_digest: str,
    challenge_id: str,
    challenge_version: str,
) -> EvaluationPackSnapshot:
    """Read the one operator manifest through the existing secure artifact API."""
    try:
        payload = read_verified_artifact_bytes(
            root, relative_path, expected_digest, max_bytes=MAX_MANIFEST_BYTES
        )
    except ArtifactAccessError as exc:
        raise EvaluationPackUnavailable("evaluation_pack." + exc.code) from exc
    return parse_pack(
        payload,
        expected_digest=expected_digest,
        challenge_id=challenge_id,
        challenge_version=challenge_version,
    )


def freeze_pack(
    root: Path,
    relative_path: str,
    *,
    challenge_id: str,
    challenge_version: str,
) -> EvaluationPackSnapshot:
    """Trusted admission helper; compute and return the exact manifest pin.

    The receiver must persist ``manifest_digest`` in its run registration,
    then call ``load_pack`` with that pin for the run. This helper is never
    called with participant-selected paths.
    """
    try:
        expected_digest = digest_artifact(root, relative_path)
    except ArtifactAccessError as exc:
        raise EvaluationPackUnavailable("evaluation_pack." + exc.code) from exc
    return load_pack(
        root,
        relative_path,
        expected_digest=expected_digest,
        challenge_id=challenge_id,
        challenge_version=challenge_version,
    )


def prepare_pack(
    root: Path,
    relative_path: str,
    *,
    public_root: Path,
    private_root: Path,
    challenge_id: str,
    challenge_version: str,
) -> PreparedEvaluationPack:
    """Turn one trusted editable manifest into an immutable, pinned snapshot.

    The editor may use ``{"path": "..."}`` without copying artifact hashes.
    The trusted caller stores ``sealed_bytes`` write-once under the returned
    snapshot digest and records that digest in the run. ``load_pack`` consumes
    only those sealed bytes. Preparing never rewrites the operator's draft or
    changes an earlier run's snapshot.
    """
    try:
        draft_digest = digest_artifact(root, relative_path)
        payload = read_verified_artifact_bytes(
            root, relative_path, draft_digest, max_bytes=MAX_MANIFEST_BYTES
        )
    except ArtifactAccessError as exc:
        raise EvaluationPackUnavailable("evaluation_pack." + exc.code) from exc
    body = _strict_json(payload)
    if (
        type(body) is not dict
        or set(body) != {"schema", "challenge", "pack_version", "public", "private"}
        or body["schema"] != SCHEMA
        or type(body["public"]) is not dict
        or set(body["public"]) != PUBLIC_ROLES
        or type(body["private"]) is not dict
        or set(body["private"]) != PRIVATE_ROLES
    ):
        raise EvaluationPackUnavailable("evaluation_pack.schema")
    for scope, roles, artifact_root in (
        ("public", body["public"], public_root),
        ("private", body["private"], private_root),
    ):
        for role, entry in roles.items():
            if entry == UNAVAILABLE or (
                scope == "private"
                and role == "case_bank"
                and type(entry) is dict
                and entry.get("kind") == "hidden_batch_store"
            ):
                continue
            if type(entry) is dict and "inline" in entry:
                if role not in INLINE_ROLES or set(entry) not in (
                    {"inline"},
                    {"inline", "sha256"},
                ):
                    raise EvaluationPackUnavailable("evaluation_pack.inline_entry")
                roles[role] = {
                    "inline": entry["inline"],
                    "sha256": _digest_bytes(_inline_bytes(entry["inline"])),
                }
                continue
            if (
                type(entry) is not dict
                or set(entry)
                not in (
                    {"path"},
                    {"path", "sha256"},
                )
                or type(entry["path"]) is not str
            ):
                raise EvaluationPackUnavailable("evaluation_pack." + scope + "_entry")
            try:
                observed = digest_artifact(artifact_root, entry["path"])
            except ArtifactAccessError as exc:
                raise EvaluationPackUnavailable("evaluation_pack." + exc.code) from exc
            roles[role] = {"path": entry["path"], "sha256": observed}
    try:
        sealed = (
            json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EvaluationPackUnavailable("evaluation_pack.json") from exc
    snapshot = parse_pack(
        sealed,
        expected_digest=_digest_bytes(sealed),
        challenge_id=challenge_id,
        challenge_version=challenge_version,
    )
    return PreparedEvaluationPack(draft_digest, sealed, snapshot)
