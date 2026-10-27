"""Why did a grade fail, and where does a launch receiver's pool store come from?

valV3, 2026-10-27: the auto-grade marker said only 'WorkerFailure', no traceback existed
anywhere (the grade loop's own record never saw it: the grader settles the failure itself), and
the receiver needs an existing pool store that nothing created.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, direct_receiver

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "sealed_exam"
A = "rtsk_" + "a" * 64


def _script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Failure(RuntimeError):
    """A WorkerFailure-shaped error: a closed code and a private diagnostic."""

    def __init__(self):
        super().__init__("Development reconstruction worker operation failed.")
        self.code = SimpleNamespace(value="RUNTIME")
        self.private_diagnostic = b"container stderr: out of memory at /private/path"


class Intake:
    def __init__(self, failure):
        self.failure = failure
        self.adapter = SimpleNamespace(
            contract_digest="sha256:" + "0" * 64,
            ledger=SimpleNamespace(submitted_outcomes=lambda contract: (A,)),
            owner=lambda submission_id: None,
        )

    def retain_result(self, submission_id, **kwargs):
        raise self.failure


def test_a_failed_grade_keeps_its_traceback_and_worker_diagnostic_privately(tmp_path):
    grader = auto_grade.AutoGrader(Intake(Failure()), tmp_path)
    assert grader.run_once() == (A, "FAILED")
    marker = json.loads((tmp_path / "auto-grade/markers" / (A + ".json")).read_text())
    assert (
        marker["code"] == "Failure"
    )  # the marker still carries a type, nothing private
    record = tmp_path / "auto-grade/failures" / (A + ".txt")
    text = record.read_text(encoding="utf-8")
    assert "Traceback" in text and "retain_result" in text
    assert "code: RUNTIME" in text and "out of memory" in text
    assert stat.S_IMODE(record.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "auto-grade/failures").stat().st_mode) == 0o700
    assert "out of memory" not in json.dumps(marker)


def test_a_typed_retention_refusal_keeps_its_traceback_too(tmp_path):
    from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

    grader = auto_grade.AutoGrader(Intake(RetentionUnavailable("regrade_x")), tmp_path)
    assert grader.run_once() == (A, "FAILED")
    text = (tmp_path / "auto-grade/failures" / (A + ".txt")).read_text()
    assert "RetentionUnavailable" in text and "regrade_x" in text


def test_a_failure_record_is_create_only_and_never_changes_the_outcome(tmp_path):
    grader = auto_grade.AutoGrader(Intake(Failure()), tmp_path)
    (tmp_path / "auto-grade/failures" / (A + ".txt")).write_text("first")
    assert grader.run_once() == (
        A,
        "FAILED",
    )  # the existing record does not stop the marker
    assert (tmp_path / "auto-grade/failures" / (A + ".txt")).read_text() == "first"


def test_the_pool_store_is_created_once_owner_only_and_opens_for_the_receiver(tmp_path):
    init = _script("init_pool_store")
    directory = tmp_path / "pools"
    directory.mkdir(mode=0o700)
    path = directory / "lean-pool.sqlite3"
    done = init.create(path)
    assert done["status"] == "POOL_STORE_READY" and done["created"] is True
    assert done["mode"] == "0o600" and done["tables"] > 0
    assert stat.S_IMODE(os.lstat(path).st_mode) == 0o600
    # The receiver opens exactly this file (it never creates one).
    assert direct_receiver._open_pool_store(path) is not None
    assert init.check(path)["created"] is False
    with pytest.raises(init.Refused, match="already exists"):
        init.create(path)


@pytest.mark.parametrize(
    "case", ["relative", "no_directory", "group_writable", "symlink"]
)
def test_the_pool_store_command_refuses_what_it_could_not_keep_private(tmp_path, case):
    init = _script("init_pool_store")
    directory = tmp_path / "pools"
    directory.mkdir(mode=0o700)
    path = directory / "lean-pool.sqlite3"
    if case == "relative":
        path = Path("lean-pool.sqlite3")
    elif case == "no_directory":
        path = tmp_path / "missing" / "lean-pool.sqlite3"
    elif case == "group_writable":
        directory.chmod(0o770)
    elif case == "symlink":
        (tmp_path / "elsewhere").write_text("x")
        path.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(init.Refused):
        init.create(path)
    assert not (directory / "lean-pool.sqlite3").exists() or case == "symlink"


def test_check_refuses_a_directory_a_symlink_and_an_open_file(tmp_path):
    init = _script("init_pool_store")
    with pytest.raises(init.Refused):
        init.check(tmp_path)
    store = tmp_path / "s.sqlite3"
    store.write_bytes(b"")
    store.chmod(0o644)
    with pytest.raises(init.Refused, match="owner-only"):
        init.check(store)


def test_the_copy_repro_points_the_config_at_the_copy_and_chooses_the_auto_grade():
    repro = _script("receiver_copy_repro")
    live = "/var/lib/carbon-val/receivers/motor"
    config = {
        "root": live,
        "host": "127.0.0.1",
        "port": 8769,
        "lifetime_seconds": None,
        "auto_grade": {"pool_store": "/var/lib/carbon-val/pools/motor/pool.sqlite3"},
        "evaluation_pack": {"root": live + "/pack", "private_root": "/custody/private"},
    }
    advance = repro.rewritten(config, live, "/scratch/root", mode="advance")
    assert "auto_grade" not in advance and advance["port"] == repro.REPRO_PORT
    assert advance["root"] == "/scratch/root"
    assert advance["evaluation_pack"] == {
        "root": "/scratch/root/pack",
        "private_root": "/custody/private",  # shared, read only: not remapped
    }
    grade = repro.rewritten(
        config, live, "/scratch/root", mode="grade", pool_store="/scratch/pool.sqlite3"
    )
    assert grade["auto_grade"] == {"pool_store": "/scratch/pool.sqlite3"}
    # the live pool store is never reachable from the copy
    assert "/var/lib/carbon-val/pools" not in json.dumps(grade)
    assert config["port"] == 8769  # the live config is untouched


def test_only_reserved_operations_are_listed_for_reconciliation():
    reconcile = _script("reconcile_dead_operation")
    listing = [
        {"id": "regrade-graded-1", "state": "FINISHED", "created": 1.0},
        {"id": "regrade-timed-9", "state": "RESERVED", "created": 3.0},
        {"id": "regrade-timed-2", "state": "RESERVED", "created": 2.0},
        {"id": "seq", "state": "HELD", "created": 0.5},
    ]
    assert [op["id"] for op in reconcile.open_operations(listing)] == [
        "regrade-timed-2",
        "regrade-timed-9",
    ]
