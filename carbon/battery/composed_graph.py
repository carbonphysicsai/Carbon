"""Graph networks trained with registered composed parts (DEVELOPMENT/CPU).

GraphModel owns verification, graph preparation, forward/init and state.
ComposedMLP owns the general training loop; no classic fit can ignore parts.
"""

from __future__ import annotations

import json

from .composed_training import ComposedMLP
from .level4_model import CHALLENGE, GraphModel

CONFLICT = "construction_rebuild_unavailable"
CONFLICT_FIELDS = ("loss_expressions", "composition_graphs")


def check_objectives(model, loss):
    """Inspect actual verified roles, never the loss_override permission alone."""
    if loss is None:
        return
    from carbon.level4 import allowlist, graph, intake, submission

    manifest = json.loads(model.raw_manifest)
    _, parsed = submission.verify(
        model.raw_manifest,
        model.files,
        allowlist=allowlist.load(),
        challenge=CHALLENGE,
        interface=manifest["interface"],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    if "loss" in parsed:
        raise graph.GraphRefused(CONFLICT, "+".join(CONFLICT_FIELDS))


class ComposedGraph(GraphModel, ComposedMLP):
    """A graph's prepared network and state, trained by the composed loop."""

    _fit_general = ComposedMLP._fit_general

    def __init__(self, model, *, loss=None, spectral=False, numerics=None):
        check_objectives(model, loss)
        super().__init__(
            model.family,
            model.settings,
            model.files,
            model.raw_manifest,
            model.submission,
            loss_override=model.loss_override,
        )
        self.loss = loss
        self.spectral = bool(spectral)
        self.numerics = None if numerics is None else dict(numerics)

    def _objective(self):
        return self.prepared.loss

    def _prepare(self, batch):
        prepared = super()._prepare(batch)
        if self.loss is not None and prepared.loss is not None:
            from carbon.level4 import graph

            raise graph.GraphRefused(CONFLICT, "+".join(CONFLICT_FIELDS))
        if self.numerics is not None:
            from . import level3_numerics

            if self.numerics["routine"] in level3_numerics.DENSE:
                import math

                from carbon.level4 import graph

                bound = self.numerics.get("memory_bound_bytes")
                if type(bound) is not int or bound <= 0:
                    raise ImportError("composed_graph_memory_bound_missing")
                count = sum(math.prod(shape) for _, _, shape in prepared.parameters)
                itemsize = 8 if self.settings["precision"] == "float64" else 4
                if level3_numerics.hessian_bytes(count, itemsize) > bound:
                    raise graph.GraphRefused(
                        "development.inverse_hessian_too_large", "quasi_newton_family"
                    )
        return prepared


def build(
    recipe, found, workspace, *, loss=None, spectral=False, numerics=None, composed=True
):
    from . import level4_model

    model = level4_model.build(recipe, found, workspace)
    check_objectives(model, loss)
    if not composed and loss is None and not spectral and numerics is None:
        # A single graph retains its own classic/general route byte for byte.
        return model
    return ComposedGraph(model, loss=loss, spectral=spectral, numerics=numerics)
