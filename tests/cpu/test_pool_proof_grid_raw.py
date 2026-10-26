"""The proof grid script reads a pool-raw document as the pool merge writes it (V8_RULINGS section 12).

The Motor grid run crashed (PoolRefused raw_rows_must_match_the_original_pool) because the whole
`{"target_id", "design_names", "raw_outputs"}` document went to `attach_raw`, which takes the rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_plugin import binding, toy_target, truth

from carbon.scoring import pool_grader, pool_plugin
from scripts.dev import pool_proof_grid as grid_script


def _document(target_id="t1"):
    spec = toy_target(target_id, 5)
    rows = [truth({"x": d[0], "y": d[1]}) for d in spec.designs]
    return spec, {
        "target_id": target_id,
        "design_names": ["x", "y"],
        "raw_outputs": rows,
    }


def test_the_raw_rows_of_a_pool_raw_document_attach_in_the_original_pool_order():
    spec, document = _document()
    # the pool merge's document is the whole thing; its rows are the original pool's (spec.pool_size of them)
    original = [truth({"x": 0.0, "y": 0.0}) for _ in range(spec.pool_size)]
    document = {**document, "raw_outputs": original}
    rows = grid_script._raw_rows(document, "t1", binding())
    attached = pool_grader.attach_raw(spec, rows)
    assert attached.raw is not None and len(attached.raw) == len(spec.designs)
    with pytest.raises(pool_grader.PoolRefused, match="raw_rows_must_match"):
        pool_grader.attach_raw(
            spec, document
        )  # the crash this fixes: the whole document


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(target_id="other"),
        lambda d: d.update(design_names=["y", "x"]),
        lambda d: d.update(design_names=["x"]),
        lambda d: d.pop("raw_outputs"),
        lambda d: d.update(raw_outputs="rows"),
        lambda d: d.update(extra=1),
    ],
)
def test_a_pool_raw_document_that_is_not_this_targets_is_a_stop_not_a_guess(mutate):
    _, document = _document()
    mutate(document)
    with pytest.raises(pool_plugin.TruthCheckStop):
        grid_script._raw_rows(document, "t1", binding())
    with pytest.raises(pool_plugin.TruthCheckStop):
        grid_script._raw_rows([1, 2, 3], "t1", binding())
