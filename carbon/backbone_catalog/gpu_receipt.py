"""Per-runtime GPU receipts for catalog entries (U58, 2026-10-22).

A GPU build (`bundles/<id>/<runtime>/`, see `gpu_build`) is offered only with a receipt from a run on a GPU:
`receipts/<catalog_id>.<runtime>.json`. Two kinds, chosen by the entry, never by the receipt:

- `repeat` (the rule): a GPU smoke (the GPU was used, the build trains and predicts, finite) and a GPU-vs-GPU repeat
  that is byte-identical (`pairs` all `identical`, none `differ`). CPU-vs-GPU parity is not asked (owner).
- `smoke` (the explicit `SMOKE_ONLY` list below): the owner's decision of 2026-10-22: CNO1d uses an op with no
  deterministic CUDA implementation (the backward of the bicubic upsample), so it gets the GPU smoke only.
  Its receipt says so and claims nothing about reproducibility.

The schema is `carbon.backbone-catalog-pair-identity.v1` with `runtime_profile_id`, `tested_on` (the GPU host and
driver), `image_digest`, `kind` and, for `smoke`, the fixed note.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECEIPTS = HERE / "receipts"
SCHEMA = "carbon.backbone-catalog-pair-identity.v1"
CARD_NOTE = "GPU practice only; official grading rebuilds on CPU"
SMOKE_NOTE = "smoke only: not bit-reproducible on GPU (no deterministic CUDA implementation of the upsample backward)"
#: The entries that get the smoke receipt instead of repeat identity: a short explicit list, not a skip.
SMOKE_ONLY = {
    "cno.CNO1d": SMOKE_NOTE,
}


class GpuReceiptBroken(ValueError):
    """A GPU receipt disagrees with the entry, its runtime or the rule for its kind."""


def required_kind(catalog_id: str) -> str:
    return "smoke" if catalog_id in SMOKE_ONLY else "repeat"


def path(catalog_id: str, runtime: str) -> Path:
    return RECEIPTS / f"{catalog_id}.{runtime}.json"


def check(receipt, catalog_id: str, runtime: str) -> None:
    """Refuse a receipt that does not prove what this entry's kind requires."""
    where = f"{catalog_id} {runtime}"
    if type(receipt) is not dict or receipt.get("schema") != SCHEMA:
        raise GpuReceiptBroken(f"{where}: receipt schema differs")
    if (
        receipt.get("catalog_id") != catalog_id
        or receipt.get("runtime_profile_id") != runtime
    ):
        raise GpuReceiptBroken(f"{where}: receipt is for another entry or runtime")
    kind = required_kind(catalog_id)
    if receipt.get("kind") != kind:
        raise GpuReceiptBroken(
            f"{where}: needs a {kind} receipt, has {receipt.get('kind')!r}"
        )
    image = receipt.get("image_digest")
    if image is None:
        # No GPU worker image exists yet (the bundles bind the pinned lock, not an image): the run is named by its
        # environment instead, and the receipt is to be repeated on the image once it is built.
        if type(receipt.get("environment")) is not str or not receipt["environment"]:
            raise GpuReceiptBroken(
                f"{where}: neither an image digest nor an environment"
            )
    elif type(image) is not str or not image.startswith("sha256:") or len(image) != 71:
        raise GpuReceiptBroken(f"{where}: no image digest")
    if not receipt.get("gpu_used") or not receipt.get("tested_on"):
        raise GpuReceiptBroken(f"{where}: not a run on a GPU")
    if not receipt.get("smoke_ok"):
        raise GpuReceiptBroken(f"{where}: the GPU smoke did not pass")
    if kind == "smoke":
        if receipt.get("note") != SMOKE_ONLY[catalog_id]:
            raise GpuReceiptBroken(
                f"{where}: a smoke receipt must carry the fixed note"
            )
        if receipt.get("pairs") not in (None, 0):
            raise GpuReceiptBroken(f"{where}: a smoke receipt claims no repeat")
        return
    pairs, identical = receipt.get("pairs"), receipt.get("identical")
    if (
        type(pairs) is not int
        or pairs < 1
        or identical != pairs
        or receipt.get("differ") != []
    ):
        raise GpuReceiptBroken(f"{where}: the GPU repeat is not byte-identical")


