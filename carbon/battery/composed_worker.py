"""What Carbon stages for a composed development rebuild (CONSTRUCTION-CONTRACT-01 S1).

A development construction whose reconstruction carries two or more parts
(Level 1's loss expression, Level 2's SpecMuon or pool selection, Level 3's
numerics) trains them together with the composed trainer
(`carbon.battery.composed_training`). The worker gets, beside a Level-0
rebuild's files:
- `battery-composed.json`: which parts are on, and Level 3's menu;
- Carbon's trainer and part modules, staged as each level stages them;
- each part's own files: the loss expression and its operation set (Level 1),
  the drawn pool case ids (Level 2).

Nothing the strategy supplied is executed.

**One part is not composed.** A construction with a single part keeps its own
level's record, program, files and trainer, byte for byte
(`development_rebuild`), so composing changes no single-level rebuild.

**Level 4 is S2.** A Level 4 graph beside any other part is refused
(`construction_rebuild_unavailable`), naming the fields, until the graph is
trained by the composed trainer.

**CPU only for now** (`CPU_ONLY_DEV`), as SpecMuon and the numerics are, until
the A40 R1 leg passes them. Any other device is refused as an environment
failure, never the candidate's.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import level1_worker, level2_worker, level3_worker, level4_worker

SCHEMA = "carbon.battery.composed.v1"
LANE = "CPU_ONLY_DEV"
REBUILD_LABEL = "rebuild: CPU-verified only"
PARTS_FILE = "battery-composed.json"
UNAVAILABLE = "construction_rebuild_unavailable"
#: The recipe field each part comes from, for a refusal that names it.
FIELDS = {
    "expression": "loss_expressions",
    "spectral": "muon_spectral",
    "pool": "pool_selection",
    "numerics": "quasi_newton_family/line_search",
    "graph": "composition_graphs",
}
STAGED_MODULES = {
    "battery-composed-training.py": ("battery", "composed_training.py"),
    "battery-level2-specmuon.py": ("battery", "level2_specmuon.py"),
    "battery-level3-numerics.py": ("battery", "level3_numerics.py"),
    "battery-level3-training.py": ("battery", "level3_training.py"),
    "battery-loss-expressions.py": ("reconstruction", "loss_expressions.py"),
    "battery-loss-terms.py": ("battery", "loss_terms.py"),
}
_BUILD = 'model = recipes.build(recipe["family"], recipe["settings"])\n'
_COMPOSED_BUILD = r"""for staged, module in (
    ("battery-composed-training.py", "composed_training.py"),
    ("battery-level2-specmuon.py", "level2_specmuon.py"),
    ("battery-level3-numerics.py", "level3_numerics.py"),
    ("battery-level3-training.py", "level3_training.py"),
    ("battery-loss-expressions.py", "loss_expressions.py"),
    ("battery-loss-terms.py", "loss_terms.py"),
):
    shutil.copyfile(work / staged, lab / module)
import jax as _jax  # noqa: E402

if _jax.default_backend() != "cpu":  # CPU_ONLY_DEV: Carbon's lane, not the candidate's
    raise ImportError("composed_cpu_only_dev")
from carbon_battery_lab import composed_training  # noqa: E402

_parts = json.loads((work / "battery-composed.json").read_text())
_loss = None
if _parts["expression"]:
    from carbon_battery_lab import loss_expressions, loss_terms  # noqa: E402

    _loss = loss_terms.factory(
        loss_expressions,
        loss_terms.load(
            loss_expressions,
            (work / "loss-expression.json").read_bytes(),
            json.loads((work / "loss-operation-set.json").read_text()),
        ),
    )
