"""Every Torch catalog entry has a verified torch-cu130-py311 build beside its CPU build (U58).

The GPU files are the CPU files plus one registered change, re-derived by `gpu_build` on every verify.
"""

import copy
import io
import json
import shutil
import tarfile

import pytest

from carbon.backbone_catalog import gpu_build, pipeline


def torch_entries():
    return [
        e
        for e in pipeline.load()["entries"]
        if e["bundle_ref"]["runtime_profile_id"] == "torch-cpu-py311"
    ]


def withdrawn_twins():
    """The 10 relicensed THUML twins withdrawn from GPU (the pinned lock lacked timm; OWNER-CATALOG-LICENCES-01 record)."""
    derivation = json.loads(
        (
            pipeline.BUNDLES.parent / "derivations/OWNER-CATALOG-LICENCES-01.json"
        ).read_bytes()
    )
    return set(derivation["gpu_twins_withdrawn"]["ids"])


def has_no_twin_by_design(item):
    """No GPU twin yet or any more: the named CPU-only entries, the v2 entries (their twins come with the GPU line), and the
    withdrawn ones."""
    return (
        item["catalog_id"] in gpu_build.NO_GPU_TWIN
        or item["catalog_id"].startswith("v2.")
        or item["catalog_id"] in withdrawn_twins()
    )


def twinned_torch():
    return [e for e in torch_entries() if "bundle_refs" in e]


def test_every_torch_entry_lists_a_gpu_build_and_keeps_its_cpu_ref():
    entries = torch_entries()
    assert entries
    assert twinned_torch()
    for item in entries:
        if has_no_twin_by_design(item):
            assert "bundle_refs" not in item
            assert not (
                pipeline.BUNDLES / item["catalog_id"] / "torch-cu130-py311"
            ).exists()
            continue
        assert set(item["bundle_refs"]) == {"torch-cu130-py311"}
        assert item["bundle_ref"]["runtime_profile_id"] == "torch-cpu-py311"
        assert (
            item["bundle_refs"]["torch-cu130-py311"]["runtime_profile_id"]
            == "torch-cu130-py311"
        )
        assert (
            item["bundle_refs"]["torch-cu130-py311"]["bundle_digest"]
            != item["bundle_ref"]["bundle_digest"]
        )
        pipeline.verify(item)


def jax_entries():
    return [
        e
        for e in pipeline.load()["entries"]
        if e["bundle_ref"]["runtime_profile_id"] == "python-cpu-py311"
    ]


def test_every_jax_entry_lists_a_jax_cuda13_build_with_the_cpu_source_unchanged():
    from carbon.reconstruction.accelerators import GPU_PROFILE

    entries = jax_entries()
    assert entries
    assert any("bundle_refs" in e for e in entries)
    for item in entries:
        if has_no_twin_by_design(item):
            assert "bundle_refs" not in item
            continue
        assert set(item["bundle_refs"]) == {"jax-cuda13-py311"}
        root = pipeline.BUNDLES / item["catalog_id"]
        gpu = json.loads((root / "jax-cuda13-py311" / "bundle.json").read_bytes())
        assert gpu["runtime_profile_id"] == "jax-cuda13-py311"
        assert gpu["accelerator"] == "cuda13"
        assert gpu["base_environment_digest"] == GPU_PROFILE.environment_lock_digest
        assert (root / "jax-cuda13-py311" / "source.tar.gz").read_bytes() == (
            root / "source.tar.gz"
        ).read_bytes()
        pipeline.verify(item)


def test_no_other_runtime_has_a_gpu_build():
    for item in pipeline.load()["entries"]:
        if item["bundle_ref"]["runtime_profile_id"] not in gpu_build.TWINS:
            assert "bundle_refs" not in item


def test_a_jax_entry_cannot_list_the_torch_build():
    item = copy.deepcopy([e for e in jax_entries() if "bundle_refs" in e][0])
    item["bundle_refs"] = {"torch-cu130-py311": item["bundle_refs"]["jax-cuda13-py311"]}
    with pytest.raises(pipeline.CatalogBroken, match="no GPU build is registered"):
        pipeline.verify(item)


