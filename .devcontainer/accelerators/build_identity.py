"""Write the NVIDIA GPU worker's build identity, inside its image build.

Run by `.devcontainer/accelerators/Dockerfile` as a file, never as a RUN
heredoc: Docker's legacy builder (no buildx) drops a heredoc's body without
an error, so the parent's identity, with its `uv.lock` digest, was kept and
setup refused the image as `gpu_image_unverified` (S20, 2026-10-21).

It keeps the C-03 worker's `worker-image-build.json` and updates only its
base image, recipe and lock, after checking the build arguments name this
source's GPU profile and lock.
"""

import json
import os
import pathlib
import re

from carbon.reconstruction.accelerators import GPU_PROFILE

KEYS = (
    "WORKER_IMAGE",
    "ACCELERATOR_RECIPE_DIGEST",
    "ACCELERATOR_PROFILE_DIGEST",
    "ACCELERATOR_LOCK_DIGEST",
)
for key in KEYS:
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", os.environ.get(key, "")):
        raise SystemExit("Exact immutable image identities required")
if (
    os.environ["ACCELERATOR_PROFILE_DIGEST"] != GPU_PROFILE.digest
    or os.environ["ACCELERATOR_LOCK_DIGEST"] != GPU_PROFILE.environment_lock_digest
):
    raise SystemExit("Installed source and accelerator environment differ")
path = pathlib.Path("/opt/carbon/worker-image-build.json")
document = json.loads(path.read_text())
document.update(
    base_image_digest=os.environ["WORKER_IMAGE"],
    build_recipe_digest=os.environ["ACCELERATOR_RECIPE_DIGEST"],
    lock_digest=os.environ["ACCELERATOR_LOCK_DIGEST"],
)
path.chmod(0o600)
path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
path.chmod(0o444)
