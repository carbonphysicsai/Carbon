"""What Carbon stages for a composed development rebuild (CONSTRUCTION-CONTRACT-01 S1/S2).

A development construction whose reconstruction carries parts of two or more
levels (Level 1's loss expression, Level 2's SpecMuon or pool selection, Level
3's numerics) trains them together with the composed trainer
(`carbon.battery.composed_training`). The worker gets, beside a Level-0
rebuild's files:
- `battery-composed.json`: which parts are on, and Level 3's menu;
- Carbon's trainer and part modules, staged as each level stages them;
- each part's own files: the loss expression and its operation set (Level 1),
  the drawn pool case ids (Level 2).

Nothing the strategy supplied is executed.

**One level is not composed.** A construction whose parts are all one level's
(SpecMuon and a pool selection are both Level 2's) keeps that level's own
record, program, files and trainer, byte for byte
(`development_rebuild`), so composing changes no single-level rebuild.

**Level 4 combinations use a prospective graph record.** The existing graph
network, initialization and state wrap the composed trainer. Its workspace
documents travel with reconstruction. An actual graph loss plus an L1 objective
refuses with `construction_rebuild_unavailable`, naming both fields.

**CPU only for now** (`CPU_ONLY_DEV`), as SpecMuon and the numerics are, until
the A40 R1 leg passes them. Any other device is refused as an environment
failure, never the candidate's.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import level1_worker, level2_worker, level3_worker, level4_worker

SCHEMA = "carbon.battery.composed.v1"
GRAPH_SCHEMA = "carbon.battery.composed-graph.v1"
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
#: The level each part belongs to: composing starts at two levels.
LEVEL_OF = {"expression": 1, "spectral": 2, "pool": 2, "numerics": 3, "graph": 4}
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


_COMPOSED_GRAPH_BUILD = level4_worker._PRELUDE + _COMPOSED_BUILD.replace(
    'model = composed_training.build(\n    recipe["family"],\n    recipe["settings"],\n',
    'shutil.copyfile(work / "battery-composed-graph.py", lab / "composed_graph.py")\n'
    "from carbon_battery_lab import composed_graph, level4_model\n"
    "model = composed_graph.ComposedGraph(\n"
    "    level4_model.build_from_work(recipe, work),\n",
)


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
    (a single part keeps its own level's record). Graph combinations use the
    prospective graph schema, preserving the existing non-graph record."""
    found = parts(reconstruction)
    if len({LEVEL_OF[name] for name in found}) < 2:
        # One level's parts (SpecMuon and a pool selection are both Level 2)
        # keep that level's own record and route.
        return None
    numerics = found.get("numerics")
    record = {
        "schema": GRAPH_SCHEMA if "graph" in found else SCHEMA,
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
    if "graph" in found:
        record["graph"] = found["graph"]
        if numerics is not None:
            source = reconstruction.get(level3_worker.QUASI_NEWTON) or {}
            if "memory_bound_bytes" in source:
                record["numerics"]["memory_bound_bytes"] = source["memory_bound_bytes"]
    return record


def is_composed(record):
    return type(record) is dict and record.get("schema") in (SCHEMA, GRAPH_SCHEMA)


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
            body = _COMPOSED_GRAPH_BUILD if record.get("graph") else _COMPOSED_BUILD
            built = base.replace(line, textwrap.indent(body, indent))
            if record.get("graph") and level4_worker._STATE in base:
                built = level4_worker._replace(
                    built, level4_worker._STATE, level4_worker._LEVEL4_STATE
                )
            return built
    raise RuntimeError("the program's build line moved")


def build_in_process(recipe, record, workspace=None):
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
    if record.get("graph") is not None:
        if workspace is None:
            raise ImportError(level4_worker.BLOCKED)
        from . import composed_graph

        return composed_graph.build(
            recipe,
            record["graph"],
            workspace,
            loss=loss,
            spectral=record["spectral"] is not None,
            numerics=record["numerics"],
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
    if record.get("graph") is not None:
        files.update(level4_worker.staged(record["graph"]))
        files["battery-composed-graph.py"] = (
            carbon / "battery" / "composed_graph.py"
        ).read_bytes()
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
