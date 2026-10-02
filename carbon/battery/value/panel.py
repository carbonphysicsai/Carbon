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


#: EV2 adds recipe families that differ in more than their seed (EV1 finding:
#: seeds are repetitions of one recipe). EV1's panel is unchanged.
EV2_RECIPES = (
    (
        "deeponet",
        _strategy("deeponet", {"steps": 6000, "width": 256, "deeponet_depth": 3}),
        (0, 1),
    ),
    ("mlp_wide", _strategy("mlp", {"steps": 6000, "width": 512, "depth": 2}), (0,)),
    ("knn15", _strategy("knn", {"neighbours": 15}), (0,)),
)


def _mlp(steps, width, depth, **extra):
    return _strategy("mlp", {"steps": steps, "width": width, "depth": depth, **extra})


def _label(prefix, steps, width, depth):
    return f"{prefix}_t{steps}_w{width}_d{depth}"


#: EV4 (owner approval 2026-10-01): a 100-member panel built to separate
#: decision quality. EV2's 15 members keep their ids; 85 are added: 70
#: distinct recipes and 15 second seeds of added recipes. A label encodes its
#: recipe, so a member id names what was rebuilt. Training budget, width,
#: depth, data fraction and regularization vary on purpose, so that decision
#: losses spread instead of tying. Every recipe compiles
#: (`test_every_ev4_recipe_compiles`).
_EV4_MLP_GRID = tuple(
    (_label("mlp", steps, width, depth), _mlp(steps, width, depth), (0,))
    for steps in (500, 1500, 3000, 6000)
    for width in (64, 128, 256, 512)
    for depth in (2, 3)
    # EV2's `mlp` (6000, 256, 3) and `mlp_wide` (6000, 512, 2) are these.
    if (steps, width, depth) not in ((6000, 256, 3), (6000, 512, 2))
)
_EV4_TRAIN_FRACTION = tuple(
    (
        f"{_label('mlp', s, w, dd)}_f{round(f * 100)}",
        _mlp(s, w, dd, train_fraction=f),
        (0,),
    )
    for s, w, dd, f in (
        (6000, 256, 3, 0.25),
        (3000, 256, 3, 0.25),
        (3000, 256, 3, 0.5),
        (1500, 128, 2, 0.25),
        (1500, 128, 2, 0.5),
        (6000, 512, 2, 0.25),
        (6000, 512, 2, 0.5),
        (500, 128, 3, 0.5),
        (3000, 512, 3, 0.25),
    )
)
_EV4_WEIGHT_DECAY = tuple(
    (f"{_label('mlp', s, w, dd)}_wd{tag}", _mlp(s, w, dd, weight_decay=wd), (0,))
    for s, w, dd, wd, tag in (
        (6000, 256, 3, 1e-5, "1em5"),
        (6000, 256, 3, 1e-3, "1em3"),
        (1500, 128, 3, 1e-4, "1em4"),
        (3000, 512, 2, 1e-4, "1em4"),
    )
)
_EV4_FEATURES = (
    ("mlp_t6000_w256_d3_arr", _mlp(6000, 256, 3, arrhenius_features=True), (0,)),
    (
        "mlp_t3000_w256_d3_arr_pca16",
        _mlp(3000, 256, 3, arrhenius_features=True, trajectory_components=16),
        (0,),
    ),
    ("mlp_t6000_w256_d3_pca8", _mlp(6000, 256, 3, trajectory_components=8), (0,)),
    ("mlp_t1500_w256_d2_arr", _mlp(1500, 256, 2, arrhenius_features=True), (0,)),
)
_EV4_IMPORTANT_REGION = tuple(
    (
        f"{_label('mlp', s, w, dd)}_irw{tag}",
        _mlp(s, w, dd, important_region_weight=x),
        (0,),
    )
    for s, w, dd, x, tag in (
        (6000, 256, 3, 0.03, "003"),
        (6000, 256, 3, 0.3, "03"),
        (6000, 256, 3, 3.0, "3"),
        (3000, 128, 2, 0.1, "01"),
    )
)
_EV4_ENSEMBLES = tuple(
    (f"{_label('mlp', s, w, dd)}_ens{n}", _mlp(s, w, dd, ensemble_members=n), (0,))
    for s, w, dd, n in ((6000, 256, 3, 2), (6000, 256, 3, 4), (3000, 128, 2, 3))
)
_EV4_DEEPONET = tuple(
    (
        f"deeponet_t{s}_w{w}_d{dd}",
        _strategy("deeponet", {"steps": s, "width": w, "deeponet_depth": dd}),
        (0,),
    )
    for s, w, dd in (
        (500, 128, 2),
        (1500, 128, 2),
        (1500, 256, 3),
        (1500, 512, 3),
        (3000, 128, 3),
        (3000, 256, 2),
        (3000, 512, 3),
        (6000, 128, 2),
        (6000, 256, 2),
        (6000, 512, 2),
        (6000, 512, 3),
    )
)
#: kNN over the neighbour count (EV1/EV2 hold 5 and 15).
_EV4_KNN = tuple(
    (f"knn{k}", _strategy("knn", {"neighbours": k}), (0,)) for k in (1, 3, 10, 25, 40)
)
#: Second seeds: repetitions of added recipes, never separate families. They
#: give the seed-to-seed loss band the divergence detector reads.
EV4_SEED_REPEATS = (
    "mlp_t500_w64_d2",
    "mlp_t500_w256_d3",
    "mlp_t1500_w128_d3",
    "mlp_t1500_w512_d2",
    "mlp_t3000_w64_d3",
    "mlp_t3000_w256_d2",
    "mlp_t6000_w64_d2",
    "mlp_t6000_w128_d3",
    "mlp_t6000_w512_d3",
    "mlp_t3000_w256_d3_f25",
    "mlp_t6000_w256_d3_wd1em3",
    "mlp_t6000_w256_d3_irw03",
    "deeponet_t1500_w256_d3",
    "deeponet_t3000_w256_d2",
    "deeponet_t6000_w512_d3",
)
EV4_RECIPES = tuple(
    (label, strategy, (0, 1) if label in EV4_SEED_REPEATS else seeds)
    for label, strategy, seeds in (
        _EV4_MLP_GRID
        + _EV4_TRAIN_FRACTION
        + _EV4_WEIGHT_DECAY
        + _EV4_FEATURES
        + _EV4_IMPORTANT_REGION
        + _EV4_ENSEMBLES
        + _EV4_DEEPONET
        + _EV4_KNN
    )
)
PANELS = {
    "ev1": RECIPES,
    "ev2": RECIPES + EV2_RECIPES,
    "ev4": RECIPES + EV2_RECIPES + EV4_RECIPES,
}


def family(strategy):
    """A member's architecture family (its backbone): mlp, deeponet or knn."""
    return strategy["backbone"]


def members(panel="ev1"):
    """Every reconstructed panel member: (member id, family, strategy, seed)."""
    return [
        (f"{family}-s{seed}", family, strategy, seed)
        for family, strategy, seeds in PANELS[panel]
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
