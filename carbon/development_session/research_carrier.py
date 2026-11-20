"""Isolated public-research carrier reusing C-03 mechanisms and output parser.

No API accepts host mounts, Docker options, credentials or protected inputs.
Research script output is always untrusted/self-reported. Trusted practice uses
a separate invocation with a controller-selected fixed program and staged data.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import stat as stat_module
import threading
import time
from contextlib import ExitStack, contextmanager, suppress
from contextvars import ContextVar
from functools import partial

from carbon.challenge_kit.version_registry import REBUILD_LIMIT_SECONDS
from carbon.reconstruction import remote_gpu_build, remote_lane
from carbon.reconstruction.worker import liveness_reaper
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    controls_predicate,
    create_arguments,
    doctor,
    inspect_effective_controls,
    observe_effective_resources,
    remove_exact_container,
    spawn_watchdog,
)
from carbon.reconstruction.worker.model import (
    CONTROL_BYTES,
    INPUT_BYTES,
    OUTPUT_BYTES,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
    worker_resources_for,
)
from carbon.reconstruction.worker.model import (
    worker_resources_version as resources_version_for,
)
from carbon.reconstruction.worker.protocol import decode_output_stream

from .data import ledger_objects, store_once, write_once
from .profile import canonical, digest
from .research_workspace import ResearchWorkspace

# --- Decoded output streams stored once (owner rule #13; grade storage head, 20 Nov 2026) ---------------------------
# Receiver-side only, so it lives HERE and never in `carbon.reconstruction.worker.protocol`: that module is a worker
# build input (`build_inputs.txt`), and any byte change there moves the worker images' ``source_tree_digest``, so a
# receiver whose trusted worker was built before refuses every start (live 116, 20 Nov 2026 16:07Z: "trusted worker must
# be built from this exact accepted source revision" after the apply of b03ca8d5, which carried this code in protocol).

#: The framing of a decoded output stream: its header, member and end lines without the member bodies (which are the
#: decoded snapshot's own files). With the snapshot it rebuilds the stream byte for byte (`reassembled_output_stream`).
OUTPUT_FRAMES = "export.frames"


def _snapshot_member(snapshot, member):
    from carbon.reconstruction.worker.protocol import _safe_relative

    path = snapshot.joinpath(*_safe_relative(member["path"]).parts)
    found = os.lstat(path)
    if not stat_module.S_ISREG(found.st_mode) or found.st_size != member["size"]:
        raise WorkerFailure(WorkerCode.OUTPUT)
    return path


def _one_line(line):
    import io

    return io.BytesIO(line)


def reassembled_output_stream(frames, snapshot):
    """The decoded stream's bytes again, in blocks, from its framing (`OUTPUT_FRAMES`) and its snapshot: each member
    line is followed by the snapshot file it names, which must have the member's size. Raises `WorkerFailure` when the
    framing or a file does not fit."""
    from carbon.reconstruction.worker.protocol import (
        _STREAM_END_FIELDS,
        _STREAM_HEADER_FIELDS,
        _STREAM_MEMBER_FIELDS,
        _closed_json_line,
        _json_line,
    )

    with frames.open("rb") as lines:
        header = lines.readline(2049)
        _closed_json_line(_one_line(header), _STREAM_HEADER_FIELDS)
        yield header
        while True:
            line = lines.readline(2049)
            record = _json_line(_one_line(line))
            yield line
            if set(record) == _STREAM_END_FIELDS:
                if lines.read(1) != b"":
                    raise WorkerFailure(WorkerCode.OUTPUT)
                return
            if set(record) != _STREAM_MEMBER_FIELDS or type(record["size"]) is not int:
                raise WorkerFailure(WorkerCode.OUTPUT)
            path = _snapshot_member(snapshot, record)
            with path.open("rb") as body:
                remaining = record["size"]
                while remaining:
                    block = body.read(min(1 << 20, remaining))
                    if not block:
                        raise WorkerFailure(WorkerCode.OUTPUT)
                    remaining -= len(block)
                    yield block
                if body.read(1) != b"":
                    raise WorkerFailure(WorkerCode.OUTPUT)


def compact_output_stream(source, snapshot, *, expected=None):
    """Store a decoded output stream once (owner rule #13): its member bodies are the snapshot's own files, so only its
    framing is kept (`OUTPUT_FRAMES` beside it) and the stream is removed, after the framing and the snapshot are shown
    to rebuild it byte for byte (the same SHA-256, so a recorded ``output_digest`` stays checkable). True when compacted;
    False (the stream kept as it is, nothing else changed) for anything that does not fit: a link, a framing file
    already there, a body that differs from its snapshot file, a stream that does not parse, or (``expected``, a
    recorded ``"sha256:<hex>"`` output digest) a stream whose own SHA-256 is not that digest.
    """
    import hashlib
    import tempfile
    from pathlib import Path

    from carbon.reconstruction.worker.protocol import (
        _STREAM_END_FIELDS,
        _STREAM_HEADER_FIELDS,
        _STREAM_MEMBER_FIELDS,
        _closed_json_line,
        _json_line,
    )

    frames = source.parent / OUTPUT_FRAMES
    staged = None
    try:
        if source.is_symlink() or not source.is_file() or os.path.lexists(frames):
            return False
        whole = hashlib.sha256()
        kept = []
        with source.open("rb") as stream:
            header = stream.readline(2049)
            _closed_json_line(_one_line(header), _STREAM_HEADER_FIELDS)
            whole.update(header)
            kept.append(header)
            while True:
                line = stream.readline(2049)
                record = _json_line(_one_line(line))
                whole.update(line)
                kept.append(line)
                if set(record) == _STREAM_END_FIELDS:
                    if stream.read(1) != b"":
                        return False
                    break
                if (
                    set(record) != _STREAM_MEMBER_FIELDS
                    or type(record["size"]) is not int
                ):
                    return False
                path = _snapshot_member(snapshot, record)
                with path.open("rb") as body:
                    remaining = record["size"]
                    while remaining:
                        block = stream.read(min(1 << 20, remaining))
                        if not block or body.read(len(block)) != block:
                            return False
                        whole.update(block)
                        remaining -= len(block)
        descriptor, staged = tempfile.mkstemp(
            prefix=f".{OUTPUT_FRAMES}.", dir=source.parent
        )
        with os.fdopen(descriptor, "wb") as output:
            output.write(b"".join(kept))
            output.flush()
            os.fsync(output.fileno())
        rebuilt = hashlib.sha256()
        for block in reassembled_output_stream(Path(staged), snapshot):
            rebuilt.update(block)
        if rebuilt.digest() != whole.digest() or (
            expected is not None and expected != "sha256:" + whole.hexdigest()
        ):
            return False
        os.chmod(staged, stat_module.S_IMODE(os.lstat(source).st_mode) & 0o700)
        os.link(staged, frames)
        os.unlink(source)
        return True
    except (OSError, WorkerFailure):
        return False
    finally:
        if staged is not None:
            try:
                os.unlink(staged)
            except OSError:
                pass


PRECHARGED_TRIAL = ContextVar("carbon_precharged_trial", default=None)

# A fixed public TRAIN build in a separately provisioned offline library child.
# This stays in the bounded Carbon worker lane, never the miner script lane.
LIBRARY_BUILD_PROVENANCE = "DIRECT_BUNDLE_PUBLIC_RECONSTRUCTION"
LIBRARY_PREP_PROVENANCE = "DIRECT_BUNDLE_DEPENDENCY_PREP"
LIBRARY_OVERLAY_BUILD_PROVENANCE = "DIRECT_BUNDLE_OVERLAY_RECONSTRUCTION"

ACTIVE_TASK = ContextVar("carbon_public_research_task", default=None)


def _checked_pinned_uv_stage(added, identity):
    """Validate the bytes produced after admission against its frozen binding."""
    if type(added) is not dict or set(added) != {"uv-bin", "control.json"}:
        raise ValueError("closed pinned UV stage output required")
    uv_binary, control_raw = added["uv-bin"], added["control.json"]
    if (
        type(uv_binary) is not bytes
        or not 0 < len(uv_binary) <= 64 * 1024**2
        or type(control_raw) is not bytes
        or not 0 < len(control_raw) <= 65536
    ):
        raise ValueError("bounded pinned UV stage required")
    try:
        control = json.loads(control_raw)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError("pinned UV stage control differs") from error
    fields = {"bundle_ref", "parent_image_id", "uv_sha256"}
    if "parent_build" in identity:
        fields.add("parent_build")
    if (
        type(control) is not dict
        or set(control) != fields
        or control["bundle_ref"] != identity["bundle_ref"]
        or control["parent_image_id"] != identity["parent_image_id"]
        or control["uv_sha256"] != digest(uv_binary)
        or (
            "parent_build" in identity
            and control["parent_build"] != identity["parent_build"]
        )
    ):
        raise ValueError("pinned UV stage control differs")
    return added


def _stage_verified_overlay(source, target, receipt):
    """Copy sealed CAS bytes into the read-only, container-readable input mount."""
    from .library_environment_cache import _verified_overlay_tree

    _verified_overlay_tree(source, receipt)
    shutil.copytree(source, target, symlinks=False)
    _verified_overlay_tree(target, receipt)
    for entry in target.rglob("*"):
        entry.chmod(0o555 if entry.is_dir() else 0o444)
    target.chmod(0o555)
    _verified_overlay_tree(target, receipt)


#: The trusted stage items a finished operation no longer needs: the pinned uv binary (~52 MB) and the copied sealed
#: overlay tree. Both are content-pinned and rebuildable from their caches; everything else in the input (the program,
#: the caller's files such as a build's ``example.npz``, which retention reads) stays.
RECLAIMED_STAGE = "reclaimed.json"


#: An op's staged input files are each stored once by bytes and mode (`data.store_once`; owner rule #13): door-wide
#: in ``<state>/objects`` for a receiver's owner ledgers (sre 20 Nov: Carbon's own staged modules and the allowlist were
#: written again into every op of every owner, 4,572 + 5,616 copies a day), else in the ledger's own `INPUT_OBJECTS`.
#: Each op's ``input/`` file is a hard link to one: the same name, bytes and mode for the container, which sees
#: ``/input`` read-only (`docker_runtime`: bind ``readonly``, checked ``RW`` false), so a shared file is one no worker
#: can change. Nothing stored is ever modified; an op's reclaim only unlinks its own names.
#: Staged per op and reclaimed when it ends (`reclaim_trusted_stage`): never a shared object.
_NOT_STORED_ONCE = frozenset({"uv-bin"})


def _stage_once(path, body, mode):
    """Stage ``path`` (a new name in a fresh ``<ledger>/operation-*/input/``) with ``body`` and ``mode`` as a hard link
    to the stored object of the same bytes and mode (`data.store_once` in `data.ledger_objects`), else an ordinary
    `write_once` + chmod, as before."""
    store_once(ledger_objects(path.parent.parent.parent), path, body, mode)


def _make_writable(path):
    """Owner-writable again (the stage is made read-only for the container), so the tree can be removed."""
    path.chmod(0o700 if path.is_dir() and not path.is_symlink() else 0o600)


def reclaim_trusted_stage(stage):
    """Remove a finished operation's trusted stage items, keeping their identities.

    GPUYard 6 Nov (Deploy 06:48, Lead 07:00): every grade and rebuild staged a fresh ~52 MB ``uv-bin`` (and an overlay
    tree) under ``ledger/operation-*/input`` and never reclaimed it, ~1.5 GB/h with crown averaging. Called only once
    the operation's container is confirmed removed, so nothing reads the mount. Writes ``reclaimed.json`` (the uv
    sha256 and the overlay's own receipt) beside them first, so the operation's record of what ran is unchanged.
    Idempotent; a stage with neither item is left exactly as it is. Returns the bytes freed.
    """
    if stage.is_symlink() or not stage.is_dir():
        return 0
    uv = stage / "uv-bin"
    overlay = stage / "overlay"
    present_uv = uv.is_file() and not uv.is_symlink()
    present_overlay = overlay.is_dir() and not overlay.is_symlink()
    if not (present_uv or present_overlay):
        return 0
    receipt = overlay / ".overlay.json"
    record = {
        "schema": "carbon.autoresearch.reclaimed-stage.v1",
        "uv_sha256": digest(uv.read_bytes()) if present_uv else None,
        "overlay_receipt": (
            json.loads(receipt.read_bytes())
            if present_overlay and receipt.is_file() and not receipt.is_symlink()
            else None
        ),
    }
    stage.chmod(0o755)
    marker = stage / RECLAIMED_STAGE
    if not marker.exists():
        write_once(marker, canonical(record))
        marker.chmod(0o444)
    freed = 0
    if present_uv:
        freed += uv.stat().st_size
        _make_writable(uv)
        uv.unlink()
    if present_overlay:
        entries = sorted(overlay.rglob("*"), reverse=True)
        freed += sum(
            e.stat().st_size for e in entries if e.is_file() and not e.is_symlink()
        )
        _make_writable(overlay)
        for entry in entries:
            if not entry.is_symlink():
                _make_writable(entry)
        shutil.rmtree(overlay)
    stage.chmod(0o755)
    return freed


BOOTSTRAP = """
import os,shutil
from pathlib import Path
work=Path('/scratch/workspace');work.mkdir()
out=Path('/scratch/output');out.mkdir()
for item in Path('/input').iterdir():
    if item.name!='program.py': shutil.copyfile(item,work/item.name)
os.chdir(work)
os.execv('/opt/carbon-worker/bin/python',['python','-I','/input/program.py'])
"""


#: Where a remote GPU build's program keeps its output and exit status in its own container (`DETACHABLE_FRONT`).
DETACHABLE_RUN_DIR = "/scratch/.carbon-run"

#: The detachable front end of a remote GPU build's program (owner, 20 Nov 2026: a door restart must never cancel an
#: in-flight build; live 116 01:52Z: ~22 cancelled and re-run from zero). Run as ``python -I -c DETACHABLE_FRONT
#: <bootstrap> <run dir> <stdout cap> <stderr cap>`` in place of ``-c <bootstrap>``: it runs the bootstrap (which
#: ``execv``s into the program) as its ONE child and relays the child's stdout and stderr unchanged, then exits with the
#: child's status (a signal as 128+n, as `docker exec` reports one), so the door sees what it saw before. Besides, it
#: keeps the first <cap> bytes of each stream and the exit status in <run dir> (``stdout``, ``stderr``, ``exit``, the
#: last written whole), and keeps running when the door's end of the stream goes away (a write there that fails is
#: dropped, never fatal), so the program outlives the door and its result can be read later (``detachable_program`` in
#: the intent). It stays the exec's root process (the box's program-age read, `_BOX_PROGRAM_AGE`, still finds exactly
#: one) and starts before its child, as the bootstrap did. A run dir that cannot be made keeps the relay, no files.
DETACHABLE_FRONT = r"""
import os,selectors,sys
boot,run=sys.argv[1],sys.argv[2]
caps={1:int(sys.argv[3]),2:int(sys.argv[4])}
try:
    os.mkdir(run,0o700)
except OSError:
    run=None
if run is not None:
    try:
        with open(run+'/front.pid','w') as record:
            record.write(str(os.getpid()))
    except OSError:
        pass
o_r,o_w=os.pipe()
e_r,e_w=os.pipe()
pid=os.fork()
if pid==0:
    os.close(o_r);os.close(e_r)
    os.dup2(o_w,1);os.dup2(e_w,2)
    os.close(o_w);os.close(e_w)
    code=0
    try:
        exec(compile(boot,'<string>','exec'),{'__name__':'__main__'})
    except SystemExit as stop:
        code=stop.code if type(stop.code) is int else (0 if stop.code is None else 1)
        if stop.code is not None and type(stop.code) is not int:
            print(stop.code,file=sys.stderr)
    except BaseException:
        import traceback
        traceback.print_exc()
        code=1
    for stream in (sys.stdout,sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    os._exit(code)
os.close(o_w);os.close(e_w)
files={}
if run is not None:
    for fd,name in ((1,'stdout'),(2,'stderr')):
        try:
            files[fd]=os.open(run+'/'+name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except OSError:
            pass
kept={1:0,2:0}
pending={1:bytearray(),2:bytearray()}
gone=set()
for fd in (1,2):
    try:
        os.set_blocking(fd,False)
    except OSError:
        gone.add(fd)
def push(fd):
    while pending[fd] and fd not in gone:
        try:
            sent=os.write(fd,pending[fd])
        except BlockingIOError:
            return
        except OSError:
            gone.add(fd);pending[fd].clear();return
        del pending[fd][:sent]
selector=selectors.DefaultSelector()
selector.register(o_r,selectors.EVENT_READ,1)
selector.register(e_r,selectors.EVENT_READ,2)
while selector.get_map():
    for fd in (1,2):
        push(fd)
    waiting=any(pending[fd] for fd in (1,2) if fd not in gone)
    for key,_ in selector.select(0.05 if waiting else None):
        fd=key.data
        block=os.read(key.fd,65536)
        if not block:
            selector.unregister(key.fd);os.close(key.fd)
            continue
        part=block[:max(0,caps[fd]-kept[fd])]
        if not part:
            continue
        kept[fd]+=len(part)
        if fd in files:
            try:
                os.write(files[fd],part)
            except OSError:
                pass
        if fd not in gone:
            pending[fd]+=part
status=os.waitpid(pid,0)[1]
code=os.waitstatus_to_exitcode(status)
code=128-code if code<0 else code
for fd in files.values():
    try:
        os.fsync(fd);os.close(fd)
    except OSError:
        pass
if run is not None:
    try:
        with open(run+'/exit.part','w') as record:
            record.write(str(code)+'\n')
        os.replace(run+'/exit.part',run+'/exit')
    except OSError:
        pass
for fd in (1,2):
    if fd not in gone and pending[fd]:
        try:
            os.set_blocking(fd,True)
            os.write(fd,bytes(pending[fd]))
        except OSError:
            pass
os._exit(code)
"""


def _detachable(session=None):
    """Whether this op's program runs under `DETACHABLE_FRONT`: a remote GPU build slot op (its container on a box's
    daemon, `remote_gpu_build.docker_host`), never a grade session's member op; every other op is unchanged.
    """
    return (
        session is None
        and remote_gpu_build.current_op() is not None
        and remote_gpu_build.docker_host() is not None
    )


def _program_command(name, bootstrap, *, detachable, maximum, adopting=False):
    """The PROGRAM stage's ``docker exec``: today's ``-c <bootstrap>``, or for a detachable op the same bootstrap under
    `DETACHABLE_FRONT`, which keeps one byte past each stream's cap (a stream over its cap is still refused here, as
    before); for an adopted op (``adopting``), the running program's recorded result (`DETACHABLE_WAIT`).
    """
    from carbon.reconstruction.worker.model import DIAGNOSTIC_BYTES

    command = ["exec", name, "/opt/carbon-worker/bin/python", "-I", "-c"]
    if adopting:
        return [*command, DETACHABLE_WAIT, DETACHABLE_RUN_DIR]
    if not detachable:
        return [*command, bootstrap]
    return [
        *command,
        DETACHABLE_FRONT,
        bootstrap,
        DETACHABLE_RUN_DIR,
        str(maximum + 1),
        str(DIAGNOSTIC_BYTES + 1),
    ]


#: The wait mode of `DETACHABLE_FRONT` (Head B): ``python -I -c DETACHABLE_WAIT <run dir>`` waits for the program's
#: recorded exit status, then writes the kept stdout and stderr and exits with that status: what the front end relayed
#: (the same bytes up to its caps, the same status). A front end that is gone with no status recorded (the program's
#: result cannot be known) prints `PROGRAM_LOST` to stderr and exits 254: the adopting door reads that as Carbon's.
DETACHABLE_WAIT = r"""
import os,sys,time
run=sys.argv[1]
def alive():
    try:
        os.kill(int(open(run+'/front.pid').read()),0)
    except (OSError,ValueError):
        return False
    return True
while not os.path.exists(run+'/exit'):
    if not alive() and not os.path.exists(run+'/exit'):
        sys.stderr.write('carbon_detached_program_lost\n')
        sys.stderr.flush()
        os._exit(254)
    time.sleep(0.5)
for fd,name in ((1,'stdout'),(2,'stderr')):
    try:
        with open(run+'/'+name,'rb') as kept:
            data=kept.read()
    except OSError:
        data=b''
    while data:
        data=data[os.write(fd,data):]
os._exit(int(open(run+'/exit').read()))
"""

#: What `DETACHABLE_WAIT` prints when the program's result cannot be known (its front end is gone, no status).
PROGRAM_LOST = b"carbon_detached_program_lost"
#: An op is adopted only with at least this long left before its recorded deadline (its export, cleanup and settle).
ADOPT_MARGIN_SECONDS = 120
#: How long a program stream that ended by a signal waits for the stop to be announced (systemd stops the unit's
#: processes together, so the docker client can die a moment before this process reads its own signal).
_STOP_ANNOUNCE_SECONDS = 10.0
#: How long one start reuses a box's list of running containers (`_running_on_box`): one probe per box per restore.
_BOX_LIST_SECONDS = 60.0
#: How long a stopping door waits for its detachable programs' docker clients to end on SIGTERM before it kills them
#: (`_release_detachable_streams`): the docker CLI keeps an attached exec stream open on one SIGTERM (live 116, 20 Nov
#: 2026: one client outlived the receiver, and systemd waited its 90 s stop timeout for it). Only the local client
#: ends; the program runs on under its front end on the box (`DETACHABLE_FRONT`).
_STREAM_RELEASE_SECONDS = 2.0

#: The receiver is stopping (`door_stopping`).
_STOPPING = threading.Event()
#: Container names of the detachable programs this process streams now (`_release_detachable_streams`).
_LIVE_PROGRAMS = set()
#: Ops a start found adoptable (`register_adoptable`): ``{(ledger root, identity): recorded slot binding}``.
_ADOPTABLE = {}
#: A start's box lists (`_running_on_box`): ``{docker host: (read at, container names)}``.
_BOX_LISTS = {}
_ADOPT_LOCK = threading.Lock()


class Detached(BaseException):
    """The receiver is stopping and this op is left as it is (owner, 20 Nov 2026: a restart must never cancel an
    in-flight build): a remote GPU build whose program runs on under `DETACHABLE_FRONT`, or an op that would start
    now. Nothing is cleaned up or settled and its task stays RUNNING: the next start adopts the op
    (`register_adoptable`) or, when it cannot, settles it as before and re-runs the build at its place. A
    BaseException, so no ``except Exception`` on the way reads it as a failure of the op.
    """


def door_stopping():
    """The receiver is stopping (its signal, or its cancel step): no remote GPU build starts from now on (`Detached`),
    and this process's own docker clients of the detachable programs are ended, so each such op leaves its container
    running on its box for the next start. Idempotent."""
    _STOPPING.set()
    _release_detachable_streams()


def clear_process_state():
    """This module's process state as a new receiver process has it (no stop announced, nothing adopted or streamed,
    no box list): for tests, which share one process (`tests/conftest.py`)."""
    _STOPPING.clear()
    _LIVE_PROGRAMS.clear()
    with _ADOPT_LOCK:
        _ADOPTABLE.clear()
        _BOX_LISTS.clear()


def announce_stop():
    """The receiver's stop signal (its handler: flag only): a detachable op whose stream the stop cuts is left for the
    next start (`_detached_by_stop`). `door_stopping` follows from the stop itself."""
    _STOPPING.set()


def _raise_if_stopping():
    if _STOPPING.is_set():
        raise Detached()


def _detached_by_stop(error):
    """Whether a detachable op's failure is the receiver's stop: the stop is announced, or the docker client itself
    died by a signal (``exit=-N``) and the stop is announced within `_STOP_ANNOUNCE_SECONDS`.
    """
    if _STOPPING.is_set():
        return True
    diagnostic = getattr(error, "private_diagnostic", b"")
    return (
        type(diagnostic) is bytes
        and diagnostic.startswith(b"exit=-")
        and _STOPPING.wait(_STOP_ANNOUNCE_SECONDS)
    )


def _release_detachable_streams():
    """End this process's own docker clients (its children) of the detachable programs it streams now: each stream
    then ends, and its op leaves as `Detached`. Read from /proc; best effort (nothing to end is not an error).
    """
    import signal

    names = {name.encode() for name in tuple(_LIVE_PROGRAMS)}
    if not names:
        return
    me = str(os.getpid())
    try:
        entries = os.listdir("/proc")
    except OSError:
        return
    ended = []
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", "rb") as stream:
                text = stream.read()
            if text[text.rindex(b")") + 2 :].split()[1].decode() != me:
                continue
            with open(f"/proc/{entry}/cmdline", "rb") as stream:
                argv = stream.read().split(b"\0")
        except (OSError, ValueError, IndexError):
            continue
        if b"exec" in argv and names.intersection(argv):
            with suppress(OSError):
                os.kill(int(entry), signal.SIGTERM)
                ended.append(int(entry))
    deadline = time.monotonic() + _STREAM_RELEASE_SECONDS
    while ended and time.monotonic() < deadline:
        time.sleep(0.05)
        ended = [pid for pid in ended if _own_live_child(pid, me)]
    for pid in ended:
        if _own_live_child(pid, me):
            with suppress(OSError):
                os.kill(pid, signal.SIGKILL)


def _docker_children(me):
    """``[(pid, argv)]`` of this process's own live ``docker`` client children, read from /proc."""
    found = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return found
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", "rb") as stream:
                text = stream.read()
            fields = text[text.rindex(b")") + 2 :].split()
            if fields[1].decode() != me or fields[0] == b"Z":
                continue
            with open(f"/proc/{entry}/cmdline", "rb") as stream:
                argv = [part for part in stream.read().split(b"\0") if part]
        except (OSError, ValueError, IndexError):
            continue
        if argv and os.path.basename(argv[0]) == b"docker":
            found.append((int(entry), argv))
    return found


