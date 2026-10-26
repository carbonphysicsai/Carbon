"""GPU-2: the GPU twins of the served v2 examples (Motor, Cooling), from the existing transform.

The twin is the CPU build plus the registered change and nothing else
(`pipeline.verify` re-derives it). It is listed under `bundle_refs`, so the
served document and its catalog digest do not move, and it is OFFERED only once
a GPU receipt proves it; until then a practice on a GPU host says why it ran on
the CPU.
"""

from __future__ import annotations

import json

import pytest

from carbon.backbone_catalog import gpu_build, gpu_receipt, listing, pipeline, served

TWINS = {
    "v2.motor.cno.CNO1d": gpu_build.PROFILE,
    "v2.cooling.cno.CNO1d": gpu_build.PROFILE,
    "v2.motor.jno.bcat": gpu_build.JAX_PROFILE,
    "v2.cooling.jno.bcat": gpu_build.JAX_PROFILE,
}


def _item(catalog_id):
    (item,) = [e for e in pipeline.load()["entries"] if e["catalog_id"] == catalog_id]
    return item


@pytest.mark.parametrize("catalog_id,runtime", sorted(TWINS.items()))
def test_each_served_example_lists_its_twin_and_verifies(catalog_id, runtime):
    item = _item(catalog_id)
    assert set(item["bundle_refs"]) == {runtime}
    pipeline.verify(
        item
    )  # re-derives the files from the CPU build; refuses any difference


def test_the_whole_catalog_still_verifies():
    assert len(pipeline.verify_all()) == 241


@pytest.mark.parametrize("catalog_id,runtime", sorted(TWINS.items()))
def test_a_twin_is_not_offered_without_a_gpu_receipt(catalog_id, runtime):
    item = listing.entry(catalog_id)
    assert runtime not in gpu_receipt.offered_runtimes(item)
    recipe = {
        "challenge": {
            "id": item["challenges"][0]["id"],
            "version": item["challenges"][0]["version"],
        },
        "source": {
            "kind": "catalog",
            "catalog_id": catalog_id,
            "catalog_digest": served.digest(
                item["challenges"][0]["id"], item["challenges"][0]["version"]
            ),
        },
        "procedure": {"configuration": {}, "train_use": {}},
        "output": {"format": item["output_format"]},
    }
    with pytest.raises(served.GpuBuildNotOffered) as refused:
        served.expand(recipe, runtime)
    assert refused.value.code == "catalog_gpu_build_not_offered"


def test_the_served_document_does_not_name_the_gpu_builds():
    for challenge, version in (
        ("electric-motor-magnetics", "1.4"),
        ("chip-cold-plate", "1.4"),
    ):
        text = json.dumps(served.document(challenge, version))
        assert (
            "bundle_refs" not in text and "cu130" not in text and "cuda13" not in text
        )


def test_the_cno1d_twins_carry_the_one_warn_only_change_and_the_jax_twins_none():
    for catalog_id in ("v2.motor.cno.CNO1d", "v2.cooling.cno.CNO1d"):
        assert catalog_id in gpu_build.WARN_ONLY_DETERMINISM
        assert gpu_receipt.required_kind(catalog_id) == "smoke"
    for catalog_id in ("v2.motor.jno.bcat", "v2.cooling.jno.bcat"):
        assert catalog_id not in gpu_build.WARN_ONLY_DETERMINISM
        assert gpu_receipt.required_kind(catalog_id) == "repeat"
        root = pipeline.BUNDLES / catalog_id
        twin = root / gpu_build.JAX_PROFILE
        # JAX runs on the GPU by default: the source is byte-identical.
        assert (twin / "source.tar.gz").read_bytes() == (
            root / "source.tar.gz"
        ).read_bytes()


def test_lsm_has_no_twin_under_its_v2_ids_either():
    for catalog_id in (
        "v2.motor.thuml.LSM",
        "v2.cooling.thuml.LSM",
        "v2.f08.thuml.LSM",
        "v2.f02.thuml.LSM",
    ):
        assert catalog_id in gpu_build.NO_GPU_TWIN
    with pytest.raises(pipeline.CatalogBroken):
        pipeline.add_twin("v2.motor.thuml.LSM")


def test_an_unknown_entry_is_refused():
    with pytest.raises(pipeline.CatalogBroken):
        pipeline.add_twin("v2.nope")
