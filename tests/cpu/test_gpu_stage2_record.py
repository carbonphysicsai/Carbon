"""The stage-2 host-class record: the one loader of the pinned GPU worker images and registered host classes."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from carbon.backbone_catalog import gpu_receipt

REPO = Path(__file__).resolve().parents[2]
CLASSES = REPO / "scripts" / "validator_host_classes"
STEM = "EPYC7402P-VM-01"
EPYC = "VALIDATOR-HOST-CLASS-EPYC7402P-VM-01"
TORCH, JAX = "torch-cu130-py311", "jax-cuda13-py311"
IMAGE = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=ENV)


def stage2(images=None, **over):
    stage1 = json.loads((CLASSES / (STEM + ".json")).read_text(encoding="utf-8"))
    runtimes = {
        runtime: {
            "image_ids": [IMAGE] if images is None else images,
            "determinism_flags_digest": gpu_receipt.required_determinism_digest(runtime),
        }
        for runtime in (TORCH, JAX)
    }
    record = {
        "schema": gpu_receipt.STAGE2_SCHEMA,
        "host_class_id": EPYC,
        "stage1_record_digest": gpu_receipt.record_digest(stage1),
        "runtimes": runtimes,
    }
    record.update(over)
    return record


@pytest.fixture
def tree(tmp_path):
    """A git clone-like work tree holding the stage-1 file; ``commit`` writes and commits a stage-2 record."""
    root = tmp_path / "repo"
    directory = root / "scripts" / "validator_host_classes"
    directory.mkdir(parents=True)
    shutil.copy(CLASSES / (STEM + ".json"), directory)
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "stage 1")

    def commit(record, name=STEM + ".stage2.json"):
        (directory / name).write_text(json.dumps(record), encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-qm", "stage 2")
        return directory

    commit.root, commit.directory = root, directory
    return commit


def refused(directory):
    with pytest.raises(gpu_receipt.Stage2Refused) as caught:
        gpu_receipt.stage2_registries(directory)
    return caught.value.code


def test_no_record_means_both_registries_are_empty_and_everything_is_refused():
    assert not list(CLASSES.glob("*.stage2.json")), "the shipped tree registers nothing until the images are read in"
    registries = gpu_receipt.stage2_registries()
    assert registries.images == {} and registries.host_classes == frozenset()
    receipt = {"kind": "repeat", "image_digest": IMAGE, "host_class": EPYC}
    assert "pinned" in gpu_receipt.official_grade_problem(receipt, TORCH)


def test_a_committed_record_registers_its_class_and_images(tree):
    registries = gpu_receipt.stage2_registries(tree(stage2()))
    assert registries.host_classes == {EPYC}
    assert registries.images[TORCH] == {IMAGE} and registries.images[JAX] == {IMAGE}


def test_an_empty_record_is_refused(tree):
    assert refused(tree(stage2(runtimes={}))) == "V_STAGE2_EMPTY"


def test_a_runtime_with_no_image_id_is_refused(tree):
    assert refused(tree(stage2(images=[]))) == "V_STAGE2_EMPTY"


def test_a_short_or_typed_image_id_is_refused(tree):
    assert refused(tree(stage2(images=["sha256:abc"]))) == "V_STAGE2_EMPTY"


def test_a_tampered_record_is_refused(tree):
    directory = tree(stage2())
    assert gpu_receipt.stage2_registries(directory).host_classes
    path = directory / (STEM + ".stage2.json")
    edited = json.loads(path.read_text(encoding="utf-8"))
    edited["runtimes"][TORCH]["image_ids"] = [OTHER]  # an image pinned in place, not committed
    path.write_text(json.dumps(edited), encoding="utf-8")
    assert refused(directory) == "V_STAGE2_MODIFIED"


def test_a_staged_but_uncommitted_record_is_refused(tree):
    directory = tree(stage2())
    path = directory / (STEM + ".stage2.json")
    path.write_text(json.dumps(stage2(images=[OTHER])), encoding="utf-8")
    git(tree.root, "add", ".")
    assert refused(directory) == "V_STAGE2_MODIFIED"


def test_an_untracked_record_is_refused(tree):
    directory = tree.directory
    (directory / (STEM + ".stage2.json")).write_text(json.dumps(stage2()), encoding="utf-8")
    assert refused(directory) == "V_STAGE2_MODIFIED"


def test_a_tree_that_is_not_a_work_tree_is_refused(tree):
    directory = tree(stage2())
    shutil.rmtree(tree.root / ".git")
    assert refused(directory) == "V_STAGE2_UNVERIFIABLE"


def test_a_changed_stage1_file_is_refused(tree):
    directory = tree(stage2())
    stage1 = directory / (STEM + ".json")
    edited = json.loads(stage1.read_text(encoding="utf-8"))
    edited["mem_total_min_gib"] = 1
    stage1.write_text(json.dumps(edited), encoding="utf-8")
    assert refused(directory) == "V_STAGE2_MODIFIED"


def test_a_stage1_digest_that_does_not_match_is_refused(tree):
    assert refused(tree(stage2(stage1_record_digest="sha256:" + "0" * 64))) == "V_STAGE2_MISMATCH"


def test_a_stale_determinism_digest_is_refused(tree):
    record = stage2()
    record["runtimes"][JAX]["determinism_flags_digest"] = "sha256:" + "0" * 64
    assert refused(tree(record)) == "V_STAGE2_MISMATCH"


def test_a_record_naming_another_class_than_its_stage1_file_is_refused(tree):
    assert refused(tree(stage2(host_class_id="VALIDATOR-HOST-CLASS-OTHER"))) == "V_STAGE2_MISMATCH"


def test_an_image_id_not_in_the_record_is_refused_officially(tree, monkeypatch):
    directory = tree(stage2())
    monkeypatch.setattr(gpu_receipt, "stage2_directory", lambda: directory)
    good = {"kind": "repeat", "image_digest": IMAGE, "host_class": EPYC}
    good["determinism"] = gpu_receipt.required_determinism(TORCH)
    assert gpu_receipt.official_grade_problem(good, TORCH) is None
    assert "pinned" in gpu_receipt.official_grade_problem({**good, "image_digest": OTHER}, TORCH)
    # a class the record does not name
    assert "host class" in gpu_receipt.official_grade_problem({**good, "host_class": "7950X-OTHER"}, TORCH)


def test_a_refused_record_makes_every_receipt_unofficial(tree, monkeypatch):
    directory = tree(stage2())
    (directory / (STEM + ".stage2.json")).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gpu_receipt, "stage2_directory", lambda: directory)
    receipt = {"kind": "repeat", "image_digest": IMAGE, "host_class": EPYC}
    assert "V_STAGE2_MODIFIED" in gpu_receipt.official_grade_problem(receipt, TORCH)


def test_the_7950x_class_is_unaffected(tree):
    """The 7950X class registers no GPU stage 2; a record for the EPYC class never names it, and the stage-1 files stay."""
    registries = gpu_receipt.stage2_registries(tree(stage2()))
    assert not any("7950" in name for name in registries.host_classes)
    assert sorted(p.name for p in CLASSES.glob("*.json")) == [STEM + ".json"]
