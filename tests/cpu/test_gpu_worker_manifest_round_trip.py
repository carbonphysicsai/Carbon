"""The GPU worker manifest the build writes is the one setup accepts (S20).

`scripts/dev/accelerator_worker_image.sh` built the GPU worker (exit 0), and
setup refused its manifest as `gpu_image_unverified`: the manifest's
`lock_digest` was the C-03 parent's `uv.lock`, not the CUDA lock the JAX GPU
profile pins. The Dockerfile's identity step was a RUN heredoc, whose body
Docker's legacy builder drops without an error, so the parent's identity
was copied out unchanged.

These tests run the real pieces, with no Docker: the C-03 parent's identity
document as its Dockerfile writes it, the GPU recipe's identity program
(`.devcontainer/accelerators/build_identity.py`) over it, and the script's
own manifest writer over the result. Setup's GPU check (`gpu_image_backend`,
`is_gpu_image`, Battery's `gpu_scope`) accepts that manifest; the parent's
unchanged identity writes no manifest at all.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY / "scripts/dev/accelerator_worker_image.sh"
RECIPE = REPOSITORY / ".devcontainer/accelerators/Dockerfile"
IDENTITY = REPOSITORY / ".devcontainer/accelerators/build_identity.py"
BUILD_FILE = "/opt/carbon/worker-image-build.json"


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def parent_identity() -> dict:
    """The C-03 parent's identity, field by field as its Dockerfile's printf
    writes it: its lock is `uv.lock`'s digest."""
    base = (REPOSITORY / ".devcontainer/Dockerfile.reconstruction-worker").read_text()
    written = re.search(r"printf '(\{\"schema\".*?\})\\n'", base).group(1)
    fields = re.findall(r'"(\w+)":', written)
    assert fields[0] == "schema"
    document = {"schema": json.loads(written.replace("%s", "x"))["schema"]}
    for n, field in enumerate(fields[1:]):
        document[field] = "sha256:" + format(n + 1, "x") * 64
    document["lock_digest"] = digest((REPOSITORY / "uv.lock").read_bytes())
    return document


def writer() -> str:
    """The script's own manifest writer: its python heredoc, byte for byte."""
    text = SCRIPT.read_text()
    (body,) = re.findall(r"<<'PY'\n(.*?)\nPY\n", text, re.DOTALL)
    return body


def build_arguments() -> dict:
    """The build arguments the script passes, computed as it computes them."""
    from carbon.reconstruction.accelerators import GPU_PROFILE

    return {
        "WORKER_IMAGE": "sha256:" + "a" * 64,
        "ACCELERATOR_RECIPE_DIGEST": digest(RECIPE.read_bytes()),
        "ACCELERATOR_PROFILE_DIGEST": GPU_PROFILE.digest,
        "ACCELERATOR_LOCK_DIGEST": digest(
            (REPOSITORY / ".devcontainer/accelerators/cuda13-py311.txt").read_bytes()
        ),
    }


def identity_step(tmp_path, document, arguments) -> Path:
    """Run the recipe's identity program over `document`, at a test path."""
    build = tmp_path / "worker-image-build.json"
    build.write_text(json.dumps(document))
    source = IDENTITY.read_text()
    assert source.count(f'"{BUILD_FILE}"') == 1
    program = tmp_path / "identity.py"
    program.write_text(source.replace(f'"{BUILD_FILE}"', repr(str(build))))
    env = {**os.environ, **arguments, "PYTHONPATH": str(REPOSITORY)}
    subprocess.run(
        [sys.executable, "-B", str(program)], env=env, check=True, cwd=tmp_path
    )
    return build


def write_manifest(tmp_path, build: Path, image: str, arguments: dict):
    """Run the script's writer as it does: `python3 - IMAGE BUILD OUT PARENT
    RECIPE LOCK`."""
    out = tmp_path / "accelerator-worker-image.json"
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-",
            image,
            str(build),
            str(out),
            arguments["WORKER_IMAGE"],
            arguments["ACCELERATOR_RECIPE_DIGEST"],
            arguments["ACCELERATOR_LOCK_DIGEST"],
        ],
        input=writer(),
        capture_output=True,
        text=True,
        check=False,
    )
    return result, out


def test_the_built_manifest_is_the_jax_gpu_worker_setup_accepts(tmp_path):
    from carbon.development_session.battery_gpu import gpu_scope
    from carbon.development_session.gpu_practice import gpu_image_backend, is_gpu_image
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    arguments = build_arguments()
    # The script's lock is the JAX GPU profile's pinned lock, not uv.lock.
    assert arguments["ACCELERATOR_LOCK_DIGEST"] == GPU_PROFILE.environment_lock_digest
    assert 'cuda13-py311.txt" | cut' in SCRIPT.read_text()
    build = identity_step(tmp_path, parent_identity(), arguments)
    image = "sha256:" + "e" * 64
    result, out = write_manifest(tmp_path, build, image, arguments)
    assert result.returncode == 0, result.stderr
    identity = load_image_identity(out)
    assert identity.image_id == image
    assert identity.lock_digest == GPU_PROFILE.environment_lock_digest
    assert identity.base_image_digest == arguments["WORKER_IMAGE"]
    assert identity.build_recipe_digest == arguments["ACCELERATOR_RECIPE_DIGEST"]
    # Setup's GPU check: the JAX GPU worker, which Battery's GPU route takes.
    assert gpu_image_backend(identity) == "jax" and is_gpu_image(identity)
    assert gpu_scope(identity)["image"] == image


def test_a_build_whose_identity_step_did_not_run_writes_no_manifest(tmp_path):
    """S20: the parent's identity, copied out unchanged, is refused by the
    writer, so setup never sees a manifest naming `uv.lock`."""
    from carbon.development_session.gpu_practice import gpu_image_backend
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    arguments = build_arguments()
    unchanged = parent_identity()
    build = tmp_path / "worker-image-build.json"
    build.write_text(json.dumps(unchanged))
    result, out = write_manifest(tmp_path, build, "sha256:" + "e" * 64, arguments)
    assert result.returncode != 0 and not out.exists()
    assert "base_image_digest, build_recipe_digest, lock_digest" in result.stderr
    # And such a manifest, had it been written, is exactly what setup refused.
    fields = {k: v for k, v in unchanged.items() if k != "schema"}
    stale = WorkerImageIdentity(
        image_id="sha256:" + "e" * 64, config_digest="sha256:" + "e" * 64, **fields
    )
    assert gpu_image_backend(stale) is None


@pytest.mark.parametrize(
    "key", ["ACCELERATOR_LOCK_DIGEST", "ACCELERATOR_PROFILE_DIGEST"]
)
def test_the_identity_step_refuses_another_profile_or_lock(tmp_path, key):
    arguments = {**build_arguments(), key: "sha256:" + "0" * 64}
    with pytest.raises(subprocess.CalledProcessError):
        identity_step(tmp_path, parent_identity(), arguments)


def test_no_gpu_recipe_step_is_a_heredoc_a_builder_can_drop():
    recipe = RECIPE.read_text()
    assert "<<" not in recipe
    assert "COPY .devcontainer/accelerators/build_identity.py " in recipe
    assert "python -I /tmp/carbon-build-identity.py" in recipe
