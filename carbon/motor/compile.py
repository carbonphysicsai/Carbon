"""Compile a motor strategy into the exact Level-0 recipe Carbon rebuilds."""

from __future__ import annotations

from dataclasses import dataclass

from carbon.construction.compiler import CompileAccepted
from carbon.construction.model import SelectedSurface
from carbon.development_session.research_catalog import RecipeRejected

from .challenge import CHALLENGE, PublicMaterial
from .contracts import canonical, digest, motor_contracts
from .recipes import build

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


def rebuild(recipe, material=None, *, root="."):
    """Deterministically fit on the verified public TRAIN records."""

    if type(recipe) is not MotorRecipe:
        raise TypeError("a compiled MotorRecipe is required")
    material = PublicMaterial.load(root) if material is None else material
    if type(material) is not PublicMaterial:
        raise TypeError("verified Motor PublicMaterial is required")
    return build(recipe.family, recipe.settings, material.train)
