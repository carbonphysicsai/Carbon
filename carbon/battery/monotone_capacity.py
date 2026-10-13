"""Development-only monotone fade head, staged beside pinned battery recipes.

The baseline encodes Q1 and cumulative Q1-Qk fade targets. This sidecar
re-expresses adjacent non-negative fade increments as softplus logits, then
reconstructs cumulative decrements before the existing prediction split.
It is a candidate mechanism only: never a miner-facing capability or a physics
qualification.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import json

import numpy as np


def _softplus(x):
    return np.maximum(x, 0.0) + np.log1p(np.exp(-np.abs(x)))


def _inverse_softplus(x):
    """Exact inverse on positive inputs; nonpositive increments fail closed."""
    values = np.asarray(x, dtype=float)
    if not np.isfinite(values).all() or np.any(values <= 0.0):
        raise ValueError("monotone_capacity.requires_positive_observed_fade")
    return values + np.log(-np.expm1(-values))


def count_capacity_increases(predictions):
    """Count strict adjacent capacity rises in a public prediction mapping."""
    if not isinstance(predictions, dict):
        raise ValueError("monotone_capacity.invalid_prediction_mapping")
    rows = predictions.get("predictions", predictions)
    if not isinstance(rows, dict) or not rows:
        raise ValueError("monotone_capacity.invalid_prediction_mapping")
    cases = transitions = increasing_cases = increasing_transitions = 0
    for case_id, record in rows.items():
        capacity = record.get("capacity_ah") if isinstance(record, dict) else None
        values = np.asarray(capacity, dtype=float)
        if values.ndim != 1 or values.size < 2 or not np.isfinite(values).all():
            raise ValueError(f"monotone_capacity.invalid_capacity_curve:{case_id}")
        cases += 1
        transitions += values.size - 1
        rises = np.diff(values) > 0.0
        increasing_cases += int(np.any(rises))
        increasing_transitions += int(np.count_nonzero(rises))
    return {
        "cases": cases,
        "adjacent_transitions": transitions,
        "increasing_cases": increasing_cases,
        "increasing_transitions": increasing_transitions,
        "disposition": (
            "STOP_NO_MEASURABLE_HELP"
            if increasing_cases == 0
            else "INCREASES_OBSERVED"
        ),
    }


def main(argv=None):
    """Run the free public-prediction precheck; this does not train a model."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count-increases", required=True, metavar="PREDICTIONS_JSON_GZ"
    )
    args = parser.parse_args(argv)
    with gzip.open(args.count_increases, "rt", encoding="utf-8") as stream:
        predictions = json.load(stream)
    print(json.dumps(count_capacity_increases(predictions), sort_keys=True))
    return 0


def layout_type(base_layout):
    """Return a Layout subclass that fits adjacent fade increments as logits."""

    class MonotoneCapacityLayout(base_layout):
        def targets(self, data):
            if not self.fade:
                raise ValueError("monotone_capacity.requires_capacity_fade_head")
            target = super().targets(data)
            start = self.nv + self.nt + 1
            cumulative = target[:, start + 1 :]
            adjacent = np.column_stack(
                [cumulative[:, :1], np.diff(cumulative, axis=1)]
            )
            target = target.copy()
            target[:, start + 1 :] = _inverse_softplus(adjacent)
            return target

        def split(self, values):
            transformed = np.asarray(values).copy()
            start = self.nv + self.nt + 1
            increments = _softplus(transformed[:, start + 1 :])
            transformed[:, start + 1 :] = np.cumsum(increments, axis=1)
            return super().split(transformed)

    return MonotoneCapacityLayout


@contextlib.contextmanager
def _monotone_layout_installed():
    """Install the candidate Layout only during one fixed Carbon call."""
    from carbon.battery import recipes

    previous = recipes.Layout
    recipes.Layout = layout_type(previous)
    try:
        yield
    finally:
        recipes.Layout = previous


class MonotoneCapacityCandidate:
    """Wrap a baseline battery model with the candidate-only output layout."""

    def __init__(self, model):
        settings = getattr(model, "settings", {})
        if not settings.get("capacity_fade_head", False):
            raise ValueError("monotone_capacity.requires_capacity_fade_head")
        if getattr(model, "family", None) not in {"mlp", "deeponet"}:
            raise ValueError("monotone_capacity.unsupported_family")
        if settings.get("backend", "jax") != "jax":
            raise ValueError("monotone_capacity.unsupported_backend")
        self._model = model

    def fit(self, *args, **kwargs):
        with _monotone_layout_installed():
            return self._model.fit(*args, **kwargs)

    def predict(self, *args, **kwargs):
        return self._model.predict(*args, **kwargs)

    def export_state(self):
        """Export wrapped weights with an explicit candidate identity."""
        from carbon.battery import recipes

        header, arrays = recipes.export_state(self._model)
        header = dict(header)
        header["construction_variant"] = "battery-monotone-capacity-fade-v1"
        return header, arrays

    def __getattr__(self, name):
        return getattr(self._model, name)


def build(family, settings):
    """Build the unmodified baseline model wrapped with monotone fade."""
    from carbon.battery import recipes

    return MonotoneCapacityCandidate(recipes.build(family, settings))


def import_state(header, arrays):
    """Restore only a marked candidate state with its candidate Layout."""
    if header.get("construction_variant") != "battery-monotone-capacity-fade-v1":
        raise ValueError("monotone_capacity.candidate_state_required")
    from carbon.battery import recipes

    with _monotone_layout_installed():
        model = recipes.import_state(header, arrays)
    return MonotoneCapacityCandidate(model)


if __name__ == "__main__":
    raise SystemExit(main())
