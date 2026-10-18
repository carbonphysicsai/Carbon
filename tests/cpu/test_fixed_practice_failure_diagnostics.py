"""Closed private diagnostics do not change fixed-practice failure behavior."""

import json
import os
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

import pytest

from carbon.development_session import research_carrier as carrier
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)
from carbon.reconstruction.worker.model import (
    MINER_HOST_AUTHORITY,
    WorkerCode,
    WorkerFailure,
)

SECRET = b"SECRET-token-seed-path /private/fixture ENV=secret"


@pytest.fixture
def harness(tmp_path, monkeypatch):
    ledger = CampaignLedger(tmp_path)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            "campaign_id": "diagnostic-fixture",
            "implementation": "fixture",
            "objective": "test-only",
            "sampling": "public-test-only",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "alice",
        }
    )
    state = SimpleNamespace(
        ledger=ledger, fail_stage=None, error=None, events=[], result=None
    )

    def fail(stage):
        state.events.append(stage)
        if state.fail_stage == stage:
            raise state.error

    class CLI:
        def run(self, arguments, **kwargs):
            if arguments[0] == "create":
                fail("CREATE")
            elif arguments[0] == "start":
                fail("START")
            elif arguments[0] == "ps":
                fail("ABSENCE_QUERY")
            return SimpleNamespace(stdout=b"")

        def stream_to_file(self, arguments, destination, **kwargs):
            # The production helper removes failed stream output. Diagnostics
            # must survive independently, not interpret its absence as a stage.
            destination.write_bytes(b"fixture-stream")
            try:
                fail("PROGRAM" if destination.name == "stdout.txt" else "EXPORT")
            except Exception:
                destination.unlink()
                raise
            return len(b"fixture-stream")

    def doctor(**kwargs):
        fail("HOST_READINESS")
        return SimpleNamespace(eligible=True, cpuset="0,1")

    def profile(*args):
        fail("PROFILE")
        return object()

    def controls(**kwargs):
        fail("CONTROLS")
        return "sha256:" + "1" * 64, {}

    def observe(**kwargs):
        fail("OBSERVE")
        return {}

    def remove(**kwargs):
        fail("CLEANUP")

    def decode(source, target):
        fail("DECODE")
        target.mkdir()
        (target / "fixture.json").write_bytes(b"{}")

    def validate(target):
        fail("VALIDATE")

    original_write = carrier.write_once

    def write(path, payload):
        if path.parent.name == "input":
            fail("STAGING")
        elif path.name == "resources.json":
            fail("RESOURCES")
        original_write(path, payload)

    monkeypatch.setattr(carrier, "DockerCLI", CLI)
    monkeypatch.setattr(carrier, "doctor", doctor)
    monkeypatch.setattr(carrier, "_worker_profile", profile)
    monkeypatch.setattr(carrier, "create_arguments", lambda **kwargs: ["create"])
    monkeypatch.setattr(carrier, "spawn_watchdog", lambda **kwargs: fail("WATCHDOG"))
    monkeypatch.setattr(carrier, "inspect_effective_controls", controls)
    monkeypatch.setattr(carrier, "observe_effective_resources", observe)
    monkeypatch.setattr(carrier, "remove_exact_container", remove)
    monkeypatch.setattr(carrier, "decode_output_stream", decode)
    monkeypatch.setattr(carrier, "write_once", write)
    monkeypatch.setattr(carrier, "_check_cancel", lambda *args: fail("CHECK_CANCEL"))

    def run(**overrides):
        return carrier._run_locked(
            ledger,
            **{
                "owner": "alice",
                "identity": "public-task",
                "source": "# fixed synthetic public program; never executed",
                "files": {},
                "image": SimpleNamespace(image_id="sha256:" + "2" * 64),
                "seconds": 60,
                "provenance": "BATTERY_PUBLIC_PRACTICE",
                "extra_resources": {"research_trials": 1},
                "output_validator": validate,
                "before_finish": lambda: fail("ASSOCIATE"),
                **overrides,
            },
        )

    state.run = run
    return state


def records(root):
    return {
        path.stem.removeprefix("failure-"): json.loads(path.read_bytes())
        for path in root.glob("operation-*/failure-*.json")
    }


