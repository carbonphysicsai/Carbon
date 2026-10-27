"""Pins: which timed receipts keep the exact measurement form, and why.

valV3, 2026-10-27: the PRACTICE timed child (the derived timed program) reports
`per_call_s` and may cover only a prefix of the practice rows, so the receiver's
retained-measurement check (`research_tasks`) and the graph custody
(`public_unbound_custody`) bind that prefix and accept `per_call_s`. The two
checks below read DIFFERENTLY produced receipts and keep the exact six-key form
at their registered batch shape; this pins that on purpose (Validator ruling
with the 91f2782aa receipt), so widening the practice form cannot silently widen
them.
"""

import pytest
from test_inference_pair_evidence import change_receipt, fixture, read

from carbon.scoring import bundle_benchmark_core as benchmark
from carbon.scoring.inference_pair_evidence import PairEvidenceRefused

REGISTRATION = {
    "timing_profile": {"input_shape": [4, 3]},
    "output": {"shape": [4, 2]},
}


def _measurement(**changes):
    measured = {
        "scope": benchmark.TIMED_SCOPE,
        "timing_s": {
            "preprocess": 0.1,
            "inference": 0.1,
            "postprocess": 0.1,
            "export": 0.1,
        },
        "input_shape": [4, 3],
        "input_dtype": "float32",
        "output_shape": [4, 2],
        "output_dtype": "float32",
    }
    measured.update(changes)
    return measured


def test_the_registered_benchmark_timed_measurement_form_is_accepted():
    benchmark._timed_measurement(_measurement(), REGISTRATION)


@pytest.mark.parametrize(
    "changes",
    [
        {"per_call_s": [0.01, 0.01]},
        {"input_shape": [2, 3], "output_shape": [2, 2]},
    ],
    ids=["per_call_s", "practice_prefix"],
)
def test_the_registered_benchmark_timed_measurement_refuses_the_practice_forms(
    changes,
):
    with pytest.raises(benchmark.BundleBenchmarkRefused):
        benchmark._timed_measurement(_measurement(**changes), REGISTRATION)


def test_the_pair_evidence_measurement_refuses_per_call_s():
    packet, kwargs = fixture()
    read(packet, kwargs)  # the unchanged fixture is valid

    change_receipt(
        packet["repeat"],
        lambda receipt: receipt["measurement"].update(per_call_s=[0.01, 0.01, 0.01]),
    )
    with pytest.raises(PairEvidenceRefused):
        read(packet, kwargs)
