"""Motor's training budget adapter (MOTOR-NEURAL-01).

The motor instance of `carbon.training_budget.adapter.ChallengeAdapter`, read
from motor's existing records. The shared study, cost calculator and capacity
calculation find it through `carbon/training_budget/adapters.json`.

The kernel ridge is a closed-form fit and trains no stepped program, so it has
no program. A neural recipe is one program of `steps` full-batch updates
through Carbon's shared trainer, as `neural.NeuralModel` trains it. Items
motor has no record for yet (an equivalence margin, a finalist rule, a public
generator) are left out, so the study names them as gaps (`AdapterGap`).
"""

from __future__ import annotations

from functools import cached_property
from typing import ClassVar

import numpy as np

CHALLENGE = "electric-motor-magnetics"


def _leaf_count(tree):
    import jax

    return int(sum(np.size(leaf) for leaf in jax.tree_util.tree_leaves(tree)))


class MotorAdapter:
    challenge_id = CHALLENGE
    #: Named record items (`module:attribute`), resolved on demand.
    records: ClassVar[dict] = {
        "worker": "carbon.motor.compile:rebuild",
        "exam": "carbon.motor.exam:score_case",
        "panel": "carbon.motor.admission_study:pins",
    }

    def __init__(self, root="."):
        self.root = root

    def contract(self):
        from carbon.reconstruction import capability_registry

        return capability_registry.contract(CHALLENGE)

    def backends(self):
        from carbon.reconstruction.capability_registry import MOTOR_BACKENDS

        return tuple(MOTOR_BACKENDS)

    def train_cases(self):
        return int(self.contract().document()["envelope"]["train_cases"])

    @cached_property
    def _material(self):
        from .challenge import PublicMaterial

        return PublicMaterial.load(self.root)

    def _train(self, train_cases):
        """Public TRAIN, or a study size drawn from it by position (cost
        depends on shapes only, never on values)."""
        train = list(self._material.train)
        n = len(train)
        if train_cases is None or train_cases == n:
            return train
        if type(train_cases) is not int or train_cases < 1:
            raise ValueError("train_cases is a positive integer")
        return [train[i % n] for i in range(train_cases)]

    def training_programs(self, strategy, *, train_cases=None, level=0):
        """The recipe's training programs: none for the kernel ridge; one
        full-batch program for a neural family. Motor has no development
        level yet."""
        from carbon.training_budget.adapter import Program

        from .compile import NEURAL_FAMILIES, compile_recipe
        from .neural import TRAINER_FIXED, NeuralModel

        if level:
            raise ValueError("Motor has no development construction level yet")
        _, recipe = compile_recipe(strategy)
        if recipe.family not in NEURAL_FAMILIES:
            return []
        settings = dict(recipe.settings)
        train = self._train(train_cases)

        def fit(main_steps):
            # The recipe's own settings with only the main steps changed.
            model = NeuralModel(recipe.family, dict(settings, steps=main_steps))
            return model.fit(train, 0)

        return [
            Program(
                backend=settings["backend"],
                members=1,
                main_steps=settings["steps"],
                polish_steps=TRAINER_FIXED["polish_steps"],
                cases_per_update=min(TRAINER_FIXED["batch_size"], len(train)),
                fit=fit,
                parameters=lambda args: _leaf_count(args[0]),
            )
        ]
