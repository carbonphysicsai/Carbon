"""A direct-recipe version's public-practice declaration for the research view.

Its outputs are the registered interface's names and units, one scalar each.
Its components are the practice summary's aggregate errors on the registered
scale (`practice.error_scale`; Validator, 2026-10-21), lower is better; per-case
detail follows the practice population's disclosure contract, which makes no
label public, so only aggregates are shown and no public reference is named.
"""

from __future__ import annotations

from carbon.challenge_registry.research_view import (
    OutputSpec,
    ResearchView,
    per_case_policy,
)

from .practice import COMPONENTS
from .spec import HUMAN_INPUT, research_key

#: Each summary component's label.
LABELS = {
    "mean": "Mean error",
    "near_mean": "Near-limit mean error",
    "worst": "Worst error",
    "margin_mean": "Margin mean error",
    "margin_worst": "Margin worst error",
    "resonance_mean": "Resonance mean error",
    "resonance_worst": "Resonance worst error",
}


def research_view(spec):
    from .contracts import interface_document
    from .research import population_and_sampling

    research_key(spec)
    interface = interface_document(spec)
    population, _ = population_and_sampling(spec)
    outputs = tuple(
        OutputSpec(name, "scalar", unit, name, ())
        for name, unit in zip(
            interface["output"]["names"], interface["output"]["units"], strict=True
        )
    )
    return ResearchView(
        challenge_id=spec.challenge_id,
        outputs=outputs,
        components=tuple((key, LABELS[key]) for key in COMPONENTS[spec.prefix]),
        direction="lower_is_better",
        per_case=per_case_policy(population.disclosure_contract),
        learning_curve={"recorded": False, "basis": HUMAN_INPUT},
        case_ids=None,
        reference=None,
        feedback_fields=lambda mode: None,
        prediction_file="predictions.json",
        inputs=tuple(interface["input"]["names"]),
    )
