"""The batch bounds, not just the per-attempt ones.

Per-attempt limits were already enforced. They cannot bound a batch: four
attempts each inside a per-attempt output ceiling still write four times that
ceiling, and four attempts each inside a per-attempt deadline still occupy the
host for four times as long. Each one looks individually compliant the whole
way, which is exactly why the batch needs its own accounting.

The two bounds are enforced differently because the envelope states them
differently. Output accumulates, so it is summed across attempts. Time is a
fixed span *from first admission* including the gaps between attempts, so
neither idling between runs nor restarting the process rewinds it.

Synthetic host roots throughout. No device is attached, no container exists and
no attempt of the real allowance is consumed.
"""

import time

import pytest
import scripted_docker  # noqa: F401  (imported for its fixtures' side effects)
from test_local_controller_lifecycle import CONTROLS, NONCE, _limits
from test_local_controller_lifecycle import harness as _lifecycle_harness

from carbon.development_session.profile import canonical
from carbon.reconstruction.worker import controller as controller_module
from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

harness = _lifecycle_harness

PLAN = "sha256:" + "7" * 64
MEBIBYTE = 1024**2


@pytest.fixture
def journal(tmp_path):
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    return dev.DevelopmentAttemptJournal(root)


def _controls(**overrides):
    return dev.effective_controls({**_limits(), **overrides})


def _reserve(journal, index, controls=None, now=None):
    return journal.reserve(
        nonce=f"{index:032x}",
        plan_digest=PLAN,
        budget=64,  # deliberately not the bound under test here
        controls=controls or CONTROLS,
        now=time.time() if now is None else now,
    )


# --- the batch output total ---------------------------------------------------


def test_the_batch_output_total_refuses_an_attempt_the_count_would_allow(journal):
    """The reported gap: attempts remain, but the batch's output is spent."""
    controls = _controls(output_bytes=64 * MEBIBYTE, batch_output_bytes=128 * MEBIBYTE)
    base = time.time()
    _reserve(journal, 0, controls, now=base)
    journal.settle(nonce=f"{0:032x}", state=dev.ATTEMPT_COMPLETED)
    _reserve(journal, 1, controls, now=base + 1)
    journal.settle(nonce=f"{1:032x}", state=dev.ATTEMPT_COMPLETED)

    assert journal.consumed() == 2, "the attempt count is nowhere near its budget"
    with pytest.raises(WorkerFailure) as failure:
        _reserve(journal, 2, controls, now=base + 2)
    assert failure.value.code is WorkerCode.POLICY
    assert journal.consumed() == 2, "a refused attempt must not be recorded"


def test_a_failed_attempt_still_charges_the_batch(journal):
    """No refund is invented for work that failed or was never observed."""
    controls = _controls(output_bytes=64 * MEBIBYTE, batch_output_bytes=128 * MEBIBYTE)
    base = time.time()
    _reserve(journal, 0, controls, now=base)
    journal.settle(nonce=f"{0:032x}", state=dev.ATTEMPT_RECONCILED)
    _reserve(journal, 1, controls, now=base + 1)
    journal.settle(nonce=f"{1:032x}", state=dev.ATTEMPT_RECONCILED)
    with pytest.raises(WorkerFailure):
        _reserve(journal, 2, controls, now=base + 2)


def test_an_observed_output_charge_releases_only_what_was_measured(journal):
    """A measurement may reduce a worst case. Nothing else may.

    Paired with the test below, which is the same batch without the
    measurement: 130 MiB holds two reserved worst cases and no third, so the
    third attempt is admitted here only because the first two were measured.
    """
    controls = _controls(output_bytes=64 * MEBIBYTE, batch_output_bytes=130 * MEBIBYTE)
    base = time.time()
    for index in range(2):
        _reserve(journal, index, controls, now=base + index)
        journal.settle(
            nonce=f"{index:032x}",
            state=dev.ATTEMPT_COMPLETED,
            observed_output_bytes=MEBIBYTE,
        )
    assert journal.batch_consumption()[dev.CHARGE_OUTPUT_BYTES] == 2 * MEBIBYTE
    _reserve(journal, 2, controls, now=base + 2)


def test_without_a_measurement_the_reserved_worst_case_stands(journal):
    """The control for the test above. Same batch, nothing measured."""
    controls = _controls(output_bytes=64 * MEBIBYTE, batch_output_bytes=130 * MEBIBYTE)
    base = time.time()
    for index in range(2):
        _reserve(journal, index, controls, now=base + index)
        journal.settle(nonce=f"{index:032x}", state=dev.ATTEMPT_COMPLETED)
    assert journal.batch_consumption()[dev.CHARGE_OUTPUT_BYTES] == 128 * MEBIBYTE
    with pytest.raises(WorkerFailure):
        _reserve(journal, 2, controls, now=base + 2)


