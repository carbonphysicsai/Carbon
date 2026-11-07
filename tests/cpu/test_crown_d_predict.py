"""Crown-time D live predictor: one loaded model, batched predict, typed faults."""

import io
import itertools
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_validator import crown_d_predict as live
from carbon.development_session import bundle_construction_worker as worker
from carbon.development_session import research_carrier
from carbon.development_session.bundle_graph_state import freeze
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist, graph
from carbon.reconstruction.worker import docker_runtime
from carbon.reconstruction.worker.model import WorkerImageIdentity

BATCH, WIDTH = 4, 3


def _sha(char):
    return "sha256:" + char * 64


def _recipe():
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": {
                "id": "public-field-fixture",
                "version": "development-v1",
                "train_digest": _sha("a"),
                "interface_digest": _sha("b"),
                "construction_limits_digest": _sha("c"),
            },
            "source": {
                "kind": "bundle",
                "bundle_ref": {
                    "schema": "carbon.library-bundle-ref.v1",
                    "bundle_digest": _sha("d"),
                    "language": "python",
                    "runtime_profile_id": "jax-cuda13-py311",
                    "environment_digest": _sha("e"),
                },
            },
            "procedure": {
                "entrypoint": {"module": "candidate.build", "name": "build"},
                "configuration": {},
                "train_use": {},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": _sha("b"),
            },
        }
    )


def _binding(recipe):
    row = recipe.to_dict()["challenge"]
    return {
        "challenge_id": row["id"],
        "challenge_version": row["version"],
        "train_digest": row["train_digest"],
        "interface_digest": row["interface_digest"],
        "construction_limits_digest": row["construction_limits_digest"],
    }


ALLOWED = allowlist.load(Path(allowlist.PATH).with_name("allowlist_v2.json"))


def _model_state(recipe):
    """A tiny synthetic fixture graph: y = x * x + p (p: one parameter)."""
    shape = [BATCH, WIDTH]
    doc = {
        "schema": graph.SCHEMA,
        "allowlist": ALLOWED.version,
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {
                        "value": 0,
                        "name": "params/0",
                        "dtype": "float32",
                        "shape": shape,
                    },
                    {
                        "value": 1,
                        "name": "inputs/x",
                        "dtype": "float32",
                        "shape": shape,
                    },
                ],
                "constants": [],
                "nodes": [
                    {
                        "op": "mul",
                        "in": [1, 1],
                        "out": [{"value": 2, "dtype": "float32", "shape": shape}],
                        "params": {"out_dtype": None},
                    },
                    {
                        "op": "add",
                        "in": [2, 0],
                        "out": [{"value": 3, "dtype": "float32", "shape": shape}],
                        "params": {},
                    },
                ],
                "outputs": [3],
            }
        },
    }
    parameter = np.tile(np.asarray([0.5, -1.0, 2.0], np.float32), (BATCH, 1))
    return freeze(recipe, doc, [parameter], ALLOWED)


def _model(rows):
    p = np.asarray([0.5, -1.0, 2.0], np.float32)
    x = np.asarray(rows, np.float32)
    return x * x + p


def _kwargs(**changes):
    recipe = _recipe()
    state = _model_state(recipe)
    return {
        "recipe": recipe,
        "challenge_binding": _binding(recipe),
        "state_bytes": state,
        "expected_state_digest": worker._digest(state),
        "allowlist_bytes": ALLOWED.raw,
        "input_dtype": "float32",
        "expected_output_dtype": "float32",
        **changes,
    }


# --------------------------------------------------------------------------
# Staging


def test_stage_is_input_only_and_reads_the_graph_on_the_host():
    files, view = live.stage_files(**_kwargs())
    assert view["batch"] == BATCH and view["feature_shape"] == [WIDTH]
    assert {"recipe.json", "state.npz", "inputs.npz", "allowlist.json"} <= set(files)
    assert not {"train.npz", "train.gz", "source.tar.gz", "program.py"} & set(files)
    assert not any(name.startswith("candidate") for name in files)
    control = json.loads(files["control.json"])
    assert control["per_case"] is False and "measure_query" not in control
    # The probe is one public all-zero row of the declared dtype.
    probe = np.load(io.BytesIO(files["inputs.npz"]))["inputs"]
    assert probe.dtype == np.float32 and probe.shape == (1, WIDTH) and not probe.any()


