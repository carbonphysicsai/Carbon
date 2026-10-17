"""Owner-bound, bounded source upload for direct DEVELOPMENT graph recipes.

The signed research gateway supplies the owner. A caller can name only the
flat Level 4 manifest or a document named by its own SHA-256 digest. Partial
uploads are private workspace files; only verified complete bytes become
visible to graph task admission.
"""

from __future__ import annotations

import hashlib

from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy
from carbon.level4 import intake, staging
from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.lifecycle import ResearchTaskProviderError
from carbon.research.model import DirectStageSourceRequestV1, DirectStageSourceResultV1

from .profile import digest
from .research_workspace import (
    ResearchWorkspace,
    WorkspaceBoundExceeded,
    WorkspaceConflict,
    WorkspaceFileMissing,
)


def _verify_complete(name: str, body: bytes, fingerprint: str) -> None:
    if digest(body) != fingerprint:
        raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    if name != staging.WORKSPACE_MANIFEST:
        return
    try:
        manifest = parse_strategy(body, max_bytes=intake.BOUNDS["manifest_bytes"])
    except MalformedStrategy:
        raise ResearchTaskProviderError(
            ResearchServiceErrorCode.REFERENCE_MISMATCH
        ) from None
    documents = manifest.get("documents") if type(manifest) is dict else None
    if (
        type(documents) is not dict
        or not set(documents) <= {"forward", "loss", "init", "init_spec"}
        or any(
            type(document) is not str
            or len(document) != 71
            or not document.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in document[7:])
            for document in documents.values()
        )
    ):
        raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)


def stage_source(
    ledger, owner: str, request: DirectStageSourceRequestV1
) -> DirectStageSourceResultV1:
    """Append/replay a verified chunk and publish only a complete file."""
    if type(request) is not DirectStageSourceRequestV1:
        raise TypeError("exact direct source request required")
    workspace = ResearchWorkspace(ledger, owner)
    name = request.name
    expected = request.expected_digest
    fingerprint = request.content_digest
    if name != staging.WORKSPACE_MANIFEST and name != (
        staging.WORKSPACE_PREFIX + fingerprint[7:] + ".json"
    ):
        raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    try:
        current = workspace.current_digest(name)
        if current == fingerprint:
            complete = workspace.get_bounded(name, request.total_bytes)
            if (
                len(complete) != request.total_bytes
                or complete[request.offset : request.offset + len(request.chunk)]
                != request.chunk
            ):
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
                )
            _verify_complete(name, complete, fingerprint)
            return DirectStageSourceResultV1(name, len(complete), fingerprint, True)
        if current != expected:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
            )
        identity = (
            name
            + "\0"
            + fingerprint
            + "\0"
            + str(request.total_bytes)
            + "\0"
            + (expected or "")
        ).encode("ascii")
        partial_name = "upload-" + hashlib.sha256(identity).hexdigest()
        try:
            partial = workspace.get_bounded(partial_name, request.total_bytes)
        except WorkspaceFileMissing:
            partial = b""
        offset = request.offset
        end = offset + len(request.chunk)
        if offset > len(partial) or (
            offset < len(partial) and partial[offset:end] != request.chunk
        ):
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
            )
        if offset == len(partial):
            body = partial + request.chunk
            if len(body) > request.total_bytes:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        else:
            body = partial
        if len(body) == request.total_bytes:
            _verify_complete(name, body, fingerprint)
            workspace.put(name, body, expected_digest=expected)
            return DirectStageSourceResultV1(name, len(body), fingerprint, True)
        if offset == len(partial):
            workspace.put(
                partial_name,
                body,
                expected_digest=digest(partial) if partial else None,
            )
        return DirectStageSourceResultV1(name, len(body), fingerprint, False)
    except WorkspaceConflict:
        raise ResearchTaskProviderError(
            ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
        ) from None
    except WorkspaceBoundExceeded:
        raise ResearchTaskProviderError(
            ResearchServiceErrorCode.BOUND_EXCEEDED
        ) from None