def test_the_gpu_source_differs_from_the_cpu_source_by_one_block_only():
    item = twinned_torch()[0]
    root = pipeline.BUNDLES / item["catalog_id"]

    def build_text(path):
        with tarfile.open(path) as archive:
            member = [
                m
                for m in archive.getmembers()
                if m.isfile() and m.name.endswith(gpu_build.BUILD_MEMBER)
            ][0]
            return archive.extractfile(member).read().decode()

    cpu = build_text(root / "source.tar.gz").split("\n")
    gpu = build_text(root / "torch-cu130-py311" / "source.tar.gz").split("\n")
    added = {part.strip() for part in gpu_build._CLEAR}
    assert len(gpu) - len(cpu) == len(gpu_build._CLEAR)
    assert [line for line in gpu if line.strip() not in added] == cpu


def test_the_gpu_manifest_binds_the_cu130_lock_not_an_image():
    from carbon.reconstruction import torch_profile

    item = twinned_torch()[0]
    manifest = json.loads(
        (
            pipeline.BUNDLES / item["catalog_id"] / "torch-cu130-py311" / "bundle.json"
        ).read_bytes()
    )
    assert manifest["accelerator"] == "cuda13"
    assert manifest["runtime_profile_id"] == "torch-cu130-py311"
    assert manifest["base_environment_digest"] == torch_profile.GPU_LOCK_DIGEST
    assert manifest["environment_digest"] == gpu_build.environment_digest(
        torch_profile.GPU_LOCK_DIGEST, manifest["lock_sha256"]
    )


@pytest.fixture
def tampered(tmp_path, monkeypatch):
    item = copy.deepcopy(torch_entries()[0])
    shutil.copytree(
        pipeline.BUNDLES / item["catalog_id"], tmp_path / item["catalog_id"]
    )
    monkeypatch.setattr(pipeline, "BUNDLES", tmp_path)
    return item, tmp_path / item["catalog_id"] / "torch-cu130-py311"


def test_a_gpu_source_that_is_not_the_derivation_is_refused(tampered):
    item, gpu = tampered
    raw = io.BytesIO()
    with (
        tarfile.open(gpu / "source.tar.gz") as archive,
        tarfile.open(fileobj=raw, mode="w:gz") as out,
    ):
        for member in archive.getmembers():
            body = archive.extractfile(member).read() if member.isfile() else None
            if member.name.endswith(gpu_build.BUILD_MEMBER):
                body = body + b"\n# changed\n"
                member.size = len(body)
            out.addfile(member, io.BytesIO(body) if body is not None else None)
    (gpu / "source.tar.gz").write_bytes(raw.getvalue())
    with pytest.raises(pipeline.CatalogBroken, match="not its CPU build's derivation"):
        pipeline.verify(item)


def test_a_wrong_environment_digest_or_ref_is_refused(tampered):
    item, gpu = tampered
    manifest = json.loads((gpu / "bundle.json").read_bytes())
    manifest["environment_digest"] = "sha256:" + "0" * 64
    (gpu / "bundle.json").write_bytes(
        json.dumps(manifest, indent=1, sort_keys=True).encode() + b"\n"
    )
    with pytest.raises(pipeline.CatalogBroken, match="not its CPU build's derivation"):
        pipeline.verify(item)


def test_a_ref_that_names_another_runtime_is_refused():
    item = copy.deepcopy(torch_entries()[0])
    item["bundle_refs"]["torch-cpu-py311"] = item["bundle_refs"].pop(
        "torch-cu130-py311"
    )
    with pytest.raises(pipeline.CatalogBroken, match="no GPU build is registered"):
        pipeline.verify(item)


def test_missing_gpu_files_are_refused(tampered):
    item, gpu = tampered
    shutil.rmtree(gpu)
    with pytest.raises(pipeline.CatalogBroken, match="files are missing"):
        pipeline.verify(item)


# --- per-runtime GPU receipts ---------------------------------------------------------------------------------

IMAGE = "sha256:" + "a" * 64


