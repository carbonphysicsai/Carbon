"""Evaluator-owned C-AUTH1 generation and isolated C-04 TRAIN label preparation."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from contextlib import suppress
from pathlib import Path

import numpy as np

from carbon.evaluation.enums import ReferenceFailureReason, ReferenceRunOutcome
from carbon.generators import burgers_dynamics
from carbon.generators.burgers_dynamics import (
    DOMAIN_LENGTH,
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    candidate_query,
    canonical_public_case_bytes,
    generate_development_case,
    requested_times,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.reconstruction.worker.model import DevelopmentWorkerProfile
from carbon.reference_runtime.controller import IsolatedBurgersReferenceController
from carbon.reference_runtime.model import (
    BurgersReferenceRole,
    build_reference_request,
    runtime_environment_digest,
)
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin

from .budget import SessionBudget
from .contracts import authored_contracts, build_contracts
from .profile import CHALLENGE, canonical, digest, profile_digest, profile_document


def write_once(path: Path, payload: bytes):
    """Write `path` once, owner-only; an existing file must hold exactly
    `payload`. The file appears whole or not at all: the bytes are written
    and synced beside it, then linked into place, which never replaces an
    existing file. A reader that sees the path never reads it half-written
    (a reader once read an empty campaign manifest between its creation and
    its write)."""
    if path.is_symlink():
        raise ValueError("symlink rejected")
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError("immutable session artifact conflict")
        return
    descriptor, staged = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staged, 0o600)
        try:
            os.link(staged, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != payload:
                raise ValueError("immutable session artifact conflict") from None
    finally:
        os.unlink(staged)


def link_once(source, path: Path, payload: bytes) -> bool:
    """`write_once` that stores the bytes ONCE on disk: when ``source`` is a regular file of this user (never a link)
    that holds exactly ``payload``, ``path`` becomes a hard link to it (the same inode: the same name and bytes for every
    reader, no copy; owner rule #13, live 116 19 Nov 2026: a counted grade copied its 12.6 MB graded predictions and
    its origin's files into each task root). ``source`` may be a tuple of candidate files, tried in order: the first
    that holds exactly ``payload`` is linked. Anything else (no source, other bytes, another user, a link, a filesystem
    that cannot link) is an ordinary `write_once`. Returns True when linked. Same immutability: an existing ``path``
    must hold exactly ``payload``; nothing is ever replaced.

    The linked inode is made owner-only (its group and other bits cleared) like `write_once`'s files, and is checked
    to be the very file whose bytes were compared (same device and inode after the link), else the link is removed
    and the next candidate is tried, else the bytes are written.
    """
    if path.is_symlink():
        raise ValueError("symlink rejected")
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError("immutable session artifact conflict")
        return False
    if _raw_note(path) is not None:
        if read_raw(path) != payload:
            raise ValueError("immutable session artifact conflict")
        return False
    compressed_source = False
    for candidate in source if type(source) is tuple else (source,):
        if candidate is None:
            continue
        # a source held COMPRESSED (`compress_raw`): ``path`` becomes the same compressed pair (its archive and note
        # linked, one inode each), never a raw copy, once the pair is shown to hold exactly ``payload``
        try:
            note = _raw_note(Path(candidate))
        except ValueError:
            note = None
        if note is not None:
            compressed_source = True
            if _link_compressed(Path(candidate), path, payload):
                return True
            continue
        linked = _link_from(candidate, path, payload)
        if linked is not None:
            return linked
    write_once(path, payload)
    if compressed_source:
        # the source was compressed but could not be linked here: store this copy compressed too
        compress_raw(path)
    return False


#: A retained file stored COMPRESSED (DATA, sre 21 Nov 2026: inference snapshot predictions.json was 90.6% of the door's
#: owner-ledger growth, ~10.7 GB/day of decimal text): ``<name>.gz`` (gzip, mtime 0) beside ``<name>.gz.raw.json``, the
#: note of the RAW bytes' sha256 and size. Every digest keeps binding the RAW bytes; `read_raw` returns them, checked.
COMPRESSED_SUFFIX = ".gz"
RAW_NOTE_SUFFIX = ".gz.raw.json"
RAW_NOTE_SCHEMA = "carbon.retained-raw-note.v1"


def _compressed(path: Path) -> Path:
    return path.with_name(path.name + COMPRESSED_SUFFIX)


def _raw_note_path(path: Path) -> Path:
    return path.with_name(path.name + RAW_NOTE_SUFFIX)


def _raw_note(path: Path) -> dict | None:
    """The RAW note of a compressed ``path`` (`RAW_NOTE_SCHEMA`), None when ``path`` is not stored compressed; ValueError
    for a note or archive that is a link or malformed (fail closed: never guess the raw bytes).
    """
    note = _raw_note_path(path)
    if not os.path.lexists(note):
        return None
    archive = _compressed(path)
    if note.is_symlink() or archive.is_symlink() or not archive.is_file():
        raise ValueError("retained snapshot file differs")
    try:
        value = json.loads(note.read_bytes())
    except ValueError:
        raise ValueError("retained snapshot file differs") from None
    if (
        type(value) is not dict
        or set(value) != {"schema", "sha256", "size"}
        or value["schema"] != RAW_NOTE_SCHEMA
        or type(value["sha256"]) is not str
        or len(value["sha256"]) != 64
        or type(value["size"]) is not int
        or value["size"] < 0
    ):
        raise ValueError("retained snapshot file differs")
    return value


def raw_exists(path) -> bool:
    """Whether ``path`` is held, raw (a regular file, never a link) or compressed (`COMPRESSED_SUFFIX` + its note)."""
    path = Path(path)
    if path.is_symlink():
        return False
    return path.is_file() or _raw_note(path) is not None


def raw_size(path) -> int:
    """The RAW size of ``path``: the file's own size, else its note's; FileNotFoundError when it is held neither way."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink rejected")
    if path.is_file():
        return path.stat().st_size
    note = _raw_note(path)
    if note is None:
        raise FileNotFoundError(str(path))
    return note["size"]


