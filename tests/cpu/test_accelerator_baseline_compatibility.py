"""Records accepted on main must still mean what they meant.

The portable-host change was the right direction and it rewrote accepted
contracts to get there. Four of them: the registered RTX-3060 profile was
replaced in `PROFILES` rather than retained beside the portable one; the common
profile body lost three serialized keys while still calling itself
`carbon.accelerator-profile.v1`, moving the TPU digest under an unchanged
profile id; the worker reader stopped accepting the three-field strict
accelerator block it had accepted under request v2; and the active-allocation
decoder began requiring an `authority` key that retained records do not carry.

Each one is a record that was written under one meaning and is read under
another. These fix the meanings in place.

The request fixture here is **bytes produced by main**, at
`0a9dbaaf8173ea039ad2e6b0aafb34539a642d50`, by that revision's own
`stage_request`. See `tests/fixtures/accelerator_baseline/README.md`. Two
constructors from the current implementation compared against each other would
prove nothing about historical compatibility, so none is used.

Retaining an interpretation is not permission to run it. The retained profile is
readable everywhere a record is read and refused everywhere execution is
decided, and that is asserted below.

Synthetic roots throughout. No device is attached and no container exists.
"""

import json
import shutil
from pathlib import Path

import pytest

from carbon.reconstruction.accelerators import (
    GPU_PROFILE,
    HISTORICAL_PROFILES,
    PROFILES,
    RTX3060_LAPTOP_PROFILE,
    TPU_PROFILE,
    AcceleratorRole,
    dispatchable,
    require_accelerator_admission,
    resolve_profile,
    worker_environment,
)
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    STRICT_HOST_GRANT_AUTHORITY,
    WorkerCode,
    WorkerFailure,
)

BASELINE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "accelerator_baseline"
    / "worker_request_v2_main"
)

# Recorded on main. Not recomputed here: recomputing an expected digest from the
# implementation under test is how a changed serialization is made to look
# unchanged.
MAIN_RTX3060_PROFILE_ID = "carbon_jax_cuda13_rtx3060_laptop_development_v1"
MAIN_RTX3060_DIGEST = (
    "sha256:8408adc8c7a3650bbbfb8d188be7dadae2df1e3c851f5b72a0e086bdcc012e79"
)
MAIN_TPU_PROFILE_ID = "carbon_jax_tpu_v5e_8_development_v1"
MAIN_TPU_DIGEST = (
    "sha256:b88d9f6f0ef2315e6f0ec40a834e8a1d7240488e644dd9f12157f9075eb8e9a9"
)


# --- 1. the retained profile ---------------------------------------------------


def test_the_replaced_gpu_profile_still_resolves():
    """A record naming it did not stop meaning what it meant."""
    profile = resolve_profile(MAIN_RTX3060_PROFILE_ID)
    assert profile is RTX3060_LAPTOP_PROFILE
    assert profile.profile_id == MAIN_RTX3060_PROFILE_ID


def test_the_retained_profile_keeps_the_digest_it_was_accepted_with():
    assert RTX3060_LAPTOP_PROFILE.digest == MAIN_RTX3060_DIGEST
    assert (
        RTX3060_LAPTOP_PROFILE.document()["schema"] == "carbon.accelerator-profile.v1"
    )


def test_the_retained_profile_is_readable_but_never_runnable():
    """Retention is interpretation. It is not an execution route."""
    assert RTX3060_LAPTOP_PROFILE in HISTORICAL_PROFILES
    assert RTX3060_LAPTOP_PROFILE not in PROFILES
    assert not dispatchable(RTX3060_LAPTOP_PROFILE)
    assert dispatchable(GPU_PROFILE) and dispatchable(TPU_PROFILE)

    for role in AcceleratorRole:
        with pytest.raises(ValueError):
            worker_environment(RTX3060_LAPTOP_PROFILE, role)


def test_the_portable_profile_did_not_inherit_the_retained_identity():
    """Two profiles, two identities. Neither stands in for the other."""
    assert GPU_PROFILE.profile_id != RTX3060_LAPTOP_PROFILE.profile_id
    assert GPU_PROFILE.digest != RTX3060_LAPTOP_PROFILE.digest


# --- 2. the serialized profile body -------------------------------------------


def test_the_tpu_profile_body_is_unchanged_under_its_unchanged_id():
    """Its id never changed, so its body must not have either."""
    assert TPU_PROFILE.profile_id == MAIN_TPU_PROFILE_ID
    assert TPU_PROFILE.digest == MAIN_TPU_DIGEST


def test_the_two_profile_shapes_are_separately_versioned():
    """A different body gets a different version, not the same one quietly."""
    pinned = RTX3060_LAPTOP_PROFILE.document()
    portable = GPU_PROFILE.document()
    assert pinned["schema"] == "carbon.accelerator-profile.v1"
    assert portable["schema"] == "carbon.accelerator-profile.v2"
    assert {"device_kind", "device_uuid", "host_driver"} <= set(pinned)
    assert not {"device_kind", "device_uuid", "host_driver"} & set(portable)


def test_the_portable_profile_names_no_host_hardware():
    """The reason the portable shape exists, asserted rather than assumed."""
    assert not GPU_PROFILE.host_pinned
    assert RTX3060_LAPTOP_PROFILE.host_pinned
    body = json.dumps(GPU_PROFILE.document())
    assert RTX3060_LAPTOP_PROFILE.device_uuid not in body
    assert "GPU-" not in body


# --- 3. the staged worker request main wrote ----------------------------------


@pytest.fixture
def staged(tmp_path):
    """The frozen main-written request, copied where the loader can read it."""
    destination = tmp_path / "stage"
    shutil.copytree(BASELINE, destination)
    return destination