def test_the_smoke_only_list_is_the_two_named_entries_and_nothing_else():
    from carbon.backbone_catalog import gpu_receipt

    assert set(gpu_receipt.SMOKE_ONLY) == {"cno.CNO1d"}
    assert gpu_receipt.required_kind("cno.CNO1d") == "smoke"
    assert gpu_receipt.required_kind("neuralop.FNO") == "repeat"
    assert "not bit-reproducible on GPU" in gpu_receipt.SMOKE_NOTE


def test_a_repeat_receipt_needs_a_byte_identical_gpu_repeat():
    from carbon.backbone_catalog import gpu_receipt

    good = gpu_receipt.make(
        "neuralop.FNO",
        "torch-cu130-py311",
        image_digest=IMAGE,
        tested_on="RTX 4090 / 595.91",
        gpu_used=True,
        smoke_ok=True,
        pairs=2,
        identical=2,
    )
    gpu_receipt.check(good, "neuralop.FNO", "torch-cu130-py311")
    for change in (
        {"identical": 1, "differ": ["x"]},
        {"gpu_used": False},
        {"smoke_ok": False},
        {"kind": "smoke"},
    ):
        with pytest.raises(gpu_receipt.GpuReceiptBroken):
            gpu_receipt.check({**good, **change}, "neuralop.FNO", "torch-cu130-py311")
    with pytest.raises(gpu_receipt.GpuReceiptBroken):
        gpu_receipt.check(good, "neuralop.TFNO", "torch-cu130-py311")


def test_a_smoke_entry_takes_the_smoke_receipt_with_its_fixed_note_and_no_repeat_claim():
    from carbon.backbone_catalog import gpu_receipt

    for catalog_id in sorted(gpu_receipt.SMOKE_ONLY):
        smoke = gpu_receipt.make(
            catalog_id,
            "torch-cu130-py311",
            image_digest=IMAGE,
            tested_on="RTX 4090 / 595.91",
            gpu_used=True,
            smoke_ok=True,
        )
        assert smoke["kind"] == "smoke" and "pairs" not in smoke
        gpu_receipt.check(smoke, catalog_id, "torch-cu130-py311")
        with pytest.raises(
            gpu_receipt.GpuReceiptBroken
        ):  # a repeat receipt does not satisfy a smoke-only entry
            gpu_receipt.check(
                {**smoke, "kind": "repeat", "pairs": 2, "identical": 2, "differ": []},
                catalog_id,
                "torch-cu130-py311",
            )
        with pytest.raises(gpu_receipt.GpuReceiptBroken):
            gpu_receipt.check(
                {**smoke, "note": "reproducible"}, catalog_id, "torch-cu130-py311"
            )
        with pytest.raises(gpu_receipt.GpuReceiptBroken):
            gpu_receipt.check({**smoke, "pairs": 2}, catalog_id, "torch-cu130-py311")


def test_a_gpu_build_without_a_receipt_is_not_offered_and_a_bad_one_breaks_verify(
    tmp_path, monkeypatch
):
    from carbon.backbone_catalog import gpu_receipt

    item = torch_entries()[0]
    assert gpu_receipt.offered_runtimes(item) == [] or gpu_receipt.load(
        item["catalog_id"], "torch-cu130-py311"
    )
    monkeypatch.setattr(gpu_receipt, "RECEIPTS", tmp_path)
    assert gpu_receipt.offered_runtimes(item) == []
    bad = {
        "schema": gpu_receipt.SCHEMA,
        "catalog_id": item["catalog_id"],
        "runtime_profile_id": "torch-cu130-py311",
    }
    (tmp_path / f"{item['catalog_id']}.torch-cu130-py311.json").write_text(
        json.dumps(bad)
    )
    with pytest.raises(pipeline.CatalogBroken):
        pipeline.verify(item)


# --- the official route and a smoke-only GPU runtime ----------------------------------------------------------


def _with_receipt(monkeypatch, tmp_path, catalog_id, **kwargs):
    from carbon.backbone_catalog import gpu_receipt

    monkeypatch.setattr(gpu_receipt, "RECEIPTS", tmp_path)
    receipt = gpu_receipt.make(
        catalog_id,
        "torch-cu130-py311",
        image_digest=IMAGE,
        tested_on="RTX 4090 / 595.91",
        gpu_used=True,
        smoke_ok=True,
        **kwargs,
    )
    (tmp_path / f"{catalog_id}.torch-cu130-py311.json").write_text(json.dumps(receipt))


