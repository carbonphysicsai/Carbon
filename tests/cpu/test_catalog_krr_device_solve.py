"""The physics-prior (prior_krr) GPU twins solve their kernel-ridge system on the device (Lead, 2026-10-29).

The CPU build solves a float64 Cholesky system in NumPy, so its twin would train on the CPU. The twin derived by
`gpu_build` moves that one solve to the JAX device with x64 enabled for the solve only; the official environment keeps
JAX_ENABLE_X64=false for everything else. The change is on an explicit four-entry list and `pipeline.verify`
re-derives it, so a twin can never differ from its CPU build by more than this.
"""

import io
import tarfile

import pytest

from carbon.backbone_catalog import gpu_build, pipeline

KRR = {
    "v2.motor.prior_krr",
    "v2.cooling.prior_krr",
    "v2.f08.prior_krr",
    "v2.f02.prior_krr",
}


def _item(catalog_id):
    (item,) = [e for e in pipeline.load()["entries"] if e["catalog_id"] == catalog_id]
    return item


def _members(raw):
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile():
                files[member.name.split("/", 1)[1]] = archive.extractfile(member).read()
    return files


def test_the_list_is_exactly_the_four_prior_krr_entries():
    assert set(gpu_build.JAX_X64_SOLVE) == KRR
    in_catalog = {
        e["catalog_id"]
        for e in pipeline.load()["entries"]
        if "prior_krr" in e["catalog_id"]
    }
    assert in_catalog == KRR


@pytest.mark.parametrize("catalog_id", sorted(KRR))
def test_the_twin_solves_on_the_device_and_differs_from_the_cpu_build_only_there(
    catalog_id,
):
    item = _item(catalog_id)
    cpu = _members(pipeline.bundle_files(item)["source.tar.gz"])
    twin = _members(
        (
            pipeline.BUNDLES / catalog_id / gpu_build.JAX_PROFILE / "source.tar.gz"
        ).read_bytes()
    )
    assert set(cpu) == set(twin)
    assert [m for m in cpu if cpu[m] != twin[m]] == [gpu_build.KRR_MEMBER]
    before = cpu[gpu_build.KRR_MEMBER].decode()
    after = twin[gpu_build.KRR_MEMBER].decode()
    assert gpu_build.KRR_CALL in before and "_solve_spd_device" not in before
    assert gpu_build.KRR_CALL not in after and gpu_build.KRR_CALL_GPU in after
    # Exactly the registered edit: the call and the helper, nothing else.
    expected = before.replace(gpu_build.KRR_CALL, gpu_build.KRR_CALL_GPU).replace(
        gpu_build.KRR_ANCHOR, gpu_build.KRR_HELPER + gpu_build.KRR_ANCHOR
    )
    assert after == expected


def test_the_helper_enables_x64_for_the_solve_only_and_restores_it():
    helper = gpu_build.KRR_HELPER
    assert 'jax.config.update("jax_enable_x64", True)' in helper
    assert "finally:" in helper
    assert 'jax.config.update("jax_enable_x64", before)' in helper
    assert helper.index("finally:") < helper.index('jax_enable_x64", before')
    assert "jnp.linalg.cholesky" in helper and "cho_solve" in helper
    # A matrix that is not positive definite is refused as the CPU build refuses it.
    assert "raise krr.ridge" in helper
    compile(helper, "helper", "exec")


def test_every_other_jax_twin_stays_byte_identical_to_its_cpu_build():
    checked = 0
    for item in pipeline.load()["entries"]:
        catalog_id = item["catalog_id"]
        if gpu_build.JAX_PROFILE not in (item.get("bundle_refs") or {}):
            continue
        if catalog_id in KRR:
            continue
        twin = pipeline.BUNDLES / catalog_id / gpu_build.JAX_PROFILE / "source.tar.gz"
        assert (
            twin.read_bytes() == pipeline.bundle_files(item)["source.tar.gz"]
        ), catalog_id
        checked += 1
    assert checked > 0
