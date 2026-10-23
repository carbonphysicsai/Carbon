"""An approved limit must govern execution, not just appear in a hash.

The approval record carries a closed set of limits, and the diagnostic plan
identity hashes them. Hashing is not enforcement: it proves which limits were
approved and says nothing about which limits the run applied. If the controller
then collects output against a fixed 128 MiB constant while the approval allowed
64 MiB, the record and the run disagree - and the record is the one that looks
authoritative afterwards.

These drive the real public `execute` and read the values the controller actually
used: the byte bound handed to the export, the profile the container is built
from, the deadline given to the independent deadline owner. `create_arguments` is
wrapped to record, not replaced; it still builds the real command line.

The rule under test is that every effective limit satisfies *both* the installed
approval and the registered implementation policy. Neither may relax the other:
an approval asking for more than the implementation supports is clamped down, and
a registered cap that is already lower stays controlling.

Synthetic host roots throughout. No device is attached and no container exists.
"""

import time

import pytest
import scripted_docker
from test_local_controller_lifecycle import NONCE, _limits
from test_local_controller_lifecycle import harness as _lifecycle_harness

from carbon.development_session.profile import canonical
from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker import controller as controller_module
from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker.model import (
    CONTROL_BYTES,
    MEMORY_BYTES,
    OUTPUT_BYTES,
    PRODUCTIVE_DEADLINE_SECONDS,
    WorkerFailure,
)

harness = _lifecycle_harness

MEBIBYTE = 1024**2


@pytest.fixture(autouse=True)
def recorded_profiles(monkeypatch):
    """Record every worker profile the real container builder receives.

    A wrapper, not a stub: `create_arguments` still runs and still produces the
    command line the container would be created from.
    """
    seen = []
    original = controller_module.create_arguments

    def recording(*args, **kwargs):
        seen.append(kwargs.get("worker_profile"))
        return original(*args, **kwargs)

    monkeypatch.setattr(controller_module, "create_arguments", recording)
    return seen


def _profile(recorded_profiles):
    assert recorded_profiles, "no container was ever built"
    return recorded_profiles[-1]


def _reapprove(bench, **limit_overrides):
    """Reinstall the approval with different limits, and match the selector.

    Everything else is held fixed. The plan identity is re-derived rather than
    edited, because the limits are part of it: changing an approved limit changes
    what was approved, and a selector echoing the old digest must stop matching.
    """
    limits = {**_limits(), **limit_overrides}
    derived, _ = dev.diagnostic_plan_identity(
        construction_plan_digest=bench.plan.to_ref().content_digest,
        training_archive_digest=bench.archive.content_digest,
        training_archive_provenance=bench.archive.provenance,
        training_archive_role=bench.archive.role,
        image=bench.image,
        profile_digest=GPU_PROFILE.digest,
        role=AcceleratorRole.MINER_RESEARCH,
        operation="registered_trainer_fit",
        limits=limits,
    )
    document = {**bench.document, "limits": limits, "plan_digest": derived}
    path = bench.host / dev.DEVELOPMENT_RECORD
    path.chmod(0o600)
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    bench.document = document
    bench.derived = derived
    bench.selector = dev.LocalDiagnosticRequest(
        plan_digest=derived,
        input_digest=bench.archive.content_digest,
        nonce=NONCE,
    )
    return derived


def _run(bench):
    """Run to its terminal failure; the export cannot produce a real artifact."""
    with pytest.raises(WorkerFailure):
        bench.run()


# --- the approved output ceiling must bound actual collection -----------------


def test_a_lower_approved_output_ceiling_bounds_the_actual_export(harness):
    """The reported mismatch, stated as the behaviour that must hold."""
    approved_bytes = 16 * MEBIBYTE
    assert approved_bytes < OUTPUT_BYTES, "the approval must be the tighter one"
    _reapprove(harness, output_bytes=approved_bytes)
    _run(harness)

    assert harness.cli.export_bounds, "the run never reached output collection"
    used = harness.cli.export_bounds[-1]["maximum"]
    assert (
        used == approved_bytes + 2 * CONTROL_BYTES
    ), "output collection used the registered constant, not the approved limit"
    assert used != OUTPUT_BYTES + 2 * CONTROL_BYTES


def test_an_approval_asking_for_more_output_is_clamped_to_the_registered_cap(
    harness,
):
    """An approval cannot widen what the implementation supports."""
    _reapprove(harness, output_bytes=4 * OUTPUT_BYTES)
    _run(harness)
    used = harness.cli.export_bounds[-1]["maximum"]
    assert used == OUTPUT_BYTES + 2 * CONTROL_BYTES


# --- the approved deadline must bound the run ---------------------------------


