"""Each C-03 parent variant has its own local tag, and an install checks that every image it recorded is still present
(val4090, 2026-10-29: a `--gpu` install built the C-03 parent three times under one mutable tag, so only the last build
kept it and, under the containerd store, the CPU parent the CPU Torch worker was built FROM was gone: every catalog
entry was refused). Stand-ins for Docker; nothing here builds an image."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
from test_miner_install import Sandbox

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "dev"
SOURCE = "sha256:" + "a" * 64
OTHER_SOURCE = "sha256:" + "b" * 64
PARENT_TAG = re.compile(
    r"^carbon-c03-worker:[0-9a-f]{16}$"
)  # image_fingerprint.PARENT_TAG
VARIANTS = ("cpu", "accelerator", "torch-gpu")


def tag(variant, source=SOURCE, role="validator"):
    done = subprocess.run(
        ["bash", str(SCRIPTS / "worker_parent_tag.sh"), variant, source],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "CARBON_INSTALL_ROLE": role},
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def ref(source=SOURCE, kind=None, **env):
    parent = "sha256:" + "9" * 64
    done = subprocess.run(
        ["bash", str(SCRIPTS / "worker_parent_ref.sh"), parent, source]
        + ([kind] if kind else []),
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "CARBON_INSTALL_ROLE": "validator", **env},
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_every_variant_has_its_own_tag_and_the_cpu_tag_is_the_original_one():
    tags = {variant: tag(variant) for variant in VARIANTS}
    assert len(set(tags.values())) == 3
    assert all(PARENT_TAG.fullmatch(value) for value in tags.values())
    # The install's identity and fingerprints name the CPU parent by this tag (installed.py).
    assert tags["cpu"] == "carbon-c03-worker:" + SOURCE[7:23]
    # Derived from the variant AND the source tree, and deterministic.
    assert tag("accelerator") == tags["accelerator"]
    assert tag("accelerator", OTHER_SOURCE) != tags["accelerator"]
    assert tag("torch-gpu", OTHER_SOURCE) != tag("accelerator", OTHER_SOURCE)


def test_the_tag_helper_refuses_an_unknown_variant_and_a_malformed_digest():
    for arguments in (("gpu", SOURCE), ("cpu", "sha256:abc"), ("cpu", "nope")):
        done = subprocess.run(
            ["bash", str(SCRIPTS / "worker_parent_tag.sh"), *arguments],
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": "/usr/bin:/bin"},
        )
        assert done.returncode == 2


def test_the_parent_reference_follows_the_variant_and_a_gpu_build_never_names_the_cpu_tag():
    cpu = ref()
    assert cpu == tag("cpu")
    named = {variant: ref(CARBON_WORKER_PARENT_VARIANT=variant) for variant in VARIANTS}
    assert named == {variant: tag(variant) for variant in VARIANTS}
    assert len(set(named.values())) == 3
    # The Torch analysis child and a registry release are unaffected.
    assert ref(kind="torch", CARBON_WORKER_PARENT_VARIANT="accelerator") == (
        "carbon-torch-worker:" + SOURCE[7:23]
    )
    released = ref(
        CARBON_WORKER_PARENT_REPOSITORY="registry.example/x/carbon-c03-worker",
        CARBON_WORKER_PARENT_VARIANT="accelerator",
    )
    assert released == "registry.example/x/carbon-c03-worker@sha256:" + "9" * 64


def test_each_builder_sets_its_own_variant_before_it_builds_or_names_the_parent():
    def text(name):
        return (SCRIPTS / name).read_text(encoding="utf-8")

    for name, variant in (
        ("accelerator_worker_image.sh", "accelerator"),
        ("torch_gpu_worker_image.sh", "torch-gpu"),
    ):
        body = text(name)
        export = f"export CARBON_WORKER_PARENT_VARIANT={variant}"
        assert export in body
        assert body.index(export) < body.index("worker_parent_manifest.sh")
        assert body.index(export) < body.index("worker_parent_ref.sh")
    # The CPU Torch worker keeps the default (cpu) tag; the C-03 builder names its tag through the helper.
    assert "CARBON_WORKER_PARENT_VARIANT=" not in text("torch_worker_image.sh")
    c03 = text("c03_worker_image.sh")
    assert "worker_parent_tag.sh" in c03 and "CARBON_WORKER_PARENT_VARIANT" in c03
    assert 'tag="carbon-c03-worker:${source_tree_digest' not in c03


def test_a_gpu_install_keeps_all_three_parents_when_each_build_tags_only_its_own_image():
    """The store as the three builds leave it: a tag points at one image, and a build tags only its own tag."""
    store = {}
    images = {variant: "sha256:" + str(i) * 64 for i, variant in enumerate(VARIANTS, 1)}
    for (
        variant
    ) in VARIANTS:  # cpu parent, accelerator parent, torch-gpu parent, in install order
        local = ref(CARBON_WORKER_PARENT_VARIANT=variant)
        store[local] = images[variant]  # `docker tag <parent image> <local tag>`
    assert set(store.values()) == set(images.values())  # none was replaced


# --- the installer checks that every image it recorded is still present --------------------


@pytest.fixture
def sandbox(tmp_path):
    return Sandbox(tmp_path)


def _run(sandbox, *arguments, **environment):
    """The sandbox install, with the REAL interpreter for the recorded-image check (the sandbox's venv python is a
    fake; the check reads manifests and asks Docker, so it needs one that runs the script).
    """
    return sandbox.run(
        *arguments, CARBON_IMAGE_CHECK_PYTHON=sys.executable, **environment
    )


WORKER, PARENTS = "sha256:" + "1" * 64, {
    "torch-parent-worker-image.json": "sha256:" + "2" * 64,
    "accelerator-parent-worker-image.json": "sha256:" + "3" * 64,
    "torch-gpu-parent-worker-image.json": "sha256:" + "4" * 64,
}


def _stage(sandbox, *, parents):
    """A Torch builder that records the worker and the parent manifests it left; Docker answers `image inspect`
    for every id except the one in CARBON_TEST_GONE."""
    writes = "".join(
        f'echo \'{{"image_id":"{image}","source_tree_digest":"{SOURCE}"}}\' '
        f'> "$(dirname "$1")/{name}"\n'
        for name, image in parents.items()
    )
    sandbox._executable(
        sandbox.work / "scripts/dev/torch_worker_image.sh",
        '#!/bin/sh\nmkdir -p "$(dirname "$1")"\n'
        f'echo \'{{"image_id":"{WORKER}","source_tree_digest":"{SOURCE}",'
        f'"base_image_digest":"{PARENTS["torch-parent-worker-image.json"]}"}}\' > "$1"\n'
        + writes
        + 'echo "torch worker" >> "$CARBON_TEST_LOG"\n',
    )
    sandbox._executable(
        sandbox.tools / "docker",
        "#!/bin/sh\n"
        'if [ "$*" = "info --format {{.DockerRootDir}}" ]; then echo "$CARBON_TEST_DOCKER_ROOT"; fi\n'
        'if [ "$1 $2" = "image inspect" ] && [ "$3" = "$CARBON_TEST_GONE" ]; then exit 1; fi\n'
        "exit 0\n",
    )
    sandbox.publish("fixture Torch builder with parent manifests")


def test_an_install_that_kept_every_recorded_image_records_them(sandbox):
    _stage(sandbox, parents=PARENTS)
    done = _run(sandbox, "--pytorch", "--no-start", CARBON_TEST_GONE="none")
    assert done.returncode == 0, done.stderr
    assert any("installed write" in line for line in sandbox.logged())


@pytest.mark.parametrize("name", sorted(PARENTS))
def test_an_install_stops_with_a_typed_code_when_a_recorded_parent_is_gone(
    sandbox, name
):
    _stage(sandbox, parents=PARENTS)
    done = _run(sandbox, "--pytorch", "--no-start", CARBON_TEST_GONE=PARENTS[name])
    assert done.returncode == 2
    assert "installed_image_missing" in done.stderr
    assert name in done.stderr and PARENTS[name] in done.stderr
    assert not any("installed write" in line for line in sandbox.logged())


def test_a_recorded_worker_image_that_is_gone_stops_the_install(sandbox):
    _stage(sandbox, parents={})
    done = _run(sandbox, "--pytorch", "--no-start", CARBON_TEST_GONE=WORKER)
    assert done.returncode == 2 and "installed_image_missing" in done.stderr


def test_a_parent_manifest_of_an_earlier_source_tree_is_not_checked(sandbox):
    """`--remove-old-images` removes an earlier install's images on purpose; their manifests stay."""
    _stage(sandbox, parents={})
    stale = sandbox.clone / ".carbon-artifacts"
    stale.mkdir(exist_ok=True)
    (stale / "torch-parent-worker-image.json").write_text(
        f'{{"image_id":"{PARENTS["torch-parent-worker-image.json"]}",'
        f'"source_tree_digest":"{OTHER_SOURCE}"}}\n'
    )
    done = _run(
        sandbox,
        "--pytorch",
        "--no-start",
        CARBON_TEST_GONE=PARENTS["torch-parent-worker-image.json"],
    )
    assert done.returncode == 0, done.stderr


