"""LEVEL4-G5-LANE-MEMORY-01: the G5 compile lane's 8 GiB memory, and nothing else.

Security-sensitive (the C-03 worker sandbox); these tests are evidence for
the owner's review, not a security audit.

Claims tested:

1. The existing C-03 CPU profile is byte-identical: same id, same body, same
   digest as before this change (pinned).
2. The G5 profile differs from it only in memory (8 GiB, swap 0), its id and
   its resource-class digest; every other control in the body is equal.
3. The launch arguments differ only in `--memory`/`--memory-swap` and the
   policy label; `--network none` and every other flag are the same.
4. The real effective-controls inspection accepts each profile's own
   container and refuses a container whose memory is not its profile's
   (`WorkerCode.POLICY`), in both directions.
5. Only G5's provenance selects the G5 profile, and that provenance is
   `carbon.level4.compile.PROVENANCE`.
"""

from __future__ import annotations

import pytest
import scripted_docker
from test_c03_worker_contract import _image

from carbon.development_session import research_carrier as rc
from carbon.reconstruction.worker import docker_runtime
from carbon.reconstruction.worker.model import (
    G5_MEMORY_BYTES,
    G5_PROFILE_ID,
    MEMORY_BYTES,
    PROFILE_ID,
    WorkerCode,
    WorkerFailure,
)

#: The C-03 CPU profile's digest before LEVEL4-G5-LANE-MEMORY-01.
C03_CPU_DIGEST = (
    "sha256:0d1168fb5bbffde24617c54df2cedfcb092d73b97f88fa8aae400f430869347f"
)


def _profiles():
    return rc._worker_profile(None), rc._worker_profile(None, rc.G5_PROVENANCE)


def test_the_existing_profile_is_unchanged():
    default, _ = _profiles()
    assert default.profile_id == PROFILE_ID
    assert default.digest == C03_CPU_DIGEST
    assert default.body["memory"] == {"bytes": MEMORY_BYTES, "swap_bytes": 0}
    assert MEMORY_BYTES == 4 * 1024**3


def test_the_g5_profile_differs_only_in_memory():
    default, g5 = _profiles()
    assert g5.profile_id == G5_PROFILE_ID and g5.digest != default.digest
    assert g5.body["memory"] == {"bytes": G5_MEMORY_BYTES, "swap_bytes": 0}
    assert G5_MEMORY_BYTES == 8 * 1024**3

    def rest(body):
        out = {k: v for k, v in body.items() if k not in ("memory", "profile_id")}
        out["b02c"] = {
            k: v for k, v in body["b02c"].items() if k != "resource_class_digest"
        }
        return out

    assert rest(g5.body) == rest(default.body)


def _arguments(profile, tmp_path):
    return docker_runtime.create_arguments(
        container_name="c03-test",
        image_id=_image().image_id,
        input_directory=tmp_path,
        cpuset="0-1",
        launch_digest="sha256:" + "1" * 64,
        worker_profile=profile,
    )


def test_launch_arguments_differ_only_in_memory(tmp_path):
    default, g5 = _profiles()
    a, b = _arguments(default, tmp_path), _arguments(g5, tmp_path)
    assert len(a) == len(b)
    changed = {i for i, (x, y) in enumerate(zip(a, b)) if x != y}
    names = {a[i - 1] for i in changed}
    assert names == {"--memory", "--memory-swap", "--label"}
    assert all(b[i] == str(G5_MEMORY_BYTES) for i in changed if a[i - 1] != "--label")
    assert "--network" in b and b[b.index("--network") + 1] == "none"


def _inspect(profile, created_with, tmp_path):
    cli = scripted_docker.ScriptedDocker(image=_image(), stage=tmp_path)
    cli.create_arguments = _arguments(created_with, tmp_path)
    cli.started = True
    return docker_runtime.inspect_effective_controls(
        cli=cli,
        container_name="c03-test",
        image_id=_image().image_id,
        input_directory=tmp_path,
        cpuset="0-1",
        launch_digest="sha256:" + "1" * 64,
        worker_profile=profile,
    )


def test_inspection_enforces_the_launching_profiles_memory(tmp_path):
    default, g5 = _profiles()
    _inspect(default, default, tmp_path)
    _inspect(g5, g5, tmp_path)
    for expected, created in ((g5, default), (default, g5)):
        with pytest.raises(WorkerFailure) as refused:
            _inspect(expected, created, tmp_path)
        assert refused.value.code == WorkerCode.POLICY


def test_only_g5_provenance_selects_the_g5_profile():
    from carbon.level4 import compile as g5_compile

    assert rc.G5_PROVENANCE == g5_compile.PROVENANCE
    for provenance in (None, "MINER_SELF_REPORTED", "CARBON_PRACTICE", "level4"):
        assert rc._worker_profile(None, provenance).profile_id == PROFILE_ID
    assert rc._worker_profile(None, rc.G5_PROVENANCE).profile_id == G5_PROFILE_ID
