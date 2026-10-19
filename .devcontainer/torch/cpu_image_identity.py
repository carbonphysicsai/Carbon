"""Build-only identity recording and pin checks for the CPU Torch image."""

from __future__ import annotations

import json
import os
import re
import sys
from importlib import metadata
from pathlib import Path


def record(path: Path) -> None:
    keys = ("WORKER_IMAGE", "TORCH_RECIPE_DIGEST", "TORCH_LOCK_DIGEST")
    for key in keys:
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", os.environ.get(key, "")):
            raise SystemExit("Exact immutable image identities required")
    document = json.loads(path.read_text())
    document.update(
        base_image_digest=os.environ["WORKER_IMAGE"],
        build_recipe_digest=os.environ["TORCH_RECIPE_DIGEST"],
        lock_digest=os.environ["TORCH_LOCK_DIGEST"],
    )
    path.chmod(0o600)
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
    path.chmod(0o444)


def verify() -> None:
    from carbon.reconstruction.torch_profile import CPU_DETERMINISM_DIGEST, PINS

    for name, version, _ in PINS:
        installed = metadata.version(name).split("+")[0]
        if installed != version:
            raise SystemExit(f"{name} {installed} is not the pinned {version}")
    if os.environ.get("TORCH_DETERMINISM_DIGEST") != CPU_DETERMINISM_DIGEST:
        raise SystemExit(
            "the determinism label is not the installed source's configuration"
        )


def main() -> None:
    if sys.argv[1:] == ["record"]:
        record(Path("/opt/carbon/worker-image-build.json"))
    elif sys.argv[1:] == ["verify"]:
        verify()
    else:
        raise SystemExit("one build operation required: record or verify")


if __name__ == "__main__":
    main()