def test_the_frozen_request_is_the_shape_main_wrote(staged):
    """Guards the fixture itself: if this changes, it was regenerated."""
    request = json.loads((staged / "request.json").read_bytes())
    assert request["schema"] == "carbon.c03.worker-request.v2"
    assert set(request["accelerator"]) == {"profile_id", "grant_digest", "role"}
    assert request["accelerator"]["profile_id"] == MAIN_RTX3060_PROFILE_ID


def test_the_frozen_request_still_loads_through_the_public_reader(staged):
    """The compatibility claim, driven end to end rather than at the decoder."""
    from carbon.reconstruction.worker.protocol import load_worker_request

    attempt, plan, archive, seed, split = load_worker_request(staged)
    assert plan is not None and archive is not None and seed is not None
    assert split is None
    assert attempt is not None


def test_the_frozen_request_decodes_to_a_strict_device_free_launch(staged):
    """Read as what it was, not upgraded and not reclassified."""
    from carbon.reconstruction.worker.protocol import _request_worker_profile

    request = json.loads((staged / "request.json").read_bytes())
    profile = _request_worker_profile(request)
    assert profile.accelerator_profile_id == MAIN_RTX3060_PROFILE_ID
    assert profile.accelerator_authority == STRICT_HOST_GRANT_AUTHORITY
    assert profile.accelerator_authority != LOCAL_DEVELOPMENT_AUTHORITY
    # It named no device, and it is not handed one now.
    assert profile.accelerator_device_uuid is None
    assert profile.accelerator_plan_digest is None


def test_a_local_block_cannot_be_presented_under_the_historical_schema(staged):
    """The pairing stays closed in both directions."""
    from carbon.reconstruction.worker.protocol import _permitted_request_schemas

    request = json.loads((staged / "request.json").read_bytes())
    assert request["schema"] in _permitted_request_schemas(request)

    local = {
        **request,
        "accelerator": {
            "profile_id": GPU_PROFILE.profile_id,
            "authority": LOCAL_DEVELOPMENT_AUTHORITY,
            "approval_digest": "sha256:" + "1" * 64,
            "diagnostic_plan_digest": "sha256:" + "2" * 64,
            "role": AcceleratorRole.MINER_RESEARCH.value,
            "device_uuid": RTX3060_LAPTOP_PROFILE.device_uuid,
        },
    }
    assert "carbon.c03.worker-request.v2" not in _permitted_request_schemas(local)


def test_the_historical_request_cannot_be_rewritten_into_a_development_one(staged):
    """A retained strict record must not become a development vehicle."""
    from carbon.reconstruction.worker.protocol import _request_worker_profile

    request = json.loads((staged / "request.json").read_bytes())
    forged = {
        **request,
        "schema": "carbon.c03.worker-request.v4",
        "accelerator": {
            "profile_id": MAIN_RTX3060_PROFILE_ID,
            "authority": LOCAL_DEVELOPMENT_AUTHORITY,
            "approval_digest": "sha256:" + "1" * 64,
            "diagnostic_plan_digest": "sha256:" + "2" * 64,
            "role": AcceleratorRole.MINER_RESEARCH.value,
            "device_uuid": RTX3060_LAPTOP_PROFILE.device_uuid,
        },
    }
    with pytest.raises(WorkerFailure):
        _request_worker_profile(forged)


def test_a_retained_profile_is_refused_where_execution_is_decided():
    """Loading a record is allowed. Admitting it to run is not."""
    for role in AcceleratorRole:
        with pytest.raises(ValueError, match="registered accelerator profile"):
            require_accelerator_admission(RTX3060_LAPTOP_PROFILE, role)


# --- 4. the retained active-allocation record ---------------------------------


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    return root


def _legacy_allocation(host, **overrides):
    """Exactly what main wrote: two fields, no authority."""
    from carbon.development_session.profile import canonical

    document = {
        "container_name": "carbon-c03-fixture",
        "launch_digest": "sha256:" + "3" * 64,
        **overrides,
    }
    path = host / "active-allocation.json"
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    return document


def test_a_retained_allocation_is_still_readable(host):
    """Refusing it strands a host that really does hold an allocation."""
    document = _legacy_allocation(host)
    assert runtime.owns_device_allocation(
        container_name=document["container_name"],
        launch_digest=document["launch_digest"],
    )


def test_a_retained_allocation_keeps_its_strict_obligation(host):
    """The direction that matters: it must not become a development record.

    A development allocation completes without claiming whole-device release. If
    a retained record were read as one, a strict cleanup obligation that was
    never satisfied would be discharged silently.
    """
    document = _legacy_allocation(host)
    authority = runtime.allocation_authority(
        container_name=document["container_name"],
        launch_digest=document["launch_digest"],
    )
    assert authority == STRICT_HOST_GRANT_AUTHORITY
    assert authority != LOCAL_DEVELOPMENT_AUTHORITY


def test_a_retained_allocation_is_not_owned_by_a_different_launch(host):
    document = _legacy_allocation(host)
    assert not runtime.owns_device_allocation(
        container_name="carbon-c03-other",
        launch_digest=document["launch_digest"],
    )
    assert (
        runtime.allocation_authority(
            container_name="carbon-c03-other",
            launch_digest=document["launch_digest"],
        )
        is None
    )


def test_an_unrecognised_allocation_shape_still_fails_closed(host):
    """Reading two known shapes is not reading anything at all."""
    for overrides in (
        {"unexpected": 1},
        {"authority": "SOMETHING_ELSE"},
    ):
        _legacy_allocation(host, **overrides)
        with pytest.raises(WorkerFailure) as failure:
            runtime.owns_device_allocation(
                container_name="carbon-c03-fixture",
                launch_digest="sha256:" + "3" * 64,
            )
        assert failure.value.code is WorkerCode.CLEANUP
