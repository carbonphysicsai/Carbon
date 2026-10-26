"""The TRAIN-fit model of the pool grid run: learned-krr-v1 fitted on TRAIN only (Validator spec section 9.2).

`learned_baseline` (Gaussian-kernel ridge, inputs scaled to [-1, 1] by the Challenge's declared input box, outputs
standardised on TRAIN) is the registered baseline of all four Challenges. F08 (length 2.0, ridge 1e-4) and Motor
(4.0, 1e-4) use their registered values; F02 and Cooling pick theirs with `learned_baseline.select` on PRACTICE,
scored by the Challenge's own v2 practice total, and the choice is reported with a flag when it lands on a grid
edge. The model answers in the same space as the other served models (Cooling 1.4: the encoded 32-value row), is
asked only at the pool's input rows, and is reported, not a pass criterion, in Phase 1.

Deterministic (a Cholesky solve, no random initialisation); numpy only.
"""

from __future__ import annotations

from carbon import learned_baseline

#: Registered (length, ridge) per Challenge kind; the others pick theirs on PRACTICE.
REGISTERED = {"f08": (2.0, 1e-4), "motor": (4.0, 1e-4)}


class PoolBaselineRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def declared_bounds(kind, version):
    """The Challenge's declared input box, as {input name: (low, high)}, from the module that declares it."""
    from carbon.scoring import practice_grid

    names = practice_grid.input_names(kind, version)
    if kind == "motor":
        from carbon.motor import domain

        table = domain.INPUT_BOUNDS
    elif kind == "cooling":
        from carbon.cold_plate import domain

        table = domain.INPUT_BOUNDS
    elif kind == "f08":
        from carbon.challenge_pipeline import structures_readiness as readiness

        table = dict(zip(readiness.FIELDS, readiness.BOUNDS, strict=True))
    elif kind == "f02":
        from carbon.scoring import f02_physics

        table = dict(zip(("peak_w", "on_time_s"), f02_physics.BOUNDS, strict=True))
    else:
        raise PoolBaselineRefused("baseline_kind_unregistered")
    if set(names) - set(table):
        raise PoolBaselineRefused("declared_bounds_do_not_cover_the_inputs")
    return {name: tuple(table[name]) for name in names}


def _train(kind, version):
    """TRAIN inputs and targets in the served models' space."""
    from carbon.scoring import pool_adapters

    encoded, inputs, targets = pool_adapters._train_arrays(kind, version)
    if encoded:
        import numpy as np

        from carbon.cold_plate import output_encoding

        targets = np.asarray(output_encoding.encode_targets(targets), dtype=float)
    return inputs, targets


def _scaled(rows, names, bounds):
    """Rows as input dicts (the practice grader's) or lists in input order (the pool's), scaled to [-1, 1]."""
    dicts = [
        r if isinstance(r, dict) else dict(zip(names, r, strict=True)) for r in rows
    ]
    return learned_baseline.scale(dicts, names, bounds)


def fit(kind, version):
    """``(predict, choice)``: ``predict(rows) -> raw output rows`` for rows (lists in input order), and the
    reported choice {length, ridge, source, at_edge}."""
    from carbon.scoring import practice_dual, practice_grid

    names = practice_grid.input_names(kind, version)
    bounds = declared_bounds(kind, version)
    inputs, targets = _train(kind, version)
    x = _scaled(inputs.tolist(), names, bounds)
    if kind in REGISTERED:
        length, ridge = REGISTERED[kind]
        model = learned_baseline.KernelRidge(x, targets, length, ridge)
        choice = {
            "length": length,
            "ridge": ridge,
            "source": "registered",
            "at_edge": [],
        }
    else:

        def practice_score(candidate):
            def predict(cases):
                return candidate.predict(_scaled(cases, names, bounds)).tolist()

            document = practice_dual.feedback_v2(kind, version, predict)
            total = document.get("total")
            if total is not None:
                return 1.0 - total
            # A gate-failed model has no total. It ranks after every eligible one, and among the gate-failed by
            # its accuracy legs (a stated ordering; the Validator confirms it), so the grid is never all-None.
            legs = document.get("accuracy_legs") or {}
            if not legs:
                return None
            return 2.0 - sum(legs.values()) / len(legs)

        model, info = learned_baseline.select(x, targets, practice_score)
        chosen_score = next(
            g["score"]
            for g in info["grid"]
            if (g["length"], g["ridge"]) == (info["length"], info["ridge"])
        )
        choice = {
            "length": info["length"],
            "ridge": info["ridge"],
            "source": "select on PRACTICE",
            "at_edge": info["at_edge"],
            "gate_failed_on_practice": chosen_score >= 1.0,
        }

    def predict_rows(rows):
        return [
            [float(v) for v in row]
            for row in model.predict(_scaled(rows, names, bounds))
        ]

    return predict_rows, choice
