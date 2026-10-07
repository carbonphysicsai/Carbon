"""Battery's training budget adapter (TRAINING-BUDGET-01).

The battery instance of `carbon.training_budget.adapter.ChallengeAdapter`.
Everything here is read from battery's existing records. The shared study,
cost calculator and capacity calculation never import battery by name; they
find this adapter through `carbon/training_budget/adapters.json`.
"""

from __future__ import annotations

from functools import cached_property

import numpy as np

CHALLENGE = "battery-fastcharge-ageing-development-v1"


def _leaf_count(tree):
    import jax

    return int(sum(np.size(leaf) for leaf in jax.tree_util.tree_leaves(tree)))


class BatteryAdapter:
    challenge_id = CHALLENGE
    #: Named record items (`module:attribute`), resolved on demand.
    records = {
        "worker": "carbon.battery.compile:rebuild",
        "exam": "carbon.battery.exam:evaluate",
        "equivalence_margin": "carbon.battery.exam:ComparisonRule",
        "finalist_rule": "carbon.battery.exam:final_compare",
        "generator": "carbon.battery.truth:TruthService",
        "panel": "carbon.battery.admission_study:pins",
    }

    def __init__(self, root="."):
        self.root = root

    def contract(self):
        from carbon.reconstruction import capability_registry

        return capability_registry.contract(CHALLENGE)

    def backends(self):
        from carbon.reconstruction.capability_registry import BATTERY_BACKENDS

        return tuple(BATTERY_BACKENDS)

    def train_cases(self):
        return int(self.contract().document()["envelope"]["train_cases"])

    @cached_property
    def _material(self):
        from .challenge import PublicMaterial

        return PublicMaterial.load(self.root)

    def _train(self, train_cases):
        """Pinned TRAIN v1, or a study size drawn from it by position (cost
        depends on shapes only, never on values)."""
        train = self._material.train
        n = len(train.case_ids)
        if train_cases is None or train_cases == n:
            return train
        if type(train_cases) is not int or train_cases < 1:
            raise ValueError("train_cases is a positive integer")
        return train.take(np.arange(train_cases) % n)

    def training_programs(self, strategy, *, train_cases=None):
        """The recipe's training programs. A KNN trains nothing (no program);
        an ensemble is one program of identical members, each with
        `steps // members` steps, as `recipes.Ensemble` trains them."""
        from carbon.training_budget.adapter import Program

        from .compile import compile_recipe
        from .recipes import MLP, Structure

        _, recipe = compile_recipe(strategy)
        if recipe.family == "knn":
            return []
        settings = dict(recipe.settings)
        members = settings["ensemble_members"]
        member_steps = (
            settings["steps"] // members if members > 1 else settings["steps"]
        )
        polish = settings["polish_steps"]
        train = self._train(train_cases)
        n = len(train.case_ids)
        fraction = settings["train_fraction"]
        used = n if fraction >= 1.0 else int(n * fraction)
        structure = Structure(self._material.ocv_soc, self._material.ocv_v)

        def fit(main_steps):
            # The recipe's own settings with only the main steps changed:
            # polish stays as recorded, so the path the recipe takes is kept.
            member = dict(settings, steps=main_steps + polish)
            return MLP(recipe.family, member).fit(train, structure, seed=0)

        return [
            Program(
                backend=settings["backend"],
                members=members,
                main_steps=member_steps - polish,
                polish_steps=polish,
                cases_per_update=min(settings["batch_size"], used),
                fit=fit,
                parameters=lambda args: _leaf_count(args[0]),
            )
        ]
