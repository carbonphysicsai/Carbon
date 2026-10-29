"""Every CNO1d entry is CPU lane only for official grading (Validator ruling, 2026-10-29).

Its GPU build's upsample backward (`upsample_bicubic2d_aa`) has no deterministic CUDA
kernel, so a second GPU rebuild can differ and a passing sample proves nothing. The
list is pinned across every Challenge version (f02 and f08 included), the official
route refuses any CNO1d GPU build, and miners see that the rebuild is on the CPU.
"""

import pytest

from carbon.backbone_catalog import gpu_build, gpu_receipt, listing
from carbon.backbone_catalog.served import (
    CatalogRefused,
    refuse_unreproducible_runtime,
    runtime_bundle_ref,
)

CNO1D = {
    "cno.CNO1d",
    "v2.motor.cno.CNO1d",
    "v2.cooling.cno.CNO1d",
    "v2.f08.cno.CNO1d",
    "v2.f02.cno.CNO1d",
}


def _manifest_cno1d():
    return {
        e["catalog_id"]: e
        for e in listing.load()["entries"]
        if e["catalog_id"].endswith("CNO1d")
    }


LSM = {
    "thuml.LSM",
    "f08.thuml.LSM",
    "v2.motor.thuml.LSM",
    "v2.cooling.thuml.LSM",
    "v2.f08.thuml.LSM",
    "v2.f02.thuml.LSM",
}
ALL = CNO1D | listing.LEGACY_CPU_REBUILD


def test_the_cno1d_list_is_every_cno1d_entry_in_the_catalog():
    # A new CNO1d entry cannot join the catalog without joining the CPU-only list.
    assert set(_manifest_cno1d()) == ALL
    # CNO1d, plus thuml.LSM (same decision, same lists): a short explicit list, never a skip.
    assert set(gpu_receipt.SMOKE_ONLY) == CNO1D | LSM
    assert set(gpu_build.WARN_ONLY_DETERMINISM) == CNO1D | LSM


@pytest.mark.parametrize("catalog_id", sorted(ALL))
def test_the_official_route_never_takes_a_cno1d_gpu_build(catalog_id):
    item = _manifest_cno1d()[catalog_id]
    for ref in (item.get("bundle_refs") or {}).values():
        with pytest.raises(CatalogRefused) as refused:
            refuse_unreproducible_runtime(ref)
        assert refused.value.code == "catalog_runtime_not_reproducible"
    # The CPU build is the official one, unchanged.
    base = item["bundle_ref"]
    assert runtime_bundle_ref(item, base["runtime_profile_id"], official=True) == base


def test_miners_see_the_cpu_rebuild_on_cno1d_and_only_there():
    note = listing.CPU_REBUILD_NOTE
    assert "CPU rebuild on this validator class" in note
    seen = 0
    for e in listing.load()["entries"]:
        text = listing.summary(e["catalog_id"], e["backbone"], None, None)
        labelled = e["catalog_id"] in ALL | LSM
        assert (note in text) == labelled, e["catalog_id"]
        seen += labelled
    assert seen == len(ALL | LSM)
