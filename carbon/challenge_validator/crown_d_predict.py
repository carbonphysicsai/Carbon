"""Crown-time D: one loaded, batched contender model behind `model_evaluator`.

The grading optimizer (`pool_model_search.model_search_de`) asks a contender's
rebuilt model for ~3000 predictions per target in batches. Today's inference
route (`bundle_construction_worker.infer_saved_bundle`) starts a fresh isolated
container for every call. `LivePredictor` starts ONE container per contender,
loads the model's `carbon.numeric-graph.v1` state ONCE with the inference
program's own rebuild code, and serves predict batches over the container's
stdin/stdout until it is closed.

Isolation is the inference route's, reused rather than restated: the same
worker image, the same `docker create` argv (`docker_runtime.create_arguments`
under the carrier's own worker profile for `DIRECT_BUNDLE_PUBLIC_INFERENCE`),
the same host doctor, watchdog, effective-controls inspection, bootstrap and
exact-container removal. The serving program is fixed and input-only: the
inference program's own staging, recipe/state/allowlist checks, x64 decision
and `carbon.level4.interpret.rebuild`, then a fixed serving loop. Nothing but
the trusted module closure, recipe, model state, allowlist, a public all-zero
dtype probe and the control document is staged; no source, TRAIN or hidden
data.

Failure typing. A container or host fault (start, crash, timeout, broken pipe,
short read, malformed frame) raises `LivePredictorFault`, which the caller maps
to FAILED_INFRA, never to the miner. A row whose raw output is non-finite comes
back as None (an invalid prediction the optimizer ranks last). A model whose
output breaks the graph contract (arity, batch, dtype) raises
`LiveModelContractError`; its classification is the caller's.

Not provided here (the caller owns them): ledger reservation and settlement of
the session, and the latency receipt document (the counts are exposed).
"""

from __future__ import annotations

import json
import math
import secrets
import shutil
import struct
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

SCHEMA = "carbon.crown-d.live-predictor.v1"
READY_SCHEMA = "carbon.crown-d.live-predictor.ready.v1"
PROVENANCE = "DIRECT_BUNDLE_PUBLIC_INFERENCE"
INPUT_NAMES = ("inputs/x", "inputs/forcing", "inputs/features")
#: Rows one predict() may carry (a DE generation is 8d <= 80 rows).
MAX_ROWS_PER_CALL = 4096
#: Frame ceilings: the ready document, one request, one response.
MAX_READY_BYTES = 65536
MAX_RESPONSE_BYTES = 64 * 1024**2
MAX_DIAGNOSTIC_BYTES = 65536
WORKER_PYTHON = "/opt/carbon-worker/bin/python"

FAULT_CODES = frozenset(
    {
        "START",  # host doctor, create, start, controls or exec launch failed
        "CRASH",  # the serving process ended (EOF on its stdout)
        "TIMEOUT",  # one call's wall clock elapsed
        "SESSION_TIMEOUT",  # the whole session's wall clock elapsed
        "BROKEN_PIPE",  # the request could not be written
        "PROTOCOL",  # a malformed, oversized or mismatched frame
        "CLOSED",  # used after close or after an earlier fault
        "CLEANUP",  # the exact container's removal was not observed
    }
)
CONTRACT_CODES = frozenset({"arity", "output_shape", "output_dtype"})


class LivePredictorFault(Exception):
    """Infrastructure, never the miner's failure: map to FAILED_INFRA."""

    failure_class = "FAILED_INFRA"

    def __init__(self, code: str, detail: str = ""):
        if code not in FAULT_CODES:
            raise TypeError("typed live predictor fault code required")
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code


class LiveModelContractError(ValueError):
    """The model's output broke the graph contract (arity, batch, dtype)."""

    def __init__(self, code: str):
        if code not in CONTRACT_CODES:
            raise TypeError("typed model contract code required")
        super().__init__(code)
        self.code = code


# --------------------------------------------------------------------------
# The fixed serving program: the inference program's own prefix (staging,
# recipe/state/allowlist checks, x64 decision, rebuild), then a serving loop.

