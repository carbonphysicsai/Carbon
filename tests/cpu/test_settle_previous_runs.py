"""V2's code item (live 116, 21:35Z, 18 Nov 2026): a receiver that died mid-grade leaves its op RESERVED with its worker
container still ALIVE, which the dead-RESERVED settle keeps, so the owner refuses every later op ("one numerical
worker; reconcile active operation"). At receiver start, an op RESERVED by a PREVIOUS process (created before this
start) has its exact container stopped and is settled FAILED_INFRA (`research_carrier.settle_previous_runs`, called by
`OwnerProviders.restore` for every owner it opens); this process's ops and finished ops are never touched.
"""

from __future__ import annotations

import hashlib
import time
from types import SimpleNamespace

from test_cw1_research_recovery import setup

from carbon.challenge_validator import direct_receiver as receiver
from carbon.development_session import research_carrier as carrier

NEXT = {"numerical_milliseconds": 60000, "research_trials": 1}


def _alive_until_removed(monkeypatch):
    """A docker double: the worker container is listed until `remove_exact_container` removes it."""
    removed = []
    monkeypatch.setattr(
        carrier, "remove_exact_container", lambda **kwargs: removed.append(kwargs)
    )

    def run(*args, **kwargs):
        return SimpleNamespace(stdout="" if removed else "c0ffee\n")

    monkeypatch.setattr(carrier, "DockerCLI", lambda: SimpleNamespace(run=run))
    return removed


def _logged(monkeypatch):
    from carbon.battery import intake

    lines = []
    monkeypatch.setattr(
        intake, "log", lambda event, **fields: lines.append((event, fields))
    )
    return lines


def _states(ledger):
    return {op["id"]: op["state"] for op in ledger.status(owner="one")["operations"]}


def test_a_previous_runs_op_with_its_container_alive_is_stopped_and_settled(
    tmp_path, monkeypatch
):
    ledger, _directory = setup(tmp_path)  # "worker" RESERVED, its supervisor gone
    removed = _alive_until_removed(monkeypatch)
    lines = _logged(monkeypatch)
    started = time.time() + 1  # this start: after the op was reserved
    assert carrier.settle_previous_runs(ledger, owner="one", before=started) == 1
    assert len(removed) == 1  # its exact container stopped
    assert _states(ledger) == {"worker": "FAILED_INFRA"}
    assert [event for event, _ in lines] == ["op_settled_previous_run"]
    # the owner is usable again: the next op reserves
    next_op = ledger.reserve(
        "next", owner="one", phase="research", request={"source": "n"}, resources=NEXT
    )
    assert next_op["dispatch"] is True
    # and a second start finds nothing left to do
    assert carrier.settle_previous_runs(ledger, owner="one", before=started) == 0
    assert len(removed) == 1


def test_this_processes_op_is_never_touched(tmp_path, monkeypatch):
    ledger, _directory = setup(tmp_path)
    removed = _alive_until_removed(monkeypatch)
    _logged(monkeypatch)
    # an op created at or after this start is this process's own: left as it is
    assert carrier.settle_previous_runs(ledger, owner="one", before=0.0) == 0
    assert removed == [] and _states(ledger) == {"worker": "RESERVED"}


def test_a_held_lease_means_a_live_supervisor_and_nothing_is_touched(
    tmp_path, monkeypatch
):
    ledger, _directory = setup(tmp_path)
    removed = _alive_until_removed(monkeypatch)
    lines = _logged(monkeypatch)
    with carrier._numerical_lease(ledger):
        assert (
            carrier.settle_previous_runs(ledger, owner="one", before=time.time() + 1)
            == 0
        )
    assert removed == [] and _states(ledger) == {"worker": "RESERVED"}
    assert lines == [
        (
            "op_previous_run_kept",
            {
                "owner_sha256": hashlib.sha256(b"one").hexdigest(),
                "reason": "lease_held",
            },
        )
    ]


def test_a_docker_failure_keeps_the_op(tmp_path, monkeypatch):
    ledger, _directory = setup(tmp_path)

    def broken(*args, **kwargs):
        raise RuntimeError("ssh: connect to host timed out")

    monkeypatch.setattr(carrier, "DockerCLI", lambda: SimpleNamespace(run=broken))
    monkeypatch.setattr(carrier, "remove_exact_container", broken)
    lines = _logged(monkeypatch)
    assert carrier.settle_previous_runs(ledger, owner="one", before=time.time() + 1) == 0
    assert _states(ledger) == {"worker": "RESERVED"}
    assert lines[0][0] == "op_previous_run_kept"


def test_the_restore_settles_each_opened_owners_previous_runs(tmp_path, monkeypatch):
    owner = "5" + "1" * 47
    name = hashlib.sha256(owner.encode()).hexdigest()
    (tmp_path / name).mkdir()
    monkeypatch.setattr(receiver, "_private_directory", lambda path: path)
    monkeypatch.setattr(receiver, "private_json", lambda path: {"hotkey": owner})
    pool = receiver.OwnerProviders(tmp_path, None, None, None)
    ledger = object()
    monkeypatch.setattr(
        pool,
        "_open",
        lambda hotkey, *, restoring, host=False: SimpleNamespace(ledger=ledger),
    )
    calls = []
    monkeypatch.setattr(
        carrier,
        "settle_previous_runs",
        lambda got, *, owner, before: calls.append((got, owner, before)),
    )
    began = time.time()
    pool.restore()
    ((got, settled_owner, before),) = calls
    assert got is ledger and settled_owner == owner
    assert began <= before <= time.time()
