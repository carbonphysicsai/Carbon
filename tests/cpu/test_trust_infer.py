"""The self-trust inference program variant (carbon/development_session/trust_infer.py, SELF_TRUST H3f): the graded container
splits a declared candidate's raw `(n, W + k)` output into the base `predictions.json` and a `sigma.json`; every other
program's text, and every undeclared candidate, is untouched.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from carbon.development_session import (
    bundle_construction_worker as worker,
    direct_graph_construction_worker as graph_worker,
    trust_infer,
)
from carbon.development_session.construction_recipe import RecipeRefused

PROGRAMS = {
    "plain bundle": lambda: worker.INFER_PROGRAM,
    "graph v2": lambda: graph_worker.PHYSICAL_V2_INFER_PROGRAM,
    "graph v2 compiled": lambda: graph_worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM,
}


@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_every_anchor_is_present_exactly_once_in_the_programs_it_can_derive_from(name):
    program = PROGRAMS[name]()
    for old, _new in trust_infer.ANCHORS:
        assert program.count(old) == 1, (name, old)


@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_the_variant_only_adds_the_three_insertions_and_the_plain_program_is_unchanged(name):
    program = PROGRAMS[name]()
    variant = trust_infer.trust_program(program)
    assert variant != program and "trust_k" in variant and "trust_k" not in program
    restored = variant
    for old, new in trust_infer.ANCHORS:
        restored = restored.replace(new, old)
    assert restored == program  # nothing else moved: no other part of the program text changed
    # the existing contract check and its raise text are still there, byte for byte, after the split
    assert variant.count('raise ValueError("bundle inference output contract differs")') == (
        program.count('raise ValueError("bundle inference output contract differs")') + 1
    )


def test_a_program_that_lost_an_anchor_or_is_already_a_trust_program_is_refused():
    program = worker.INFER_PROGRAM
    with pytest.raises(RuntimeError, match="anchor moved"):
        trust_infer.trust_program(program.replace(trust_infer.ANCHORS[1][0], "pass\n"))
    with pytest.raises(RuntimeError, match="already"):
        trust_infer.trust_program(trust_infer.trust_program(program))
    with pytest.raises(RuntimeError):
        trust_infer.trust_program(None)


def run_split(raw, control):
    """Run exactly the inserted split block, as the container would, on a raw output."""
    scope = {"np": np, "control": control, "outputs": [raw]}
    exec(trust_infer._RESULT_TRUST, scope)  # noqa: S102 - the program text under test, nothing else
    return scope["result"], scope["sigma"]


def test_a_declared_candidate_is_split_into_base_and_trust_columns():
    raw = np.arange(12, dtype="float32").reshape(3, 4)
    result, sigma = run_split(
        raw, {"expected_output_shape": [3, 3], "trust_outputs": 1}
    )
    assert result.shape == (3, 3) and sigma.shape == (3, 1)
    assert np.array_equal(result, raw[:, :3]) and np.array_equal(sigma, raw[:, 3:])


def test_an_undeclared_candidate_is_not_split_and_the_plain_contract_check_judges_it():
    raw = np.arange(12, dtype="float32").reshape(3, 4)
    result, sigma = run_split(raw, {"expected_output_shape": [3, 3]})
    assert sigma is None and result is raw  # a width of W + 1 without a declaration reaches the plain check unchanged


@pytest.mark.parametrize(
    "raw",
    [
        np.zeros((3, 3), dtype="float32"),  # a declared candidate sending only W
        np.zeros((3, 5), dtype="float32"),  # too wide
        np.zeros((2, 4), dtype="float32"),  # the wrong number of rows
        np.zeros((3, 4, 1), dtype="float32"),  # the wrong rank
        np.full((3, 4), np.nan, dtype="float32"),  # non-finite
        np.zeros((3, 4), dtype="U1"),  # not a numeric dtype
    ],
)
def test_a_declared_candidate_with_any_other_output_gets_todays_contract_refusal(raw):
    with pytest.raises(ValueError, match="^bundle inference output contract differs$"):
        run_split(raw, {"expected_output_shape": [3, 3], "trust_outputs": 1})


def test_the_split_columns_are_written_with_their_digest_in_the_receipt(tmp_path):
    import hashlib

    sigma = np.array([[0.5], [0.25]], dtype="float32")
    scope = {
        "out": tmp_path,
        "body": b"[]",
        "sigma": sigma,
        "json": json,
        "trust_k": 1,
        "digest": lambda raw: "sha256:" + hashlib.sha256(raw).hexdigest(),
        "receipt": {"predictions_digest": "x"},
    }
    exec(trust_infer._WRITE_TRUST, scope)  # noqa: S102
    exec(trust_infer._DIGEST_TRUST.split("}\n", 1)[1], scope)  # noqa: S102 - the receipt addition only
    written = (tmp_path / "sigma.json").read_bytes()
    assert json.loads(written) == [[0.5], [0.25]]
    assert scope["receipt"]["sigma_digest"] == "sha256:" + hashlib.sha256(written).hexdigest()
    assert scope["receipt"]["trust_outputs"] == 1


def test_infer_state_refuses_a_bad_trust_count_or_a_trust_candidate_without_its_program():
    common = dict(
        owner="o",
        identity="i",
        inference_image=None,
        recipe=None,
        binding={},
        state=b"",
        state_digest="x",
        inputs=None,
        expected_output_shape=(1, 1),
        allowlist_bytes=b"",
    )
    for bad in (-1, True, 1.5):
        with pytest.raises(RecipeRefused, match="direct_inference_trust_invalid"):
            worker._infer_state(None, trust_outputs=bad, **common)
    with pytest.raises(RecipeRefused, match="direct_inference_trust_needs_its_own_program"):
        worker._infer_state(None, trust_outputs=2, **common)  # no program


def test_the_trust_query_is_the_versions_own_program_plus_the_count():
    from carbon.development_session import physical_graph_adapter_v2 as v2

    key = next(
        k
        for k in v2.SPECS
        if k not in graph_worker.CASE_PROCS_INFERENCE_VERSIONS
        and k not in graph_worker.VMAP64_INFERENCE_VERSIONS
    )
    plain = graph_worker.v2_infer_query(*key)
    trust = graph_worker.v2_trust_infer_query(*key, 3)
    assert trust["trust_outputs"] == 3 and "trust_outputs" not in plain
    assert trust["program"] == trust_infer.trust_program(plain["program"])
    for k in ("input_name", "staged_files"):
        assert trust[k] == plain[k]


def test_a_per_case_processes_version_and_a_bad_count_have_no_trust_program():
    for key in graph_worker.CASE_PROCS_INFERENCE_VERSIONS:
        with pytest.raises(RecipeRefused, match="trust_program_not_offered"):
            graph_worker.v2_trust_infer_query(*key, 2)
    key = next(iter(graph_worker.JIT_INFERENCE_VERSIONS))
    for bad in (0, -1, True):
        with pytest.raises(RecipeRefused, match="trust_interface_not_offered"):
            graph_worker.v2_trust_infer_query(*key, bad)