_PROTOCOL_HEAD = r'''"""Fixed input-only live graph serving; no source or TRAIN."""
import os as _os, sys as _sys
# The protocol owns the original stdout; anything else written to fd 1 (a
# library warning) goes to stderr and can never corrupt a frame.
_channel = _os.fdopen(_os.dup(1), "wb", buffering=0)
_requests = _os.fdopen(_os.dup(0), "rb", buffering=0)
_os.dup2(2, 1)
_sys.stdout = _sys.stderr
'''

_PREFIX_END = "blocks = []\n"

_SERVE_TAIL = r"""
import struct

MAX_ROWS = __MAX_ROWS__


class _Contract(Exception):
    pass


def _read_exact(count):
    chunks, got = [], 0
    while got < count:
        block = _requests.read(count - got)
        if not block:
            return None
        chunks.append(block)
        got += len(block)
    return b"".join(chunks)


def _send(payload):
    view = memoryview(struct.pack(">I", len(payload)) + payload)
    while len(view):
        view = view[_channel.write(view):]


feature = tuple(int(n) for n in declared[-1]["shape"][1:])
width = 1
for n in feature:
    width *= n
in_dtype = inputs.dtype
want_dtype = control.get("expected_output_dtype")


def _forward(part):
    outputs = forward(*parameter_arrays, part)
    if len(outputs) != 1:
        raise _Contract("arity")
    result = np.asarray(outputs[0])
    if result.ndim < 1 or result.shape[0] != batch:
        raise _Contract("output_shape")
    if result.dtype.kind not in "fiu" or (
        want_dtype is not None and result.dtype != np.dtype(want_dtype)
    ):
        raise _Contract("output_dtype")
    return result


# One warm-up call on the public all-zero constant the per-case path pads with:
# the graph is compiled before the first timed request.
try:
    warm = _forward(jnp.zeros((batch, *feature), dtype=in_dtype))
    ready = {"warm": "ok", "row_shape": list(warm.shape[1:]),
             "output_dtype": str(warm.dtype)}
except _Contract as error:
    ready = {"warm": str(error), "row_shape": None, "output_dtype": None}
ready.update({
    "schema": "__READY_SCHEMA__",
    "batch": int(batch),
    "feature_shape": list(feature),
    "input_dtype": str(in_dtype),
    "state_digest": control["state_digest"],
    "per_case": per_case,
    "x64": bool(_os.environ.get("JAX_ENABLE_X64") == "1"),
})
_send(json.dumps(ready, sort_keys=True, allow_nan=False).encode())
step = 1 if per_case else batch
while True:
    head = _read_exact(4)
    if head is None:
        break
    (length,) = struct.unpack(">I", head)
    if not 5 <= length <= 5 + 8 * MAX_ROWS * width:
        raise SystemExit(3)
    body = _read_exact(length)
    if body is None or body[:1] != b"R":
        raise SystemExit(3)
    (count,) = struct.unpack(">I", body[1:5])
    if not 1 <= count <= MAX_ROWS or length != 5 + 8 * count * width:
        raise SystemExit(3)
    rows = np.frombuffer(body[5:], dtype="<f8").reshape((count, *feature))
    rows = jnp.asarray(rows.astype(in_dtype))
    blocks, calls = [], 0
    try:
        for start in range(0, count, step):
            part = rows[start:start + step]
            used = len(part)
            if used < batch:
                part = jnp.pad(part, [(0, batch - used)] + [(0, 0)] * len(feature))
            blocks.append(_forward(part)[:used])
            calls += 1
    except _Contract as error:
        _send(b"E" + str(error).encode())
        continue
    result = np.concatenate(blocks)
    tail = result.shape[1:]
    _send(b"O" + struct.pack(">III", count, calls, len(tail))
          + struct.pack(">%dI" % len(tail), *tail)
          + np.ascontiguousarray(result, dtype="<f8").tobytes())
"""