@pytest.mark.parametrize(
    "stage",
    [
        "STAGING",
        "HOST_READINESS",
        "PROFILE",
        "CHECK_CANCEL",
        "CREATE",
        "WATCHDOG",
        "START",
        "CONTROLS",
        "PROGRAM",
        "OBSERVE",
        "EXPORT",
        "RESOURCES",
        "CLEANUP",
        "DECODE",
        "VALIDATE",
        "ASSOCIATE",
    ],
)
def test_failure_stage_survives_with_same_exception_cleanup_and_no_retry(
    harness, stage
):
    error = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=SECRET + b" CUDA_ERROR_OUT_OF_MEMORY"
    )
    harness.fail_stage, harness.error = stage, error
    with pytest.raises(WorkerFailure) as caught:
        harness.run()
    assert caught.value is error
    assert records(harness.ledger.root) == {
        stage: {
            "schema": "carbon.autoresearch.fixed-practice-failure.v1",
            "stage": stage,
            "exception_class": "WorkerFailure",
            "worker_code": WorkerCode.RUNTIME.value,
            "diagnostic_markers": ["CUDA_ERROR_OUT_OF_MEMORY"],
        }
    }
    operation = harness.ledger.status(owner="alice")["operations"][0]
    if stage in {"STAGING", "HOST_READINESS"}:
        assert operation["state"] == "FAILED_INFRA"
        assert operation["actual"] == operation["reservation"]
        assert "CLEANUP" not in harness.events
    else:
        assert operation["state"] == "RESERVED"
    if "CREATE" in harness.events:
        assert harness.events.count("CREATE") == 1
        assert harness.events.count("CLEANUP") == 1
        if stage != "CLEANUP":
            assert harness.events.count("ABSENCE_QUERY") == 1
    for path in harness.ledger.root.glob("operation-*/failure-*.json"):
        assert SECRET not in path.read_bytes()
        assert len(path.read_bytes()) < 2048
    if stage == "PROGRAM":
        assert not list(harness.ledger.root.glob("operation-*/stdout.txt"))


def test_success_does_not_add_diagnostics_or_change_result_contract(harness):
    result = harness.run()
    assert records(harness.ledger.root) == {}
    assert result["schema"] == "carbon.autoresearch.worker-result.v1"
    assert set(result) == {
        "schema",
        "provenance",
        "output_digest",
        "files",
        "operation",
        "scientific_qualification",
        "official_eligible",
    }
    assert result["scientific_qualification"] is False
    assert result["official_eligible"] is False
    assert harness.ledger.operation_state("public-task", owner="alice") == "SUCCEEDED"


@pytest.mark.parametrize(
    "provenance,diagnose",
    [
        ("BATTERY_PUBLIC_PRACTICE", True),
        (carrier.LIBRARY_PREP_PROVENANCE, True),
        ("DIRECT_BUNDLE_PUBLIC_INFERENCE", True),
        ("GRAPHITE_CARRIER_PRACTICE", False),
    ],
)
def test_only_fixed_public_phases_opt_into_controls_diagnosis(
    harness, monkeypatch, provenance, diagnose
):
    seen = []

    def inspect(**kwargs):
        seen.append(kwargs["diagnose_policy"])
        return "sha256:" + "1" * 64, {}

    monkeypatch.setattr(carrier, "inspect_effective_controls", inspect)
    harness.run(provenance=provenance)
    assert seen == [diagnose]


def test_normal_reconciliation_keeps_failed_record_and_full_original_charge(harness):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=SECRET)
    harness.fail_stage, harness.error = "PROGRAM", original
    with pytest.raises(WorkerFailure):
        harness.run()
    before = records(harness.ledger.root)
    result = carrier.reconcile_worker(
        harness.ledger, owner="alice", identity="public-task"
    )
    assert result["state"] == "FAILED_INFRA"
    assert result["cleanup_observed"] is True
    assert result["retry_dispatched"] is False
    assert records(harness.ledger.root) == before
    operation = harness.ledger.status(owner="alice")["operations"][0]
    assert operation["state"] == "FAILED_INFRA"
    assert operation["actual"] == operation["reservation"]
    assert harness.events.count("CREATE") == 1


@pytest.mark.parametrize("failure", [OSError("disk full"), ValueError("file conflict")])
def test_failed_diagnostic_write_cannot_replace_original_failure(
    harness, monkeypatch, failure
):
    original_write = carrier.write_once

    def write(path, payload):
        if path.name.startswith("failure-"):
            raise failure
        original_write(path, payload)

    monkeypatch.setattr(carrier, "write_once", write)
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=SECRET)
    harness.fail_stage, harness.error = "PROGRAM", original
    with pytest.raises(WorkerFailure) as caught:
        harness.run()
    assert caught.value is original
    assert records(harness.ledger.root) == {}
    assert "CLEANUP" in harness.events and "ABSENCE_QUERY" in harness.events
    assert harness.ledger.operation_state("public-task", owner="alice") == "RESERVED"


