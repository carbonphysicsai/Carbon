"""A graph `while` that never ends is the candidate's failure at both walls (Validator
ruling 2(b), GRAPH_LIMITS_AUDIT row 2).

`while` is implemented (`interpret._while`) but refused by every served allowlist until
both walls end a never-ending loop as a typed candidate failure, never FAILED_INFRA.

* BUILD wall and the task's own INFERENCE wall: a real never-ending `lax.while_loop`,
  run through the real interpreter in a stub `docker` process under the real
  `DockerCLI.stream_to_file` wall and the real carrier, ends as `MinerProgramFailure`
  (`DEADLINE`, `WORKER_WALL_LIMIT_REACHED`), the operation settled FAILED_MINER.
* The official grade's inference pair: a wall hit there is wrapped as
  `RetentionUnavailable("inference_pair_incomplete")` and given back as FAILED_INFRA.
  That is the open hole; the strict xfail below states the required behaviour and waits
  for the Validator's ruling on what the official grade of a candidate wall-hit is.

No allowlist is changed here: the admitted allowlist exists only inside the test.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_candidate_resource_failure import (
    GRAPH_BUILD,
    GRAPH_INFERENCE,
    _observation,
    _observe,
    _state,
)
from test_fixed_practice_failure_diagnostics import harness as _runner_harness

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker.docker_runtime import DockerCLI
from carbon.reconstruction.worker.model import WorkerCode

harness = _runner_harness  # pytest discovers the existing fixture by this name

posix = pytest.mark.skipif(os.name != "posix", reason="a stub executable needs POSIX")

ROOT = Path(__file__).resolve().parents[2]

#: Runs inside the stub "docker": rebuilds the never-ending graph with the real
#: interpreter and runs it. The marker proves the loop was entered; it is rewritten with
#: the process id so the test can show the wall really ended that process.
STUB = """#!{python}
import os, sys
os.environ.setdefault("JAX_PLATFORMS", "cpu")
sys.path.insert(0, {root!r})
import jax
import numpy as np
from carbon.level4 import allowlist, graph, interpret

admitted = allowlist.Allowlist(open({allowlist!r}, "rb").read())
doc = graph.parse(open({document!r}, "rb").read(), max_bytes=allowlist.CAPS["document_bytes"])
run = interpret.rebuild(doc, admitted)
x = np.full((3, 4), 2.0, dtype=np.float32)
open({marker!r}, "w").write(str(os.getpid()))
jax.jit(lambda a: run(a)[0])(x).block_until_ready()
"""


def _never_ending_graph():
    """`while c[0, 0] >= 0: c = c * 1.5 + 0.5` from a positive start: it grows and the
    condition holds forever. Returns the document bytes and the allowlist bytes that
    admit `while` (a test-only copy of v8; the served one still refuses it)."""
    import jax
    import jax.numpy as jnp
    from jax import lax

    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import graph
    from carbon.level4.tooling import lower_jax

    v8 = Path(allowlist_module.__file__).with_name("allowlist_v8.json")
    raw = json.loads(v8.read_bytes())
    assert raw["carbon_ops"]["while"]["default"] == "refuse"
    raw["carbon_ops"]["while"]["default"] = "allow"
    admitted_bytes = json.dumps(raw).encode()
    admitted = allowlist_module.Allowlist(admitted_bytes)

    def forever(x):
        return lax.while_loop(lambda c: c[0, 0] >= 0.0, lambda c: c * 1.5 + 0.5, x)

    closed = lower_jax.trace(forever, jax.ShapeDtypeStruct((3, 4), jnp.float32))
    document = lower_jax.lower(
        closed, role="forward", allowlist=admitted, input_names=["x"]
    )
    return graph.dumps(document), admitted_bytes


@pytest.fixture
def stub_docker(tmp_path):
    document, admitted = _never_ending_graph()
    (tmp_path / "graph.json").write_bytes(document)
    (tmp_path / "allowlist.json").write_bytes(admitted)
    marker = tmp_path / "entered-the-loop"
    stub = tmp_path / "docker"
    stub.write_text(
        STUB.format(
            python=sys.executable,
            root=str(ROOT),
            allowlist=str(tmp_path / "allowlist.json"),
            document=str(tmp_path / "graph.json"),
            marker=str(marker),
        )
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return SimpleNamespace(path=stub, marker=marker)


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_the_served_allowlist_still_refuses_while():
    """This ticket changes no allowlist: `while` stays refused where it is served."""
    from carbon.level4 import allowlist as allowlist_module

    v8 = Path(allowlist_module.__file__).with_name("allowlist_v8.json")
    assert json.loads(v8.read_bytes())["carbon_ops"]["while"]["default"] == "refuse"


@posix
@pytest.mark.parametrize("provenance", [GRAPH_BUILD, GRAPH_INFERENCE])
def test_a_never_ending_while_hits_the_wall_as_a_typed_candidate_failure(
    harness, monkeypatch, stub_docker, provenance
):
    _observe(monkeypatch, _observation())

    class WallCLI:
        """The harness's fake Docker, except the program stage: that is the real
        `DockerCLI.stream_to_file` (its own clock, its own kill) over the stub."""

        def __init__(self):
            self.real = DockerCLI.__new__(DockerCLI)
            self.real.executable = str(stub_docker.path)

        def run(self, arguments, **kwargs):
            return SimpleNamespace(stdout=b"")

        def stream_to_file(self, arguments, destination, **kwargs):
            if destination.name == "stdout.txt":
                return self.real.stream_to_file(arguments, destination, **kwargs)
            destination.write_bytes(b"fixture-stream")
            return len(b"fixture-stream")

    monkeypatch.setattr(carrier, "DockerCLI", WallCLI)
    # 56 s leaves the program stage an allowance of about 11 s (56 - 45).
    with pytest.raises(carrier.MinerProgramFailure) as caught:
        harness.run(provenance=provenance, seconds=56)
    # The loop really started, and the wall really ended it.
    assert stub_docker.marker.exists()
    assert not _alive(int(stub_docker.marker.read_text()))
    assert caught.value.code is WorkerCode.DEADLINE
    result = caught.value.result
    assert result["observation"] == carrier.CANDIDATE_WALL_LIMIT
    assert result["state"] == "FAILED_MINER"
    assert result["limit"]["kind"] == "wall"
    assert result["retry_dispatched"] is False
    assert _state(harness) == "FAILED_MINER"
    assert "CLEANUP" in harness.events


def test_a_wall_hit_task_is_refused_as_the_candidates_not_infrastructure():
    """Task level, graph route included: `MinerProgramFailure` out of the build or the
    inference child is REFUSED `candidate_program_failed` (research_tasks), proven for
    the wall code by test_candidate_resource_failure.py::
    test_the_task_refuses_a_candidate_resource_failure_not_infrastructure. Here: the
    graph route's child classes are exactly the candidate-resource set."""
    assert {GRAPH_BUILD, GRAPH_INFERENCE} <= carrier._CANDIDATE_RESOURCE_PROVENANCES


