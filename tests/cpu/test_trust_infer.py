"""The self-trust inference program variants (carbon/development_session/trust_infer.py, SELF_TRUST H3f): the graded container
splits a declared candidate's raw `(n, W + k)` output into the base `predictions.json` and a `sigma.json`; every other
program's text, and every undeclared candidate, is untouched. Derived from each program a trust version can run: the plain
program and the graph route v2 ensemble program (plain and compiled), which already decodes its result.
"""

from __future__ import annotations

import hashlib
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
FAMILY = {
    "plain bundle": trust_infer.PLAIN_ANCHORS,
    "graph v2": trust_infer.V2_ANCHORS,
    "graph v2 compiled": trust_infer.V2_ANCHORS,
}


def run(code, scope):
    """Run a piece of the program text under test on arrays, as the container would."""
    exec(code, scope)  # noqa: S102
    return scope


@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_every_anchor_of_the_programs_family_is_present_exactly_once(name):
    program = PROGRAMS[name]()
    assert trust_infer.anchors_for(program) is FAMILY[name]
    for old, _new in FAMILY[name]:
        assert program.count(old) == 1, (name, old)


@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_the_variant_only_adds_its_insertions_and_the_plain_program_is_unchanged(name):
    program = PROGRAMS[name]()
    variant = trust_infer.trust_program(program)
    assert variant != program and "trust_k" in variant and "trust_k" not in program
    restored = variant
    for old, new in FAMILY[name]:
        restored = restored.replace(new, old)
    assert restored == program  # nothing else moved: no other part of the program text changed
    raise_text = 'raise ValueError("bundle inference output contract differs")'
    assert variant.count(raise_text) == program.count(raise_text) + 1
    compile(variant, "trust_variant", "exec")  # the variant is still a program


def test_a_program_that_lost_an_anchor_or_is_already_a_trust_program_is_refused():
    program = worker.INFER_PROGRAM
    with pytest.raises(RuntimeError, match="anchor moved"):
        trust_infer.trust_program(program.replace(trust_infer.PLAIN_ANCHORS[1][0], "pass\n"))
    v2 = graph_worker.PHYSICAL_V2_INFER_PROGRAM
    with pytest.raises(RuntimeError, match="anchor moved"):
        trust_infer.trust_program(v2.replace(trust_infer.V2_ANCHORS[2][0], "pass\n"))
    with pytest.raises(RuntimeError, match="already"):
        trust_infer.trust_program(trust_infer.trust_program(program))
    with pytest.raises(RuntimeError):
        trust_infer.trust_program(None)


def test_a_declared_candidate_is_split_into_base_and_trust_columns():
    raw = np.arange(12, dtype="float32").reshape(3, 4)
    scope = run(
        trust_infer._RESULT_TRUST,
        {"np": np, "control": {"expected_output_shape": [3, 3], "trust_outputs": 1}, "outputs": [raw]},
    )
    assert scope["result"].shape == (3, 3) and scope["sigma"].shape == (3, 1)
    assert np.array_equal(scope["result"], raw[:, :3])
    assert np.array_equal(scope["sigma"], raw[:, 3:])


def test_an_undeclared_candidate_is_not_split_and_the_plain_contract_check_judges_it():
    raw = np.arange(12, dtype="float32").reshape(3, 4)
    scope = run(
        trust_infer._RESULT_TRUST,
        {"np": np, "control": {"expected_output_shape": [3, 3]}, "outputs": [raw]},
    )
    assert scope["sigma"] is None and scope["result"] is raw


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
@pytest.mark.parametrize("code", ["plain", "v2"])
def test_a_declared_candidate_with_any_other_output_gets_todays_contract_refusal(raw, code):
    text = trust_infer._RESULT_TRUST if code == "plain" else trust_infer._V2_RESULT_TRUST
    scope = {
        "np": np,
        "control": {"expected_output_shape": [3, 3], "trust_outputs": 1},
        "outputs": [raw],
        "decoder_sd": np.ones(3),
        "decoder_mu": np.zeros(3),
    }
    with pytest.raises(ValueError, match="^bundle inference output contract differs$"):
        run(text, scope)