def _serve_program() -> str:
    from carbon.development_session.bundle_construction_worker import INFER_PROGRAM

    first, _, body = INFER_PROGRAM.partition("\n")
    if (
        not first.startswith('"""Fixed input-only graph inference')
        or body.count(_PREFIX_END) != 1
        or "from carbon.level4.interpret import rebuild" not in body
    ):
        raise RuntimeError("inference program prefix differs")
    prefix = body[: body.index(_PREFIX_END)]
    tail = _SERVE_TAIL.replace("__MAX_ROWS__", str(MAX_ROWS_PER_CALL)).replace(
        "__READY_SCHEMA__", READY_SCHEMA
    )
    return _PROTOCOL_HEAD + prefix + tail


SERVE_PROGRAM = _serve_program()


# --------------------------------------------------------------------------
# Staging: the inference route's own checks and module closure.


def stage_files(
    *,
    recipe,
    challenge_binding: dict,
    state_bytes: bytes,
    expected_state_digest: str,
    allowlist_bytes: bytes,
    input_dtype: str,
    expected_output_dtype: str | None,
    input_name: str = "inputs/x",
    per_case: bool = False,
    limits_document: dict | None = None,
) -> tuple[dict[str, bytes], dict]:
    """The checked input-only stage and the host's own view of the graph.

    Checks mirror `infer_saved_bundle`: recipe output format, exact state
    digest and size, trusted allowlist, trusted Challenge binding, optional
    resource policy, and a host-side `load` of the state.
    """
    from carbon.development_session import bundle_construction_worker as worker
    from carbon.development_session.bundle_graph_state import load, state_fits
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        RecipeRefused,
    )

    if (
        type(recipe) is not ConstructionRecipe
        or recipe.to_dict()["source"]["kind"] not in ("bundle", "graph")
        or recipe.to_dict()["output"]["format"] != "carbon.numeric-graph.v1"
        or type(state_bytes) is not bytes
        or type(expected_state_digest) is not str
        or type(allowlist_bytes) is not bytes
        or not 0 < len(allowlist_bytes) <= 1024**2
        or not state_fits(len(state_bytes), allowlist_bytes)
        or input_name not in INPUT_NAMES
        or type(per_case) is not bool
    ):
        raise RecipeRefused("live_predictor_binding_invalid")
    if worker._digest(state_bytes) != expected_state_digest:
        raise RecipeRefused("live_predictor_state_changed")
    if not worker._exact_numeric_dtype(input_dtype, input_dtype) or (
        np.dtype(input_dtype).kind != "f"
    ):
        raise RecipeRefused("live_predictor_input_dtype_invalid")
    if expected_output_dtype is not None and not worker._exact_numeric_dtype(
        expected_output_dtype, expected_output_dtype
    ):
        raise RecipeRefused("live_predictor_output_dtype_invalid")
    binding = worker._checked_binding(recipe, challenge_binding)
    allowed = worker._trusted_allowlist(allowlist_bytes)
    if limits_document is not None:
        # called bare (Validator-2B 7 Nov): the check takes the version's own published profile, the one live predict
        # builds under; a caller naming its own profile could drift from it (test_published_policy_is_enforced)
        worker.verify_direct_resource_policy(binding, limits_document)
    doc, parameters = load(state_bytes, recipe, allowed)
    declared = doc["graphs"][doc["entry"]]["inputs"]
    if len(declared) != len(parameters) + 1 or declared[-1]["name"] != input_name:
        raise RecipeRefused("live_predictor_input_binding_invalid")
    shape = [int(n) for n in declared[-1]["shape"]]
    if len(shape) < 2 or any(n < 1 for n in shape):
        raise RecipeRefused("live_predictor_input_shape_invalid")
    batch, feature = shape[0], tuple(shape[1:])
    # The public dtype probe: one all-zero row. The inference prefix decides
    # x64 from it exactly as from a real query of that dtype.
    probe = worker._tensors(inputs=np.zeros((1, *feature), dtype=input_dtype))
    files, codec_modules = worker._stage_bundle_modules(binding, training=False)
    control = {
        "recipe_digest": recipe.digest,
        "binding": binding,
        "codec_modules": codec_modules,
        "state_digest": expected_state_digest,
        "inputs_digest": worker._digest(probe),
        "allowlist_digest": allowed.digest,
        "expected_output_shape": [1],
        "per_case": per_case,
    }
    if expected_output_dtype is not None:
        control["expected_output_dtype"] = expected_output_dtype
    if input_name != "inputs/x":
        control["input_name"] = input_name
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "state.npz": state_bytes,
            "inputs.npz": probe,
            "allowlist.json": allowlist_bytes,
            "control.json": json.dumps(
                control, sort_keys=True, separators=(",", ":")
            ).encode(),
        }
    )
    if {"train.npz", "train.gz", "source.tar.gz", "program.py"} & set(files):
        raise ValueError("live predictor stage contains construction material")
    view = {
        "batch": batch,
        "feature_shape": list(feature),
        "input_dtype": str(np.dtype(input_dtype)),
        "expected_output_dtype": expected_output_dtype,
        "state_digest": expected_state_digest,
        "per_case": per_case,
        "allowlist_version": allowed.version,
        "rebuild_wall": worker.rebuild_wall_kwargs(limits_document),
    }
    return files, view


