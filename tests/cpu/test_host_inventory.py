"""The host device record: portability without inventing hardware coverage.

These fixtures describe *shapes* of host - a laptop behind WSL2, a bare-metal
workstation, a hosted instance, a multi-device host - so the record format can
be shown to carry them without source edits. None of them asserts that Carbon
runs correctly on that hardware: no device is attached here, nothing is
dispatched, and installing a record qualifies nothing.

Synthetic roots throughout; the real host root is never touched.
"""

import accelerator_host
import pytest

from carbon.development_session.profile import canonical
from carbon.reconstruction.accelerators import GPU_PROFILE, TPU_PROFILE
from carbon.reconstruction.host_inventory import (
    HOST_DEVICE_RECORD,
    HostDeviceRecord,
    require_host_device,
)
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

# --- host shapes, written the way an operator tool would emit them ------------
#
# Each entry is a plausible *shape* of host. Carbon is not claimed to work on
# any of them; what is claimed is only that expressing them needs no source
# edit. The device UUIDs are synthetic.

_document = accelerator_host.document
_install = accelerator_host.install
HOSTS = accelerator_host.HOSTS


@pytest.fixture
def root(tmp_path):
    return tmp_path / "host"


# --- every shape installs and binds with no source edit -----------------------


@pytest.mark.parametrize("shape", sorted(accelerator_host.NVIDIA_SHAPES))
def test_each_host_shape_installs_and_binds(root, shape):
    """The portability claim: a different host is a different record, not a diff."""
    _install(root, _document(shape))
    record = HostDeviceRecord.load(root)
    bound = require_host_device(record, GPU_PROFILE)
    assert bound.device_uuid == HOSTS[shape]["device_uuid"]
    assert bound.device_kind == HOSTS[shape]["device_kind"]
    assert bound.provider == HOSTS[shape]["provider"]


def test_no_machine_specific_value_appears_in_the_workload_profile():
    """The profile must describe the work, not one person's hardware."""
    document = GPU_PROFILE.document()
    flattened = canonical(document).decode()
    for name in accelerator_host.NVIDIA_SHAPES:
        shape = HOSTS[name]
        for key in ("device_uuid", "device_kind", "driver_version"):
            assert (
                shape[key] not in flattened
            ), f"{key} for {shape['record_id']} leaked into the workload profile"
    assert "device_uuid" not in document
    assert "host_driver" not in document


def test_two_hosts_share_one_workload_profile_digest(root, tmp_path):
    """Comparability: the same work has the same identity on any host."""
    other = tmp_path / "other-host"
    _install(root, _document("laptop_wsl2"))
    _install(other, _document("workstation_linux"))
    first = HostDeviceRecord.load(root)
    second = HostDeviceRecord.load(other)
    assert first.digest != second.digest, "different hosts are different records"
    # The profile both bind to is unchanged, so runs stay comparable.
    assert require_host_device(first, GPU_PROFILE) is first
    assert require_host_device(second, GPU_PROFILE) is second


# --- a record is evidence, never authority ------------------------------------


def test_a_record_for_another_workload_profile_is_refused(root):
    _install(root, _document("laptop_wsl2", workload_profile_id=TPU_PROFILE.profile_id))
    record = HostDeviceRecord.load(root)
    with pytest.raises(WorkerFailure) as error:
        require_host_device(record, GPU_PROFILE)
    assert error.value.code is WorkerCode.POLICY


def test_a_missing_record_is_unavailable_not_guessed(root):
    root.mkdir(mode=0o700, parents=True)
    with pytest.raises(WorkerFailure) as error:
        HostDeviceRecord.load(root)
    assert error.value.code is WorkerCode.UNAVAILABLE


def test_a_world_readable_record_is_refused(root):
    path = _install(root, _document("laptop_wsl2"))
    path.chmod(0o644)
    with pytest.raises(WorkerFailure) as error:
        HostDeviceRecord.load(root)
    assert error.value.code is WorkerCode.UNAVAILABLE


def test_a_non_canonical_record_is_refused(root):
    root.mkdir(mode=0o700, parents=True)
    path = root / HOST_DEVICE_RECORD
    path.write_bytes(b'{ "schema": "carbon.accelerator-host-device.v1" }')
    path.chmod(0o600)
    with pytest.raises(WorkerFailure) as error:
        HostDeviceRecord.load(root)
    assert error.value.code is WorkerCode.UNAVAILABLE


def test_the_record_cannot_claim_its_own_authority(root):
    _install(
        root,
        _document("laptop_wsl2", observation_authority="EXCLUSIVE_DEVICE_VERIFIED"),
    )
    with pytest.raises(WorkerFailure) as error:
        HostDeviceRecord.load(root)
    assert error.value.code is WorkerCode.POLICY


