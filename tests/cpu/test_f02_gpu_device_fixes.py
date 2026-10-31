"""The F02 GPU twins of `lno.LNO1d` and `neuralop.GINO` carry the registered device fixes; no other twin moved.

The GPU screen found `v2.f02.lno.LNO1d` and `v2.f02.neuralop.GINO` failing on a GPU build with 'tensors on different devices
(cpu vs cuda)', while the same backbones pass on Motor and F08. The F02 v2 sources still build the DFT matrices and the
query-row index on the CPU inside `forward`, and `gpu_build.DEVICE_FIXES` is keyed by the original ids, so their twins were
derived with no fix. `gpu_build.device_fix_key` now selects the same fixes for those two F02 entries. These tests pin that
both twins carry device placement, that they are the derivation of their CPU build, and that every other twin is byte
unchanged (their SHA-256 pins were taken from the committed twins before this change)."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from carbon.backbone_catalog import gpu_build, pipeline

BUNDLES = Path(pipeline.BUNDLES)
TWIN = "torch-cu130-py311"


def member(raw: bytes, name: str) -> str:
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for entry in archive.getmembers():
            if entry.isfile() and entry.name.split("/", 1)[1] == name:
                return archive.extractfile(entry).read().decode("utf-8")
    raise AssertionError(name)


def twin_source(catalog_id: str) -> bytes:
    return (BUNDLES / catalog_id / TWIN / "source.tar.gz").read_bytes()


def cpu_source(catalog_id: str) -> bytes:
    return (BUNDLES / catalog_id / "source.tar.gz").read_bytes()


BACKBONES = "carbon_candidate/backbones.py"


def test_the_f02_lno_twin_places_its_dft_matrices_on_the_inputs_device():
    twin = member(twin_source("v2.f02.lno.LNO1d"), BACKBONES)
    cpu = member(cpu_source("v2.f02.lno.LNO1d"), BACKBONES)
    assert "def _mats():" in cpu and "def _mats(device=None):" in twin
    assert "_mats(x.device)" in twin and "_mats(z.device)" in twin
    assert ".to(torch.float32).to(device)" in twin
    assert twin != cpu


def test_the_f02_gino_twin_places_its_query_rows_on_the_index_device():
    twin = member(twin_source("v2.f02.neuralop.GINO"), BACKBONES)
    cpu = member(cpu_source("v2.f02.neuralop.GINO"), BACKBONES)
    assert "torch.arange(self.n_queries).view(-1, 1)" in cpu
    assert "torch.arange(self.n_queries, device=self.query_index.device)" in twin
    assert twin != cpu


@pytest.mark.parametrize("catalog_id", ["v2.f02.lno.LNO1d", "v2.f02.neuralop.GINO"])
def test_the_committed_f02_twin_is_the_derivation_of_its_cpu_build(catalog_id):
    derived = gpu_build.derived_source(
        "torch-cpu-py311", cpu_source(catalog_id), catalog_id
    )
    assert derived == twin_source(catalog_id)
    item = next(
        e for e in pipeline.load_fresh()["entries"] if e["catalog_id"] == catalog_id
    )
    pipeline.verify(item)  # the manifest's ref, the files and the derivation all agree
    ref = item["bundle_refs"][TWIN]
    manifest = json.loads((BUNDLES / catalog_id / TWIN / "bundle.json").read_text())
    assert ref == gpu_build.bundle_ref(manifest)


#: SHA-256 of every other candidate twin's source, taken from the committed twins before this change: none moved.
UNCHANGED = {
    "v2.motor.lno.LNO1d": "77dd2bea2daadd39fb4977c324a9b858ec30088b3aa55e4f44597b04ee4c8a2f",
    "v2.motor.neuralop.GINO": "a6547af0590a90286106808031c47c46688010c57917e4013c8d84a108506b5f",
    "v2.f08.lno.LNO1d": "ddac2671b101544f2dc0e8aa6f17ac30c8705d4129762c310fab0ffd3e90be53",
    "v2.f08.neuralop.GINO": "c5fd4d2d730fdb7db903178fbb8397a6f24f5c1052dc1a481095cfc138765d8b",
    "v2.cooling.lno.LNO1d": "bdf3776a6877d47964403d706922d69dfb011feba3b48cd5df76b80fcf16efdc",
    "v2.cooling.neuralop.GINO": "c3cb40b3b3fa17ac0895fb460bd68cb8805200bda05e42de44bfeffcc1d9e317",
    "v2.f02.neuralop.LocalNO": "31434f2a08c4e6a0ff58abca2bd0473ca386d559def4b39e4449ccb38dbf68e6",
    "v2.f02.physicsnemo.MeshGraphNet": "64df22db06a5fbad5a9694dc7dbec86bcf91656633d293ee678006896b9771a3",
}


@pytest.mark.parametrize(("catalog_id", "expected"), sorted(UNCHANGED.items()))
def test_every_other_twin_is_byte_unchanged_and_still_its_derivation(
    catalog_id, expected
):
    committed = twin_source(catalog_id)
    assert hashlib.sha256(committed).hexdigest() == expected
    assert (
        gpu_build.derived_source("torch-cpu-py311", cpu_source(catalog_id), catalog_id)
        == committed
    )


def test_the_motor_and_f08_sources_already_place_their_tensors_so_no_fix_applies():
    # why those twins need nothing: their v2 sources are device-aware, so the registered anchors are absent
    for catalog_id in ("v2.motor.lno.LNO1d", "v2.f08.lno.LNO1d"):
        cpu = member(cpu_source(catalog_id), BACKBONES)
        assert "def _mats(device):" in cpu and "def _mats():" not in cpu
    for catalog_id in ("v2.motor.neuralop.GINO", "v2.f08.neuralop.GINO"):
        cpu = member(cpu_source(catalog_id), BACKBONES)
        assert "torch.arange(self.n_queries).view(-1, 1)" not in cpu


def test_the_fix_key_maps_only_the_two_f02_entries():
    assert gpu_build.device_fix_key("v2.f02.lno.LNO1d") == "lno.LNO1d"
    assert gpu_build.device_fix_key("v2.f02.neuralop.GINO") == "neuralop.GINO"
    for other in (
        "lno.LNO1d",
        "neuralop.GINO",
        "v2.motor.lno.LNO1d",
        "v2.f08.neuralop.GINO",
        "v2.cooling.lno.LNO1d",
        "v2.f02.neuralop.LocalNO",
        "v2.f02.physicsnemo.MeshGraphNet",
        "v2.f02.prior_krr",
        None,
    ):
        assert gpu_build.device_fix_key(other) == other


def test_an_f02_source_missing_an_anchor_is_refused_not_skipped():
    # the transform never silently skips a fix: a source without exactly one anchor stops the derivation
    raw = cpu_source("v2.f02.lno.LNO1d")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for entry in archive.getmembers():
            if entry.isfile():
                files[entry.name] = archive.extractfile(entry).read()
    root = next(iter(files)).split("/", 1)[0]
    key = f"{root}/{BACKBONES}"
    files[key] = files[key].replace(b"    def _mats():", b"    def _mats_renamed():")
    packed = io.BytesIO()
    with tarfile.open(fileobj=packed, mode="w:gz") as out:
        for name, body in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            out.addfile(info, io.BytesIO(body))
    with pytest.raises(
        gpu_build.GpuBuildRefused, match="device fix anchor found 0 times"
    ):
        gpu_build.derived_source(
            "torch-cpu-py311", packed.getvalue(), "v2.f02.lno.LNO1d"
        )