# --------------------------------------------------------------------------
# Transport: one long-lived process speaking length-prefixed frames.


class PipeChannel:
    """Frames over one process's stdin/stdout, every read under a deadline.

    Reader threads make the deadline portable (no select on pipes); stderr is
    kept as a bounded private diagnostic and never parsed.
    """

    def __init__(self, process):
        self.process = process
        self._buffer = bytearray()
        self._eof = False
        self._ready = threading.Condition()
        self.diagnostic = bytearray()
        threading.Thread(target=self._pump, daemon=True).start()
        if getattr(process, "stderr", None) is not None:
            threading.Thread(target=self._drain, daemon=True).start()

    def _pump(self):
        stream = self.process.stdout
        try:
            while True:
                block = (
                    stream.read1(1 << 16)
                    if hasattr(stream, "read1")
                    else (stream.read(1 << 16))
                )
                if not block:
                    break
                with self._ready:
                    self._buffer.extend(block)
                    if len(self._buffer) > MAX_RESPONSE_BYTES + 64:
                        break
                    self._ready.notify_all()
        except (OSError, ValueError):
            pass
        with self._ready:
            self._eof = True
            self._ready.notify_all()

    def _drain(self):
        try:
            for block in iter(lambda: self.process.stderr.read(4096), b""):
                keep = MAX_DIAGNOSTIC_BYTES - len(self.diagnostic)
                if keep > 0:
                    self.diagnostic.extend(block[:keep])
        except (OSError, ValueError):
            pass

    def send(self, data: bytes, deadline: float, code_on_timeout: str) -> None:
        errors = []

        def write():
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (OSError, ValueError) as error:
                errors.append(error)

        writer = threading.Thread(target=write, daemon=True)
        writer.start()
        writer.join(max(0.0, deadline - time.monotonic()))
        if writer.is_alive():
            raise LivePredictorFault(code_on_timeout, "request write")
        if errors:
            raise LivePredictorFault("BROKEN_PIPE", type(errors[0]).__name__)

    def recv_exact(self, count: int, deadline: float, code_on_timeout: str) -> bytes:
        with self._ready:
            while len(self._buffer) < count:
                if self._eof:
                    raise LivePredictorFault("CRASH", "serving process ended")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LivePredictorFault(code_on_timeout)
                self._ready.wait(min(remaining, 0.5))
            body = bytes(self._buffer[:count])
            del self._buffer[:count]
            return body

    def close(self) -> None:
        for stream in (self.process.stdin,):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass


def _writable_retry(function, path, _info):
    """The staged files are read-only (0o444); make one writable and retry."""
    import os

    os.chmod(path, 0o700)
    function(path)


def _docker_environment() -> dict[str, str]:
    """The Docker CLI environment `DockerCLI.run` passes, nothing more."""
    import os

    environment = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        if name in os.environ:
            environment[name] = os.environ[name]
    return environment


def exec_arguments(container_name: str) -> list[str]:
    """The carrier's fixed program exec, plus `-i` for the request stream."""
    from carbon.development_session.research_carrier import BOOTSTRAP

    return ["exec", "-i", container_name, WORKER_PYTHON, "-I", "-c", BOOTSTRAP]


