"""The owner catalog install: a busy-daemon failure gets one bounded retry, and a skipped entry names its cause.

The failing entries on a busy VM carried only the fixed worker-failure wrapper; the typed code and the daemon's last
word were dropped. Only the UNAVAILABLE kind (a Docker CLI timeout or an unreachable daemon) is retried, once.
"""

from pathlib import Path

import pytest

from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure
from scripts.dev import catalog_install


@pytest.fixture
def harness(monkeypatch):
    calls, sleeps = [], []
    monkeypatch.setattr(catalog_install.time, "sleep", sleeps.append)
    monkeypatch.setattr(
        catalog_install.pipeline,
        "bundle_directory",
        lambda item, work, wheelhouse=None: work,
    )
    monkeypatch.setattr(catalog_install.pipeline, "verify", lambda item: None)
    monkeypatch.setattr(catalog_install, "_declares_wheels", lambda item: False)
    monkeypatch.setattr(
        catalog_install, "_missing_wheel", lambda item, wheelhouse: None
    )
    monkeypatch.setattr(catalog_install, "stage_gpu_twins", lambda *a, **k: None)
    only = catalog_install.pipeline.load()["entries"][0]["catalog_id"]

    def run(behaviour, ids=None):
        def install_bundle(directory, inventory=None, **kwargs):
            calls.append(1)
            return behaviour(len(calls))

        monkeypatch.setattr(
            catalog_install.library_bundle, "install_bundle", install_bundle
        )
        skipped = []
        installed = (
            catalog_install.install(
                ids or [only],
                wheelhouse=Path("."),
                state_dir=Path("."),
                skipped=skipped,
            )
            if ids
            else catalog_install.install(
                wheelhouse=Path("."), state_dir=Path("."), skipped=skipped
            )
        )
        return installed, skipped

    return run, calls, sleeps


def _unavailable(attempt):
    raise WorkerFailure(
        WorkerCode.UNAVAILABLE, private_diagnostic=b"bounded command timed out"
    )


def test_a_busy_daemon_failure_is_retried_once_and_can_then_succeed(harness):
    run, calls, sleeps = harness
    entries = len(catalog_install.pipeline.load()["entries"])

    def behaviour(attempt):
        if attempt == 1:
            return _unavailable(attempt)
        return {"status": "INSTALLED_VERIFIED", "bundle_ref": {}}

    installed, skipped = run(behaviour)
    assert skipped == [] and len(installed) == entries
    assert len(calls) == entries + 1 and sleeps == [
        catalog_install.RETRY_BACKOFF_SECONDS
    ]


def test_a_second_busy_failure_is_skipped_and_says_it_was_retried(harness):
    run, calls, sleeps = harness
    seen = {}

    def behaviour(attempt):
        seen.setdefault("first", attempt)
        if attempt in (seen["first"], seen["first"] + 1):
            return _unavailable(attempt)
        return {"status": "INSTALLED_VERIFIED", "bundle_ref": {}}

    _, skipped = run(behaviour)
    assert len(skipped) == 1 and skipped[0]["reason"] == "install_failed"
    detail = skipped[0]["detail"]
    assert WorkerCode.UNAVAILABLE.value in detail
    assert "bounded command timed out" in detail and detail.endswith("(retried once)")
    assert len(sleeps) == 1


def test_any_other_failure_is_never_retried_and_names_its_code(harness):
    run, calls, sleeps = harness
    seen = {}

    def behaviour(attempt):
        seen.setdefault("first", attempt)
        if attempt == seen["first"]:
            raise WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\nboom")
        return {"status": "INSTALLED_VERIFIED", "bundle_ref": {}}

    _, skipped = run(behaviour)
    assert len(skipped) == 1 and sleeps == []
    assert WorkerCode.RUNTIME.value in skipped[0]["detail"]
    assert "retried" not in skipped[0]["detail"]


def test_the_recorded_cause_carries_no_path_or_token():
    secret = "A" * 40
    failure = WorkerFailure(
        WorkerCode.RUNTIME,
        private_diagnostic=(
            "exit=1\nError: cannot read /home/miner/.carbon/key.json "
            f"C:\\Users\\x\\y token {secret}"
        ).encode(),
    )
    detail = catalog_install._diagnostic(failure)
    assert "/home" not in detail and "C:" not in detail and secret not in detail
    assert "<redacted>" in detail and "Error:" in detail and len(detail) <= 300
    assert catalog_install._diagnostic(ValueError("plain")) == "ValueError: plain"


def test_an_entry_named_by_id_raises_and_is_not_retried(harness):
    run, calls, sleeps = harness
    with pytest.raises(WorkerFailure):
        run(
            _unavailable,
            ids=[catalog_install.pipeline.load()["entries"][0]["catalog_id"]],
        )
    assert len(calls) == 1 and sleeps == []