def read_raw(path, *, max_bytes=None) -> bytes:
    """The RAW bytes of ``path``: the file itself when it is held raw (every file written before compression, and every
    file nothing compresses), else ``<path>.gz`` decompressed and checked against its note's size and sha256 (ValueError
    "retained snapshot file differs" on any mismatch). ``max_bytes`` bounds the RAW size before anything is read.
    FileNotFoundError when it is held neither way."""
    import gzip
    import zlib

    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink rejected")
    if path.is_file():
        if max_bytes is not None and path.stat().st_size > max_bytes:
            raise ValueError("retained snapshot file oversized")
        return path.read_bytes()
    note = _raw_note(path)
    if note is None:
        raise FileNotFoundError(str(path))
    if max_bytes is not None and note["size"] > max_bytes:
        raise ValueError("retained snapshot file oversized")
    try:
        with gzip.open(_compressed(path), "rb") as stream:
            raw = stream.read(note["size"] + 1)
    except (OSError, EOFError, zlib.error):
        raise ValueError("retained snapshot file differs") from None
    if len(raw) != note["size"] or hashlib.sha256(raw).hexdigest() != note["sha256"]:
        raise ValueError("retained snapshot file differs")
    return raw


def compress_raw(path) -> bool:
    """Store ``path`` (a regular file of this user, never a link) COMPRESSED: ``<path>.gz`` (gzip level 6, mtime 0: the
    same bytes give the same archive) and its RAW note, each written once and synced, the archive read back and checked
    against the raw sha256, and only THEN the raw name removed. True when compressed; False when ``path`` is already held
    compressed. Other hard links to the raw inode keep it (their names still read raw); the raw bytes' digest is what
    every record already binds, so nothing it names changes."""
    import gzip

    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink rejected")
    if not path.is_file():
        if _raw_note(path) is not None:
            return False
        raise FileNotFoundError(str(path))
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    write_once(_compressed(path), gzip.compress(raw, compresslevel=6, mtime=0))
    write_once(
        _raw_note_path(path),
        canonical({"schema": RAW_NOTE_SCHEMA, "sha256": sha, "size": len(raw)}),
    )
    if gzip.decompress(_compressed(path).read_bytes()) != raw:
        raise ValueError("retained snapshot file differs")
    path.unlink()
    return True


#: A ledger's own stored objects (`store_once`) where it is not in a receiver's ``owners/`` layout.
INPUT_OBJECTS = "input-objects"
#: A receiver state root's door-wide stored objects (`store_once`): one file per bytes and mode, shared by every owner
#: ledger's op inputs and every retained grade file of the same bytes (owner rule #13; sre 20 Nov 2026).
DOOR_OBJECTS = "objects"


def ledger_objects(ledger_root) -> Path:
    """Where an owner ledger's op inputs are stored once: ``<state>/objects`` for a receiver's
    ``<state>/owners/<owner>/ledger``, else the ledger's own `INPUT_OBJECTS`."""
    root = Path(ledger_root)
    if root.name == "ledger" and root.parent.parent.name == "owners":
        return root.parent.parent.parent / DOOR_OBJECTS
    return root / INPUT_OBJECTS