def test_the_official_route_refuses_a_smoke_only_gpu_runtime_with_a_typed_gap_naming_the_cpu_build(
    tmp_path, monkeypatch
):
    from carbon.backbone_catalog import served
    from carbon.backbone_catalog.entries import CatalogRefused
    from carbon.challenge_validator.dispatch import RECIPE_SCREEN_REFUSALS

    assert "catalog_runtime_not_reproducible" in RECIPE_SCREEN_REFUSALS
    for catalog_id in ("cno.CNO1d",):
        item = next(
            e for e in pipeline.load()["entries"] if e["catalog_id"] == catalog_id
        )
        _with_receipt(monkeypatch, tmp_path, catalog_id)
        practice = served.runtime_bundle_ref(item, "torch-cu130-py311", official=False)
        assert practice == item["bundle_refs"]["torch-cu130-py311"]
        with pytest.raises(CatalogRefused) as refused:
            served.runtime_bundle_ref(item, "torch-cu130-py311", official=True)
        assert refused.value.code == "catalog_runtime_not_reproducible"
        assert (
            "GPU practice only; official grading rebuilds on CPU"
            in refused.value.detail
        )
        assert item["bundle_ref"]["bundle_digest"] in refused.value.detail
        # the CPU build stays officially gradable
        assert (
            served.runtime_bundle_ref(item, "torch-cpu-py311", official=True)
            == item["bundle_ref"]
        )


def test_a_repeat_receipt_backs_practice_but_the_official_route_needs_an_official_grade_one(
    tmp_path, monkeypatch
):
    from carbon.backbone_catalog import gpu_receipt, served
    from carbon.backbone_catalog.entries import CatalogRefused

    item = next(
        e for e in pipeline.load()["entries"] if e["catalog_id"] == "neuralop.FNO"
    )
    runtime = "torch-cu130-py311"
    monkeypatch.setattr(gpu_receipt, "RECEIPTS", tmp_path)
    with pytest.raises(CatalogRefused) as none:
        served.runtime_bundle_ref(item, runtime, official=True)
    assert none.value.code == "catalog_entry_unknown"
    _with_receipt(monkeypatch, tmp_path, "neuralop.FNO", pairs=2, identical=2)
    ref = item["bundle_refs"][runtime]
    # the venv-grade receipt offers the GPU build for practice ...
    assert served.runtime_bundle_ref(item, runtime, official=False) == ref
    # ... and the official route refuses it: no pinned image, no determinism environment, no registered host class
    with pytest.raises(CatalogRefused) as refused:
        served.runtime_bundle_ref(item, runtime, official=True)
    assert refused.value.code == "catalog_runtime_not_reproducible"
    assert "not on the pinned GPU worker image" in refused.value.detail
    assert item["bundle_ref"]["bundle_digest"] in refused.value.detail


def test_only_a_receipt_with_the_pinned_image_the_full_determinism_environment_and_a_registered_host_is_official_grade(
    tmp_path, monkeypatch
):
    from carbon.backbone_catalog import gpu_receipt, served
    from carbon.backbone_catalog.entries import CatalogRefused

    item = next(
        e for e in pipeline.load()["entries"] if e["catalog_id"] == "neuralop.FNO"
    )
    runtime = "torch-cu130-py311"
    monkeypatch.setattr(gpu_receipt, "RECEIPTS", tmp_path)
    receipt = gpu_receipt.make(
        "neuralop.FNO",
        runtime,
        image_digest=IMAGE,
        tested_on="RTX 4090 / 595.91",
        gpu_used=True,
        smoke_ok=True,
        pairs=2,
        identical=2,
    )
    receipt.update(
        determinism=gpu_receipt.required_determinism(runtime), host_class="rtx4090-v1"
    )
    target = tmp_path / f"neuralop.FNO.{runtime}.json"

    def official():
        target.write_text(json.dumps(receipt))
        return served.runtime_bundle_ref(item, runtime, official=True)

    with pytest.raises(CatalogRefused, match="pinned GPU worker image"):
        official()
    monkeypatch.setattr(gpu_receipt, "PINNED_GPU_IMAGES", {runtime: frozenset({IMAGE})})
    with pytest.raises(CatalogRefused, match="registered host class"):
        official()
    monkeypatch.setattr(
        gpu_receipt, "REGISTERED_HOST_CLASSES", frozenset({"rtx4090-v1"})
    )
    assert official() == item["bundle_refs"][runtime]
    receipt["determinism"] = [["use_deterministic_algorithms", False]]
    with pytest.raises(CatalogRefused, match="full determinism environment"):
        official()
    receipt["determinism"] = gpu_receipt.required_determinism(runtime)
    receipt["image_digest"] = "sha256:" + "b" * 64
    with pytest.raises(CatalogRefused, match="pinned GPU worker image"):
        official()


