"""Lead (18 Nov 2026): live 116 had 8 RESERVED numerical ops left by dead runs, each refusing every later build of its
owner with "one numerical worker; reconcile active operation" until a door stop and a manual `reconcile_worker`. A
round that holds the owner's numerical lease (so no live supervisor of that owner runs) now settles such an op itself
through `reconcile_worker`'s own settle (an orphan container of the dead run removed first), and reserves once more.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test_cw1_research_recovery import setup

from carbon.development_session import research_carrier as carrier

NEXT = {"numerical_milliseconds": 60000, "research_trials": 1}


def _docker(monkeypatch, listed=""):
    removed = []
    monkeypatch.setattr(
        carrier, "remove_exact_container", lambda **kwargs: removed.append(kwargs)
    )
    monkeypatch.setattr(
        carrier,
        "DockerCLI",
        lambda: SimpleNamespace(run=lambda *a, **k: SimpleNamespace(stdout=listed)),
    )
    return removed


def _logged(monkeypatch):
    from carbon.battery import intake

    lines = []
    monkeypatch.setattr(
        intake, "log", lambda event, **fields: lines.append((event, fields))
    )
    return lines


def _reserve_next(ledger):
    return ledger.reserve(
        "next", owner="one", phase="research", request={"source": "n"}, resources=NEXT
    )


def test_a_dead_reserved_op_whose_worker_is_gone_is_settled_and_the_next_op_reserves(
    tmp_path, monkeypatch
):
    ledger, _directory = setup(tmp_path)
    with pytest.raises(ValueError) as refused:
        _reserve_next(ledger)
    # the exact refusal the round matches
    assert str(refused.value) == carrier.ONE_NUMERICAL_WORKER
    removed = _docker(monkeypatch)
    lines = _logged(monkeypatch)
    with carrier._numerical_lease(ledger):
        assert carrier._settle_dead_numerical(ledger, owner="one", keep="next") == 1
        assert _reserve_next(ledger)["dispatch"] is True
    states = {op["id"]: op["state"] for op in ledger.status(owner="one")["operations"]}
    assert states == {"worker": "FAILED_INFRA", "next": "RESERVED"}
    assert [event for event, _ in lines] == ["op_settled_dead_reserved"]
    # the settle's exact-container removal (a no-op: none was left)
    assert len(removed) == 1


def test_an_orphan_container_of_a_dead_run_is_removed_and_its_op_settled(tmp_path, monkeypatch):
    """Deploy (live 116, 18 Nov 2026 21:35Z): a restart without a drain left the op's remote container running. Under
    the owner's lease no live supervisor exists, so the container is an orphan: removed by its exact name, the op
    settled, and the next op reserves."""
    ledger, _directory = setup(tmp_path)
    present = ["c0ffee"]
    removed = []

    def remove(**kwargs):
        removed.append(kwargs)
        present[0] = ""

    monkeypatch.setattr(carrier, "remove_exact_container", remove)
    monkeypatch.setattr(
        carrier,
        "DockerCLI",
        lambda: SimpleNamespace(run=lambda *a, **k: SimpleNamespace(stdout=present[0])),
    )
    lines = _logged(monkeypatch)
    with carrier._numerical_lease(ledger):
        assert carrier._settle_dead_numerical(ledger, owner="one", keep="next") == 1
        assert _reserve_next(ledger)["dispatch"] is True
    assert len(removed) == 1
    assert [event for event, _ in lines] == ["op_settled_dead_reserved"]


def test_a_container_that_cannot_be_confirmed_gone_keeps_the_op(tmp_path, monkeypatch):
    ledger, _directory = setup(tmp_path)
    _docker(monkeypatch, listed="c0ffee")  # still listed after the removal
    lines = _logged(monkeypatch)
    with carrier._numerical_lease(ledger):
        assert carrier._settle_dead_numerical(ledger, owner="one", keep="next") == 0
        with pytest.raises(ValueError, match="one numerical worker"):
            _reserve_next(ledger)
    assert ledger.status(owner="one")["operations"][0]["state"] == "RESERVED"
    assert lines[0][0] == "op_dead_reserved_kept"
    assert "cleanup uncertain" in lines[0][1]["reason"]


def test_the_op_about_to_run_is_never_settled(tmp_path, monkeypatch):
    ledger, _directory = setup(tmp_path)
    _docker(monkeypatch)
    _logged(monkeypatch)
    with carrier._numerical_lease(ledger):
        assert carrier._settle_dead_numerical(ledger, owner="one", keep="worker") == 0
    assert ledger.status(owner="one")["operations"][0]["state"] == "RESERVED"


def test_the_manual_settle_is_unchanged(tmp_path, monkeypatch):
    """`reconcile_worker` keeps its own lease and still removes a surviving container (the operator's settle)."""
    ledger, _directory = setup(tmp_path)
    removed = _docker(monkeypatch)
    result = carrier.reconcile_worker(ledger, owner="one", identity="worker")
    assert result["state"] == "FAILED_INFRA" and result["cleanup_observed"]
    assert len(removed) == 1
    with carrier._numerical_lease(ledger), pytest.raises(ValueError, match="active"):
        carrier.reconcile_worker(ledger, owner="one", identity="worker")


def test_a_docker_or_ssh_failure_keeps_the_op_and_the_plain_refusal(
    tmp_path, monkeypatch
):
    """V2: a `cli.run` that raises (ssh, docker, a timeout) never fails the round: the op stays RESERVED, the line says
    why, and the round's reservation refuses exactly as before."""
    ledger, _directory = setup(tmp_path)

    def broken(*args, **kwargs):
        raise RuntimeError("ssh: connect to host timed out")

    monkeypatch.setattr(carrier, "remove_exact_container", lambda **kwargs: None)
    monkeypatch.setattr(carrier, "DockerCLI", lambda: SimpleNamespace(run=broken))
    lines = _logged(monkeypatch)
    with carrier._numerical_lease(ledger):
        assert carrier._settle_dead_numerical(ledger, owner="one", keep="next") == 0
        with pytest.raises(ValueError) as refused:
            _reserve_next(ledger)
    assert str(refused.value) == carrier.ONE_NUMERICAL_WORKER
    assert ledger.status(owner="one")["operations"][0]["state"] == "RESERVED"
    assert [event for event, _ in lines] == ["op_dead_reserved_kept"]
    assert lines[0][1]["reason"] == "RuntimeError"
