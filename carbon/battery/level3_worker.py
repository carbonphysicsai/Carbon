"""What Carbon stages for a Level-3 (training-time numerics) rebuild.

A development construction whose reconstruction names a non-default
quasi-Newton routine or line search trains with them in the polish stage.
The worker gets, beside a Level-0 rebuild's files, Carbon's numerics module
and the Level-3 trainer (`battery-level3-numerics.py`,
`battery-level3-training.py`) and `level3-numerics.json`, the menu choices.
Nothing the strategy supplied is executed.

**The default is Level 0.** A recipe that names the default routine and line
search (or neither) has no numerics record: it rebuilds through Level 0's
program, files and trainer, byte for byte.

**CPU only for now** (`CPU_ONLY_DEV`). The dense inverse Hessian and its
linear algebra are GPU-nondeterminism risks until the A40 R1 leg passes them,
so a Level-3 rebuild on any other device is refused as an environment
failure, never the candidate's.
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.battery.level3_numerics import DEFAULT

QUASI_NEWTON = "numerics.quasi_newton_family"
LINE_SEARCH = "numerics.line_search"
SCHEMA = "carbon.battery.level3-numerics.v1"
LANE = "CPU_ONLY_DEV"
REBUILD_LABEL = "rebuild: CPU-verified only"
NUMERICS_FILE = "level3-numerics.json"
STAGED_MODULES = {
    "battery-level3-numerics.py": ("battery", "level3_numerics.py"),
    "battery-level3-training.py": ("battery", "level3_training.py"),
}
_BUILD = 'model = recipes.build(recipe["family"], recipe["settings"])\n'
_LEVEL3_BUILD = r"""for staged, module in (
    ("battery-level3-numerics.py", "level3_numerics.py"),
    ("battery-level3-training.py", "level3_training.py"),
):
    shutil.copyfile(work / staged, lab / module)
import jax as _jax  # noqa: E402

if _jax.default_backend() != "cpu":  # CPU_ONLY_DEV: Carbon's lane, not the candidate's
    raise ImportError("level3_cpu_only_dev")
from carbon_battery_lab import level3_training  # noqa: E402

model = level3_training.build(
    recipe["family"],
    recipe["settings"],
    json.loads((work / "level3-numerics.json").read_text()),
)
"""


def numerics_record(reconstruction):
    """The numerics a development construction trains with, or None: Level 0,
    a variant without Level 3, or Level 3's defaults."""
    if type(reconstruction) is not dict:
        return None
    routine = (reconstruction.get(QUASI_NEWTON) or {}).get(
        "routine", DEFAULT["routine"]
    )
    search = (reconstruction.get(LINE_SEARCH) or {}).get(
        "line_search", DEFAULT["line_search"]
    )
    if {"routine": routine, "line_search": search} == DEFAULT:
        return None
    return {"schema": SCHEMA, "routine": routine, "line_search": search, "lane": LANE}


def is_numerics(record):
    return type(record) is dict and record.get("schema") == SCHEMA


def _menu(record):
    return {"routine": record["routine"], "line_search": record["line_search"]}


def program(base):
    """`base` (a Level-0 program) with its one build line replaced by the
    Level-3 build."""
    import textwrap

    for indent in ("    ", ""):
        line = indent + _BUILD
        if base.count(line) == 1:
            return base.replace(line, textwrap.indent(_LEVEL3_BUILD, indent))
    raise RuntimeError("the program's build line moved")


def build_in_process(recipe, record):
    """The untrained Level-3 model, built in this process as the staged
    program builds it. CPU only, refused as an environment failure."""
    import jax

    if jax.default_backend() != "cpu":
        raise ImportError("level3_cpu_only_dev")
    from carbon.battery import level3_training

    return level3_training.build(recipe.family, recipe.settings, _menu(record))


def staged(record):
    """The extra files a Level-3 rebuild stages, by name."""
    carbon = Path(__file__).resolve().parents[1]
    files = {
        name: (carbon / folder / module).read_bytes()
        for name, (folder, module) in STAGED_MODULES.items()
    }
    files[NUMERICS_FILE] = json.dumps(
        _menu(record), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return files