def _client_summary(argv):
    """A docker client's subcommand and container name prefix only (never its program text or a host)."""
    words = [part.decode("utf-8", "replace") for part in argv[1:]]
    sub = next(
        (
            w
            for w in words
            if w in ("exec", "run", "create", "start", "rm", "kill", "inspect", "cp")
        ),
        None,
    )
    container = next((w[:24] for w in words if w.startswith("carbon-d4-")), None)
    return {"subcommand": sub, "container": container}


def release_own_docker_clients():
    """The receiver's very last stop step (`direct_receiver._stop_providers`): every ``docker`` client still a child of
    this process is orphaned now (its providers are closed, the process exits), so each is ended (SIGTERM, then SIGKILL
    after `_STREAM_RELEASE_SECONDS`) and named in one ``stop_docker_client_ended`` journal line (subcommand and
    container prefix only). Live 116, 20 Nov 2026 13:13:32Z: a docker child outlived the main process and systemd
    waited its 90 s stop timeout to kill it. A local client only: a remote program or container is never touched here.
    Never raises."""
    import signal

    try:
        me = str(os.getpid())
        clients = _docker_children(me)
        if not clients:
            return
        for pid, _argv in clients:
            with suppress(OSError):
                os.kill(pid, signal.SIGTERM)
        pending = [pid for pid, _argv in clients]
        deadline = time.monotonic() + _STREAM_RELEASE_SECONDS
        while pending and time.monotonic() < deadline:
            time.sleep(0.05)
            pending = [pid for pid in pending if _own_live_child(pid, me)]
        for pid in pending:
            with suppress(OSError):
                os.kill(pid, signal.SIGKILL)
        from carbon.battery.intake import log

        log(
            "stop_docker_client_ended",
            clients=[_client_summary(argv) for _pid, argv in clients],
            killed=len(pending),
        )
    except Exception:  # noqa: BLE001 - a stop step never fails the stop
        return


def _own_live_child(pid, me):
    """Whether ``pid`` is still this process's child and has not exited (not a zombie): read from /proc."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as stream:
            text = stream.read()
        fields = text[text.rindex(b")") + 2 :].split()
        return fields[0] != b"Z" and fields[1].decode() == me
    except (OSError, ValueError, IndexError):
        return False


def _slot_names(binding, name, launch):
    """Whether the recorded slot's allocation record names exactly this container and launch."""
    try:
        record = json.loads((binding.slot_dir / "active-allocation.json").read_bytes())
    except (OSError, ValueError):
        return False
    return (
        type(record) is dict
        and record.get("container_name") == name
        and record.get("launch_digest") == launch
    )


def _running_on_box(binding):
    """The names of the containers running on ``binding``'s box now: one ``docker ps`` per box per start (reused for
    `_BOX_LIST_SECONDS`), through the box's pinned wrapper. Unreadable: empty (nothing is adopted).
    """
    host = binding.docker_host
    now = time.monotonic()
    with _ADOPT_LOCK:
        cached = _BOX_LISTS.get(host)
        if cached is not None and now - cached[0] < _BOX_LIST_SECONDS:
            return cached[1]
    try:
        with remote_gpu_build.bound(binding):
            listed = remote_gpu_build.cli(binding).run(
                ["ps", "--filter", "status=running", "--format", "{{.Names}}"],
                timeout=remote_lane.PROBE_SECONDS,
            )
        printed = listed.stdout
        if type(printed) is bytes:
            printed = printed.decode("ascii", "replace")
        names = frozenset(line.strip() for line in printed.splitlines())
    except Exception:  # noqa: BLE001 - an unreadable box adopts nothing
        names = frozenset()
    with _ADOPT_LOCK:
        _BOX_LISTS[host] = (now, names)
    return names


def adoption_check(ledger, *, owner, identity):
    """``(binding, None)`` for an op a restart can ADOPT (Head B of the build re-attach design, owner 20 Nov 2026),
    else ``(None, why)``, ``why`` a closed code. Every condition must hold, any doubt refuses and the op is settled as
    before: the op is RESERVED (``not_reserved``) with exactly one intent (``intent_not_one``) whose identity checks
    pass, as `reconcile_worker`'s (``intent_mismatch``); the intent says its program runs under `DETACHABLE_FRONT`
    (``not_detachable``) and the program was started (``not_started``); at least `ADOPT_MARGIN_SECONDS` remain before
    its recorded deadline (``deadline_near``); its box is still the door's (`remote_gpu_build.recorded`, not gone:
    ``box_gone``); the binding gives the request it reserved (`remote_gpu_build.as_recorded`: ``slot_class_differs``);
    its slot's allocation record names this container and launch (``slot_record_differs``); and the container is
    running on that box with this name (``not_running_on_box``). Anything unreadable: ``unreadable``.
    """
    try:
        if ledger.operation_state(identity, owner=owner) != "RESERVED":
            return None, "not_reserved"
        intents = []
        for path in ledger.root.glob("operation-*/intent.json"):
            if path.is_symlink() or path.stat().st_size > 65536:
                return None, "unreadable"
            value = json.loads(path.read_bytes())
            if value.get("owner") == owner and value.get("identity") == identity:
                intents.append((path, value))
        if len(intents) != 1:
            return None, "intent_not_one"
        path, intent = intents[0]
        launch = digest(
            canonical(
                {"owner": owner, "identity": identity, "request": intent["request"]}
            )
        )
        name, _ = _intent_container(intent, launch)
        if (
            intent["launch"] != launch
            or intent["container"] != name
            or path.parent.name != "operation-" + launch[7:]
        ):
            return None, "intent_mismatch"
        if intent.get("detachable_program") != 1:
            return None, "not_detachable"
        if not (path.parent / "program-started").is_file():
            return None, "not_started"
        deadline = intent.get("deadline_unix")
        if (
            type(deadline) not in (int, float)
            or deadline - time.time() < ADOPT_MARGIN_SECONDS
        ):
            return None, "deadline_near"
        binding = remote_gpu_build.recorded(intent)
        if binding is None or binding.gone:
            return None, "box_gone"
        binding = remote_gpu_build.as_recorded(binding, intent["request"])
        if binding is None:
            return None, "slot_class_differs"
        if not _slot_names(binding, name, launch):
            return None, "slot_record_differs"
        if name not in _running_on_box(binding):
            return None, "not_running_on_box"
        return binding, None
    except Exception:  # noqa: BLE001 - any doubt: settled as before
        return None, "unreadable"


def adoptable(ledger, *, owner, identity):
    """The slot binding of an op a restart can ADOPT (`adoption_check`), or None."""
    return adoption_check(ledger, owner=owner, identity=identity)[0]


def register_adoptable(ledger, *, owner, identity):
    """At a start: record ``identity`` for adoption when it is adoptable (`adoption_check`). Returns None when it was
    registered, else the closed code why not (the caller's journal line). A registered op is left RESERVED by the
    start's settles (`settle_previous_runs`, `_settle_dead_numerical`) until its task resumes and `_run` adopts it.
    """
    binding, why = adoption_check(ledger, owner=owner, identity=identity)
    if binding is None:
        return why
    with _ADOPT_LOCK:
        _ADOPTABLE[(str(ledger.root), identity)] = binding
    return None


def _adoption(ledger, identity):
    root = getattr(ledger, "root", None)
    if root is None:
        return None
    with _ADOPT_LOCK:
        return _ADOPTABLE.get((str(root), identity))


def forget_adoption(ledger, identity):
    """The op's adoption ended (its run here, or its task's settle): it is never adopted again in this process."""
    root = getattr(ledger, "root", None)
    if root is not None:
        with _ADOPT_LOCK:
            _ADOPTABLE.pop((str(root), identity), None)


def program_runs_on(ledger, *, owner, identity):
    """Whether a stopping receiver may leave ``identity`` for the next start (read from this host's own records only,
    no box call): the op is RESERVED with exactly one intent, which says its program runs under `DETACHABLE_FRONT`,
    and the program was started (``program-started``). The next start still adopts it only when `adoptable` holds.
    """
    try:
        if ledger.operation_state(identity, owner=owner) != "RESERVED":
            return False
        found = []
        for path in ledger.root.glob("operation-*/intent.json"):
            if path.is_symlink() or path.stat().st_size > 65536:
                return False
            value = json.loads(path.read_bytes())
            if value.get("owner") == owner and value.get("identity") == identity:
                found.append((path, value))
        return (
            len(found) == 1
            and found[0][1].get("detachable_program") == 1
            and (found[0][0].parent / "program-started").is_file()
        )
    except Exception:  # noqa: BLE001 - any doubt: cancelled as before
        return False


def _run_adopted(ledger, binding, **kwargs):
    """`_run` for an op this start adopted (`register_adoptable`): on the very slot its intent recorded
    (`remote_gpu_build.adopted`), off this host, read as any remote build (its box guard and retyping); `_run_locked`
    then follows the running program (`adopt`) instead of launching one. The adoption ends with this attempt.
    """
    from carbon.reconstruction import grade_lanes

    identity = kwargs["identity"]
    try:
        with (
            grade_lanes.running_op(identity),
            grade_lanes.released(),
            remote_gpu_build.adopted(binding) as remote_build,
        ):
            try:
                with _remote_build_guarded(remote_build):
                    return _run_supervised(ledger, adopt=remote_build, **kwargs)
            except MinerProgramFailure:
                raise
            except Exception as error:
                down = remote_gpu_build.retyped(error)
                if down is not None:
                    raise down from error
                raise
    finally:
        forget_adoption(ledger, identity)


def run_script(
    ledger, *, owner, identity, source, files, image, seconds=600, accelerator=None
):
    """Run miner Python only on explicitly staged public/own file bytes.

    `accelerator=MINER_GPU` runs it on the host's installed GPU, in the
    campaign's pinned GPU worker image (RSURF-D20, owner, 2026-10-03): the
    same miner lane and isolation with the device attached. Omitted, it runs
    in the CPU analysis image exactly as before.
    """
    from .research_image import ResearchImageIdentity

    if accelerator is None:
        if type(image) is not ResearchImageIdentity:
            raise ValueError("miner scripts require the separate analysis image")
    else:
        from .gpu_practice import gpu_image_backend

        if accelerator != MINER_GPU or gpu_image_backend(image) is None:
            raise ValueError("a GPU code cell runs the campaign's pinned GPU worker")
    if type(source) is not str or not source:
        raise ValueError("research source required")
    return _run(
        ledger,
        owner=owner,
        identity=identity,
        source=source,
        files=files,
        image=image,
        seconds=seconds,
        provenance="MINER_SELF_REPORTED",
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
        miner_authored=True,
        **({} if accelerator is None else {"accelerator": accelerator}),
    )


class MinerProgramFailure(Exception):
    """The miner's own program failed, observed - not an infrastructure failure.

    Raised only where the evidence was observed: the miner's own wall allowance
    elapsed, the daemon reported the container OOM-killed, the miner's program
    exited nonzero inside a still-running container, or the miner's output was
    refused for its own content. The operation is already settled as
    FAILED_MINER with the full reservation retained and cleanup observed, so
    there is nothing to reconcile. Daemon, CLI and host failures never take this
    type; they stay infrastructure failures.
    """

    def __init__(self, result):
        if (
            type(result) is not dict
            or result.get("schema") != MINER_FAILURE_SCHEMA
            or result.get("failure_code")
            not in {code.value for code in MINER_FAILURE_CODES}
        ):
            raise TypeError("typed miner program failure result required")
        super().__init__(result["observation"])
        self.result = result
        self.code = WorkerCode(result["failure_code"])
        #: True only on a REPLAY of an already settled operation (`run_script`: nothing ran this time). A replay is the
        #: record of an EARLIER observation, never a new one: no door counts it against a candidate.
        self.replayed = False


MINER_FAILURE_SCHEMA = "carbon.autoresearch.miner-program-failure.v1"
# Existing worker codes, reused: the miner's allowance elapsed (DEADLINE), their
# program failed (RUNTIME: nonzero exit or OOM kill), their output was refused
# for its own content (OUTPUT), or, on a host whose resource profile is in
# force, their scratch passed its cap (POLICY, observation
# `scratch_cap_exceeded`; LANE-RESOURCE-BOUND-01).
MINER_FAILURE_CODES = frozenset(
    {WorkerCode.DEADLINE, WorkerCode.RUNTIME, WorkerCode.OUTPUT, WorkerCode.POLICY}
)


#: `CampaignLedger.reserve`'s refusal while another numerical op of the owner is RESERVED
ONE_NUMERICAL_WORKER = "one numerical worker; reconcile active operation"


def _settle_dead_numerical(ledger, *, owner, keep):
    """Settle this owner's RESERVED numerical ops left by a dead run (the caller holds the owner's numerical lease, so
    none of them has a live supervisor), each through `reconcile_worker`'s own settle (FAILED_INFRA, the reservation
    kept as conservative consumption, never a retry). A worker container still present is an ORPHAN of a dead
    process (the lease is an flock the dead holder lost; Deploy, live 116 18 Nov 2026 21:35Z: a restart without a drain
    left remote containers running and every later grade of those owners failed): it is removed by its exact name and
    the op settled; a container that cannot be confirmed gone keeps the op (`reconcile_worker`'s own check).
    ``keep`` (the op about to run) is never touched. Returns how many were settled; one logged line each
    (``op_settled_dead_reserved``), or ``op_dead_reserved_kept`` with why one was left.
    """
    import hashlib

    from carbon.battery.intake import log

    who = hashlib.sha256(owner.encode()).hexdigest()
    settled = 0
    for op in ledger.status(owner=owner)["operations"]:
        reservation = op.get("reservation") or {}
        if (
            op.get("state") != "RESERVED"
            or op.get("id") == keep
            # adopted by this start (`register_adoptable`): its task resumes it
            or _adoption(ledger, op.get("id")) is not None
            or not reservation.get("numerical_milliseconds", 0)
        ):
            continue
        try:
            _reconcile_locked(ledger, owner=owner, identity=op["id"])
        except Exception as kept:  # noqa: BLE001
            # any doubt (ssh, docker, a timeout) keeps the op as it was
            log(
                "op_dead_reserved_kept",
                owner_sha256=who,
                phase=op.get("phase"),
                reason=(
                    str(kept)[:120]
                    if isinstance(kept, ValueError)
                    else type(kept).__name__
                ),
            )
            continue
        settled += 1
        log("op_settled_dead_reserved", owner_sha256=who, phase=op.get("phase"))
    return settled


def settle_previous_runs(ledger, *, owner, before):
    """At receiver start (`OwnerProviders.restore`): settle this owner's operations still RESERVED by a PREVIOUS
    receiver process (V2's code item, live 116 21:35Z, 18 Nov 2026: the dead-RESERVED settle keeps an op whose worker
    container is still ALIVE, and a container a dead receiver started stays alive, so the owner is blocked with "one
    numerical worker; reconcile active operation"). An op created before ``before`` (this start's wall time) cannot have
    a supervisor in this process; under the owner's numerical lease (so none anywhere), its exact worker container is
    stopped by name and launch label and it is settled FAILED_INFRA (Carbon's, owed; the reservation kept as
    conservative consumption) by `reconcile_worker`'s own settle. An op created at or after ``before`` (this process's)
    and every finished op are never touched; any doubt (no exact intent, a daemon that does not answer, cleanup not
    observed) keeps the op as it was. Never raises. Returns how many were settled; one logged line each
    (``op_settled_previous_run``), or ``op_previous_run_kept`` with why one was left.
    """
    import hashlib

    from carbon.battery.intake import log

    who = hashlib.sha256(owner.encode()).hexdigest()
    try:
        with ledger.db() as db:
            rows = db.execute(
                "SELECT id, phase FROM operations WHERE owner=? AND state='RESERVED' AND created<?",
                (owner, float(before)),
            ).fetchall()
    except Exception:  # noqa: BLE001 - unreadable: the normal path reports
        return 0
    if not rows:
        return 0
    settled = 0
    try:
        with _numerical_lease(ledger):
            for identity, phase in rows:
                if _adoption(ledger, identity) is not None:
                    # adopted by this start (`register_adoptable`): its program runs on, its task resumes it
                    continue
                try:
                    _reconcile_locked(ledger, owner=owner, identity=identity)
                except Exception as kept:  # noqa: BLE001 - any doubt keeps the op
                    log(
                        "op_previous_run_kept",
                        owner_sha256=who,
                        phase=phase,
                        reason=(
                            str(kept)[:120]
                            if isinstance(kept, ValueError)
                            else type(kept).__name__
                        ),
                    )
                    continue
                settled += 1
                log("op_settled_previous_run", owner_sha256=who, phase=phase)
    except ValueError:
        # the lease is held: a live supervisor exists after all, so nothing is touched
        log("op_previous_run_kept", owner_sha256=who, reason="lease_held")
    return settled


@contextmanager
def _numerical_lease(ledger):
    import fcntl

    path = ledger.root / "numerical-supervisor.lock"
    if path.is_symlink():
        raise ValueError("numerical lease symlink")
    with path.open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError(
                "numerical supervisor active; do not reconcile live work"
            ) from None
        yield


def _cancel_path(ledger, owner, identity):
    return ledger.root / (
        "cancel-" + digest(canonical([owner, identity]))[7:] + ".json"
    )


def request_cancel(ledger, *, owner, identity):
    """Trusted task provider only; a flag grants no arbitrary process handle."""
    write_once(
        _cancel_path(ledger, owner, identity),
        canonical({"owner": owner, "identity": identity}),
    )


def _check_cancel(ledger, owner, identity):
    if _cancel_path(ledger, owner, identity).exists():
        raise ValueError("research operation cancelled")


#: A direct task's phase identity (`bundle_construction_worker.
#: direct_child_identity`): one task digest, one phase.
_DIRECT_PHASE = re.compile(r"(direct-[0-9a-f]{64}-)(?:prep|build|inference|timed)")


def _one_trial_per_task(ledger, identity, extra_resources):
    """`extra_resources` with the research trial charged once per direct task
    (Launchpad round 6, R6-3). A practice's build and inference phases each
    asked for one, so one practice counted as two attempted trials and the
    page showed "started but not finished" trials that never existed. The
    task's first phase to reach the ledger charges it; a later phase does not.
    A phase already in the ledger keeps exactly what it reserved, so an
    earlier campaign resumes and replays unchanged and its stored counts are
    never rewritten."""
    if (extra_resources or {}).get("research_trials") != 1:
        return extra_resources
    match = _DIRECT_PHASE.fullmatch(identity) if type(identity) is str else None
    if match is None:
        return extra_resources
    without = {k: v for k, v in extra_resources.items() if k != "research_trials"}
    with ledger.db() as db:
        own = db.execute(
            "SELECT reservation FROM operations WHERE id=?", (identity,)
        ).fetchone()
        siblings = (
            []
            if own is not None
            else db.execute(
                "SELECT reservation FROM operations WHERE id LIKE ? AND id != ?",
                (match.group(1) + "%", identity),
            ).fetchall()
        )
    if own is not None:
        recorded = json.loads(own[0]).get("research_trials", 0)
        return extra_resources if recorded else without
    if any(json.loads(row[0]).get("research_trials", 0) for row in siblings):
        return without
    return extra_resources


