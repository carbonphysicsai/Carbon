"""FAILED_INFRA failure classes (owner P0, 20 Nov 2026: "better failure labels and explanations"): every retained
diagnosis maps to one closed class with one fixed plain-English line; a recipe-side class is never re-run
automatically, an unclassified one once; Carbon's classes keep owner D16's caps. Tails are the live 116 shapes.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import lean_recipe
from carbon.development_session import infra_diagnosis as d

SSH = (
    "exit=1\nstdout:\n\nstderr:\ncommand [ssh -l carbon-grade -o ConnectTimeout=30 -T -- 10.0.0.1 docker system "
    "dial-stdio] has exited"
)


def _record(stage, reason, tail, place=""):
    return {
        "failed_stage": stage,
        "reason_code": reason,
        "tail": tail,
        "raised_at": place,
    }


RUNTIME = "reconstruction.worker.runtime.failed"
UNAVAILABLE = "reconstruction.worker.infrastructure.unavailable"


@pytest.mark.parametrize(
    "record,expected",
    [
        (
            _record(
                "build",
                RUNTIME,
                "stream command timed out",
                "docker_runtime.py:441:stream_to_file",
            ),
            "carbon_build_wall_busy_host",
        ),
        (
            _record(
                "inference",
                RUNTIME,
                "stream command timed out",
                "docker_runtime.py:441:stream_to_file",
            ),
            "carbon_inference_wall_busy_host",
        ),
        (
            _record("build", RUNTIME, SSH, "docker_runtime.py:383:run"),
            "carbon_box_link_lost",
        ),
        (
            _record("build", RUNTIME, SSH, "docker_runtime.py:471:stream_to_file"),
            "carbon_box_link_lost",
        ),
        (
            _record(
                "build",
                UNAVAILABLE,
                "BrokenPipeError(32, 'Broken pipe')",
                "remote_gpu_build.py:2102:_box_run",
            ),
            "carbon_box_link_lost",
        ),
        (
            _record(
                "build",
                RUNTIME,
                "exit=143\nstdout:\n\nstderr:\n",
                "docker_runtime.py:383:run",
            ),
            "carbon_worker_killed",
        ),
        (
            _record(
                "build",
                UNAVAILABLE,
                "bounded command timed out",
                "docker_runtime.py:246:_bounded_capture",
            ),
            "carbon_docker_command_timeout",
        ),
        (
            _record(
                "orchestration",
                UNAVAILABLE,
                "remote_gpu_build_no_box",
                "remote_gpu_build.py:1396:_take",
            ),
            "carbon_box_unavailable",
        ),
        (
            _record(
                "orchestration",
                "custody_or_state_invalid",
                "RecipeRefused: construction_total_deadline_reached",
                "direct_graph_construction_worker.py:1300:phase_seconds",
            ),
            "carbon_construction_deadline",
        ),
        (
            _record(
                "dependency_check",
                "dependency_unavailable",
                "ValueError: admitted direct library image",
            ),
            "carbon_dependency_unavailable",
        ),
        (_record("restart_reconcile", "worker_lost", ""), "carbon_restart_lost"),
        (
            _record(
                "orchestration",
                "custody_or_state_invalid",
                "ValueError: one numerical worker; reconcile",
            ),
            "carbon_state_conflict",
        ),
        (
            _record(
                "build",
                "reconstruction.worker.cleanup.uncertain",
                "WorkerFailure: Development reconstruction",
            ),
            "carbon_cleanup_uncertain",
        ),
        (
            _record(
                "build",
                RUNTIME,
                "exit=1\nstderr:\nTraceback (most recent call last):\nValueError: bad shape",
                "docker_runtime.py:441:stream_to_file",
            ),
            "recipe_program_exited",
        ),
        (
            _record(
                "orchestration", "graph_decision", "carbon_graph_adapter_unavailable"
            ),
            d.UNCLASSIFIED,
        ),
        (None, d.UNCLASSIFIED),
        ("not a record", d.UNCLASSIFIED),
    ],
)
def test_every_live_shape_maps_to_one_closed_class(record, expected):
    assert d.classify(record) == expected
    assert d.classify(record) in d.CLASSES


def test_every_class_has_one_fixed_line_and_a_retry_rule():
    assert set(d.EXPLANATIONS) == d.CLASSES == set(d.RETRIES)
    assert not d.CARBON_CLASSES & d.RECIPE_CLASSES
    for name in d.CLASSES:
        line = d.EXPLANATIONS[name]
        assert type(line) is str and 20 < len(line) < 300 and "\n" not in line
    assert all(d.RETRIES[name] == 0 for name in d.RECIPE_CLASSES)
    assert d.RETRIES[d.UNCLASSIFIED] == 1
    assert all(d.RETRIES[name] is None for name in d.CARBON_CLASSES)


def test_a_class_never_carries_the_private_tail():
    secret = "stream command timed out SECRET-PATH /home/carbon/rs116c"
    name = d.classify(_record("build", RUNTIME, secret))
    assert "SECRET" not in name and "SECRET" not in d.EXPLANATIONS[name]


@pytest.mark.parametrize(
    "failure_class,same,expected",
    [
        (None, 9, None),  # no diagnosis: D16's caps as before
        ("carbon_build_wall_busy_host", 2, None),  # Carbon's: D16's caps decide
        (d.UNCLASSIFIED, 0, None),
        (d.UNCLASSIFIED, 1, "class_cap_spent"),  # once only
        ("recipe_program_exited", 0, "recipe_side"),  # never re-run
    ],
)
def test_the_retry_rule_by_class(failure_class, same, expected):
    assert lean_recipe._class_refusal(failure_class, same) == expected


def test_the_class_is_read_from_the_retained_diagnosis_and_unreadable_is_none():
    record = _record("build", RUNTIME, "stream command timed out")
    provider = SimpleNamespace(private_infra_diagnosis=lambda task_id: record)
    assert lean_recipe._failure_class(provider, "t") == "carbon_build_wall_busy_host"
    assert (
        lean_recipe._failure_class(
            SimpleNamespace(private_infra_diagnosis=lambda t: None), "t"
        )
        is None
    )

    def broken(task_id):
        raise ValueError("retained infrastructure diagnosis custody differs")

    assert (
        lean_recipe._failure_class(SimpleNamespace(private_infra_diagnosis=broken), "t")
        is None
    )
    assert lean_recipe._failure_class(SimpleNamespace(), "t") is None
