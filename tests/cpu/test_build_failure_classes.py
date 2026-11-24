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
            d.UNCLASSIFIED,
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


def test_every_class_has_one_fixed_carbon_side_row_and_a_retry_rule():
    assert set(d.EXPLANATIONS) == set(d.FAILURE_TABLE) == d.CLASSES == set(d.RETRIES)
    assert (
        d.RECIPE_CLASSES == frozenset()
    )  # recipe-side needs a structured detector (V2 FAILURE_LABELS ruling)
    for name in d.CLASSES:
        row = d.public_row(name)
        assert tuple(row) == d.PUBLIC_ROW_KEYS
        assert (
            row["code"] == name and row["side"] == "carbon" and row["charged"] is False
        )
        for key in ("what_happened", "next_step", "retried_or_owed"):
            assert (
                type(row[key]) is str
                and 10 < len(row[key]) < 300
                and chr(10) not in row[key]
            )
    # owner G-LEAD-10: a proven Carbon-side class is rebuilt once; an unknown one never (the miner resubmits)
    assert d.RETRIES[d.UNCLASSIFIED] == 0
    assert all(d.RETRIES[name] == 1 for name in d.CARBON_CLASSES)
    assert d.public_row(d.UNCLASSIFIED)["next_step"].startswith("Resubmit")
    assert d.public_row("carbon_build_wall_busy_host")["next_step"].startswith(
        "Nothing to do"
    )
    assert d.public_row("not_a_class") is None and d.public_row(None) is None


def test_a_class_never_carries_the_private_tail():
    secret = "stream command timed out SECRET-PATH /home/carbon/rs116c"
    name = d.classify(_record("build", RUNTIME, secret))
    assert "SECRET" not in name and "SECRET" not in d.EXPLANATIONS[name]


@pytest.mark.parametrize(
    "failure_class,chain,expected",
    [
        (None, 0, "unknown_no_rebuild"),  # no diagnosis: unknown
        (d.UNCLASSIFIED, 0, "unknown_no_rebuild"),
        ("carbon_build_wall_busy_host", 0, None),  # proven Carbon-side: one rebuild
        ("carbon_build_wall_busy_host", 1, "one_rebuild_spent"),
        ("carbon_cpu_worker_wall", 0, None),
    ],
)
def test_the_rebuild_rule_by_class(failure_class, chain, expected):
    assert lean_recipe._class_refusal(failure_class, chain) == expected


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


def test_feedback_v10_is_opt_in_and_serves_only_the_closed_row():
    from carbon.challenge_validator import direct_intake

    assert direct_intake.feedback_reply({"reply": "v10", "submission_id": "t"}) == "v10"
    assert direct_intake.feedback_reply({"reply": "v11", "submission_id": "t"}) == "v11"
    assert direct_intake.feedback_reply({"reply": "v13", "submission_id": "t"}) is None
    door = SimpleNamespace(
        grade_marker=lambda sid: None,
        adapter=SimpleNamespace(
            failure_class=lambda sid: "carbon_build_wall_busy_host"
        ),
    )
    row = direct_intake.DirectRecipeIntake._failure_class_row(door, "t")
    assert tuple(row) == d.PUBLIC_ROW_KEYS and row["side"] == "carbon"
    door.grade_marker = lambda sid: {
        "state": "FAILED"
    }  # a grade's own failure: not a build row
    assert direct_intake.DirectRecipeIntake._failure_class_row(door, "t") is None
    door.grade_marker = lambda sid: None

    def unreadable(sid):
        raise ValueError("custody differs")

    door.adapter = SimpleNamespace(failure_class=unreadable)
    assert direct_intake.DirectRecipeIntake._failure_class_row(door, "t") is None
