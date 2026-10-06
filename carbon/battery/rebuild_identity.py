"""Which worker image and device class rebuilt a scored model (TORCH-GPU-01).

The Test Lead's condition on battery implementation 2.0: CPU and GPU rebuilds
of one recipe produce different numbers, so every score record carries the
worker image that rebuilt the model and its device class, and scores from
different device classes are never ranked or compared together - not in
nomination, the incumbent comparison, finals, or any report. This is what
keeps OWNER-SHARED-ANSWER-KEY-01's "a CPU rebuild is not a scored result"
enforceable: a GPU-scored leader is never decided against a CPU-scored one.

A device class is `cpu`, or `gpu:<device name>` as the rebuilding framework
reports it (for example `gpu:NVIDIA A40`).

**Versioned.** A score record made before this field existed carries no
`rebuild` identity. It keeps its meaning: every validator rebuild then ran on
the CPU (the validator's accelerator dispatch is disabled and PyTorch had no
CUDA path before implementation 2.0), so such a record reads as `cpu` with
its worker image unrecorded (`LEGACY_SCHEMA`). Nothing is rewritten.

Pure data and the standard library: importing this module initializes no
numerical runtime.
"""

from __future__ import annotations

import re

SCHEMA = "carbon.battery.rebuild-identity.v1"
LEGACY_SCHEMA = "carbon.battery.rebuild-identity.legacy-cpu"
CPU = "cpu"
_GPU = re.compile(r"gpu:[A-Za-z0-9][A-Za-z0-9 ._()-]{0,95}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class DeviceClassMixed(ValueError):
    """Scores from different device classes were put into one comparison."""

    def __init__(self, classes):
        super().__init__("device classes differ: " + ", ".join(sorted(classes)))
        self.classes = tuple(sorted(classes))


def valid_class(value) -> bool:
    return value == CPU or (type(value) is str and _GPU.fullmatch(value) is not None)


def from_reconstruction(reconstruction) -> dict:
    """The rebuild identity of a retained model, from what its rebuild
    recorded: the backend identity (`image`, and `pytorch_image` for a
    PyTorch rebuild) and the fit statistics (`device_class` on a GPU)."""
    reconstruction = reconstruction if type(reconstruction) is dict else {}
    fit = reconstruction.get("fit") if type(reconstruction.get("fit")) is dict else {}
    key = "pytorch_image" if fit.get("backend") == "pytorch" else "image"
    image = reconstruction.get(key)
    device_class = fit.get("device_class", CPU)
    if not valid_class(device_class):
        raise ValueError("unrecognised device class")
    return {
        "schema": SCHEMA,
        "worker_image": (
            image if type(image) is str and _DIGEST.fullmatch(image) else None
        ),
        "device_class": device_class,
    }


def of(record) -> dict:
    """A score record's rebuild identity, or the legacy CPU identity for a
    record made before the field existed."""
    found = record.get("rebuild") if type(record) is dict else None
    if found is None:
        return {"schema": LEGACY_SCHEMA, "worker_image": None, "device_class": CPU}
    if (
        type(found) is not dict
        or found.get("schema") != SCHEMA
        or not valid_class(found.get("device_class"))
    ):
        raise ValueError("malformed rebuild identity")
    return found


def device_class(record) -> str:
    return of(record)["device_class"]


def require_one_class(records) -> str:
    """The one device class of `records`, or `DeviceClassMixed`."""
    classes = {device_class(r) for r in records if r is not None}
    if len(classes) > 1:
        raise DeviceClassMixed(classes)
    return next(iter(classes), CPU)
