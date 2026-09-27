"""Concurrency admission derived from observed host facts.

:func:`admit_concurrency` is a pure function: the same facts and demand give
the same answer, and nothing in it is a hard-coded worker count. Observation is
separate (:func:`observe_local_host`) and distinguishes "not observed" (``None``)
from "observed zero"; a GPU demand against unobserved GPU facts admits nothing
rather than guessing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "AdmissionDecision",
    "GpuFact",
    "HostFacts",
    "WorkloadDemand",
    "admit_concurrency",
    "observe_local_host",
]


@dataclass(frozen=True)
class GpuFact:
    memory_bytes: int


@dataclass(frozen=True)
class HostFacts:
    cpu_count: int | None
    memory_bytes: int | None
    gpus: tuple[GpuFact, ...] | None  # None: not observed


@dataclass(frozen=True)
class WorkloadDemand:
    cpus: float
    memory_bytes: int
    gpus: int = 0
    gpu_memory_bytes: int = 0

    def __post_init__(self) -> None:
        if self.cpus <= 0 or self.memory_bytes <= 0 or self.gpus < 0:
            raise ValueError("demand must be positive")
        if self.gpu_memory_bytes and not self.gpus:
            raise ValueError("gpu memory demand without a GPU")


@dataclass(frozen=True)
class AdmissionDecision:
    max_concurrent: int
    limiting: str
    per_resource: tuple[tuple[str, int], ...]


def admit_concurrency(
    facts: HostFacts,
    demand: WorkloadDemand,
    *,
    reserve_cpus: float = 1.0,
    reserve_memory_bytes: int = 2 * 1024**3,
) -> AdmissionDecision:
    """How many copies of ``demand`` fit on the host after a reserve for Carbon itself."""

    limits: list[tuple[str, int]] = []
    if facts.cpu_count is None:
        limits.append(("cpu_not_observed", 0))
    else:
        usable = max(0.0, facts.cpu_count - reserve_cpus)
        limits.append(("cpu", int(usable // demand.cpus)))
    if facts.memory_bytes is None:
        limits.append(("memory_not_observed", 0))
    else:
        usable_mem = max(0, facts.memory_bytes - reserve_memory_bytes)
        limits.append(("memory", usable_mem // demand.memory_bytes))
    if demand.gpus:
        if facts.gpus is None:
            limits.append(("gpu_not_observed", 0))
        else:
            fitting = sum(
                1 for gpu in facts.gpus if gpu.memory_bytes >= demand.gpu_memory_bytes
            )
            limits.append(("gpu", fitting // demand.gpus))
    limiting, count = min(limits, key=lambda item: item[1])
    return AdmissionDecision(max(0, int(count)), limiting, tuple(limits))


def observe_local_host(meminfo: Path = Path("/proc/meminfo")) -> HostFacts:
    """CPU and memory of this host. GPUs are not probed here: ``gpus=None``."""

    cpus = (
        len(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else os.cpu_count()
    )
    memory = None
    try:
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemTotal:"):
                memory = int(line.split()[1]) * 1024
                break
    except (OSError, ValueError, IndexError):
        memory = None
    return HostFacts(cpu_count=cpus, memory_bytes=memory, gpus=None)