def test_the_warn_only_list_is_a_subset_of_the_smoke_only_list():
    from carbon.backbone_catalog import gpu_receipt

    assert set(gpu_build.WARN_ONLY_DETERMINISM) <= set(gpu_receipt.SMOKE_ONLY)


def test_the_receivers_recipe_screen_refuses_a_smoke_only_gpu_bundle_ref_before_reserve():
    from carbon.backbone_catalog.entries import CatalogRefused
    from carbon.challenge_kit import physical_material
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

    kit = physical_material.bundle_material("electric-motor-magnetics", "1.3")[
        "construction_kit"
    ]
    adapter = object.__new__(LeanRecipeAdapter)
    adapter._kit = kit

    def recipe_for(item, ref):
        return {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "bundle", "bundle_ref": ref},
            "procedure": {
                "entrypoint": item["entrypoint"],
                "configuration": item["defaults"]["configuration"],
                "train_use": {},
                "initial_state": None,
            },
            "output": {
                "format": item["output_format"],
                "interface_digest": kit["interface_digest"],
            },
        }

    entries = {e["catalog_id"]: e for e in pipeline.load()["entries"]}
    for catalog_id in ("cno.CNO1d",):
        item = entries[catalog_id]
        gpu_ref = item["bundle_refs"]["torch-cu130-py311"]
        with pytest.raises(CatalogRefused) as refused:
            adapter.validate_strategy(recipe_for(item, gpu_ref))
        assert refused.value.code == "catalog_runtime_not_reproducible"
        assert item["bundle_ref"]["bundle_digest"] in refused.value.detail
        # the CPU build is officially fine, and practice (runtime_bundle_ref official=False) still gets the GPU ref
        assert adapter.validate_strategy(recipe_for(item, item["bundle_ref"]))
    other = entries["neuralop.FNO"]
    # every GPU ref is refused officially until it has an official-grade receipt; its CPU build is fine
    with pytest.raises(CatalogRefused) as refused_other:
        adapter.validate_strategy(
            recipe_for(other, other["bundle_refs"]["torch-cu130-py311"])
        )
    assert refused_other.value.code == "catalog_runtime_not_reproducible"
    assert adapter.validate_strategy(recipe_for(other, other["bundle_ref"]))


def test_a_receipt_without_an_image_must_name_its_environment():
    from carbon.backbone_catalog import gpu_receipt

    ok = gpu_receipt.make(
        "neuralop.FNO",
        "torch-cu130-py311",
        image_digest=None,
        environment="uv venv, torch 2.13.0+cu130",
        tested_on="RTX 4090 / 595.71",
        gpu_used=True,
        smoke_ok=True,
        pairs=1,
        identical=1,
    )
    gpu_receipt.check(ok, "neuralop.FNO", "torch-cu130-py311")
    for change in ({"environment": ""}, {"environment": None}):
        with pytest.raises(gpu_receipt.GpuReceiptBroken):
            gpu_receipt.check({**ok, **change}, "neuralop.FNO", "torch-cu130-py311")


def test_every_listed_gpu_build_with_a_receipt_has_a_valid_one():
    from carbon.backbone_catalog import gpu_receipt

    offered = 0
    for item in pipeline.load()["entries"]:
        for runtime in item.get("bundle_refs") or {}:
            if gpu_receipt.path(item["catalog_id"], runtime).exists():
                offered += 1
                assert (
                    gpu_receipt.load(item["catalog_id"], runtime)["runtime_profile_id"]
                    == runtime
                )
    assert offered