def test_an_ambiguous_attempt_keeps_its_worst_case_whatever_was_measured(journal):
    """An uncertain cleanup has not established that the attempt stopped."""
    controls = _controls(output_bytes=64 * MEBIBYTE, batch_output_bytes=128 * MEBIBYTE)
    _reserve(journal, 0, controls)
    journal.settle(
        nonce=f"{0:032x}",
        state=dev.ATTEMPT_AMBIGUOUS,
        observed_output_bytes=1,
    )
    assert journal.batch_consumption()[dev.CHARGE_OUTPUT_BYTES] == 64 * MEBIBYTE


def test_an_unsettled_attempt_keeps_its_worst_case(journal):
    """The process dying before settlement must not release the batch."""
    controls = _controls(output_bytes=64 * MEBIBYTE, batch_output_bytes=128 * MEBIBYTE)
    _reserve(journal, 0, controls)
    reopened = dev.DevelopmentAttemptJournal(journal.root.parent)
    assert reopened.batch_consumption()[dev.CHARGE_OUTPUT_BYTES] == 64 * MEBIBYTE


# --- the batch time window ----------------------------------------------------


def test_the_window_refuses_an_attempt_that_could_not_finish_inside_it(journal):
    """Admitting it would leave the batch bound unenforceable as it binds."""
    base = time.time()
    _reserve(journal, 0, now=base)
    journal.settle(nonce=f"{0:032x}", state=dev.ATTEMPT_COMPLETED)

    # 3600 s batch, 1800 s attempt: at t+1801 a full-length attempt would end
    # after the window closes.
    with pytest.raises(WorkerFailure) as failure:
        _reserve(journal, 1, now=base + 1801)
    assert failure.value.code is WorkerCode.POLICY

    # And it is genuinely the window, not the clock: one that still fits passes.
    _reserve(journal, 2, now=base + 1799)


def test_the_window_runs_from_first_admission_not_the_latest_attempt(journal):
    """Otherwise each new attempt would silently start a fresh batch."""
    base = time.time()
    for index in range(3):
        _reserve(journal, index, now=base + index * 900)
        journal.settle(nonce=f"{index:032x}", state=dev.ATTEMPT_COMPLETED)
    assert journal.batch_consumption()["first_admission_unix"] == base

    # t+2700 is only 900 s after the previous attempt, but 2700 s into the batch.
    with pytest.raises(WorkerFailure):
        _reserve(journal, 3, now=base + 2700)


def test_idle_time_consumes_the_window(journal):
    """A pause between attempts is not free; the envelope bounds the span."""
    base = time.time()
    _reserve(journal, 0, now=base)
    journal.settle(nonce=f"{0:032x}", state=dev.ATTEMPT_COMPLETED)
    # Nothing ran in between, and the window closed regardless.
    with pytest.raises(WorkerFailure):
        _reserve(journal, 1, now=base + 3599)


def test_a_restart_does_not_rewind_the_window(journal):
    """A new process, worktree or output directory reads the same first admission."""
    base = time.time()
    _reserve(journal, 0, now=base)
    journal.settle(nonce=f"{0:032x}", state=dev.ATTEMPT_COMPLETED)

    restarted = dev.DevelopmentAttemptJournal(journal.root.parent)
    assert restarted.batch_consumption()["first_admission_unix"] == base
    with pytest.raises(WorkerFailure):
        _reserve(restarted, 1, now=base + 1801)


def test_a_clock_that_moved_backwards_is_refused_rather_than_trusted(journal):
    """The only reading that cannot be used to rewind a spent batch."""
    base = time.time()
    _reserve(journal, 0, now=base)
    journal.settle(nonce=f"{0:032x}", state=dev.ATTEMPT_COMPLETED)
    with pytest.raises(WorkerFailure) as failure:
        _reserve(journal, 1, now=base - 60)
    assert failure.value.code is WorkerCode.POLICY


def test_the_first_attempt_of_a_batch_is_always_admissible(journal):
    """`effective_controls` already guarantees an attempt fits its own batch."""
    _reserve(journal, 0)
    assert journal.consumed() == 1


# --- records this journal cannot read ----------------------------------------


