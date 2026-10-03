"""Battery's declaration for the research surface (RSURF-D8).

Read entirely from what battery already publishes:
- the outputs and their units, from the public objective's I/O description,
  with the trajectory grid and capacity checkpoints the Challenge defines;
- the four aggregate practice components, from the exam;
- whether per-case public practice curves may be drawn, from the practice
  population's own disclosure contract (RSURF-D2);
- what each feedback mode shows of an evaluation outcome, from the campaign's
  leak ladder (RSURF-D4).

The references named here are the pinned public PRACTICE references only.
Nothing here reads a private pool, a seed or an evaluation case.
"""

from __future__ import annotations

import functools
from pathlib import Path

from carbon.challenge_registry.research_view import (
    Axis,
    OutputSpec,
    ResearchView,
    per_case_policy,
)

REPOSITORY = Path(__file__).resolve().parents[2]
#: Short labels for the outputs; units and shapes come from the objective.
LABELS = {
    "voltage_v": "Voltage",
    "temperature_c": "Temperature",
    "plating_margin_v": "Plating margin (cycle 1 minimum)",
    "capacity_ah": "Capacity at checkpoints",
}
LEARNING_CURVE = {
    "recorded": True,
    "basis": (
        "Practice on trainer v2 records up to 64 points of the trainer's own "
        "loss on TRAIN data (RSURF-D3). Runs before trainer v2, "
        "k-nearest-neighbour recipes, which do not train, and an L-BFGS polish "
        "have none."
    ),
}


def _outputs():
    from .challenge import GRID_STEP_S, WINDOW_S
    from .research import objective

    grid = Axis("time", "s", tuple(range(0, WINDOW_S + 1, GRID_STEP_S)))
    found = []
    for name, spec in objective()["outputs"].items():
        label = LABELS.get(name, name.replace("_", " "))
        if not spec["shape"]:
            found.append(OutputSpec(name, "scalar", spec["unit"], label))
        elif "cycles" in spec:
            axis = Axis("cycle", None, tuple(spec["cycles"]))
            found.append(
                OutputSpec(name, "checkpoint_vector", spec["unit"], label, (axis,))
            )
        else:
            if spec["shape"] != [len(grid.values)]:
                raise ValueError(f"{name}: the trajectory grid differs")
            found.append(OutputSpec(name, "time_series", spec["unit"], label, (grid,)))
    return tuple(found)


@functools.lru_cache(maxsize=1)
def _practice(root):
    from .practice import PracticeSet

    return PracticeSet.load(root)


def _feedback_fields(mode):
    from .campaign import (
        _SCREENING_FIELDS,
        _WITHHELD_OUTCOME_FIELDS,
        FEEDBACK_FULL,
    )
    from .research import EVALUATION_FEEDBACK_FIELDS, SCREENING_FEEDBACK_FIELDS

    if mode == FEEDBACK_FULL:
        return tuple(EVALUATION_FEEDBACK_FIELDS), tuple(SCREENING_FEEDBACK_FIELDS)
    if mode in _SCREENING_FIELDS:
        return tuple(_WITHHELD_OUTCOME_FIELDS), tuple(_SCREENING_FIELDS[mode])
    return None


def research_view(root=REPOSITORY):
    from .challenge import CHALLENGE, INPUTS
    from .exam import COMPONENTS
    from .research import population_and_sampling

    population, _ = population_and_sampling()
    root = Path(root)

    def case_ids():
        return list(_practice(root).case_ids)

    def reference(case_id):
        for record in _practice(root).records:
            if record["case_id"] == case_id:
                return {
                    "inputs": {k: record["inputs"][k] for k in INPUTS},
                    "outputs": record["outputs"],
                }
        return None

    return ResearchView(
        challenge_id=CHALLENGE.challenge_id,
        outputs=_outputs(),
        components=tuple((c, c.capitalize()) for c in COMPONENTS),
        direction="lower_is_better",
        per_case=per_case_policy(population.disclosure_contract),
        learning_curve=dict(LEARNING_CURVE),
        case_ids=case_ids,
        reference=reference,
        feedback_fields=_feedback_fields,
        prediction_file="predictions.json",
        inputs=tuple(INPUTS),
    )
