#!/usr/bin/env python3
"""Inspect or stage a pinned user library bundle for offline construction.

The input directory contains bundle.json, source.tar.gz, requirements.txt,
LICENSE, and the manifest-named files under wheels/. Its name need not appear
in Carbon's discovery catalogue. Staging stores exact source bytes without
building an image; an admitted task separately verifies its dependency closure
and child image before a model runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from carbon.development_session.gpu_practice import (
    direct_parent_backend,
    gpu_image_backend,
)
from carbon.development_session.library_bundles import (
    bundle_ref,
    load_pinned_bundle_directory,
    prepare_pinned_bundle_directory,
    verify_bundle_parent_environment,
)
from carbon.development_session.library_environment_cache import (
    install_pinned_library_worker_image,
    stage_pinned_bundle_material,
)
from carbon.development_session.profile import digest
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    load_image_identity,
)
from carbon.reconstruction.worker.model import WorkerFailure
from scripts.dev.miner_launchpad.environment_setup import (
    DEFAULT_STATE_DIR,
    EnvironmentSetup,
    SetupRefused,
    _private_dir,
)


def inspect(directory):
    """Return source-closure readiness, not installed-environment readiness."""
    material = load_pinned_bundle_directory(directory)
    return {
        "status": "PINNED_MATERIAL_VALIDATED",
        "bundle_ref": bundle_ref(*material).to_dict(),
        "dependency_status": "PENDING_OFFLINE_INSTALL_AND_PIP_CHECK",
        "image_status": "NOT_VERIFIED",
        "qualification": "DEVELOPMENT_ONLY",
    }


def import_bundle(directory, cache_root, parent_image):
    """Prepare exact immutable build inputs without Docker or code execution."""
    ref, context, context_digest = prepare_pinned_bundle_directory(
        directory, cache_root, parent_image
    )
    return {
        "status": "OFFLINE_CONTEXT_PREPARED",
        "bundle_ref": ref.to_dict(),
        "context": str(context),
        "context_digest": context_digest,
        "parent_image": parent_image,
        "dependency_status": "PENDING_OFFLINE_INSTALL_AND_PIP_CHECK",
        "image_status": "NOT_VERIFIED",
        "qualification": "DEVELOPMENT_ONLY",
    }


def _checked_cpu_parent(profile, manifest):
    """Bind the CPU closure to Setup's actual installed C-03 worker ABI."""
    from carbon.development_session.research_campaign import verify_direct_v13_worker

    paths = profile.get("paths")
    runtime = profile.get("runtime")
    if (
        type(paths) is not dict
        or type(runtime) is not dict
        or type(paths.get("image_manifest")) is not str
        or type(runtime.get("implementation")) is not dict
        or type(runtime.get("images")) is not list
        or not runtime["images"]
    ):
        raise ValueError("compatible installed CPU parent missing")
    parent = load_image_identity(Path(paths["image_manifest"]))
    verify_direct_v13_worker(parent, runtime["implementation"], role="cpu")
    expected_lock = digest((REPOSITORY / "uv.lock").read_bytes())
    if (
        parent.image_id != runtime["images"][0]
        or parent.lock_digest != expected_lock
        or manifest["base_environment_digest"] != expected_lock
        or parent.build_recipe_digest
        != digest(
            (REPOSITORY / ".devcontainer/Dockerfile.reconstruction-worker").read_bytes()
        )
        or parent.entrypoint_digest
        != digest(
            (REPOSITORY / "carbon/reconstruction/worker/entrypoint.py").read_bytes()
        )
        or gpu_image_backend(parent) is not None
    ):
        raise ValueError("installed CPU parent lock or ABI differs")
    return parent