# --- the warn-only determinism exception (CNO1d only) -------------------------------------------------


def _common(path):
    with tarfile.open(path) as archive:
        member = [
            m
            for m in archive.getmembers()
            if m.isfile() and m.name.endswith(gpu_build.COMMON_MEMBER)
        ][0]
        return archive.extractfile(member).read().decode()


def test_the_warn_only_exception_is_exactly_the_smoke_only_list():
    from carbon.backbone_catalog import gpu_receipt

    assert (
        set(gpu_build.WARN_ONLY_DETERMINISM)
        == set(gpu_receipt.SMOKE_ONLY)
        == {"cno.CNO1d"}
    )


def test_only_the_named_gpu_twin_relaxes_determinism_and_the_cpu_builds_never_do():
    for item in torch_entries():
        if has_no_twin_by_design(item):
            continue
        root = pipeline.BUNDLES / item["catalog_id"]
        cpu, gpu = _common(root / "source.tar.gz"), _common(
            root / "torch-cu130-py311" / "source.tar.gz"
        )
        assert "warn_only" not in cpu
        if item["catalog_id"] in gpu_build.WARN_ONLY_DETERMINISM:
            assert gpu == cpu.replace(gpu_build.DETERMINISM, gpu_build.WARN_ONLY)
        else:
            assert gpu == cpu


def _copy_entry(tmp_path, catalog_id):
    from pathlib import Path

    source = Path(pipeline.__file__).resolve().parent / "bundles" / catalog_id
    shutil.copytree(source, tmp_path / catalog_id)
    return tmp_path / catalog_id / "torch-cu130-py311"


def _with_source(gpu_dir, source_bytes):
    (gpu_dir / "source.tar.gz").write_bytes(source_bytes)


def test_verify_refuses_the_exception_on_a_third_entry_and_a_missing_one_on_a_named_entry(
    tmp_path, monkeypatch
):
    named = next(e for e in torch_entries() if e["catalog_id"] == "cno.CNO1d")
    third = next(e for e in torch_entries() if e["catalog_id"] == "neuralop.FNO")
    gpu_named = _copy_entry(tmp_path, named["catalog_id"])
    gpu_third = _copy_entry(tmp_path, third["catalog_id"])
    cpu_named = (tmp_path / named["catalog_id"] / "source.tar.gz").read_bytes()
    cpu_third = (tmp_path / third["catalog_id"] / "source.tar.gz").read_bytes()
    monkeypatch.setattr(pipeline, "BUNDLES", tmp_path)
    pipeline.verify(named)
    pipeline.verify(third)
    # a named entry whose GPU twin lacks the exception is not the derivation
    _with_source(gpu_named, gpu_build.patched_source(cpu_named))
    with pytest.raises(pipeline.CatalogBroken, match="not its CPU build's derivation"):
        pipeline.verify(named)
    # a third entry carrying the exception is not the derivation either
    _with_source(gpu_third, _relax(gpu_build.patched_source(cpu_third)))
    with pytest.raises(pipeline.CatalogBroken, match="not its CPU build's derivation"):
        pipeline.verify(third)


