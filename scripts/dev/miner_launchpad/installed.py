"""Where the installer put this machine's pinned images (C-MLP-04).

`scripts/install_miner.sh` builds the worker and analysis images, and with
`--gpu` the GPU worker, on the miner's own machine. It records their manifest
paths here, owner-only, in the Control Center's state directory, so setup can
fill them in rather than asking a miner to find them. A record names local
paths only; nothing in it is secret, and setup still verifies every image.

With `--release TAG` the installer pulls Carbon's released images by digest
instead of building them (OWNER-WORKER-IMAGES-V2-01), and also records the
GPU worker's release record, so remote setup can name the released reference
a container is started from (`released_gpu`).
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

SCHEMA = "carbon.launchpad.installed-images.v1"
FILE = "installed-images.json"
FIELDS = ("image_manifest", "analysis_image_manifest", "gpu_image_manifest")
#: The released GPU worker's record (`carbon.worker-image-release.v1`), kept
#: beside the image manifests but never read as one: `read` returns FIELDS only.
GPU_RELEASE_RECORD = "gpu_release_record"
#: The release kind of the GPU worker remote setup uses.
GPU_RELEASE_KIND = "accelerator"
DEVELOPMENT_CANDIDATE_FILE = "development-candidate.json"
DEVELOPMENT_CANDIDATE_SCHEMA = "carbon.launchpad.development-candidate.v1"
#: Where `scripts/dev/accelerator_worker_image.sh` writes the GPU worker's
#: manifest by default. A miner whose controller has no GPU builds it with
#: that script for their remote setup (`install_miner.sh --gpu` checks for a
#: local NVIDIA driver first), and setup still finds it.
GPU_DEFAULT = ".carbon-artifacts/accelerator-worker-image.json"
#: The one command that builds each image, named when setup finds none: the
#: script in the checkout and its arguments.
BUILD = {
    "image_manifest": ("scripts/install_miner.sh", "--no-start"),
    "analysis_image_manifest": ("scripts/install_miner.sh", "--no-start"),
    "gpu_image_manifest": ("scripts/dev/accelerator_worker_image.sh",),
}


def write(
    state_dir,
    *,
    image_manifest,
    analysis_image_manifest,
    gpu_image_manifest=None,
    gpu_release_record=None,
):
    from scripts.dev.miner_launchpad.environment_setup import write_private

    record = {"schema": SCHEMA}
    for field, value in zip(
        (*FIELDS, GPU_RELEASE_RECORD),
        (
            image_manifest,
            analysis_image_manifest,
            gpu_image_manifest,
            gpu_release_record,
        ),
    ):
        if value is None:
            continue
        path = Path(value).resolve()
        if not path.is_file():
            raise SystemExit(f"{field}: no file at {path}")
        record[field] = str(path)
    candidate = Path(state_dir) / DEVELOPMENT_CANDIDATE_FILE
    if candidate.is_symlink():
        raise ValueError("development candidate record is a link")
    candidate.unlink(missing_ok=True)
    return write_private(
        Path(state_dir) / FILE, json.dumps(record, sort_keys=True).encode()
    )


def candidate_implementation(state_dir, *, repository=None) -> dict | None:
    """Read an operator's exact local DEVELOPMENT source pin, if one exists.

    Absence keeps every ordinary install on the main-accepted path. A present
    but stale, malformed, or non-private record refuses rather than falling
    back to main or accepting a caller's asserted source authority.
    """
    from carbon.development_session.private_records import private_json
    from carbon.development_session.research_campaign import (
        development_candidate_implementation,
    )

    path = Path(state_dir) / DEVELOPMENT_CANDIDATE_FILE
    if not path.exists() and not path.is_symlink():
        return None
    record = private_json(path)
    if (
        type(record) is not dict
        or set(record)
        != {
            "schema",
            "revision",
            "tree",
            "source_tree_digest",
        }
        or record["schema"] != DEVELOPMENT_CANDIDATE_SCHEMA
    ):
        raise ValueError("development candidate record differs")
    return development_candidate_implementation(
        record["revision"],
        expected_tree=record["tree"],
        expected_source_tree_digest=record["source_tree_digest"],
        repository=repository,
    )


def profile_candidate(profile_path, profile=None, *, repository=None) -> dict | None:
    """Resolve a candidate only from the exact owner-private installed profile.

    A caller's configuration cannot grant DEVELOPMENT source authority: the
    on-disk profile and separate operator pin must both agree with it.
    """
    from carbon.development_session.private_records import private_json
    from scripts.dev.miner_launchpad.runner import validated_profile

    path = Path(profile_path)
    candidate_declared = (
        type(profile) is dict
        and (profile.get("runtime") or {})
        .get("implementation", {})
        .get("source_authority")
        == "DEVELOPMENT_CANDIDATE"
    )
    if (
        not path.is_absolute()
        or path.is_symlink()
        or path.resolve() != path
        or path.name != "runner-profile.json"
        or path.parent.name != "environment"
    ):
        if candidate_declared:
            raise ValueError("exact installed development profile required")
        return None
    candidate = candidate_implementation(
        path.parent.parent,
        **({} if repository is None else {"repository": repository}),
    )
    if candidate is None:
        if candidate_declared:
            raise ValueError("development candidate operator pin required")
        return None
    actual = validated_profile(private_json(path))
    if (
        (profile is not None and actual != profile)
        or actual["campaigns_root"] != str(path.parent / "campaigns")
        or actual["accepted_revision"] != candidate["revision"]
        or actual["runtime"]["implementation"] != candidate
    ):
        raise ValueError("development candidate profile differs")
    return candidate


def bind_development_candidate(
    state_dir, *, revision, tree, source_tree_digest, repository=None
) -> dict:
    """Operator-only pin for a locally built, unqualified DEVELOPMENT tree."""
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_campaign import (
        development_candidate_implementation,
    )
    from scripts.dev.miner_launchpad.environment_setup import write_private

    state = Path(state_dir)
    if not state.is_absolute() or state.is_symlink() or state.resolve() != state:
        raise ValueError("exact owner state directory required")
    recorded = read(state) or {}
    if not {"image_manifest", "analysis_image_manifest"} <= set(recorded):
        raise ValueError("installed image records required before candidate pin")
    if _recorded(state, (GPU_RELEASE_RECORD,)):
        raise ValueError("released image record cannot use development candidate")
    implementation = development_candidate_implementation(
        revision,
        expected_tree=tree,
        expected_source_tree_digest=source_tree_digest,
        repository=repository,
    )
    write_private(
        state / DEVELOPMENT_CANDIDATE_FILE,
        canonical(
            {
                "schema": DEVELOPMENT_CANDIDATE_SCHEMA,
                "revision": revision,
                "tree": tree,
                "source_tree_digest": source_tree_digest,
            }
        ),
    )
    return implementation


def _recorded(state_dir, fields):
    path = Path(state_dir) / FILE
    try:
        if path.is_symlink() or path.stat().st_size > 8192:
            return None
        record = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    if type(record) is not dict or record.get("schema") != SCHEMA:
        return None
    found = {
        field: record[field]
        for field in fields
        if type(record.get(field)) is str
        and Path(record[field]).is_absolute()
        and Path(record[field]).is_file()
    }
    return found or None


def read(state_dir):
    """The recorded image manifests that still exist, or None."""
    return _recorded(state_dir, FIELDS)


def released_gpu(state_dir, gpu_manifest) -> dict | None:
    """The released GPU worker a container can be started from, or None.

    Named only when the installer recorded the GPU worker's release record,
    the record passes every check `worker_image_release` makes, and
    `gpu_manifest`, the GPU worker setup found, is byte-for-byte that
    release's manifest: so the reference names the very worker setup checks
    the container's build identity against. Anything else is None, and setup
    offers the push helper as before.
    """
    from scripts.dev import worker_image_release as release

    path = (_recorded(state_dir, (GPU_RELEASE_RECORD,)) or {}).get(GPU_RELEASE_RECORD)
    if path is None or gpu_manifest is None:
        return None
    try:
        record = release.check_record(json.loads(Path(path).read_text("utf-8")))
        manifest = Path(gpu_manifest).read_text("utf-8")
    except (OSError, ValueError, release.Refused):
        return None
    if record["kind"] != GPU_RELEASE_KIND or manifest != release.canonical(
        record["manifest"]
    ):
        return None
    return {"release_tag": record["release_tag"], "reference": record["reference"]}


def found(state_dir, repo) -> dict:
    """Each image setup can fill in: its path and who recorded it, or none
    and the one command, from the checkout `repo`, that builds it.

    The installer's record comes first. Only the GPU worker is also looked
    for where its build script writes it; setup verifies every image anyway.
    """
    recorded = read(state_dir) or {}
    images = {}
    for field in FIELDS:
        path, by = recorded.get(field), "install_miner.sh"
        if path is None and field == "gpu_image_manifest":
            default = Path(repo) / GPU_DEFAULT
            if default.is_file() and not default.is_symlink():
                path, by = str(default), "accelerator_worker_image.sh"
        script, *arguments = BUILD[field]
        images[field] = {
            "path": path,
            "found_by": by if path else None,
            "build": " ".join([shlex.quote(str(Path(repo) / script)), *arguments]),
        }
    return images


#: The label every image built on the C-03 worker carries: the source tree it
#: was built from (`.devcontainer/Dockerfile.reconstruction-worker`). The GPU
#: worker inherits it from its parent.
SOURCE_TREE_LABEL = "org.opencontainers.image.carbon.c03.source-tree"


def current(manifest, *, implementation=None, cli=None) -> bool:
    """Whether the worker manifest `manifest` (the C-03 worker's or the GPU
    worker's) names an image built from this checkout's exact source tree
    that Docker still holds, so an install can use it again rather than
    build it again (LA-F16).

    Two installs share one checkout, and so its manifests at fixed paths. A
    rebuild at the same revision is a new image with a new id, so a second
    install that rebuilt would change the first one's record under it. The
    test is setup's own (`verify_current_worker`), plus the image itself:
    Docker holds that image id, and its source-tree label is the manifest's.
    Anything else, or any error, is False, and the install builds as before.
    `implementation` is `accepted_implementation` of this checkout's HEAD,
    worked out when not given.
    """
    from carbon.development_session.research_campaign import (
        accepted_implementation,
        verify_current_worker,
    )
    from carbon.reconstruction.worker.docker_runtime import (
        DockerCLI,
        load_image_identity,
    )

    path = Path(manifest)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
            return False
        image = load_image_identity(path)
        if implementation is None:
            import subprocess

            repo = Path(__file__).resolve().parents[3]
            head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True, timeout=30
            ).strip()
            implementation = accepted_implementation(head)
        verify_current_worker(image, implementation)
        metadata = (cli or DockerCLI()).json(
            ["image", "inspect", image.image_id, "--format", "{{json .}}"]
        )
        labels = (metadata.get("Config") or {}).get("Labels") or {}
        return (
            metadata.get("Id") == image.image_id
            and labels.get(SOURCE_TREE_LABEL) == image.source_tree_digest
        )
    except Exception:  # noqa: BLE001 - any doubt builds the image again.
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("write")
    record.add_argument("--state-dir", type=Path, required=True)
    record.add_argument("--image-manifest", required=True)
    record.add_argument("--analysis-image-manifest", required=True)
    record.add_argument("--gpu-image-manifest")
    record.add_argument("--gpu-release-record")
    reuse = commands.add_parser("current")
    reuse.add_argument("--manifest", type=Path, required=True)
    reuse.add_argument("--candidate-revision")
    reuse.add_argument("--candidate-tree")
    reuse.add_argument("--candidate-source-tree-digest")
    verify = commands.add_parser("verify-development-source")
    verify.add_argument("--revision", required=True)
    verify.add_argument("--tree", required=True)
    verify.add_argument("--source-tree-digest", required=True)
    candidate = commands.add_parser("bind-development-candidate")
    candidate.add_argument("--state-dir", type=Path, required=True)
    candidate.add_argument("--revision", required=True)
    candidate.add_argument("--tree", required=True)
    candidate.add_argument("--source-tree-digest", required=True)
    args = parser.parse_args(argv)
    if args.command == "verify-development-source":
        from carbon.development_session.research_campaign import (
            development_candidate_implementation,
        )

        development_candidate_implementation(
            args.revision,
            expected_tree=args.tree,
            expected_source_tree_digest=args.source_tree_digest,
        )
        print("Exact clean DEVELOPMENT source verified.")
        return
    if args.command == "current":
        candidate_fields = (
            args.candidate_revision,
            args.candidate_tree,
            args.candidate_source_tree_digest,
        )
        if any(value is not None for value in candidate_fields):
            if any(value is None for value in candidate_fields):
                raise ValueError("complete development source identity required")
            from carbon.development_session.research_campaign import (
                development_candidate_implementation,
            )

            implementation = development_candidate_implementation(
                args.candidate_revision,
                expected_tree=args.candidate_tree,
                expected_source_tree_digest=args.candidate_source_tree_digest,
            )
        else:
            implementation = None
        print("yes" if current(args.manifest, implementation=implementation) else "no")
        return
    if args.command == "bind-development-candidate":
        bind_development_candidate(
            args.state_dir,
            revision=args.revision,
            tree=args.tree,
            source_tree_digest=args.source_tree_digest,
        )
        print("Pinned exact local DEVELOPMENT candidate for setup.")
        return
    path = write(
        args.state_dir,
        image_manifest=args.image_manifest,
        analysis_image_manifest=args.analysis_image_manifest,
        gpu_image_manifest=args.gpu_image_manifest,
        gpu_release_record=args.gpu_release_record,
    )
    print(f"Recorded the installed images for setup: {path}")


if __name__ == "__main__":
    main()