def install_bundle(directory, state_dir=DEFAULT_STATE_DIR):
    """Owner-initiated install using checked local setup, never MCP preflight.

    Select the declared installed CPU or CUDA parent by exact runtime ABI.
    Image selection does not assert a live GPU or scientific qualification.
    """
    profile = EnvironmentSetup(state_dir, onboarding=None).profile()
    material = load_pinned_bundle_directory(directory)
    selected = bundle_ref(*material)
    if selected.runtime_profile_id == "python-cpu-py311":
        parent = _checked_cpu_parent(profile, material[0])
    elif selected.runtime_profile_id == "torch-cpu-py311":
        paths = profile.get("paths")
        runtime = profile.get("runtime")
        if (
            type(paths) is not dict
            or type(paths.get("image_manifest")) is not str
            or type(runtime) is not dict
            or type(runtime.get("images")) is not list
            or not runtime["images"]
        ):
            raise ValueError("compatible installed Torch CPU parent missing")
        parent = load_image_identity(Path(paths["image_manifest"]))
        if parent.image_id != runtime["images"][0]:
            raise ValueError("installed Torch CPU parent differs from profile")
        verify_bundle_parent_environment(material[0], parent)
    else:
        expected_backend = {
            "jax-cuda13-py311": "jax",
            "torch-cu130-py311": "pytorch",
        }.get(selected.runtime_profile_id)
        if expected_backend is None:
            raise ValueError("pinned bundle runtime has no registered parent")
        parent_manifest = profile.get("gpu_image")
        if type(parent_manifest) is not str:
            raise ValueError(
                "compatible installed parent missing for " + selected.runtime_profile_id
            )
        parent = load_image_identity(Path(parent_manifest))
        if direct_parent_backend(parent) != expected_backend:
            raise ValueError("installed parent backend differs from pinned bundle")
    campaigns = Path(profile["campaigns_root"])
    owner_root = _private_dir(campaigns / ".direct-development")
    cache_root = _private_dir(owner_root / "library-cache")
    image = install_pinned_library_worker_image(
        directory,
        cache_root,
        parent,
        expected_bundle=selected,
        cli=DockerCLI(),
    )
    return {
        "status": "INSTALLED_VERIFIED",
        "bundle_ref": image.bundle_ref,
        "qualification": "DEVELOPMENT_ONLY",
    }


def install_receiver_bundle(directory, receiver_config):
    """Owner-initiated install on a DEVELOPMENT receiver host, never MCP.

    A receiver has no Launchpad miner setup (signer, inference, agent): it
    serves from its operator record's runner profile. The parent and library
    cache are exactly the ones the receiver verifies when it starts
    (`direct_receiver.installed_source`), so its resolver finds the child.
    """
    from carbon.challenge_validator import direct_receiver

    cfg = direct_receiver.load_config(Path(receiver_config))
    _implementation, parent, _network, cache = direct_receiver.installed_source(
        Path(cfg["runner_profile"]),
        **(
            {"construction_image_manifest": Path(cfg["construction_image_manifest"])}
            if "construction_image_manifest" in cfg
            else {}
        ),
    )
    material = load_pinned_bundle_directory(directory)
    selected = bundle_ref(*material)
    try:
        verify_bundle_parent_environment(material[0], parent)
    except ValueError as error:
        raise ValueError(
            "backend_not_served: the receiver's construction parent does not "
            f"build {selected.runtime_profile_id} bundles ({error})"
        ) from None
    # The receiver's own campaigns root; the library cache under it is created
    # owner-only here exactly where `installed_source` names it.
    if not cache.parent.parent.is_dir() or cache.parent.parent.is_symlink():
        raise ValueError("receiver campaigns root missing")
    cache_root = _private_dir(_private_dir(cache.parent) / cache.name)
    image = install_pinned_library_worker_image(
        directory,
        cache_root,
        parent,
        expected_bundle=selected,
        cli=DockerCLI(),
    )
    return {
        "status": "INSTALLED_VERIFIED",
        "host": "receiver",
        "bundle_ref": image.bundle_ref,
        "parent_image": parent.image_id,
        "qualification": "DEVELOPMENT_ONLY",
    }


