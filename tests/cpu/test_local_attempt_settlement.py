"""A finished attempt must be reconciled, or the next one is blocked forever.

The reservation is deliberately conservative: an attempt is durable before any
container can exist, and `blocking_attempt()` refuses a new launch while one is
RESERVED or AMBIGUOUS. That is correct, and it is exactly why the terminal side
has to be wired up. A run that removes its container and releases its allocation
but never settles its own marker consumes one attempt and then blocks every
remaining attempt in the budget.

These use the same real-controller fixture as the lifecycle tests: the real
public `execute`, real queue, store, staging and cleanup. Nothing settles the
journal by hand - a test that called `settle()` itself would prove only that the
journal works, which was never in doubt.

Synthetic host roots throughout. No device is attached and no container exists.
"""

import time

import pytest
from test_local_controller_lifecycle import CONTROLS, NONCE
from test_local_controller_lifecycle import harness as _lifecycle_harness

from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

SECOND_NONCE = "b" * 32

# The same real-controller fixture the lifecycle tests use, re-exported so
# pytest resolves it in this module too. One definition, two suites.
harness = _lifecycle_harness


def _journal(bench):
    return dev.DevelopmentAttemptJournal(bench.host)


def _second_request(bench, nonce=SECOND_NONCE):
    """A distinct, otherwise-valid request for the same approved work."""
    return dev.LocalDiagnosticRequest(
        plan_digest=bench.derived,
        input_digest=bench.archive.content_digest,
        nonce=nonce,
    )


# --- a terminal outcome with confirmed cleanup frees the next attempt ---------


def test_a_failed_run_with_confirmed_cleanup_does_not_block_the_next_attempt(
    harness,
):
    """The reported defect, stated as the behaviour that must hold."""
    journal = _journal(harness)
    with pytest.raises(WorkerFailure):
        harness.run()

    # The run ended, the container was removed and the allocation released.
    assert harness.cli.removed, "the exact container was removed"
    assert not (harness.host / "active-allocation.json").exists()
    assert not (harness.host / "device-quarantined").exists()

    # So the attempt is reconciled: it still counts, and it no longer blocks.
    assert journal.consumed() == 1, "a failed attempt is never refunded"
    assert (
        journal.blocking_attempt() is None
    ), "a run whose cleanup was confirmed must not leave its attempt blocking"

    # And the next permitted attempt can actually be reserved.
    journal.reserve(
        nonce=SECOND_NONCE,
        plan_digest=harness.derived,
        budget=4,
        controls=CONTROLS,
        now=float(time.time()),
    )
    assert journal.consumed() == 2


def test_a_cancelled_run_with_confirmed_cleanup_also_frees_the_next_attempt(
    harness,
):
    calls = {"count": 0}

    def cancelled():
        calls["count"] += 1
        return harness.cli.started and calls["count"] > 3

    journal = _journal(harness)
    with pytest.raises(WorkerFailure) as error:
        harness.run(cancelled=cancelled)
    assert error.value.code is WorkerCode.CANCELLED
    assert harness.cli.removed
    assert journal.consumed() == 1
    assert journal.blocking_attempt() is None


def test_the_settled_outcome_does_not_claim_the_work_succeeded(harness):
    """A reconciled failure must not be recorded as a completed one.

    The distinction matters beyond bookkeeping: COMPLETED on this path would say
    a development run produced a result, and nothing here did.
    """
    journal = _journal(harness)
    with pytest.raises(WorkerFailure):
        harness.run()
    marker = journal.attempt(nonce=NONCE)
    assert marker["state"] == dev.ATTEMPT_RECONCILED
    assert marker["state"] != dev.ATTEMPT_COMPLETED
    # Whatever the label, it is still spent.
    assert journal.consumed() == 1


# --- unconfirmed cleanup stays blocking --------------------------------------


def test_a_run_whose_cleanup_could_not_be_confirmed_stays_blocking(harness):
    """Unknown cleanup is not a free attempt; it blocks until reconciled."""
    harness.cli.removable = False
    journal = _journal(harness)
    with pytest.raises(WorkerFailure) as error:
        harness.run()
    assert error.value.code is WorkerCode.QUARANTINED

    blocking = journal.blocking_attempt()
    assert blocking is not None, "unconfirmed cleanup must keep blocking"
    assert blocking["state"] == dev.ATTEMPT_AMBIGUOUS
    assert journal.consumed() == 1

    # A second, otherwise-valid request is refused while that stands.
    with pytest.raises(WorkerFailure) as error:
        harness.run(local_diagnostic=_second_request(harness))
    assert error.value.code is WorkerCode.CONFLICT


def test_an_ambiguous_attempt_is_never_erased_to_obtain_a_launch(harness):
    harness.cli.removable = False
    journal = _journal(harness)
    with pytest.raises(WorkerFailure):
        harness.run()
    before = journal.blocking_attempt()
    assert before is not None
    for _ in range(3):
        with pytest.raises(WorkerFailure):
            harness.run(local_diagnostic=_second_request(harness))
    after = journal.blocking_attempt()
    assert after == before, "repeated attempts must not rewrite the marker"
    assert journal.consumed() == 1


# --- replay and accounting ----------------------------------------------------


def test_a_replayed_nonce_after_settlement_does_not_execute_again(harness):
    journal = _journal(harness)
    with pytest.raises(WorkerFailure):
        harness.run()
    settled = journal.consumed()
    created_once = harness.cli.create_arguments

    with pytest.raises(WorkerFailure) as error:
        harness.run()
    assert error.value.code is WorkerCode.CONFLICT
    assert journal.consumed() == settled, "a replay invents no allowance"
    assert harness.cli.create_arguments == created_once


def test_the_budget_still_bounds_the_total_after_settlement(harness):
    """Settling frees the next attempt; it does not refund the spent one."""
    journal = _journal(harness)
    with pytest.raises(WorkerFailure):
        harness.run()
    assert journal.consumed() == 1
    for index in range(1, 4):
        journal.reserve(
            nonce=f"{index:032x}",
            plan_digest=harness.derived,
            budget=4,
            controls=CONTROLS,
            now=float(time.time()),
        )
        journal.settle(nonce=f"{index:032x}", state=dev.ATTEMPT_RECONCILED)
    assert journal.consumed() == 4
    with pytest.raises(WorkerFailure):
        journal.reserve(
            nonce="f" * 32,
            plan_digest=harness.derived,
            budget=4,
            controls=CONTROLS,
            now=float(time.time()),
        )


def test_settlement_does_not_touch_the_shared_host_slot_or_quarantine(harness):
    """Reconciling accounting must not clear a strict device quarantine."""
    marker = harness.host / "device-quarantined"
    with pytest.raises(WorkerFailure):
        harness.run()
    assert not marker.exists(), "this run created no quarantine"

    marker.write_bytes(b"UNRECONCILED_DEVICE_RELEASE\n")
    with pytest.raises(WorkerFailure) as error:
        harness.run(local_diagnostic=_second_request(harness))
    assert error.value.code is WorkerCode.QUARANTINED
    assert marker.is_file(), "local settlement never clears strict quarantine"