def retained_objects(task_root):
    """Where a retained grade's files are stored once: ``<state>/objects`` for a receiver's
    ``<state>/auto-grade/artifacts/<task>``, else None (written as before)."""
    root = Path(task_root)
    if root.parent.name == "artifacts" and root.parent.parent.name == "auto-grade":
        return root.parent.parent.parent / DOOR_OBJECTS
    return None


def store_once(objects, path: Path, payload: bytes, mode: int) -> bool:
    """Place the NEW name ``path`` holding ``payload`` with ``mode`` as a hard link to ``objects``'
    ``<sha256>-<octal mode>`` file, storing that file first when absent (owner rule #13: identical bytes on disk once).
    Same name, bytes and mode for every reader. Anything that does not fit (no objects folder given, a linked or foreign
    folder or object, other bytes or mode, a filesystem or link count that refuses the link, a host without POSIX
    owners) is an ordinary `write_once` + chmod. Nothing stored is ever modified. True when linked.
    """
    if objects is not None and hasattr(os, "getuid"):
        objects = Path(objects)
        stored = objects / (
            hashlib.sha256(payload).hexdigest() + "-" + format(mode, "o")
        )
        try:
            objects.mkdir(mode=0o700, exist_ok=True)
            found = os.lstat(objects)
            if stat.S_ISDIR(found.st_mode) and found.st_uid == os.getuid():
                for _ in range(2):
                    if _link_stored(stored, path, payload, mode):
                        return True
                    if os.path.lexists(stored):
                        break
                    descriptor, staged = tempfile.mkstemp(prefix=".store.", dir=objects)
                    try:
                        with os.fdopen(descriptor, "wb") as stream:
                            stream.write(payload)
                            stream.flush()
                            os.fsync(stream.fileno())
                        os.chmod(staged, mode)
                        with suppress(FileExistsError):
                            os.link(staged, stored)
                    finally:
                        os.unlink(staged)
        except OSError:
            pass
    write_once(path, payload)
    os.chmod(path, mode)
    return False


