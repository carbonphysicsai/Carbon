"""A canonical run fails (never silently skips) a test that skipped for a missing tool."""

import subprocess
import sys
import textwrap

SKIPPING = textwrap.dedent("""
    import shutil
    import pytest

    def test_needs_node():
        if shutil.which("node-that-does-not-exist") is None:
            pytest.skip("node is not installed here")

    @pytest.mark.skipif(True, reason="node is not installed")
    def test_marked():
        pass

    def test_other_skip():
        pytest.skip("a different reason")
    """)


def _run(tmp_path, env_extra):
    import os

    (tmp_path / "test_x.py").write_text(SKIPPING)
    root = tmp_path.parents[0]
    del root
    env = {k: v for k, v in os.environ.items() if k != "CARBON_CANONICAL_DEV_ENV"}
    env.update(env_extra)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-q",
            "--rootdir",
            str(tmp_path),
            "-c",
            "/dev/null",
            "--confcutdir",
            str(tmp_path),
            "-p",
            "tests.conftest",
            str(tmp_path / "test_x.py"),
        ],
        capture_output=True,
        text=True,
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
        env=env,
    )


def test_outside_the_canonical_image_a_missing_tool_is_a_skip(tmp_path):
    done = _run(tmp_path, {})
    assert "3 skipped" in done.stdout, done.stdout + done.stderr


def test_in_the_canonical_image_a_missing_node_is_a_failure(tmp_path):
    done = _run(tmp_path, {"CARBON_CANONICAL_DEV_ENV": "ubuntu-24.04-test"})
    # The test-body skip fails; the skipif mark fails at setup (an error); a skip
    # for any other reason stays a skip.
    assert "1 failed" in done.stdout and "1 error" in done.stdout, done.stdout
    assert "1 skipped" in done.stdout, done.stdout
    assert "required tool missing in the canonical environment: node" in done.stdout


def test_the_dockerfile_pins_node_by_version_and_sha256():
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2] / ".devcontainer/Dockerfile"
    ).read_text()
    assert "ARG NODE_VERSION=22.11.0" in text
    assert (
        "ARG NODE_SHA256=83bf07dd343002a26211cf1fcd46a9d9534219aad42ee02847816940bf610a72"
        in text
    )
    assert "sha256sum -c -" in text
