"""Practice serves a GPU build only when it is offered (a valid receipt); the official route is stricter (Validator, 2026-10-22).

Three rules, one test each, plus the hold on CNO1d's GPU twin until the owner confirms O-WARN directly.
"""

import pytest

from carbon.backbone_catalog import gpu_receipt, pipeline, served

GPU = "torch-cu130-py311"


def entry(catalog_id):
    return pipeline.entry(catalog_id)


def test_practice_without_a_receipt_is_refused_naming_the_cpu_build(
    tmp_path, monkeypatch
):
    item = entry("neuralop.FNO")
    monkeypatch.setattr(gpu_receipt, "RECEIPTS", tmp_path)  # no receipt anywhere
    with pytest.raises(served.GpuBuildNotOffered) as refused:
        served._bundle_ref(item, GPU)
    assert refused.value.code == "catalog_gpu_build_not_offered"
    assert item["bundle_ref"]["bundle_digest"] in str(refused.value)
    assert isinstance(
        refused.value, served.GpuBuildMissing
    )  # the same fallback handler covers it


def test_practice_with_a_smoke_receipt_is_served():
    item = entry("cno.CNO1d")
    assert gpu_receipt.required_kind("cno.CNO1d") == "smoke"
    assert GPU in gpu_receipt.offered_runtimes(item)
    assert served._bundle_ref(item, GPU) == item["bundle_refs"][GPU]


def test_the_official_route_refuses_a_smoke_receipt():
    item = entry("cno.CNO1d")
    with pytest.raises(served.CatalogRefused) as refused:
        served.runtime_bundle_ref(item, GPU, official=True)
    assert refused.value.code == "catalog_runtime_not_reproducible"
    # practice is not the official route: the same entry's GPU build is served there
    assert (
        served.runtime_bundle_ref(item, GPU, official=False) == item["bundle_refs"][GPU]
    )


def test_a_repeat_receipt_entry_is_served_for_practice():
    item = entry("neuralop.FNO")
    assert GPU in gpu_receipt.offered_runtimes(item)
    assert served._bundle_ref(item, GPU) == item["bundle_refs"][GPU]
    # the CPU build is the default and is never affected
    assert served._bundle_ref(item, None) == item["bundle_ref"]


def test_cno1d_gpu_twin_is_offered_for_practice_and_nothing_is_on_hold():
    """OWNER-CATALOG-CNO1D-WARN-ONLY-01: the owner confirmed the warn-only exception; the hold is gone."""
    assert not hasattr(gpu_receipt, "OWNER_CONFIRMATION_PENDING")
    item = entry("cno.CNO1d")
    assert GPU in gpu_receipt.offered_runtimes(item)
    assert served._bundle_ref(item, GPU) == item["bundle_refs"][GPU]