def _link_stored(stored, path, payload, mode):
    """True when ``path`` is now a hard link to ``stored``, this user's regular file holding exactly ``payload`` with
    exactly ``mode``; False (nothing placed) otherwise."""
    try:
        descriptor = os.open(stored, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return False
    try:
        found = os.fstat(descriptor)
        if not (
            stat.S_ISREG(found.st_mode)
            and found.st_uid == os.getuid()
            and stat.S_IMODE(found.st_mode) == mode
            and found.st_size == len(payload)
        ):
            return False
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            if stream.read() != payload:
                return False
        os.link(stored, path)
        placed = os.lstat(path)
        if (placed.st_dev, placed.st_ino) == (found.st_dev, found.st_ino):
            return True
        # the object moved between the read and the link: never keep it
        os.unlink(path)
        return False
    except OSError:
        return False
    finally:
        os.close(descriptor)


def _link_from(source, path: Path, payload: bytes) -> bool | None:
    """One `link_once` candidate: True when ``path`` is now a hard link to ``source``; False when ``path`` appeared
    meanwhile holding exactly ``payload`` (nothing left to write); None when ``source`` cannot be linked (not this
    user's regular file, other bytes, another filesystem): the next candidate is tried, else the bytes are written.
    """
    import stat

    try:
        descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    try:
        found = os.fstat(descriptor)
        if not (
            stat.S_ISREG(found.st_mode)
            and found.st_size == len(payload)
            and found.st_uid == os.getuid()
        ):
            return None
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            if stream.read() != payload:
                return None
        if stat.S_IMODE(found.st_mode) & 0o077:
            # owner-only, never wider than it was (a read-only output stays read-only)
            os.fchmod(descriptor, stat.S_IMODE(found.st_mode) & 0o700)
        try:
            os.link(source, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != payload:
                raise ValueError("immutable session artifact conflict") from None
            return False
        placed = os.stat(path, follow_symlinks=False)
        if (placed.st_dev, placed.st_ino) == (found.st_dev, found.st_ino):
            return True
        # the source moved between the read and the link: never keep it
        os.unlink(path)
        return None
    except (OSError, AttributeError):
        # cannot link here (another filesystem, no fchmod): the next candidate, else written
        return None
    finally:
        os.close(descriptor)


def _link_compressed(source: Path, path: Path, payload: bytes) -> bool:
    """``path`` as hard links to ``source``'s compressed pair (archive and RAW note), True only when both linked and
    `read_raw` of ``path`` then gives exactly ``payload``; anything less removes what was linked and returns False.
    """
    pairs = (
        (_compressed(source), _compressed(path)),
        (_raw_note_path(source), _raw_note_path(path)),
    )
    placed = []
    try:
        for origin, name in pairs:
            if (
                os.path.lexists(name)
                or _link_from(origin, name, origin.read_bytes()) is not True
            ):
                return False
            placed.append(name)
        return _raw_note_matches(path, payload)
    except (OSError, ValueError):
        return False
    finally:
        if len(placed) != len(pairs) or not _raw_note_matches(path, payload):
            for name in placed:
                with suppress(OSError):
                    name.unlink()


def _raw_note_matches(path: Path, payload: bytes) -> bool:
    try:
        return read_raw(path) == payload
    except (OSError, ValueError):
        return False


def _failure_resource_summary(resources: object) -> dict[str, int | None]:
    """Retain only bounded counters useful for private reference diagnosis."""

    def mapping(value: object) -> dict[str, object]:
        return value if type(value) is dict else {}

    def counter(value: object) -> int | None:
        return value if type(value) is int and 0 <= value <= 2**63 - 1 else None

    observed = mapping(resources)
    memory = mapping(observed.get("memory"))
    events = mapping(memory.get("events"))
    pids = mapping(observed.get("pids"))
    return {
        "memory_peak_bytes": counter(memory.get("peak_bytes")),
        "memory_oom_events": counter(events.get("oom")),
        "memory_oom_kill_events": counter(events.get("oom_kill")),
        "pids_peak": counter(pids.get("peak")),
    }


def _retain_reference_failure(
    record_path: Path, request_digest: str, result: object
) -> None:
    """Retain a private typed failure in the existing result family, then stop."""

    try:
        observed = result.result
        if (
            type(observed.outcome) is ReferenceRunOutcome
            and observed.outcome is not ReferenceRunOutcome.SUPPORTED
            and type(observed.failure_reason) is ReferenceFailureReason
        ):
            write_once(
                record_path,
                canonical(
                    {
                        "request_digest": request_digest,
                        "outcome": observed.outcome.value,
                        "failure_reason": observed.failure_reason.value,
                        "resources": _failure_resource_summary(result.resources),
                        "candidate_judged": False,
                    }
                ),
            )
    except (OSError, ValueError, TypeError, AttributeError):
        # Evidence failure never replaces the original non-SUPPORTED stop.
        pass
    raise ValueError("reference failure; retain run and stop, no case replacement")


def context(root: Path) -> MockContext:
    entropy = root / "private-generation-entropy.bin"
    if not entropy.exists():
        write_once(entropy, os.urandom(32))
    if entropy.is_symlink() or entropy.stat().st_size != 32:
        raise ValueError("invalid generation material")
    # Generation pins are independently retained. A prospective adapter repair
    # must not silently redraw a cohort by changing a scoring/profile digest.
    pin_path = root / "generation-pin.json"
    if not pin_path.exists():
        write_once(
            pin_path,
            canonical(
                {
                    "generator_digest": digest(
                        Path(burgers_dynamics.__file__).read_bytes()
                    ),
                    "scoring_digest": profile_digest(),
                    "evaluation_binding_hex": profile_digest()[7:],
                }
            ),
        )
    if pin_path.is_symlink() or pin_path.stat().st_size > 1024:
        raise ValueError("invalid retained generation pin")
    value = json.loads(pin_path.read_bytes())
    if set(value) != {"generator_digest", "scoring_digest", "evaluation_binding_hex"}:
        raise ValueError("invalid generation pin fields")
    if value["generator_digest"] != digest(
        Path(burgers_dynamics.__file__).read_bytes()
    ):
        raise ValueError("generator implementation changed")
    pin = SeedPin(
        CHALLENGE,
        "c-auth1-1.0",
        value["generator_digest"],
        "unresolved-development-v1",
        value["scoring_digest"],
        EvaluationBinding(bytes.fromhex(value["evaluation_binding_hex"])),
    )
    return MockContext(MockEntropy(entropy.read_bytes()), pin)


def frozen_cases(root: Path):
    ctx = context(root)
    return tuple(
        generate_development_case(ctx, BurgersCaseCoordinates(role, cell, 0, 0))
        for role in PublicDevelopmentRole
        for cell in range(12)
    )


def freeze(root: Path, image_manifest: Path) -> dict[str, object]:
    if not root.is_absolute() or root.is_symlink():
        raise ValueError("private absolute session directory required")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    image = load_image_identity(image_manifest)
    write_once(root / "profile.json", canonical(profile_document()))
    contracts = build_contracts()
    for index, obj in enumerate(authored_contracts()):
        write_once(root / f"authored-{index}.json", obj.canonical_bytes())
    write_once(root / "assembly.json", contracts.assembly.canonical_bytes())
    write_once(
        root / "catalog.json",
        contracts.catalog.canonical_bytes(candidate_assembly=contracts.assembly),
    )
    cases = frozen_cases(root)
    rows = []
    for case in cases:
        name = f"{case.coordinates.role.value.lower()}-{case.coordinates.cell:02d}"
        payload = canonical_public_case_bytes(case)
        write_once(root / f"{name}-case.json", payload)
        request = build_reference_request(
            case,
            BurgersReferenceRole.CANDIDATE_PRIMARY,
            output_points=64,
            requested_times=requested_times(case, 4),
            environment_digest=runtime_environment_digest(),
        )
        write_once(
            root / f"{name}-reference-request.json", canonical(request.document())
        )
        rows.append(
            {
                "name": name,
                "role": case.coordinates.role.value,
                "case_digest": digest(payload),
                "reference_request_digest": request.request_digest,
            }
        )
    manifest = {
        "schema": "carbon.burgers-session.frozen-cases.v1",
        "profile_digest": profile_digest(),
        "worker_image": image.image_id,
        "cases": rows,
    }
    write_once(root / "case-manifest.json", canonical(manifest))
    return manifest


def prepare(root: Path, image_manifest: Path) -> dict[str, object]:
    manifest = freeze(root, image_manifest)
    image = load_image_identity(image_manifest)
    controller = IsolatedBurgersReferenceController(
        state_root=root / "references",
        image=image,
        worker_profile=DevelopmentWorkerProfile(
            profile_digest(), digest(canonical(profile_document()["budget"]))
        ),
    )
    budget = SessionBudget(root / "budget.sqlite3")
    initial, viscosity, times, solutions, records = [], [], [], [], []
    for case, row in zip(frozen_cases(root), manifest["cases"], strict=True):
        request = build_reference_request(
            case,
            BurgersReferenceRole.CANDIDATE_PRIMARY,
            output_points=64,
            requested_times=requested_times(case, 4),
            environment_digest=runtime_environment_digest(),
        )
        record_path = root / f"{row['name']}-reference-result.json"
        if record_path.exists():
            record = json.loads(record_path.read_bytes())
            if record["request_digest"] != request.request_digest:
                raise ValueError("reference association conflict")
            if record.get("outcome") is not None:
                raise ValueError(
                    "reference failure; retain run and stop, no case replacement"
                )
            payload = Path(record["solution_path"]).read_bytes()
            if digest(payload) != record["payload_digest"]:
                raise ValueError("reference artifact changed")
        else:
            result = budget.run_worker(
                request.request_digest,
                lambda request=request: controller.execute(request),
            )
            if result.result.outcome is not ReferenceRunOutcome.SUPPORTED:
                _retain_reference_failure(record_path, request.request_digest, result)
            solution_path = result.snapshot_path / "solution.f64le"
            payload = solution_path.read_bytes()
            record = {
                "request_digest": request.request_digest,
                "artifact_digest": result.result.artifact_digest,
                "shape": list(result.result.shape),
                "solution_path": str(solution_path),
                "payload_digest": digest(payload),
                "snapshot_digest": result.snapshot_digest,
                "timings": result.timings,
                "resources": result.resources,
                "controls": result.controls,
            }
            write_once(record_path, canonical(record))
        records.append(record)
        if case.coordinates.role is PublicDevelopmentRole.TRAIN:
            query = candidate_query(case, grid_points=64, intervals_per_phase=4)
            initial.append(query.initial_field)
            viscosity.append(query.viscosity)
            times.append(query.requested_times)
            solutions.append(np.frombuffer(payload, dtype="<f8").reshape(13, 64))
        print(f"Reference retained: {row['name']}", flush=True)
    archive = root / "public-train.npz"
    if not archive.exists():
        data = Trajectories(
            np.array(initial),
            np.array(viscosity),
            np.array(times),
            np.array(solutions),
            np.arange(64, dtype=np.float64) * DOMAIN_LENGTH / 64,
            "train",
            "carbon_c_auth1_c04_train",
            domain_length=DOMAIN_LENGTH,
        )
        data.save(archive)
        archive.chmod(0o600)
    report = {
        "schema": "carbon.burgers-session.preparation.v1",
        "profile_digest": profile_digest(),
        "case_manifest_digest": digest(canonical(manifest)),
        "reference_count": len(records),
        "training_parent_count": len(initial),
        "train_archive_digest": digest(archive.read_bytes()),
        "accounting": budget.summary(),
        "agent_inference": False,
        "training_runs": 0,
        "chain_transactions": 0,
    }
    write_once(root / "preparation.json", canonical(report))
    return report
