"""Every committed GPU twin is exactly what the registered derivation makes of its CPU entry.

`pipeline.add_twin` writes a twin from the entry's CPU build with `gpu_build` and nothing else. This test redoes that
derivation from the CPU files, independently of the files already on disk, and compares byte for byte: the twin's
source, manifest, licence and requirements, the set of files in its directory, and the ref the catalog manifest lists.
With 231+ twins and their binaries in the tree, it is the guard against a hand-edited twin: any change to a twin's
bytes, or a twin the derivation would not make, fails here and names the entry.
"""

import json

from carbon.backbone_catalog import gpu_build, pipeline


def _twinned():
    return [e for e in pipeline.load()["entries"] if e.get("bundle_refs")]


def test_every_twin_is_reproduced_byte_for_byte_from_its_cpu_entry():
    twinned = _twinned()
    assert twinned
    checked = 0
    for item in twinned:
        catalog_id = item["catalog_id"]
        cpu_files = pipeline.bundle_files(item)
        cpu_manifest = json.loads(cpu_files["bundle.json"])
        runtime = gpu_build.TWINS[cpu_manifest["runtime_profile_id"]]
        assert set(item["bundle_refs"]) == {runtime}, catalog_id
        source = gpu_build.derived_source(
            cpu_manifest["runtime_profile_id"], cpu_files["source.tar.gz"], catalog_id
        )
        expected = gpu_build.gpu_manifest(
            cpu_manifest, source, gpu_build.base_lock(runtime)
        )
        root = pipeline.BUNDLES / catalog_id / runtime
        committed = {p.name: p.read_bytes() for p in root.iterdir()}
        assert set(committed) == {
            "source.tar.gz",
            "bundle.json",
            "LICENSE",
            "requirements.txt",
        }, catalog_id
        assert committed["source.tar.gz"] == source, catalog_id
        assert (
            committed["bundle.json"]
            == (json.dumps(expected, sort_keys=True, indent=1) + "\n").encode()
        ), catalog_id
        assert committed["LICENSE"] == cpu_files["LICENSE"], catalog_id
        assert (
            committed["requirements.txt"] == cpu_files["requirements.txt"]
        ), catalog_id
        assert item["bundle_refs"][runtime] == gpu_build.bundle_ref(
            expected
        ), catalog_id
        checked += 1
    assert checked == len(twinned)


def test_no_twin_directory_exists_without_a_listed_ref():
    listed = {
        (e["catalog_id"], runtime) for e in _twinned() for runtime in e["bundle_refs"]
    }
    on_disk = {
        (entry.name, twin.name)
        for entry in pipeline.BUNDLES.iterdir()
        if entry.is_dir()
        for twin in entry.iterdir()
        if twin.is_dir()
    }
    assert on_disk == listed
