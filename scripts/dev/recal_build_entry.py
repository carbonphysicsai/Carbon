#!/usr/bin/env python3
# ruff: noqa: BLE001 - a failed build is a result for the driver, not a crash
"""Rebuild one catalog entry at a given seed, as the receiver builds it, and write its calibration artifact.

This is the build half of the launch recalibration driver (GPUYARD_GPU4_REPEAT_EVIDENCE_RULING_20261030, item 4). It runs the
entry through the same practice code a miner's practice and the receiver's direct path use, so the ledger, the owner
identity, the verified GPU overlay, the challenge binding, the train bytes, the example, the allowlist and the limits
document are the ones that route assembles. Only the last step differs: the practice's build-and-infer call is replaced by
`bundle_construction_worker.reconstruct_public` (build only) at the seed you ask for, and the built state is packaged by
`calibration_artifact_job.write_artifact`. The inference and the grade are the existing calibration grade tool's.

    recal_build_entry.py build   --kind motor|cooling|f08|f02 --entry CATALOG_ID --seed S --repeat R --out DIR
                                 --parent-identity ID.json --cache-root DIR --gpu-image GPU_ID.json
                                 [--gpu-cache-root DIR] [--work-dir DIR] [--pod-id REF] [--fake]
    recal_build_entry.py assemble --grades-dir DIR --meta META.json --out INPUT.json

`build` writes DIR/<entry>/s<seed>r<repeat>/ (recipe.json, state.npz, manifest.json, SHA256SUMS) and prints one canonical JSON
line with the state sha256 and where it ran. Exit 0 a GPU build; 3 the practice ran a CPU build (not a GPU datum; nothing is
written); 1 the build failed. `--fake` builds nothing real: it uses the real recipe and writes a deterministic stand-in state,
so the whole chain below can be rehearsed with no GPU, no image and no docker.

The chain, per panel member (10 seed-0 rebuilds) and for the control (seeds 0..9), then the existing tools:

    recal_build_entry.py build ...  ->  python -m carbon.challenge_validator.calibration_grade_run
        --artifact DIR/<entry>/s<S>r<R> --pack PACK --challenge ID --version V --work W --judge-image JUDGE.json
        > DIR/<entry>/s<S>r<R>.grade.json   (add --fake for the rehearsal)
    recal_build_entry.py assemble --grades-dir DIR --meta META.json --out INPUT.json  ->  recal_stats.py INPUT.json

`assemble` reads every `DIR/<entry>/s<S>r<R>.grade.json` plus the artifact's manifest beside it and writes the
`carbon.recal-stats.input.v1` document. META.json carries what no grade file holds: per Challenge `pack_digest`,
`class_record_digest`, `control_basis_bit_identical`, `control_basis_within_noise`, `panel` (entry ids in panel order),
and per entry `reference_fingerprint` and `within_noise`. Nothing is guessed: a missing run, grade or meta field refuses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

#: The launch versions (the versions the recal measures), not practice_v2_curves' older defaults.
LAUNCH = {
    "motor": ("electric-motor-magnetics", "1.5"),
    "cooling": ("chip-cold-plate", "1.6"),
    "f08": ("f08-ribbed-bracket", "1.7"),
    "f02": ("f02", "2.5"),
}
SEEDS = range(10)
REPEATS = range(10)
POD_DEFAULT = "recal"


class BuildDone(BaseException):
    """Raised by the capture to leave the practice after the build (a BaseException: no handler in the
    practice's own error paths may swallow it)."""

    def __init__(self, record):
        super().__init__("build captured")
        self.record = record


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _runtime(profile_id, gpu):
    text = str(profile_id or "")
    if "jax" in text:
        return "jax-cuda13-py311" if gpu else "python-cpu-py311"
    return "torch-cu130-py311" if gpu else "torch-cpu-py311"


class OfficialMismatch(RuntimeError):
    """The bundle the practice path would rebuild is not the bundle official grading rebuilds."""


def verify_official(expanded, catalog_recipe, gpu_runtimes, expand_official):
    """Refuse unless ``expanded`` (the bundle recipe the practice path is about to build) equals the bundle recipe
    `served.expand_official(catalog_recipe, gpu_runtimes)` gives for the same entry: the GPU build the grading
    rebuild runs, never a CPU fallback. Then sigma is measured on exactly what official grading builds.
    """
    official, runtime = expand_official(catalog_recipe, gpu_runtimes)
    if expanded != official:
        raise OfficialMismatch(
            "recal_bundle_differs_from_official: the practice-expanded bundle recipe is not "
            f"expand_official's for runtime {runtime}"
        )
    return runtime


def make_capture(
    *, seed, reconstruct, record_into, check_binding=None, official_check=None
):
    """The replacement for `reconstruct_and_infer_public`: build only, at ``seed``, then leave the practice.

    ``reconstruct`` is `bundle_construction_worker.reconstruct_public` (or a fake with its signature).
    """

    def capture(ledger, **kw):
        from carbon.development_session import bundle_construction_worker as worker
        from carbon.development_session.bundle_construction_worker import (
            direct_child_identity,
        )

        recipe = kw["recipe"]
        if official_check is not None:
            official_check(recipe.to_dict())
        binding = (check_binding or worker._checked_binding)(
            recipe, kw["challenge_binding"]
        )
        policy = kw["limits_document"]["reconstruction_resource_policy"]
        accelerator = kw.get("accelerator")
        started = _now()
        build = reconstruct(
            ledger,
            owner=kw["owner"],
            identity=direct_child_identity(kw["identity"], "build"),
            image=kw["image"],
            construction_parent=kw.get("construction_parent"),
            recipe=recipe,
            challenge_binding=binding,
            train=kw["train"],
            example=kw["example"],
            seed=seed,
            allowlist_bytes=kw["allowlist_bytes"],
            limits_document=kw["limits_document"],
            seconds=policy["build_wall_seconds_max"],
            **({} if accelerator is None else {"accelerator": accelerator}),
            runner=kw.get("runner"),
        )
        record_into.update(
            {
                "recipe": recipe,
                "image": kw["image"],
                "construction_parent": kw.get("construction_parent"),
                "train": kw["train"],
                "train_sha256": kw.get("train_sha256"),
                "accelerator": accelerator,
                "build": build,
                "wall_s": _now() - started,
            }
        )
        raise BuildDone(record_into)

    return capture


def _now():
    import time

    return time.monotonic()


def _identities(record):
    """(worker_image_digest, parent_image_digest, bundle_sha256, runtime profile id) from what the practice built on."""
    image = record["image"]
    parent = record["construction_parent"]
    overlay_ref = getattr(image, "bundle_ref", None)
    if hasattr(image, "tree_digest"):  # a verified GPU overlay on the pinned parent
        worker = image.tree_digest
        parent_digest = getattr(parent, "image_id", None) or image.parent_image_id
        bundle = overlay_ref
    else:  # the CPU library child
        worker = image.image_id if hasattr(image, "image_id") else None
        parent_digest = getattr(parent, "image_id", None) or worker
        bundle = overlay_ref
    return worker, parent_digest, bundle


def package(record, *, entry, kind, seed, out, pod_id, gpu_facts=None):
    """Write the calibration artifact for a captured build into ``out`` and return (manifest, state sha256)."""
    from carbon.agent_campaign import calibration_artifact_job as job

    recipe = record["recipe"]
    build = record["build"]
    worker, parent_digest, bundle = _identities(record)
    source = recipe.to_dict().get("source") or {}
    bundle_sha = getattr(bundle, "bundle_digest", None) or (
        source.get("bundle_ref") or {}
    ).get("bundle_digest")
    gpu = record["accelerator"] is not None
    state_bytes = Path(build.state_path).read_bytes()
    challenge_id, version = LAUNCH[kind]
    manifest = job.write_artifact(
        out,
        recipe_bytes=recipe.canonical_bytes,
        state_bytes=state_bytes,
        challenge_id=challenge_id,
        version=version,
        bundle_ref="catalog/" + entry,
        bundle_sha256=bundle_sha,
        worker_image_digest=worker,
        parent_image_digest=parent_digest,
        runtime=_runtime(getattr(bundle, "runtime_profile_id", None), gpu),
        train_sha256=record.get("train_sha256") or _sha(record["train"]),
        seed=seed,
        build_wall_s=record["wall_s"],
        pod_id=pod_id,
        gpu=gpu_facts,
    )
    return manifest, _sha(state_bytes)


def build_one(
    kind,
    entry,
    seed,
    repeat,
    args,
    *,
    factory=None,
    reconstruct=None,
    check_binding=None,
    expand_official=None,
):
    """One rebuild at ``seed`` (repeat index ``repeat``): returns the printable record, or raises on a CPU build."""
    import practice_v2_curves as curves

    from carbon.development_session import bundle_construction_worker as worker

    curves.TARGETS = {**curves.TARGETS, **LAUNCH}
    factory = factory or curves.practice_for
    practice = factory(kind, args)
    if getattr(args, "gpu_image", None):
        from carbon.reconstruction.worker.docker_runtime import load_image_identity

        practice.gpu_image = load_image_identity(Path(args.gpu_image))
    record: dict = {}
    reconstruct = reconstruct or worker.reconstruct_public
    catalog_recipe = curves.recipe_for(kind, entry)
    official_check = None
    if (
        expand_official is not False
    ):  # False = the stand-in (--fake) has no official GPU receipt to check
        if expand_official is None:
            from carbon.backbone_catalog.served import expand_official
            from carbon.development_session.gpu_practice import gpu_runtimes

            declared = gpu_runtimes(getattr(practice, "gpu_image", None))
        else:
            declared = ()

        def official_check(expanded):
            return verify_official(expanded, catalog_recipe, declared, expand_official)

    capture = make_capture(
        seed=seed,
        reconstruct=reconstruct,
        record_into=record,
        check_binding=check_binding,
        official_check=official_check,
    )
    identity = f"recal-{kind}-{hashlib.sha256(entry.encode()).hexdigest()[:12]}-s{seed}-r{repeat}"
    original = worker.reconstruct_and_infer_public
    worker.reconstruct_and_infer_public = capture
    try:
        practice(identity, catalog_recipe)
    except BuildDone:
        pass
    finally:
        worker.reconstruct_and_infer_public = original
    if "build" not in record:
        raise RuntimeError("the practice did not reach the build")
    return record


def install_receipts(path):
    """Point the official route at the receiver's on-box GPU receipt store, exactly as the receiver does
    (`direct_receiver.install_official_receipt_store`: the registered rebuild noise is the only tolerance a
    receipt may carry). Without it every catalog entry is refused `catalog_gpu_receipt_pending`.
    """
    from carbon.challenge_validator import direct_receiver

    store = Path(path)
    if not store.is_absolute() or store.is_symlink() or store.resolve() != store:
        raise ValueError("exact official gpu receipts path required")
    direct_receiver.install_official_receipt_store(
        {"official_gpu_receipts": str(store)}
    )


def _out_dir(base, entry, seed, repeat):
    return Path(base) / entry / f"s{seed}r{repeat}"


def cmd_build(
    ns,
    *,
    factory=None,
    reconstruct=None,
    gpu_facts=None,
    check_binding=None,
    expand_official=None,
):
    base = Path(ns.work_dir) if ns.work_dir else Path(tempfile.mkdtemp(prefix="recal-"))
    args = SimpleNamespace(
        out_dir=str(base),
        parent_identity=ns.parent_identity,
        cache_root=(
            ns.gpu_cache_root if ns.gpu_image and ns.gpu_cache_root else ns.cache_root
        ),
        gpu_image=ns.gpu_image,
    )
    try:
        record = build_one(
            ns.kind,
            ns.entry,
            ns.seed,
            ns.repeat,
            args,
            factory=factory,
            reconstruct=reconstruct,
            check_binding=check_binding,
            expand_official=expand_official,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "entry": ns.entry,
                    "status": "BUILD_FAILED",
                    "error": type(exc).__name__ + ": " + str(exc)[-300:],
                },
                sort_keys=True,
            )
        )
        return 1
    if (ns.gpu_image or ns.fake) and record["accelerator"] is None:
        print(
            json.dumps(
                {
                    "entry": ns.entry,
                    "status": "CPU_BUILD",
                    "note": "asked for GPU, the practice built on the CPU",
                },
                sort_keys=True,
            )
        )
        return 3
    out = _out_dir(ns.out, ns.entry, ns.seed, ns.repeat)
    manifest, _state_sha = package(
        record,
        entry=ns.entry,
        kind=ns.kind,
        seed=ns.seed,
        out=out,
        pod_id=ns.pod_id,
        gpu_facts=gpu_facts,
    )
    print(
        json.dumps(
            {
                "entry": ns.entry,
                "status": "BUILT",
                "artifact": str(out),
                "state_sha256": manifest["state_sha256"],
                "recipe_digest": manifest["recipe_digest"],
                "device": "gpu" if record["accelerator"] is not None else "cpu",
                "official_bundle_check": (
                    "skipped (fake)"
                    if expand_official is False
                    else "equal to expand_official"
                ),
                "seed": ns.seed,
                "repeat": ns.repeat,
            },
            sort_keys=True,
        )
    )
    return 0


