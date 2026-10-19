"""The dual producer's `paired_repeat` gate over a pinned source-free pair.

Inert Platform-shaped pair records (the reader's own fixture); no worker, model
or scientific value. The tolerance below is a fixture value, never a Challenge
rule. Claims: three runs (the graded original and two fresh repeats) are
compared under the Challenge's own registered rule only; a missing pair or
rule is typed unavailable, never a candidate verdict; a repeat that reuses the
graded operation is not independent.
"""

from copy import deepcopy

import pytest
from test_inference_pair_evidence import encode, fixture, sha

from carbon.scoring.private_evaluation_source import (
    PrivateEvaluationSourceRefused,
    paired_repeat_verdict,
)

RULE = {
    "schema": "carbon.paired-repeat-rule.v1",
    "status": "REGISTERED",
    "comparison": "abs_diff_le_ulp_scaled",
    "placements": ["across_runs_same_position"],
    "dtype": "float32",
    "floor": 1.0,
    "tolerance_ulp": {"q": 4},
}


def case(repeat=None, *, outputs=(1.0, 2.0, 3.0)):
    packet, kwargs = fixture(repeat)
    expected = kwargs["expected"]
    raw = encode(packet)
    receipt = {
        **{k: expected[k] for k in ("recipe_digest", "state_digest", "inputs_digest")},
        "measurement": {
            k: deepcopy(expected[k])
            for k in ("input_shape", "output_shape", "input_dtype", "output_dtype")
        },
    }
    worker = {
        "inference_image_id": expected["inference_image_id"],
        "inference_operation": "operation-" + "9" * 64,
    }
    originals = {"inference_pair_raw": raw, "inference_pair_sha256": sha(raw)}
    return originals, receipt, worker, list(outputs)


def verdict(originals, receipt, worker, outputs, rule=RULE):
    return paired_repeat_verdict(
        originals,
        receipt=receipt,
        worker=worker,
        outputs=outputs,
        rule=rule,
        quantity_of=lambda _index: "q",
    )


def test_three_runs_within_the_registered_rule_pass():
    assert verdict(*case()) is True


def test_a_repeat_beyond_the_rule_fails_and_one_within_it_passes():
    eps = 2.0**-23
    # Every pair of the three runs is compared, not only graded vs repeat.
    near = [[1.0], [2.0], [3.0 + 2 * eps * 3.0]]
    assert verdict(*case(near)) is True
    far = [[1.0], [2.0], [3.0 + 8 * eps * 3.0]]
    assert verdict(*case(far)) is False
    # The graded original disagreeing with both repeats also fails.
    assert verdict(*case(outputs=(1.0, 2.0, 3.0 + 8 * eps * 3.0))) is False


def test_missing_pair_is_unavailable_evidence_not_a_candidate_fail():
    _, receipt, worker, outputs = case()
    with pytest.raises(
        PrivateEvaluationSourceRefused, match="dual_repeat_evidence_unavailable"
    ):
        verdict({}, receipt, worker, outputs)


@pytest.mark.parametrize(
    "rule",
    [
        None,
        {**RULE, "status": "PROPOSED"},
        {**RULE, "placements": ["same_batch_different_position"]},
        {**RULE, "dtype": "float64"},
        {**RULE, "tolerance_ulp": {}},
        {**RULE, "tolerance_ulp": {"q": float("nan")}},
        {k: v for k, v in RULE.items() if k != "floor"},
    ],
)
def test_an_absent_or_inapplicable_rule_is_unregistered_never_borrowed(rule):
    with pytest.raises(
        PrivateEvaluationSourceRefused, match="dual_repeat_rule_unregistered"
    ):
        verdict(*case(), rule=rule)


def test_an_unpinned_or_other_model_pair_is_unavailable():
    originals, receipt, worker, outputs = case()
    with pytest.raises(PrivateEvaluationSourceRefused, match="registered_digest"):
        verdict(
            {**originals, "inference_pair_sha256": sha(b"other")},
            receipt,
            worker,
            outputs,
        )
    other = {**receipt, "state_digest": sha(b"another-model")}
    with pytest.raises(PrivateEvaluationSourceRefused, match="pair_binding"):
        verdict(originals, other, worker, outputs)
    with pytest.raises(PrivateEvaluationSourceRefused, match="pair_binding"):
        verdict(
            originals, receipt, {**worker, "inference_image_id": sha(b"x")}, outputs
        )


def test_a_repeat_that_is_the_graded_operation_is_not_independent():
    originals, receipt, worker, outputs = case()
    reused = {**worker, "inference_operation": "operation-" + "1" * 64}
    with pytest.raises(PrivateEvaluationSourceRefused, match="not_independent"):
        verdict(originals, receipt, reused, outputs)
