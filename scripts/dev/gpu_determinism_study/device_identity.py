"""Which physical device produced this result?

Stage A compares two devices in one chassis, so every digest has to be
attributable to a named device. Nothing in the pinned image can do that on its
own:

- `nvidia-smi` is absent, so the runner's original UUID lookup cannot run.
- **JAX exposes no device identity.** A CUDA device object carries `id` (an
  index), `device_kind` (a model name) and nothing resembling a UUID, PCI
  address or serial. Checked directly: the identity-ish attribute set is empty.

So JAX can *target* device 0 or 1 and cannot *name* either. A study that recorded
"device 0" and "device 1" would be recording two indices whose mapping to
hardware is not preserved anywhere, which is not an answer to a per-device
question.

`libnvidia-ml.so` is present in the container when a device is attached - the
driver library is mounted even though the CLI built on it is not - so this reads
the UUID through it with `ctypes`, needing nothing installed.

`STUDY_DEVICE_UUID` overrides, for the case where the identity is already known
from outside and the operator would rather state it than have it read.

    python device_identity.py            # every visible device
    python device_identity.py 0          # one, by index
"""

from __future__ import annotations

import ctypes
import json
import os
import sys

# Tried in order. The first is where a normal Linux host and the NVIDIA
# container runtime put it; the second is WSL, where the driver is mounted from
# the Windows host under a generated directory name.
CANDIDATES = (
    "libnvidia-ml.so.1",
    "libnvidia-ml.so",
    "/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1",
)
WSL_DRIVERS = "/usr/lib/wsl/drivers"


def _library():
    names = list(CANDIDATES)
    if os.path.isdir(WSL_DRIVERS):
        for root, _dirs, files in os.walk(WSL_DRIVERS):
            names.extend(
                os.path.join(root, name)
                for name in files
                if name.startswith("libnvidia-ml.so")
            )
    for name in names:
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    return None


def device_uuids() -> list[dict]:
    """UUID and name per visible device, in JAX's index order.

    NVML enumerates the devices this process can see, which under
    `CUDA_VISIBLE_DEVICES` is the same set and order JAX reports - so index `i`
    here is JAX's device `i`.
    """
    library = _library()
    if library is None:
        return []
    if library.nvmlInit_v2() != 0:
        return []
    try:
        # The host's driver build. Read here rather than in its own function
        # because NVML requires nvmlInit first, and a call made outside this
        # block returns nothing while looking exactly like an unreadable driver.
        #
        # The acceptance requires the driver build recorded per device and
        # confirmed matching across compared units. In one chassis it is a
        # host-level property, so one read describes both devices - but it is
        # attached to each and reported rather than assumed, because "same
        # chassis therefore same driver" is the kind of inference this study
        # exists to avoid.
        driver = ctypes.create_string_buffer(96)
        build = (
            driver.value.decode("ascii", "replace")
            if library.nvmlSystemGetDriverVersion(driver, 96) == 0
            else None
        )
        count = ctypes.c_uint()
        if library.nvmlDeviceGetCount_v2(ctypes.byref(count)) != 0:
            return []
        devices = []
        for index in range(count.value):
            handle = ctypes.c_void_p()
            if library.nvmlDeviceGetHandleByIndex_v2(index, ctypes.byref(handle)) != 0:
                continue
            uuid = ctypes.create_string_buffer(96)
            name = ctypes.create_string_buffer(96)
            got_uuid = library.nvmlDeviceGetUUID(handle, uuid, 96) == 0
            got_name = library.nvmlDeviceGetName(handle, name, 96) == 0
            devices.append(
                {
                    "index": index,
                    # Absent rather than fabricated. A caller that needs a name
                    # and finds None must refuse, not invent one.
                    "uuid": uuid.value.decode("ascii", "replace") if got_uuid else None,
                    "name": name.value.decode("ascii", "replace") if got_name else None,
                    "driver_version": build,
                }
            )
        return devices
    finally:
        library.nvmlShutdown()


def main(argv: list[str]) -> int:
    override = os.environ.get("STUDY_DEVICE_UUID")
    devices = device_uuids()
    if override and not devices:
        devices = [{"index": 0, "uuid": override, "name": None, "source": "override"}]
    if not devices:
        print(
            "no device identity available: libnvidia-ml could not be loaded and "
            "STUDY_DEVICE_UUID is unset. A per-device study cannot name its "
            "devices, so this is a refusal rather than a warning.",
            file=sys.stderr,
        )
        return 1
    if len(argv) > 1:
        index = int(argv[1])
        match = [d for d in devices if d["index"] == index]
        if not match:
            print(f"no device at index {index}", file=sys.stderr)
            return 1
        devices = match
    print(json.dumps(devices, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