def _relax(source):
    """A GPU source with determinism relaxed, as a mistaken exception on a non-named entry would be."""
    files, root = {}, None
    with tarfile.open(fileobj=io.BytesIO(source), mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile():
                root = root or member.name.split("/", 1)[0]
                files[member.name.split("/", 1)[1]] = archive.extractfile(member).read()
    files[gpu_build.COMMON_MEMBER] = (
        files[gpu_build.COMMON_MEMBER]
        .decode()
        .replace(gpu_build.DETERMINISM, gpu_build.WARN_ONLY)
        .encode()
    )
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
    import gzip

    with gzip.GzipFile(fileobj=zipped, mode="wb", filename="", mtime=0) as stream:
        stream.write(packed.getvalue())
    return zipped.getvalue()


def test_lsm_has_no_gpu_twin_and_a_gpu_ref_for_it_is_refused(tmp_path, monkeypatch):
    from carbon.backbone_catalog import gpu_receipt

    assert gpu_build.NO_GPU_TWIN == ("thuml.LSM", "f08.thuml.LSM")
    assert "thuml.LSM" not in gpu_receipt.SMOKE_ONLY
    lsm = next(e for e in pipeline.load()["entries"] if e["catalog_id"] == "thuml.LSM")
    assert "bundle_refs" not in lsm
    assert not (pipeline.BUNDLES / "thuml.LSM" / "torch-cu130-py311").exists()
    assert not gpu_receipt.path("thuml.LSM", "torch-cu130-py311").exists()
    with pytest.raises(gpu_build.GpuBuildRefused, match="no GPU twin"):
        gpu_build.derived_source("torch-cpu-py311", b"", "thuml.LSM")
    fake = copy.deepcopy(lsm)
    fake["bundle_refs"] = {"torch-cu130-py311": lsm["bundle_ref"]}
    with pytest.raises(pipeline.CatalogBroken, match="no GPU twin"):
        pipeline.verify(fake)


DEVICE_FIXED = ("lno.LNO1d", "neuralop.GINO", "physicsnemo.MeshGraphNet")


def _members(path):
    with tarfile.open(path) as archive:
        return {
            m.name.split("/", 1)[1]: archive.extractfile(m).read()
            for m in archive.getmembers()
            if m.isfile()
        }


def test_the_three_device_fixed_twins_differ_from_their_cpu_build_by_the_registered_fixes_only():
    """RTX 4090 repeat (2026-10-22): helper tensors made on the CPU inside `forward` move to the input's device in the
    GPU twin; the CPU build's bytes are untouched and no other entry carries a device fix.
    """
    assert set(gpu_build.DEVICE_FIXES) == set(DEVICE_FIXED)
    for catalog_id in DEVICE_FIXED:
        base = pipeline.BUNDLES / catalog_id
        cpu = _members(base / "source.tar.gz")
        gpu = _members(base / "torch-cu130-py311" / "source.tar.gz")
        changed = {name for name in cpu if cpu[name] != gpu[name]}
        assert set(cpu) == set(gpu)
        assert changed == {"carbon_candidate/backbones.py", "carbon_candidate/build.py"}
        text = gpu["carbon_candidate/backbones.py"].decode()
        for _, before, after in gpu_build.DEVICE_FIXES[catalog_id]:
            assert after in text and before not in text
        assert "device" in text


def test_an_unlisted_entry_gets_no_device_fix_and_a_listed_one_missing_its_anchor_is_refused():
    raw = (pipeline.BUNDLES / "neuralop.FNO" / "source.tar.gz").read_bytes()
    # An entry outside the three-entry list is derived by the first change alone.
    assert "neuralop.FNO" not in gpu_build.DEVICE_FIXES
    assert gpu_build.derived_source(
        "torch-cpu-py311", raw, "neuralop.FNO"
    ) == gpu_build.derived_source("torch-cpu-py311", raw, None)
    # A listed entry whose build lacks the anchor exactly once is refused, never skipped.
    with pytest.raises(gpu_build.GpuBuildRefused, match="device fix anchor found 0"):
        gpu_build.derived_source("torch-cpu-py311", raw, "neuralop.GINO")


def test_the_catalog_constants_equal_the_accelerator_profile():
    """The catalog copies the JAX GPU lock and determinism constants instead of importing the accelerator profile (the
    protected-material boundary); this is the one place that compares them, outside the scanned `carbon/` tree.
    """
    from carbon.backbone_catalog import gpu_receipt
    from carbon.reconstruction import accelerators

    assert (
        gpu_build.JAX_GPU_LOCK_DIGEST
        == accelerators.GPU_PROFILE.environment_lock_digest
    )
    assert (
        gpu_receipt.JAX_DETERMINISM_XLA_FLAGS == accelerators.GPU_DETERMINISM_XLA_FLAGS
    )
    assert (
        gpu_receipt.JAX_DETERMINISM_ENVIRONMENT
        == accelerators.GPU_DETERMINISM_ENVIRONMENT
    )
