"""What Carbon stages for a Level-1 (loss-expression) practice trial.

A development construction whose reconstruction carries a compiled loss
expression trains with the expression in place of the objective menu. The
practice worker gets, beside a Level-0 trial's files:
- `loss-expression.json`: the expression's canonical bytes;
- `loss-operation-set.json`: the canonical document of the operation set it
  was compiled against;
- `battery-loss-expressions.py`, `battery-loss-terms.py` and
  `battery-level1-training.py`: Carbon's loss-expression module, battery's
  terms and the Level-1 trainer (`carbon.battery.level1_training`), staged as
  the trainer is.

The worker recompiles the expression from those bytes (the reconstruction
rule) and trains with Carbon's code, in JAX. Nothing the strategy supplied is
executed.

**Level 0 is untouched.** The program is Level 0's GPU practice program with
its one build line replaced. A Level-0 trial's program, staged files and
recipe digest are byte for byte what they were: `recipes.py` and
`training.py` (battery's implementation modules, whose bytes enter every
Level-0 recipe digest) are not changed, and the Level-1 trainer is a module
of its own. This module does not import the development-variant module (the
validator package imports it through `battery_scoring`).
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.battery.loss_terms import REBUILD_LABEL

#: The loss-expression record key in a development construction's
#: reconstruction (`development_variants.CompiledDevelopment.reconstruction`).
CAPABILITY = "objective.loss_expressions"
EXPRESSION_FILE = "loss-expression.json"
OPERATION_SET_FILE = "loss-operation-set.json"
STAGED_MODULES = {
    "battery-loss-expressions.py": ("reconstruction", "loss_expressions.py"),
    "battery-loss-terms.py": ("battery", "loss_terms.py"),
    "battery-level1-training.py": ("battery", "level1_training.py"),
}
_BUILD = 'model = recipes.build(recipe["family"], recipe["settings"])\n'
_LEVEL1_BUILD = r"""for staged, module in (
    ("battery-loss-expressions.py", "loss_expressions.py"),
    ("battery-loss-terms.py", "loss_terms.py"),
    ("battery-level1-training.py", "level1_training.py"),
):
    shutil.copyfile(work / staged, lab / module)
from carbon_battery_lab import level1_training, loss_expressions, loss_terms  # noqa: E402

compiled = loss_terms.load(
    loss_expressions,
    (work / "loss-expression.json").read_bytes(),
    json.loads((work / "loss-operation-set.json").read_text()),
)
model = level1_training.build(
    recipe["family"],
    recipe["settings"],
    loss_terms.factory(loss_expressions, compiled),
)
"""


def _program():
    from carbon.development_session.battery_gpu import GPU_PROGRAM

    if GPU_PROGRAM.count(_BUILD) != 1:
        raise RuntimeError("the practice program's build line moved")
    return GPU_PROGRAM.replace(_BUILD, _LEVEL1_BUILD)


def program():
    """The Level-1 practice program."""
    return _program()


def build_in_process(recipe, record):
    """The untrained Level-1 model for a compiled recipe and its pinned
    loss-expression record, built in this process the way the staged program
    builds it: the expression recompiled from its canonical bytes against its
    operation set, then Carbon's Level-1 trainer. Nothing the strategy
    supplied is executed."""
    from carbon.battery import level1_training, loss_terms
    from carbon.reconstruction import loss_expressions

    compiled = loss_terms.load(
        loss_expressions,
        record["canonical"].encode("utf-8"),
        record["operation_set_document"],
    )
    return level1_training.build(
        recipe.family,
        recipe.settings,
        loss_terms.factory(loss_expressions, compiled),
    )


def expression_record(reconstruction):
    """The loss-expression reconstruction record of a development
    construction, or None (Level 0, or a variant without it)."""
    if type(reconstruction) is not dict:
        return None
    return reconstruction.get(CAPABILITY)


def staged(record):
    """The extra files a Level-1 trial stages, by name."""
    carbon = Path(__file__).resolve().parents[1]
    files = {
        name: (carbon / folder / module).read_bytes()
        for name, (folder, module) in STAGED_MODULES.items()
    }
    files[EXPRESSION_FILE] = record["canonical"].encode("utf-8")
    files[OPERATION_SET_FILE] = json.dumps(
        record["operation_set_document"],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return files


__all__ = [
    "CAPABILITY",
    "EXPRESSION_FILE",
    "OPERATION_SET_FILE",
    "REBUILD_LABEL",
    "build_in_process",
    "expression_record",
    "program",
    "staged",
]