def test_stage_refuses_a_changed_state_or_an_untrusted_allowlist():
    kwargs = _kwargs()
    with pytest.raises(RecipeRefused, match="state_changed"):
        live.stage_files(**{**kwargs, "expected_state_digest": _sha("f")})
    with pytest.raises(RecipeRefused):
        live.stage_files(**{**kwargs, "allowlist_bytes": ALLOWED.raw + b" "})
    with pytest.raises(RecipeRefused):
        live.stage_files(**{**kwargs, "input_dtype": "int32"})


def test_serving_program_reuses_the_inference_prefix_and_its_rebuild():
    program = live.SERVE_PROGRAM
    prefix = worker.INFER_PROGRAM.partition("\n")[2]
    prefix = prefix[: prefix.index("blocks = []\n")]
    assert prefix in program
    assert "from carbon.level4.interpret import rebuild" in program
    for forbidden in ("train.npz", "predictions.json", "source.tar.gz"):
        assert forbidden not in program.split(prefix)[1]


# --------------------------------------------------------------------------
# The real serving loop, run with numpy standing in for jax.numpy


def _run_tail(requests, *, per_case=False, forward=None, want="float32"):
    calls = []

    def default_forward(part):
        calls.append(np.asarray(part).copy())
        return [_model(part)]

    sent = io.BytesIO()
    namespace = {
        "np": np,
        "jnp": np,
        "json": json,
        "_os": os,
        "_requests": io.BytesIO(requests),
        "_channel": sent,
        "declared": [
            {"name": "params/0", "shape": [BATCH, WIDTH]},
            {"name": "inputs/x", "shape": [BATCH, WIDTH]},
        ],
        "inputs": np.zeros((1, WIDTH), np.float32),
        "control": {"state_digest": _sha("9"), "expected_output_dtype": want},
        "per_case": per_case,
        "batch": BATCH,
        "parameter_arrays": [],
        "forward": forward or default_forward,
    }
    tail = live._SERVE_TAIL.replace(
        "__MAX_ROWS__", str(live.MAX_ROWS_PER_CALL)
    ).replace("__READY_SCHEMA__", live.READY_SCHEMA)
    exec(compile(tail, "serve_tail", "exec"), namespace)  # noqa: S102
    raw, frames = sent.getvalue(), []
    while raw:
        (length,) = struct.unpack(">I", raw[:4])
        frames.append(raw[4 : 4 + length])
        raw = raw[4 + length :]
    return frames, calls


def _request(rows):
    rows = np.asarray(rows, "<f8")
    body = b"R" + struct.pack(">I", len(rows)) + rows.tobytes()
    return struct.pack(">I", len(body)) + body


@pytest.mark.parametrize("count", [1, 3, 4, 5, 9, 24])
def test_serving_loop_chunks_to_the_batch_pads_and_strips(count):
    rows = np.arange(count * WIDTH, dtype=np.float64).reshape(count, WIDTH) / 7
    frames, calls = _run_tail(_request(rows))
    ready = json.loads(frames[0])
    assert ready["batch"] == BATCH and ready["warm"] == "ok"
    assert ready["row_shape"] == [WIDTH] and ready["output_dtype"] == "float32"
    graph_calls = calls[1:]  # after the one warm-up call
    assert len(graph_calls) == math.ceil(count / BATCH)
    assert all(part.shape == (BATCH, WIDTH) for part in graph_calls)
    used = count - BATCH * (len(graph_calls) - 1)
    assert not graph_calls[-1][used:].any()  # padding is the zero constant
    body = frames[1]
    assert body[:1] == b"O"
    n, made, ndim = struct.unpack(">III", body[1:13])
    assert (n, made, ndim) == (count, len(graph_calls), 1)
    values = np.frombuffer(body[17:], "<f8").reshape(count, WIDTH)
    np.testing.assert_array_equal(values, _model(rows.astype(np.float32)))


def test_serving_loop_per_case_makes_one_graph_call_per_row():
    rows = np.ones((5, WIDTH))
    frames, calls = _run_tail(_request(rows), per_case=True)
    assert len(calls) == 1 + 5
    assert all(not part[1:].any() for part in calls[1:])
    assert struct.unpack(">III", frames[1][1:13]) == (5, 5, 1)


def test_serving_loop_reports_a_contract_break_and_keeps_serving():
    frames, _ = _run_tail(_request([[1, 2, 3]]) * 2, want="float64")
    assert json.loads(frames[0])["warm"] == "output_dtype"
    assert frames[1:] == [b"Eoutput_dtype", b"Eoutput_dtype"]


