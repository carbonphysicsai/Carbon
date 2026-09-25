"""Compile a battery strategy into the exact recipe Carbon rebuilds.

B-02B resolves the strategy against the battery catalog; the backend rules
B-02B's finite tables cannot express are named here. A `BatteryRecipe` exists
only as the output of `compile_recipe`: its constructor refuses to be called
without the module's compile token, so a raw dictionary of valid values is
still refused.
"""

from __future__ import annotations

from dataclasses import dataclass

from carbon.construction.compiler import CompileAccepted, CompileRejected
from carbon.construction.model import SelectedSurface
from carbon.development_session.research_catalog import RecipeRejected, _issue

from .challenge import CHALLENGE
from .contracts import battery_contracts, canonical, digest
from .recipes import KNN, MLP, Ensemble, Structure

_COMPILED = object()
MIN_MEMBER_STEPS = 16


@dataclass(frozen=True)
class BatteryRecipe:
    family: str
    values: tuple[tuple[str, object], ...]
    supplied: frozenset[str]
    strategy_hash: str
    plan_digest: str
    token: object = None

    def __post_init__(self):
        if self.token is not _COMPILED:
            raise TypeError("a BatteryRecipe comes only from compile_recipe")

    @property
    def settings(self):
        return dict(self.values)

    def document(self):
        """The canonical design Carbon rebuilds, as plain JSON data."""
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


def rebuild_issues(family, values):
    """Backend rules beyond B-02B's closed tables, each naming its field.

    Every battery surface changes what is rebuilt at every value in its range,
    so no supplied field can be silently ignored; only the ensemble's split of
    the step budget needs a rule.
    """
    issues = []
    if family == "mlp":
        members = values["ensemble_members"]
        # Members split the step budget exactly; a remainder would be dropped.
        if values["steps"] % members:
            issues.append(
                _issue("parameter.dependency_unsatisfied", "ensemble_members")
            )
        elif values["steps"] // members < MIN_MEMBER_STEPS:
            issues.append(_issue("parameter.dependency_unsatisfied", "steps"))
    return tuple(issues)


def compile_recipe(strategy, *, contracts=None):
    """Raises `RecipeRejected`, carrying every named issue."""
    compiled = (battery_contracts() if contracts is None else contracts).compile(
        strategy
    )
    if type(compiled) is not CompileAccepted:
        raise RecipeRejected(compiled)
    plan = compiled.construction_plan
    values = {}
    family = None
    for surface in plan.resolved_surfaces:
        if not hasattr(surface, "value"):
            continue  # not applicable to the selected family
        if surface.surface_id == "strategy_backbone":
            family = surface.value.value
        else:
            values[surface.surface_id] = surface.value.value
    supplied = frozenset(
        s.surface_id
        for s in plan.resolved_surfaces
        if type(s) is SelectedSurface and s.surface_id != "strategy_backbone"
    )
    issues = rebuild_issues(family, values)
    if issues:
        raise RecipeRejected(CompileRejected(issues))
    recipe = BatteryRecipe(
        family,
        tuple(sorted(values.items())),
        supplied,
        plan.strategy_hash.value,
        plan.to_ref().content_digest,
        _COMPILED,
    )
    return compiled, recipe


def build_model(recipe):
    if type(recipe) is not BatteryRecipe:
        raise TypeError("a compiled BatteryRecipe is required")
    s = recipe.settings
    if recipe.family == "knn":
        return KNN(s["neighbours"])
    member = {
        k: s[k]
        for k in (
            "width",
            "depth",
            "steps",
            "learning_rate",
            "weight_decay",
            "arrhenius_features",
            "trajectory_components",
            "bounded_voltage_head",
            "ocv_initial_voltage",
            "capacity_fade_head",
        )
    }
    if s["ensemble_members"] == 1:
        return MLP(**member)
    return Ensemble(s["ensemble_members"], **member)


def rebuild(recipe, material, seed, *, train=None):
    """Train a fresh model from the recipe on pinned public TRAIN v1.

    `seed` is Carbon's reconstruction randomness. `train` narrows TRAIN for
    bounded tests and diagnostics; a validator rebuild uses the full set.
    """
    if type(seed) is not int or seed < 0:
        raise ValueError("a non-negative integer reconstruction seed is required")
    model = build_model(recipe)
    structure = Structure(material.ocv_soc, material.ocv_v)
    stats = model.fit(material.train if train is None else train, structure, seed)
    return model, stats