def stage_bundle(directory, state_dir=DEFAULT_STATE_DIR):
    """Place an exact closure where direct admission can find its digest."""
    # Source staging precedes compute, agent and image setup. The launchpad's
    # campaigns path is fixed by its owner state directory, so no ready runner
    # profile is needed to store inert bytes there.
    root = Path(state_dir)
    for part in ("environment", "campaigns"):
        if root.is_symlink():
            raise ValueError("staging state path must not be a link")
        root = _private_dir(root)
        root = root / part
    if root.is_symlink():
        raise ValueError("staging campaigns path must not be a link")
    campaigns = _private_dir(root)
    owner_root = _private_dir(campaigns / ".direct-development")
    cache_root = _private_dir(owner_root / "library-cache")
    selected = stage_pinned_bundle_material(directory, cache_root)
    return {
        "status": "PINNED_MATERIAL_STAGED",
        "bundle_ref": selected.to_dict(),
        "image_status": "NOT_BUILT",
        "qualification": "DEVELOPMENT_ONLY",
    }


#: The step that clears each kind of refusal. A refusal names a closed code and
#: its next step, not only free text (Launchpad J0, 19 Oct: "step_not_checked"
#: and "wheel identity differs" left the miner without a next action).
MATERIAL_NEXT_STEP = (
    "rebuild the bundle directory from its pinned inputs, so bundle.json, "
    "source.tar.gz, requirements.txt, LICENSE and every file in wheels/ match "
    "bundle.json's digests; `library_bundle.py doctor DIR` checks them again"
)
UNREADABLE_NEXT_STEP = (
    "check that the directory and every file bundle.json names exist and are "
    "readable by you, then run the command again"
)
WORKER_NEXT_STEP = (
    "run the miner setup check (carbon_setup_status, or the Control Center's "
    "setup page) and repair what it names, then run the command again"
)


def refusal(exc):
    """`{"status": "REFUSED", "code", "next_step", ...}` for a refused command.
    `reason` keeps the refusal's own words where it has them."""
    if isinstance(exc, SetupRefused):
        from scripts.dev.miner_launchpad.setup_operations import NEXT_STEPS

        step = exc.next_step or NEXT_STEPS.get(exc.code, WORKER_NEXT_STEP)
        return {
            "status": "REFUSED",
            "code": exc.code,
            "field": exc.field,
            "reason": exc.code,
            "next_step": step,
        }
    if isinstance(exc, WorkerFailure):
        code = getattr(exc.code, "value", str(exc.code))
        return {
            "status": "REFUSED",
            "code": "library_worker_" + code,
            "reason": str(exc),
            "next_step": WORKER_NEXT_STEP,
        }
    if isinstance(exc, OSError):
        return {
            "status": "REFUSED",
            "code": "library_bundle_unreadable",
            "reason": exc.strerror or type(exc).__name__,
            "next_step": UNREADABLE_NEXT_STEP,
        }
    return {
        "status": "REFUSED",
        "code": "library_bundle_material_differs",
        "reason": str(exc),
        "next_step": MATERIAL_NEXT_STEP,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="validate pinned input bytes")
    doctor.add_argument("directory", type=Path)
    imported = subcommands.add_parser(
        "import", help="prepare an owner cache for the existing offline builder"
    )
    imported.add_argument("directory", type=Path)
    imported.add_argument("--cache-root", required=True, type=Path)
    imported.add_argument("--parent-image", required=True)
    staged = subcommands.add_parser(
        "stage", help="stage a complete pinned closure without building an image"
    )
    staged.add_argument("directory", type=Path)
    staged.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    installed = subcommands.add_parser(
        "install", help="install a pinned bundle under checked local setup"
    )
    installed.add_argument("directory", type=Path)
    installed.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = inspect(args.directory)
        elif args.command == "import":
            result = import_bundle(args.directory, args.cache_root, args.parent_image)
        elif args.command == "stage":
            result = stage_bundle(args.directory, args.state_dir)
        else:
            result = install_bundle(args.directory, args.state_dir)
    except (OSError, ValueError, SetupRefused, WorkerFailure) as exc:
        print(json.dumps(refusal(exc), sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