model = composed_training.build(
    recipe["family"],
    recipe["settings"],
    loss=_loss,
    spectral=_parts["spectral"],
    numerics=_parts["numerics"],
)
"""


class RebuildUnavailable(ValueError):
    """A combination Carbon cannot rebuild yet: `code` names the fields."""

    def __init__(self, fields):
        self.fields = tuple(fields)
        self.code = UNAVAILABLE + ":" + "+".join(self.fields)
        super().__init__(self.code)


def parts(reconstruction):
    """Every part a development construction's reconstruction carries, by
    name; absent parts are left out."""
    if type(reconstruction) is not dict:
        return {}
    level2 = level2_worker.level2_record(reconstruction)
    found = {
        "expression": level1_worker.expression_record(reconstruction),
        "spectral": level2_worker._spectral_of(level2) if level2 else None,
        "pool": (
            level2.get("pool")
            if type(level2) is dict and level2.get("schema") == level2_worker.SCHEMA_V2
            else None
        ),
        "numerics": level3_worker.numerics_record(reconstruction),
        "graph": level4_worker.graph_record(reconstruction),
    }
    return {name: value for name, value in found.items() if value is not None}


def composed_record(reconstruction):
    """The composed record of a construction with two or more parts, or None
    (a single part keeps its own level's record). A graph beside another part
    is not composed yet: `RebuildUnavailable`, naming the fields."""
    found = parts(reconstruction)
    if len(found) < 2:
        return None
    if "graph" in found:
        raise RebuildUnavailable(FIELDS[name] for name in found)
    numerics = found.get("numerics")
    return {
        "schema": SCHEMA,
        "expression": found.get("expression"),
        "spectral": found.get("spectral"),
        "pool": found.get("pool"),
        "numerics": (
            None
            if numerics is None
            else {
                "routine": numerics["routine"],
                "line_search": numerics["line_search"],
            }
        ),
        "lane": LANE,
    }


def is_composed(record):
    return type(record) is dict and record.get("schema") == SCHEMA


def changes(record):
    """The recipe fields a composed record trains, in a fixed order."""
    return [FIELDS[name] for name in FIELDS if record.get(name)]


def _flags(record):
    return {
        "expression": record["expression"] is not None,
        "spectral": record["spectral"] is not None,
        "numerics": record["numerics"],
    }


def program(base, record):
    """`base` (a Level-0 program) with the pool restriction after TRAIN v1 is
    loaded, when the record selects a pool, and its one build line replaced by
    the composed build."""
    import textwrap

    if record["pool"] is not None:
        if base.count(level2_worker._POOL_ANCHOR) != 1:
            raise RuntimeError("the program's TRAIN load moved")
        base = base.replace(
            level2_worker._POOL_ANCHOR,
            level2_worker._POOL_RESTRICT + level2_worker._POOL_ANCHOR,
        )
    for indent in ("    ", ""):
        line = indent + _BUILD
        if base.count(line) == 1:
            return base.replace(line, textwrap.indent(_COMPOSED_BUILD, indent))
    raise RuntimeError("the program's build line moved")


def build_in_process(recipe, record):
    """The untrained composed model, built in this process as the staged
    program builds it. CPU only, refused as an environment failure."""
    import jax

    if jax.default_backend() != "cpu":
        raise ImportError("composed_cpu_only_dev")
    from carbon.battery import composed_training, loss_terms
    from carbon.reconstruction import loss_expressions

    loss = None
    if record["expression"] is not None:
        expression = record["expression"]
        loss = loss_terms.factory(
            loss_expressions,
            loss_terms.load(
                loss_expressions,
                expression["canonical"].encode("utf-8"),
                expression["operation_set_document"],
            ),
        )
    return composed_training.build(
        recipe.family,
        recipe.settings,
        loss=loss,
        spectral=record["spectral"] is not None,
        numerics=record["numerics"],
    )


def training_data(record, train):
    """The TRAIN a composed record trains on: the drawn pool subset, else
    `train` itself."""
    if record["pool"] is not None:
        from carbon.battery import pools

        return pools.subset(train, record["pool"]["case_ids"])
    return train


def staged(record):
    """The extra files a composed rebuild stages, by name."""
    carbon = Path(__file__).resolve().parents[1]
    files = {
        name: (carbon / folder / module).read_bytes()
        for name, (folder, module) in STAGED_MODULES.items()
    }
    files[PARTS_FILE] = json.dumps(
        _flags(record), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if record["expression"] is not None:
        expression_files = level1_worker.staged(record["expression"])
        for name in (level1_worker.EXPRESSION_FILE, level1_worker.OPERATION_SET_FILE):
            files[name] = expression_files[name]
    if record["pool"] is not None:
        pool = record["pool"]
        files[level2_worker.POOL_FILE] = json.dumps(
            {"cases": pool["cases"], "case_ids": pool["case_ids"]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    return files
