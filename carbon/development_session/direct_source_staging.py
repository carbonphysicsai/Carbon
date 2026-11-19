"""Owner-bound, bounded source upload for direct DEVELOPMENT graph recipes.

The signed research gateway supplies the owner. A caller can name only the
flat Level 4 manifest or a document named by its own SHA-256 digest. Partial
uploads are private files of the owner's campaign; only verified complete
bytes become visible to graph task admission.

APPEND, NOT REWRITE (live 116, 19 Nov 2026: chunks are at most 8 KiB, and each
one stored the WHOLE partial again as a new content-addressed workspace object,
never deleting the one it replaced, so a 1 MiB upload left ~64 MiB of superseded
copies and every later chunk's storage scan walked them all). A partial upload
is one append-only file, ``<campaign>/workspace-partials/<owner id>/upload-<id>``: its
length IS the count of received bytes (nothing else to keep in step, exact
across restarts and crashes); a chunk is offset-checked and appended; the
complete file is read once, verified and published as before. The storage
check runs at the same point (before the chunk is accepted) with the same
amount as before (the whole partial plus the chunk, plus the 64 KiB margin).
A partial written by the earlier layout (a workspace row) is continued from
that row.
"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

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


def _partial_name(request: DirectStageSourceRequestV1) -> str:
    identity = (
        request.name
        + "\0"
        + request.content_digest
        + "\0"
        + str(request.total_bytes)
        + "\0"
        + (request.expected_digest or "")
    ).encode("ascii")
    return "upload-" + hashlib.sha256(identity).hexdigest()


_PARTIALS = "workspace-partials"
#: One lock per partial upload (campaign root, upload id): a stage of the same upload is serial even on a path that does
#: not hold the intake's owner lock; different uploads and owners never wait on each other here.
_UPLOAD_LOCKS: dict = {}
_UPLOAD_LOCKS_GUARD = threading.Lock()


def _upload_lock(ledger, owner, partial_name):
    key = (str(ledger.root), owner, partial_name)
    with _UPLOAD_LOCKS_GUARD:
        return _UPLOAD_LOCKS.setdefault(key, threading.Lock())


def _partial_path(ledger, owner, partial_name, *, create=True) -> Path:
    """The owner's own append file (a ledger may hold several owners: each has its own directory); ``create`` False
    makes no directory (a read)."""
    root = Path(ledger.root) / _PARTIALS
    directory = root / hashlib.sha256(owner.encode()).hexdigest()
    if create:
        root.mkdir(mode=0o700, exist_ok=True)
        directory.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or directory.is_symlink():
        raise ValueError("campaign symlink rejected")
    path = directory / partial_name
    if path.is_symlink():
        raise ValueError("campaign symlink rejected")
    return path


def _fsync_write(path: Path, body: bytes) -> None:
    staged = path.with_name(path.name + ".staging")
    staged.unlink(missing_ok=True)
    handle = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(handle, "wb") as out:
        out.write(body)
        out.flush()
        os.fsync(out.fileno())
    os.replace(staged, path)


def _partial(ledger, owner, request):
    """``(path, received bytes)`` of ``owner``'s partial upload for ``request``: the append file, else one written by
    the earlier layout (a workspace row, read bounded as before and moved into the append file once), else none (0).
    An existing partial longer than the file refuses (`WorkspaceBoundExceeded`) before any byte is read.
    """
    partial_name = _partial_name(request)
    path = _partial_path(ledger, owner, partial_name)
    if path.is_file():
        size = path.stat().st_size
        if size > request.total_bytes:
            raise WorkspaceBoundExceeded("workspace artifact exceeds read bound")
        return path, size
    try:
        earlier = ResearchWorkspace(ledger, owner).get_bounded(
            partial_name, request.total_bytes
        )
    except WorkspaceFileMissing:
        return path, 0
    _fsync_write(path, earlier)
    return path, len(earlier)


def _read(path: Path, start: int, length: int) -> bytes:
    with path.open("rb") as source:
        source.seek(start)
        return source.read(length)


def continuation_at(ledger, owner: str, request) -> bool:
    """Whether ``request`` continues ``owner``'s OWN partial upload of that file exactly at its current length (offset > 0
    and == the bytes already staged). A read only: nothing is staged or changed. The R89 chunk bucket's test (Validator-2B
    7 Nov): a first chunk, a replayed one, or one naming an upload this owner does not hold is a request, not a chunk.
    """
    if (
        type(request) is not DirectStageSourceRequestV1
        or type(request.offset) is not int
        or request.offset <= 0
    ):
        return False
    try:
        partial_name = _partial_name(request)
        path = _partial_path(ledger, owner, partial_name, create=False)
        if path.is_file():
            size = path.stat().st_size
            return size <= request.total_bytes and size == request.offset
        partial = ResearchWorkspace(ledger, owner).get_bounded(
            partial_name, request.total_bytes
        )
    except (WorkspaceFileMissing, WorkspaceBoundExceeded, ValueError, OSError):
        return False
    return len(partial) == request.offset


def _append(ledger, workspace, request, name, fingerprint, expected):
    """One chunk of ``workspace.owner``'s partial upload, the same decisions as the earlier rewrite: a chunk past the received bytes, or one
    that differs from the bytes already held at its offset, is a conflict; a replay of held bytes changes nothing; the
    storage check sees the whole partial plus the chunk before it is accepted; the complete file is verified and
    published, then its partial removed."""
    path, size = _partial(ledger, workspace.owner, request)
    offset = request.offset
    chunk = request.chunk
    end = offset + len(chunk)
    if offset > size:
        raise ResearchTaskProviderError(ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT)
    tail = chunk
    if offset < size:
        held = _read(path, offset, end - offset)
        if held != chunk:
            if not (end > size and chunk.startswith(held)):
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
                )
            # the held bytes are this chunk's first bytes (a torn append, or a resend from an earlier offset): only
            # the rest is new (V2, 19 Nov: same bytes accepted; a differing byte still refuses; the file never shrinks)
            tail = chunk[size - offset :]
        else:
            tail = b""  # a replay of held bytes
    received = size + len(tail)
    if received > request.total_bytes:
        raise ResearchTaskProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    if received == request.total_bytes:
        # the completing chunk: the whole file is built and verified IN MEMORY before anything is written, so a chunk
        # that fails the digest leaves the partial exactly as it was (as the earlier rewrite did); `put` runs the
        # storage check of the published file, as before
        body = (_read(path, 0, size + 1) if size else b"") + tail
        if len(body) != request.total_bytes:
            raise ResearchTaskProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        _verify_complete(name, body, fingerprint)
        workspace.put(name, body, expected_digest=expected)
        path.unlink(missing_ok=True)
        return DirectStageSourceResultV1(name, received, fingerprint, True)
    if tail:
        # the same amount the earlier rewrite admitted at this point: the whole partial with the chunk, plus 64 KiB
        ledger.check_storage(received + 65536)
        with path.open("ab") as out:
            out.write(tail)
            out.flush()
            os.fsync(out.fileno())
    return DirectStageSourceResultV1(name, received, fingerprint, False)


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
            # a replace that names a file the receiver no longer holds is not a conflict with another file: say so
            # (REFERENCE_NOT_FOUND, "no manifest held"), so the miner re-stages instead of hunting for a digest
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REFERENCE_NOT_FOUND
                if current is None and expected is not None
                else ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
            )
        with _upload_lock(ledger, owner, _partial_name(request)):
            return _append(ledger, workspace, request, name, fingerprint, expected)
    except WorkspaceConflict:
        raise ResearchTaskProviderError(
            ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
        ) from None
    except WorkspaceBoundExceeded:
        raise ResearchTaskProviderError(
            ResearchServiceErrorCode.BOUND_EXCEEDED
        ) from None
