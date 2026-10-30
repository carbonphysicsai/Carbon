"""The recal build driver, rehearsed with --fake: the real recipe and the real artifact writer, a stand-in build."""

import importlib.util
import json
from pathlib import Path

import pytest

from carbon.backbone_catalog import listing
from carbon.challenge_validator import calibration_grade as cg

REPOSITORY = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, REPOSITORY / "scripts" / "dev" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


driver = _load("recal_build_entry")
stats = _load("recal_stats")


def build(tmp_path, kind, entry, seed, repeat, capsys):
    rc = driver.main(
        [
            "build",
            "--kind",
            kind,
            "--entry",
            entry,
            "--seed",
            str(seed),
            "--repeat",
            str(repeat),
            "--out",
            str(tmp_path / "out"),
            "--work-dir",
            str(tmp_path / "work"),
            "--fake",
        ]
    )
    return rc, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def entry():
    return min(
        item["catalog_id"] for item in listing.entries("f08-ribbed-bracket", "1.7")
    )


def test_a_fake_build_writes_an_artifact_the_grade_tool_loads(tmp_path, entry, capsys):
    rc, line = build(tmp_path, "f08", entry, 0, 0, capsys)
    assert rc == 0 and line["status"] == "BUILT" and line["device"] == "gpu"
    artifact = cg.load_artifact(line["artifact"], challenge_id="f08-ribbed-bracket")
    assert artifact.manifest["seed"] == 0
    assert artifact.manifest["version"] == "1.7"


def test_repeats_at_seed_0_are_bit_identical_and_other_seeds_differ(
    tmp_path, entry, capsys
):
    states = {}
    for seed, repeat in ((0, 0), (0, 1), (3, 0)):
        _rc, line = build(tmp_path, "f08", entry, seed, repeat, capsys)
        states[(seed, repeat)] = line["state_sha256"]
    assert states[(0, 0)] == states[(0, 1)] != states[(3, 0)]


def _grade_tree(root, name, total):
    for seed in range(10):
        for repeat in range(10):
            if seed != 0 and repeat != 0:
                continue
            run = root / name / f"s{seed}r{repeat}"
            run.mkdir(parents=True, exist_ok=True)
            (run / "manifest.json").write_text(
                json.dumps({"state_sha256": "sha256:" + "ab" * 32}), encoding="utf-8"
            )
            (root / name / f"s{seed}r{repeat}.grade.json").write_text(
                json.dumps({"total": total(seed, repeat)}), encoding="utf-8"
            )


def _meta(panel, control):
    return {
        "challenges": {
            "Ribbed Bracket": {
                "pack_digest": "1" * 64,
                "class_record_digest": "2" * 64,
                "control_basis_bit_identical": "10 bit-identical rebuilds",
                "control_basis_within_noise": "smallest sigma",
                "panel": panel,
                "control": control,
                "entries": {
                    name: {"reference_fingerprint": "3" * 64, "within_noise": True}
                    for name in panel
                },
            }
        }
    }


def test_assemble_builds_the_recal_stats_input(tmp_path):
    _grade_tree(
        tmp_path, "m1", lambda seed, repeat: 0.5 + 0.001 * seed + 0.0001 * repeat
    )
    document = driver.assemble(tmp_path, _meta(["m1"], "m1"))
    own = document["challenges"]["Ribbed Bracket"]
    member = own["members"]["m1"]
    assert len(member["seed0_totals"]) == 10 and len(member["state_digests"]) == 10
    assert member["state_digests"][0] == "ab" * 32
    assert len(own["control_seed_totals"]["m1"]) == 10
    result = stats.measure(document)  # the existing tool accepts it
    assert result["schema"] == stats.SCHEMA_OUT


def test_a_missing_run_refuses(tmp_path):
    with pytest.raises(driver.MetaError):
        driver.assemble(tmp_path, _meta(["m1"], None))


def _args(tmp_path):
    from types import SimpleNamespace

    return SimpleNamespace(
        out_dir=str(tmp_path / "work"),
        parent_identity=None,
        cache_root=None,
        gpu_image=None,
    )


