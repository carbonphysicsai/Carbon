"""The KOTH margin registry is outside the worker image's build inputs: writing a margin never moves the image id.

The image's source digest is the git listing of `build_inputs.paths()` (`carbon/` among them); a registered margin is
host-read data, so it lives beside the host-class records instead, and nothing a worker container imports reads it.
"""

from __future__ import annotations

from pathlib import Path

from carbon.challenge_validator import koth_registry
from carbon.reconstruction.worker import build_inputs

ROOT = Path(__file__).resolve().parents[2]


def _inside(path: Path, inputs) -> bool:
    relative = path.resolve().relative_to(ROOT).as_posix()
    return any(relative == item or relative.startswith(item + "/") for item in inputs)


def test_the_margin_registry_is_not_a_worker_image_build_input():
    assert koth_registry.REGISTRY.is_file()
    assert not _inside(koth_registry.REGISTRY, build_inputs.paths())
    assert koth_registry.REGISTRY.parent.name == "validator_host_classes"


def test_the_registry_still_loads_and_the_old_path_is_gone():
    assert isinstance(koth_registry._load(), dict)
    assert not (ROOT / "carbon/challenge_validator/koth_rebuild_noise.json").exists()


def test_no_worker_staged_module_reads_the_registry():
    from carbon.development_session import (
        bundle_construction_worker,
        direct_graph_construction_worker,
    )

    staged = {
        *bundle_construction_worker.STAGED_MODULES,
        *direct_graph_construction_worker.STAGED_MODULES,
    }
    for module in sorted(staged):
        source = (ROOT / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8")
        assert (
            "koth_registry" not in source and "koth_rebuild_noise" not in source
        ), module
