"""Compile a motor strategy into the exact Level-0 recipe Carbon rebuilds.

The kernel ridge is a deterministic closed-form fit; the neural families
(`neural`, MOTOR-NEURAL-01) train with Carbon's reconstruction seed."""

from __future__ import annotations

from dataclasses import dataclass

from carbon.construction.compiler import CompileAccepted
from carbon.construction.model import SelectedSurface
from carbon.development_session.research_catalog import RecipeRejected

from .challenge import CHALLENGE, PublicMaterial
from .contracts import canonical, digest, motor_contracts
from .recipes import build

NEURAL_FAMILIES = ("mlp", "deeponet")

LENGTH_VALUES = {
    "length_0p25": 0.25,
    "length_0p5": 0.5,
    "length_1": 1.0,
    "length_2": 2.0,
    "length_4": 4.0,
    "length_8": 8.0,
    "length_16": 16.0,
}
RIDGE_VALUES = {
    "ridge_1e_8": 1e-8,
    "ridge_1e_6": 1e-6,
    "ridge_1e_4": 1e-4,
    "ridge_1e_2": 1e-2,
    "ridge_1e_1": 1e-1,
    "ridge_1": 1.0,
}

#: Each neural surface's token -> the value Carbon trains with.
NEURAL_VALUES = {
    "width": {"width_64": 64, "width_128": 128, "width_256": 256},
    "depth": {"depth_2": 2, "depth_3": 3, "depth_4": 4},
    "steps": {
        "steps_500": 500,
        "steps_1000": 1000,
        "steps_2000": 2000,
        "steps_4000": 4000,
    },
    "learning_rate": {
        "lr_5e_4": 0.0005,
        "lr_1e_3": 0.001,
        "lr_2e_3": 0.002,
        "lr_5e_3": 0.005,
    },
    "basis_functions": {"basis_8": 8, "basis_16": 16, "basis_32": 32},
    "activation": {name: name for name in ("gelu", "tanh", "silu")},
    "backend": {name: name for name in ("jax", "pytorch")},
}

_COMPILED = object()


@dataclass(frozen=True)
class MotorRecipe:
    family: str
    values: tuple[tuple[str, object], ...]
    supplied: frozenset[str]
    strategy_hash: str
    plan_digest: str
    token: object = None

    def __post_init__(self):
        if self.token is not _COMPILED:
            raise TypeError("a MotorRecipe comes only from compile_recipe")

    @property
    def settings(self):
        return dict(self.values)

    def document(self):
        return {
            "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
            "family": self.family,
            "settings": self.settings,
            "strategy_hash": self.strategy_hash,
            "plan_digest": self.plan_digest,
        }

    @property
    def recipe_digest(self):
        return digest(canonical(self.document()))


def compile_recipe(strategy, *, contracts=None):
    """Compile through the shared B-02B contract or raise `RecipeRejected`."""

    compiled = (motor_contracts() if contracts is None else contracts).compile(strategy)
    if type(compiled) is not CompileAccepted:
        raise RecipeRejected(compiled)
    plan = compiled.construction_plan
    family = None
    values = {}
    for surface in plan.resolved_surfaces:
        if not hasattr(surface, "value"):
            continue
        if surface.surface_id == "strategy_backbone":
            family = surface.value.value
        else:
            values[surface.surface_id] = surface.value.value
    supplied = frozenset(
        surface.surface_id
        for surface in plan.resolved_surfaces
        if type(surface) is SelectedSurface
        and surface.surface_id != "strategy_backbone"
    )
    if family in NEURAL_FAMILIES:
        values = {name: NEURAL_VALUES[name][token] for name, token in values.items()}
    else:
        values = {
            "length": LENGTH_VALUES[values["length"]],
            "ridge": RIDGE_VALUES[values["ridge"]],
        }
    recipe = MotorRecipe(
        family,
        tuple(sorted(values.items())),
        supplied,
        plan.strategy_hash.value,
        plan.to_ref().content_digest,
        _COMPILED,
    )
    return compiled, recipe


def rebuild(recipe, material=None, *, root=".", seed=None):
    """Fit on the verified public TRAIN records: the kernel ridge
    deterministically, a neural family with `seed`, Carbon's reconstruction
    randomness (required; the kernel ridge takes none)."""

    if type(recipe) is not MotorRecipe:
        raise TypeError("a compiled MotorRecipe is required")
    material = PublicMaterial.load(root) if material is None else material
    if type(material) is not PublicMaterial:
        raise TypeError("verified Motor PublicMaterial is required")
    if recipe.family in NEURAL_FAMILIES:
        from . import neural

        return neural.build(recipe.family, recipe.settings, material.train, seed)[0]
    if seed is not None:
        raise ValueError("the kernel ridge takes no reconstruction seed")
    return build(recipe.family, recipe.settings, material.train)