def test_the_build_refuses_a_bundle_that_is_not_the_official_one(tmp_path, entry):
    def official_other(recipe, runtimes):
        return {**recipe, "extra": "different bundle"}, "torch-cu130-py311"

    with pytest.raises(driver.OfficialMismatch, match="differs_from_official"):
        driver.build_one(
            "f08",
            entry,
            0,
            0,
            _args(tmp_path),
            factory=driver.fake_factory,
            reconstruct=driver.fake_reconstruct,
            check_binding=lambda _r, b: b,
            expand_official=official_other,
        )


def test_the_build_proceeds_when_the_bundle_equals_expand_officials(tmp_path, entry):
    calls = []

    def official_same(recipe, runtimes):
        calls.append(runtimes)
        return recipe, "torch-cu130-py311"

    record = driver.build_one(
        "f08",
        entry,
        0,
        0,
        _args(tmp_path),
        factory=driver.fake_factory,
        reconstruct=driver.fake_reconstruct,
        check_binding=lambda _r, b: b,
        expand_official=official_same,
    )
    assert "build" in record and calls == [()]


def test_a_catalog_entry_with_no_official_gpu_receipt_refuses_before_any_build(
    tmp_path, entry
):
    from carbon.backbone_catalog.served import CatalogRefused

    def pending(recipe, runtimes):
        raise CatalogRefused("catalog_gpu_receipt_pending", "no official receipt")

    with pytest.raises(CatalogRefused):
        driver.build_one(
            "f08",
            entry,
            0,
            0,
            _args(tmp_path),
            factory=driver.fake_factory,
            reconstruct=lambda *a, **k: pytest.fail("built before the official check"),
            check_binding=lambda _r, b: b,
            expand_official=pending,
        )


def test_a_null_total_is_refused_typed_never_read_as_zero(tmp_path):
    """A --fake grade has total null (the stand-in fails the physics-laws gate): assemble refuses it, and
    recal_stats refuses a null total in its own input."""
    _grade_tree(tmp_path, "m1", lambda seed, repeat: None)
    with pytest.raises(driver.MetaError, match="no numeric total"):
        driver.assemble(tmp_path, _meta(["m1"], "m1"))
    good = tmp_path / "good"
    _grade_tree(good, "m1", lambda seed, repeat: 0.5)
    document = driver.assemble(good, _meta(["m1"], "m1"))
    own = document["challenges"]["Ribbed Bracket"]
    own["members"]["m1"]["seed0_totals"][3] = None
    with pytest.raises(stats.StatsError, match="finite numbers"):
        stats.measure(document)


def test_the_receiver_receipt_store_is_installed_for_the_official_route(
    tmp_path, monkeypatch
):
    from carbon.backbone_catalog import gpu_receipt, receipt_store

    monkeypatch.setattr(gpu_receipt, "OFFICIAL_STORE", None)
    store_dir = tmp_path.resolve() / "gpu-receipts"
    driver.install_receipts(str(store_dir))
    store = gpu_receipt.OFFICIAL_STORE
    assert type(store) is receipt_store.ReceiptStore and store.root == store_dir


@pytest.mark.parametrize("bad", ["relative/path", ""])
def test_a_receipt_store_path_must_be_exact(bad):
    with pytest.raises(ValueError, match="exact official gpu receipts path"):
        driver.install_receipts(bad)


def test_the_build_command_installs_the_store_only_when_asked(
    tmp_path, monkeypatch, capsys
):
    from carbon.backbone_catalog import gpu_receipt

    monkeypatch.setattr(gpu_receipt, "OFFICIAL_STORE", None)
    seen = []
    monkeypatch.setattr(driver, "install_receipts", seen.append)
    rc, _ = build(
        tmp_path,
        "f08",
        min(
            item["catalog_id"] for item in listing.entries("f08-ribbed-bracket", "1.7")
        ),
        0,
        0,
        capsys,
    )
    assert rc == 0 and seen == []
    driver.main(
        [
            "build",
            "--kind",
            "f08",
            "--entry",
            min(
                item["catalog_id"]
                for item in listing.entries("f08-ribbed-bracket", "1.7")
            ),
            "--seed",
            "0",
            "--out",
            str(tmp_path / "o2"),
            "--work-dir",
            str(tmp_path / "w2"),
            "--fake",
            "--gpu-receipts",
            str(tmp_path),
        ]
    )
    assert seen == [str(tmp_path)]
