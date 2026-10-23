"""Each Torch catalog settings schema accepts its entries' GPU
(`torch-cu130-py311`) build too (Graphite Test's `gpu_build`, U58): the same
vocabulary, its own build hash, beside the CPU one."""

from __future__ import annotations

from carbon.backbone_catalog import settings


def test_each_torch_schema_accepts_its_cpu_and_its_gpu_build():
    torch = (
        settings.COVERAGE,
        settings.LEVERS,
        settings.COOLING_LEVERS,
        settings.F08_LEVERS,
        settings.F02_LEVERS,
        settings.COVERAGE_F32,
    )
    assert set(settings.GPU_BUILDS) == {schema.schema_id for schema in torch}
    for schema in torch:
        gpu = settings.GPU_BUILDS[schema.schema_id]
        assert gpu.startswith("sha256:") and len(gpu) == 71
        assert settings.build_hashes(schema.schema_id) == (schema.build_sha256, gpu)
        assert settings.schema_for_build(schema.build_sha256) == schema.schema_id
        assert settings.schema_for_build(gpu) == schema.schema_id
    # The JAX build has no Torch GPU twin.
    jax = settings.JAX_LEVERS.schema_id
    assert settings.build_hashes(jax) == (settings.JAX_LEVERS.build_sha256,)
    # Every build hash, CPU or GPU, names one schema only.
    every = [h for s in settings.SCHEMAS for h in settings.build_hashes(s)]
    assert len(every) == len(set(every))


def test_every_shipped_gpu_twin_build_is_one_its_schema_accepts():
    # The float32 coverage line (F08 1.4, F02 2.3) shipped GPU twins whose
    # build hash no schema accepted, so their GPU practice could not run.
    import hashlib
    import tarfile
    from pathlib import Path

    bundles = Path(settings.__file__).parent / "bundles"
    twins = sorted(bundles.glob("*/torch-cu130-py311/source.tar.gz"))
    assert twins
    for twin in twins:
        cpu = twin.parent.parent / "source.tar.gz"
        with tarfile.open(cpu) as a, tarfile.open(twin) as b:
            hashes = []
            for archive in (a, b):
                member = next(
                    (
                        m
                        for m in archive.getmembers()
                        if m.name.endswith("carbon_candidate/build.py")
                    ),
                    None,
                )
                if member is None:
                    break
                data = archive.extractfile(member).read()
                hashes.append("sha256:" + hashlib.sha256(data).hexdigest())
        if len(hashes) != 2:
            continue  # not a settings-schema build
        try:
            schema = settings.schema_for_build(hashes[0])
        except settings.CatalogRefused:
            continue  # its CPU build is not a settings-schema build either
        assert hashes[1] in settings.build_hashes(schema), twin.parent.parent.name
