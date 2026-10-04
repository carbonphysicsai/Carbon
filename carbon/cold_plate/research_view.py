"""Cooling's public-practice declaration for the Challenge research view."""

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


def _outputs():
    from .domain import PROFILE_SEGMENTS

    axial = Axis("axial_segment", None, tuple(range(PROFILE_SEGMENTS)))
    return (
        OutputSpec("peak_c", "scalar", "degC", "Peak heated-face temperature"),
        OutputSpec(
            "profile_c",
            "time_series",
            "degC",
            "Axial heated-face temperature",
            (axial,),
        ),
        OutputSpec("pressure_drop_pa", "scalar", "Pa", "Pressure drop"),
    )


@functools.lru_cache(maxsize=1)
def _practice(root):
    from .practice import PracticeSet

    return PracticeSet.load(root)


def research_view(root=REPOSITORY):
    from .challenge import CHALLENGE
    from .domain import INPUTS
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
                    "inputs": {name: record["inputs"][name] for name in INPUTS},
                    "outputs": record["outputs"],
                }
        return None

    return ResearchView(
        challenge_id=CHALLENGE.challenge_id,
        outputs=_outputs(),
        components=tuple((name, name.capitalize()) for name in COMPONENTS),
        direction="lower_is_better",
        per_case=per_case_policy(population.disclosure_contract),
        learning_curve={
            "recorded": False,
            "basis": "The registered kernel-ridge fit is a closed-form solve.",
        },
        case_ids=case_ids,
        reference=reference,
        feedback_fields=lambda mode: None,
        prediction_file="predictions.json",
        inputs=tuple(INPUTS),
    )