# --- malformed and hostile values fail closed ---------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"device_uuid": ""},
        {"device_uuid": "GPU with spaces"},
        {"device_uuid": "$(id)"},
        {"device_uuid": "GPU-00000000-1111-2222-3333-444444444444\nextra"},
        {"device_kind": "rm -rf /; echo"},
        {"device_kind": "name\nwith-newline"},
        {"device_kind": ""},
        {"driver_version": "not-a-version"},
        {"driver_model": "UNKNOWN"},
        {"compute_capability": "8"},
        {"device_memory_mib": 0},
        {"device_memory_mib": -1},
        {"device_memory_mib": 6144.0},
        {"display_active": "Maybe"},
        {"platform": "MY_LAPTOP"},
        {"container_runtime": "PODMAN"},
        {"provider": "provider with spaces"},
        {"provider": "$(whoami)"},
        {"observed_at_unix": 0.0},
        {"observed_at_unix": -1.0},
        {"observed_at_unix": "yesterday"},
        {"observation_provenance": ""},
        {"observation_provenance": "line\nbreak"},
        {"observation_provenance": "back`tick`"},
        {"observation_provenance": "x" * 300},
        {"schema": "carbon.accelerator-host-device.v2"},
    ],
)
def test_malformed_values_are_refused(root, override):
    _install(root, _document("laptop_wsl2", **override))
    with pytest.raises(WorkerFailure):
        HostDeviceRecord.load(root)


@pytest.mark.parametrize(
    "identifier",
    [
        # Well formed as a device identifier, but not NVIDIA's UUID shape. The
        # vendor rule is applied where the workload's backend is known, so an
        # NVIDIA workload is no less strict than when the UUID was a constant.
        "GPU-not-a-uuid",
        "tpu-v5litepod-8:0",
        "GPU-00000000-1111-2222-3333-44444444444",
        "gpu-00000000-1111-2222-3333-444444444444",
        "GPU-0000000G-1111-2222-3333-444444444444",
    ],
)
def test_a_non_nvidia_identifier_cannot_bind_an_nvidia_workload(root, identifier):
    _install(root, _document("laptop_wsl2", device_uuid=identifier))
    record = HostDeviceRecord.load(root)
    with pytest.raises(WorkerFailure) as error:
        require_host_device(record, GPU_PROFILE)
    assert error.value.code is WorkerCode.POLICY


def test_a_non_finite_observation_time_is_refused(root):
    """Not reachable through a canonical file, so it is checked directly."""
    record = HostDeviceRecord(
        {**_document("laptop_wsl2"), "observed_at_unix": float("inf")}, _sha_like()
    )
    with pytest.raises(WorkerFailure) as error:
        record.validate()
    assert error.value.code is WorkerCode.POLICY


def _sha_like():
    return "sha256:" + "0" * 64


def test_extra_and_missing_fields_are_refused(root):
    _install(root, _document("laptop_wsl2", surprise="value"))
    with pytest.raises(WorkerFailure) as error:
        HostDeviceRecord.load(root)
    assert error.value.code is WorkerCode.POLICY

    trimmed = _document("laptop_wsl2")
    trimmed.pop("provider")
    _install(root, trimmed)
    with pytest.raises(WorkerFailure) as error:
        HostDeviceRecord.load(root)
    assert error.value.code is WorkerCode.POLICY


def test_binding_refuses_untyped_arguments(root):
    _install(root, _document("laptop_wsl2"))
    record = HostDeviceRecord.load(root)
    for bad in (None, "GPU_PROFILE", {}, 1):
        with pytest.raises(WorkerFailure):
            require_host_device(record, bad)
        with pytest.raises(WorkerFailure):
            require_host_device(bad, GPU_PROFILE)


def test_a_wddm_record_does_not_become_an_observation_contract(root):
    """A record states the driver model; it cannot establish enumeration."""
    from carbon.reconstruction.worker import accelerator_runtime as runtime

    _install(root, _document("laptop_wsl2"))
    record = HostDeviceRecord.load(root)
    assert record.driver_model == "WDDM"
    assert (
        runtime.enumeration_capability(record.driver_model)
        == runtime.ENUMERATION_UNSUPPORTED
    )
    # And a record claiming a compute-oriented driver model still does not
    # establish it, because no observation contract is registered.
    _install(root, _document("workstation_linux", driver_model="TCC"))
    other = HostDeviceRecord.load(root)
    assert (
        runtime.enumeration_capability(other.driver_model)
        != runtime.ENUMERATION_ESTABLISHED
    )