class DockerLauncher:
    """Start one serving container with the inference route's exact controls.

    `cli` and `popen` are injectable for tests; production uses the real
    `DockerCLI` and `subprocess.Popen`.
    """

    def __init__(self, *, image, stage_root: Path, cli=None, popen=None):
        from carbon.reconstruction.worker.model import WorkerImageIdentity

        if type(image) is not WorkerImageIdentity:
            raise ValueError("pinned inference worker image required")
        stage_root = Path(stage_root)
        if not stage_root.is_absolute() or not stage_root.is_dir():
            raise ValueError("absolute existing stage root required")
        self.image = image
        self.stage_root = stage_root
        self._cli = cli
        self._popen = popen or subprocess.Popen
        self.container_name = None
        self.launch_digest = None
        self.stage = None
        self.controls_digest = None
        self._created = False

    def worker_profile(self, view):
        from carbon.development_session.research_carrier import _worker_profile
        from carbon.reconstruction.worker.model import worker_resources_version

        return _worker_profile(
            None,
            PROVENANCE,
            worker_resources_version(view["allowlist_version"]),
            view["rebuild_wall"].get("rebuild_wall_seconds"),
        )

    def start(self, files: dict[str, bytes], view: dict, session_deadline_unix: float):
        from carbon.development_session.profile import canonical, digest
        from carbon.development_session.research_carrier import (
            _FIXED_DIAGNOSTIC_PROVENANCES,
        )
        from carbon.reconstruction.worker.docker_runtime import (
            DOCKER_CWD,
            DockerCLI,
            create_arguments,
            doctor,
            inspect_effective_controls,
            spawn_watchdog,
        )
        from carbon.reconstruction.worker.model import worker_resources_version

        cli = self._cli or DockerCLI()
        self._cli = cli
        worker = self.worker_profile(view)
        sizing = (
            {}
            if worker_resources_version(view["allowlist_version"]) is None
            else {"worker_profile": worker}
        )
        launch = digest(
            canonical(
                {
                    "schema": SCHEMA,
                    "files": {name: digest(body) for name, body in files.items()},
                    "program": digest(SERVE_PROGRAM.encode()),
                    "image": self.image.image_id,
                    "nonce": secrets.token_hex(16),
                }
            )
        )
        self.launch_digest = launch
        self.container_name = "carbon-dl-" + launch[7:31]
        self.stage = self.stage_root / ("live-" + launch[7:39]) / "input"
        self.stage.mkdir(parents=True, mode=0o755)
        self.stage.chmod(0o755)
        for name, body in {**files, "program.py": SERVE_PROGRAM.encode()}.items():
            path = self.stage / name
            path.write_bytes(body)
            path.chmod(0o444)
        checked = doctor(
            image_id=self.image.image_id, image_identity=self.image, cli=cli, **sizing
        )
        if not checked.eligible:
            raise LivePredictorFault("START", "host ineligible")
        self._created = True
        cli.run(
            create_arguments(
                container_name=self.container_name,
                image_id=self.image.image_id,
                input_directory=self.stage,
                cpuset=checked.cpuset,
                launch_digest=launch,
                worker_profile=worker,
            ),
            timeout=30,
        )
        # The external deadline: the container goes even if this controller dies.
        spawn_watchdog(
            container_name=self.container_name,
            launch_digest=launch,
            deadline_unix=float(session_deadline_unix),
        )
        cli.run(["start", self.container_name], timeout=20)
        self.controls_digest, _ = inspect_effective_controls(
            cli=cli,
            container_name=self.container_name,
            image_id=self.image.image_id,
            input_directory=self.stage,
            cpuset=checked.cpuset,
            launch_digest=launch,
            worker_profile=worker,
            diagnose_policy=PROVENANCE in _FIXED_DIAGNOSTIC_PROVENANCES,
        )
        process = self._popen(
            [cli.executable, *exec_arguments(self.container_name)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_docker_environment(),
            cwd=DOCKER_CWD,
        )
        return PipeChannel(process)

    def stop(self) -> None:
        from carbon.reconstruction.worker.docker_runtime import remove_exact_container

        try:
            if self._created:
                remove_exact_container(
                    cli=self._cli,
                    container_name=self.container_name,
                    launch_digest=self.launch_digest,
                )
                remaining = self._cli.run(
                    ["ps", "-aq", "--filter", "name=^" + self.container_name + "$"],
                    timeout=10,
                )
                if remaining.stdout.strip():
                    raise LivePredictorFault("CLEANUP", "container still present")
        finally:
            if self.stage is not None and self.stage.parent.exists():
                shutil.rmtree(self.stage.parent, onerror=_writable_retry)


# --------------------------------------------------------------------------


class LivePredictor:
    """One loaded contender model serving batched predictions.

    `call_seconds` bounds one predict() (request write to response read);
    `session_seconds` bounds the whole session from start (startup included)
    and is also the external watchdog deadline. Both are required: there is
    no production default. `launcher` is a `DockerLauncher` (production) or a
    test double with the same `start(files, view, deadline_unix) -> channel`
    and `stop()`.
    """

    def __init__(
        self,
        *,
        recipe,
        challenge_binding: dict,
        state_bytes: bytes,
        expected_state_digest: str,
        allowlist_bytes: bytes,
        input_dtype: str,
        expected_output_dtype: str | None,
        call_seconds: float,
        session_seconds: float,
        launcher,
        per_case: bool,  # True = one row per graph call (the graded route's property); False = batched rows (a
        # model sees other rows of the same call). No default: the Validator chooses per Challenge.
        input_name: str = "inputs/x",
        limits_document: dict | None = None,
    ):
        for value in (call_seconds, session_seconds):
            if type(value) not in (int, float) or not 0 < value < math.inf:
                raise ValueError("explicit positive call and session wall clocks")
        self.call_seconds = float(call_seconds)
        self.session_seconds = float(session_seconds)
        self._files, self.view = stage_files(
            recipe=recipe,
            challenge_binding=challenge_binding,
            state_bytes=state_bytes,
            expected_state_digest=expected_state_digest,
            allowlist_bytes=allowlist_bytes,
            input_dtype=input_dtype,
            expected_output_dtype=expected_output_dtype,
            input_name=input_name,
            per_case=per_case,
            limits_document=limits_document,
        )
        self._launcher = launcher
        self._channel = None
        self._state = "NEW"
        self._deadline = None
        self._width = math.prod(self.view["feature_shape"])
        self._out_dtype = None
        self._row_shape = None
        self.calls = 0
        self.rows = 0
        self.graph_calls = 0
        self.wall_seconds = 0.0
        self.startup_seconds = None

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_exc):
        self.close()
        return False

    def start(self):
        if self._state != "NEW":
            raise LivePredictorFault("CLOSED", "a session starts once")
        self._state = "STARTING"
        begun = time.perf_counter()
        self._deadline = time.monotonic() + self.session_seconds
        try:
            self._channel = self._launcher.start(
                self._files, self.view, time.time() + self.session_seconds
            )
            ready = json.loads(self._frame(self._deadline, "SESSION_TIMEOUT", True))
        except LivePredictorFault:
            self._fail()
            raise
        except Exception as error:  # every start fault is infra
            self._fail()
            raise LivePredictorFault("START", type(error).__name__) from error
        expected = {
            "schema": READY_SCHEMA,
            "batch": self.view["batch"],
            "feature_shape": self.view["feature_shape"],
            "input_dtype": self.view["input_dtype"],
            "state_digest": self.view["state_digest"],
            "per_case": self.view["per_case"],
        }
        if type(ready) is not dict or any(
            ready.get(k) != v for k, v in expected.items()
        ):
            self._fail()
            raise LivePredictorFault("PROTOCOL", "ready document differs")
        if ready.get("warm") != "ok":
            self._fail()
            if ready.get("warm") in CONTRACT_CODES:
                raise LiveModelContractError(ready["warm"])
            raise LivePredictorFault("PROTOCOL", "warm-up result differs")
        self._out_dtype = np.dtype(ready["output_dtype"])
        self._row_shape = tuple(ready["row_shape"])
        self.startup_seconds = time.perf_counter() - begun
        self._state = "READY"
        return self

    def close(self):
        if self._state == "CLOSED":
            return
        self._state = "CLOSED"
        try:
            if self._channel is not None:
                self._channel.close()
        finally:
            self._launcher.stop()

    def _fail(self):
        try:
            self.close()
        except Exception:  # noqa: BLE001, S110 - the first fault is reported
            pass

    # -- protocol ----------------------------------------------------------

    def _frame(self, deadline, code, ready=False):
        head = self._channel.recv_exact(4, deadline, code)
        (length,) = struct.unpack(">I", head)
        ceiling = MAX_READY_BYTES if ready else MAX_RESPONSE_BYTES
        if not 1 <= length <= ceiling:
            raise LivePredictorFault("PROTOCOL", "frame length")
        return self._channel.recv_exact(length, deadline, code)

    @property
    def predict(self):
        """`predict(rows) -> list`, one raw output row (or None) per input row."""
        return self._predict

    def _predict(self, rows):
        if self._state != "READY":
            raise LivePredictorFault("CLOSED", self._state)
        matrix = np.asarray(rows, dtype=np.float64)
        if (
            matrix.ndim != 2
            or not 1 <= len(matrix) <= MAX_ROWS_PER_CALL
            or matrix.shape[1] != self._width
            or not np.isfinite(matrix).all()
        ):
            raise ValueError("finite rows of the model's input width required")
        timer = time.perf_counter()
        now = time.monotonic()
        if now >= self._deadline:
            self._fail()
            raise LivePredictorFault("SESSION_TIMEOUT")
        session_bound = self._deadline <= now + self.call_seconds
        deadline = min(now + self.call_seconds, self._deadline)
        code = "SESSION_TIMEOUT" if session_bound else "TIMEOUT"
        count = len(matrix)
        try:
            request = (
                b"R"
                + struct.pack(">I", count)
                + np.ascontiguousarray(matrix, dtype="<f8").tobytes()
            )
            self._channel.send(
                struct.pack(">I", len(request)) + request, deadline, code
            )
            body = self._frame(deadline, code)
            predictions, graph_calls = self._decode(body, count)
        except LiveModelContractError:
            raise
        except LivePredictorFault:
            self._fail()
            raise
        except Exception as error:  # a malformed reply is infra
            self._fail()
            raise LivePredictorFault("PROTOCOL", type(error).__name__) from error
        self.calls += 1
        self.rows += count
        self.graph_calls += graph_calls
        self.wall_seconds += time.perf_counter() - timer
        return predictions

    def _decode(self, body, count):
        if body[:1] == b"E":
            code = body[1:].decode("ascii", "strict")
            if code not in CONTRACT_CODES:
                raise LivePredictorFault("PROTOCOL", "error frame")
            raise LiveModelContractError(code)
        if body[:1] != b"O" or len(body) < 13:
            raise LivePredictorFault("PROTOCOL", "response tag")
        n, graph_calls, ndim = struct.unpack(">III", body[1:13])
        step = 1 if self.view["per_case"] else self.view["batch"]
        if (
            n != count
            or graph_calls != -(-count // step)
            or ndim != len(self._row_shape)
            or len(body) < 13 + 4 * ndim
        ):
            raise LivePredictorFault("PROTOCOL", "response header")
        tail = struct.unpack(f">{ndim}I", body[13 : 13 + 4 * ndim])
        offset = 13 + 4 * ndim
        if tuple(tail) != self._row_shape or len(body) - offset != 8 * n * math.prod(
            tail
        ):
            raise LivePredictorFault("PROTOCOL", "response size")
        values = np.frombuffer(body[offset:], dtype="<f8").reshape((n, *tail))
        out = []
        for row in values:
            if not np.isfinite(row).all():
                out.append(None)
            else:
                # Back to the graph's own dtype: the same values the file
                # route's JSON carries (float32 -> float64 is exact).
                out.append(row.astype(self._out_dtype).tolist())
        return out, graph_calls

    def counts(self) -> dict:
        """The latency receipt's numbers."""
        return {
            "calls": self.calls,
            "rows": self.rows,
            "graph_calls": self.graph_calls,
            "wall_seconds": self.wall_seconds,
            "startup_seconds": self.startup_seconds,
            "batch": self.view["batch"],
            "per_case": self.view["per_case"],
        }
