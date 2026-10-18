#!/usr/bin/env python3
"""Inspect and import a pinned user library bundle for offline construction.

The input directory contains bundle.json, source.tar.gz, requirements.txt,
LICENSE, and the manifest-named files under wheels/. Its name need not appear
in Carbon's discovery catalogue. Import only prepares an immutable context;
the Product host separately verifies local images and the installed dependency
closure before a model can run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from carbon.development_session.gpu_practice import gpu_image_backend
from carbon.development_session.library_bundles import (
    bundle_ref,
    load_pinned_bundle_directory,
    prepare_pinned_bundle_directory,
)
from carbon.development_session.library_environment_cache import (
    install_pinned_library_worker_image,
)
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


def install_bundle(directory, state_dir=DEFAULT_STATE_DIR):
    """Owner-initiated install using checked local setup, never MCP preflight.

    Current pinned bundle ABI closures require one of the two registered CUDA
    worker parents. This selects a compatible image identity, not a live GPU
    device or a scientific qualification state.
    """
    profile = EnvironmentSetup(state_dir, onboarding=None).profile()
    material = load_pinned_bundle_directory(directory)
    selected = bundle_ref(*material)
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
    if gpu_image_backend(parent) != expected_backend:
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
        else:
            result = install_bundle(args.directory, args.state_dir)
    except (OSError, ValueError, SetupRefused, WorkerFailure) as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
