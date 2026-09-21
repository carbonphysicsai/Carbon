"""What determines the numbers, as distinct from what happens to be installed.

`environment()` records the installed software: versions, backend, platform. That
is what a run *was built from*, and it is the right record for compatibility. It
is not enough to tell two runs apart when they compute different answers.

Measured under C-CORE-19: the same registered strategy, under identical R0
identities, produces different trained weights at different CPU instruction-set
levels - and `environment()` is byte-identical across every one of them. Two
hosts that disagree numerically record the same environment, so nothing in the
evidence distinguishes them.

On a GPU the same problem is worse rather than better. Autotuning selects kernels
per device and sometimes per run, streaming-multiprocessor count changes how
reductions are split, atomics have no fixed order, and TF32 silently drops
mantissa bits on matmuls from Ampere onward. None of that appears in a version
list either.

This module records the missing half. It is descriptive only: it changes no
execution, pins nothing, and enabling determinism is `worker_environment`'s job.
Its single purpose is that a record which could have diverged says how.

**Unknown is recorded as unknown.** Every value here is read from the running
process or the host, and anything that cannot be read becomes `None` rather than
a default. A guess would be worse than a gap, because a gap is visible.
"""

from __future__ import annotations

import os
import re

NUMERICS_SCHEMA = "carbon.reconstruction.numerics-environment.v1"

# Ordered weakest to strongest. The effective level is the strongest the hardware
# advertises, capped by any XLA instruction-set ceiling in force - because a cap
# genuinely changes the emitted code, which is the whole reason this is recorded.
_ISA_ORDER = ("SSE4_2", "AVX", "AVX2", "AVX512")
_ISA_CPUINFO_FLAG = {
    "SSE4_2": "sse4_2",
    "AVX": "avx",
    "AVX2": "avx2",
    "AVX512": "avx512f",
}
_MAX_ISA = re.compile(r"--xla_cpu_max_isa=([A-Za-z0-9_]+)")


def _cpu_flags() -> set[str] | None:
    try:
        with open("/proc/cpuinfo", encoding="ascii", errors="replace") as handle:
            for line in handle:
                if line.startswith(("flags", "Features")):
                    return set(line.split(":", 1)[1].split())
    except OSError:
        return None
    return None


def _hardware_isa(flags: set[str] | None) -> str | None:
    if flags is None:
        return None
    best = None
    for name in _ISA_ORDER:
        if _ISA_CPUINFO_FLAG[name] in flags:
            best = name
    return best


def _effective_isa(xla_flags: str | None) -> tuple[str | None, str | None]:
    """The instruction set the backend may actually emit, and the cap if any."""
    hardware = _hardware_isa(_cpu_flags())
    cap = None
    if xla_flags:
        match = _MAX_ISA.search(xla_flags)
        if match:
            cap = match.group(1).upper()
    if cap is None or hardware is None:
        return hardware, cap
    if cap not in _ISA_ORDER:
        # An unrecognised ceiling is reported as given rather than normalised
        # away; it still changed what the backend was allowed to emit.
        return hardware, cap
    effective = min(hardware, cap, key=_ISA_ORDER.index)
    return effective, cap


def _accelerator_numerics() -> dict[str, object]:
    """Device-side facts, read from the live backend. Absent means unread."""
    import jax

    record: dict[str, object] = {
        "device_kind": None,
        "device_count": None,
        "cuda_version": None,
        "cudnn_version": None,
        "driver_version": None,
    }
    try:
        devices = jax.devices()
    except Exception:  # noqa: BLE001 - an unreadable backend is recorded as such
        return record
    if devices:
        record["device_kind"] = getattr(devices[0], "device_kind", None)
        record["device_count"] = len(devices)
    try:
        import jaxlib

        versions = getattr(jaxlib, "cuda_versions", None)
        if versions is not None:
            for key, reader in (
                ("cuda_version", "cuda_runtime_get_version"),
                ("cudnn_version", "cudnn_get_version"),
                ("driver_version", "cuda_driver_get_version"),
            ):
                call = getattr(versions, reader, None)
                if callable(call):
                    try:
                        record[key] = int(call())
                    except Exception:  # noqa: BLE001
                        record[key] = None
    except Exception:  # noqa: BLE001
        # The version readers are optional and vary by plugin build. An
        # unreadable one leaves its field None, which is the recorded answer.
        return record
    return record


def numerics_environment() -> dict[str, object]:
    """The determinism-relevant facts about this process and this host.

    Deliberately flat and JSON-canonical: it is hashed alongside the installed
    environment, and a nested or order-dependent shape would make the digest
    depend on something other than the facts.
    """
    import jax

    xla_flags = os.environ.get("XLA_FLAGS")
    effective_isa, isa_cap = _effective_isa(xla_flags)
    try:
        backend = jax.default_backend()
    except Exception:  # noqa: BLE001
        backend = None

    record: dict[str, object] = {
        "schema": NUMERICS_SCHEMA,
        "backend": backend,
        # Verbatim. Normalising it would hide the difference between two hosts
        # that set the same flags in a different order, which is exactly the
        # kind of difference this exists to expose.
        "xla_flags": xla_flags,
        "cpu_effective_isa": effective_isa,
        "cpu_isa_ceiling": isa_cap,
        "default_matmul_precision": os.environ.get("JAX_DEFAULT_MATMUL_PRECISION"),
        # TF32 is the one that silently changes results rather than failing, so
        # both controls over it are recorded even when unset.
        "nvidia_tf32_override": os.environ.get("NVIDIA_TF32_OVERRIDE"),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
    }
    if backend == "gpu":
        record.update(_accelerator_numerics())
    else:
        record.update(
            {
                "device_kind": None,
                "device_count": None,
                "cuda_version": None,
                "cudnn_version": None,
                "driver_version": None,
            }
        )
    return record
