"""Disclosed-score gamer on analytic toy; true buyer value is measured later.

Every disclosure setting is an assumption, not a claim about Launchpad's
actual feedback or a Challenge's registered question law.
"""

from __future__ import annotations

from . import campaign_goodhart, feedback
from .core import LabRefused


def run(
    config,
    candidate_id,
    spec,
    *,
    candidates_sha256,
    search,
    disclosure,
    component_spec=None,
):
    """Sweep score grain, rounding and probe count without exposing value."""
    campaign_goodhart.validate(config, search)
    if not isinstance(disclosure, dict):
        raise LabRefused("feedback_disclosure_spec")
    initial = disclosure.get("initial")
    if not isinstance(initial, dict) or set(initial) != set(search["parameters"]):
        raise LabRefused("feedback_initial_traits")
    grains = disclosure.get("grains")
    if (
        not isinstance(grains, list)
        or not grains
        or any(
            grain != "aggregate"
            and (
                not isinstance(grain, str)
                or not grain.startswith("prefix:")
                or not grain[7:].isdigit()
            )
            for grain in grains
        )
    ):
        raise LabRefused("feedback_disclosure_grain")
    bounds = {name: tuple(values[:2]) for name, values in search["parameters"].items()}
    step = {name: values[2] for name, values in search["parameters"].items()}
    experiment = campaign_goodhart.ToyTraitEvaluator(
        config,
        candidate_id,
        spec,
        candidates_sha256=candidates_sha256,
        search=search,
        component_spec=component_spec,
    )

    def disclosed_score(parameters, grain):
        rank = experiment.score(parameters, grain)
        if rank is None or rank[0] != 0:
            raise LabRefused("feedback_probe_unscored")
        return rank[1]

    rows = feedback.sweep(
        disclosed_score,
        experiment.value_loss,
        initial=initial,
        bounds=bounds,
        step=step,
        grains=grains,
        roundings=disclosure.get("roundings"),
        probe_allowances=disclosure.get("probe_allowances"),
        epochs=disclosure.get("epochs"),
    )
    return {
        **campaign_goodhart.receipt_identity(
            config,
            search,
            candidates_sha256=candidates_sha256,
            candidate_ids=[candidate_id],
            component_spec=component_spec,
            disclosure=disclosure,
        ),
        "status": "MEASURED_SYNTHETIC_DEVELOPMENT",
        "candidate": candidate_id,
        "value_scope": search["value_scope"],
        "disclosure_kind": "TOY_AGGREGATE_OR_SCORE_QUESTION_PREFIX",
        "rows": rows,
        "calls": experiment.calls,
        "unique_toy_panels": len(experiment.cache),
    }
