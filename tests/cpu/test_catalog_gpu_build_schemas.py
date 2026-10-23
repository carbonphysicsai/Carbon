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