def _run(ledger, **kwargs):
    identity = kwargs["identity"]
    if (
        remote_lane.current() is not None
        and kwargs.get("provenance") == "MINER_SELF_REPORTED"
    ):
        # The miner's own lane bind-mounts a writable scratch it reads back here: never on a REMOTE grade lane, nor
        # rebound to this host's cores beside a local lane.
        raise remote_lane.RemoteLaneDown(b"remote_lane_miner_lane")
    # (`remote_lane.local_for`, which moved a remote round's timing ops onto this host, is no longer called; it stays in
    # that module only because the module is a worker-image build input, whose bytes must not move with this change.)
    # Every op of a REMOTE grade lane's round, its speed stage included, sends its docker calls to the lane's daemon (owner
    # D6: timed on the box, on the lane's pinned cores); ``timed`` (a control that asks for a timing measurement) only
    # keeps such an op off a remote GPU build slot.
    # an op this start adopted (a remote GPU build whose program ran on through a restart): followed, never relaunched
    adoption = _adoption(ledger, identity)
    if adoption is not None:
        return _run_adopted(ledger, adoption, **kwargs)
    timed = _timed_control(kwargs.get("files"))
    # A GPU BUILD of a build offered a remote GPU build lane takes one of its slots for its whole life and runs on that
    # machine (`remote_gpu_build.op`); every other op (inference, timing, grading) is unchanged. An op the ledger has
    # already settled replays its recorded result here and takes no slot.
    owner = kwargs.get("owner")
    settled = (
        remote_gpu_build.offered_lane() is not None
        and owner is not None
        and callable(getattr(ledger, "operation_state", None))
        and ledger.operation_state(identity, owner=owner) not in (None, "RESERVED")
    )
    # Option A (Lead 17 Nov 2026): an op bound for a REMOTE GPU build box runs on none of this host's cores, so a build
    # round gives its LOCAL lane back for the op, its slot wait included, and holds a lane again once the op has ended,
    # before the op's error leaves here (`grade_lanes.released`): the door's other rounds grade on that lane meanwhile.
    off_host = (
        not settled
        and remote_gpu_build.offered_off_host()
        and remote_gpu_build.eligible(
            identity,
            accelerator=kwargs.get("accelerator"),
            provenance=kwargs.get("provenance"),
            timed=timed,
        )
    )
    from carbon.reconstruction import grade_lanes

    with (
        # the op named, so its lane or slot waits show as waiting, never building (`grade_lanes.waiting_for`)
        grade_lanes.running_op(identity),
        # an op on this host: a build round that started laneless holds a local lane first (`grade_lanes.laned`)
        grade_lanes.released() if off_host else grade_lanes.laned(),
        remote_gpu_build.op(
            identity,
            accelerator=kwargs.get("accelerator"),
            settled=settled,
            # a settled op's replay binds the box its intent recorded (its request names that box's device)
            recorded=_recorded_build(ledger, owner, identity) if settled else None,
            provenance=kwargs.get("provenance"),
            timed=timed,
            check=(
                None
                if ledger is None or owner is None
                else lambda: (
                    _raise_if_stopping(),
                    _check_cancel(ledger, owner, identity),
                )
            ),
        ) as remote_build,
    ):
        try:
            if remote_build is None or settled:
                return _run_supervised(ledger, **kwargs)
            # a REMOTE GPU build's wall is read against its own box (CV-Motor L12624 (b) + (c))
            with _remote_build_guarded(remote_build):
                return _run_supervised(ledger, **kwargs)
        except MinerProgramFailure:
            # settled in the ledger as the candidate's (a resource stop is retyped BEFORE it is settled): never retyped
            raise
        except Exception as error:
            # A GPU shared by more than one build: a device memory exhaustion beside a neighbour is Carbon's.
            if remote_build is not None and remote_gpu_build.shared_memory_exhausted(
                error, _MEMORY_EXHAUSTED_MARKERS
            ):
                raise remote_lane.RemoteLaneDown(
                    b"remote_gpu_build_shared_device_memory"
                ) from error
            # A remote build that failed while its link or its GPU is unhealthy is Carbon's, never the miner's.
            down = None if remote_build is None else remote_gpu_build.retyped(error)
            if down is not None:
                raise down from error
            raise


def _recorded_build(ledger, owner, identity):
    """The GPU build slot binding the op's durable intent recorded (`remote_gpu_build.recorded`), or None (no single
    readable intent, or none recorded)."""
    from pathlib import Path

    found = []
    root = getattr(ledger, "root", None)
    if root is None:
        return None
    for path in Path(root).glob("operation-*/intent.json"):
        try:
            if path.is_symlink() or path.stat().st_size > 65536:
                continue
            value = json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue
        if (
            type(value) is dict
            and value.get("owner") == owner
            and value.get("identity") == identity
        ):
            found.append(value)
    if len(found) != 1:
        return None
    try:
        return remote_gpu_build.recorded(found[0])
    except (ValueError, OSError):
        return None


def _run_supervised(ledger, **kwargs):
    import contextvars
    import threading

    owner, identity = kwargs["owner"], kwargs["identity"]
    with _numerical_lease(ledger):
        _check_cancel(ledger, owner, identity)
        stop = threading.Event()
        errors = []

        def watch():
            # Finite worker-lifetime helper. It never dispatches numerical work,
            # reads another owner's intent, or accepts a caller container name.
            while not stop.wait(0.1):
                if not _cancel_path(ledger, owner, identity).exists():
                    continue
                try:
                    _cancel_active_intent(ledger, owner=owner, identity=identity)
                except Exception:  # noqa: BLE001
                    errors.append("cancellation cleanup uncertain")
                    return

        def settle():
            # Called immediately before the ledger records a terminal state.
            # The watcher is stopped and its errors read first, so the ledger
            # can never say an operation finished while the task then fails on
            # an uncertain cancellation: raising here leaves it RESERVED.
            stop.set()
            watcher.join(timeout=45)
            if watcher.is_alive():
                raise ValueError("cancellation supervisor did not stop")
            if errors:
                raise ValueError(errors[0])

        # the round's context (its grade lane, so a remote lane's container is cancelled on its own daemon)
        watcher = threading.Thread(
            target=contextvars.copy_context().run, args=(watch,), daemon=True
        )
        watcher.start()
        try:
            result = _run_locked(ledger, before_finish=settle, **kwargs)
            if errors:
                raise ValueError(errors[0])
            return result
        finally:
            stop.set()
            watcher.join(timeout=45)
            if watcher.is_alive():
                raise ValueError("cancellation supervisor did not stop")


def _cancel_active_intent(ledger, *, owner, identity):
    cli = DockerCLI()
    for path in ledger.root.glob("operation-*/intent.json"):
        if path.is_symlink() or path.stat().st_size > 65536:
            raise ValueError("invalid cancellation intent")
        intent = json.loads(path.read_bytes())
        if (intent.get("owner"), intent.get("identity")) != (owner, identity):
            continue
        launch = digest(
            canonical(
                {"owner": owner, "identity": identity, "request": intent["request"]}
            )
        )
        name, label = _intent_container(intent, launch)
        if (
            intent["launch"] != launch
            or intent["container"] != name
            or path.parent.name != "operation-" + launch[7:]
        ):
            raise ValueError("cancellation intent conflict")
        try:
            if (
                type(intent["request"]) is dict
                and intent["request"].get("provenance") == LIBRARY_PREP_PROVENANCE
            ):
                _retain_fixed_program_evidence(
                    path.parent,
                    "private-owned-cancel-observation.json",
                    {
                        "schema": "carbon.autoresearch.owned-cancel-observation.v1",
                        "launch_digest": launch,
                        "observed_unix": time.time(),
                        "action": "CANCEL_CLEANUP_REQUESTED",
                        "interpretation": "Request observed; cleanup outcome is separate.",
                    },
                )
        except Exception:  # noqa: BLE001, S110 - observation never gates cleanup
            pass
        # a remote GPU build slot's container is removed on its box's daemon, its slot record finished there; a box
        # whose file is gone (drained or refused) is still reached through its copy when it can be (`_clear_gone_box`)
        remote_build = remote_gpu_build.recorded(intent)
        if remote_build is not None and remote_build.gone:
            _clear_gone_box(remote_build, name, label)
            continue
        with remote_gpu_build.bound(remote_build):
            remove_exact_container(
                cli=remote_gpu_build.cli(remote_build) or cli,
                container_name=name,
                launch_digest=label,
            )


def _clear_gone_box(remote_build, name, label):
    """A recorded op on a box whose file is gone (`remote_gpu_build.recorded` ``gone``): remove its container through the
    box COPY's pinned wrapper, best effort, and clear its local slot record only once that worked, so a slot whose
    container may still run is never offered again. Returns whether it was removed."""
    if remote_build.lane.device is None:
        return False
    try:
        with remote_gpu_build.bound(remote_build):
            remove_exact_container(
                cli=remote_gpu_build.cli(remote_build),
                container_name=name,
                launch_digest=label,
            )
    except Exception:  # noqa: BLE001 - its own watchdog and sweep remove the container
        return False
    remote_gpu_build.forget(remote_build)
    return True


# Fixed public construction phases use the same private, closed diagnostic
# vocabulary. These records never enter the worker snapshot or public task.
#: The direct graph route's inference program (the counted grade's graded pass, its pair, the single-call loop and the menu
#: re-check all run it). It was in neither evidence set, so a failed graph inference left only `intent.json` and its input
#: folder, a slow model's wall stop and a stalled worker alike (13 Nov, Motor 1.8 testnet wall stops): nothing said how far a
#: stop got. It now keeps the same private, bounded, closed-vocabulary evidence as the bundle inference.
GRAPH_INFERENCE_PROVENANCE = "DIRECT_GRAPH_PUBLIC_INFERENCE"
_FIXED_DIAGNOSTIC_PROVENANCES = frozenset(
    {
        "BATTERY_PUBLIC_PRACTICE",
        LIBRARY_PREP_PROVENANCE,
        LIBRARY_BUILD_PROVENANCE,
        LIBRARY_OVERLAY_BUILD_PROVENANCE,
        "DIRECT_BUNDLE_PUBLIC_INFERENCE",
        GRAPH_INFERENCE_PROVENANCE,
    }
)


class HostTooSmall(ValueError):
    """The host's Docker sees less memory or fewer CPUs than the practice worker needs
    (the worker runs under a memory limit and Docker must see that plus 1 GiB, and the
    worker's CPUs). The numbers are the miner's own machine's and the worker profile's,
    so they are safe to record and to say."""

    def __init__(self, seen_memory_bytes, seen_cpus, needs_memory_bytes, needs_cpus):
        super().__init__("research host too small")
        self.capacity = {
            "memory_gib": round(seen_memory_bytes / 1024**3, 1),
            "cpus": seen_cpus,
            "needs_memory_gib": round(needs_memory_bytes / 1024**3, 1),
            "needs_cpus": needs_cpus,
        }


def _host_capacity_shortfall(checked, sizing):
    """`HostTooSmall` for a doctor verdict that failed on capacity, else None."""
    from carbon.reconstruction.worker.docker_runtime import (
        CPU_COUNT,
        MEMORY_BYTES,
    )

    if getattr(checked, "code", None) != "worker.doctor.capacity_or_cgroup_ineligible":
        return None
    host = getattr(checked, "host", None)
    info = host.get("info") if isinstance(host, dict) else None
    if not isinstance(info, dict):
        return None
    profile = sizing.get("worker_profile")
    needs_memory = (
        MEMORY_BYTES if profile is None else profile.effective_memory_bytes
    ) + 1024**3
    needs_cpus = CPU_COUNT if profile is None else profile.effective_cpu_count
    memory, cpus = info.get("MemTotal"), info.get("NCPU")
    if type(memory) is not int or type(cpus) is not int:
        return None
    if memory >= needs_memory and cpus >= needs_cpus:
        return None  # capacity is fine: the cgroup version or the engine mode is not
    return HostTooSmall(memory, cpus, needs_memory, needs_cpus)


_PRACTICE_FAILURE_STAGES = frozenset(
    {
        "STAGING",
        "HOST_READINESS",
        "PROFILE",
        "DEVICE_LEASE",
        "CHECK_CANCEL",
        "CREATE",
        "WATCHDOG",
        "START",
        "CONTROLS",
        "PROGRAM",
        "OBSERVE",
        "EXPORT",
        "RESOURCES",
        "CLEANUP",
        "LEASE_RELEASE",
        "DECODE",
        "VALIDATE",
        "ASSOCIATE",
    }
)
_PRACTICE_FAILURE_MARKERS = {
    b"CUDA_ERROR_OUT_OF_MEMORY": "CUDA_ERROR_OUT_OF_MEMORY",
    b"CUDA_ERROR_NO_DEVICE": "CUDA_ERROR_NO_DEVICE",
    b"CUDA_ERROR_INSUFFICIENT_DRIVER": "CUDA_ERROR_INSUFFICIENT_DRIVER",
    b"CUDA_ERROR_SYSTEM_DRIVER_MISMATCH": "CUDA_ERROR_SYSTEM_DRIVER_MISMATCH",
    b"CUDA_ERROR_UNSUPPORTED_PTX_VERSION": "CUDA_ERROR_UNSUPPORTED_PTX_VERSION",
    b"CUBLAS_STATUS_ALLOC_FAILED": "CUBLAS_STATUS_ALLOC_FAILED",
    b"CUDNN_STATUS_NOT_INITIALIZED": "CUDNN_STATUS_NOT_INITIALIZED",
    b"nvidia-container-cli: initialization error": "NVIDIA_INITIALIZATION_ERROR",
    b"driver/library version mismatch": "NVIDIA_DRIVER_LIBRARY_MISMATCH",
    b"unsatisfied condition: cuda": "NVIDIA_CUDA_REQUIREMENT_UNSATISFIED",
    b"stream command timed out": "STREAM_TIMEOUT",
    b"stream output exceeded cap": "STREAM_OUTPUT_CAP",
    # What a program that stopped on its own printed last (the closed names of the
    # Python and XLA exceptions a model run raises, and Carbon's own output checks).
    b"MemoryError": "PYTHON_MEMORY_ERROR",
    b"Cannot allocate memory": "CANNOT_ALLOCATE_MEMORY",
    b"RESOURCE_EXHAUSTED": "XLA_RESOURCE_EXHAUSTED",
    b"Out of memory": "OUT_OF_MEMORY",
    b"FloatingPointError": "FLOATING_POINT_ERROR",
    b"bundle inference output contract differs": "OUTPUT_CONTRACT_DIFFERS",
    b"bundle inference input binding differs": "INPUT_BINDING_DIFFERS",
    b"graph inference output arity differs": "OUTPUT_ARITY_DIFFERS",
    b"XlaRuntimeError": "XLA_RUNTIME_ERROR",
    b"Traceback (most recent call last)": "PYTHON_TRACEBACK",
    b"ValueError": "PYTHON_VALUE_ERROR",
    b"container stopped before its done-file": "CONTAINER_STOPPED_EARLY",
}


def _stopped_container_facts(diagnostic):
    """The engine's recorded exit code and kernel-kill flag of a container that stopped
    before its done-file (`controller._stopped_diagnostic`): two closed values (an
    integer and a boolean), or {}."""
    try:
        line = next(
            row
            for row in diagnostic.split(b"\n")
            if row.startswith(b"state:{") and len(row) < 512
        )
        state = json.loads(line[len(b"state:") :])
    except (StopIteration, ValueError):
        return {}
    facts = {}
    if type(state) is dict:
        code = state.get("ExitCode")
        if type(code) is int and -256 <= code <= 255:
            facts["container_exit_code"] = code
        if type(state.get("OOMKilled")) is bool:
            facts["container_oom_killed"] = state["OOMKilled"]
    return facts


#: Product-raised ValueError messages a failed practice stage may name, as closed codes (matched by
#: prefix, so a message's trailing detail is never recorded). Anything else records no reason.
_PRACTICE_FAILURE_REASONS = (
    ("pinned library parent ineligible", "LIBRARY_PARENT_INELIGIBLE"),
    ("library worker identity differs", "LIBRARY_WORKER_IDENTITY_DIFFERS"),
    ("library worker child binding differs", "LIBRARY_CHILD_BINDING_DIFFERS"),
    ("pinned local uv image differs", "UV_IMAGE_DIFFERS"),
    ("required local image absent", "REQUIRED_LOCAL_IMAGE_ABSENT"),
    ("research host too small", "HOST_TOO_SMALL"),
)


_TRACEBACK_FRAME = re.compile(
    rb'^\s*File "(?P<path>[^"\n]{1,300})", line (?P<line>\d{1,6}), in (?P<name>[A-Za-z_<][A-Za-z0-9_<>]{0,80})\s*$'
)
_EXCEPTION_LINE = re.compile(rb"^(?P<name>[A-Za-z_][A-Za-z0-9_.]{0,80})(?::|$)")


def _traceback_summary(diagnostic):
    """Where a program that stopped on a Python exception stopped, without any message text:
    the exception's class name and its last frames as `file.py:line:function` (file base names
    and function names are code, never data). Nothing when the diagnostic holds no traceback
    (Test Runner 11:13Z: Cooling 1.4's timed run died with only the PYTHON_TRACEBACK marker
    recorded, and the cause was unrecoverable from the record)."""
    start = diagnostic.rfind(b"Traceback (most recent call last)")
    if start < 0:
        return {}
    lines = diagnostic[start:].split(b"\n")
    frames = []
    for row in lines[1:]:
        found = _TRACEBACK_FRAME.match(row)
        if found:
            base = found["path"].rsplit(b"/", 1)[-1].decode("ascii", "replace")
            name = found["name"].decode("ascii", "replace")
            frames.append(f"{base}:{int(found['line'])}:{name}"[:160])
    last = next(
        (row for row in reversed(lines) if row.strip() and not row.startswith(b" ")),
        b"",
    )
    named = _EXCEPTION_LINE.match(last)
    summary = {}
    if named is not None and not named["name"].startswith(b"Traceback"):
        summary["worker_exception_class"] = named["name"].decode("ascii", "replace")
    if frames:
        summary["worker_traceback_frames"] = frames[-8:]
    return summary


def _retain_stage_traceback(operation, stage, error):
    """The bounded, private traceback of a failure before the fixed program ran.

    `failure-<STAGE>.json` is closed metadata and names no text, so a STAGING, CREATE or START failure
    (a Docker, filesystem or device fault on this host) gave no way to tell which call failed (a GPU
    prep that fell back to CPU on a fresh 4090 VM with only `worker_code runtime.failed`). This keeps,
    beside the operation, the exception chain with its traceback and the controller's own private
    diagnostic bytes. It is the owner's host's private file, like `private-prep-program-diagnostic.bin`:
    never part of a public result or a model snapshot. Best effort; it never gates the failure.
    """
    try:
        import traceback

        if stage in ("PROGRAM", "EXPORT") or stage not in _PRACTICE_FAILURE_STAGES:
            return  # those keep the controller's stderr (`private-*-program-diagnostic.bin`)
        text = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        diagnostic = getattr(error, "private_diagnostic", b"")
        if type(diagnostic) is bytes and diagnostic:
            text += "\n-- controller diagnostic --\n" + diagnostic[:16384].decode(
                "utf-8", "replace"
            )
        write_once(
            operation / ("private-" + stage.lower() + "-traceback.txt"),
            text.encode("utf-8", "replace")[:32768],
        )
    except Exception:  # noqa: BLE001, S110 - diagnostics never gate work
        pass


def _retain_practice_failure(operation, stage, error):
    """Best-effort closed metadata, never exception text or a result artifact."""
    try:
        if stage not in _PRACTICE_FAILURE_STAGES:
            return
        category = next(
            (
                name
                for kind, name in (
                    (WorkerFailure, "WorkerFailure"),
                    (ValueError, "ValueError"),
                    (TimeoutError, "TimeoutError"),
                    (OSError, "OSError"),
                    (RuntimeError, "RuntimeError"),
                )
                if isinstance(error, kind)
            ),
            "Exception",
        )
        code = error.code if isinstance(error, WorkerFailure) else None
        diagnostic = (
            error.private_diagnostic if isinstance(error, WorkerFailure) else b""
        )
        diagnostic = diagnostic[:65536] if type(diagnostic) is bytes else b""
        # A marker is an untrusted hint from a fixed vocabulary, not a proven
        # cause. No captured substring, arbitrary name or diagnostic is stored.
        markers = sorted(
            {
                value
                for token, value in _PRACTICE_FAILURE_MARKERS.items()
                if token.lower() in diagnostic.lower()
            }
        )
        controls = (
            controls_predicate(error)
            if stage == "CONTROLS"
            and isinstance(error, WorkerFailure)
            and error.code is WorkerCode.POLICY
            else None
        )
        reason = next(
            (
                name
                for prefix, name in _PRACTICE_FAILURE_REASONS
                if isinstance(error, ValueError) and str(error).startswith(prefix)
            ),
            None,
        )
        write_once(
            operation / ("failure-" + stage + ".json"),
            canonical(
                {
                    "schema": "carbon.autoresearch.fixed-practice-failure.v1",
                    "stage": stage,
                    "exception_class": category,
                    "worker_code": code.value if type(code) is WorkerCode else None,
                    "diagnostic_markers": markers,
                    **_stopped_container_facts(diagnostic),
                    **_traceback_summary(diagnostic),
                    **({} if reason is None else {"reason": reason}),
                    **(
                        {"capacity": error.capacity}
                        if isinstance(error, HostTooSmall)
                        else {}
                    ),
                    **({} if controls is None else {"controls_predicate": controls}),
                }
            ),
        )
    except Exception:  # noqa: BLE001 - diagnostics must not replace the failure
        return


_CGROUP_PATH = re.compile(r"/[A-Za-z0-9_.:@-]+(?:/[A-Za-z0-9_.:@-]+)*")


