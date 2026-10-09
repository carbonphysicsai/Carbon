"""Battery's training budget adapter (TRAINING-BUDGET-01).

The battery instance of `carbon.training_budget.adapter.ChallengeAdapter`.
Everything here is read from battery's existing records. The shared study,
cost calculator and capacity calculation never import battery by name; they
find this adapter through `carbon/training_budget/adapters.json`.
"""

from __future__ import annotations

from functools import cached_property
from typing import ClassVar

import numpy as np

CHALLENGE = "battery-fastcharge-ageing-development-v1"


def level3_numerics_schema():
    from .level3_worker import SCHEMA

    return SCHEMA


def _leaf_count(tree):
    import jax

    return int(sum(np.size(leaf) for leaf in jax.tree_util.tree_leaves(tree)))


class BatteryAdapter:
    challenge_id = CHALLENGE
    #: Named record items (`module:attribute`), resolved on demand.
    records: ClassVar[dict] = {
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

    def _development(self, strategy, level, graph_compile=None):
        """`(recipe, record)` of `strategy` under `level`'s current development
        variant, compiled as the development rebuild compiles it, with no budget
        check of its own (the calculator is the budget check)."""
        from carbon.reconstruction import development_variants as dv
        from carbon.training_budget.cost import CostRefused

        from . import development_rebuild

        try:
            found = dv.compile_development(
                strategy, dv.variant(CHALLENGE, level), check_budget=False
            )
        except dv.VariantRefused as refused:
            raise CostRefused("cost_development_refused", refused.code) from None
        record = development_rebuild.record(found.reconstruction)
        if (
            development_rebuild.kind(record) == development_rebuild.LEVEL4
            and graph_compile is None
        ):
            # A graph's FLOPs come from its G5 compile (`train_step_flops`),
            # not from a battery training program: TRAINING-BUDGET-02 slice 5.
            raise CostRefused("cost_level4_graph_pending", "no G5 compile result")
        return found.construction, record

    def _graph_program(self, recipe, graph_compile):
        """A graph-only Level 4 recipe's one program: Carbon's loop over the
        graph, `steps` gradient steps, each G5's measured `train_step_flops` at
        the declared batch (the optimizer's update is not in it)."""
        from carbon.training_budget.adapter import Program
        from carbon.training_budget.cost import CostRefused

        flops = (graph_compile or {}).get("train_step_flops")
        if type(flops) not in (int, float) or not flops > 0:
            raise CostRefused("cost_level4_graph_unmeasured", "train_step_flops")
        settings = dict(recipe.settings)
        return Program(
            backend="jax",
            members=1,
            main_steps=settings["steps"],
            polish_steps=0,
            cases_per_update=settings["batch_size"],
            fit=None,
            parameters=None,
            measured_step_flops=float(flops),
        )

    def training_programs(
        self, strategy, *, train_cases=None, level=0, graph_compile=None
    ):
        """The recipe's training programs. A KNN trains nothing (no program);
        an ensemble is one program of identical members, each with
        `steps // members` steps, as `recipes.Ensemble` trains them.

        At a development `level` (TRAINING-BUDGET-02) the program is the one
        the development rebuild trains: its own build (`development_rebuild`),
        on a Level 2 pool selection's drawn subset when it names one, with a
        Level 3 polish priced at its line search's recorded worst case."""
        from types import SimpleNamespace

        from carbon.training_budget.adapter import Program

        from . import development_rebuild, level3_numerics
        from .compile import compile_recipe
        from .recipes import MLP, Structure

        if level:
            recipe, record = self._development(strategy, level, graph_compile)
            if development_rebuild.kind(record) == development_rebuild.LEVEL4:
                return [self._graph_program(recipe, graph_compile)]
        else:
            _, recipe = compile_recipe(strategy)
            record = None
        if recipe.family == "knn":
            return []
        settings = dict(recipe.settings)
        members = settings["ensemble_members"]
        member_steps = (
            settings["steps"] // members if members > 1 else settings["steps"]
        )
        polish = settings["polish_steps"]
        train = self._train(train_cases)
        if record is not None:
            # A pool selection's drawn subset is the training set; its size is
            # the recipe's `cases`, whatever study size was asked for.
            train = development_rebuild.training_data(record, train)
        n = len(train.case_ids)
        fraction = settings["train_fraction"]
        used = n if fraction >= 1.0 else int(n * fraction)
        structure = Structure(self._material.ocv_soc, self._material.ocv_v)

        def fit(main_steps):
            # The recipe's own settings with only the main steps changed:
            # polish stays as recorded, so the path the recipe takes is kept.
            member = dict(settings, steps=main_steps + polish)
            if record is None:
                model = MLP(recipe.family, member)
            else:
                model = development_rebuild.build_in_process(
                    SimpleNamespace(family=recipe.family, settings=member), record
                )
            return model.fit(train, structure, seed=0)

        polish_factor, dense = None, 0
        if record is not None and record.get("schema") == level3_numerics_schema():
            # Level 3's polish, at its worst case: every evaluation of a step
            # is a full-batch loss and gradient (`used` cases), counted in
            # minibatch steps; a dense routine also updates its p x p inverse
            # Hessian (a rank-two update: about 4 p^2 FLOPs).
            evaluations = level3_numerics.evaluations_per_step(record["line_search"])
            cases = min(settings["batch_size"], used)
            polish_factor = evaluations * used / cases
            dense = 0 if record["routine"] == "lbfgs" else 4

        return [
            Program(
                backend=settings["backend"],
                members=members,
                main_steps=member_steps - polish,
                polish_steps=polish,
                cases_per_update=min(settings["batch_size"], used),
                fit=fit,
                parameters=lambda args: _leaf_count(args[0]),
                polish_factor=polish_factor,
                polish_dense_flops_per_p2=dense,
            )
        ]