def test_cleanup_failure_records_both_errors_without_changing_precedence(
    harness, monkeypatch
):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=SECRET)
    cleanup = WorkerFailure(WorkerCode.CLEANUP, private_diagnostic=SECRET)
    harness.fail_stage, harness.error = "PROGRAM", original

    def remove(**kwargs):
        harness.events.append("CLEANUP")
        raise cleanup

    monkeypatch.setattr(carrier, "remove_exact_container", remove)
    with pytest.raises(WorkerFailure) as caught:
        harness.run()
    # Existing finally cleanup precedence is retained; the first failure is
    # still available separately, without replacing the raised cleanup error.
    assert caught.value is cleanup
    saved = records(harness.ledger.root)
    assert saved["PROGRAM"]["worker_code"] == WorkerCode.RUNTIME.value
    assert saved["CLEANUP"]["worker_code"] == WorkerCode.CLEANUP.value
    assert harness.ledger.operation_state("public-task", owner="alice") == "RESERVED"


def test_unknown_class_and_unvalidated_code_cannot_leak(tmp_path):
    secret_class = type("SECRET_token_seed_path", (Exception,), {})
    with (
        pytest.raises(secret_class),
        carrier._fixed_practice_stage(tmp_path, "BATTERY_PUBLIC_PRACTICE", "START"),
    ):
        raise secret_class(SECRET)
    first = (tmp_path / "failure-START.json").read_bytes()
    assert json.loads(first)["exception_class"] == "Exception"
    assert b"SECRET" not in first
    bad_code = WorkerFailure("SECRET-unvalidated-code", private_diagnostic=SECRET)
    carrier._retain_practice_failure(tmp_path, "CREATE", bad_code)
    assert (
        json.loads((tmp_path / "failure-CREATE.json").read_bytes())["worker_code"]
        is None
    )


def test_marker_scan_and_file_names_are_closed_and_bounded(tmp_path):
    error = WorkerFailure(
        WorkerCode.RUNTIME,
        private_diagnostic=b"x" * 65536 + b" CUDA_ERROR_OUT_OF_MEMORY " + SECRET,
    )
    carrier._retain_practice_failure(tmp_path, "PROGRAM", error)
    original = (tmp_path / "failure-PROGRAM.json").read_bytes()
    assert json.loads(original)["diagnostic_markers"] == []
    carrier._retain_practice_failure(tmp_path, "../outside", error)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["failure-PROGRAM.json"]
    carrier._retain_practice_failure(tmp_path, "PROGRAM", ValueError("changed"))
    assert (tmp_path / "failure-PROGRAM.json").read_bytes() == original


def test_controls_predicate_is_exact_private_battery_only(harness):
    from carbon.reconstruction.worker.docker_runtime import _CONTROL_PREDICATE_PREFIX

    error = WorkerFailure(
        WorkerCode.POLICY,
        private_diagnostic=_CONTROL_PREDICATE_PREFIX + b"MEMORY",
    )
    harness.fail_stage, harness.error = "CONTROLS", error
    with pytest.raises(WorkerFailure) as caught:
        harness.run()
    assert caught.value is error
    saved = records(harness.ledger.root)["CONTROLS"]
    assert saved["controls_predicate"] == "MEMORY"
    assert SECRET not in json.dumps(saved).encode()
    assert harness.ledger.operation_state("public-task", owner="alice") == "RESERVED"
    assert "CLEANUP" in harness.events and "ABSENCE_QUERY" in harness.events


@pytest.mark.parametrize(
    "diagnostic",
    [
        b"MEMORY",
        b"carbon.controls.predicate.v1:MEMORY" + SECRET,
        b"carbon.controls.predicate.v1:UNKNOWN",
    ],
)
def test_controls_predicate_rejects_untrusted_diagnostics(tmp_path, diagnostic):
    carrier._retain_practice_failure(
        tmp_path,
        "CONTROLS",
        WorkerFailure(WorkerCode.POLICY, private_diagnostic=diagnostic),
    )
    assert "controls_predicate" not in json.loads(
        (tmp_path / "failure-CONTROLS.json").read_bytes()
    )
    assert SECRET not in (tmp_path / "failure-CONTROLS.json").read_bytes()


def test_policy_predicate_does_not_enter_other_stage(tmp_path):
    from carbon.reconstruction.worker.docker_runtime import _CONTROL_PREDICATE_PREFIX

    carrier._retain_practice_failure(
        tmp_path,
        "PROGRAM",
        WorkerFailure(
            WorkerCode.POLICY,
            private_diagnostic=_CONTROL_PREDICATE_PREFIX + b"MEMORY",
        ),
    )
    assert "controls_predicate" not in json.loads(
        (tmp_path / "failure-PROGRAM.json").read_bytes()
    )