def _read_small_file(path, limit=4096):
    """At most ``limit`` bytes of one regular file, never following a link; None when it cannot be read as such."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if not stat_module.S_ISREG(os.fstat(fd).st_mode):
            return None
        raw = os.read(fd, limit + 1)
    finally:
        os.close(fd)
    return raw if 0 < len(raw) <= limit else None


def _fixed_program_cpu_usage_usec(
    cli,
    *,
    container_name,
    launch_digest,
    deadline,
    proc_root="/proc",
    cgroup_root="/sys/fs/cgroup",
):
    """The container cgroup's cumulative CPU time in microseconds (``usage_usec`` of ``cpu.stat``), or None.

    Read from the HOST (no ``docker exec`` into the candidate's container): one ``docker inspect`` for the container's full id and
    its init pid, then the host's own ``/proc/<pid>/cgroup`` for the cgroup path (cgroup v2, whichever driver names it) and that
    cgroup's ``cpu.stat``. The path is used only if it names THIS container's full id, so a reused pid cannot be another
    container's. Fail-soft, no inference: with the program's own wall time it is the host-side way to tell a pass that was
    COMPUTING (CPU time near wall time times the cores it used) from one that was BLOCKED (CPU time near zero), with no
    worker-image change. It is a number in a private record, never a decision.
    """
    try:
        remaining = deadline - time.monotonic()
        if (
            not math.isfinite(remaining)
            or remaining <= 0
            or type(launch_digest) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", launch_digest) is None
            or container_name not in _container_names(launch_digest)
        ):
            return None
        raw = cli.run(
            ["inspect", container_name, "--format", "{{.Id}} {{.State.Pid}}"],
            timeout=min(0.5, remaining),
        ).stdout
        if type(raw) is not bytes or not 0 < len(raw) <= 256:
            return None
        parts = raw.decode("ascii", "strict").split()
        if len(parts) != 2 or re.fullmatch(r"[0-9a-f]{64}", parts[0]) is None:
            return None
        if not parts[1].isdecimal() or not 0 < int(parts[1]) < 2**22:
            return None
        container_id, pid = parts[0], int(parts[1])
        listing = _read_small_file(f"{proc_root}/{pid}/cgroup")
        if listing is None:
            return None
        relative = None
        for line in listing.decode("ascii", "strict").splitlines():
            if line.startswith("0::"):
                relative = line[3:]
        if (
            relative is None
            or _CGROUP_PATH.fullmatch(relative) is None
            or any(part in ("", ".", "..") for part in relative.split("/")[1:])
            or container_id not in relative
        ):
            return None
        counters = _read_small_file(f"{cgroup_root}{relative}/cpu.stat")
        if counters is None:
            return None
        for line in counters.decode("ascii", "strict").splitlines():
            key, _, number = line.partition(" ")
            if key == "usage_usec":
                value = int(number) if number.isdecimal() else None
                return value if value is not None and value < 2**64 else None
    except Exception:  # noqa: BLE001 - a private observation never gates work
        return None
    return None


_PROGRAM_STATE_FORMAT = (
    '{"launch_digest":{{json (index .Config.Labels '
    '"org.opencontainers.image.carbon.c03.launch")}},'
    '"image_id":{{json .Image}},"running":{{json .State.Running}},'
    '"oom_killed":{{json .State.OOMKilled}},"exit_code":{{json .State.ExitCode}}}'
)
_PRIVATE_PROGRAM_FILES = frozenset(
    {
        "private-program-baseline.json",
        "private-program-failure-evidence.json",
        "private-export-failure-evidence.json",
        "private-container-end-evidence.json",
        "private-owned-cancel-observation.json",
    }
)
_PROGRAM_EVIDENCE_PROVENANCES = frozenset(
    {
        LIBRARY_PREP_PROVENANCE,
        LIBRARY_OVERLAY_BUILD_PROVENANCE,
        GRAPH_INFERENCE_PROVENANCE,
    }
)


def _retain_fixed_program_evidence(operation, filename, value):
    """A private observation never replaces the worker outcome or cleanup."""
    try:
        if filename not in _PRIVATE_PROGRAM_FILES:
            return None
        raw = canonical(value)
        if len(raw) > 4096:
            return None
        write_once(operation / filename, raw)
        return digest(raw)
    except Exception:  # noqa: BLE001 - failure diagnostics are best effort
        return None


def _fixed_program_container_observation(
    cli, *, container_name, launch_digest, image_id, deadline
):
    """At most two bounded reads of this exact launch; no causal inference."""
    unknown = {"status": "UNKNOWN", "state": None, "memory": None}

    def budget():
        remaining = deadline - time.monotonic()
        if not math.isfinite(remaining) or remaining <= 0:
            raise TimeoutError("private observation budget elapsed")
        return min(0.5, remaining)

    def integer(value):
        return type(value) is int and 0 <= value < 2**64

    try:
        if (
            type(deadline) not in (int, float)
            or not math.isfinite(deadline)
            or type(launch_digest) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", launch_digest) is None
            or type(image_id) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None
            or container_name not in _container_names(launch_digest)
        ):
            return unknown
        value = cli.json(
            ["inspect", container_name, "--format", _PROGRAM_STATE_FORMAT],
            timeout=budget(),
        )
        if (
            type(value) is not dict
            or set(value)
            != {"launch_digest", "image_id", "running", "oom_killed", "exit_code"}
            or value["launch_digest"] != launch_digest
            or value["image_id"] != image_id
            or type(value["running"]) is not bool
            or type(value["oom_killed"]) is not bool
            or not integer(value["exit_code"])
            or value["exit_code"] > 255
        ):
            return unknown
        result = {
            "status": "OBSERVED",
            "state": {
                "running": value["running"],
                "oom_killed": value["oom_killed"],
                "exit_code": value["exit_code"],
            },
            "memory": None,
        }
        if not value["running"]:
            return result
        try:
            raw = cli.run(
                [
                    "exec",
                    container_name,
                    "/bin/cat",
                    "/sys/fs/cgroup/memory.events",
                    "/sys/fs/cgroup/memory.peak",
                    "/sys/fs/cgroup/memory.current",
                ],
                timeout=budget(),
            ).stdout
            if type(raw) is not bytes or not 0 < len(raw) <= 4096:
                return result
            lines = raw.decode("ascii", "strict").splitlines()
            if not 4 <= len(lines) <= 16:
                return result
            events = {}
            allowed = {"low", "high", "max", "oom", "oom_kill", "oom_group_kill"}
            for line in lines[:-2]:
                key, number = line.split()
                if key not in allowed or key in events or not number.isdecimal():
                    return result
                count = int(number)
                if not integer(count):
                    return result
                events[key] = count
            peak, current = lines[-2:]
            if not peak.isdecimal() or not current.isdecimal():
                return result
            peak, current = int(peak), int(current)
            if not {"oom", "oom_kill"} <= set(events) or not all(
                integer(item) for item in (peak, current)
            ):
                return result
            result["memory"] = {
                "current_bytes": current,
                "peak_bytes": peak,
                "events": {
                    key: events[key]
                    for key in ("oom", "oom_kill", "oom_group_kill")
                    if key in events
                },
            }
        except Exception:  # noqa: BLE001, S110 - private counters remain unknown
            pass
        return result
    except Exception:  # noqa: BLE001 - unknown is never absence or a new failure
        return unknown


_CONTAINER_END_LOG_BYTES = 1200
_CONTAINER_END_STATUS = frozenset(
    {"created", "exited", "dead", "removing", "paused", "restarting", "running"}
)
_CONTAINER_END_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]{8,20}Z")


def _printable(raw, limit):
    """Closed text for a private record: printable ASCII and newlines only."""
    return bytes(
        byte if 32 <= byte < 127 or byte == 10 else 63 for byte in bytes(raw)[-limit:]
    ).decode("ascii")


def _fixed_program_container_end(cli, *, container_name, launch_digest, deadline):
    """How a container that is no longer running ended: its State and PID 1's last output.

    The receiver removes the container at cleanup and its log goes with it, so a worker
    that ends by itself otherwise leaves only an exit code. Private observation only; a
    container that is still running, or any read that fails, gives nothing."""
    try:
        if (
            type(deadline) not in (int, float)
            or not math.isfinite(deadline)
            or type(launch_digest) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", launch_digest) is None
            or container_name not in _container_names(launch_digest)
        ):
            return None

        def budget():
            remaining = deadline - time.monotonic()
            if not math.isfinite(remaining) or remaining <= 0:
                raise TimeoutError("private observation budget elapsed")
            return min(1.0, remaining)

        value = cli.json(
            ["inspect", container_name, "--format", "{{json .State}}"],
            timeout=budget(),
        )
        if type(value) is not dict or value.get("Running") is not False:
            return None
        exit_code = value.get("ExitCode")
        status = value.get("Status")
        state = {
            "status": status if status in _CONTAINER_END_STATUS else None,
            "exit_code": (
                exit_code if type(exit_code) is int and 0 <= exit_code <= 255 else None
            ),
            "oom_killed": (
                value["OOMKilled"] if type(value.get("OOMKilled")) is bool else None
            ),
            "daemon_error": (
                _printable(value["Error"].encode("ascii", "replace"), 200)
                if type(value.get("Error")) is str
                else None
            ),
        }
        for key, field in (("started_at", "StartedAt"), ("finished_at", "FinishedAt")):
            moment = value.get(field)
            state[key] = (
                moment
                if type(moment) is str and _CONTAINER_END_TIME.fullmatch(moment)
                else None
            )
        log_tail = None
        try:
            logs = cli.run(["logs", "--tail", "40", container_name], timeout=budget())
            log_tail = _printable(logs.stdout + logs.stderr, _CONTAINER_END_LOG_BYTES)
        except Exception:  # noqa: BLE001, S110 - the State alone still helps
            pass
        return {
            "schema": "carbon.autoresearch.container-end-evidence.v1",
            "launch_digest": launch_digest,
            "observed_unix": time.time(),
            "state": state,
            "log_tail": log_tail,
            "interpretation": "Observations only; no inferred cause.",
        }
    except Exception:  # noqa: BLE001 - unknown is never absence or a new failure
        return None


def _retain_container_end(cli, operation, *, container_name, launch_digest, deadline):
    end = _fixed_program_container_end(
        cli,
        container_name=container_name,
        launch_digest=launch_digest,
        deadline=deadline,
    )
    if end is not None:
        _retain_fixed_program_evidence(
            operation, "private-container-end-evidence.json", end
        )


#: Fixed build and inference programs whose body is the candidate's own graph
#: or recipe. Their memory and wall are the candidate's to stay within, so a
#: stop at either limit is a candidate resource failure, never an infrastructure
#: failure that refunds or retries (otherwise a memory bomb is a free retry).
#: The dependency-install prep and every Carbon-only program stay infrastructure.
_CANDIDATE_RESOURCE_PROVENANCES = frozenset(
    {
        LIBRARY_BUILD_PROVENANCE,
        LIBRARY_OVERLAY_BUILD_PROVENANCE,
        "DIRECT_BUNDLE_PUBLIC_INFERENCE",
        "DIRECT_GRAPH_PUBLIC_RECONSTRUCTION",
        "DIRECT_GRAPH_PUBLIC_INFERENCE",
    }
)
#: Closed observations of a candidate resource stop (the typed failure's
#: `observation`); the worker code is RUNTIME for memory and DEADLINE for the wall.
CANDIDATE_MEMORY_LIMIT = "WORKER_MEMORY_LIMIT_REACHED"
CANDIDATE_WALL_LIMIT = "WORKER_WALL_LIMIT_REACHED"
#: Slow staging or container start is the host's, not the candidate's: the wall
#: counts as the candidate's only when the program stage started this soon.
_PROGRAM_SETUP_BUDGET_SECONDS = 60
#: What a worker that ran out of memory inside its own limit prints last.
_MEMORY_EXHAUSTED_MARKERS = (
    b"MemoryError",
    b"Cannot allocate memory",
    b"RESOURCE_EXHAUSTED",
    b"Out of memory",
)


_ALLOCATION_BYTES = (
    re.compile(rb"allocat\w*[^\n]{0,80}?(\d{4,})\s*bytes", re.IGNORECASE),
    re.compile(rb"\((\d{4,})\s*B\)"),
)
_ALLOCATION_UNITS = re.compile(
    rb"allocat\w*\s+([0-9]+(?:\.[0-9]+)?)\s*([KMGT])i?B\b", re.IGNORECASE
)
_UNIT_BYTES = {b"K": 1024, b"M": 1024**2, b"G": 1024**3, b"T": 1024**4}


def requested_allocation_bytes(diagnostic):
    """The largest allocation a worker's own memory error says it asked for, in
    bytes (XLA's "allocate N bytes" / "(NB)" and NumPy's "allocate 32.0 GiB"),
    or None when the diagnostic names none. Read from the private diagnostic
    only; nothing of it is stored or shown."""
    if type(diagnostic) is not bytes:
        return None
    found = [
        int(match.group(1))
        for pattern in _ALLOCATION_BYTES
        for match in pattern.finditer(diagnostic)
    ]
    found += [
        int(float(match.group(1)) * _UNIT_BYTES[match.group(2).upper()])
        for match in _ALLOCATION_UNITS.finditer(diagnostic)
    ]
    return max(found) if found else None


class _CandidateResourceStop(Exception):
    """A fixed program stopped at the memory or wall limit its candidate set off.

    Raised inside the program stage so the container is still cleaned up and
    its absence observed; the run then settles FAILED_MINER, typed.
    """

    def __init__(self, code, observation, limit, original):
        super().__init__(observation)
        self.code = code
        self.observation = observation
        self.limit = limit
        self.original = original


def _case_procs_fell_back(source, error) -> bool:
    """Whether a failed per-case processes program fell back in this run (`case_procs.fell_back`, Validator-2 F2): then
    the failure is Carbon's (never a candidate resource stop) and `bundle_construction_worker._infer_state` records it,
    so every later run of the same pass runs the one-process program. Any other program: False, whatever its stderr.
    """
    from .case_procs import fell_back

    diagnostic = error.private_diagnostic if isinstance(error, WorkerFailure) else b""
    return fell_back(source, diagnostic)


def _candidate_resource_stop(
    cli,
    error,
    *,
    container_name,
    launch_digest,
    image_id,
    program_started,
    box_deadline=None,
    program_timeout,
    setup_seconds,
    memory_limit_bytes,
    deadline,
    observation=None,
    accelerated=False,
):
    """``(WorkerCode, observation, limit)`` when the kernel or the clock stopped the program.

    Observed evidence only: the engine's OOM-kill flag or the cgroup's
    ``oom_kill`` count for memory (or the worker's own memory exception with
    the cgroup peak at its limit, or asking for more than the limit in one
    allocation: XLA refuses that before the kernel ever kills anything), and
    the program stage's own allowance elapsing for the wall. An allocation
    failure that asks for less than the limit stays infrastructure (host
    pressure), as does anything else, and any program stage that started
    late. ``limit`` names what was reached, for the miner's message.
    """
    memory_limit = (
        {"kind": "memory", "bytes": memory_limit_bytes}
        if type(memory_limit_bytes) is int
        else {"kind": "memory"}
    )
    diagnostic = error.private_diagnostic if isinstance(error, WorkerFailure) else b""
    if type(diagnostic) is not bytes:
        diagnostic = b""
    if observation is None:
        # The failure evidence of an evidence provenance already took this read.
        observation = _fixed_program_container_observation(
            cli,
            container_name=container_name,
            launch_digest=launch_digest,
            image_id=image_id,
            deadline=deadline,
        )
    exhausted = any(marker in diagnostic for marker in _MEMORY_EXHAUSTED_MARKERS)
    requested = requested_allocation_bytes(diagnostic) if exhausted else None
    if (
        exhausted
        and not accelerated
        and type(memory_limit_bytes) is int
        and requested is not None
        and requested > memory_limit_bytes
    ):
        # A request larger than memory.max can never be served, whatever the
        # host is doing: the candidate's own allocation (a GPU run's device
        # memory is another limit and is not judged here).
        return WorkerCode.RUNTIME, CANDIDATE_MEMORY_LIMIT, memory_limit
    if observation["status"] == "OBSERVED":
        if observation["state"]["oom_killed"] is True:
            return WorkerCode.RUNTIME, CANDIDATE_MEMORY_LIMIT, memory_limit
        memory = observation["memory"]
        if memory is not None:
            if memory["events"].get("oom_kill", 0) >= 1:
                return WorkerCode.RUNTIME, CANDIDATE_MEMORY_LIMIT, memory_limit
            if (
                type(memory_limit_bytes) is int
                and memory["peak_bytes"] >= memory_limit_bytes
                and exhausted
            ):
                return WorkerCode.RUNTIME, CANDIDATE_MEMORY_LIMIT, memory_limit
    if (
        b"stream command timed out" in diagnostic
        and setup_seconds <= _PROGRAM_SETUP_BUDGET_SECONDS
        and time.monotonic() >= program_started + program_timeout - 1
        # a REMOTE grade lane: a stalled link looks exactly like a stalled program, so the stop is the candidate's
        # only by the box's own clock (the program still running there, its whole wall run at its stop), the
        # container observed at the stop and the link up now (CV-Motor L12624; else Carbon's)
        # (a REMOTE GPU build box's link is read through its own pinned ssh: `remote_gpu_build.wall_stop_observable`)
        and remote_gpu_build.wall_stop_observable(
            observation,
            box_seconds=(
                None
                if box_deadline is None
                else lambda: _box_program_seconds(
                    cli,
                    container_name,
                    deadline=box_deadline,
                    program_started=program_started,
                    program_deadline=program_started + program_timeout,
                )
            ),
            needed=program_timeout - 1,
        )
        # a build beside other rounds: its wall is the candidate's only on a quiet host (A19, V2 F-A19)
        and _build_wall_quiet()
        # a GPU build slot: never the candidate's on a remote lane (the remote class's walls wait on Validator-Motor),
        # nor on a lane shared by more than one slot (a neighbour's load is not the candidate's); a one-slot local lane's
        # wall is read as a local GPU build's always was
        and remote_gpu_build.wall_counts()
    ):
        return (
            WorkerCode.DEADLINE,
            CANDIDATE_WALL_LIMIT,
            {"kind": "wall", "seconds": int(program_timeout)},
        )
    return None


#: Read inside a REMOTE lane's container (its python, ``-I``): the age, on the box's own kernel clock, of the ONE live
#: ``docker exec`` root there other than this read (a process whose parent is outside the container's pid namespace,
#: ppid 0, not pid 1): the program's exec (its bootstrap ``execv``s into the program, keeping its pid and start time).
#: ``none`` when there is no such process or more than one (ambiguous: Carbon's). Read-only. (Its optional arguments, a
#: proc root, own pid and clock ticks, exist for tests; the carrier passes none.)
_BOX_PROGRAM_AGE = (
    "import os,sys\n"
    "proc=sys.argv[1] if len(sys.argv)>1 else '/proc'\n"
    "me=int(sys.argv[2]) if len(sys.argv)>2 else os.getpid()\n"
    "tck=int(sys.argv[3]) if len(sys.argv)>3 else os.sysconf('SC_CLK_TCK')\n"
    "up=float(open(proc+'/uptime').read().split()[0]);ages=[]\n"
    "for p in os.listdir(proc):\n"
    " if not p.isdigit() or int(p) in (1,me):continue\n"
    " try:\n"
    "  s=open(proc+'/'+p+'/stat').read();f=s[s.rindex(')')+2:].split()\n"
    "  if f[0] in 'ZXx' or f[1]!='0':continue\n"
    "  ages.append(up-int(f[19])/tck)\n"
    " except (OSError,ValueError,IndexError):pass\n"
    "print('%.3f'%ages[0] if len(ages)==1 else 'none')\n"
)


def _box_program_seconds(
    cli, container_name, *, deadline, program_started, program_deadline
):
    """How long the program had run AT ITS STOP, on the REMOTE box's own clock, read inside its container (the age of
    its exec, `_BOX_PROGRAM_AGE`); None when it no longer runs there, is ambiguous, or anything cannot be read
    (Carbon's, never the candidate's). One bounded read, no inference.

    The read comes after the stop: the time from the controller's deadline to the read's ANSWER is taken off (the
    stop was at or after the deadline, the age was read before the answer), so a slow link only ever shortens the
    age. An age longer than the controller saw since it
    issued the exec (+1 s) is not this program's clock (e.g. a namespaced uptime): None.
    """
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        return None
    asked = time.monotonic()
    remaining = deadline - asked
    if remaining <= 0:
        return None
    try:
        raw = cli.run(
            [
                "exec",
                container_name,
                "/opt/carbon-worker/bin/python",
                "-I",
                "-c",
                _BOX_PROGRAM_AGE,
            ],
            timeout=min(10.0, remaining),
        ).stdout
        text = raw.decode("ascii", "strict").strip()
        if text == "none":
            return None
        age = float(text)
    except Exception:  # noqa: BLE001 - unreadable: None
        return None
    answered = time.monotonic()
    if not math.isfinite(age) or age < 0 or age > answered - program_started + 1:
        return None
    return age - max(0.0, answered - program_deadline)


@contextmanager
def _remote_inputs_discarded(stage):
    """On every exit, a REMOTE grade lane's copy of ``stage`` is removed (best effort: a failed link leaves it to the
    remote machine's own sweep). Outside a remote round, or for a grade session's op (``stage`` None: the session
    removes its own), nothing."""
    try:
        yield
    finally:
        if stage is not None:
            with suppress(remote_lane.RemoteLaneDown):
                remote_lane.discard(stage)
            with suppress(remote_lane.RemoteLaneDown):
                remote_gpu_build.discard(stage)


@contextmanager
def _fixed_practice_stage(operation, provenance, stage):
    try:
        yield
    except Exception as raised:
        # A candidate resource stop keeps the original failure's diagnostics.
        error = (
            raised.original if isinstance(raised, _CandidateResourceStop) else raised
        )
        if provenance in _FIXED_DIAGNOSTIC_PROVENANCES:
            _retain_practice_failure(operation, stage, error)
            _retain_stage_traceback(operation, stage, error)
        if (
            (
                provenance
                in {
                    LIBRARY_PREP_PROVENANCE,
                    LIBRARY_BUILD_PROVENANCE,
                    LIBRARY_OVERLAY_BUILD_PROVENANCE,
                }
                and stage == "PROGRAM"
            )
            or (provenance in _FIXED_DIAGNOSTIC_PROVENANCES and stage == "EXPORT")
        ) and isinstance(error, WorkerFailure):
            # The fixed Docker stream removes its partial stdout on failure.
            # Keep the bounded, private controller diagnostic for a failed
            # fixed program or exporter so its original stderr can be diagnosed.
            # This file is never part of the public result or model snapshot.
            try:
                diagnostic = error.private_diagnostic
                if type(diagnostic) is bytes and diagnostic:
                    write_once(
                        operation
                        / (
                            "private-export-diagnostic.bin"
                            if stage == "EXPORT"
                            else (
                                "private-prep-program-diagnostic.bin"
                                if provenance == LIBRARY_PREP_PROVENANCE
                                else "private-build-program-diagnostic.bin"
                            )
                        ),
                        diagnostic[:65536],
                    )
            except Exception:  # noqa: BLE001, S110 - preserve worker failure
                pass
        raise


#: ONE CONTAINER SESSION PER GRADE (item 4, Sun 15 Nov; owner "as fast as possible"). Inside `grade_session()` (opened
#: around a counted grade only), the grade's fixed inference ops run one after another in ONE worker container, each as
#: its own `docker exec` (a NEW process), instead of one container each: the create / start / teardown is paid once.
#: Everything an op records stays per op (ledger operation, intent, controls digest, outputs, evidence). The program
#: sees exactly today's paths (`/input`, `/scratch/workspace`, `/scratch/output`) and today's environment.
#: The session name keeps the carrier's `carbon-d4-` prefix, so the host's contention probes (`host_quiet`,
#: `auto_grade`) see a session container as they see any worker container; `s-` is not hex, so it never equals an
#: op's own `carbon-d4-<24 hex>` name.
SESSION_CONTAINER_PREFIX = "carbon-d4-s-"
#: The only ops that join: Carbon's fixed inference program (graded pass, pair / subset repeat, menu row check). The
#: build, the speed stage and anything timed keep their own container.
SESSION_PROVENANCES = frozenset(
    {"DIRECT_BUNDLE_PUBLIC_INFERENCE", "DIRECT_GRAPH_PUBLIC_INFERENCE"}
)
#: The session container's own hard lifetime (its deadline watchdog); a controller that dies is covered sooner by the
#: liveness reaper. An op whose own deadline would pass it starts a new session instead.
SESSION_LIFETIME_SECONDS = 3600
#: Run before every op after a session's first, as the worker user. It refuses (non-zero exit: the host then removes the
#: container and the op runs in a NEW session container, as today's next op runs in a new container) if anything of the
#: previous op could still act or be read: a process other than the image's PID 1 entrypoint (still waiting, never
#: authorized), an OOM in the cgroup or a memory peak at the limit (the per-op memory classification reads these
#: counters), or a SysV / POSIX IPC object. Then it empties /scratch and /dev/shm, restores the /scratch root's
#: mode (0700) and drops its user xattrs, and rebuilds exactly what the entrypoint makes in a new container (home,
#: tmp, cache, jax-cache at 0700, control-ready at 0400). Last it sets the /scratch root's atime and mtime to 0 and
#: refuses unless both read back 0: an op could set them (a future atime survives relatime), so none carries over.
SESSION_RESET = """
import os,shutil,sys
from pathlib import Path
me=os.getpid()
for p in os.listdir('/proc'):
    if p.isdigit() and int(p) not in (1,me): sys.exit(3)
