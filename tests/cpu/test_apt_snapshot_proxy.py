"""The worker-image build's apt snapshot proxy (scripts/dev/apt_snapshot_proxy.py) and what it must leave alone."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = "20261116T000000Z"


def _proxy():
    spec = importlib.util.spec_from_file_location(
        "apt_snapshot_proxy", ROOT / "scripts/dev/apt_snapshot_proxy.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_base_images_archive_urls_map_to_the_dated_snapshot():
    url = _proxy().snapshot_url
    root = "https://snapshot.ubuntu.com/ubuntu/" + SNAP + "/"
    assert url(
        "http://archive.ubuntu.com/ubuntu/dists/noble-updates/InRelease", SNAP
    ) == (root + "dists/noble-updates/InRelease")
    # apt percent-encodes `~` and `+` in package file names; they pass through unchanged
    pool = "pool/main/l/llvm-toolchain-20/libllvm20_20.1.2-0ubuntu1%7e24.04.3_amd64.deb"
    assert url("http://security.ubuntu.com/ubuntu/" + pool, SNAP) == root + pool


def test_anything_but_the_ubuntu_archive_is_refused():
    url = _proxy().snapshot_url
    for refused in (
        "http://pypi.org/simple/numpy/",
        "https://archive.ubuntu.com/ubuntu/dists/noble/InRelease",
        "http://archive.ubuntu.com/debian/dists/noble/InRelease",
        "http://archive.ubuntu.com:8080/ubuntu/dists/noble/InRelease",
        "http://archive.ubuntu.com/ubuntu/dists/noble/InRelease?x=1",
        "http://archive.ubuntu.com/ubuntu/../etc/passwd",
        "http://archive.ubuntu.com.evil.example/ubuntu/dists/noble/InRelease",
    ):
        assert url(refused, SNAP) is None, refused


def test_a_malformed_snapshot_is_refused_before_listening():
    run = subprocess.run(
        [
            sys.executable,
            "-I",
            str(ROOT / "scripts/dev/apt_snapshot_proxy.py"),
            "2026-11-16",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert run.returncode == 2 and run.stdout == ""


def test_the_proxy_is_not_a_worker_build_input():
    """It and the build script stay outside the worker image identity; the lock, install script and Dockerfile stay in."""
    inputs = (
        (ROOT / "carbon/reconstruction/worker/build_inputs.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert "scripts/dev/apt_snapshot_proxy.py" not in inputs
    assert "scripts/dev/c03_worker_image.sh" not in inputs
    for kept in (
        ".devcontainer/worker-native-mesh.lock",
        ".devcontainer/install-worker-native-mesh.sh",
        ".devcontainer/Dockerfile.reconstruction-worker",
    ):
        assert kept in inputs
