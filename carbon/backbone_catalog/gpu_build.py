"""The GPU (`torch-cu130-py311`) build of a Torch catalog entry, derived from its CPU build.

One deterministic transform and no per-entry edits (U58, 2026-10-22). The CPU bundle stays the entry's
`bundle_ref`; the GPU build is a second ref under `bundle_refs`, stored in
`bundles/<catalog_id>/torch-cu130-py311/`. `pipeline.verify` re-derives it from the CPU files with this module and
refuses any difference, so a GPU bundle can never differ from its CPU twin by more than the change below.

The one change: after `model = model.cpu().eval()` in `carbon_candidate/build.py`, drop plain-attribute caches
(`_grid`, `_res`) that modules such as neuralop's GridEmbedding keep on the training device. Without it a model
trained on cuda fails at its first CPU inference with a device mismatch.

A bundle's environment digest depends on the pinned cu130 LOCK (`torch_profile.GPU_LOCK_DIGEST`) and the overlay
lock, not on a published image, so GPU bundles can be sealed before the image build.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile

PROFILE = "torch-cu130-py311"
CPU_PROFILE = "torch-cpu-py311"
#: The JAX twin (jNO entries): `python-cpu-py311` -> `jax-cuda13-py311`. JAX runs on the GPU by default and the
#: registry/build code pins no device, so the source is byte-identical; only the manifest's runtime changes.
JAX_PROFILE = "jax-cuda13-py311"
JAX_CPU_PROFILE = "python-cpu-py311"
TWINS = {CPU_PROFILE: PROFILE, JAX_CPU_PROFILE: JAX_PROFILE}
#: The JAX GPU environment lock digest, copied here rather than imported: `carbon.reconstruction.accelerators` is on the
#: execution side of the protected-material boundary, and catalog modules must not import it
#: (tests/cpu/test_protected_material_isolation.py). `test_the_catalog_constants_equal_the_accelerator_profile` keeps the
#: copy equal to `accelerators.GPU_PROFILE.environment_lock_digest`.
JAX_GPU_LOCK_DIGEST = (
    "sha256:a197af534a061636ba77e4f97f7e9be508b795d58883b6774fde74a5135ad434"
)
ANCHOR = "model = model.cpu().eval()"
BUILD_MEMBER = "carbon_candidate/build.py"
_CLEAR = (
    "# GPU build: modules that cache tensors in plain attributes (neuralop's GridEmbedding grid) keep them on the",
    "# training device after .cpu(); drop such caches so the first CPU inference rebuilds them there.",
    "for _module in model.modules():",
    '    if getattr(_module, "_grid", None) is not None:',
    "        _module._grid = None",
    "        _module._res = None",
)


#: Entries with no GPU twin at all (Validator ruling, 2026-10-22): thuml.LSM stays CPU-only and officially gradable
#: with its CPU receipt (its GPU build would need `timm`, which the cu130 lock does not carry, and its upsample backward
#: has no deterministic CUDA kernel).
NO_GPU_TWIN = ("thuml.LSM", "f08.thuml.LSM")
#: The second registered change, on an explicit one-entry list and never a general rule (owner, 2026-10-22): the CNO1d
#: build's upsample backward has no deterministic CUDA kernel, so its GPU twin relaxes
#: `use_deterministic_algorithms(True)` to `warn_only=True`. The twin is therefore not a pure derivation of the CPU build
#: by the first change alone; the CPU build is untouched, and its receipt claims smoke only
#: (`gpu_receipt.SMOKE_ONLY`, the same entry).
WARN_ONLY_DETERMINISM = (
    "cno.CNO1d",
    # The same CNO1d build served on the launch versions (Lead GPU-2, 2026-10-26): the upsample backward is the
    # same op, so the owner's decision applies to the same entry under its v2 ids. Validator to confirm.
    "v2.motor.cno.CNO1d",
    "v2.cooling.cno.CNO1d",
    "v2.f08.cno.CNO1d",
    "v2.f02.cno.CNO1d",
)
COMMON_MEMBER = "carbon_candidate/common.py"
DETERMINISM = "torch.use_deterministic_algorithms(True)"
WARN_ONLY = "torch.use_deterministic_algorithms(True, warn_only=True)  # GPU twin of this entry only"


BACKBONES_MEMBER = "carbon_candidate/backbones.py"
#: The third registered change, on an explicit three-entry list (RTX 4090 repeat, 2026-10-22): these builds make helper
#: tensors (DFT matrices, graph index/one-hot matrices) on the CPU inside `forward`, which only works while the model
#: runs on the CPU. Each pair below makes the tensor on the input's (or its owner buffer's) device instead; the values
#: are the same (computed on the CPU, then moved), so the CPU build is untouched and only the GPU twin carries it. Every
#: `old` must occur exactly once in the member.
DEVICE_FIXES = {
    "lno.LNO1d": (
        (
            BACKBONES_MEMBER,
            "        return torch.cos(angle).to(torch.float32), torch.sin(angle).to(torch.float32)",
            "        return torch.cos(angle).to(torch.float32).to(device), torch.sin(angle).to(torch.float32).to(device)",
        ),
        (BACKBONES_MEMBER, "    def _mats():", "    def _mats(device=None):"),
        (
            BACKBONES_MEMBER,
            "        cos_m, sin_m = _mats()\n        return torch.view_as_complex",
            "        cos_m, sin_m = _mats(x.device)\n        return torch.view_as_complex",
        ),
        (
            BACKBONES_MEMBER,
            "        cos_m, sin_m = _mats()\n        parts = torch.view_as_real(z)",
            "        cos_m, sin_m = _mats(z.device)\n        parts = torch.view_as_real(z)",
        ),
        (
            BACKBONES_MEMBER,
            'node.value = ast.Name("_lambda0", ast.Load())',
            'node.value = ast.Call(ast.Attribute(ast.Name("_lambda0", ast.Load()), "to", ast.Load()), [ast.Attribute(ast.Name("x", ast.Load()), "device", ast.Load())], [])',
        ),
    ),
    "neuralop.GINO": (
        (
            BACKBONES_MEMBER,
            "rows, owner = torch.arange(self.n_queries).view(-1, 1), self.query_index.view(1, -1)",
            "rows, owner = torch.arange(self.n_queries, device=self.query_index.device).view(-1, 1), self.query_index.view(1, -1)",
        ),
    ),
    "physicsnemo.MeshGraphNet": (
        (
            BACKBONES_MEMBER,
            "torch.zeros((size,) + tuple(src.shape[1:]), dtype=src.dtype)",
            "torch.zeros((size,) + tuple(src.shape[1:]), dtype=src.dtype, device=src.device)",
        ),
        (
            BACKBONES_MEMBER,
            "torch.zeros(size, dtype=src.dtype).index_add(\n            0, index, torch.ones(index.shape[0], dtype=src.dtype)",
            "torch.zeros(size, dtype=src.dtype, device=src.device).index_add(\n            0, index, torch.ones(index.shape[0], dtype=src.dtype, device=src.device)",
        ),
        (
            BACKBONES_MEMBER,
            "        src = torch.as_tensor(graph.src_np)\n        dst = torch.as_tensor(graph.dst_np)",
            "        src = torch.as_tensor(graph.src_np).to(efeat.device)\n        dst = torch.as_tensor(graph.dst_np).to(efeat.device)",
        ),
        (
            BACKBONES_MEMBER,
            "rows, owner = torch.arange(nodes).view(-1, 1), torch.as_tensor(local).view(1, -1)",
            "rows, owner = torch.arange(nodes, device=efeat.device).view(-1, 1), torch.as_tensor(local).to(efeat.device).view(1, -1)",
        ),
        (
            BACKBONES_MEMBER,
            "        edges = torch.as_tensor(edges_np)\n",
            "        edges = torch.as_tensor(edges_np).to(x.device)\n",
        ),
    ),
}


class GpuBuildRefused(ValueError):
    """The CPU build cannot be turned into a GPU build by this transform."""


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def environment_digest(base: str, lock: str) -> str:
    """As `library_bundles._environment_digest`: the base lock and the overlay lock."""
    return digest(
        canonical({"base_environment_digest": base, "overlay_lock_sha256": lock})
    )


def patched_source(raw: bytes, catalog_id: str | None = None) -> bytes:
    """The CPU build's `source.tar.gz` with the GPU change (and, for the two named entries, the warn-only
    determinism change), repacked deterministically."""
    files = {}
    root = None
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile():
                top, rest = member.name.split("/", 1)
                root = root or top
                files[rest] = archive.extractfile(member).read()
    text = files[BUILD_MEMBER].decode("utf-8")
    if text.count(ANCHOR) != 1:
        raise GpuBuildRefused(
            f"{BUILD_MEMBER}: anchor found {text.count(ANCHOR)} times, expected once"
        )
    lines = []
    for line in text.split("\n"):
        lines.append(line)
        if line.strip() == ANCHOR:
            indent = line[: len(line) - len(line.lstrip())]
            lines.extend(indent + part for part in _CLEAR)
    files[BUILD_MEMBER] = "\n".join(lines).encode("utf-8")
    if catalog_id in WARN_ONLY_DETERMINISM:
        common = files[COMMON_MEMBER].decode("utf-8")
        if common.count(DETERMINISM) != 1:
            raise GpuBuildRefused(
                f"{COMMON_MEMBER}: determinism call found {common.count(DETERMINISM)} times, expected once"
            )
        files[COMMON_MEMBER] = common.replace(DETERMINISM, WARN_ONLY).encode("utf-8")
    for member, before, after in DEVICE_FIXES.get(catalog_id, ()):
        body = files[member].decode("utf-8")
        if body.count(before) != 1:
            raise GpuBuildRefused(
                f"{member}: device fix anchor found {body.count(before)} times, expected once: {before[:60]!r}"
            )
        files[member] = body.replace(before, after).encode("utf-8")
    packed = io.BytesIO()
    with tarfile.open(fileobj=packed, mode="w:") as out:
        for rest in sorted(files):
            info = tarfile.TarInfo(f"{root}/{rest}")
            info.size, info.mode, info.uid, info.gid, info.mtime = (
                len(files[rest]),
                0o644,
                0,
                0,
                0,
            )
            out.addfile(info, io.BytesIO(files[rest]))
    zipped = io.BytesIO()
    with gzip.GzipFile(fileobj=zipped, mode="wb", filename="", mtime=0) as stream:
        stream.write(packed.getvalue())
    return zipped.getvalue()


def gpu_manifest(
    cpu_manifest: dict, source: bytes, base_environment_digest: str
) -> dict:
    """The CPU bundle manifest, retargeted to the cu130 runtime over `source`."""
    twin = TWINS.get(cpu_manifest["runtime_profile_id"])
    if twin is None:
        raise GpuBuildRefused(
            "only a torch-cpu-py311 or python-cpu-py311 build has a GPU twin"
        )
    gpu = dict(cpu_manifest)
    gpu.update(
        accelerator="cuda13",
        runtime_profile_id=twin,
        base_environment_digest=base_environment_digest,
        environment_digest=environment_digest(
            base_environment_digest, cpu_manifest["lock_sha256"]
        ),
        source_bytes=len(source),
        source_sha256=digest(source),
    )
    return gpu


def bundle_ref(manifest: dict) -> dict:
    """The ref a catalog entry lists for this manifest (as `library_bundles.bundle_ref(...).to_dict()`)."""
    return {
        "bundle_digest": digest(canonical(manifest)),
        "environment_digest": manifest["environment_digest"],
        "language": manifest["language"],
        "runtime_profile_id": manifest["runtime_profile_id"],
        "schema": "carbon.library-bundle-ref.v1",
    }


def derived_source(
    cpu_profile: str, raw: bytes, catalog_id: str | None = None
) -> bytes:
    """The GPU twin's `source.tar.gz`: the Torch change for a Torch build, the CPU bytes unchanged for a JAX one."""
    if catalog_id in NO_GPU_TWIN:
        raise GpuBuildRefused(f"{catalog_id} has no GPU twin (CPU only)")
    if cpu_profile == CPU_PROFILE:
        return patched_source(raw, catalog_id)
    if cpu_profile == JAX_CPU_PROFILE:
        return raw
    raise GpuBuildRefused(f"no GPU twin for {cpu_profile}")


def base_lock(twin: str) -> str:
    """The pinned GPU base lock a twin binds (a lock digest, not an image)."""
    if twin == PROFILE:
        from carbon.reconstruction import torch_profile

        return torch_profile.GPU_LOCK_DIGEST
    if twin == JAX_PROFILE:
        return JAX_GPU_LOCK_DIGEST
    raise GpuBuildRefused(f"no GPU lock for {twin}")