def load(catalog_id: str, runtime: str):
    """The receipt, or None when the GPU build has none yet (it is then not offered)."""
    target = path(catalog_id, runtime)
    if not target.exists():
        return None
    receipt = json.loads(target.read_bytes())
    check(receipt, catalog_id, runtime)
    return receipt


def offered_runtimes(item) -> list:
    """The GPU runtimes of an entry that may be listed: those with a valid receipt. CNO1d's warn-only GPU twin is
    offered for practice on its smoke receipt (OWNER-CATALOG-CNO1D-WARN-ONLY-01); the official route refuses it.
    """
    return [
        runtime
        for runtime in sorted(item.get("bundle_refs") or {})
        if load(item["catalog_id"], runtime)
    ]


def make(
    catalog_id: str,
    runtime: str,
    *,
    image_digest,
    tested_on,
    gpu_used,
    smoke_ok,
    pairs=0,
    identical=0,
    differ=(),
    environment=None,
):
    """A receipt from a Test Lead GPU run (`gpu_repeat.py compare`): `pairs`/`identical` count the cross-run repeat."""
    kind = required_kind(catalog_id)
    receipt = {
        "schema": SCHEMA,
        "catalog_id": catalog_id,
        "runtime_profile_id": runtime,
        "kind": kind,
        "image_digest": image_digest,
        "tested_on": tested_on,
        "gpu_used": bool(gpu_used),
        "smoke_ok": bool(smoke_ok),
    }
    if environment is not None:
        receipt["environment"] = environment
    if kind == "smoke":
        receipt["note"] = SMOKE_ONLY[catalog_id]
    else:
        receipt.update(pairs=pairs, identical=identical, differ=sorted(differ))
    check(receipt, catalog_id, runtime)
    return receipt


# --- the official route (Validator ruling, 2026-10-22) ---------------------------------------------------------
#
# A receipt from a run in a plain venv proves repeatability in that venv only, so it backs PRACTICE offering. A GPU build
# is officially gradable only with a `repeat` receipt that carries the pinned GPU worker image digest, the full determinism
# environment the official worker runs under, and a host of a registered class. Neither registry exists until the image is
# built and the two-host check (the Validator's GPU host-class decision) is done, so until the Validator fills them every GPU ref is
# refused officially.

#: runtime -> the worker image digests the official route accepts (filled by the Validator when the image is registered).
PINNED_GPU_IMAGES: dict = {}
#: the registered validator GPU host classes (filled by the Validator after the two-host check).
REGISTERED_HOST_CLASSES: frozenset = frozenset()


def required_determinism(runtime: str):
    """The full determinism environment an official run carries, as a JSON-comparable value."""
    from carbon.reconstruction import torch_profile
    from carbon.reconstruction.accelerators import (
        GPU_DETERMINISM_ENVIRONMENT,
        GPU_DETERMINISM_XLA_FLAGS,
    )

    if runtime == "torch-cu130-py311":
        return [[key, value] for key, value in torch_profile.GPU_DETERMINISM]
    if runtime == "jax-cuda13-py311":
        return {
            **GPU_DETERMINISM_ENVIRONMENT,
            "XLA_FLAGS": " ".join(GPU_DETERMINISM_XLA_FLAGS),
        }
    raise GpuReceiptBroken(f"no determinism environment for {runtime}")


def official_grade_problem(receipt, runtime: str):
    """Why this receipt does not back an official rebuild, or None when it does."""
    if receipt is None:
        return "it has no receipt"
    if receipt.get("kind") != "repeat":
        return "its receipt is smoke only"
    image = receipt.get("image_digest")
    if image is None or image not in PINNED_GPU_IMAGES.get(runtime, ()):
        return "its receipt is not on the pinned GPU worker image"
    if receipt.get("determinism") != required_determinism(runtime):
        return "its receipt does not carry the full determinism environment"
    if receipt.get("host_class") not in REGISTERED_HOST_CLASSES:
        return "its receipt is not from a registered host class"
    return None