@pytest.mark.parametrize("provenance", ["MINER_SELF_REPORTED", "BATTERY_VALIDATOR"])
def test_other_security_domains_gain_no_record(tmp_path, provenance):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=SECRET)
    with (
        pytest.raises(WorkerFailure) as caught,
        carrier._fixed_practice_stage(tmp_path, provenance, "PROGRAM"),
    ):
        raise original
    assert caught.value is original
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-only mode")
def test_record_is_owner_only(tmp_path):
    carrier._retain_practice_failure(tmp_path, "CREATE", ValueError("fixture"))
    assert (tmp_path / "failure-CREATE.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("stage", ["DEVICE_LEASE", "LEASE_RELEASE"])
def test_gpu_lease_failures_preserve_classification_and_cleanup(
    harness, monkeypatch, stage
):
    from carbon.reconstruction.worker import accelerator_runtime

    original = WorkerFailure(WorkerCode.CONFLICT, private_diagnostic=SECRET)
    device = SimpleNamespace(digest="sha256:" + "3" * 64, device_uuid="fixture-device")
    monkeypatch.setattr(carrier, "_gpu_device", lambda: device)
    monkeypatch.setattr(carrier, "_gpu_pins", lambda *args: ("fixture", "p", "l"))
    monkeypatch.setattr(carrier, "_check_gpu_host", lambda *args: None)
    monkeypatch.setattr(
        carrier,
        "_worker_profile",
        lambda *args: SimpleNamespace(accelerator_authority=MINER_HOST_AUTHORITY),
    )
    monkeypatch.setattr(accelerator_runtime, "shared_host_lease", nullcontext)
    monkeypatch.setattr(
        accelerator_runtime, "mark_device_allocation", lambda **kwargs: None
    )

    @contextmanager
    def lease(uuid):
        assert uuid == device.device_uuid
        if stage == "DEVICE_LEASE":
            raise original
        try:
            yield
        finally:
            raise original

    monkeypatch.setattr(accelerator_runtime, "miner_device_lease", lease)
    monkeypatch.setattr(
        accelerator_runtime, "reject_existing_device_containers", lambda **kwargs: None
    )
    with pytest.raises(WorkerFailure) as caught:
        harness.run(accelerator=carrier.MINER_GPU)
    assert caught.value is original
    assert (
        records(harness.ledger.root)[stage]["worker_code"] == WorkerCode.CONFLICT.value
    )
    assert harness.ledger.operation_state("public-task", owner="alice") == "RESERVED"
    if stage == "LEASE_RELEASE":
        assert "CLEANUP" in harness.events and "ABSENCE_QUERY" in harness.events
    else:
        assert "CREATE" not in harness.events


@pytest.mark.parametrize(
    "provenance",
    [
        carrier.LIBRARY_PREP_PROVENANCE,
        carrier.LIBRARY_OVERLAY_BUILD_PROVENANCE,
        "DIRECT_BUNDLE_PUBLIC_INFERENCE",
    ],
)
def test_direct_phase_records_closed_control_reason_without_changing_failure(
    tmp_path, provenance
):
    from carbon.reconstruction.worker.docker_runtime import _CONTROL_PREDICATE_PREFIX

    original = WorkerFailure(
        WorkerCode.POLICY, private_diagnostic=_CONTROL_PREDICATE_PREFIX + b"MEMORY"
    )
    with (
        pytest.raises(WorkerFailure) as caught,
        carrier._fixed_practice_stage(tmp_path, provenance, "CONTROLS"),
    ):
        raise original
    assert caught.value is original
    record = json.loads((tmp_path / "failure-CONTROLS.json").read_bytes())
    assert record["stage"] == "CONTROLS"
    assert record["worker_code"] == WorkerCode.POLICY.value
    assert record["controls_predicate"] == "MEMORY"
    assert (
        b"carbon.controls.predicate"
        not in (tmp_path / "failure-CONTROLS.json").read_bytes()
    )


def test_prep_program_diagnostic_is_private_bounded_and_best_effort(
    tmp_path, monkeypatch
):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=SECRET * 5000)

    def fail():
        with carrier._fixed_practice_stage(
            tmp_path, carrier.LIBRARY_PREP_PROVENANCE, "PROGRAM"
        ):
            raise original

    with pytest.raises(WorkerFailure) as caught:
        fail()
    assert caught.value is original
    record = (tmp_path / "failure-PROGRAM.json").read_bytes()
    assert SECRET not in record and len(record) < 2048
    private_path = tmp_path / "private-prep-program-diagnostic.bin"
    assert private_path.read_bytes() == original.private_diagnostic[:65536]
    assert set(tmp_path.iterdir()) == {tmp_path / "failure-PROGRAM.json", private_path}
    if os.name != "nt":
        assert private_path.stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / "snapshot").exists()
    assert not (tmp_path / "export.stream").exists()

    def unavailable(*args):
        raise OSError("disk full")

    monkeypatch.setattr(carrier, "write_once", unavailable)
    with pytest.raises(WorkerFailure) as caught:
        fail()
    assert caught.value is original
    assert (tmp_path / "failure-PROGRAM.json").read_bytes() == record
    assert private_path.read_bytes() == original.private_diagnostic[:65536]