def test_a_marker_from_an_older_schema_blocks_rather_than_counting_as_zero(journal):
    """Historical meaning preserved: it recorded no charge, so none is inferred."""
    journal.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    (journal.root / f"{0:032x}.json").write_bytes(
        canonical(
            {
                "schema": "carbon.accelerator-development-attempt.v1",
                "nonce": f"{0:032x}",
                "plan_digest": PLAN,
                "reserved_unix": time.time(),
                "state": dev.ATTEMPT_COMPLETED,
            }
        )
    )
    with pytest.raises(WorkerFailure) as failure:
        _reserve(journal, 1)
    assert failure.value.code is WorkerCode.POLICY
    with pytest.raises(WorkerFailure):
        journal.batch_consumption()


@pytest.mark.parametrize("value", [None, -1, True, "64", 1.0])
def test_a_malformed_charge_blocks_rather_than_counting_as_zero(journal, value):
    journal.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    (journal.root / f"{0:032x}.json").write_bytes(
        canonical(
            {
                "schema": dev.ATTEMPT_SCHEMA,
                "nonce": f"{0:032x}",
                "plan_digest": PLAN,
                "reserved_unix": time.time(),
                "state": dev.ATTEMPT_COMPLETED,
                dev.CHARGE_OUTPUT_BYTES: value,
                "charge_basis": dev.CHARGE_RESERVED,
                dev.OBSERVED_SECONDS: None,
            }
        )
    )
    with pytest.raises(WorkerFailure):
        _reserve(journal, 1)


def test_reserve_requires_the_resolved_controls_not_a_partial_dict(journal):
    for controls in ({}, {"batch_seconds": 3600}, {**CONTROLS, "extra": 1}, None):
        with pytest.raises(WorkerFailure):
            journal.reserve(
                nonce=f"{9:032x}",
                plan_digest=PLAN,
                budget=4,
                controls=controls,
                now=time.time(),
            )
    assert journal.consumed() == 0


# --- through the real controller ---------------------------------------------


class _OffsetClock:
    """The real `time`, with a test-controlled offset on `monotonic` only.

    Installed into the controller module's own namespace rather than over the
    global module, so nothing outside the controller sees a shifted clock.
    """

    def __init__(self, offset):
        self._offset = offset

    def __getattr__(self, name):
        return getattr(time, name)

    def monotonic(self):
        return time.monotonic() + self._offset["value"]


def test_the_whole_attempt_deadline_interrupts_a_real_run(harness, monkeypatch):
    """The attempt bound governs the run, not only the productive window.

    Only `productive_seconds` ever reached execution, so time spent staging,
    verifying, exporting and cleaning up was outside every deadline. The clock
    is advanced while the lease is being taken - before any timing object or
    container exists - so the attempt deadline is the only bound that can fire
    and the assertion cannot pass for the wrong reason.
    """
    offset = {"value": 0.0}
    monkeypatch.setattr(controller_module, "time", _OffsetClock(offset))

    original = dev.DevelopmentHostApproval.exclusive_lease

    def delayed(self):
        offset["value"] = float(_limits()["attempt_seconds"] + 1)
        return original(self)

    monkeypatch.setattr(dev.DevelopmentHostApproval, "exclusive_lease", delayed)

    with pytest.raises(WorkerFailure) as failure:
        harness.run()
    assert failure.value.code is WorkerCode.DEADLINE
    assert not harness.cli.created, "no container may be built after the deadline"


def test_a_real_run_charges_the_batch_and_records_its_duration(harness):
    """The controller's own accounting, read back from the journal."""
    journal = dev.DevelopmentAttemptJournal(harness.host)
    with pytest.raises(WorkerFailure):
        harness.run()

    marker = journal.attempt(nonce=NONCE)
    assert marker["state"] == dev.ATTEMPT_RECONCILED
    # The export never produced a snapshot, so the output charge was never
    # observed and stays at the approved worst case.
    assert marker[dev.CHARGE_OUTPUT_BYTES] == CONTROLS["output_bytes"]
    assert marker["charge_basis"] == dev.CHARGE_RESERVED
    # The duration was observed, and is recorded as evidence about the attempt.
    assert type(marker[dev.OBSERVED_SECONDS]) is int
    assert marker[dev.OBSERVED_SECONDS] >= 0

    consumption = journal.batch_consumption()
    assert consumption[dev.CHARGE_OUTPUT_BYTES] == CONTROLS["output_bytes"]
    assert consumption["first_admission_unix"] is not None