def test_serving_loop_refuses_a_malformed_request():
    bad = struct.pack(">I", 9) + b"R" + struct.pack(">I", 2) + b"\0" * 4
    with pytest.raises(SystemExit):
        _run_tail(bad)


# --------------------------------------------------------------------------
# Host side over a real pipe to a fake server (no docker, no jax)

FAKE_SERVER = r"""
import json, math, struct, sys, time
import numpy as np
mode, batch, width = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
state_digest = sys.argv[4]
inp, out = sys.stdin.buffer, sys.stdout.buffer
def send(payload):
    out.write(struct.pack(">I", len(payload)) + payload); out.flush()
def exact(n):
    data = b""
    while len(data) < n:
        block = inp.read(n - len(data))
        if not block:
            sys.exit(0)
        data += block
    return data
if mode == "no_ready":
    sys.exit(1)
send(json.dumps({"schema": "carbon.crown-d.live-predictor.ready.v1",
    "batch": batch, "feature_shape": [width], "input_dtype": "float32",
    "state_digest": state_digest, "per_case": False, "warm": "ok",
    "row_shape": [width], "output_dtype": "float32", "x64": False}).encode())
p = np.asarray([0.5, -1.0, 2.0], np.float32)
while True:
    (length,) = struct.unpack(">I", exact(4))
    body = exact(length)
    (n,) = struct.unpack(">I", body[1:5])
    x = np.frombuffer(body[5:], "<f8").reshape(n, width).astype(np.float32)
    y = (x * x + p).astype("<f8")
    y[x[:, 0] > 100] = math.nan
    y[x[:, 0] < -100, 1] = math.inf
    calls = -(-n // batch)
    if mode == "crash":
        sys.exit(1)
    if mode == "hang":
        time.sleep(30)
    if mode == "short":
        out.write(struct.pack(">I", 1000) + b"O12"); out.flush(); sys.exit(0)
    if mode == "bad_count":
        calls += 1
    if mode == "contract":
        send(b"Earity"); continue
    send(b"O" + struct.pack(">IIII", n, calls, 1, width) + y.tobytes())
"""


class FakeLauncher:
    def __init__(self, mode="ok", hang_start=False):
        self.mode = mode
        self.process = None
        self.stopped = 0
        self.hang_start = hang_start

    def start(self, files, view, deadline_unix):
        assert "program.py" not in files and deadline_unix > time.time()
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                FAKE_SERVER,
                self.mode,
                str(view["batch"]),
                str(view["feature_shape"][0]),
                view["state_digest"],
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return live.PipeChannel(self.process)

    def stop(self):
        self.stopped += 1
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)


def _predictor(launcher, call_seconds=20, session_seconds=60, per_case=False):
    return live.LivePredictor(
        **_kwargs(),
        call_seconds=call_seconds,
        session_seconds=session_seconds,
        launcher=launcher,
        per_case=per_case,
    )


def test_per_case_has_no_default():
    with pytest.raises(TypeError, match="per_case"):
        live.LivePredictor(
            **_kwargs(), call_seconds=20, session_seconds=60, launcher=FakeLauncher()
        )


def test_predict_round_trips_counts_and_none_for_non_finite_rows():
    launcher = FakeLauncher()
    with _predictor(launcher) as predictor:
        rows = [[1.0, 2.0, 3.0], [200.0, 0.0, 0.0], [-200.0, 1.0, 1.0]] + [
            [0.25, 0.5, 0.75]
        ] * 6
        out = predictor.predict(rows)
        assert len(out) == len(rows)
        assert out[0] == _model([[1.0, 2.0, 3.0]])[0].tolist()
        assert out[1] is None and out[2] is None
        assert out[3] == _model([[0.25, 0.5, 0.75]])[0].tolist()
        predictor.predict([[0.0, 0.0, 0.0]])
        counts = predictor.counts()
        assert counts["calls"] == 2 and counts["rows"] == 10
        assert counts["graph_calls"] == math.ceil(9 / BATCH) + 1
        assert counts["wall_seconds"] > 0 and counts["startup_seconds"] > 0
    assert launcher.stopped == 1 and launcher.process.poll() is not None
    with pytest.raises(live.LivePredictorFault) as fault:
        predictor.predict([[0.0, 0.0, 0.0]])
    assert fault.value.code == "CLOSED"
    assert fault.value.failure_class == "FAILED_INFRA"


