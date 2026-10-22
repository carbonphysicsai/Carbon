"""The image scripts never write bytecode into the checkout (M1, 2026-10-21).

`scripts/dev/accelerator_worker_image.sh` imported `carbon` from the checkout
and left carbon/**/__pycache__ behind; every later launch of a development
candidate was then interrupted "development candidate has ignored runtime
source". Each script that builds, verifies, pushes or releases a worker image
(or the doctor) exports PYTHONDONTWRITEBYTECODE=1 before any Python runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "dev"
IMAGE_SCRIPTS = (
    "accelerator_worker_image",
    "c03_worker_image",
    "doctor",
    "julia_worker_image",
    "push_worker_image",
    "release_c03_parent",
    "release_parent_rehearsal",
    "release_worker_images",
    "torch_gpu_worker_image",
    "torch_worker_image",
    "tpu_worker_image",
    "verify_image",
    "worker_parent_manifest",
)


@pytest.mark.parametrize("name", IMAGE_SCRIPTS)
def test_the_script_exports_no_bytecode_before_any_python(name):
    lines = (SCRIPTS / (name + ".sh")).read_text(encoding="utf-8").splitlines()
    guard = lines.index("export PYTHONDONTWRITEBYTECODE=1")
    first_python = next(
        (i for i, line in enumerate(lines) if "python" in line and i != guard),
        len(lines),
    )
    assert guard < first_python


def test_every_worker_image_script_is_listed():
    found = {p.stem for p in SCRIPTS.glob("*_worker_image*.sh")}
    assert found <= set(IMAGE_SCRIPTS), found - set(IMAGE_SCRIPTS)