if b'carbon.reconstruction.worker.entrypoint' not in Path('/proc/1/cmdline').read_bytes(): sys.exit(3)
s=Path('/scratch')
if os.path.lexists('/scratch/authorized'): sys.exit(4)
ev=dict(l.split() for l in Path('/sys/fs/cgroup/memory.events').read_text().splitlines())
if int(ev.get('oom','0')) or int(ev.get('oom_kill','0')): sys.exit(5)
mx=Path('/sys/fs/cgroup/memory.max').read_text().strip()
pk=Path('/sys/fs/cgroup/memory.peak')
if pk.exists() and mx!='max' and int(pk.read_text())>=int(mx): sys.exit(6)
for f in ('shm','msg','sem'):
    q=Path('/proc/sysvipc')/f
    if q.exists() and q.read_text().splitlines()[1:]: sys.exit(7)
if os.path.isdir('/dev/mqueue') and os.listdir('/dev/mqueue'): sys.exit(7)
def wipe(root):
    for name in os.listdir(root):
        p=os.path.join(root,name)
        if os.path.isdir(p) and not os.path.islink(p):
            os.chmod(p,0o700)
            for d,subs,_ in os.walk(p):
                for x in subs:
                    y=os.path.join(d,x)
                    if not os.path.islink(y): os.chmod(y,0o700)
            shutil.rmtree(p)
        else:
            os.unlink(p)
    if os.listdir(root): sys.exit(8)
wipe('/scratch')
wipe('/dev/shm')
os.chmod('/scratch',0o700)
for a in os.listxattr('/scratch'):
    if a.startswith('user.'): os.removexattr('/scratch',a)
