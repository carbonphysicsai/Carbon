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

from .challenge import CHALLENGE, TRAIN_V1_CASES
from .contracts import battery_contracts, canonical, digest
from .recipes import Structure, build

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


#: The optimizer hyperparameters each optimizer family consumes.
USES = {
    "adam": {"beta1", "beta2", "adam_epsilon"},
    "lion": {"beta1", "beta2"},
    "lamb": {"beta1", "beta2", "adam_epsilon"},
    "adafactor": set(),
    "radam": {"beta1", "beta2", "adam_epsilon"},
    "nadamw": {"beta1", "beta2", "adam_epsilon"},
    "sgd_momentum": {"beta1"},
    "muon": {"beta1", "adam_epsilon"},
    "prodigy": {"beta1", "beta2", "adam_epsilon"},
    "free_adamw": {"beta1", "beta2", "adam_epsilon"},
    "sam": {"beta1", "beta2", "adam_epsilon"},
}
#: Curves whose final rate `min_learning_rate_ratio` sets.
FLOORED = {"cosine", "exponential", "polynomial"}


def rebuild_issues(family, values, supplied):
    """Backend rules beyond B-02B's closed tables, each naming its field.

    A supplied field must change what Carbon rebuilds; one the rest of the
    recipe would ignore is refused by name, never silently accepted.
    """
    issues = []

    def refuse(code, field):
        issues.append(_issue(code, field))

    if family == "knn":
        return ()
    v = values
    members = v["ensemble_members"]
    # Members split the step budget exactly; a remainder would be dropped.
    if v["steps"] % members:
        refuse("parameter.dependency_unsatisfied", "ensemble_members")
        return tuple(issues)
    member_steps = v["steps"] // members
    main = member_steps - v["polish_steps"]
    if member_steps < MIN_MEMBER_STEPS:
        refuse("parameter.dependency_unsatisfied", "steps")
    elif main < MIN_MEMBER_STEPS:
        refuse("parameter.dependency_unsatisfied", "polish_steps")
    if v["warmup_steps"] and v["warmup_steps"] >= main:
        refuse("parameter.dependency_unsatisfied", "warmup_steps")
    optimizer, curve = v["optimizer_family"], v["learning_rate_curve"]
    for field in sorted({"beta1", "beta2", "adam_epsilon"} - USES[optimizer]):
        if field in supplied:
            refuse("parameter.dependency_unsatisfied", field)
    if "min_learning_rate_ratio" in supplied and curve not in FLOORED:
        refuse("parameter.dependency_unsatisfied", "min_learning_rate_ratio")
    if "warmup_steps" in supplied and curve == "one_cycle":
        refuse("parameter.dependency_unsatisfied", "warmup_steps")
    if "learning_rate_curve" in supplied and optimizer == "free_adamw":
        refuse("parameter.dependency_unsatisfied", "learning_rate_curve")
    # SAM alternates adversarial and true updates; a TRAIN-loss plateau
    # measured across both is not a plateau of the model being trained.
    if optimizer == "sam" and curve == "train_loss_plateau":
        refuse("parameter.dependency_unsatisfied", "learning_rate_curve")
    if "weight_decay_mask" in supplied and v["weight_decay"] == 0:
        refuse("parameter.dependency_unsatisfied", "weight_decay_mask")
    ema = v["inference_weights"] == "ema"
    if "ema_decay" in supplied and not ema:
        refuse("parameter.dependency_unsatisfied", "ema_decay")
    if v["tail_averaging"] and ema:
        refuse("parameter.dependency_unsatisfied", "tail_averaging")
    # SAM's adversarial updates and schedule-free's evaluation point are not
    # the iterates an average should see.
    if optimizer in ("sam", "free_adamw") and (ema or v["tail_averaging"]):
        refuse(
            "parameter.dependency_unsatisfied",
            "inference_weights" if ema else "tail_averaging",
        )
    cases = int(TRAIN_V1_CASES * v["train_fraction"])
    if "batch_size" in supplied and v["batch_size"] > cases:
        refuse("parameter.domain_mismatch", "batch_size")
    if min(v["batch_size"], cases) % v["microbatches"]:
        refuse("parameter.dependency_unsatisfied", "microbatches")
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
    issues = rebuild_issues(family, values, supplied)
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
    return build(recipe.family, recipe.settings)


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