def test_predict_works_through_model_evaluator():
    from carbon.scoring.pool_model_search import model_evaluator

    with _predictor(FakeLauncher()) as predictor:
        solve = model_evaluator(
            predictor.predict,
            input_names=("a", "b", "c"),
            design_names=("b", "c"),
            derive=lambda inputs, out: None if out is None else {"y": out[0]},
        )
        result = solve({"a": 1.0}, [(0.0, 0.0), (1.0, 1.0)])
    assert [row["outputs"]["y"] for row in result] == [1.5, 1.5]


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("crash", "CRASH"),
        ("short", "CRASH"),
        ("bad_count", "PROTOCOL"),
        ("hang", "TIMEOUT"),
    ],
)
def test_host_faults_are_typed_infra_and_close_the_session(mode, code):
    launcher = FakeLauncher(mode)
    predictor = _predictor(launcher, call_seconds=2).start()
    with pytest.raises(live.LivePredictorFault) as fault:
        predictor.predict([[1.0, 2.0, 3.0]])
    assert fault.value.code == code and fault.value.failure_class == "FAILED_INFRA"
    assert launcher.stopped == 1
    with pytest.raises(live.LivePredictorFault):
        predictor.predict([[1.0, 2.0, 3.0]])


def test_a_session_timeout_is_typed():
    launcher = FakeLauncher("hang")
    predictor = _predictor(launcher, call_seconds=30, session_seconds=3).start()
    with pytest.raises(live.LivePredictorFault) as fault:
        predictor.predict([[1.0, 2.0, 3.0]])
    assert fault.value.code == "SESSION_TIMEOUT" and launcher.stopped == 1


def test_a_start_failure_is_typed_infra_and_cleans_up():
    launcher = FakeLauncher("no_ready")
    with pytest.raises(live.LivePredictorFault) as fault:
        _predictor(launcher).start()
    assert fault.value.code == "CRASH" and launcher.stopped == 1

    class Broken(FakeLauncher):
        def start(self, *_args):
            raise OSError("docker unavailable")

    broken = Broken()
    with pytest.raises(live.LivePredictorFault) as fault:
        _predictor(broken).start()
    assert fault.value.code == "START" and broken.stopped == 1


def test_a_model_contract_break_is_not_infra():
    with _predictor(FakeLauncher("contract")) as predictor:
        with pytest.raises(live.LiveModelContractError) as error:
            predictor.predict([[1.0, 2.0, 3.0]])
        assert error.value.code == "arity"
        assert not isinstance(error.value, live.LivePredictorFault)


def test_wall_clocks_are_required_and_rows_are_checked():
    for bad in (None, 0, -1, math.inf):
        with pytest.raises(ValueError):
            live.LivePredictor(
                **_kwargs(),
                call_seconds=bad,
                session_seconds=10,
                launcher=FakeLauncher(),
                per_case=False,
            )
    with _predictor(FakeLauncher()) as predictor:
        for rows in ([], [[1.0, 2.0]], [[math.nan, 0.0, 0.0]]):
            with pytest.raises(ValueError):
                predictor.predict(rows)


# --------------------------------------------------------------------------
# The docker launch: the inference route's exact controls


class RecordingCLI:
    executable = "docker"

    def __init__(self):
        self.calls = []

    def run(self, arguments, *, timeout=30, accepted=(0,)):
        self.calls.append(list(arguments))
        return subprocess.CompletedProcess(arguments, 0, b"", b"")


class FakeProcess:
    def __init__(self, argv, **kwargs):
        self.argv, self.kwargs = argv, kwargs
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


