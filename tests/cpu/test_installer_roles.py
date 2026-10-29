"""One role per Docker daemon (val4090, 2026-10-29): a scratch miner install of the validator's source tree retagged the
validator's parent and worker images. Local worker tags now carry the install ROLE (a validator's names unchanged), and a
miner install refuses outright while a validator install lives on the host. Stand-ins for Docker; nothing is built."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest
from test_miner_install import Sandbox

from scripts.dev.miner_launchpad import installed

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SOURCE = "sha256:" + "a" * 64
OTHER = "sha256:" + "c" * 64
REPOSITORIES = ("carbon-c03-worker", "carbon-torch-worker", "carbon-torch-gpu-worker")
VARIANTS = ("cpu", "accelerator", "torch-gpu")
SHAPE = re.compile(r"^carbon-(c03|torch|torch-gpu)-worker:[0-9a-f]{16}$")


def tag(repository, variant, role, source=SOURCE):
    done = subprocess.run(
        ["bash", str(SCRIPTS / "dev" / "worker_tag.sh"), repository, variant, source],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "CARBON_INSTALL_ROLE": role},
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def hash16(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def test_a_validators_names_are_the_ones_it_has_always_used():
    assert (
        tag("carbon-c03-worker", "cpu", "validator")
        == "carbon-c03-worker:" + SOURCE[7:23]
    )
    assert (
        tag("carbon-torch-worker", "cpu", "validator")
        == "carbon-torch-worker:" + SOURCE[7:23]
    )
    assert tag("carbon-torch-gpu-worker", "torch-gpu", "validator") == (
        "carbon-torch-gpu-worker:" + SOURCE[7:23]
    )
    # The accelerator and torch-gpu C-03 parents (the parent-tag fix) keep their own names.
    assert tag("carbon-c03-worker", "accelerator", "validator") == (
        "carbon-c03-worker:" + hash16("accelerator\n" + SOURCE)
    )
    assert tag("carbon-c03-worker", "torch-gpu", "validator") == (
        "carbon-c03-worker:" + hash16("torch-gpu\n" + SOURCE)
    )


def test_a_miner_name_can_match_no_validator_name_of_any_tree():
    for source in (SOURCE, OTHER):
        validator = {
            (r, v): tag(r, v, "validator", source)
            for r in REPOSITORIES
            for v in VARIANTS
        }
        miner = {
            (r, v): tag(r, v, "miner", source) for r in REPOSITORIES for v in VARIANTS
        }
        for key, name in miner.items():
            assert SHAPE.fullmatch(name), name
            assert name.split(":")[0] == key[0]
        # No miner name equals any validator name, and the miner names do not collide among themselves.
        assert not set(miner.values()) & set(validator.values())
        assert len(set(miner.values())) == len(miner)
    # Deterministic, and a different tree is a different name.
    assert tag("carbon-c03-worker", "cpu", "miner") == tag(
        "carbon-c03-worker", "cpu", "miner"
    )
    assert tag("carbon-c03-worker", "cpu", "miner", OTHER) != tag(
        "carbon-c03-worker", "cpu", "miner"
    )


def test_the_default_role_is_the_miner_and_bad_arguments_are_refused():
    default = subprocess.run(
        [
            "bash",
            str(SCRIPTS / "dev" / "worker_tag.sh"),
            "carbon-c03-worker",
            "cpu",
            SOURCE,
        ],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert default.stdout.strip() == tag("carbon-c03-worker", "cpu", "miner")
    for arguments, role in (
        (("carbon-other", "cpu", SOURCE), "miner"),
        (("carbon-c03-worker", "gpu", SOURCE), "miner"),
        (("carbon-c03-worker", "cpu", "sha256:abc"), "miner"),
        (("carbon-c03-worker", "cpu", SOURCE), "operator"),
    ):
        done = subprocess.run(
            ["bash", str(SCRIPTS / "dev" / "worker_tag.sh"), *arguments],
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": "/usr/bin:/bin", "CARBON_INSTALL_ROLE": role},
        )
        assert done.returncode == 2, arguments


@pytest.mark.parametrize("role", ("miner", "validator"))
def test_the_install_record_names_the_same_tag_as_the_builder(role):
    assert installed.parent_tag(SOURCE, role=role) == tag(
        "carbon-c03-worker", "cpu", role
    )
    for repository, variant in (
        ("carbon-torch-worker", "cpu"),
        ("carbon-torch-gpu-worker", "torch-gpu"),
        ("carbon-c03-worker", "accelerator"),
    ):
        assert installed.parent_tag(
            SOURCE, role=role, repository=repository, variant=variant
        ) == tag(repository, variant, role)
    with pytest.raises(ValueError):
        installed.parent_tag(SOURCE, role="operator")


def test_the_builders_name_their_tags_through_the_role_helper():
    def text(name):
        return (SCRIPTS / "dev" / name).read_text(encoding="utf-8")

    assert 'worker_tag.sh" carbon-torch-worker cpu' in text("torch_worker_image.sh")
    assert 'worker_tag.sh" carbon-torch-gpu-worker torch-gpu' in text(
        "torch_gpu_worker_image.sh"
    )
    assert "carbon-torch-worker:${source_digest" not in text("torch_worker_image.sh")
    assert "carbon-torch-gpu-worker:${source_digest" not in text(
        "torch_gpu_worker_image.sh"
    )
    assert "worker_tag.sh" in text("worker_parent_tag.sh") and "worker_tag.sh" in text(
        "worker_parent_ref.sh"
    )
    # The validator installer runs the shared installer as the validator.
    validator = (SCRIPTS / "install_validator.sh").read_text(encoding="utf-8")
    assert (
        'CARBON_INSTALL_ROLE=validator "${repo_root}/scripts/install_miner.sh"'
        in validator
    )


# --- a miner install refuses on a host that holds a validator install ---------------------------


@pytest.fixture
def sandbox(tmp_path):
    return Sandbox(tmp_path)


def _marker_dir(tmp_path):
    return tmp_path / "host-role"


def test_a_miner_install_runs_where_no_validator_install_lives(sandbox, tmp_path):
    done = sandbox.run("--no-start", CARBON_HOST_ROLE_DIR=str(_marker_dir(tmp_path)))
    assert done.returncode == 0, done.stderr
    assert "installer_role_conflict" not in done.stderr


def test_a_miner_install_after_a_validator_install_is_refused_before_anything_runs(
    sandbox, tmp_path
):
    """The validator installer's marker (--mark-installed writes the same record an install does)."""
    state = tmp_path / "validator-state"
    state.mkdir()
    (state / "installed-images.json").write_text("{}")
    marker = _marker_dir(tmp_path)
    marked = subprocess.run(
        ["bash", str(SCRIPTS / "install_validator.sh"), "--mark-installed"],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "CARBON_STATE_DIR": str(state),
            "CARBON_HOST_ROLE_DIR": str(marker),
        },
    )
    assert marked.returncode == 0, marked.stderr
    record = json.loads((marker / "validator-host.json").read_text())
    assert record["role"] == "validator" and record["state_dir"] == str(state)
    assert ((marker / "validator-host.json").stat().st_mode & 0o077) == 0
    refused = sandbox.run("--no-start", CARBON_HOST_ROLE_DIR=str(marker))
    assert refused.returncode == 2
    assert "installer_role_conflict" in refused.stderr
    assert str(marker / "validator-host.json") in refused.stderr
    assert sandbox.logged() == []  # nothing was built, fetched or recorded
    # The validator's own install of the same tree is not refused.
    allowed = sandbox.run(
        "--no-start", CARBON_HOST_ROLE_DIR=str(marker), CARBON_INSTALL_ROLE="validator"
    )
    assert allowed.returncode == 0, allowed.stderr


def test_marking_an_install_that_does_not_exist_is_refused(tmp_path):
    done = subprocess.run(
        ["bash", str(SCRIPTS / "install_validator.sh"), "--mark-installed"],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "CARBON_STATE_DIR": str(tmp_path / "nothing"),
            "CARBON_HOST_ROLE_DIR": str(_marker_dir(tmp_path)),
        },
    )
    assert done.returncode == 2 and "installed-images.json is missing" in done.stderr
    assert not (_marker_dir(tmp_path) / "validator-host.json").exists()


def test_an_invalid_role_is_refused(sandbox, tmp_path):
    done = sandbox.run(
        "--no-start",
        CARBON_HOST_ROLE_DIR=str(_marker_dir(tmp_path)),
        CARBON_INSTALL_ROLE="operator",
    )
    assert done.returncode == 2 and "installer_role_invalid" in done.stderr
