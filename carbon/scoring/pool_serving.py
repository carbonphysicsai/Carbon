"""Serving a built model over the pool's rows for the pool grader (Test Engineer, 2026-10-24).

The pool grader only ever asks a model about pool points (each CMA-ES proposal snaps to one), so a model
needs to answer ONE batch: every (target fixed values + design) row of the version's pools. `predict_rows`
runs a catalog practice object (Motor / Cooling / F08 / F02, as the practice and curves jobs build them)
on exactly those rows and returns the raw output rows; `write_table` / `TableServer` carry the answers to
the grading side, where `serve(rows)` is a lookup. The grader then needs no Docker and no model:

    build host:   rows = pool rows (inputs only)  ->  predict_rows(practice, identity, recipe, rows)  ->  table file
    custody:      TableServer(load_table(path), input_names)  ->  ChallengeBinding.serve_good / serve_train

`predict_rows` reuses the practice object's own build path (image resolution, device choice, the pinned
worker) by wrapping its one call to `reconstruct_and_infer_public` with the pool rows as the query and
stopping once the predictions are in hand; the practice scoring that would follow is not run. The table
holds the model's predictions at the pool's input rows only: no truths, targets, limits or seeds.
"""

from __future__ import annotations

import json
import math

SCHEMA = "carbon.pool-prediction-table.v1"


class PoolServingRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _Captured(BaseException):
    """Raised to leave the practice call as soon as the pool predictions exist (not an Exception, so a
    practice's own error handling cannot swallow it)."""


def _key(values):
    return tuple(float(v) for v in values)


def predict_rows(practice, identity, strategy, input_rows):
    """``(raw rows, state_digest)`` for ``strategy`` (a bound catalog recipe dict) on ``input_rows``
    (lists in the interface's input order), by ``practice``'s own build and inference.
    """
    import numpy as np

    from carbon.development_session import bundle_construction_worker as worker

    if not input_rows:
        raise PoolServingRefused("no_rows_to_predict")
    real = worker.reconstruct_and_infer_public
    captured = {}

    def intercept(*args, **kwargs):
        like = np.asarray(kwargs["inputs"])
        shape = tuple(kwargs["expected_output_shape"])
        rows = np.asarray(input_rows, dtype=like.dtype)
        if rows.ndim != 2 or rows.shape[1:] != like.shape[1:]:
            raise PoolServingRefused("pool_rows_do_not_match_the_interface_width")
        result = real(
            *args,
            **{
                **kwargs,
                "inputs": rows,
                "expected_output_shape": (len(rows), *shape[1:]),
            },
        )
        if result.build.state_digest != result.inference.state_digest:
            raise PoolServingRefused("state_differs_between_phases")
        captured["raw"] = [
            [float(v) for v in row] for row in np.asarray(result.inference.predictions)
        ]
        captured["state_digest"] = result.build.state_digest
        raise _Captured

    worker.reconstruct_and_infer_public = intercept
    try:
        practice(identity, strategy)
    except _Captured:
        pass
    finally:
        worker.reconstruct_and_infer_public = real
    if "raw" not in captured:
        raise PoolServingRefused("the_practice_never_queried_the_model")
    if len(captured["raw"]) != len(input_rows) or not all(
        math.isfinite(v) for row in captured["raw"] for v in row
    ):
        raise PoolServingRefused("predictions_are_not_one_finite_row_per_input")
    return captured["raw"], captured["state_digest"]


def write_table(path, *, kind, version, input_names, rows, raw, state_digest, recipe):
    """The prediction table as canonical JSON; ``recipe`` is the strategy's digest (provenance only)."""
    if len(rows) != len(raw):
        raise PoolServingRefused("one_prediction_row_per_input_row")
    document = {
        "schema": SCHEMA,
        "kind": kind,
        "version": version,
        "input_names": list(input_names),
        "state_digest": state_digest,
        "recipe_digest": recipe,
        "rows": [
            {"inputs": list(map(float, r)), "raw": list(p)}
            for r, p in zip(rows, raw, strict=True)
        ],
    }
    with open(path, "wb") as handle:
        handle.write(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )


def load_table(path):
    with open(path, "rb") as handle:
        document = json.loads(handle.read())
    if (
        type(document) is not dict
        or document.get("schema") != SCHEMA
        or type(document.get("rows")) is not list
    ):
        raise PoolServingRefused("not_a_pool_prediction_table")
    return document


class TableServer:
    """``serve(rows)`` for a `ChallengeBinding`: each row is a dict {input_name: value}; the answer is the
    table's raw row at exactly that input. A row the table does not hold is refused, never guessed.
    """

    def __init__(self, document, input_names):
        if list(document["input_names"]) != list(input_names):
            raise PoolServingRefused("table_input_names_differ_from_the_binding")
        self.input_names = tuple(input_names)
        self.state_digest = document["state_digest"]
        self._answers = {_key(r["inputs"]): list(r["raw"]) for r in document["rows"]}
        if len(self._answers) != len(document["rows"]):
            raise PoolServingRefused("table_repeats_an_input_row")

    def __call__(self, rows):
        out = []
        for row in rows:
            key = _key(row[name] for name in self.input_names)
            if key not in self._answers:
                raise PoolServingRefused("row_not_in_the_prediction_table")
            out.append(list(self._answers[key]))
        return out