def test_docker_launch_uses_the_inference_routes_exact_isolation(tmp_path, monkeypatch):
    image_id = _sha("7")
    image = WorkerImageIdentity(*(image_id for _ in range(8)))
    seen = {}

    def doctor(**kwargs):
        seen["doctor"] = kwargs
        return docker_runtime.DockerDoctor(True, "ok", {}, "0,1")

    monkeypatch.setattr(docker_runtime, "doctor", doctor)
    monkeypatch.setattr(
        docker_runtime,
        "spawn_watchdog",
        lambda **kwargs: seen.setdefault("watchdog", kwargs),
    )

    def controls(**kwargs):
        seen["controls"] = kwargs
        return "sha256:" + "0" * 64, {}

    monkeypatch.setattr(docker_runtime, "inspect_effective_controls", controls)
    removed = []
    monkeypatch.setattr(
        docker_runtime,
        "remove_exact_container",
        lambda **kwargs: removed.append(kwargs),
    )
    processes = []

    def popen(argv, **kwargs):
        processes.append(FakeProcess(argv, **kwargs))
        return processes[-1]

    cli = RecordingCLI()
    stage_root = tmp_path / "stage"
    stage_root.mkdir()
    launcher = live.DockerLauncher(
        image=image, stage_root=stage_root, cli=cli, popen=popen
    )
    files, view = live.stage_files(**_kwargs())
    launcher.start(files, view, time.time() + 120)

    # The carrier's own worker profile for the inference provenance.
    profile = research_carrier._worker_profile(
        None, "DIRECT_BUNDLE_PUBLIC_INFERENCE", None, None
    )
    create = cli.calls[0]
    assert create == docker_runtime.create_arguments(
        container_name=launcher.container_name,
        image_id=image_id,
        input_directory=launcher.stage,
        cpuset="0,1",
        launch_digest=launcher.launch_digest,
        worker_profile=profile,
    )
    pairs = set(itertools.pairwise(create))
    from carbon.reconstruction.worker.model import PIDS_LIMIT, WORKER_GID, WORKER_UID

    for flag in (
        ("--network", "none"),
        ("--ipc", "private"),
        ("--user", f"{WORKER_UID}:{WORKER_GID}"),
        ("--cap-drop", "ALL"),
        ("--security-opt", "no-new-privileges=true"),
        ("--pids-limit", str(PIDS_LIMIT)),
        ("--memory", str(profile.effective_memory_bytes)),
        ("--memory-swap", str(profile.effective_memory_bytes)),
        ("--cpus", str(profile.effective_cpu_count)),
        ("--restart", "no"),
        ("--env", "JAX_PLATFORMS=cpu"),
    ):
        assert flag in pairs
    assert "--read-only" in create
    assert any(item.startswith("/scratch:rw,nosuid,nodev,noexec") for item in create)
    assert any(
        item.endswith("target=/input,readonly,bind-propagation=rprivate")
        for item in create
    )
    assert "--privileged" not in create and "host" not in create
    assert cli.calls[1] == ["start", launcher.container_name]
    assert seen["controls"]["worker_profile"] == profile
    assert seen["controls"]["diagnose_policy"] is True
    assert seen["watchdog"]["container_name"] == launcher.container_name
    assert seen["doctor"]["image_identity"] is image

    # The carrier's fixed program exec, plus -i for the request stream only.
    argv = processes[0].argv
    assert argv == [
        "docker",
        "exec",
        "-i",
        launcher.container_name,
        "/opt/carbon-worker/bin/python",
        "-I",
        "-c",
        research_carrier.BOOTSTRAP,
    ]
    assert set(processes[0].kwargs["env"]) <= {
        "PATH",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    }
    staged = {path.name for path in launcher.stage.iterdir()}
    assert staged == set(files) | {"program.py"}
    assert (launcher.stage / "program.py").read_text() == live.SERVE_PROGRAM

    launcher.stop()
    assert removed and removed[0]["container_name"] == launcher.container_name
    assert cli.calls[-1][:3] == ["ps", "-aq", "--filter"]
    assert not launcher.stage.parent.exists()


def test_the_worker_inference_route_runs_under_the_same_provenance(monkeypatch):
    """Pin PROVENANCE to what `_infer_state` hands the carrier."""
    captured = {}

    def runner(_ledger, **kwargs):
        captured.update(kwargs)
        raise RuntimeError("captured")

    recipe = _recipe()
    state = _model_state(recipe)
    with pytest.raises(RuntimeError, match="captured"):
        worker._infer_state(
            None,
            owner="o",
            identity="i",
            inference_image=None,
            recipe=recipe,
            binding=_binding(recipe),
            state=state,
            state_digest=worker._digest(state),
            inputs=np.zeros((1, WIDTH), np.float32),
            expected_output_shape=(1, WIDTH),
            allowlist_bytes=ALLOWED.raw,
            runner=runner,
        )
    assert captured["provenance"] == live.PROVENANCE
    assert captured["source"] == worker.INFER_PROGRAM


# --------------------------------------------------------------------------
# The real serving program and graph rebuild in a local process (needs jax),
# compared with the file route's inference program row for row.


class LocalLauncher:
    """TEST ONLY: the fixed serving program in a local process, no isolation."""

    def __init__(self, root):
        self.root = root
        self.process = None

    def start(self, files, view, deadline_unix):
        work = self.root / "workspace"
        work.mkdir(parents=True)
        for name, body in files.items():
            (work / name).write_bytes(body)
        self.process = subprocess.Popen(
            [sys.executable, "-c", live.SERVE_PROGRAM],
            cwd=work,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        )
        return live.PipeChannel(self.process)

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)
        shutil.rmtree(self.root, ignore_errors=True)


