"""Image context/identity controls with scripted Docker, not a built host image."""

import json
import shutil
import subprocess

import pytest
from test_validator_setup_bundle import command, source

from carbon.validator_setup import image
from carbon.validator_setup.bundle import SetupRefused


def context(tmp_path):
    repo, _ = source(tmp_path)
    recipe = repo / image.RECIPE
    recipe.parent.mkdir(parents=True)
    recipe.write_text("# public fixture recipe", encoding="utf-8")
    command(repo, "add", ".")
    command(repo, "commit", "-qm", "fixture recipe")
    revision = command(repo, "rev-parse", "HEAD")
    root = tmp_path / "context"
    receipt = image.prepare(repo, revision, root)
    return root, receipt


def inspected(receipt, image_id, *, reference=None):
    labels = {
        image.LABEL + key: value
        for key, value in {
            "source-revision": receipt["source_revision"],
            "source-git-tree": receipt["source_git_tree"],
            "bundle": receipt["bundle_digest"],
            "lock": receipt["lock_digest"],
            "sdk": "11.1.0",
            "scope": "DEVELOPMENT_UNQUALIFIED_OPERATOR",
        }.items()
    }
    return {
        "Id": image_id,
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {"Labels": labels},
        "RepoDigests": [] if reference is None else [reference],
    }


@pytest.mark.parametrize("drift", [False, True])
def test_build_inspects_actual_identity_and_never_pushes_or_runs(tmp_path, drift):
    root, receipt = context(tmp_path)
    image_id = "sha256:" + "a" * 64
    calls = []

    def docker(argv, **kwargs):
        calls.append(argv)
        if argv[1] == "build":
            (root / "local-image-id").write_text(image_id, encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0)
        record = inspected(receipt, image_id)
        if drift:
            record["Config"]["Labels"][image.LABEL + "bundle"] = "sha256:" + "b" * 64
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps([record]).encode()
        )

    if drift:
        with pytest.raises(SetupRefused, match="VALIDATOR_IMAGE_IDENTITY_DRIFT"):
            image.build(root, runner=docker)
    else:
        result = image.build(root, runner=docker)
        assert result["local_image_id"] == image_id
        assert result["published_manifest_digest"] is None
        assert result["host_acceptance"] == "NOT_RUN"
    assert len(calls) == 2
    assert [call[1] for call in calls] == ["build", "image"]


def test_changed_recipe_refuses_before_docker(tmp_path):
    root, _ = context(tmp_path)
    (root / "Dockerfile").write_bytes(b"changed")
    with pytest.raises(SetupRefused, match="IMAGE_RECIPE_DRIFT"):
        image.build(
            root, runner=lambda *_args, **_kwargs: pytest.fail("must not execute")
        )


def test_digest_pulled_image_extracts_bound_public_code_without_start_or_state(
    tmp_path,
):
    root, receipt = context(tmp_path)
    reference = "ghcr.io/public-fixture/validator@sha256:" + "b" * 64
    destination = tmp_path / "fresh-release"
    calls = []

    def docker(argv, **kwargs):
        calls.append(argv)
        if argv[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps(
                    [inspected(receipt, "sha256:" + "a" * 64, reference=reference)]
                ).encode(),
            )
        if argv[1] == "cp":
            shutil.copytree(root / "runtime", destination, dirs_exist_ok=True)
        return subprocess.CompletedProcess(argv, 0)

    extracted = image.extract(
        reference,
        destination,
        receipt["bundle_digest"],
        receipt["source_revision"],
        runner=docker,
    )
    assert extracted.digest == receipt["bundle_digest"]
    assert [call[1] for call in calls] == ["image", "create", "cp", "rm"]
    created_name = calls[1][calls[1].index("--name") + 1]
    assert calls[-1] == ["docker", "rm", created_name]
    assert not (destination / "state").exists()
    assert not (destination / "Business").exists()


def test_mutable_tag_cannot_touch_docker_or_destination(tmp_path):
    with pytest.raises(SetupRefused, match="DIGEST_PINNED_PUBLISHED_IMAGE_REQUIRED"):
        image.extract(
            "fixture:latest",
            tmp_path / "release",
            "sha256:" + "a" * 64,
            "0" * 40,
            runner=lambda *_a, **_k: pytest.fail("must not execute"),
        )
    assert not (tmp_path / "release").exists()


@pytest.mark.parametrize("bad", [False, True])
def test_docker_host_source_mirror_is_verified_without_private_mounts_or_network(
    tmp_path, bad
):
    from carbon.validator_setup.bundle import verify

    root, receipt = context(tmp_path)
    bundle = verify(root / "runtime", receipt["bundle_digest"])
    calls = []

    def docker(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(
                {
                    "status": "BYTES_VERIFIED",
                    "digest": "wrong" if bad else bundle.digest,
                    "source_revision": bundle.manifest["source_revision"],
                    "qualification": "NOT_GRANTED",
                }
            ).encode(),
        )

    image_ref = "ghcr.io/public-fixture/validator@sha256:" + "b" * 64
    if bad:
        with pytest.raises(SetupRefused, match="DOCKER_HOST_SOURCE_MIRROR_REFUSED"):
            image.check_host_mirror(image_ref, bundle, runner=docker)
    else:
        assert (
            image.check_host_mirror(image_ref, bundle, runner=docker)["qualification"]
            == "NOT_GRANTED"
        )
    assert len(calls) == 1
    argv = calls[0]
    assert (
        argv[:3] == ["docker", "run", "--rm"]
        and argv[argv.index("--network") + 1] == "none"
    )
    assert (
        argv.count("--mount") == 1
        and "target=/mirror,readonly" in argv[argv.index("--mount") + 1]
    )
    assert not any("docker.sock" in a or "state" in a or "wallet" in a for a in argv)
