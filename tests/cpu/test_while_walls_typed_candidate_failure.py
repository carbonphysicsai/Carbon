"""A graph `while` that never ends is the candidate's failure at both walls (Validator
ruling 2(b), GRAPH_LIMITS_AUDIT row 2).

`while` is implemented (`interpret._while`) but refused by every served allowlist until
both walls end a never-ending loop as a typed candidate failure, never FAILED_INFRA.

* BUILD wall and the task's own INFERENCE wall: a real never-ending `lax.while_loop`,
  run through the real interpreter in a stub `docker` process under the real
  `DockerCLI.stream_to_file` wall and the real carrier, ends as `MinerProgramFailure`
  (`DEADLINE`, `WORKER_WALL_LIMIT_REACHED`), the operation settled FAILED_MINER.
* The official grade's inference pair (Validator ruling, TEAM_BOARD 2026-11-01 22:10): a
  candidate wall hit is retried once; a second is the typed candidate failure
  WORKER_WALL_LIMIT_REACHED: not scored, the exam slot COUNTED, never FAILED_INFRA. A host
  or infrastructure fault stays `inference_pair_incomplete`, FAILED_INFRA, released.

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
from test_exam_cap import EXAM, HOTKEY, MOTOR, Clock, _count, _reserve, make_cap
from test_fixed_practice_failure_diagnostics import harness as _runner_harness

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker.docker_runtime import DockerCLI
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

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


def _wall():
    return carrier.MinerProgramFailure(
        {
            "schema": carrier.MINER_FAILURE_SCHEMA,
            "failure_code": WorkerCode.DEADLINE.value,
            "observation": carrier.CANDIDATE_WALL_LIMIT,
        }
    )


def _pair_failure(cause):
    from carbon.development_session.paired_inference import InferencePairFailure

    return InferencePairFailure("primary", {}, {}, cause)


def _pair(tmp_path, monkeypatch, behaviours):
    """`_inference_pair_raw` over a fake `infer_frozen_pair` that plays `behaviours` in
    order (an exception is raised, anything else is returned as the pair's evidence)."""
    import numpy as np
    from test_lean_recipe_retention import _tensors

    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.development_session import construction_recipe, paired_inference

    calls = []
    plays = list(behaviours)

    def fake_pair(ledger, **call):
        calls.append(call["identity"])
        play = plays.pop(0)
        if isinstance(play, Exception):
            raise play
        return SimpleNamespace(evidence=play)

    monkeypatch.setattr(paired_inference, "infer_frozen_pair", fake_pair)
    monkeypatch.setattr(
        construction_recipe.ConstructionRecipe, "from_dict", staticmethod(lambda d: d)
    )
    monkeypatch.setattr(
        retention, "_private_evaluation_directory", lambda result, sid: tmp_path
    )
    snapshot = SimpleNamespace(
        manifest_digest="sha256:" + "a" * 64,
        read_json_role=lambda root, side, role, max_bytes: {},
    )
    kit = {
        "id": "c",
        "version": "1",
        "train_digest": "t",
        "interface_digest": "i",
        "construction_limits_digest": "l",
    }
    material = {
        "construction_kit": kit,
        "construction_limits_document": {
            "reconstruction_resource_policy": {
                "inference_wall_seconds_max": 60,
                "total_reconstruction_wall_seconds_max": 120,
            }
        },
        "interface_document": {"dtype": "<f8"},
        "practice_inputs": np.zeros((2, 1)),
        "expected_output_shape": (2, 1),
        "allowlist_bytes": b"",
    }
    provider = SimpleNamespace(
        ledger=object(),
        inference_image=object(),
        _requests={"rtsk_x": SimpleNamespace(recipe={})},
    )
    adapter = SimpleNamespace(
        owner=lambda sid: "owner",
        _provider=lambda owner: provider,
        discovery=SimpleNamespace(
            _material=material,
            evaluation_pack_snapshot=snapshot,
            evaluation_pack_public_root=tmp_path,
        ),
    )

    def run():
        return retention._inference_pair_raw(
            adapter,
            "rtsk_x",
            {},
            {
                "state.npz": b"s",
                "inputs.npz": _tensors(inputs=material["practice_inputs"]),
            },
            {"state_digest": "sd"},
        )

    return run, calls


def test_one_wall_hit_in_the_official_pair_is_retried_and_grades_normally(
    tmp_path, monkeypatch
):
    run, calls = _pair(
        tmp_path, monkeypatch, [_pair_failure(_wall()), {"fixture": True}]
    )
    assert json.loads(run()) == {"fixture": True}
    # The retry runs under fresh identities, never a replay.
    assert len(calls) == 2 and calls[0] != calls[1]


def test_two_wall_hits_are_the_candidates_typed_failure_not_infrastructure(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import lean_recipe_retention as retention

    run, calls = _pair(
        tmp_path, monkeypatch, [_pair_failure(_wall()), _pair_failure(_wall())]
    )
    with pytest.raises(retention.CandidateWallLimitReached) as caught:
        run()
    assert str(caught.value) == "WORKER_WALL_LIMIT_REACHED"
    assert len(calls) == 2


def _memory_stop():
    return carrier.MinerProgramFailure(
        {
            "schema": carrier.MINER_FAILURE_SCHEMA,
            "failure_code": WorkerCode.RUNTIME.value,
            "observation": carrier.CANDIDATE_MEMORY_LIMIT,
        }
    )


@pytest.mark.parametrize(
    "plays",
    [
        # A host or infrastructure fault is Carbon's, exactly as before.
        lambda: [_pair_failure(WorkerFailure(WorkerCode.UNAVAILABLE))],
        lambda: [_pair_failure(RuntimeError("daemon"))],
        # A wall hit, then a host fault on the retry, is still Carbon's.
        lambda: [_pair_failure(_wall()), _pair_failure(RuntimeError("daemon"))],
        # Only the wall changes: a memory stop keeps its meaning.
        lambda: [_pair_failure(_memory_stop())],
    ],
)
def test_a_host_fault_in_the_pair_stays_inference_pair_incomplete(
    tmp_path, monkeypatch, plays
):
    from carbon.challenge_validator import lean_recipe_retention as retention

    run, _calls = _pair(tmp_path, monkeypatch, plays())
    with pytest.raises(retention.RetentionUnavailable) as caught:
        run()
    assert not isinstance(caught.value, retention.CandidateWallLimitReached)
    assert str(caught.value) == "inference_pair_incomplete"


def test_a_candidate_wall_failure_counts_the_slot_and_is_never_given_back(tmp_path):
    cap = make_cap(tmp_path, Clock())
    from carbon.challenge_validator import lean_recipe_retention as retention

    slot = _reserve(cap, 0)
    result = retention._settle_candidate_wall_hit(cap, slot, {"entry_id": "e"})
    assert result == {
        "entry_id": "e",
        "private_evaluation_state": "CANDIDATE_FAILED",
        "private_evaluation_reason": "WORKER_WALL_LIMIT_REACHED",
    }
    assert _count(cap) == 1
    row = {
        "hotkey": HOTKEY,
        "challenge_id": MOTOR[0],
        "challenge_version": MOTOR[1],
        "exam_key": EXAM,
        "submission_id": "rtsk_0",
    }
    # Nothing can hand a counted row back as infrastructure.
    assert cap.give_back_on_infra(**row) == "COUNTED"
    assert not cap.released_on_infra(**row)


def _grader(tmp_path, behaviour):
    from test_auto_grade import A, FakeIntake

    from carbon.challenge_validator import auto_grade
    from carbon.challenge_validator.ledger import AttemptLedger

    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    hotkey = "5" + "1" * 47
    exam_key = "sha256:" + "e" * 64

    class Ledger:
        _db = staticmethod(ledger._db)

        @staticmethod
        def submitted_outcomes(contract):
            return (A,)

    adapter = SimpleNamespace(
        challenge_id="electric-motor-magnetics",
        challenge_version="1.3",
        contract_digest="sha256:" + "0" * 64,
        ledger=Ledger,
        owner=lambda submission_id: hotkey,
        _provider=lambda owner: SimpleNamespace(evaluation_pack_digest=exam_key),
    )
    intake = FakeIntake([A], {A: behaviour})
    intake.adapter = adapter
    return auto_grade.AutoGrader(intake, tmp_path), ledger, hotkey, exam_key, A


def test_the_marker_and_the_miner_state_name_the_candidate_failure(tmp_path):
    from carbon.challenge_validator import direct_intake
    from carbon.challenge_validator.exam_cap import ExamCap

    grader, ledger, hotkey, exam_key, A = _grader(
        tmp_path,
        {
            "entry_id": "e1",
            "private_evaluation_state": "CANDIDATE_FAILED",
            "private_evaluation_reason": "WORKER_WALL_LIMIT_REACHED",
        },
    )
    assert grader.run_once() == (A, "CANDIDATE_FAILED")
    marker = grader.marker(A)
    assert marker["state"] == "CANDIDATE_FAILED"
    assert marker["code"] == "WORKER_WALL_LIMIT_REACHED"
    # Not a FAILED marker: no infrastructure failure is counted or summarised.
    from carbon.challenge_validator import auto_grade

    assert auto_grade.failure_summary(tmp_path) == {
        "auto_grade_failed": 0,
        "auto_grade_last_failure": None,
    }
    assert not ExamCap(ledger).released_on_infra(
        hotkey=hotkey,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.3",
        exam_key=exam_key,
        submission_id=A,
    )
    assert (
        "CANDIDATE_FAILED" in direct_intake.GRADE_STATES_V3
    )  # a v3 reply only (Validator 22:40)
    assert "CANDIDATE_FAILED" not in direct_intake.GRADE_STATES
    state = direct_intake.DirectRecipeIntake._grade_state(
        SimpleNamespace(grade_marker=lambda sid: marker), hotkey, A
    )
    assert state == "CANDIDATE_FAILED"


def test_a_host_fault_is_still_failed_infra_and_released(tmp_path):
    from carbon.challenge_validator.exam_cap import ExamCap
    from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

    grader, ledger, hotkey, exam_key, A = _grader(
        tmp_path, RetentionUnavailable("inference_pair_incomplete")
    )
    assert grader.run_once() == (A, "FAILED")
    assert grader.marker(A)["state"] == "FAILED"
    assert ExamCap(ledger).released_on_infra(
        hotkey=hotkey,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.3",
        exam_key=exam_key,
        submission_id=A,
    )
