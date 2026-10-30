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

import hashlib
import json
import os
import re
import subprocess
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

# The two registries are not module constants: this file is a build input, so a pin written here would move the image it
# pins. They are loaded from a tracked stage-2 record outside the build inputs, `scripts/validator_host_classes/
# <class>.stage2.json` (Validator ruling GPUYARD_GPU4_REPEAT_EVIDENCE_RULING_20261030, stage 2). This loader is the only
# source: with no record both are empty and every GPU ref is refused officially; a record that is empty, edited,
# untracked, outside a git work tree, or that disagrees with the stage-1 file or the determinism environment is refused
# with a typed code, never partly read.

STAGE2_SCHEMA = "carbon.validator.host-class-stage2.v1"
STAGE2_SUFFIX = ".stage2.json"
_RUNTIMES = ("torch-cu130-py311", "jax-cuda13-py311")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_STAGE2_KEYS = {"schema", "host_class_id", "stage1_record_digest", "runtimes"}
_RUNTIME_KEYS = {"image_ids", "determinism_flags_digest"}


class Stage2Refused(Exception):
    """A stage-2 record that cannot be trusted. ``code`` is the typed reason."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


class Stage2Registries:
    """What the stage-2 record(s) register: the pinned worker images per runtime and the registered host classes."""

    def __init__(self, images=None, host_classes=()):
        self.images = {k: frozenset(v) for k, v in (images or {}).items()}
        self.host_classes = frozenset(host_classes)


def stage2_directory() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "validator_host_classes"


def record_digest(document) -> str:
    """sha256 of the canonical JSON of a parsed record (line endings and key order do not matter)."""
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _git(directory: Path, *args):
    try:
        return subprocess.run(
            ["git", "-C", str(directory), *args],
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
            check=False,
        )
    except OSError:
        return None


def _tracked_and_unmodified(directory: Path, name: str):
    """Refuse unless ``name`` is tracked at HEAD with no change (staged or not) in a usable git work tree."""
    inside = _git(directory, "rev-parse", "--is-inside-work-tree")
    if inside is None or inside.returncode != 0 or inside.stdout.strip() != "true":
        raise Stage2Refused(
            "V_STAGE2_UNVERIFIABLE",
            f"{name}: this is not a git work tree, so the record cannot be checked (install from a git clone)",
        )
    tracked = _git(directory, "ls-files", "--error-unmatch", "--", name)
    clean = _git(directory, "diff", "--quiet", "HEAD", "--", name)
    if (
        tracked is None
        or clean is None
        or tracked.returncode != 0
        or clean.returncode != 0
    ):
        raise Stage2Refused(
            "V_STAGE2_MODIFIED", f"{name}: untracked or changed against HEAD"
        )


def _load_json(path: Path, code: str):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError) as error:
        raise Stage2Refused(code, f"{path.name}: {error}") from None


def _read_record(directory: Path, path: Path):
    name = path.name
    _tracked_and_unmodified(directory, name)
    record = _load_json(path, "V_STAGE2_MALFORMED")
    stem = name[: -len(STAGE2_SUFFIX)]
    if (
        type(record) is not dict
        or set(record) != _STAGE2_KEYS
        or record["schema"] != STAGE2_SCHEMA
        or type(record["runtimes"]) is not dict
    ):
        raise Stage2Refused(
            "V_STAGE2_MALFORMED",
            f"{name}: not a {STAGE2_SCHEMA} record",
        )
    if not record["runtimes"]:
        raise Stage2Refused("V_STAGE2_EMPTY", f"{name}: registers no runtime")
    stage1_name = stem + ".json"
    _tracked_and_unmodified(directory, stage1_name)
    stage1 = _load_json(directory / stage1_name, "V_STAGE2_MISMATCH")
    if (
        type(stage1) is not dict
        or stage1.get("id") != record["host_class_id"]
        or record_digest(stage1) != record["stage1_record_digest"]
    ):
        raise Stage2Refused(
            "V_STAGE2_MISMATCH",
            f"{name}: the stage-1 class record differs (id or digest)",
        )
    images = {}
    for runtime, entry in record["runtimes"].items():
        if (
            runtime not in _RUNTIMES
            or type(entry) is not dict
            or set(entry) != _RUNTIME_KEYS
        ):
            raise Stage2Refused(
                "V_STAGE2_MALFORMED", f"{name}: unknown or malformed runtime {runtime!r}"
            )
        ids = entry["image_ids"]
        if (
            type(ids) is not list
            or not ids
            or any(type(i) is not str or not _IMAGE_ID.fullmatch(i) for i in ids)
        ):
            raise Stage2Refused(
                "V_STAGE2_EMPTY", f"{name}: {runtime} pins no full sha256 image id"
            )
        if entry["determinism_flags_digest"] != required_determinism_digest(runtime):
            raise Stage2Refused(
                "V_STAGE2_MISMATCH",
                f"{name}: {runtime} determinism digest differs from the code's",
            )
        images[runtime] = set(ids)
    return record["host_class_id"], images


def _stat(path: Path):
    try:
        info = path.stat()
    except OSError:
        return (None, None)
    return (info.st_mtime_ns, info.st_size)


_STAGE2_CACHE: dict = {}


def stage2_registries(directory=None) -> Stage2Registries:
    """THE loader of the pinned GPU worker images and registered host classes (nothing else may set them).

    No ``.stage2.json`` file means empty registries. Any record that fails verification raises ``Stage2Refused``."""
    directory = Path(directory) if directory is not None else stage2_directory()
    paths = sorted(directory.glob("*" + STAGE2_SUFFIX)) if directory.is_dir() else []
    if not paths:
        return Stage2Registries()
    key = (str(directory),) + tuple(
        (p.name, *_stat(p), *_stat(directory / (p.name[: -len(STAGE2_SUFFIX)] + ".json")))
        for p in paths
    )
    cached = _STAGE2_CACHE.get(key)
    if cached is not None:
        return cached
    images: dict = {}
    classes = set()
    for path in paths:
        host_class, found = _read_record(directory, path)
        classes.add(host_class)
        for runtime, ids in found.items():
            images.setdefault(runtime, set()).update(ids)
    result = Stage2Registries(images, classes)
    _STAGE2_CACHE.clear()
    _STAGE2_CACHE[key] = result
    return result


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
    try:
        registries = stage2_registries()
    except Stage2Refused as refused:
        return f"its host-class stage-2 record is refused ({refused.code})"
    image = receipt.get("image_digest")
    if image is None or image not in registries.images.get(runtime, ()):
        return "its receipt is not on the pinned GPU worker image"
    if receipt.get("determinism") != required_determinism(runtime):
        return "its receipt does not carry the full determinism environment"
    if receipt.get("host_class") not in registries.host_classes:
        return "its receipt is not from a registered host class"
    return None
