"""A self-trust candidate's sigma.json is kept with its evidence (SELF_TRUST H3g R2).

`lean_recipe_retention._sigma_snapshot` reads the graded inference snapshot's sigma.json bound to the digest the inference receipt names; every
other receipt keeps nothing new. ScoreLab custody's two small trust helpers (`_declared_interface_digests`, `_graph_sigma_ok`) are held here too.
"""

from __future__ import annotations

import json

import pytest

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable
from scripts.dev.score_lab import public_unbound_custody as custody


def _write(tmp_path, raw=b"[[0.5],[0.25]]"):
    (tmp_path / "sigma.json").write_bytes(raw)
    return raw


def test_a_receipt_that_names_no_sigma_keeps_nothing_new(tmp_path):
    assert retention._sigma_snapshot(tmp_path, {"schema": "x"}) is None
    _write(tmp_path)  # a file next to a receipt that does not name it is never read
    assert retention._sigma_snapshot(tmp_path, {"schema": "x"}) is None
    assert retention._sigma_snapshot(tmp_path, None) is None


def test_the_named_sigma_is_read_raw_and_bound_to_the_receipts_digest(tmp_path):
    raw = _write(tmp_path)
    receipt = {"sigma_digest": retention._sha(raw), "trust_outputs": 1}
    assert retention._sigma_snapshot(tmp_path, receipt) == raw


def test_a_missing_empty_or_different_sigma_refuses_and_is_never_replaced(tmp_path):
    receipt = {"sigma_digest": retention._sha(b"[[0.5],[0.25]]")}
    with pytest.raises(RetentionUnavailable, match="sigma_snapshot_unavailable"):
        retention._sigma_snapshot(tmp_path, receipt)
    _write(tmp_path, b"")
    with pytest.raises(RetentionUnavailable, match="sigma_snapshot_unavailable|size"):
        retention._sigma_snapshot(tmp_path, receipt)
    _write(tmp_path, b"[[0.5],[0.26]]")
    with pytest.raises(RetentionUnavailable, match="sigma_snapshot_changed"):
        retention._sigma_snapshot(tmp_path, receipt)
    assert (tmp_path / "sigma.json").read_bytes() == b"[[0.5],[0.26]]"


def test_the_operation_sources_link_sigma_to_the_inference_snapshot():
    names = {retained for _field, _name, retained in retention._OPERATION_FILES}
    assert "sigma.json" in names and "predictions.json" in names


def test_the_custody_accepts_the_declaration_digest_only_beside_the_versions_own():
    from carbon.development_session.construction_recipe import trust_declaration_digest

    own = "sha256:" + "b" * 64
    assert custody._declared_interface_digests(own) == (
        own,
        trust_declaration_digest(own),
    )
    # an invalid digest is not turned into a RecipeRefused: the old checks refuse it as before
    assert custody._declared_interface_digests("not-a-digest") == ("not-a-digest",)


def _ok(sigma, predictions, width):
    return custody._graph_sigma_ok(
        json.dumps(sigma).encode(), json.dumps(predictions).encode(), width
    )


def test_a_sigma_file_has_one_row_of_k_finite_numbers_per_prediction_row():
    predictions = [[1.0, 2.0], [3.0, 4.0]]
    assert _ok([[0.5], [0.25]], predictions, 1) is True
    assert _ok([[0.5, 0.1], [0.25, 0.2]], predictions, 2) is True
    for bad in (
        [[0.5]],  # a row short
        [[0.5], [0.25], [0.1]],  # a row too many
        [[0.5, 0.1], [0.25]],  # a ragged row
        [0.5, 0.25],  # not rows
        [["x"], [0.25]],
        [[True], [0.25]],
        {"rows": []},
    ):
        assert _ok(bad, predictions, 1) is False
    assert (
        custody._graph_sigma_ok(b"[[NaN],[0.25]]", b"[[1.0],[2.0]]", 1) is False
    )  # a non-finite constant is not JSON here
    assert custody._graph_sigma_ok(b"not json", b"[[1.0]]", 1) is False
