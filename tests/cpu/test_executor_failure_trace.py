"""A research task that ends as an infrastructure failure leaves a private trace.

Graphite's Cooling run on the launch candidate: after one scored practice the
agent's later practice requests ended FAILED_INFRA with no operation folder and
no record of where they stopped. The durable provider now writes, per such
failure, one private line: the task, the exception's class and its last frames.
Never the exception's message or arguments.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

from carbon.research import durable
from carbon.research.model import InfrastructureFailureClass


class Boom(Exception):
    pass


def _fail():
    raise Boom("PRIVATE_VALUE the trace must not keep")


class Executor:
    def __init__(self, fail=True, typed=None):
        self.fail, self.typed = fail, typed

    def execute(self, attempt):
        if self.fail:
            _fail()
        return "outcome"

    def refusal_outcome(self, attempt, error):
        return self.typed


def _attempt(task="task-1"):
    return SimpleNamespace(task_id=SimpleNamespace(value=task))


def test_an_executor_exception_leaves_a_class_and_frames_and_no_message(tmp_path):
    reply = durable._NoRetry(Executor(), tmp_path).execute(_attempt())
    assert reply.failure_class is InfrastructureFailureClass.INTERNAL
    (line,) = (tmp_path / durable.EXECUTOR_FAILURES).read_text().splitlines()
    record = json.loads(line)
    assert record["task"] == "task-1"
    assert record["exception_class"].endswith("Boom")
    assert any(frame.endswith(":_fail") for frame in record["frames"])
    assert all(frame.count(":") == 2 for frame in record["frames"])
    assert "PRIVATE_VALUE" not in line
    assert oct(os.stat(tmp_path / durable.EXECUTOR_FAILURES).st_mode & 0o777) == "0o600"


def test_each_failure_adds_a_line(tmp_path):
    guard = durable._NoRetry(Executor(), tmp_path)
    guard.execute(_attempt("a"))
    guard.execute(_attempt("b"))
    lines = (tmp_path / durable.EXECUTOR_FAILURES).read_text().splitlines()
    assert [json.loads(line)["task"] for line in lines] == ["a", "b"]


def test_a_success_or_a_typed_refusal_leaves_no_trace(tmp_path):
    assert durable._NoRetry(Executor(fail=False), tmp_path).execute(_attempt()) == (
        "outcome"
    )
    typed = durable._NoRetry(Executor(typed="typed outcome"), tmp_path).execute(
        _attempt()
    )
    assert typed == "typed outcome"
    assert not (tmp_path / durable.EXECUTOR_FAILURES).exists()


def test_an_unwritable_root_never_changes_the_outcome(tmp_path):
    reply = durable._NoRetry(Executor(), tmp_path / "missing" / "dir").execute(
        _attempt()
    )
    assert reply.failure_class is InfrastructureFailureClass.INTERNAL


def test_without_a_root_nothing_is_written(tmp_path):
    durable._NoRetry(Executor()).execute(_attempt())
    assert not list(tmp_path.iterdir())
