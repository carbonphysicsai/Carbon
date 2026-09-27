"""carbon.compute accounting, admission and capability summary (MOCK provider)."""

from __future__ import annotations

import pytest
from compute_fake_runpod import Clock, FakeRunPod, key_file

from carbon.compute import (
    ComputeError,
    ComputeService,
    ComputeStore,
    FileCredentialProvider,
    GpuFact,
    HostFacts,
    PodSpec,
    ProvisionRequest,
    RunPodAdapter,
    WorkloadDemand,
    admit_concurrency,
    capability_summary,
    collect_charges,
    observe_local_host,
    summarize,
)

IMAGE = "ghcr.io/example/worker@sha256:" + "0" * 64
GIB = 1024**3


def _service(tmp_path):
    clock, fake = Clock(), FakeRunPod(rate=0.40)
    store = ComputeStore(tmp_path / "store", clock=clock)
    adapter = RunPodAdapter(
        FileCredentialProvider(key_file(tmp_path)),
        fake,
        clock=clock,
        sleep=lambda _s: None,
    )
    service = ComputeService(store, adapter, clock=clock)
    store.start_campaign("camp-1")
    service.observe_balance("camp-1")
    return clock, fake, store, adapter, service


def _request(clock, intent_id="i1", storage_rate=0.10):
    return ProvisionRequest(
        tenant="t",
        miner="m",
        campaign_id="camp-1",
        intent_id=intent_id,
        spec=PodSpec(
            image=IMAGE,
            gpu_type_id="NVIDIA A40",
            gpu_count=1,
            container_disk_gb=20,
            volume_gb=10,
            max_rate_usd_per_hr=0.49,
            storage_usd_per_gb_month=storage_rate,
        ),
        deadline_at=clock() + 10 * 3600,
    )


def test_estimates_charges_and_unresolved_stay_separate(tmp_path):
    clock, fake, store, adapter, service = _service(tmp_path)
    a = service.provision(_request(clock, "i1"))
    b = service.provision(_request(clock, "i2"))
    clock.advance(3600)
    service.stop("camp-1", "i1", a.resource_id)  # storage survives the stop
    clock.advance(3600)

    fake.billing[a.resource_id] = 0.55  # only one pod has a provider report
    assert collect_charges(store, adapter) == [b.resource_id]
    summary = summarize(store, clock=clock)
    by_id = {r.resource_id: r for r in summary.resources}

    storage_hourly = 30 * 0.10 / 730
    assert by_id[a.resource_id].compute_hours == pytest.approx(1.0)
    assert by_id[a.resource_id].storage_gb_hours == pytest.approx(60.0)
    assert by_id[a.resource_id].estimated_compute_usd == pytest.approx(0.40)
    assert by_id[a.resource_id].estimated_storage_usd == pytest.approx(
        2 * storage_hourly
    )
    assert by_id[b.resource_id].estimated_compute_usd == pytest.approx(0.80)
    assert by_id[a.resource_id].provider_reported_usd == pytest.approx(0.55)
    assert by_id[b.resource_id].provider_reported_usd is None

    assert summary.provider_reported_usd == pytest.approx(0.55)
    assert summary.provider_unresolved == (b.resource_id,)
    assert summary.estimated_usd == pytest.approx(1.20 + 4 * storage_hourly)


def test_missing_storage_rate_is_refused_as_unbounded_before_dispatch(tmp_path):
    clock, fake, store, _adapter, service = _service(tmp_path)
    with pytest.raises(ComputeError, match="unbounded"):
        service.provision(_request(clock, storage_rate=None))
    assert fake.creates() == 0
    assert summarize(store, clock=clock).estimate_unresolved == ()


def test_concurrency_is_derived_from_host_facts():
    demand = WorkloadDemand(cpus=2, memory_bytes=4 * GIB)
    small = HostFacts(cpu_count=8, memory_bytes=16 * GIB, gpus=None)
    big = HostFacts(cpu_count=64, memory_bytes=256 * GIB, gpus=None)
    assert admit_concurrency(small, demand).max_concurrent == 3  # 7 cpu / 2
    assert admit_concurrency(small, demand).limiting == "cpu"
    assert admit_concurrency(big, demand).max_concurrent == 31  # 63 / 2
    memory_bound = HostFacts(cpu_count=64, memory_bytes=10 * GIB, gpus=None)
    decision = admit_concurrency(memory_bound, demand)
    assert (decision.max_concurrent, decision.limiting) == (2, "memory")

    gpu_demand = WorkloadDemand(
        cpus=1, memory_bytes=GIB, gpus=1, gpu_memory_bytes=40 * GIB
    )
    gpus = (GpuFact(48 * GIB), GpuFact(48 * GIB), GpuFact(24 * GIB))
    host = HostFacts(cpu_count=64, memory_bytes=256 * GIB, gpus=gpus)
    assert admit_concurrency(host, gpu_demand).max_concurrent == 2
    unobserved = HostFacts(cpu_count=64, memory_bytes=256 * GIB, gpus=None)
    decision = admit_concurrency(unobserved, gpu_demand)
    assert (decision.max_concurrent, decision.limiting) == (0, "gpu_not_observed")
    assert admit_concurrency(HostFacts(None, None, None), demand).max_concurrent == 0
    # Pure: same input, same answer.
    assert admit_concurrency(host, gpu_demand) == admit_concurrency(host, gpu_demand)


def test_local_host_observation_reports_gpus_as_not_observed(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       16384 kB\nMemFree: 1 kB\n")
    facts = observe_local_host(meminfo)
    assert facts.memory_bytes == 16384 * 1024 and facts.gpus is None
    assert facts.cpu_count and facts.cpu_count >= 1
    assert observe_local_host(tmp_path / "absent").memory_bytes is None


def test_capability_summary_reports_runpod_credential_state(tmp_path):
    missing = capability_summary(runpod_key_file=None)
    runpod = missing["providers"][0]
    assert (runpod["id"], runpod["available"], runpod["reason"]) == (
        "runpod",
        False,
        "credential_not_configured",
    )
    configured = capability_summary(runpod_key_file=key_file(tmp_path))["providers"][0]
    assert configured["available"] is True
    assert configured["reason"] == "credential_configured_capacity_not_queried"
    user = missing["providers"][1]
    assert user["kind"] == "user_managed" and "terminate" not in user["capabilities"]