class MetaError(ValueError):
    pass


def _hex(value):
    return value.split(":", 1)[-1]


def assemble(grades_dir, meta):
    """The `carbon.recal-stats.input.v1` document from the grade files under ``grades_dir`` and ``meta``."""
    grades_dir = Path(grades_dir)
    challenges = {}
    for name, own in sorted(meta["challenges"].items()):
        members, control_totals = {}, {}
        for entry in own["panel"]:
            totals0, digests0 = [], []
            for repeat in REPEATS:
                grade, manifest = _read_run(grades_dir, entry, 0, repeat)
                totals0.append(grade["total"])
                digests0.append(_hex(manifest["state_sha256"]))
            facts = own["entries"][entry]
            members[entry] = {
                "reference_fingerprint": facts["reference_fingerprint"],
                "seed0_totals": totals0,
                "state_digests": digests0,
                "within_noise": facts["within_noise"],
            }
        control = own.get("control")
        if control is not None:
            control_totals[control] = [
                _read_run(grades_dir, control, seed, 0)[0]["total"] for seed in SEEDS
            ]
        challenges[name] = {
            "pack_digest": own["pack_digest"],
            "class_record_digest": own["class_record_digest"],
            "control_basis_bit_identical": own["control_basis_bit_identical"],
            "control_basis_within_noise": own["control_basis_within_noise"],
            "panel": list(own["panel"]),
            "members": members,
            "control_seed_totals": control_totals,
        }
    return {"schema": "carbon.recal-stats.input.v1", "challenges": challenges}