def test_the_v2_ensemble_combines_the_physics_columns_and_takes_the_trust_columns_from_member_zero():
    # door-code 08:10:59Z: every member is W + k wide; combine the W columns by the registered weights, the k columns
    # from the ONE trust member, then decode the physics columns only.
    program = trust_infer.trust_program(graph_worker.PHYSICAL_V2_INFER_PROGRAM)
    start = program.index("def forward(*arguments):")
    end = program.index("\n", program.index("    return [jnp.concatenate")) + 1
    width, trust, batch = 3, 2, 4
    rng = np.random.default_rng(0)
    members = [rng.normal(size=(batch, width + trust)) for _ in range(2)]
    weights = [np.array([0.25, 0.5, 1.0]), np.array([0.75, 0.5, 0.0])]
    scope = run(
        program[start:end],
        {
            "jnp": np,
            "member_forward": lambda index, _part: [members[index]],
            "member_arrays": [[0], [1]],
            "combine": weights,
            "width": width,
        },
    )
    out = scope["forward"](None, "part")[0]
    physics = members[0][:, :width] * weights[0] + members[1][:, :width] * weights[1]
    assert out.shape == (batch, width + trust)
    assert np.allclose(out[:, :width], physics)
    assert np.allclose(out[:, width:], members[0][:, width:])  # member 0 alone, weight 1
    # the split happens BEFORE the decoder, which then touches the W physics columns only
    scope = run(
        trust_infer._V2_RESULT_TRUST,
        {
            "np": np,
            "control": {"expected_output_shape": [batch, width], "trust_outputs": trust},
            "outputs": [out],
            "decoder_sd": np.full(width, 2.0),
            "decoder_mu": np.ones(width),
        },
    )
    assert np.allclose(scope["result"], physics * 2.0 + 1.0)
    assert np.allclose(scope["sigma"], members[0][:, width:])  # the trust columns are not decoded


def test_the_split_columns_are_written_with_their_digest_in_the_receipt(tmp_path):
    scope = {
        "out": tmp_path,
        "body": b"[]",
        "sigma": np.array([[0.5], [0.25]], dtype="float32"),
        "json": json,
        "trust_k": 1,
        "digest": lambda raw: "sha256:" + hashlib.sha256(raw).hexdigest(),
        "receipt": {"predictions_digest": "x"},
    }
    run(trust_infer._WRITE_TRUST, scope)
    run(trust_infer._DIGEST_TRUST.split("}\n", 1)[1], scope)  # the receipt addition only
    written = (tmp_path / "sigma.json").read_bytes()
    assert json.loads(written) == [[0.5], [0.25]]
    assert scope["receipt"]["sigma_digest"] == "sha256:" + hashlib.sha256(written).hexdigest()
    assert scope["receipt"]["trust_outputs"] == 1


def test_infer_state_refuses_a_bad_trust_count_or_a_trust_candidate_without_its_program():
    common = {
        "owner": "o",
        "identity": "i",
        "inference_image": None,
        "recipe": None,
        "binding": {},
        "state": b"",
        "state_digest": "x",
        "inputs": None,
        "expected_output_shape": (1, 1),
        "allowlist_bytes": b"",
    }
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
    for field in ("input_name", "staged_files"):
        assert trust[field] == plain[field]


def test_a_per_case_processes_version_and_a_bad_count_have_no_trust_program():
    for key in graph_worker.CASE_PROCS_INFERENCE_VERSIONS:
        with pytest.raises(RecipeRefused, match="trust_program_not_offered"):
            graph_worker.v2_trust_infer_query(*key, 2)
    key = next(iter(graph_worker.JIT_INFERENCE_VERSIONS))
    for bad in (0, -1, True):
        with pytest.raises(RecipeRefused, match="trust_interface_not_offered"):
            graph_worker.v2_trust_infer_query(*key, bad)


def test_no_trust_version_is_registered_in_a_program_set_that_has_no_trust_variant():
    # door-code 08:35:37Z: the per-case-processes and vmap-64 programs derive from the compiled v2 text and have no trust
    # variant, so a version that offers a trust interface must not be listed there (the query refuses typed otherwise).
    from carbon.development_session import physical_graph_adapter_v2 as v2

    for key, spec in v2.SPECS.items():
        if spec.trust_outputs:
            assert key not in graph_worker.CASE_PROCS_INFERENCE_VERSIONS, key
            assert key not in graph_worker.VMAP64_INFERENCE_VERSIONS, key