if [a for a in os.listxattr('/scratch') if a.startswith('user.')]: sys.exit(8)
for c in ('home','tmp','cache','jax-cache'): (s/c).mkdir(mode=0o700)
(s/'control-ready').touch(mode=0o400)
os.utime('/scratch',ns=(0,0))
t=os.stat('/scratch')
if t.st_atime_ns or t.st_mtime_ns: sys.exit(9)
"""
_GRADE_SESSION: ContextVar = ContextVar("carbon_grade_session", default=None)
#: A19 (V2's F-A19): a build that runs beside other rounds (a door's parallel build rounds, `lean_recipe`) carries a
#: guard over its host: called at a wall stop, it says whether the host was QUIET for that build (no other Carbon
#: worker container, no foreign GPU compute). A wall stop is the candidate's only on a quiet host, else Carbon's
#: (FAILED_INFRA, retried), as for grades (`host_quiet`). None: no guard (today's single build loop), unchanged.
BUILD_WALL_GUARD: ContextVar = ContextVar("carbon_build_wall_guard", default=None)


def _build_wall_quiet():
    guard = BUILD_WALL_GUARD.get()
    return True if guard is None else bool(guard())


#: CV-Motor L12624 (b) + (c) for a REMOTE GPU build slot (`remote_gpu_build`): installed by the build round
#: (`lean_recipe`), called with the op's slot binding when a remote GPU op starts. It returns ``(quiet, stop)``: ``quiet()``
#: whether the op's BOX was quiet for its run (no other Carbon worker container, no foreign GPU compute), sampled ON the
#: box with every in-run sample answered (`host_quiet.box_counters`); ``stop()`` ends the sampling. The op's
#: `BUILD_WALL_GUARD` is that box's, not this host's. None installed: a remote GPU build's wall is never the candidate's.
REMOTE_BUILD_GUARD: ContextVar = ContextVar("carbon_remote_build_guard", default=None)


@contextmanager
def _remote_build_guarded(binding):
    """For a REMOTE GPU build op: its wall guard is its box's (`REMOTE_BUILD_GUARD`), never this host's; nothing
    installed is never quiet. Anything else: unchanged."""
    if remote_gpu_build.remote_box(binding) is None:
        yield
        return
    factory = REMOTE_BUILD_GUARD.get()
    quiet, stop = (lambda: False, lambda: None) if factory is None else factory(binding)
    token = BUILD_WALL_GUARD.set(quiet)
    try:
        yield
    finally:
        BUILD_WALL_GUARD.reset(token)
        with suppress(Exception):
            stop()


def _container_names(launch_digest):
    """The container names a launch digest may label: an op's own container, or a grade session's."""
    return (
        "carbon-d4-" + launch_digest[7:31],
        SESSION_CONTAINER_PREFIX + launch_digest[7:31],
    )


def _intent_container(intent, launch):
    """`(container name, container launch label)` an op's durable intent names: its own container, or the grade
    session container it ran in (the session's own launch labels that container)."""
    session = intent.get("session")
    if session is None:
        return "carbon-d4-" + launch[7:31], launch
    label = session.get("launch") if type(session) is dict else None
    if type(label) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", label) is None:
        raise ValueError("invalid grade session intent")
    return SESSION_CONTAINER_PREFIX + label[7:31], label


def _timing_stage(identity):
    """A timing op (`grade_lanes.is_timing_identity`, or inside `grade_lanes.timing_exclusive`): it runs in its own
    container on its lane's pinned cores, never in its grade's session, which is closed first. No gate is taken.
    """
    from carbon.reconstruction import grade_lanes

    return grade_lanes.is_timing_identity(identity) or bool(
        grade_lanes._EXCLUSIVE.get()
    )


def _timed_control(files):
    """Whether an op's staged control asks for a timing measurement (the batched cold query or the single-call
    loop): a timing measurement is taken in its own container, as today, never in a reused one.
    """
    raw = files.get("control.json") if type(files) is dict else None
    if raw is None:
        return False
    try:
        control = json.loads(raw)
    except (TypeError, ValueError):
        return True
    return type(control) is not dict or bool(
        control.get("measure_query") or "single_call" in control
    )


def _cli_for(remote):
    """This module's Docker CLI for a recorded REMOTE lane's daemon (`remote_lane.recorded`), or the local one (None)."""
    cli = DockerCLI()
    if remote is not None:
        cli.docker_host = remote.docker_host
    elif getattr(cli, "docker_host", None) is not None:
        cli.docker_host = None
    return cli


def _sweep_stale_sessions(root, cli):
    """Remove session folders a dead controller left (its recorded controller is gone and its container is absent);
    a folder whose controller lives, or with no readable intent yet, is never touched.
    """
    for directory in root.glob("session-*"):
        try:
            intent = json.loads((directory / "intent.json").read_bytes())
            guard = intent["reaper"]
            name = intent["container"]
            if not str(name).startswith(SESSION_CONTAINER_PREFIX):
                continue
            if liveness_reaper.process_identity(guard["pid"]) == guard["identity"]:
                continue
            # the daemon the session's intent names (a REMOTE grade lane's, or this host's), never the caller's
            remote = remote_lane.recorded(intent)
            daemon = _cli_for(remote) if remote is not None else cli
            if remote is None and getattr(cli, "docker_host", None) is not None:
                daemon = _cli_for(None)
            if daemon.run(
                ["ps", "-aq", "--filter", "name=^" + name + "$"], timeout=10
            ).stdout.strip():
                continue
            if remote is not None:
                remote_lane.discard(directory / "input", remote)
        except Exception:  # noqa: BLE001, S112 - an unreadable folder is left as it is
            continue
        shutil.rmtree(directory, ignore_errors=True)


class _GradeSession:
    """One counted grade's worker container, opened by its first member op and removed at the grade's end (or as soon
    as any op in it fails, is cancelled or would outlive it; the next member op then opens a new one). Never shared
    across grades: it lives only inside `grade_session()`."""

    def __init__(self):
        self.ledger_root = None
        self.owner = None
        self.launch = None
        self.name = None
        self.directory = None
        self.input = None
        self.live = False
        self.created = False
        self.image_id = None
        self.worker = None
        self.cpuset = None
        self.deadline_unix = None
        #: The REMOTE grade lane (`remote_lane`) the container runs on, set when it is opened; None: this host.
        self.remote = None
        self.sequence = 0
        #: How many session containers this grade opened (evidence for the timing run; never read by a decision).
        self.opened = 0

    def member(
        self,
        ledger,
        *,
        owner,
        identity,
        image,
        provenance,
        seconds,
        worker,
        bootstrap,
        plain,
        files,
    ):
        """Whether this op joins: Carbon's fixed inference program, CPU, no trusted stage or overlay, today's bootstrap,
        the grade's ledger and owner, and (once open) the session's image and worker profile.
        """
        if (
            not plain
            or getattr(self, "broken", False)
            or provenance not in SESSION_PROVENANCES
            or bootstrap != BOOTSTRAP
            or type(seconds) is not int
            or seconds + 90 > SESSION_LIFETIME_SECONDS
            or _timing_stage(identity)
            or _timed_control(files)
        ):
            return False
        if self.ledger_root is not None and (
            self.ledger_root != ledger.root or self.owner != owner
        ):
            return False
        return not self.live or (
            self.image_id == image.image_id and self.worker == worker
        )

    def prepare(self, ledger, *, owner, seconds, cli):
        """Before the op's reservation: reset a live session for this op (a refusal removes it), or retire one this op
        would outlive; then name the container the op will run in, so its intent can name it.
        """
        self.ledger_root, self.owner = ledger.root, owner
        # Retire a session this op could outlive (its wall plus the 30 s reset and the reservation).
        if self.live and time.time() + seconds + 60 > self.deadline_unix:
            self.close(cli)
        if self.live:
            try:
                cli.run(
                    [
                        "exec",
                        self.name,
                        "/opt/carbon-worker/bin/python",
                        "-I",
                        "-c",
                        SESSION_RESET,
                    ],
                    timeout=30,
                )
            except WorkerFailure:
                self.close(cli)
        if self.launch is None:
            _sweep_stale_sessions(ledger.root, cli)
            self.launch = digest(
                canonical(
                    {
                        "schema": "carbon.autoresearch.grade-session.v1",
                        "owner": owner,
                        "ledger": str(ledger.root),
                        "nonce": os.urandom(16).hex(),
                    }
                )
            )
            self.name = SESSION_CONTAINER_PREFIX + self.launch[7:31]
            self.directory = ledger.root / ("session-" + self.launch[7:])
            self.directory.mkdir(mode=0o700)
            self.input = self.directory / "input"
            self.input.mkdir(mode=0o755)
            self.input.chmod(0o755)
        self.sequence += 1

    def link(self, stage):
        """The op's staged inputs, shown at `/input` exactly as its own container would show them (hard links of the
        op's retained stage; a copy where a link is refused). The session's input folder is empty between ops.
        """
        if any(self.input.iterdir()):
            raise ValueError("grade session input not empty")
        for path in sorted(stage.iterdir()):
            if path.is_symlink() or not path.is_file():
                raise ValueError("grade session stages plain files only")
            target = self.input / path.name
            try:
                os.link(path, target)
            except OSError:
                shutil.copyfile(path, target)
                target.chmod(stat_module.S_IMODE(path.stat().st_mode))

    def open(self, *, cli, image, cpuset, worker):
        """The session's ONE create + start, under today's `create_arguments`, on the round's lane cores. A failure
        removes what was made.
        """
        guard = liveness_reaper.controller_guard()
        deadline = time.time() + SESSION_LIFETIME_SECONDS
        #: The REMOTE grade lane the container runs on (`remote_lane`), or None: its inputs live there too.
        self.remote = remote_lane.current()
        try:
            write_once(
                self.directory / "intent.json",
                canonical(
                    {
                        "schema": "carbon.autoresearch.grade-session-intent.v1",
                        "launch": self.launch,
                        "container": self.name,
                        "owner": self.owner,
                        "deadline_unix": deadline,
                        "reaper": guard,
                        # a REMOTE grade lane: the daemon (and mirror root) the stale-session sweep must use
                        **remote_lane.intent_fields(),
                    }
                ),
            )
            self.created = True
            cli.run(
                create_arguments(
                    container_name=self.name,
                    image_id=image.image_id,
                    input_directory=self.input,
                    cpuset=cpuset,
                    launch_digest=self.launch,
                    worker_profile=worker,
                ),
                timeout=30,
            )
            spawn_watchdog(
                container_name=self.name,
                launch_digest=self.launch,
                deadline_unix=float(deadline),
            )
            liveness_reaper.spawn_liveness_reaper(
                container_name=self.name, launch_digest=self.launch, guard=guard
            )
            cli.run(["start", self.name], timeout=20)
        except BaseException:
            self.close(cli)
            raise
        self.live = True
        self.opened += 1
        self.image_id, self.worker, self.cpuset = image.image_id, worker, cpuset
        self.deadline_unix = deadline

    def clear_input(self):
        if self.input is not None and self.input.is_dir():
            for path in self.input.iterdir():
                try:
                    path.unlink()
                except PermissionError:
                    # A development host that will not unlink a read-only file (Windows); a door unlinks directly.
                    path.chmod(0o600)
                    path.unlink()
            if self.remote is not None:
                # the remote container's /input empties too (a link fault raises: the caller closes the session)
                try:
                    remote_lane.mirror(self.input, self.remote)
                except remote_lane.RemoteLaneDown as error:
                    raise OSError("grade session remote input not cleared") from error

    def after_op(self, cli, *, ok):
        """The op's inputs leave `/input`; an op that did not finish cleanly takes the container with it."""
        if ok:
            try:
                self.clear_input()
            except OSError:
                self.close(cli)
            return
        try:
            self.clear_input()
        finally:
            self.close(cli)

    def close(self, cli=None):
        """Remove the exact session container (confirmed absent), delete the session folder.
        Removal that cannot be confirmed raises and keeps the folder (its intent names the container).
        """
        if self.created:
            remote = self.remote
            if cli is None and remote is not None:
                # the container is on the remote lane's daemon, whatever context closes it
                from carbon.reconstruction import grade_lanes

                with grade_lanes.bound(remote):
                    cli = DockerCLI()
            cli = cli or DockerCLI()
            remove_exact_container(
                cli=cli, container_name=self.name, launch_digest=self.launch
            )
            if cli.run(
                ["ps", "-aq", "--filter", "name=^" + self.name + "$"], timeout=10
            ).stdout.strip():
                raise ValueError("grade session cleanup uncertain")
        if self.remote is not None and self.input is not None:
            with suppress(remote_lane.RemoteLaneDown):
                remote_lane.discard(self.input, self.remote)
        if self.directory is not None:
            shutil.rmtree(self.directory, ignore_errors=True)
        self.live = self.created = False
        self.launch = self.name = self.directory = self.input = None
        self.image_id = self.worker = self.cpuset = self.deadline_unix = None


def yield_grade_session():
    """Remove this grade's live session container now (the grade goes on; its next member op opens a new one). Called by
    a grade waiting for its commit turn (`carbon.challenge_validator.grade_sequencer`), so the idle container never sits
    on the lane's cores meanwhile. No-op without a live session. Returns whether no container of the session is left
    (none, or removed and confirmed): only then may the grade give its lane back (`grade_lanes.given_back`).
    """
    session = _GRADE_SESSION.get()
    if session is None:
        return True
    if getattr(session, "broken", False):
        return False
    if session.live:
        try:
            session.close()
        except Exception as failure:  # noqa: BLE001 - best effort, retried at exit
            # The container is NOT confirmed gone: no later op joins it (`broken`), and the grade session's own exit
            # removes it, confirmed, or reports it.
            session.live = False
            session.broken = True
            with suppress(Exception):
                from carbon.battery.intake import log

                log("grade_session_yield_uncertain", type=type(failure).__name__)
            return False
    return True


@contextmanager
def grade_session():
    """One counted grade's session (item 4). Ops run in it only through `_run_locked`'s membership rule; everything is
    removed when this exits, normally or not. Never nested, never reused across grades.
    """
    if _GRADE_SESSION.get() is not None:
        raise ValueError("grade sessions do not nest")
    session = _GradeSession()
    token = _GRADE_SESSION.set(session)
    failed = True
    try:
        yield session
        failed = False
    finally:
        _GRADE_SESSION.reset(token)
        try:
            session.close()
        except Exception:
            if not failed:
                raise


def _run_locked(
    ledger,
    *,
    owner,
    identity,
    source,
    files,
    image,
    seconds,
    provenance,
    extra_resources,
    phase="research",
    program_name="program.py",
    bootstrap=BOOTSTRAP,
    execution_contract=None,
    output_validator=None,
    miner_authored=False,
    before_finish=None,
    accelerator=None,
    network=None,
    executable_files=(),
    trusted_overlay=None,
    trusted_stage_provider=None,
    trusted_stage_identity=None,
    worker_resources_version=None,
    rebuild_wall_seconds=None,
    adopt=None,
):
    before_finish = before_finish or (lambda: None)
    # A GPU build slot of a lane split into N > 1 slots: the program caps its own share of the device first, JAX's and
    # PyTorch's (`remote_gpu_build.with_slot_prelude`); one slot, or any other op: the program is unchanged.
    source = remote_gpu_build.with_slot_prelude(source, program_name=program_name)
    # The miner's own research has no Carbon limits (owner direction): any
    # positive wall allowance, or none at all. Carbon's own work in this carrier
    # keeps its bounded allowance.
    miner_lane = provenance == "MINER_SELF_REPORTED"
    if miner_lane and remote_lane.current() is not None:
        # The miner's own lane bind-mounts a writable scratch it reads back here: never on a REMOTE grade lane.
        raise remote_lane.RemoteLaneDown(b"remote_lane_miner_lane")
    if miner_lane:
        if seconds is not None and (type(seconds) is not int or seconds < 1):
            raise ValueError("a positive wall allowance, or none")
        if seconds is None and _has_time_budget(ledger):
            # The miner's own budget still binds where they set one: a run
            # with no allowance could not be reserved against it.
            raise ValueError(
                "you set a compute-time budget; give this run a wall allowance"
            )
    # A graph route v2 version's build or inference runs under its longer
    # rebuild wall (OWNER-SANDBOX-REBUILD-WALL-01), named by the caller from
    # the version's trusted limits document; every other run keeps 600 s.
    if rebuild_wall_seconds is not None and (
        miner_lane
        or rebuild_wall_seconds != REBUILD_LIMIT_SECONDS
        or provenance in (G5_PROVENANCE, LIBRARY_PREP_PROVENANCE)
    ):
        raise ValueError("unsupported rebuild wall")
    if not miner_lane and (
        type(seconds) is not int or not 40 <= seconds <= (rebuild_wall_seconds or 600)
    ):
        raise ValueError("bounded worker wall allowance required")
    # A next version's larger worker resources (OWNER-WORKER-RESOURCES-LARGE-
    # MODELS-01), named by the allowlist version the run builds under. Only
    # Carbon's bounded C-03 lane takes them; the miner lane is bounded, if at
    # all, by its host's own profile.
    if worker_resources_version is not None and (
        miner_lane
        or resources_version_for(worker_resources_version) != worker_resources_version
    ):
        raise ValueError("unsupported worker resources")
    output_bytes = worker_resources_for(worker_resources_version)["output_bytes"]
    if type(files) is not dict or "program.py" in files or program_name in files:
        raise ValueError("closed stage required")
    if executable_files not in ((), ("uv-bin",)) or (
        executable_files and provenance != LIBRARY_PREP_PROVENANCE
    ):
        raise ValueError("trusted preparation executable role required")
    for name, body in files.items():
        ResearchWorkspace.name(name)
        if type(body) is not bytes:
            raise ValueError("stage accepts bytes, never paths")
    trusted_stage_bound = 0
    if trusted_stage_provider is not None:
        from .library_bundles import UV_IMAGE

        if (
            provenance != LIBRARY_PREP_PROVENANCE
            or not callable(trusted_stage_provider)
            or type(trusted_stage_identity) is not dict
            or set(trusted_stage_identity)
            not in (
                {"schema", "uv_image", "bundle_ref", "parent_image_id"},
                {"schema", "uv_image", "bundle_ref", "parent_image_id", "parent_build"},
            )
            or trusted_stage_identity["schema"]
            != "carbon.development.pinned-uv-stage.v1"
            or trusted_stage_identity["uv_image"] != UV_IMAGE
            or type(trusted_stage_identity["bundle_ref"]) is not dict
            or type(trusted_stage_identity["parent_image_id"]) is not str
            or {"uv-bin", "control.json"} & set(files)
        ):
            raise ValueError("trusted pinned UV stage required")
        if "parent_build" in trusted_stage_identity and (
            type(image) is not WorkerImageIdentity
            or trusted_stage_identity["parent_image_id"] != image.image_id
            or trusted_stage_identity["parent_build"]
            != {
                "schema": "carbon.c03.worker-image-build.v2",
                "source_tree_digest": image.source_tree_digest,
                "wheel_digest": image.wheel_digest,
                "lock_digest": image.lock_digest,
                "base_image_digest": image.base_image_digest,
                "build_recipe_digest": image.build_recipe_digest,
                "entrypoint_digest": image.entrypoint_digest,
            }
        ):
            raise ValueError("pinned UV stage parent differs")
        trusted_stage_bound = 64 * 1024**2 + 65536
        if (
            sum(map(len, files.values())) + len(source.encode()) + trusted_stage_bound
            > INPUT_BYTES
        ):
            raise ValueError("bounded preparation input exceeded")
    elif trusted_stage_identity is not None:
        raise ValueError("trusted stage identity without provider")
    overlay_receipt = None
    if trusted_overlay is not None:
        from .library_environment_cache import (
            VerifiedLibraryOverlay,
            _verified_overlay_tree,
        )

        if (
            provenance != LIBRARY_OVERLAY_BUILD_PROVENANCE
            or type(image) is not WorkerImageIdentity
            or type(trusted_overlay) is not VerifiedLibraryOverlay
            or trusted_overlay.parent_image_id != image.image_id
        ):
            raise ValueError("trusted construction-only overlay required")
        overlay_path = trusted_overlay.path
        if overlay_path.is_symlink() or not overlay_path.is_dir():
            raise ValueError("trusted overlay path differs")
        overlay_receipt = json.loads((overlay_path / ".overlay.json").read_bytes())
        if (
            type(overlay_receipt) is not dict
            or overlay_receipt.get("tree_digest") != trusted_overlay.tree_digest
            or overlay_receipt.get("bundle_ref") != trusted_overlay.bundle_ref.to_dict()
            or overlay_receipt.get("parent_image_id") != image.image_id
            or overlay_receipt.get("archive_sha256") != trusted_overlay.archive_digest
        ):
            raise ValueError("trusted overlay receipt differs")
        _verified_overlay_tree(overlay_path, overlay_receipt)
        if (
            sum(map(len, files.values()))
            + len(source.encode())
            + trusted_overlay.total_bytes
            + (overlay_path / ".overlay.json").stat().st_size
            > INPUT_BYTES
        ):
            raise ValueError("bounded construction input exceeded")
    elif provenance == LIBRARY_OVERLAY_BUILD_PROVENANCE:
        raise ValueError("verified construction overlay required")
    request = {
        "source": digest(source.encode()),
        "files": {n: digest(b) for n, b in files.items()},
        "image": image.image_id,
        "seconds": seconds,
        "provenance": provenance,
    }
    if executable_files:
        request["executable_files"] = list(executable_files)
    if trusted_stage_provider is not None:
        request["trusted_stage_identity"] = trusted_stage_identity
    if trusted_overlay is not None:
        request["verified_overlay"] = {
            "tree_digest": trusted_overlay.tree_digest,
            "bundle_ref": trusted_overlay.bundle_ref.to_dict(),
            "parent_image_id": trusted_overlay.parent_image_id,
            "archive_digest": trusted_overlay.archive_digest,
        }
    if worker_resources_version is not None:
        # Absent for today's resources, so every existing identity is unchanged.
        request["worker_resources_version"] = worker_resources_version
    if rebuild_wall_seconds is not None:
        # Absent at 600 s, so every existing identity is unchanged.
        request["rebuild_wall_seconds"] = rebuild_wall_seconds
    if execution_contract is not None:
        # Prospective language routes bind their complete reviewed environment.
        # Leaving this absent preserves historical Python operation identities.
        request["execution_contract"] = execution_contract
    device = None
    if accelerator is not None:
        # The miner's own GPU: Carbon's fixed practice program (C-MLP-03 slice
        # 3), or the miner's own code cell (RSURF-D20). The device is the
        # host's installed record, bound to this request, so a replaced or
        # withdrawn record is a different request. Absent for every CPU run,
        # so their identities are unchanged.
        if accelerator == MINER_GPU:
            # The validator's scored rebuild never runs in the miner lane.
            if (
                miner_lane and not miner_authored
            ) or provenance == VALIDATOR_PROVENANCE:
                raise ValueError("unsupported accelerator request")
        elif accelerator == VALIDATOR_GPU:
            # The validator's own GPU (VALIDATOR-27): only its scored rebuild,
            # and only on a device class a hardware acceptance has passed.
            if provenance != VALIDATOR_PROVENANCE:
                raise ValueError("unsupported accelerator request")
        else:
            raise ValueError("unsupported accelerator request")
        device = _gpu_device()
        profile_id = _gpu_pins(image, accelerator)[0]
        if accelerator == VALIDATOR_GPU:
            from carbon.reconstruction.hardware_acceptance import require_accepted

            # The deployment's network: an acceptance names its networks.
            require_accepted(device.device_kind, profile_id, network)
        request["accelerator"] = {
            "kind": accelerator,
            "profile": profile_id,
            "device": device.digest,
            # a remote GPU build slot of a lane split into N > 1 slots: its memory share (absent otherwise)
            **remote_gpu_build.request_fields(),
        }
    launch = digest(
        canonical({"owner": owner, "identity": identity, "request": request})
    )
    # Item 4: inside a counted grade's `grade_session()`, a member op runs as an exec in the grade's session container
    # (reset for it here, before its reservation); any other op (a timing op above all) closes the session first.
    # Outside a session nothing here changes.
    session = _GRADE_SESSION.get()
    if session is not None:
        if _timing_stage(identity):
            session.close()
            session = None
        elif device is None and session.member(
            ledger,
            owner=owner,
            identity=identity,
            image=image,
            provenance=provenance,
            seconds=seconds,
            worker=_worker_profile(
                None, provenance, worker_resources_version, rebuild_wall_seconds
            ),
            bootstrap=bootstrap,
            files=files,
            plain=(
                not miner_lane
                and trusted_overlay is None
                and trusted_stage_provider is None
                and not executable_files
                and program_name == "program.py"
            ),
        ):
            session.prepare(ledger, owner=owner, seconds=seconds, cli=DockerCLI())
        else:
            # Any other op takes its own container: the session is closed first.
            session.close()
            session = None
    operation = ledger.root / ("operation-" + launch[7:])
    if miner_lane:
        # The miner's disk; the only bound is their own retained_bytes budget.
        reservation_bytes = sum(map(len, files.values())) + 65536
    else:
        storage = sum(p.stat().st_size for p in ledger.root.rglob("*") if p.is_file())
        # Account stored input, provisional stream and decoded bounded output.
        reservation_bytes = (
            sum(map(len, files.values()))
            + trusted_stage_bound
            + (trusted_overlay.total_bytes if trusted_overlay is not None else 0)
            + 2 * output_bytes
            + 2 * CONTROL_BYTES
            + 65536
        )
        if storage + reservation_bytes > 10 * 1024**3:
            raise ValueError("campaign retained storage ceiling")
    resources = {
        "numerical_milliseconds": (seconds or 0) * 1000,
        "retained_bytes": reservation_bytes,
        **_one_trial_per_task(ledger, identity, extra_resources),
    }
    if not miner_lane and _detachable(session):
        # the receiver is stopping: no remote GPU build starts now (`Detached`); every other op is as before
        _raise_if_stopping()
    try:
        admission = ledger.reserve(
            identity, owner=owner, phase=phase, request=request, resources=resources
        )
    except ValueError as refused:
        # Lead, 18 Nov 2026 (live 116: 8 dead RESERVED ops blocked 3 miners' builds until a door stop): this round holds
        # the owner's numerical lease, so no live supervisor of this owner runs; a RESERVED numerical op left by a dead
        # run is settled here (`_settle_dead_numerical`, only when its worker is gone) and the reservation tried ONCE more
        if str(refused) != ONE_NUMERICAL_WORKER or not _settle_dead_numerical(
            ledger, owner=owner, keep=identity
        ):
            raise
        admission = ledger.reserve(
            identity, owner=owner, phase=phase, request=request, resources=resources
        )
    # an adopted op (`_run_adopted`): its RESERVED row is the running program's own, followed below, never relaunched
    adopting = (
        adopt is not None
        and not admission["dispatch"]
        and admission["state"] == "RESERVED"
    )
    if not admission["dispatch"]:
        if admission["state"] == "RESERVED" and not adopting:
            raise ValueError("research operation ambiguous; reconcile, never duplicate")
        if admission["state"] == "FAILED_MINER":
            # A replay reports the same typed outcome, never a success, and says that it IS a replay: the worker did not
            # run, so a door must not read it as a fresh observation of the candidate's own wall stop (13 Nov: a
            # re-queued task replayed its first attempt's contended stop and was counted against the miner).
            replay = MinerProgramFailure(admission["result"])
            replay.replayed = True
            raise replay
        if admission["state"] == "FAILED_INFRA":
            # A settled infrastructure failure (its own run's, or `reconcile_worker`'s after an interruption) is never a
            # worker result: returned as one, every later attempt under this identity read the reconciliation document
            # as its output (switch-2 copy, 17 Nov, rtsk_a6b1490a). Typed as Carbon's and as a replay (nothing ran this
            # time): the grader writes REPLAYED_NOT_RERUN, a re-run takes a fresh identity (lean_recipe_retention).
            replay = WorkerFailure(WorkerCode.UNAVAILABLE)
            replay.replayed = True
            raise replay
        if not adopting:
            return admission["result"]
    started = time.monotonic()
    started_unix = time.time()
    recorded_deadline = None
    if adopting:
        # the adopted op keeps its own start and deadline (its intent's ``deadline_unix``), so its walls are the ones
        # it was launched with; its intent is rewritten below with the identical bytes, or the adoption stops there
        recorded_deadline = json.loads((operation / "intent.json").read_bytes())[
            "deadline_unix"
        ]
        if type(recorded_deadline) not in (int, float) or seconds is None:
            raise ValueError("adopted operation deadline unreadable")
        started_unix = recorded_deadline + 30 - seconds
        started -= time.time() - started_unix
    name = "carbon-d4-" + launch[7:31] if session is None else session.name
    # The label of the container the op runs in: its own launch, or its grade session's.
    clabel = launch if session is None else session.launch
    # The durable intent is written first, before staging, image verification
    # or the host doctor: an interruption anywhere after the reservation then
    # leaves an operation reconcile_worker can settle, rather than a RESERVED
    # row with no record of what might have been launched.
    operation.mkdir(exist_ok=adopting)
    # What removes a miner-lane container if its owner cannot: the deadline
    # watchdog when the miner set a time budget, otherwise a reaper that
    # watches this controller process and removes the container only once it
    # is gone. An unbounded run has no time limit, but it is never unguarded.
    guard = _miner_guard(seconds) if miner_lane else None
    # a remote GPU build's program can outlive this process (`DETACHABLE_FRONT`); its intent says so, for recovery
    detachable = not miner_lane and _detachable(session)
    write_once(
        operation / "intent.json",
        canonical(
            {
                "launch": launch,
                "container": name,
                "request": request,
                "owner": owner,
                "identity": identity,
                "deadline_unix": (
                    recorded_deadline
                    if adopting
                    else (None if seconds is None else started_unix + seconds - 30)
                ),
                **({} if guard is None else {"reaper": guard}),
                # a REMOTE grade lane: the daemon (and mirror root) recovery must use
                **remote_lane.intent_fields(),
                # a remote GPU build slot: its daemon, mirror root, lane and slot
                **remote_gpu_build.intent_fields(),
                **({"detachable_program": 1} if detachable else {}),
                **(
                    {}
                    if session is None
                    else {
                        "session": {
                            "launch": session.launch,
                            "sequence": session.sequence,
                        }
                    }
                ),
            }
        ),
    )
    stage = operation / "input"
    # a remote GPU build slot: the lane's daemon (through its wrapper); otherwise this host's
    cli = remote_gpu_build.cli() or DockerCLI()
    sizing = (
        {}
        if worker_resources_version is None
        else {
            "worker_profile": _worker_profile(
                device, provenance, worker_resources_version
            )
        }
    )
    try:
        # an adopted op's stage and its box copy exist since its first launch
        if not adopting:
            with _fixed_practice_stage(operation, provenance, "STAGING"):
                stage.mkdir(mode=0o755)
                stage.chmod(0o755)
                staged_files = files
                if trusted_stage_provider is not None:
                    _check_cancel(ledger, owner, identity)
                    added = _checked_pinned_uv_stage(
                        trusted_stage_provider(cli), trusted_stage_identity
                    )
                    _check_cancel(ledger, owner, identity)
                    staged_files = {**files, **added}
                for filename, body in {
                    **staged_files,
                    program_name: source.encode(),
                }.items():
                    path = stage / filename
                    mode = 0o555 if filename in executable_files else 0o444
                    if filename in _NOT_STORED_ONCE:
                        write_once(path, body)
                        path.chmod(mode)
                    else:
                        _stage_once(path, body, mode)
                if trusted_overlay is not None:
                    _stage_verified_overlay(
                        trusted_overlay.path, stage / "overlay", overlay_receipt
                    )
                if session is not None:
                    session.link(stage)
                # an upload to another machine (a REMOTE grade lane's box, or a remote GPU build slot's): the container's
                # /input at the same path there. No timing gate (owner, 17 Nov 2026: lane core pinning is the protection)
                if session is not None:
                    remote_lane.mirror(session.input)
                elif remote_gpu_build.docker_host() is not None:
                    # a remote GPU build slot: the build's public stage at the same path on the lane machine
                    remote_gpu_build.mirror(stage)
                elif remote_lane.current() is not None:
                    remote_lane.mirror(stage)
        # Every doctor here is sized as the worker it launches (``sizing``: the same resources version), so the cpuset it
        # resolves has exactly the worker's CPU count (`host_execution._fitted`) and the kernel's quota equals its size.
        with _fixed_practice_stage(operation, provenance, "HOST_READINESS"):
            if provenance == LIBRARY_BUILD_PROVENANCE:
                from .research_image import verify_library_worker_image

                verify_library_worker_image(image, cli)
                checked = doctor(image_id=image.image_id, cli=cli, **sizing)
            elif provenance == "MINER_SELF_REPORTED":
                from .julia_analysis import (
                    JuliaResearchImageIdentity,
                    verify_julia_image,
                )
                from .research_image import verify_image

                if device is not None and type(image) is JuliaResearchImageIdentity:
                    # A Julia GPU code cell (JULIA-GPU-01): the composed image and
                    # its depot, checked as every Julia run is, and the host's GPU
                    # readiness without the Python GPU worker's lock.
                    verify_julia_image(image, cli)
                    checked = doctor(image_id=image.image_id, cli=cli, **sizing)
                    _check_gpu_host(cli, None, device)
                elif device is not None:
                    # A GPU code cell: the pinned GPU worker and the host's GPU
                    # readiness, checked as GPU practice checks them.
                    checked = doctor(
                        image_id=image.image_id, image_identity=image, cli=cli, **sizing
                    )
                    _check_gpu_host(cli, image, device, _gpu_pins(image, accelerator))
                elif type(image) is JuliaResearchImageIdentity:
                    verify_julia_image(image, cli)
                    checked = doctor(image_id=image.image_id, cli=cli, **sizing)
                else:
                    verify_image(image, cli)
                    checked = doctor(image_id=image.image_id, cli=cli, **sizing)
            else:
                checked = doctor(
                    image_id=image.image_id, image_identity=image, cli=cli, **sizing
                )
                if device is not None:
                    _check_gpu_host(cli, image, device, _gpu_pins(image, accelerator))
            if not checked.eligible:
                # No attempt is automatically retried and its reservation remains
                # visible. A host that is simply too small says so, with its numbers.
                shortfall = _host_capacity_shortfall(checked, sizing)
                if shortfall is not None:
                    raise shortfall
                raise ValueError("research host ineligible")
    except Exception:
        if adopting:
            # an adopted op's container runs: its task's settle removes it (`reconcile_worker`), never "nothing made"
            raise
        if session is not None:
            with suppress(Exception):
                session.after_op(cli, ok=False)
        else:
            # a REMOTE grade lane's copy of the inputs never outlives an op that made nothing
            with suppress(remote_lane.RemoteLaneDown):
                remote_lane.discard(stage)
            with suppress(remote_lane.RemoteLaneDown):
                remote_gpu_build.discard(stage)
        _settle_nothing_created(
            ledger,
            owner=owner,
            identity=identity,
            operation=operation,
            resources=resources,
            before_finish=before_finish,
        )
        raise
    if miner_lane:
        return _run_miner_lane(
            ledger,
            guard=guard,
            owner=owner,
            identity=identity,
            operation=operation,
            stage=stage,
            name=name,
            cli=cli,
            image=image,
            launch=launch,
            request=request,
            seconds=seconds,
            started=started,
            started_unix=started_unix,
            bootstrap=bootstrap,
            output_validator=output_validator,
            provenance=provenance,
            resources=resources,
            miner_authored=miner_authored,
            before_finish=before_finish,
            device=device,
        )
    with _fixed_practice_stage(operation, provenance, "PROFILE"):
        worker = _worker_profile(
            device, provenance, worker_resources_version, rebuild_wall_seconds
        )
    create_attempted = False
    session_op_ok = False
    candidate_stop = None
    # left as it is for the next start (`Detached`): nothing cleaned up or settled
    detached = False
    output = operation / "export.stream"
    lease = ExitStack()
    slot = ExitStack()
    try:
        if session is None and adopting:
            # an adopted op: its container runs since its first launch (no device lease, create or start here); a
            # fresh watchdog holds it to its recorded deadline (one that survived the restart is harmless: the same one)
            create_attempted = True
            with _fixed_practice_stage(operation, provenance, "CHECK_CANCEL"):
                _check_cancel(ledger, owner, identity)
            with _fixed_practice_stage(operation, provenance, "WATCHDOG"):
                remote_gpu_build.spawn_watchdog(
                    container_name=name,
                    launch_digest=launch,
                    deadline_unix=float(recorded_deadline),
                    **(
                        {"intent_path": operation / "intent.json"}
                        if provenance == LIBRARY_PREP_PROVENANCE
                        else {}
                    ),
                )
        elif session is None:
            with _fixed_practice_stage(operation, provenance, "DEVICE_LEASE"):
                if device is not None and remote_gpu_build.current_op() is not None:
                    from carbon.reconstruction.worker.accelerator_runtime import (
                        reject_existing_device_containers,
                        shared_host_lease,
                    )

                    if remote_gpu_build.docker_host() is None:
                        # a LOCAL slot lane shares this host's GPU with its other Carbon work: check and create under
                        # the host's one Carbon device lock, as every other launch on this device does
                        slot.enter_context(shared_host_lease())

                    # A remote GPU build slot: the slot lock (`remote_gpu_build.op`) is this launch's share of the
                    # lane's device, held since the op began; at most the lane's slot count of Carbon containers
                    # run on it, each with its own slot record.
                    reject_existing_device_containers(
                        cli=cli, device_uuid=device.device_uuid
                    )
                elif device is not None:
                    from carbon.reconstruction.worker.accelerator_runtime import (
                        miner_device_lease,
                        reject_existing_device_containers,
                        shared_host_lease,
                    )

                    # This host's own concurrent runs on the device, and Carbon's own
                    # retained work on it; nothing about anyone else's use of the GPU.
                    lease.enter_context(miner_device_lease(device.device_uuid))
                    # Serialize only check/record/create against Carbon's own
                    # launches. This is not an exclusive GPU lease or assurance.
                    slot.enter_context(shared_host_lease())
                    reject_existing_device_containers(
                        cli=cli, device_uuid=device.device_uuid
                    )
            with _fixed_practice_stage(operation, provenance, "CHECK_CANCEL"):
                _check_cancel(ledger, owner, identity)
            with _fixed_practice_stage(operation, provenance, "CREATE"):
                try:
                    if device is not None:
                        from carbon.reconstruction.worker.accelerator_runtime import (
                            mark_device_allocation,
                        )

                        # The same task-owned provenance the existing miner-script
                        # and reconstruction paths persist before create. Cleanup
                        # may complete only the authority that owns this launch.
                        mark_device_allocation(
                            container_name=name,
                            launch_digest=launch,
                            authority=worker.accelerator_authority,
                        )
                    create_attempted = True
                    cli.run(
                        # a remote GPU build slot of a lane split into N > 1 slots: each process's memory share
                        remote_gpu_build.with_slot_environment(
                            create_arguments(
                                container_name=name,
                                image_id=image.image_id,
                                input_directory=stage,
                                cpuset=checked.cpuset,
                                launch_digest=launch,
                                worker_profile=worker,
                            )
                        ),
                        timeout=30,
                    )
                finally:
                    slot.close()
            with _fixed_practice_stage(operation, provenance, "CHECK_CANCEL"):
                _check_cancel(ledger, owner, identity)
            with _fixed_practice_stage(operation, provenance, "WATCHDOG"):
                # a remote GPU build slot: the watchdog watches the lane's daemon, where the container runs
                (
                    # a slot op's (remote or local): it is handed the slot, so it finishes that slot's record
                    remote_gpu_build.spawn_watchdog
                    if remote_gpu_build.current_op() is not None
                    else spawn_watchdog
                )(
                    container_name=name,
                    launch_digest=launch,
                    deadline_unix=float(started_unix + seconds - 30),
                    **(
                        {"intent_path": operation / "intent.json"}
                        if provenance == LIBRARY_PREP_PROVENANCE
                        else {}
                    ),
                )
            with _fixed_practice_stage(operation, provenance, "START"):
                cli.run(["start", name], timeout=20)
        elif not session.live:
            with _fixed_practice_stage(operation, provenance, "CHECK_CANCEL"):
                _check_cancel(ledger, owner, identity)
            # The grade session's ONE create + start (its first member op, or the first after a removal); its
            # watchdog and liveness reaper are the session's own.
            with _fixed_practice_stage(operation, provenance, "CREATE"):
                session.open(cli=cli, image=image, cpuset=checked.cpuset, worker=worker)
        with _fixed_practice_stage(operation, provenance, "CONTROLS"):
            control_digest, controls = inspect_effective_controls(
                cli=cli,
                container_name=name,
                image_id=image.image_id,
                input_directory=stage if session is None else session.input,
                cpuset=checked.cpuset if session is None else session.cpuset,
                launch_digest=clabel,
                worker_profile=worker,
                diagnose_policy=provenance in _FIXED_DIAGNOSTIC_PROVENANCES,
            )
        baseline_digest = None
        baseline_cpu = None
        if provenance == GRAPH_INFERENCE_PROVENANCE:
            baseline_cpu = _fixed_program_cpu_usage_usec(
                cli,
                container_name=name,
                launch_digest=clabel,
                deadline=min(time.monotonic() + 1, started + seconds - 45),
            )
        if provenance in _PROGRAM_EVIDENCE_PROVENANCES:
            try:
                baseline_digest = _retain_fixed_program_evidence(
                    operation,
                    "private-program-baseline.json",
                    {
                        "schema": "carbon.autoresearch.program-resource-baseline.v1",
                        "launch_digest": launch,
                        "observed_unix": time.time(),
                        "observation": _fixed_program_container_observation(
                            cli,
                            container_name=name,
                            launch_digest=clabel,
                            image_id=image.image_id,
                            deadline=min(time.monotonic() + 1, started + seconds - 45),
                        ),
                        **(
                            {"cpu_usage_usec": baseline_cpu}
                            if provenance == GRAPH_INFERENCE_PROVENANCE
                            else {}
                        ),
                    },
                )
            except Exception:  # noqa: BLE001, S110 - diagnostics never gate work
                pass
        with _fixed_practice_stage(operation, provenance, "PROGRAM"):
            program_started = time.monotonic()
            program_timeout = max(1, seconds - 45 - (program_started - started))
            program_deadline = program_started + program_timeout
            if detachable:
                # its docker client is this process's own: a stop ends that client (`door_stopping`), never the program
                _LIVE_PROGRAMS.add(name)
                if adopting:
                    # a stream the stop cut kept nothing whole: read again from the program's own record
                    (operation / "stdout.txt").unlink(missing_ok=True)
                else:
                    write_once(operation / "program-started", b"")
            try:
                cli.stream_to_file(
                    # a remote GPU build's program under its detachable front end (`DETACHABLE_FRONT`); an adopted
                    # one's recorded result (`DETACHABLE_WAIT`)
                    _program_command(
                        name,
                        bootstrap,
                        detachable=detachable,
                        maximum=1024**2,
                        adopting=adopting,
                    ),
                    operation / "stdout.txt",
                    maximum=1024**2,
                    timeout=program_timeout,
                )
            except Exception as error:
                if detachable and _detached_by_stop(error):
                    # the receiver is stopping: the program runs on, for the next start
                    detached = True
                    raise Detached() from error
                lost = getattr(error, "private_diagnostic", None)
                if adopting and type(lost) is bytes and PROGRAM_LOST in lost:
                    # the adopted program's result cannot be known: Carbon's
                    raise remote_lane.RemoteLaneDown(
                        b"remote_gpu_build_adopted_program_lost"
                    ) from error
                failure_observation = None
                if provenance in _PROGRAM_EVIDENCE_PROVENANCES:
                    try:
                        diagnostic = (
                            error.private_diagnostic
                            if isinstance(error, WorkerFailure)
                            else b""
                        )
                        exited = (
                            re.match(rb"exit=([0-9]{1,3})\n", diagnostic)
                            if type(diagnostic) is bytes
                            else None
                        )
                        observed_exit = None if exited is None else int(exited.group(1))
                        if observed_exit is not None and observed_exit > 255:
                            observed_exit = None
                        failure_observation = _fixed_program_container_observation(
                            cli,
                            container_name=name,
                            launch_digest=clabel,
                            image_id=image.image_id,
                            deadline=min(time.monotonic() + 1, started + seconds - 30),
                        )
                        failure_cpu = {}
                        if provenance == GRAPH_INFERENCE_PROVENANCE:
                            # CPU time of the container at the failure, and the part used during the program (None when
                            # either reading failed): with elapsed_milliseconds, computing vs blocked, host-side only
                            after = _fixed_program_cpu_usage_usec(
                                cli,
                                container_name=name,
                                launch_digest=clabel,
                                deadline=min(
                                    time.monotonic() + 1, started + seconds - 30
                                ),
                            )
                            failure_cpu = {
                                "cpu_usage_usec": after,
                                "cpu_usec_during_program": (
                                    after - baseline_cpu
                                    if after is not None
                                    and baseline_cpu is not None
                                    and after >= baseline_cpu
                                    else None
                                ),
                            }
                        _retain_fixed_program_evidence(
                            operation,
                            "private-program-failure-evidence.json",
                            {
                                "schema": "carbon.autoresearch.program-failure-evidence.v1",
                                "launch_digest": launch,
                                "baseline_digest": baseline_digest,
                                "observed_unix": time.time(),
                                "elapsed_milliseconds": int(
                                    max(0, time.monotonic() - program_started) * 1000
                                ),
                                "program_timeout_seconds": program_timeout,
                                "program_deadline_reached": time.monotonic()
                                >= program_deadline,
                                "watchdog_deadline_unix": started_unix + seconds - 30,
                                "watchdog_deadline_reached": time.time()
                                >= started_unix + seconds - 30,
                                "cancel_flag_observed": _cancel_path(
                                    ledger, owner, identity
                                ).exists(),
                                "observed_exec_exit": observed_exit,
                                "observation": failure_observation,
                                **failure_cpu,
                                "interpretation": "Observations only; no inferred kill cause.",
                            },
                        )
                        _retain_container_end(
                            cli,
                            operation,
                            container_name=name,
                            launch_digest=clabel,
                            deadline=min(time.monotonic() + 2, started + seconds - 30),
                        )
                    except Exception:  # noqa: BLE001, S110 - preserve original failure
                        pass
                if (
                    provenance in _CANDIDATE_RESOURCE_PROVENANCES
                    and not _cancel_path(ledger, owner, identity).exists()
                    # a per-case processes pass that fell back is Carbon's, ONCE: its every later run is the
                    # one-process program (`case_procs.pass_program`), classified below exactly as any other
                    and not _case_procs_fell_back(source, error)
                ):
                    stop = _candidate_resource_stop(
                        cli,
                        error,
                        container_name=name,
                        launch_digest=clabel,
                        image_id=image.image_id,
                        program_started=program_started,
                        program_timeout=program_timeout,
                        box_deadline=started + seconds - 30,
                        setup_seconds=program_started - started,
                        observation=failure_observation,
                        deadline=min(time.monotonic() + 1, started + seconds - 30),
                        memory_limit_bytes=getattr(
                            worker, "effective_memory_bytes", None
                        ),
                        accelerated=device is not None,
                    )
                    if stop is not None:
                        raise _CandidateResourceStop(*stop, error) from error
                raise
        with _fixed_practice_stage(operation, provenance, "OBSERVE"):
            observed = observe_effective_resources(cli=cli, container_name=name)
        with _fixed_practice_stage(operation, provenance, "EXPORT"):
            export_started = time.monotonic()
            if adopting:
                # an export the stop cut kept nothing whole
                output.unlink(missing_ok=True)
            export_timeout = max(1, seconds - 35 - (export_started - started))
            try:
                cli.stream_to_file(
                    [
                        "exec",
                        name,
                        "/opt/carbon-worker/bin/python",
                        "-I",
                        "-m",
                        "carbon.reconstruction.worker.exporter",
                        # Today's envelope is the exporter's own default, so
                        # today's command line is unchanged.
                        *(() if output_bytes == OUTPUT_BYTES else (str(output_bytes),)),
                    ],
                    output,
                    maximum=output_bytes + 2 * CONTROL_BYTES,
                    timeout=export_timeout,
                )
            except Exception as error:
                if provenance in _FIXED_DIAGNOSTIC_PROVENANCES:
                    try:
                        diagnostic = (
                            error.private_diagnostic
                            if isinstance(error, WorkerFailure)
                            else b""
                        )
                        exited = (
                            re.match(rb"exit=([0-9]{1,3})\n", diagnostic)
                            if type(diagnostic) is bytes
                            else None
                        )
                        observed_exit = None if exited is None else int(exited.group(1))
                        if observed_exit is not None and observed_exit > 255:
                            observed_exit = None
                        _retain_fixed_program_evidence(
                            operation,
                            "private-export-failure-evidence.json",
                            {
                                "schema": "carbon.autoresearch.export-failure-evidence.v1",
                                "launch_digest": launch,
                                "observed_unix": time.time(),
                                "export_timeout_seconds": export_timeout,
                                "export_deadline_reached": time.monotonic()
                                >= export_started + export_timeout,
                                "observed_exec_exit": observed_exit,
                                "observation": _fixed_program_container_observation(
                                    cli,
                                    container_name=name,
                                    launch_digest=clabel,
                                    image_id=image.image_id,
                                    deadline=min(
                                        time.monotonic() + 1, started + seconds - 30
                                    ),
                                ),
                                "interpretation": "Observations only; no inferred export failure cause.",
                            },
                        )
                        _retain_container_end(
                            cli,
                            operation,
                            container_name=name,
                            launch_digest=clabel,
                            deadline=min(time.monotonic() + 2, started + seconds - 30),
                        )
                    except Exception:  # noqa: BLE001, S110 - preserve original failure
                        pass
                raise
        with _fixed_practice_stage(operation, provenance, "RESOURCES"):
            write_once(
                operation / "resources.json",
                canonical(
                    {
                        "controls": controls,
                        "controls_digest": control_digest,
                        "resources": observed,
                        # A session's cgroup counters span its ops (each op starts from a reset, no OOM, peak
                        # below the limit): named so no reader takes them for this op alone.
                        **(
                            {}
                            if session is None
                            else {
                                "session": {
                                    "container": name,
                                    "sequence": session.sequence,
                                    "counters": "SESSION_CUMULATIVE",
                                }
                            }
                        ),
                    }
                ),
            )
        session_op_ok = True
    except _CandidateResourceStop as stop:
        # A remote GPU build whose link or GPU is unhealthy now: the stop is Carbon's, never the candidate's.
        down = remote_gpu_build.retyped(stop.original)
        if down is not None:
            raise down from stop.original
        # Settled below, once cleanup of this exact container is observed.
        candidate_stop = stop
    except Exception as error:
        if detachable and create_attempted and _detached_by_stop(error):
            # the receiver is stopping (its stream cut after the program): the container is left for the next start
            detached = True
            raise Detached() from error
        raise
    finally:
        _LIVE_PROGRAMS.discard(name)
        try:
            with (
                _fixed_practice_stage(operation, provenance, "CLEANUP"),
                _remote_inputs_discarded(
                    stage if session is None and not detached else None
                ),
            ):
                if create_attempted and not detached:
                    # C-03 checks the exact launch label, removes the entire
                    # container, and confirms absence before any output becomes an
                    # associated result.
                    remove_exact_container(
                        cli=cli, container_name=name, launch_digest=launch
                    )
                    # Require a successful daemon query too: an inspect transport
                    # error alone is not evidence that the container and descendants
                    # are gone.
                    remaining = cli.run(
                        ["ps", "-aq", "--filter", "name=^" + name + "$"], timeout=10
                    )
                    if remaining.stdout.strip():
                        raise ValueError(
                            "research cleanup uncertain; capacity stays reserved"
                        )
                if session is not None:
                    # The op's inputs leave the session; an op that did not finish cleanly (failure, wall or
                    # memory stop, cancel) removes the session container, confirmed, before any outcome.
                    session.after_op(cli, ok=session_op_ok)
        finally:
            with _fixed_practice_stage(operation, provenance, "LEASE_RELEASE"):
                try:
                    slot.close()
                finally:
                    lease.close()
    # The container is confirmed removed (or never created): the trusted stage items are reclaimed before any result
    # is associated, so a stopped candidate's operation frees them too.
    # Best effort: a reclaim that fails never changes the operation's outcome (the disk floor alert still sees it).
    if trusted_stage_provider is not None or trusted_overlay is not None:
        with suppress(OSError, ValueError):
            reclaim_trusted_stage(stage)
    if candidate_stop is not None:
        # The candidate's own graph or recipe hit the worker's memory or wall
        # limit. The full reservation is kept and nothing is retried or
        # refunded: a typed candidate failure, never FAILED_INFRA.
        _settle_miner_failure(
            ledger,
            owner=owner,
            identity=identity,
            operation=operation,
            resources=resources,
            started=started,
            failure=(candidate_stop.code, candidate_stop.observation),
            limit=candidate_stop.limit,
            before_finish=before_finish,
        )
    with _fixed_practice_stage(operation, provenance, "CHECK_CANCEL"):
        _check_cancel(ledger, owner, identity)
    snapshot = operation / "snapshot"
    with _fixed_practice_stage(operation, provenance, "DECODE"):
        # Today's envelope is the decoder's default, so today's call is unchanged.
        decode_output_stream(
            output,
            snapshot,
            **({} if output_bytes == OUTPUT_BYTES else {"output_bytes": output_bytes}),
        )
    with _fixed_practice_stage(operation, provenance, "VALIDATE"):
        if output_validator is not None:
            output_validator(snapshot)
    result = {
        "schema": "carbon.autoresearch.worker-result.v1",
        "provenance": provenance,
        "output_digest": digest(output.read_bytes()),
        "files": {
            p.relative_to(snapshot).as_posix(): digest(p.read_bytes())
            for p in sorted(snapshot.rglob("*"))
            if p.is_file()
        },
        "operation": operation.name,
        "scientific_qualification": False,
        "official_eligible": False,
    }
    # owner rule #13: the stream's bodies are the snapshot's own files, so only its framing stays (`export.frames`);
    # the stream is rebuilt byte for byte from both (the same output_digest), else it is kept as it is
    compact_output_stream(output, snapshot, expected=result["output_digest"])
    elapsed = math.ceil((time.monotonic() - started) * 1000)
    actual = {
        **resources,
        "numerical_milliseconds": elapsed,
        "retained_bytes": sum(
            p.stat().st_size for p in operation.rglob("*") if p.is_file()
        ),
    }
    with _fixed_practice_stage(operation, provenance, "ASSOCIATE"):
        before_finish()
        ledger.finish(
            identity, owner=owner, state="SUCCEEDED", actual=actual, result=result
        )
    return result


#: The one accelerator a carrier run may ask for: the miner's own GPU, for
#: Carbon's fixed practice program or, in the miner lane's isolated
#: container, the miner's own code cell (RSURF-D20).
MINER_GPU = "MINER_OWN_GPU"
#: The validator's own GPU for its scored rebuild (VALIDATOR-27), under the
#: validator reconstruction role, on an accepted device class only.
VALIDATOR_GPU = "VALIDATOR_OWN_GPU"
#: The battery validator's scored rebuild (`battery.worker.CarrierBackend`).
VALIDATOR_PROVENANCE = "BATTERY_VALIDATOR"


def _gpu_profile_id():
    from carbon.reconstruction.accelerators import GPU_PROFILE

    return GPU_PROFILE.profile_id


def _gpu_device():
    """The installed host device record (a remote GPU build slot's machine's own, inside one); fails closed when
    absent."""
    from carbon.reconstruction.worker.accelerator_runtime import (
        miner_host_device,
    )

    remote = remote_gpu_build.device()
    if remote is not None:
        return remote

    try:
        return miner_host_device()
    except WorkerFailure:
        raise ValueError(
            "no GPU device record is installed on this host; run setup's GPU "
            "check (or scripts/dev/carbon_accelerator.py prepare)"
        ) from None


def _gpu_pins(image, accelerator):
    """`(profile_id, profile_digest, lock_digest)` a GPU run's pinned worker
    carries: JAX's accelerator worker, or the PyTorch GPU worker for miner
    practice and validator rebuild (TORCH-GPU-01; PLT-30), named
    by its own exact-hashed lock. The image's labels are then checked against
    these pins, so a claimed lock alone admits nothing."""
    from carbon.reconstruction import torch_profile
    from carbon.reconstruction.accelerators import GPU_PROFILE

    if (
        accelerator in {MINER_GPU, VALIDATOR_GPU}
        and getattr(image, "lock_digest", None) == torch_profile.GPU_LOCK_DIGEST
    ):
        return (
            torch_profile.GPU_PROFILE_ID,
            torch_profile.GPU_PROFILE_DIGEST,
            torch_profile.GPU_LOCK_DIGEST,
        )
    return (
        GPU_PROFILE.profile_id,
        GPU_PROFILE.digest,
        GPU_PROFILE.environment_lock_digest,
    )


def _check_gpu_host(cli, image, device, pins=None):
    """The miner-lane readiness the GPU controller requires, and no more.

    `image` is the pinned Python GPU worker, checked by its lock and labels
    with the NVIDIA runtime. None for a Julia GPU code cell: its image is the
    composed Julia image (verified on its own), which carries no Python GPU
    worker lock, so only the NVIDIA container runtime is checked here.
    """
    from carbon.reconstruction.onboarding import doctor_report, miner_lane_blockers
    from carbon.reconstruction.worker.accelerator_runtime import (
        HOST_ROOT,
        verify_image_and_toolkit,
    )

    if remote_gpu_build.docker_host() is not None:
        # The lane machine's readiness, on its own daemon: this host's GPU doctor describes this host only.
        remote_gpu_build.check_host(cli, image, device, pins)
        return
    if image is None:
        info = cli.json(["info", "--format", "{{json .}}"])
        if type(info) is not dict or "nvidia" not in (info.get("Runtimes") or {}):
            raise ValueError("the NVIDIA container runtime is not available")
    elif pins is None:
        verify_image_and_toolkit(cli=cli, image=image)
    else:
        _, profile_digest, lock_digest = pins
        verify_image_and_toolkit(
            cli=cli, image=image, profile_digest=profile_digest, lock_digest=lock_digest
        )
    if miner_lane_blockers(doctor_report(root=HOST_ROOT, cli=cli, image=image)):
        raise ValueError("GPU host not ready")
    if _gpu_device().digest != device.digest:
        raise ValueError("installed host device record changed before dispatch")


#: The one provenance that runs under the G5 compile lane's profile
#: (`carbon.level4.compile.PROVENANCE`; LEVEL4-G5-LANE-MEMORY-01).
G5_PROVENANCE = "LEVEL4_G5_COMPILE_DEVELOPMENT"


def _worker_profile(
    device, provenance=None, worker_resources_version=None, rebuild_wall_seconds=None
):
    """The carrier's worker profile: CPU, the G5 compile lane's CPU profile
    (only for G5's own provenance, never with a device), or the miner lane on
    `device`; under a next version's larger resources when
    ``worker_resources_version`` names one, and a graph route v2 version's
    rebuild wall when ``rebuild_wall_seconds`` names it (None: 600 s, and the
    profile's body and digest unchanged)."""
    policy = digest(b"carbon.autoresearch.public-research.v1")
    if worker_resources_version is not None and (
        provenance == G5_PROVENANCE
        or resources_version_for(worker_resources_version) != worker_resources_version
    ):
        raise ValueError("unsupported worker resources")
    if rebuild_wall_seconds is not None and (
        rebuild_wall_seconds != REBUILD_LIMIT_SECONDS or provenance == G5_PROVENANCE
    ):
        raise ValueError("unsupported rebuild wall")
    if device is None and provenance == G5_PROVENANCE:
        from carbon.reconstruction.worker.model import G5_PROFILE_ID, PROFILE_VERSION

        return DevelopmentWorkerProfile(
            policy,
            digest(b"2cpu-8gib-noswap-600seconds"),
            G5_PROFILE_ID,
            PROFILE_VERSION,
        )
    label = (
        b"2cpu-4gib-noswap-600seconds"
        if worker_resources_version is None
        else b"4cpu-16gib-noswap-600seconds"
    )
    if rebuild_wall_seconds is not None:
        # The resource class names its wall, so a rebuild-wall profile is a
        # different class rather than the 600-second one restated.
        label = label.replace(b"600seconds", b"%dseconds" % rebuild_wall_seconds)
    resources = digest(label)
    if device is None:
        return DevelopmentWorkerProfile(
            policy,
            resources,
            worker_resources_version=worker_resources_version,
            rebuild_wall_seconds=rebuild_wall_seconds,
        )
    from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
    from carbon.reconstruction.worker.model import (
        MINER_HOST_AUTHORITY,
        registered_run_controls,
    )

    # The validator's scored rebuild runs under the validator reconstruction
    # role (C-CORE-19 admits both roles on a self-service host); every other
    # GPU run stays the miner lane.
    role = (
        AcceleratorRole.VALIDATOR_RECONSTRUCTION
        if provenance == VALIDATOR_PROVENANCE
        else AcceleratorRole.MINER_RESEARCH
    )
    return DevelopmentWorkerProfile(
        policy,
        resources,
        "carbon.c03.cuda.development.v1",
        "1.0",
        GPU_PROFILE.profile_id,
        device.digest,
        role.value,
        MINER_HOST_AUTHORITY,
        None,
        device.device_uuid,
        (
            registered_run_controls(worker_resources_version)
            if rebuild_wall_seconds is None
            else {
                **registered_run_controls(worker_resources_version),
                "productive_seconds": rebuild_wall_seconds,
            }
        ),
        worker_resources_version=worker_resources_version,
        rebuild_wall_seconds=rebuild_wall_seconds,
    )


def _miner_guard(seconds):
    """The deadline watchdog for a timed run; otherwise the controller-liveness
    reaper, so an unbounded run is never unguarded."""
    if seconds is not None:
        return {"kind": "DEADLINE"}
    return liveness_reaper.controller_guard()


def _settle_nothing_created(
    ledger, *, owner, identity, operation, resources, before_finish
):
    """Settle an operation refused before any container command.

    Nothing was created: no container command has been issued. That is a
    fact of this process, not an inference from absence, so settle now as
    infrastructure failure keeping the full reservation - no refund.
    """
    before_finish()
    ledger.finish(
        identity,
        owner=owner,
        state="FAILED_INFRA",
        actual=resources,
        result={
            "schema": "carbon.autoresearch.worker-reconciliation.v1",
            "operation": operation.name,
            "state": "FAILED_INFRA",
            "worker_created": False,
            "cleanup_observed": True,
            "accounting": "full original reservation retained as conservative consumption",
            "scientific_outcome": "UNRESOLVED",
            "retry_dispatched": False,
        },
    )


def _run_miner_lane(
    ledger,
    *,
    guard,
    owner,
    identity,
    operation,
    stage,
    name,
    cli,
    image,
    launch,
    request,
    seconds,
    started,
    started_unix,
    bootstrap,
    output_validator,
    provenance,
    resources,
    miner_authored,
    before_finish,
    device=None,
):
    """Run the miner's own research: isolated, no Carbon limits.

    `device` is the host's installed GPU record for a GPU code cell
    (RSURF-D20): the same container with that one device attached, under the
    same device lease as GPU practice. None for every CPU run.

    Same lifecycle as Carbon's lane - durable intent, exact-label removal,
    cancellation, a digest of every output - in the miner lane's container,
    which has no size or time limit, writing to scratch on the miner's own disk.

    Where the miner's own program is observed to be the cause of a failure
    (``miner_authored`` only), the operation settles FAILED_MINER with cleanup
    observed and the full reservation kept, and ``MinerProgramFailure`` is
    raised. Every other failure keeps its infrastructure meaning.
    """
    from .miner_container import (
        SCRATCH_CAP_EXCEEDED,
        SCRATCH_CAP_INODES,
        MinerOutputRefused,
        MinerResearchLaunch,
        collect_outputs,
        copy_out_scratch,
        create_arguments,
        inspect_isolation,
        load_host_profile,
        prepare_scratch,
        scratch_full,
    )

    try:
        # Carbon's own host may name an operator profile; a miner's machine
        # names none, and a named one that is unreadable refuses here.
        profile = load_host_profile()
        scratch = prepare_scratch(operation / "scratch")
        run = MinerResearchLaunch(
            name,
            image.image_id,
            launch,
            stage,
            scratch,
            **({} if device is None else {"gpu_device": device.device_uuid}),
            **({} if profile is None else {"resource_profile": profile}),
        )
    except Exception:
        # Refused before any container command: settle now, as the prechecks
        # do, rather than leave the reservation for reconciliation.
        _settle_nothing_created(
            ledger,
            owner=owner,
            identity=identity,
            operation=operation,
            resources=resources,
            before_finish=before_finish,
        )
        raise
    # No deadline unless the miner asked for one; a very long transport bound
    # stands in for "none" where the CLI needs a number.
    unbounded = 10 * 365 * 24 * 3600
    create_attempted = False
    failure = None
    output_refused = None
    lease = ExitStack()
    slot = ExitStack()
    try:
        if device is not None:
            from carbon.reconstruction.worker.accelerator_runtime import (
                miner_device_lease,
                reject_existing_device_containers,
                shared_host_lease,
            )

            # The same lease GPU practice takes: one run on the device at a
            # time, on this host.
            lease.enter_context(miner_device_lease(device.device_uuid))
            # And the shared Carbon slot across check-then-create. Validator
            # GPU work holds that slot for its whole run and checks for
            # labelled device containers under it, so neither side can pass
            # its check while the other is between check and create. Once
            # created, this run's device label is what the other side sees.
            slot.enter_context(shared_host_lease())
            reject_existing_device_containers(cli=cli, device_uuid=device.device_uuid)
        _check_cancel(ledger, owner, identity)
        create_attempted = True
        try:
            if device is not None:
                from carbon.reconstruction.worker.accelerator_runtime import (
                    mark_device_allocation,
                )
                from carbon.reconstruction.worker.model import MINER_HOST_AUTHORITY

                # Ownership is persisted before create, as GPU practice does,
                # under the miner lane's own task-owned authority. Removal of
                # a device-labelled container completes the allocation that
                # created it; without this record it takes the strict path,
                # which this run never had the evidence for, and refuses.
                mark_device_allocation(
                    container_name=name,
                    launch_digest=launch,
                    authority=MINER_HOST_AUTHORITY,
                )
            cli.run(create_arguments(run), timeout=30)
        finally:
            slot.close()
        _check_cancel(ledger, owner, identity)
        if seconds is not None:
            spawn_watchdog(
                container_name=name,
                launch_digest=launch,
                deadline_unix=float(started_unix + seconds),
            )
        else:
            liveness_reaper.spawn_liveness_reaper(
                container_name=name, launch_digest=launch, guard=guard
            )
        cli.run(["start", name], timeout=20)
        isolation = inspect_isolation(cli, run)
        try:
            # The last 64 KiB of stdout and of stderr are kept, whatever the
            # outcome (RSURF-D21). A Docker double supplies its own.
            keep = getattr(cli, "stream_kept", None) or partial(stream_kept, cli)
            keep(
                [
                    "exec",
                    name,
                    "/opt/carbon-worker/bin/python",
                    "-I",
                    "-c",
                    bootstrap,
                ],
                operation,
                timeout=unbounded if seconds is None else max(1, seconds),
            )
        except WorkerFailure as error:
            # Classified while the container still exists to be inspected. A
            # requested cancellation is never the miner's failure.
            if not miner_authored or _cancel_path(ledger, owner, identity).exists():
                raise
            failure = _observed_miner_failure(cli, name, error, seconds, started)
            if failure is None:
                raise
            if profile is not None and scratch_full(cli, name):
                # Carbon's own host caps scratch in the kernel
                # (LANE-RESOURCE-BOUND-01): a program that failed with its
                # tmpfs full is typed so, never a score or a scientific
                # outcome. A miner's machine has no cap and no such type.
                write_once(
                    operation / "scratch-cap.json",
                    canonical(
                        {
                            "refusal": SCRATCH_CAP_EXCEEDED,
                            "cap_bytes": profile.scratch_cap_bytes,
                            "cap_inodes": SCRATCH_CAP_INODES,
                        }
                    ),
                )
                failure = (WorkerCode.POLICY, SCRATCH_CAP_EXCEEDED)
        if failure is None:
            # The worker writes as its fixed non-root uid, so a directory the
            # miner's code creates with default modes is unreadable to the host
            # that collects it. The worker owns every output, so it opens them
            # to reading before the container goes; links are refused at
            # collection, and chmod -R does not follow them.
            cli.run(
                ["exec", name, "chmod", "-R", "a+rX", "/scratch/output"], timeout=120
            )
            if profile is not None:
                # A tmpfs scratch goes with its container, and `docker cp`
                # cannot read one: the output is copied out first, through
                # the same refusals collection applies.
                try:
                    copy_out_scratch(cli, name, scratch, profile.export_max_bytes)
                except MinerOutputRefused as refusal:
                    output_refused = refusal
        write_once(operation / "resources.json", canonical({"isolation": isolation}))
    finally:
        try:
            if create_attempted:
                remove_exact_container(
                    cli=cli, container_name=name, launch_digest=launch
                )
                remaining = cli.run(
                    ["ps", "-aq", "--filter", "name=^" + name + "$"], timeout=10
                )
                if remaining.stdout.strip():
                    raise ValueError(
                        "research cleanup uncertain; capacity stays reserved"
                    )
        finally:
            slot.close()
            lease.close()
    if failure is not None:
        _settle_miner_failure(
            ledger,
            owner=owner,
            identity=identity,
            operation=operation,
            resources=resources,
            started=started,
            failure=failure,
            before_finish=before_finish,
        )
    _check_cancel(ledger, owner, identity)
    snapshot = operation / "snapshot"
    try:
        if output_refused is not None:
            raise output_refused
        collect_outputs(scratch, snapshot)
    except MinerOutputRefused:
        # A link, FIFO, socket or device in the output is the miner's own
        # doing. An unreadable tree is not typed this way: that can be the
        # host's, and stays an infrastructure failure.
        if not miner_authored:
            raise
        _settle_miner_failure(
            ledger,
            owner=owner,
            identity=identity,
            operation=operation,
            resources=resources,
            started=started,
            failure=(WorkerCode.OUTPUT, "OUTPUT_NOT_REGULAR_FILES"),
            before_finish=before_finish,
        )
    if output_validator is not None:
        try:
            output_validator(snapshot)
        except ValueError:
            # The declared validator refused the miner's own bytes (malformed,
            # non-finite, undeclared type). OSError and the like stay infra.
            if not miner_authored:
                raise
            _settle_miner_failure(
                ledger,
                owner=owner,
                identity=identity,
                operation=operation,
                resources=resources,
                started=started,
                failure=(WorkerCode.OUTPUT, "OUTPUT_REFUSED_BY_VALIDATOR"),
                before_finish=before_finish,
            )
    files = {
        p.relative_to(snapshot).as_posix(): _file_digest(p)
        for p in sorted(snapshot.rglob("*"))
        if p.is_file()
    }
    result = {
        "schema": "carbon.autoresearch.worker-result.v1",
        "provenance": provenance,
        "output_digest": digest(canonical(files)),
        "files": files,
        "operation": operation.name,
        "lane": "MINER_RESEARCH_UNLIMITED",
        "scientific_qualification": False,
        "official_eligible": False,
    }
    elapsed = math.ceil((time.monotonic() - started) * 1000)
    actual = {
        **resources,
        "numerical_milliseconds": elapsed,
        "retained_bytes": sum(
            p.stat().st_size for p in operation.rglob("*") if p.is_file()
        ),
    }
    before_finish()
    ledger.finish(
        identity, owner=owner, state="SUCCEEDED", actual=actual, result=result
    )
    return result


_DOCKER_OWN_EXITS = frozenset({125, 126, 127})

#: What a miner-lane run keeps of its stdout and of its stderr: the last
#: 64 KiB of each, for successful and failed runs alike (RSURF-D21, owner,
#: 2026-10-03: "Keep both, capped").
KEPT_BYTES = 64 * 1024
STDOUT_FILE, STDERR_FILE = "stdout.txt", "stderr.txt"
#: What a code cell's result returns of what the program printed: the end of
#: its stdout and of its stderr and, on a nonzero exit, its traceback, each at
#: most 4 KiB as the result delivers it - JSON-escaped, so a byte that needs
#: an escape counts for every byte of its escape (LP-PROD-D). An engineering
#: bound on what reaches a model's context per call, not a limit on the
#: program: the kept 64 KiB stay in the operation folder.
OUTPUT_TAIL_BYTES = 4096
#: Where a traceback starts, in the order looked for: Python's, then Julia's.
_TRACEBACK_MARKERS = (b"Traceback (most recent call last):", b"ERROR: ")
#: What a long traceback keeps of its start: Julia's error message is its
#: first line, Python's exception its last, so a long one keeps both ends.
_TRACEBACK_HEAD = 2048
#: The note between a long traceback's two ends; `{}` is how many characters
#: were left out. Room is kept for it within `OUTPUT_TAIL_BYTES`.
_ELIDED = "\n[... {} characters left out by Carbon ...]\n"
_ELIDED_ROOM = 64
#: A run's operation folder: a direct child of the ledger root, never a path.
_OPERATION_FOLDER = re.compile(r"operation-[A-Za-z0-9_.-]{1,160}\Z", re.ASCII)


def _escaped(character):
    """One character's size as a result delivers it: JSON, escaped exactly as
    `canonical` escapes it (a control or non-ASCII character is \\uXXXX)."""
    return len(json.dumps(character)) - 2


def _bounded(text, limit, *, end):
    """The longest end (`end=True`) or start of `text` whose JSON-escaped
    size is at most `limit`, cut between whole characters. Reads no further
    than the cut."""
    total = count = 0
    for character in reversed(text) if end else text:
        size = _escaped(character)
        if total + size > limit:
            break
        total, count = total + size, count + 1
    return text[len(text) - count :] if end else text[:count]


def _text_tail(body):
    """The end of `body` as text, at most `OUTPUT_TAIL_BYTES` as delivered.
    Bytes that are not UTF-8 (or a character the cut split) become U+FFFD,
    never an error; the escaped text still fits."""
    return _bounded(
        body[-OUTPUT_TAIL_BYTES:].decode("utf-8", "replace"),
        OUTPUT_TAIL_BYTES,
        end=True,
    )


def _traceback_text(block):
    """One traceback, from its marker on, at most `OUTPUT_TAIL_BYTES` as
    delivered: whole when it fits, otherwise its start and its end with the
    number of characters left out between them. Its start holds Julia's
    `ERROR: <message>` and the outermost frames; its end holds Python's
    exception line and Julia's `in expression starting at <file>:<line>`."""
    text = block.decode("utf-8", "replace")
    whole = _bounded(text, OUTPUT_TAIL_BYTES, end=False)
    if len(whole) == len(text):
        return text
    head = _bounded(text, _TRACEBACK_HEAD, end=False)
    tail = _bounded(
        text[len(head) :],
        OUTPUT_TAIL_BYTES - _TRACEBACK_HEAD - _ELIDED_ROOM,
        end=True,
    )
    return head + _ELIDED.format(len(text) - len(head) - len(tail)) + tail


def program_output(ledger, operation, *, observation=None):
    """What the miner's program printed, bounded, for its own result.

    `operation` is the run's operation folder name, from its worker result;
    anything but a flat `operation-...` name reads nothing. Each tail is None
    where no kept file exists (a replayed or reconciled operation from before
    output was kept). On `NONZERO_EXIT`, `traceback` is the last traceback in
    the kept stderr (`_traceback_text`): Python's or Julia's, with both its
    first and its last lines kept when it is long, so the error is there in
    either language even when the program printed more after it. The output
    is the miner's own, self-reported and untrusted: it is returned to them,
    never interpreted.
    """
    if type(operation) is not str or not _OPERATION_FOLDER.match(operation):
        return {"stdout_tail": None, "stderr_tail": None}
    folder = ledger.root / operation

    def kept(name):
        path = folder / name
        if path.is_symlink() or not path.is_file():
            return None
        return path.read_bytes()[-KEPT_BYTES:]

    stdout, stderr = kept(STDOUT_FILE), kept(STDERR_FILE)
    value = {
        "stdout_tail": None if stdout is None else _text_tail(stdout),
        "stderr_tail": None if stderr is None else _text_tail(stderr),
    }
    if observation == "NONZERO_EXIT":
        start = -1
        for marker in _TRACEBACK_MARKERS if stderr is not None else ():
            start = stderr.rfind(marker)
            if start >= 0:
                break
        value["traceback"] = None if start < 0 else _traceback_text(stderr[start:])
    return value


class _Tail:
    """The last `limit` bytes of a stream, in bounded memory."""

    def __init__(self, limit):
        self.limit, self.buffer = limit, bytearray()

    def add(self, block):
        self.buffer += block
        if len(self.buffer) > 2 * self.limit:
            del self.buffer[: -self.limit]

    def value(self):
        return bytes(self.buffer[-self.limit :])


def stream_kept(cli, arguments, operation, *, timeout):
    """Run one fixed Docker command for the miner lane, keeping the last
    `KEPT_BYTES` of its stdout and of its stderr in `operation`, whatever the
    outcome. A timeout or nonzero exit raises `WorkerFailure(RUNTIME)` with
    the diagnostic `DockerCLI.stream_to_file` gives, so a failure is
    classified exactly as before; a large stderr no longer fails a run.
    """
    import os
    import selectors
    import subprocess

    from carbon.reconstruction.worker.docker_runtime import _stop_process
    from carbon.reconstruction.worker.model import DIAGNOSTIC_BYTES

    if type(timeout) not in (int, float) or timeout <= 0:
        raise WorkerFailure(WorkerCode.INVALID)
    environment = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        if key in os.environ:
            environment[key] = os.environ[key]
    stdout, stderr = _Tail(KEPT_BYTES), _Tail(KEPT_BYTES)
    head = bytearray()
    process = None
    try:
        process = subprocess.Popen(
            [cli.executable, *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, stdout)
        selector.register(process.stderr, selectors.EVENT_READ, stderr)
        deadline = time.monotonic() + float(timeout)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkerFailure(
                    WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
                )
            for key, _ in selector.select(timeout=min(remaining, 0.25)):
                block = os.read(key.fd, 1 << 16)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                key.data.add(block)
                if key.data is stderr and len(head) < DIAGNOSTIC_BYTES:
                    head.extend(block[: DIAGNOSTIC_BYTES - len(head)])
        code = process.wait(timeout=1)
        if code != 0:
            raise WorkerFailure(
                WorkerCode.RUNTIME,
                private_diagnostic=(
                    f"exit={code}\nstderr:\n".encode("ascii") + bytes(head)
                )[:DIAGNOSTIC_BYTES],
            )
    except WorkerFailure:
        if process is not None:
            _stop_process(process)
        raise
    except (OSError, subprocess.SubprocessError):
        if process is not None:
            _stop_process(process)
        raise WorkerFailure(
            WorkerCode.RUNTIME, private_diagnostic=bytes(head)
        ) from None
    finally:
        for name, tail in ((STDOUT_FILE, stdout), (STDERR_FILE, stderr)):
            path = operation / name
            if not path.exists():
                write_once(path, tail.value())


def _observed_miner_failure(cli, name, error, seconds, started):
    """Name the miner's program as the cause only on observed evidence.

    Returns ``(WorkerCode, observation)`` or None. None keeps the failure an
    infrastructure failure: an ambiguous daemon or CLI error is never blamed on
    the miner.
    """
    if seconds is not None and time.monotonic() - started >= seconds:
        # The miner's own allowance elapsed; the watchdog or stream bound that
        # fired is the one they chose.
        return WorkerCode.DEADLINE, "OWN_ALLOWANCE_ELAPSED"
    try:
        state = cli.json(["inspect", name, "--format", "{{json .State}}"], timeout=10)
    except WorkerFailure:
        return None
    if type(state) is not dict:
        return None
    if state.get("OOMKilled") is True:
        return WorkerCode.RUNTIME, "OOM_KILLED"
    exited = re.match(rb"exit=(\d+)\n", error.private_diagnostic)
    if (
        exited is not None
        and state.get("Running") is True
        and int(exited.group(1)) not in _DOCKER_OWN_EXITS
        and int(exited.group(1)) != 0
        and b"Error response from daemon" not in error.private_diagnostic
    ):
        # docker exec returned the program's own status from a container that
        # is still running: the program ran and exited nonzero.
        return WorkerCode.RUNTIME, "NONZERO_EXIT"
    return None


def _settle_miner_failure(
    ledger,
    *,
    owner,
    identity,
    operation,
    resources,
    started,
    failure,
    before_finish,
    limit=None,
):
    """Settle an observed miner-caused failure and raise it, typed.

    The full reservation is kept, and anything measured beyond it is charged
    too: the metered dimensions record at least what the run used.
    """
    code, observation = failure
    result = {
        "schema": MINER_FAILURE_SCHEMA,
        "operation": operation.name,
        "state": "FAILED_MINER",
        "cause": "MINER_PROGRAM",
        "failure_code": code.value,
        "observation": observation,
        "cleanup_observed": True,
        "accounting": "full original reservation retained; no refund",
        "retry_dispatched": False,
        "scientific_qualification": False,
        "official_eligible": False,
        # The limit that was reached (kind and value), for the miner's message.
        **({} if limit is None else {"limit": limit}),
    }
    elapsed = math.ceil((time.monotonic() - started) * 1000)
    retained = sum(p.stat().st_size for p in operation.rglob("*") if p.is_file())
    actual = {
        **resources,
        "numerical_milliseconds": max(resources["numerical_milliseconds"], elapsed),
        "retained_bytes": max(resources["retained_bytes"], retained),
    }
    before_finish()
    ledger.finish(
        identity, owner=owner, state="FAILED_MINER", actual=actual, result=result
    )
    raise MinerProgramFailure(result)


def record_output_tamper(ledger, *, owner, operation, name, expected, observed):
    """Leave a durable security_incident record, then refuse the output.

    A retained output whose digest no longer matches the one recorded when it
    was collected was changed after collection. Refusing it silently would
    leave no trace that anything happened; the record is written first, and if
    it cannot be written the refusal says so.
    """
    body = {
        "event": "RESEARCH_OUTPUT_DIGEST_MISMATCH",
        "operation": operation,
        "file": name[:256],
        "expected_digest": expected,
        "observed_digest": observed,
    }
    try:
        ledger.note(owner=owner, kind="security_incident", body=body)
    except Exception:  # noqa: BLE001
        raise ValueError(
            "research output changed; security incident record failed"
        ) from None
    raise ValueError("research output changed after collection")


def _has_time_budget(ledger):
    from .research_ledger import NO_BUDGET, _caps

    with ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    if row is None:
        return False
    return (
        _caps(json.loads(row[0])).get("numerical_milliseconds", NO_BUDGET)
        is not NO_BUDGET
    )


def _file_digest(path):
    import hashlib

    sha = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024**2):
            sha.update(chunk)
    return "sha256:" + sha.hexdigest()


def reconcile_worker(ledger, *, owner, identity):
    """Trusted recovery after supervisor exit; never dispatch/retry work.

    Cleanup success does not prove completed training or exact lost runtime.
    Retain the entire original reservation as conservative charged consumption.
    """
    with _numerical_lease(ledger):
        return _reconcile_locked(ledger, owner=owner, identity=identity)


def _reconcile_locked(ledger, *, owner, identity, only_if_gone=False):
    """`reconcile_worker`'s settle, with the owner's numerical lease ALREADY held by the caller. ``only_if_gone``
    (`_settle_dead_numerical`): a worker container still present refuses (reservation retained), never removed.
    """
    matches = [
        op for op in ledger.status(owner=owner)["operations"] if op["id"] == identity
    ]
    if len(matches) != 1:
        raise ValueError("owned operation unavailable")
    op = matches[0]
    if op["state"] == "HELD":
        raise ValueError("never-claimed sequence capacity requires sequence cleanup")
    if op["state"] != "RESERVED":
        return op["result"]
    # Keyed on the durable intent, not the reserved milliseconds: the
    # miner's own run with no wall allowance reserves none and is still a
    # worker. An operation with no intent is refused below, never skipped.
    intents = []
    for path in ledger.root.glob("operation-*/intent.json"):
        if path.is_symlink() or path.stat().st_size > 65536:
            raise ValueError("invalid worker intent")
        value = json.loads(path.read_bytes())
        if value.get("owner") == owner and value.get("identity") == identity:
            intents.append((path, value))
    # An absent intent may represent another provider or a interrupted stage.
    # Do not infer safe cleanup from absence or invent lost launch details.
    if len(intents) != 1:
        raise ValueError(
            "exact durable worker intent unavailable; reservation retained"
        )
    path, intent = intents[0]
    launch = digest(
        canonical({"owner": owner, "identity": identity, "request": intent["request"]})
    )
    name, label = _intent_container(intent, launch)
    if (
        intent["launch"] != launch
        or intent["container"] != name
        or path.parent.name != "operation-" + launch[7:]
    ):
        raise ValueError("worker intent identity conflict")
    # the daemon the intent names: a REMOTE grade lane's, a remote GPU build slot's, or this host's
    remote = remote_lane.recorded(intent)
    remote_build = remote_gpu_build.recorded(intent)
    if remote_build is not None and remote_build.gone:
        # its box file is gone (drained or refused): the box is gone for the door and the op is Carbon's. Its
        # container is removed through the box's copy when the box still answers, and only then is its local slot
        # record cleared; one that cannot be reached is its watchdog's and the box's own sweep's.
        _clear_gone_box(remote_build, name, label)
        result = {
            "schema": "carbon.autoresearch.worker-reconciliation.v1",
            "operation": path.parent.name,
            "state": "FAILED_INFRA",
            "cleanup_observed": False,
            "accounting": "full original reservation retained as conservative consumption",
            "scientific_outcome": "UNRESOLVED",
            "retry_dispatched": False,
        }
        ledger.finish(
            identity,
            owner=owner,
            state="FAILED_INFRA",
            actual=op["reservation"],
            result=result,
        )
        return result
    cli = remote_gpu_build.cli(remote_build) or _cli_for(remote)
    if (
        only_if_gone
        and cli.run(
            ["ps", "-aq", "--filter", "name=^" + name + "$"], timeout=10
        ).stdout.strip()
    ):
        raise ValueError("worker container present; reservation retained")
    with remote_gpu_build.bound(remote_build):
        remove_exact_container(cli=cli, container_name=name, launch_digest=label)
    if cli.run(
        ["ps", "-aq", "--filter", "name=^" + name + "$"], timeout=10
    ).stdout.strip():
        raise ValueError("cleanup uncertain; reservation retained")
    if remote is not None:
        with suppress(remote_lane.RemoteLaneDown):
            remote_lane.discard(path.parent / "input", remote)
    if remote_build is not None:
        with suppress(remote_lane.RemoteLaneDown):
            remote_gpu_build.discard(path.parent / "input", remote_build)
    result = {
        "schema": "carbon.autoresearch.worker-reconciliation.v1",
        "operation": path.parent.name,
        "state": "FAILED_INFRA",
        "cleanup_observed": True,
        "accounting": "full original reservation retained as conservative consumption",
        "scientific_outcome": "UNRESOLVED",
        "retry_dispatched": False,
    }
    ledger.finish(
        identity,
        owner=owner,
        state="FAILED_INFRA",
        actual=op["reservation"],
        result=result,
    )
    return result