def _file_route(tmp_path, kwargs, rows):
    recipe = kwargs["recipe"]
    requested = worker._tensors(inputs=np.asarray(rows, np.float32))
    files, modules = worker._stage_bundle_modules(_binding(recipe), training=False)
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "state.npz": kwargs["state_bytes"],
            "inputs.npz": requested,
            "allowlist.json": ALLOWED.raw,
            "control.json": json.dumps(
                {
                    "recipe_digest": recipe.digest,
                    "binding": _binding(recipe),
                    "codec_modules": modules,
                    "state_digest": kwargs["expected_state_digest"],
                    "inputs_digest": worker._digest(requested),
                    "allowlist_digest": ALLOWED.digest,
                    "expected_output_shape": [len(rows), WIDTH],
                    "expected_output_dtype": "float32",
                }
            ).encode(),
        }
    )
    work = tmp_path / "file-route" / "workspace"
    work.mkdir(parents=True)
    (work.parent / "output").mkdir()
    for name, body in files.items():
        (work / name).write_bytes(body)
    done = subprocess.run(
        [sys.executable, "-c", worker.INFER_PROGRAM],
        cwd=work,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads((work.parent / "output/predictions.json").read_bytes())


@pytest.mark.parametrize("per_case", [False, True])
def test_local_serving_program_matches_the_file_route_row_for_row(tmp_path, per_case):
    pytest.importorskip("jax")
    rng = np.random.default_rng(0)
    rows = rng.uniform(-3, 3, (11, WIDTH)).astype(np.float32).tolist()
    kwargs = _kwargs()
    expected = _file_route(tmp_path, kwargs, rows)
    sessions = []
    for index in range(2):
        with live.LivePredictor(
            **kwargs,
            call_seconds=120,
            session_seconds=600,
            per_case=per_case,
            launcher=LocalLauncher(tmp_path / f"live-{index}"),
        ) as predictor:
            sessions.append(predictor.predict(rows))
            assert predictor.graph_calls == (11 if per_case else math.ceil(11 / BATCH))
    assert sessions[0] == sessions[1]  # bit-identical across two sessions
    assert sessions[0] == expected  # == the file route's JSON, row for row


def test_local_serving_program_times_one_3000_call_de_search(tmp_path):
    pytest.importorskip("jax")
    from carbon.scoring import pool_model_search as search
    from carbon.scoring import pool_solver_reference as psr

    kwargs = _kwargs()
    with live.LivePredictor(
        **kwargs,
        call_seconds=120,
        session_seconds=600,
        launcher=LocalLauncher(tmp_path / "live"),
        per_case=False,
    ) as predictor:
        evaluator = search.model_evaluator(
            predictor.predict,
            input_names=("a", "b", "c"),
            design_names=("b", "c"),
            derive=lambda _inputs, out: (
                None if out is None else {"y": out[0] + out[1] + out[2]}
            ),
        )
        problem = psr.Problem(
            target_id="fixture",
            fixed={"a": 0.5},
            outputs=("y",),
            objective="y",
            sense="min",
            limits=(),
            u={"y": 0.001},
            box=((-2.0, 2.0), (-2.0, 2.0)),
            start=(0.5, 0.5),
            seed=0,
        )
        started = time.monotonic()
        result = search.model_search_de(
            problem, evaluator, host_class="custody2", budget=3000
        )
        seconds = time.monotonic() - started
        counts = predictor.counts()
    print(f"\nlive predictor 3000-call DE search: {seconds:.2f} s, {counts}")
    # every model call the search made reached the container, within the budget; de_polish_v1 leaves unused
    # calls unused (no limits = no polish; compass stops below step 1e-4), so the count is not ~3000
    assert counts["rows"] == result.counts["model_calls"] <= 3000
    assert result.pick is not None


# --------------------------------------------------------------------------
# A real isolated container: skipped unless docker and the pinned image exist.


def test_docker_live_predictor_matches_infer_saved_bundle():
    if shutil.which("docker") is None or not os.environ.get(
        "CARBON_LIVE_PREDICTOR_IMAGE"
    ):
        pytest.skip("docker or the pinned inference worker image is not available")
    pytest.skip(
        "real-container comparison needs the installed C-03 worker image record "
        "and a ledger; run on the validator host"
    )