# --- a child worker is reused or accepted only if its base is the current recorded parent ---------


def _manifests(sandbox, *, base):
    """The Torch builder leaves a worker built FROM `base` and the parent it recorded beside it."""
    parent = PARENTS["torch-parent-worker-image.json"]
    sandbox._executable(
        sandbox.work / "scripts/dev/torch_worker_image.sh",
        '#!/bin/sh\nmkdir -p "$(dirname "$1")"\n'
        f'echo \'{{"image_id":"{WORKER}","source_tree_digest":"{SOURCE}",'
        f'"base_image_digest":"{base}"}}\' > "$1"\n'
        f'echo \'{{"image_id":"{parent}","source_tree_digest":"{SOURCE}"}}\' '
        '> "$(dirname "$1")/torch-parent-worker-image.json"\n'
        'echo "torch worker" >> "$CARBON_TEST_LOG"\n',
    )
    sandbox._executable(
        sandbox.tools / "docker",
        "#!/bin/sh\n"
        'if [ "$*" = "info --format {{.DockerRootDir}}" ]; then echo "$CARBON_TEST_DOCKER_ROOT"; fi\n'
        'if [ "$1 $2" = "image inspect" ] && [ "$3" = "$CARBON_TEST_GONE" ]; then exit 1; fi\n'
        "exit 0\n",
    )
    sandbox.publish("fixture Torch builder with a worker base")


