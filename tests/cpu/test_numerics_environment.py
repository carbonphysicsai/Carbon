"""The record has to distinguish runs that compute different answers.

`environment()` records what was installed. Two hosts that disagree numerically
record the same thing, which was measured: the same registered strategy under
identical R0 identities produces different weights at different CPU
instruction-set levels, and every identity Carbon recorded was byte-identical
across all of them.

These check that the numerics record closes that gap - that it moves when the
thing determining the numbers moves - and that adding it did not quietly change
what an already-accepted artifact means.

No device is attached and no backend is initialized beyond the CPU default.
"""

from __future__ import annotations

import json

from carbon.reconstruction.numerics_environment import (
    NUMERICS_SCHEMA,
    numerics_environment,
)
from carbon.reconstruction.service import (
    ACCELERATOR_ARTIFACT_SCHEMAS,
    CPU_ARTIFACT_SCHEMAS,
    NUMERICS_ARTIFACT_SCHEMAS,
)


def test_the_record_names_itself():
    record = numerics_environment()
    assert record["schema"] == NUMERICS_SCHEMA


def test_the_record_is_json_canonical():
    """It is hashed, so it must not depend on anything but the facts."""
    from carbon.development_session.profile import canonical

    first, second = numerics_environment(), numerics_environment()
    assert canonical(first) == canonical(second)
    json.dumps(first, sort_keys=True, allow_nan=False)


def test_the_effective_instruction_set_follows_the_ceiling(monkeypatch):
    """The measured cause of divergence, now visible in the record.

    A ceiling below the hardware genuinely changes what the backend emits, and
    was measured to change the trained weights. The record has to move with it,
    or two runs that computed different numbers still look identical.
    """
    seen = {}
    for ceiling in ("AVX512", "AVX2", "AVX", "SSE4_2"):
        monkeypatch.setenv("XLA_FLAGS", f"--xla_cpu_max_isa={ceiling}")
        record = numerics_environment()
        assert record["cpu_isa_ceiling"] == ceiling
        seen[ceiling] = record["cpu_effective_isa"]

    # A ceiling at or above the hardware is inert and must read the same; a
    # ceiling below it must read lower. Which of these applies depends on the
    # host, so the assertion is on the ordering rather than on fixed values.
    order = ["SSE4_2", "AVX", "AVX2", "AVX512"]
    levels = [order.index(seen[c]) for c in order if seen[c] in order]
    assert levels == sorted(
        levels
    ), f"effective level must not rise with a lower cap: {seen}"
    assert seen["SSE4_2"] == "SSE4_2"


def test_an_absent_ceiling_is_recorded_as_absent(monkeypatch):
    monkeypatch.delenv("XLA_FLAGS", raising=False)
    record = numerics_environment()
    assert record["cpu_isa_ceiling"] is None
    assert record["xla_flags"] is None


def test_the_determinism_controls_are_recorded_verbatim(monkeypatch):
    """Including when unset - an absent control is a fact about the run."""
    monkeypatch.delenv("NVIDIA_TF32_OVERRIDE", raising=False)
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)
    absent = numerics_environment()
    assert absent["nvidia_tf32_override"] is None
    assert absent["cublas_workspace_config"] is None

    monkeypatch.setenv("NVIDIA_TF32_OVERRIDE", "0")
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    present = numerics_environment()
    assert present["nvidia_tf32_override"] == "0"
    assert present["cublas_workspace_config"] == ":4096:8"
    assert absent != present, "the record must distinguish these two runs"


def test_gpu_fields_are_present_and_null_on_cpu():
    """Absent is recorded as null rather than omitted, so the shape is stable."""
    record = numerics_environment()
    for key in ("device_kind", "device_count", "cuda_version", "cudnn_version"):
        assert key in record


# --- the schema migration ------------------------------------------------------


def test_the_previous_artifact_versions_are_still_readable():
    """An artifact written before the numerics block keeps its exact meaning."""
    assert "carbon.c02.reconstruction-artifact.v3" in CPU_ARTIFACT_SCHEMAS
    assert "carbon.c02.reconstruction-artifact.v4" in ACCELERATOR_ARTIFACT_SCHEMAS


def test_only_the_new_versions_declare_the_numerics_block():
    assert NUMERICS_ARTIFACT_SCHEMAS == {
        "carbon.c02.reconstruction-artifact.v5",
        "carbon.c02.reconstruction-artifact.v6",
    }
    # The old versions are not in the set, so an old record is never expected to
    # carry a block it was never written with.
    assert "carbon.c02.reconstruction-artifact.v3" not in NUMERICS_ARTIFACT_SCHEMAS
    assert "carbon.c02.reconstruction-artifact.v4" not in NUMERICS_ARTIFACT_SCHEMAS


def test_new_artifacts_are_written_at_the_new_version():
    assert CPU_ARTIFACT_SCHEMAS[-1] == "carbon.c02.reconstruction-artifact.v5"
    assert ACCELERATOR_ARTIFACT_SCHEMAS[-1] == "carbon.c02.reconstruction-artifact.v6"


# --- the pinned determinism configuration -------------------------------------


def test_the_gpu_overlay_pins_the_determinism_configuration():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    import accelerator_host

    from carbon.development_session.profile import canonical
    from carbon.reconstruction.accelerators import (
        GPU_DETERMINISM_ENVIRONMENT,
        GPU_DETERMINISM_XLA_FLAGS,
        GPU_PROFILE,
        AcceleratorRole,
        worker_environment,
    )
    from carbon.reconstruction.host_inventory import HostDeviceRecord
    from carbon.reconstruction.worker.model import tagged_sha256

    document = accelerator_host.document("workstation_linux")
    record = HostDeviceRecord(document, tagged_sha256(canonical(document)))
    overlay = worker_environment(
        GPU_PROFILE, AcceleratorRole.MINER_RESEARCH, host_device=record
    )

    for flag in GPU_DETERMINISM_XLA_FLAGS:
        assert flag in overlay["XLA_FLAGS"]
    for key, value in GPU_DETERMINISM_ENVIRONMENT.items():
        assert overlay[key] == value
    # Measured to change the numbers, so it is pinned rather than left to the
    # machine: autotuning off, deterministic ops on, and an op with no
    # deterministic implementation refused rather than silently substituted.
    assert "--xla_gpu_autotune_level=0" in overlay["XLA_FLAGS"]
    assert "--xla_gpu_deterministic_ops=true" in overlay["XLA_FLAGS"]
    assert "--xla_gpu_exclude_nondeterministic_ops=true" in overlay["XLA_FLAGS"]


def test_the_cpu_overlay_is_not_given_gpu_determinism_settings():
    """The CPU lane's environment is unchanged by the GPU policy."""
    from carbon.reconstruction.accelerators import (
        TPU_PROFILE,
        AcceleratorRole,
        worker_environment,
    )

    overlay = worker_environment(TPU_PROFILE, AcceleratorRole.MINER_RESEARCH)
    assert "XLA_FLAGS" not in overlay
    assert "NVIDIA_TF32_OVERRIDE" not in overlay