def _read_run(grades_dir, entry, seed, repeat):
    directory = grades_dir / entry
    grade_path = directory / f"s{seed}r{repeat}.grade.json"
    manifest_path = directory / f"s{seed}r{repeat}" / "manifest.json"
    try:
        grade = json.loads(grade_path.read_bytes())
        manifest = json.loads(manifest_path.read_bytes())
    except (OSError, ValueError) as exc:
        raise MetaError(
            f"missing or unreadable run {entry} s{seed}r{repeat}: {exc.__class__.__name__}"
        ) from exc
    total = grade.get("total")
    if type(total) not in (int, float) or isinstance(total, bool):
        raise MetaError(f"{entry} s{seed}r{repeat}: the grade has no numeric total")
    return grade, manifest


def cmd_assemble(ns):
    try:
        meta = json.loads(Path(ns.meta).read_bytes())
        document = assemble(ns.grades_dir, meta)
    except (MetaError, KeyError, OSError, ValueError) as exc:
        print(f"refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    Path(ns.out).write_text(
        json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return 0


class _FakePractice:
    """A practice that reaches the build with stand-in images and the real recipe: no docker, no GPU."""

    gpu_image = None

    def __init__(self, kind):
        self.kind = kind

    def __call__(self, identity, strategy):
        from carbon.challenge_kit import physical_material
        from carbon.development_session import bundle_construction_worker as worker
        from carbon.development_session.construction_recipe import ConstructionRecipe
        from carbon.development_session.research_carrier import MINER_GPU

        bundle = SimpleNamespace(
            bundle_digest="sha256:" + "2" * 64, runtime_profile_id="torch-fake"
        )
        return worker.reconstruct_and_infer_public(
            None,
            owner="recal",
            identity=identity,
            image=SimpleNamespace(image_id="sha256:" + "1" * 64, bundle_ref=bundle),
            construction_parent=SimpleNamespace(image_id="sha256:" + "3" * 64),
            recipe=ConstructionRecipe.from_dict(strategy),
            challenge_binding={},
            limits_document={
                "reconstruction_resource_policy": {"build_wall_seconds_max": 60}
            },
            train=b"fake-train",
            # the grade tool pins the artifact to the kit's TRAIN: the stand-in carries the kit's own digest
            train_sha256=physical_material.bundle_material(*LAUNCH[self.kind])[
                "construction_kit"
            ]["train_digest"],
            allowlist_bytes=b"",
            example=None,
            accelerator=MINER_GPU,
        )


def fake_factory(kind, args):
    return _FakePractice(kind)


def fake_reconstruct(ledger, *, recipe, seed, **kw):
    """A deterministic stand-in build: the state depends on the recipe and the seed only (repeats at one
    seed are bit-identical, different seeds differ)."""
    path = Path(tempfile.mkdtemp(prefix="recal-fake-")) / "state.npz"
    path.write_bytes(
        b"FAKE-STATE" + hashlib.sha256(f"{recipe.digest}|{seed}".encode()).digest()
    )
    return SimpleNamespace(state_path=path)


FAKE_GPU = ("FAKE GPU", "0.0", "0.0")


def main(
    argv=None,
    *,
    factory=None,
    reconstruct=None,
    gpu_facts=None,
    check_binding=None,
    expand_official=None,
):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("build")
    b.add_argument("--kind", required=True, choices=sorted(LAUNCH))
    b.add_argument("--entry", required=True)
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--repeat", type=int, default=0)
    b.add_argument("--out", required=True)
    b.add_argument("--parent-identity", required=False)
    b.add_argument("--cache-root", required=False)
    b.add_argument("--gpu-image")
    b.add_argument("--gpu-cache-root")
    b.add_argument("--work-dir")
    b.add_argument("--pod-id", default=POD_DEFAULT)
    b.add_argument(
        "--gpu-receipts",
        help="the receiver's official_gpu_receipts store directory (receiver.json, or the GPU receipt worker's --store-dir)",
    )
    b.add_argument("--fake", action="store_true")
    a = sub.add_parser("assemble")
    a.add_argument("--grades-dir", required=True)
    a.add_argument("--meta", required=True)
    a.add_argument("--out", required=True)
    ns = parser.parse_args(argv)
    if ns.mode == "assemble":
        return cmd_assemble(ns)
    if ns.fake:
        factory, reconstruct, gpu_facts = fake_factory, fake_reconstruct, FAKE_GPU
        expand_official = False  # the stand-in has no official GPU receipt

        def check_binding(_recipe, binding):  # the stand-in carries no kit binding
            return binding

    elif not (ns.parent_identity and ns.cache_root):
        parser.error("build needs --parent-identity and --cache-root (or --fake)")
    if ns.gpu_receipts:
        install_receipts(ns.gpu_receipts)
    return cmd_build(
        ns,
        factory=factory,
        reconstruct=reconstruct,
        gpu_facts=gpu_facts,
        check_binding=check_binding,
        expand_official=expand_official,
    )


if __name__ == "__main__":
    raise SystemExit(main())
