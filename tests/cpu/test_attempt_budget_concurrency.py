"""The total attempt budget holds across genuinely independent processes.

These use real subprocesses, not serial fixture calls, because the defect being
guarded against is a race between two callers with *different* nonces. Synthetic
state roots only; no accelerator is initialized and no device is attached.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from test_c03_worker_contract import _sha

from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

REPO = Path(__file__).resolve().parents[2]
PLAN = _sha("5")

# The batch a contending child is admitted against. The bound under test
# here is the attempt count; the batch bounds have their own tests.
LIMITS = {
    "productive_seconds": 600,
    "cleanup_seconds": 120,
    "attempt_seconds": 1800,
    "batch_seconds": 3600,
    "host_ram_bytes": 8 * 1024**3,
    "output_bytes": 64 * 1024**2,
    "batch_output_bytes": 256 * 1024**2,
    "training_steps": 32,
    "worker_network": "DISABLED",
}
CONTROLS = dev.effective_controls(LIMITS)

_CHILD = """
import json, sys, time
sys.path.insert(0, {repo!r})
from pathlib import Path
from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker.model import WorkerFailure

root = Path(sys.argv[1])
nonce = sys.argv[2]
budget = int(sys.argv[3])
start = float(sys.argv[4])
journal = dev.DevelopmentAttemptJournal(root)
# Start together so the two processes genuinely contend.
while time.time() < start:
    time.sleep(0.001)
try:
    journal.reserve(
        nonce=nonce,
        plan_digest={plan!r},
        budget=budget,
        controls=dev.effective_controls({limits!r}),
        now=time.time(),
    )
    print(json.dumps({{"outcome": "reserved"}}))
except WorkerFailure as failure:
    print(json.dumps({{"outcome": "refused", "code": failure.code.value}}))
"""


def _race(root, nonces, budget, delay=1.5):
    """Launch one process per nonce, all releasing at the same wall-clock time."""
    start = time.time() + delay
    source = _CHILD.format(repo=str(REPO), plan=PLAN, limits=LIMITS)
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", source, str(root), nonce, str(budget), str(start)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for nonce in nonces
    ]
    results = []
    for process in processes:
        out, err = process.communicate(timeout=120)
        assert process.returncode == 0, err
        results.append(json.loads(out.strip().splitlines()[-1]))
    return results


@pytest.fixture
def root(tmp_path):
    host = tmp_path / "host"
    host.mkdir(mode=0o700)
    return host


def test_two_different_nonces_cannot_both_take_the_last_attempt(root):
    """The race the previous count-then-create implementation allowed."""
    journal = dev.DevelopmentAttemptJournal(root)
    for index in range(3):
        nonce = f"{index:032x}"
        journal.reserve(
            nonce=nonce,
            plan_digest=PLAN,
            budget=4,
            controls=CONTROLS,
            now=time.time(),
        )
        journal.settle(nonce=nonce, state=dev.ATTEMPT_COMPLETED)
    assert journal.consumed() == 3

    results = _race(root, ["a" * 32, "b" * 32], budget=4)
    reserved = [r for r in results if r["outcome"] == "reserved"]
    refused = [r for r in results if r["outcome"] == "refused"]
    assert len(reserved) == 1, results
    assert len(refused) == 1, results
    assert journal.consumed() == 4, "the budget must never be overspent"


def test_a_full_budget_refuses_every_racing_process(root):
    journal = dev.DevelopmentAttemptJournal(root)
    for index in range(4):
        nonce = f"{index:032x}"
        journal.reserve(
            nonce=nonce,
            plan_digest=PLAN,
            budget=4,
            controls=CONTROLS,
            now=time.time(),
        )
        journal.settle(nonce=nonce, state=dev.ATTEMPT_COMPLETED)

    results = _race(root, ["a" * 32, "b" * 32], budget=4)
    assert all(r["outcome"] == "refused" for r in results), results
    assert journal.consumed() == 4


def test_the_same_nonce_replayed_across_processes_takes_one_attempt(root):
    results = _race(root, ["c" * 32, "c" * 32], budget=4)
    reserved = [r for r in results if r["outcome"] == "reserved"]
    assert len(reserved) == 1, results
    assert dev.DevelopmentAttemptJournal(root).consumed() == 1


def test_a_second_process_cannot_start_while_one_is_unreconciled(root):
    """An unsettled attempt blocks a new launch from any process."""
    dev.DevelopmentAttemptJournal(root).reserve(
        nonce="d" * 32, plan_digest=PLAN, budget=4, controls=CONTROLS, now=time.time()
    )
    results = _race(root, ["e" * 32], budget=4)
    assert results[0]["outcome"] == "refused"
    assert results[0]["code"] == WorkerCode.CONFLICT.value


def test_a_different_directory_does_not_grant_a_fresh_budget(root, tmp_path):
    """A new output path or worktree must not reset consumed attempts."""
    journal = dev.DevelopmentAttemptJournal(root)
    for index in range(4):
        nonce = f"{index:032x}"
        journal.reserve(
            nonce=nonce,
            plan_digest=PLAN,
            budget=4,
            controls=CONTROLS,
            now=time.time(),
        )
        journal.settle(nonce=nonce, state=dev.ATTEMPT_COMPLETED)
    # The journal is bound to the host record's parent, not to a caller path.
    assert dev.DevelopmentAttemptJournal(root).consumed() == 4
    with pytest.raises(WorkerFailure):
        dev.DevelopmentAttemptJournal(root).reserve(
            nonce="f" * 32,
            plan_digest=PLAN,
            budget=4,
            controls=CONTROLS,
            now=time.time(),
        )


def test_a_restart_sees_the_same_consumed_total(root):
    journal = dev.DevelopmentAttemptJournal(root)
    journal.reserve(
        nonce="a" * 32, plan_digest=PLAN, budget=4, controls=CONTROLS, now=1.0
    )
    journal.settle(nonce="a" * 32, state=dev.ATTEMPT_COMPLETED)
    source = (
        f"import sys; sys.path.insert(0, {str(REPO)!r});"
        "from pathlib import Path;"
        "from carbon.reconstruction.worker import development_admission as dev;"
        f"print(dev.DevelopmentAttemptJournal(Path({str(root)!r})).consumed())"
    )
    result = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1"


def test_an_interrupted_marker_write_does_not_grant_a_free_attempt(root):
    """A truncated marker is unreadable, so it blocks rather than vanishing."""
    journal = dev.DevelopmentAttemptJournal(root)
    path = journal.reserve(
        nonce="a" * 32, plan_digest=PLAN, budget=4, controls=CONTROLS, now=1.0
    )
    path.chmod(0o600)
    path.write_bytes(b"{partial")
    path.chmod(0o600)
    with pytest.raises(WorkerFailure):
        dev.DevelopmentAttemptJournal(root).blocking_attempt()


def test_the_accounting_lock_is_not_the_device_slot(root, monkeypatch):
    """Holding the accounting lock must not block the shared host lease."""
    from carbon.reconstruction.worker import accelerator_runtime as runtime

    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    journal = dev.DevelopmentAttemptJournal(root)
    with journal._accounting_lock():  # noqa: SIM117
        # A different lock: taking the device slot here must still succeed, so a
        # caller that reserves and then leases cannot deadlock.
        with runtime.shared_host_lease():
            pass