def test_a_worker_built_from_the_recorded_parent_passes(sandbox):
    _manifests(sandbox, base=PARENTS["torch-parent-worker-image.json"])
    done = _run(sandbox, "--pytorch", "--no-start", CARBON_TEST_GONE="none")
    assert done.returncode == 0, done.stderr


def test_a_worker_whose_base_is_not_the_recorded_parent_is_refused(sandbox):
    """val4090: the Torch CPU worker survived but its base (93fa1967) was a parent that no longer existed."""
    _manifests(sandbox, base="sha256:" + "7" * 64)
    done = _run(sandbox, "--pytorch", "--no-start", CARBON_TEST_GONE="none")
    assert done.returncode == 2
    assert "installed_worker_parent_stale" in done.stderr
    assert "torch-worker-image.json" in done.stderr
    assert not any("installed write" in line for line in sandbox.logged())


def test_a_worker_whose_base_is_the_recorded_parent_but_gone_is_refused(sandbox):
    parent = PARENTS["torch-parent-worker-image.json"]
    _manifests(sandbox, base=parent)
    done = _run(sandbox, "--pytorch", "--no-start", CARBON_TEST_GONE=parent)
    assert done.returncode == 2
    assert "installed_image_missing" in done.stderr or (
        "installed_worker_parent_stale" in done.stderr
    )


class _Docker:
    """`docker image inspect` over a set of image ids Docker still holds."""

    def __init__(self, held):
        self.held = set(held)

    def json(self, arguments):
        image = arguments[2]
        if image not in self.held:
            raise ValueError("No such image")
        return {"Id": image}


def _identity(base):
    return type("Identity", (), {"base_image_digest": base})()


@pytest.mark.parametrize(
    "name, base, held, parent_present, reason",
    [
        # reusable: the base is the recorded parent and Docker holds it
        (
            "torch-worker-image.json",
            "sha256:" + "2" * 64,
            {"sha256:" + "2" * 64},
            True,
            None,
        ),
        # the parent was rebuilt (a new id): the old worker's base is stale
        (
            "torch-worker-image.json",
            "sha256:" + "8" * 64,
            {"sha256:" + "8" * 64},
            True,
            "base_is_not_the_recorded_parent",
        ),
        # the recorded parent is gone from Docker
        (
            "accelerator-worker-image.json",
            "sha256:" + "2" * 64,
            set(),
            True,
            "parent_image_absent",
        ),
        # the C-03 worker itself, and a release install with no parent manifest, have no parent to compare
        ("c03-worker-image.json", "sha256:" + "5" * 64, set(), True, None),
        ("torch-gpu-worker-image.json", "sha256:" + "5" * 64, set(), False, None),
    ],
)
def test_installed_current_reuses_a_child_worker_only_when_its_parent_is_current(
    tmp_path, name, base, held, parent_present, reason
):
    from scripts.dev.miner_launchpad import installed

    manifest = tmp_path / name
    manifest.write_text("{}")
    parent_name = installed.CHILD_PARENT_MANIFEST.get(name)
    if parent_present and parent_name:
        (tmp_path / parent_name).write_text(
            f'{{"image_id":"{PARENTS["torch-parent-worker-image.json"]}"}}'
        )
    assert (
        installed.worker_parent_stale(manifest, _identity(base), _Docker(held))
        == reason
    )