@pytest.mark.xfail(
    strict=True,
    reason=(
        "OPEN, Validator decision: the official grade's inference pair turns a "
        "candidate wall hit (MinerProgramFailure) into RetentionUnavailable("
        "'inference_pair_incomplete'), which AutoGrader gives back as FAILED_INFRA "
        "(exam row RELEASED, free retry). Ruling 2(b) forbids that for `while`."
    ),
)
def test_the_official_grade_does_not_give_a_candidate_wall_hit_back_as_infrastructure(
    tmp_path,
):
    from test_auto_grade import A, FakeIntake

    from carbon.challenge_validator import auto_grade
    from carbon.challenge_validator.exam_cap import ExamCap
    from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable
    from carbon.challenge_validator.ledger import AttemptLedger
    from carbon.development_session.paired_inference import InferencePairFailure

    wall = carrier.MinerProgramFailure(
        {
            "schema": carrier.MINER_FAILURE_SCHEMA,
            "failure_code": WorkerCode.DEADLINE.value,
            "observation": carrier.CANDIDATE_WALL_LIMIT,
        }
    )
    unavailable = RetentionUnavailable("inference_pair_incomplete")
    unavailable.__cause__ = InferencePairFailure("primary", {}, {}, wall)

    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    hotkey = "5" + "1" * 47
    challenge, exam_key = "electric-motor-magnetics", "sha256:" + "e" * 64

    class Ledger:
        _db = staticmethod(ledger._db)

        @staticmethod
        def submitted_outcomes(contract):
            return (A,)

    adapter = SimpleNamespace(
        challenge_id=challenge,
        challenge_version="1.3",
        contract_digest="sha256:" + "0" * 64,
        ledger=Ledger,
        owner=lambda submission_id: hotkey,
        _provider=lambda owner: SimpleNamespace(evaluation_pack_digest=exam_key),
    )
    intake = FakeIntake([A], {A: unavailable})
    intake.adapter = adapter
    auto_grade.AutoGrader(intake, tmp_path).run_once()
    assert not ExamCap(ledger).released_on_infra(
        hotkey=hotkey,
        challenge_id=challenge,
        challenge_version="1.3",
        exam_key=exam_key,
        submission_id=A,
    )
