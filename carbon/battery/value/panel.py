"""The model panel: reconstructed campaign recipes and labelled controls.

**Reconstructed members.** These are the exam-design campaign's recipes,
which Carbon's construction contract reproduces bit for bit
(`test_promoted_recipes_match_the_campaign_recipes_bit_for_bit`). The
campaign kept only weight digests, not weights, so each member is rebuilt
from its recipe on public TRAIN v1 with its declared seed. Seeds are
repetitions of one recipe, never separate families.

They cover the patterns the experiment needs:
- strong overall (mlp, mlp_ens3);
- weak overall (knn);
- localized weighting (mlp_localized);
- less data (mlp_half);
- a different feature path (mlp_plus);
- a gate-failing head (mlp_raw).

**Synthetic controls.** These are built from the reference answers
themselves, to test specific scoring failure modes. They are scoring tests,
not miner submissions, and not evidence of achievable model performance.
Their kind is always `SYNTHETIC_CONTROL`.
"""

from __future__ import annotations

import copy

CHALLENGE_ID = "battery-fastcharge-ageing-development-v1"
MLP = {"steps": 6000, "width": 256, "depth": 3}


def _strategy(backbone, parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE_ID,
        "backbone": backbone,
        "parameters": parameters,
    }


RECIPES = (
    ("knn", _strategy("knn", {"neighbours": 5}), (0,)),
    ("mlp", _strategy("mlp", dict(MLP)), (0, 1, 2)),
    ("mlp_half", _strategy("mlp", {**MLP, "train_fraction": 0.5}), (0, 1)),
    (
        "mlp_plus",
        _strategy(
            "mlp",
            {
                **MLP,
                "weight_decay": 1e-4,
                "arrhenius_features": True,
                "trajectory_components": 16,
            },
        ),
        (0,),
    ),
    (
        "mlp_localized",
        _strategy("mlp", {**MLP, "important_region_weight": 0.1}),
        (0, 1),
    ),
    ("mlp_raw", _strategy("mlp", {**MLP, "bounded_voltage_head": False}), (0,)),
    ("mlp_ens3", _strategy("mlp", {**MLP, "ensemble_members": 3}), (0,)),
)


def members():
    """Every reconstructed panel member: (member id, family, strategy, seed)."""
    return [
        (f"{family}-s{seed}", family, strategy, seed)
        for family, strategy, seeds in RECIPES
        for seed in seeds
    ]


def _shift_voltage_late(outputs, steps=1):
    """Delay the whole voltage trajectory by `steps` grid points."""
    v = list(outputs["voltage_v"])
    return [v[0]] * steps + v[:-steps]


def _after_start(values, delta):
    """Shift a trajectory after t = 0: the initial value is fixed by the
    declared structure (T(0) = ambient), as it is for every real model."""
    return [values[0]] + [v + delta for v in values[1:]]


def _control(kind, outputs):
    out = copy.deepcopy(outputs)
    margin = out["plating_margin_v"]
    temperatures = out["temperature_c"]
    peak = max(temperatures)
    if kind == "oracle":
        return out
    if kind == "conservative":
        # Predicts every protocol as harsher than it is.
        out["plating_margin_v"] = margin - 0.010
        out["temperature_c"] = _after_start(temperatures, +2.0)
        return out
    if kind == "boundary_optimist":
        # Accurate almost everywhere, optimistic exactly near the limits.
        if -0.012 < margin < 0.003:
            out["plating_margin_v"] = margin + 0.012
        if 44.0 < peak < 48.5:
            out["temperature_c"] = _after_start(temperatures, -3.5)
        return out
    if kind == "rank_preserving_delay":
        # Imperfect absolute voltage timing, same design ranking.
        out["voltage_v"] = _shift_voltage_late(out)
        return out
    if kind == "localized_sign_error":
        # Wrong only in the published important plating band.
        if abs(margin) <= 0.005:
            out["plating_margin_v"] = -margin
        return out
    raise ValueError("unknown control")


CONTROLS = (
    "oracle",
    "conservative",
    "boundary_optimist",
    "rank_preserving_delay",
    "localized_sign_error",
)


def control_predictions(kind, references):
    """A control's predictions for every case with an OK reference."""
    return {
        case_id: _control(kind, record["outputs"])
        for case_id, record in references.items()
        if record.get("status") == "OK"
    }
