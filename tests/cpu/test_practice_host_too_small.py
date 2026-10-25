"""M1 rc41b (Test Runner 19:47Z): a 7 GiB / 4 CPU host cannot run any 1.4+ practice, because
the practice worker runs under a 16 GiB limit and Docker must see 1 GiB more, but the
miner was told only "an infrastructure problem". The refusal now names the host's own
numbers and the worker's: `practice_host_too_small`.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from test_launchpad_smoke_practice import HEAVY, FixturePractice, ledger_at, prepared

from carbon.development_session import research_campaign as rc
from carbon.development_session import research_carrier as carrier
from scripts.dev.miner_launchpad import supervisor

GIB = 1024**3
CAPACITY_CODE = "worker.doctor.capacity_or_cgroup_ineligible"


def _verdict(memory_gib, cpus, *, code=CAPACITY_CODE, cgroup="2"):
    info = {"MemTotal": int(memory_gib * GIB), "NCPU": cpus, "CgroupVersion": cgroup}
    return SimpleNamespace(eligible=False, code=code, host={"info": info})


def _large_profile():
    return SimpleNamespace(effective_memory_bytes=16 * GIB, effective_cpu_count=4)


def test_a_host_under_the_worker_s_need_is_too_small_with_both_sets_of_numbers():
    shortfall = carrier._host_capacity_shortfall(
        _verdict(6.8, 4), {"worker_profile": _large_profile()}
    )
    assert isinstance(shortfall, carrier.HostTooSmall) and isinstance(shortfall, ValueError)
    assert shortfall.capacity == {
        "memory_gib": 6.8,
        "cpus": 4,
        "needs_memory_gib": 17.0,
        "needs_cpus": 4,
    }


def test_too_few_cpus_alone_is_too_small_and_exactly_enough_is_not():
    profile = {"worker_profile": _large_profile()}
    assert carrier._host_capacity_shortfall(_verdict(32, 2), profile).capacity["cpus"] == 2
    assert carrier._host_capacity_shortfall(_verdict(17, 4, cgroup="1"), profile) is None
    assert carrier._host_capacity_shortfall(_verdict(31.2, 8), profile) is None


def test_other_ineligibility_is_not_called_too_small():
    profile = {"worker_profile": _large_profile()}
    # A different doctor code, or a verdict with no host facts, is the generic failure.
    assert carrier._host_capacity_shortfall(_verdict(4, 2, code="worker.doctor.x"), profile) is None
    assert (
        carrier._host_capacity_shortfall(
            SimpleNamespace(eligible=False, code=CAPACITY_CODE, host={}), profile
        )
        is None
    )


def test_without_a_worker_profile_the_c03_default_is_the_need():
    shortfall = carrier._host_capacity_shortfall(_verdict(1, 1), {})
    assert shortfall.capacity["needs_memory_gib"] > 1 and shortfall.capacity["needs_cpus"] >= 1


def test_the_failure_file_records_the_closed_reason_and_only_numbers(tmp_path):
    error = carrier.HostTooSmall(7 * GIB, 4, 17 * GIB, 4)
    carrier._retain_practice_failure(tmp_path, "HOST_READINESS", error)
    written = json.loads((tmp_path / "failure-HOST_READINESS.json").read_text())
    assert written["reason"] == "HOST_TOO_SMALL"
    assert written["capacity"] == {
        "memory_gib": 7.0,
        "cpus": 4,
        "needs_memory_gib": 17.0,
        "needs_cpus": 4,
    }
    assert "research host" not in json.dumps(written)  # the message text is never stored


def _run(tmp_path, state="FAILED_INFRA", capacity=None):
    ledger, manifest = ledger_at(tmp_path)
    practice = FixturePractice(ledger)
    practice.seconds = 10**6

    async def call(name, args, identity):
        if capacity is not None:
            operation = ledger.root / ("operation-" + "ab" * 32)
            operation.mkdir(exist_ok=True)
            carrier._retain_practice_failure(
                operation,
                "HOST_READINESS",
                carrier.HostTooSmall(
                    int(capacity[0] * GIB), capacity[1], 17 * GIB, 4
                ),
            )
        return {"terminal_task": {"state": state}}

    value = prepared(ledger, manifest, practice)
    value.sdk = SimpleNamespace(call=call)
    return asyncio.run(
        rc.practice_recipe(
            value, strategy=HEAVY, hypothesis="h", expected_effect="e", identity="small"
        )
    )


def test_a_practice_that_failed_on_capacity_is_refused_with_the_hosts_numbers(tmp_path):
    with pytest.raises(rc.OperationRefused) as refused:
        _run(tmp_path, capacity=(7, 4))
    assert refused.value.code == "practice_host_too_small"
    step = refused.value.next_step
    assert "7.0 GiB of memory and 4 CPUs" in step and "17.0 GiB" in step
    assert "32 GB" in step and "docker info" in step and "nothing counts against you" in step


def test_a_failure_with_no_capacity_record_stays_practice_could_not_run(tmp_path):
    with pytest.raises(rc.OperationRefused) as refused:
        _run(tmp_path, capacity=None)
    assert refused.value.code == "practice_could_not_run"
    assert getattr(refused.value, "next_step", None) is None


def test_an_old_failure_file_is_not_blamed_on_a_new_practice(tmp_path):
    """Only a failure written since this practice started counts."""
    ledger, manifest = ledger_at(tmp_path)
    operation = ledger.root / ("operation-" + "cd" * 32)
    operation.mkdir()
    carrier._retain_practice_failure(
        operation, "HOST_READINESS", carrier.HostTooSmall(7 * GIB, 4, 17 * GIB, 4)
    )
    import os
    import time

    path = operation / "failure-HOST_READINESS.json"
    os.utime(path, (time.time() - 3600, time.time() - 3600))
    assert rc._retained_capacity_shortfall(ledger.root, time.time()) is None
    assert rc._retained_capacity_shortfall(ledger.root, time.time() - 7200)["cpus"] == 4


def test_the_catalog_has_a_fixed_fallback_that_names_the_requirement():
    step = supervisor.next_action("practice_host_too_small")
    assert "17 GiB" in step and "4 CPUs" in step and "32 GB" in step
    assert "practice_host_too_small" in supervisor.NEXT_ACTIONS


def test_a_non_numeric_record_says_nothing_rather_than_something_wrong():
    assert rc._host_too_small_step({"memory_gib": "x", "cpus": 4}) is None
    assert rc._host_too_small_step({}) is None
