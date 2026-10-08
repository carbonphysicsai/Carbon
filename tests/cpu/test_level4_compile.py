"""Level 4 G5, compile in isolation (development only): `carbon.level4.compile`.

The C-03 lane needs Docker; here a stand-in runner with the lane's signature
runs Carbon's lane program in an isolated (`python -I`) subprocess on the
staged bytes only, as `test_graphite_carrier_lane.py` does.

Claims tested:

1. The lane program, given only staged module and document bytes, rebuilds
   and compiles the forward graph, a gradient step and the init graph, and
   reports the measurements.
2. Every staged name is a flat workspace name; documents are staged as
   canonical bytes and parsed again inside.
3. Lane outcomes are typed: deadline is `compile_deadline`, a program failure
   is `compile_failed` (both the submission's), any other lane failure is
   FAILED_INFRA (`CompileInfraFailure`). An unset deadline blocks.
4. The profile is recorded as awaiting the security owner (D3).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.development_session.research_workspace import is_workspace_name
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import compile as g5
from carbon.level4 import graph, submission, tooling
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

MAX_BYTES = 1 << 26  # the tests' parser bound; not a G3 limit
DEADLINE = 120  # a test fixture inside the lane's own range; NOT a G5 value


class StandIn:
    """The lane's `_run` signature; runs the program locally in isolation."""

    def __init__(self, fail=None):
        self.fail, self.calls = fail, []

    def __call__(
        self,
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
    ):
        self.calls.append(
            {"provenance": provenance, "seconds": seconds, "files": sorted(files)}
        )
        if self.fail is not None:
            raise self.fail
        operation = Path(ledger.root) / "operation-test"
        snapshot = operation / "snapshot"
        snapshot.mkdir(parents=True)
        with tempfile.TemporaryDirectory() as directory:
            work, output = Path(directory) / "work", Path(directory) / "output"
            work.mkdir()
            output.mkdir()
            for name, body in files.items():
                (work / name).write_bytes(body)
            try:
                run = subprocess.run(
                    [sys.executable, "-I", "-c", source],
                    cwd=work,
                    capture_output=True,
                    timeout=seconds,
                    check=False,
                    env={"JAX_PLATFORMS": "cpu", "PATH": "/usr/bin:/bin"},
                )
            except subprocess.TimeoutExpired:
                raise WorkerFailure(WorkerCode.DEADLINE) from None
            if run.returncode:
                raise WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=run.stderr)
            for path in output.iterdir():
                (snapshot / path.name).write_bytes(path.read_bytes())
        return {"operation": operation.name}


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


@pytest.fixture(scope="module")
def parsed(allowlist):
    import jax
    import jax.numpy as jnp

    def init(key):
        return [jax.random.normal(key, (3, 8)) * 0.5, jnp.zeros(8)]

    def forward(w, b, x):
        return jax.nn.softplus(x @ w + b)

    _, fwd, _ = tooling.through_bprime(
        forward,
        (jnp.ones((3, 8)), jnp.zeros(8), jnp.ones((4, 3))),
        role="forward",
        allowlist=allowlist,
        input_names=["params/0", "params/1", "inputs/x"],
        max_bytes=MAX_BYTES,
    )
    _, ini, _ = tooling.through_bprime(
        init,
        (jax.random.PRNGKey(0),),
        role="init",
        allowlist=allowlist,
        input_names=["carbon/key"],
        max_bytes=MAX_BYTES,
    )
    manifest, files = submission.build(
        challenge="example",
        interface="sha256:" + "1" * 64,
        allowlist=allowlist,
        forward=fwd,
        init=ini,
    )
    return submission.verify(
        submission.canonical(manifest),
        files,
        allowlist=allowlist,
        challenge="example",
        interface="sha256:" + "1" * 64,
        max_bytes=MAX_BYTES,
    )[1]


def _compile(parsed, allowlist, tmp_path, runner, deadline=DEADLINE):
    return g5.compile_in_isolation(
        parsed,
        allowlist,
        ledger=SimpleNamespace(root=tmp_path),
        owner="test",
        image="test-image",
        deadline_seconds=deadline,
        max_bytes=MAX_BYTES,
        runner=runner,
    )


def test_lane_program_compiles_from_staged_bytes(parsed, allowlist, tmp_path):
    runner = StandIn()
    result = _compile(parsed, allowlist, tmp_path, runner)
    for key in ("forward_seconds", "train_step_seconds", "init_seconds"):
        assert result[key] >= 0
    assert result["forward_flops"] > 0
    assert result["profile"] == g5.PROFILE_STATUS
    call = runner.calls[0]
    assert call["provenance"] == g5.PROVENANCE and call["seconds"] == DEADLINE
    assert all(is_workspace_name(name) for name in call["files"])
    staged = g5.staged_files(parsed, allowlist, max_bytes=MAX_BYTES)
    assert staged["forward.json"] == graph.dumps(parsed["forward"])


def test_unset_deadline_blocks(parsed, allowlist, tmp_path):
    with pytest.raises(g5.CompileBlocked):
        _compile(
            parsed,
            allowlist,
            tmp_path,
            StandIn(),
            deadline=allowlist_module.HUMAN_INPUT,
        )


@pytest.mark.parametrize(
    ("failure", "outcome"),
    [
        (WorkerFailure(WorkerCode.DEADLINE), "compile_deadline"),
        (WorkerFailure(WorkerCode.RUNTIME), "compile_failed"),
        (WorkerFailure(WorkerCode.UNAVAILABLE), g5.CompileInfraFailure),
        (WorkerFailure(WorkerCode.STAGING), g5.CompileInfraFailure),
        (RuntimeError("docker is not running"), g5.CompileInfraFailure),
    ],
)
def test_lane_outcomes_are_typed(parsed, allowlist, tmp_path, failure, outcome):
    if isinstance(outcome, str):
        with pytest.raises(graph.GraphRefused) as refused:
            _compile(parsed, allowlist, tmp_path, StandIn(fail=failure))
        assert refused.value.code == outcome
    else:
        with pytest.raises(outcome) as caught:
            _compile(parsed, allowlist, tmp_path, StandIn(fail=failure))
        assert caught.value.kind == g5.FAILED_INFRA


def test_missing_record_is_infra(parsed, allowlist, tmp_path):
    def silent(ledger, **_):
        (Path(ledger.root) / "operation-empty" / "snapshot").mkdir(parents=True)
        return {"operation": "operation-empty"}

    with pytest.raises(g5.CompileInfraFailure):
        _compile(parsed, allowlist, tmp_path, silent)
