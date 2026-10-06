"""Which worker image and device class rebuilt a scored model (TORCH-GPU-01).

The Test Lead's condition on battery implementation 2.0: CPU and GPU rebuilds
of one recipe produce different numbers, so every score record carries the
worker image that rebuilt the model and its device class, and scores from
different device classes are never ranked or compared together - not in
nomination, the incumbent comparison, finals, or any report. This is what
keeps OWNER-SHARED-ANSWER-KEY-01's "a CPU rebuild is not a scored result"
enforceable: a GPU-scored leader is never decided against a CPU-scored one.

A device class is `cpu`, or `gpu:<device kind>` (for example
`gpu:NVIDIA A40`). The device kind is the one the run was bound to from the
installed host record, the field JAX's GPU records already carry
(`device_kind`: `battery_gpu.backend_record`, the accelerator overlay's
`CARBON_ACCELERATOR_DEVICE_KIND`), and the rule is the same for every backend:
a JAX GPU score and a PyTorch GPU score of one device kind are one class, and
neither is ever compared with a CPU score.

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
#: A development record whose rebuild device was never recorded (a Graphite
#: pod record made before TORCH-GPU-01, which may have run on a GPU). It is
#: never compared with anything, not even another unrecorded record.
UNRECORDED = "unrecorded"
#: A synthetic dry-run pod (`graphite.pods`), which rebuilds nothing: its own
#: class, comparable only with other synthetic records.
SYNTHETIC = "synthetic"
_GPU = re.compile(r"gpu:[A-Za-z0-9][A-Za-z0-9 ._()-]{0,95}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class DeviceClassMixed(ValueError):
    """Scores from different device classes were put into one comparison."""

    def __init__(self, classes):
        super().__init__("device classes differ: " + ", ".join(sorted(classes)))
        self.classes = tuple(sorted(classes))


def valid_class(value) -> bool:
    return value in (CPU, UNRECORDED, SYNTHETIC) or (
        type(value) is str and _GPU.fullmatch(value) is not None
    )


def from_reconstruction(reconstruction) -> dict:
    """The rebuild identity of a retained model, from what its rebuild
    recorded, the same way for every backend: the backend identity (`image`,
    and `pytorch_image` for a PyTorch rebuild) and the device kind - from the
    backend identity (a GPU carrier names it, as JAX's GPU backend records
    do) or the fit statistics (a PyTorch GPU rebuild records it). Two that
    disagree are refused."""
    reconstruction = reconstruction if type(reconstruction) is dict else {}
    fit = reconstruction.get("fit") if type(reconstruction.get("fit")) is dict else {}
    key = "pytorch_image" if fit.get("backend") == "pytorch" else "image"
    image = reconstruction.get(key)
    kinds = {
        kind
        for kind in (reconstruction.get("device_kind"), fit.get("device_kind"))
        if kind is not None
    }
    if len(kinds) > 1:
        raise ValueError("the backend and the rebuild name different devices")
    device_class = "gpu:" + kinds.pop() if kinds else CPU
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
    """The one device class of `records`, or `DeviceClassMixed`. A record of
    the unrecorded class is never comparable, even with its own kind."""
    records = [r for r in records if r is not None]
    classes = {device_class(r) for r in records}
    if len(classes) > 1 or (UNRECORDED in classes and len(records) > 1):
        raise DeviceClassMixed(classes)
    return next(iter(classes), CPU)


def comparable(*records) -> bool:
    """Whether `records` may be ranked or compared together."""
    try:
        require_one_class(records)
    except DeviceClassMixed:
        return False
    return True


def of_bundle(bundle) -> dict:
    """The rebuild identity of a prediction bundle
    (`carbon.battery.value.experiment.member_bundle`): its backend identity
    and fit statistics, read as a retained model's are."""
    bundle = bundle if type(bundle) is dict else {}
    reconstruction = bundle.get("reconstruction")
    reconstruction = dict(reconstruction) if type(reconstruction) is dict else {}
    return from_reconstruction({**reconstruction, "fit": bundle.get("fit") or {}})


def bundles_class(bundles) -> str:
    """The one device class of a panel of prediction bundles that will be
    ranked against each other, or `DeviceClassMixed`."""
    return require_one_class([{"rebuild": of_bundle(b)} for b in bundles])


def from_runtime(runtime) -> dict:
    """The rebuild identity a pod program's `runtime.json` records (Graphite's
    pods): `cpu` for a CPU backend, `gpu:<device kind>` for one GPU kind, and
    the unrecorded class when the runtime names no backend or several kinds."""
    runtime = runtime if type(runtime) is dict else {}
    backend = runtime.get("backend") or runtime.get("default_backend")
    kinds = {
        d.get("kind") if type(d) is dict else d for d in runtime.get("devices") or []
    }
    if runtime.get("synthetic") is True and len(runtime) == 1:
        device_class = SYNTHETIC
    elif backend == "cpu":
        device_class = CPU
    elif backend == "gpu" and len(kinds) == 1 and type(next(iter(kinds))) is str:
        device_class = "gpu:" + next(iter(kinds))
    else:
        device_class = UNRECORDED
    if not valid_class(device_class):
        device_class = UNRECORDED
    return {"schema": SCHEMA, "worker_image": None, "device_class": device_class}
