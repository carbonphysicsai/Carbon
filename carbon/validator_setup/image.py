"""Prepare an isolated image context; explicit build never pushes or deploys."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .bundle import SetupRefused, encoded, git, materialize, sha

RECIPE = ".devcontainer/Dockerfile.validator-service"
LABEL = "org.opencontainers.image.carbon.validator."


def prepare(repository, revision, context):
    context = Path(context)
    if not context.is_absolute() or context.exists() or context.is_symlink():
        raise SetupRefused("NEW_ABSOLUTE_IMAGE_CONTEXT_REQUIRED")
    recipe = git(repository, "show", revision + ":" + RECIPE)
    context.mkdir()
    bundle = materialize(repository, revision, context / "runtime")
    (context / "Dockerfile").write_bytes(recipe)
    (context / ".dockerignore").write_text(
        "*\n!Dockerfile\n!runtime\n!runtime/**\n", encoding="utf-8", newline="\n"
    )
    receipt = {
        "schema": "carbon.validator-image-context.v1",
        "bundle_digest": bundle.digest,
        "source_revision": revision,
        "source_git_tree": bundle.manifest["source_git_tree"],
        "lock_digest": bundle.manifest["lock_digest"],
        "recipe_digest": sha(recipe),
        "sdk": "11.1.0",
        "image_built": False,
        "local_image_id": None,
        "published_manifest_digest": None,
        "host_acceptance": "NOT_RUN",
    }
    (context / "image-context.json").write_bytes(encoded(receipt))
    return receipt


def build(context, *, runner=subprocess.run):
    """Explicit operator/CI image build; caller retains publication authority."""
    from .bundle import verify

    context = Path(context)
    receipt = json.loads((context / "image-context.json").read_bytes())
    bundle = verify(context / "runtime", receipt["bundle_digest"])
    if sha((context / "Dockerfile").read_bytes()) != receipt["recipe_digest"]:
        raise SetupRefused("IMAGE_RECIPE_DRIFT")
    iid = context / "local-image-id"
    if iid.exists() or iid.is_symlink():
        raise SetupRefused("NEW_IMAGE_BUILD_RECEIPT_REQUIRED")
    argv = ["docker", "build", "--platform", "linux/amd64", "--iidfile", str(iid)]
    for key, value in {
        "BUNDLE_DIGEST": bundle.digest,
        "SOURCE_REVISION": bundle.manifest["source_revision"],
        "SOURCE_GIT_TREE": bundle.manifest["source_git_tree"],
        "LOCK_DIGEST": bundle.manifest["lock_digest"],
    }.items():
        argv += ["--build-arg", key + "=" + value]
    result = runner([*argv, str(context)], capture_output=True, check=False)
    if result.returncode:
        raise SetupRefused("VALIDATOR_IMAGE_BUILD_FAILED")
    image_id = iid.read_text(encoding="utf-8").strip()
    if re.fullmatch("sha256:[0-9a-f]{64}", image_id) is None:
        raise SetupRefused("EXACT_LOCAL_IMAGE_ID_REQUIRED")
    inspected = runner(
        ["docker", "image", "inspect", image_id], capture_output=True, check=False
    )
    if inspected.returncode:
        raise SetupRefused("VALIDATOR_IMAGE_INSPECTION_FAILED")
    try:
        image = json.loads(inspected.stdout)[0]
        labels = image["Config"]["Labels"]
        wanted = {
            "source-revision": receipt["source_revision"],
            "source-git-tree": receipt["source_git_tree"],
            "bundle": receipt["bundle_digest"],
            "lock": receipt["lock_digest"],
            "sdk": "11.1.0",
            "scope": "DEVELOPMENT_UNQUALIFIED_OPERATOR",
        }
        if (
            image["Id"] != image_id
            or (image["Os"], image["Architecture"]) != ("linux", "amd64")
            or any(labels.get(LABEL + k) != v for k, v in wanted.items())
        ):
            raise ValueError
    except (KeyError, ValueError, TypeError, IndexError):
        raise SetupRefused("VALIDATOR_IMAGE_IDENTITY_DRIFT") from None
    return {
        **receipt,
        "image_built": True,
        "local_image_id": image_id,
        "published_manifest_digest": None,
        "host_acceptance": "NOT_RUN",
    }


def extract(
    image_reference,
    destination,
    expected_bundle_digest,
    expected_revision,
    *,
    runner=subprocess.run,
):
    """Fresh-machine public payload extraction; no process, service or state start."""
    import uuid

    from .bundle import verify

    if (
        type(image_reference) is not str
        or re.fullmatch(r"[A-Za-z0-9._:/-]+@sha256:[0-9a-f]{64}", image_reference)
        is None
    ):
        raise SetupRefused("DIGEST_PINNED_PUBLISHED_IMAGE_REQUIRED")
    destination = Path(destination)
    if (
        not destination.is_absolute()
        or destination.exists()
        or destination.is_symlink()
        or any(p.is_symlink() for p in destination.parents)
    ):
        raise SetupRefused("NEW_ABSOLUTE_RELEASE_DIRECTORY_REQUIRED")
    inspected = runner(
        ["docker", "image", "inspect", image_reference],
        capture_output=True,
        check=False,
    )
    if inspected.returncode:
        raise SetupRefused("PULL_EXACT_IMAGE_BEFORE_EXTRACTION")
    try:
        image = json.loads(inspected.stdout)[0]
        labels = image["Config"]["Labels"]
        if (
            image_reference not in image.get("RepoDigests", [])
            or (image["Os"], image["Architecture"]) != ("linux", "amd64")
            or labels.get(LABEL + "bundle") != expected_bundle_digest
            or labels.get(LABEL + "source-revision") != expected_revision
            or labels.get(LABEL + "sdk") != "11.1.0"
            or labels.get(LABEL + "scope") != "DEVELOPMENT_UNQUALIFIED_OPERATOR"
        ):
            raise ValueError
    except (KeyError, IndexError, TypeError, ValueError):
        raise SetupRefused("PUBLISHED_OPERATOR_IMAGE_BINDING_REFUSED") from None
    name = "carbon-validator-extract-" + uuid.uuid4().hex
    created = runner(
        ["docker", "create", "--name", name, image_reference],
        capture_output=True,
        check=False,
    )
    if created.returncode:
        raise SetupRefused("IMAGE_PAYLOAD_EXTRACTION_UNAVAILABLE")
    try:
        destination.mkdir()
        copied = runner(
            ["docker", "cp", name + ":/opt/carbon/.", str(destination)],
            capture_output=True,
            check=False,
        )
        if copied.returncode:
            raise SetupRefused("IMAGE_PAYLOAD_EXTRACTION_UNAVAILABLE")
        bundle = verify(destination, expected_bundle_digest)
        if bundle.manifest["source_revision"] != expected_revision:
            raise SetupRefused("IMAGE_SOURCE_REVISION_DRIFT")
        return bundle
    finally:
        cleaned = runner(["docker", "rm", name], capture_output=True, check=False)
        if cleaned.returncode:
            raise SetupRefused("OWN_EXTRACTION_CONTAINER_CLEANUP_REQUIRED")


def check_host_mirror(image_reference, bundle, *, runner=subprocess.run):
    """Use the operator image to verify the Docker host's public source bind.

    This trusted read-only probe gets no Docker socket, state, keys or network.
    It is not a miner workload or containment acceptance.
    """
    from .bundle import verify

    bundle = verify(bundle.root, bundle.digest)
    if (
        type(image_reference) is not str
        or re.fullmatch(r"[A-Za-z0-9._:/-]+@sha256:[0-9a-f]{64}", image_reference)
        is None
    ):
        raise SetupRefused("DIGEST_PINNED_PUBLISHED_IMAGE_REQUIRED")
    argv = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--mount",
        "type=bind,source=" + str(bundle.root) + ",target=/mirror,readonly",
        image_reference,
        "verify",
        "--bundle",
        "/mirror",
        "--digest",
        bundle.digest,
    ]
    result = runner(argv, capture_output=True, check=False)
    if result.returncode:
        raise SetupRefused("DOCKER_HOST_SOURCE_MIRROR_REFUSED")
    try:
        report = json.loads(result.stdout)
        if (
            report["status"] != "BYTES_VERIFIED"
            or report["digest"] != bundle.digest
            or report["source_revision"] != bundle.manifest["source_revision"]
            or report["qualification"] != "NOT_GRANTED"
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise SetupRefused("DOCKER_HOST_SOURCE_MIRROR_REFUSED") from None
    return {
        "status": "DOCKER_HOST_PUBLIC_SOURCE_BYTES_VERIFIED",
        "source_revision": bundle.manifest["source_revision"],
        "bundle_digest": bundle.digest,
        "qualification": "NOT_GRANTED",
    }
