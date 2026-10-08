"""What Carbon stages for a Level-2 SpecMuon rebuild (`specmuon-carbon-v1`).

A development construction whose reconstruction turns `muon_spectral` on
trains with `carbon.battery.level2_specmuon` wrapping battery's Muon. The
worker gets, beside a Level-0 rebuild's files, Carbon's SpecMuon module and
the Level-2 trainer. Nothing the strategy supplied is executed.

**Off is Level 0.** A recipe without `muon_spectral`, or with it false, has no
record and rebuilds through Level 0's program, files and trainer.

**CPU only for now** (`CPU_ONLY_DEV`): the per-step SVD is a
GPU-nondeterminism risk until the A40 R1 leg passes it. Any other device is
refused as an environment failure, never the candidate's.
"""

from __future__ import annotations

from pathlib import Path

SPECTRAL = "optimizer.muon_spectral"
SCHEMA = "carbon.battery.level2-spectral.v1"
LANE = "CPU_ONLY_DEV"
REBUILD_LABEL = "rebuild: CPU-verified only"
STAGED_MODULES = {
    "battery-level2-specmuon.py": ("battery", "level2_specmuon.py"),
    "battery-level2-training.py": ("battery", "level2_training.py"),
}
_BUILD = 'model = recipes.build(recipe["family"], recipe["settings"])\n'
_LEVEL2_BUILD = r"""for staged, module in (
    ("battery-level2-specmuon.py", "level2_specmuon.py"),
    ("battery-level2-training.py", "level2_training.py"),
):
    shutil.copyfile(work / staged, lab / module)
import jax as _jax  # noqa: E402

if _jax.default_backend() != "cpu":  # CPU_ONLY_DEV: Carbon's lane, not the candidate's
    raise ImportError("level2_cpu_only_dev")
from carbon_battery_lab import level2_training  # noqa: E402

model = level2_training.build(recipe["family"], recipe["settings"])
"""


def spectral_record(reconstruction):
    """The SpecMuon record of a development construction, or None."""
    if type(reconstruction) is not dict:
        return None
    found = reconstruction.get(SPECTRAL) or {}
    if not found.get("muon_spectral"):
        return None
    return {"schema": SCHEMA, "interpretation": found["interpretation"], "lane": LANE}


def is_spectral(record):
    return type(record) is dict and record.get("schema") == SCHEMA


def program(base):
    """`base` with its one build line replaced by the Level-2 build."""
    import textwrap

    for indent in ("    ", ""):
        line = indent + _BUILD
        if base.count(line) == 1:
            return base.replace(line, textwrap.indent(_LEVEL2_BUILD, indent))
    raise RuntimeError("the program's build line moved")


def build_in_process(recipe, record):
    import jax

    if jax.default_backend() != "cpu":
        raise ImportError("level2_cpu_only_dev")
    from carbon.battery import level2_training

    return level2_training.build(recipe.family, recipe.settings)


def staged(record):
    carbon = Path(__file__).resolve().parents[1]
    return {
        name: (carbon / folder / module).read_bytes()
        for name, (folder, module) in STAGED_MODULES.items()
    }
