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
    # The same entry under its v2 ids (see `gpu_build.WARN_ONLY_DETERMINISM`).
    "v2.motor.cno.CNO1d": SMOKE_NOTE,
    "v2.cooling.cno.CNO1d": SMOKE_NOTE,
    "v2.f08.cno.CNO1d": SMOKE_NOTE,
    "v2.f02.cno.CNO1d": SMOKE_NOTE,
    # thuml.LSM (U-Net `nn.Upsample` linear backward), twinned under the same warn-only decision.
    "thuml.LSM": SMOKE_NOTE,
    "f08.thuml.LSM": SMOKE_NOTE,
    "v2.motor.thuml.LSM": SMOKE_NOTE,
    "v2.cooling.thuml.LSM": SMOKE_NOTE,
    "v2.f08.thuml.LSM": SMOKE_NOTE,
    "v2.f02.thuml.LSM": SMOKE_NOTE,
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
    # The official-route fields, when a receipt carries them, are well formed (their absence is a
    # practice-grade receipt, judged by `official_grade_problem`, not broken).
    if "host_class" in receipt and (
        type(receipt["host_class"]) is not str or not receipt["host_class"]
    ):
        raise GpuReceiptBroken(f"{where}: host_class is a non-empty name")
    if "determinism" in receipt and type(receipt["determinism"]) not in (dict, list):
        raise GpuReceiptBroken(
            f"{where}: determinism is the environment the run carried"
        )
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


#: The on-box store of OFFICIAL GPU receipts (`receipt_store.ReceiptStore`), set by the validator's composition.
#: None means there is none: the official route then reads only the repository receipts, which never qualify
#: (`official_grade_problem` needs a pinned image, the determinism environment and a registered host class).
OFFICIAL_STORE = None


def required_determinism_digest(runtime: str) -> str:
    """The digest an official record binds for the determinism environment the official worker runs under:
    sha256 of the canonical JSON of `required_determinism(runtime)`."""
    import hashlib

    raw = json.dumps(
        required_determinism(runtime), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def official_receipt(item, runtime: str, store=None):
    """The receipt-shaped view of the store's record in force for ``item``'s ``runtime`` build, or None.

    Never served from a store that fails verification (`GpuReceiptBroken`), nor for a record of another entry or
    bundle. The record's determinism digest becomes the full environment only when it IS the official one.
    """
    from . import receipt_store

    store = store or OFFICIAL_STORE
    ref = (item.get("bundle_refs") or {}).get(runtime)
    if store is None or ref is None:
        return None
    try:
        record = store.current(ref["bundle_digest"], runtime)
    except receipt_store.ReceiptRefused as refused:
        raise GpuReceiptBroken(f"{item['catalog_id']} {runtime}: {refused}") from None
    if record is None:
        return None
    if record["catalog_id"] != item["catalog_id"]:
        raise GpuReceiptBroken(
            f"{item['catalog_id']} {runtime}: the record is for another entry"
        )
    same = record["determinism_flags_digest"] == required_determinism_digest(runtime)
    return {
        "schema": SCHEMA,
        "catalog_id": record["catalog_id"],
        "runtime_profile_id": runtime,
        "kind": "repeat",
        "image_digest": record["image_id"],
        "tested_on": "the on-box official receipt store",
        "gpu_used": True,
        "smoke_ok": True,
        "pairs": len(record["run_digests"]) - 1,
        "identical": len(record["run_digests"]) - 1,
        "differ": [],
        "host_class": record["host_class"],
        "determinism": required_determinism(runtime) if same else None,
    }


def official_load(item, runtime: str, store=None):
    """The receipt the OFFICIAL route reads: the store's record when there is one, else the repository receipt
    (practice and legacy). `official_grade_problem` judges either."""
    return official_receipt(item, runtime, store) or load(item["catalog_id"], runtime)


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
    determinism,
    host_class,
    pairs=0,
    identical=0,
    differ=(),
    environment=None,
):
    """A receipt from a Test Lead GPU run (`gpu_repeat.py compare`): `pairs`/`identical` count the cross-run repeat.

    `determinism` and `host_class` are what the official check reads (`official_grade_problem`) and have
    no default: pass what the run really carried - `required_determinism(runtime)` when it ran under the
    official environment, the registered host class name when it ran on one - or `None`, which records
    nothing (a venv-grade practice receipt, never officially gradable). A smoke receipt records neither.
    """
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
        if determinism is not None or host_class is not None:
            raise GpuReceiptBroken(
                f"{catalog_id} {runtime}: a smoke receipt records no determinism or host class"
            )
        receipt["note"] = SMOKE_ONLY[catalog_id]
    else:
        receipt.update(pairs=pairs, identical=identical, differ=sorted(differ))
        if determinism is not None:
            receipt["determinism"] = determinism
        if host_class is not None:
            receipt["host_class"] = host_class
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


#: The JAX GPU determinism environment, copied rather than imported (the accelerator profile is on the execution side of
#: the protected-material boundary; catalog modules must not import it). The test
#: `test_the_catalog_constants_equal_the_accelerator_profile` keeps both equal to `accelerators.GPU_DETERMINISM_*`.
JAX_DETERMINISM_XLA_FLAGS = (
    "--xla_gpu_deterministic_ops=true",
    "--xla_gpu_exclude_nondeterministic_ops=true",
    "--xla_gpu_autotune_level=0",
)
JAX_DETERMINISM_ENVIRONMENT = {
    "NVIDIA_TF32_OVERRIDE": "0",
    "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
}


def required_determinism(runtime: str):
    """The full determinism environment an official run carries, as a JSON-comparable value."""
    from carbon.reconstruction import torch_profile

    if runtime == "torch-cu130-py311":
        return [[key, value] for key, value in torch_profile.GPU_DETERMINISM]
    if runtime == "jax-cuda13-py311":
        return {
            **JAX_DETERMINISM_ENVIRONMENT,
            "XLA_FLAGS": " ".join(JAX_DETERMINISM_XLA_FLAGS),
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