def test_a_lower_approved_deadline_bounds_the_run(harness, recorded_profiles):
    approved_seconds = 120
    assert approved_seconds < PRODUCTIVE_DEADLINE_SECONDS
    _reapprove(harness, productive_seconds=approved_seconds)
    before = time.time()
    _run(harness)

    assert _profile(recorded_profiles).body["deadline_seconds"] == approved_seconds
    # The independent deadline owner enforces it, so it must receive the
    # effective value rather than the registered maximum.
    assert harness.spawned, "the deadline owner was never started"
    deadline = harness.spawned[-1]["deadline_unix"]
    assert deadline - before <= approved_seconds + 30
    assert deadline - before < PRODUCTIVE_DEADLINE_SECONDS


def test_an_approval_asking_for_a_longer_deadline_is_clamped(
    harness, recorded_profiles
):
    """Internally coherent, but longer than the implementation enforces.

    900s fits inside the approval's own 1800s attempt window, so the approval is
    self-consistent and is not refused on its own terms - which is exactly the
    case where clamping has to do the work.
    """
    requested = 900
    assert requested > PRODUCTIVE_DEADLINE_SECONDS
    _reapprove(harness, productive_seconds=requested)
    _run(harness)
    body = _profile(recorded_profiles).body
    assert body["deadline_seconds"] == PRODUCTIVE_DEADLINE_SECONDS


def test_an_internally_incoherent_approval_is_refused_outright(harness):
    """A productive window that cannot fit its own attempt window is refused."""
    with pytest.raises(WorkerFailure):
        _reapprove(harness, productive_seconds=10 * PRODUCTIVE_DEADLINE_SECONDS)
        harness.run()
    assert not harness.cli.created


# --- a registered cap that is already lower stays controlling -----------------


def test_the_lower_registered_memory_cap_is_not_widened_by_the_approval(harness):
    """The approval allows 8 GiB; the implementation registers 4 GiB."""
    _reapprove(harness, host_ram_bytes=8 * 1024**3)
    _run(harness)
    flags = scripted_docker._flags(harness.cli.create_arguments)
    assert int(flags["memory"][0]) == MEMORY_BYTES
    assert int(flags["memory-swap"][0]) == MEMORY_BYTES


# --- the published profile states the effective limits ------------------------


def test_the_worker_profile_publishes_the_effective_limits(harness, recorded_profiles):
    approved_bytes = 16 * MEBIBYTE
    _reapprove(harness, output_bytes=approved_bytes, productive_seconds=120)
    _run(harness)
    body = _profile(recorded_profiles).body
    assert body["output"]["bytes"] == approved_bytes
    assert body["deadline_seconds"] == 120
    # The registered cap still controls where it is the lower one.
    assert body["memory"]["bytes"] == MEMORY_BYTES


def test_the_approved_training_step_ceiling_reaches_the_worker(
    harness, recorded_profiles
):
    """A step ceiling nobody carries into the worker is not a ceiling."""
    _reapprove(harness, training_steps=8)
    _run(harness)
    controls = _profile(recorded_profiles).body["accelerators"]["effective_controls"]
    assert controls["training_steps"] == 8


def test_the_effective_limits_are_bound_into_the_plan_identity(harness):
    """Changing an approved limit changes what was approved."""
    first = _reapprove(harness, output_bytes=16 * MEBIBYTE)
    second = _reapprove(harness, output_bytes=32 * MEBIBYTE)
    assert first != second

    # A selector echoing the superseded identity no longer matches the record.
    stale = dev.LocalDiagnosticRequest(
        plan_digest=first,
        input_digest=harness.archive.content_digest,
        nonce=NONCE,
    )
    with pytest.raises(WorkerFailure):
        harness.run(local_diagnostic=stale)
    assert not harness.cli.created


# --- an unrepresentable request is refused before attachment ------------------


@pytest.mark.parametrize(
    "override",
    [
        {"output_bytes": 0},
        {"productive_seconds": 0},
        {"training_steps": 0},
        {"host_ram_bytes": 0},
        {"output_bytes": -1},
        {"productive_seconds": "600"},
    ],
)
def test_an_unrepresentable_limit_is_refused_before_any_container(harness, override):
    """A limit the implementation cannot honour rejects; it does not round up.

    The rejection may land while deriving the identity or while admitting the
    run. Either is acceptable - both are before attachment - so this asserts the
    outcome that matters rather than the exact line.
    """
    try:
        _reapprove(harness, **override)
    except WorkerFailure:
        assert not harness.cli.created
        return
    with pytest.raises(WorkerFailure):
        harness.run()
    assert not harness.cli.created
    assert dev.DevelopmentAttemptJournal(harness.host).consumed() == 0
