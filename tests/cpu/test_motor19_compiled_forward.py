"""Motor 1.9's graded inference is compiled from its first grade (blind-audit row 16, 23 Nov 2026).

Claims:
1. Motor 1.9 is a compiled version (`JIT_INFERENCE_VERSIONS`), so every judged 1.9 call runs the one compiled forward.
2. It is NOT a per-case-processes or vmap-64 version: 1.9 offers trust outputs, and only the plain and compiled programs
   have a trust variant, so its trust query must stay offered (checked once 1.9's graph Spec is registered).
3. The program builders read a version's limits through `physical_material` (each family's own public module), never a
   family-specific module directly; for Motor the document is the one `physical_public` serves.
"""

from __future__ import annotations

import pytest

from carbon.challenge_kit import physical_material, physical_public
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session import physical_graph_adapter_v2

MOTOR_18 = ("electric-motor-magnetics", "1.8")
MOTOR_19 = ("electric-motor-magnetics", "1.9")


def test_motor_1_9_is_compiled_and_grades_in_one_process():
    assert MOTOR_19 in worker.JIT_INFERENCE_VERSIONS
    assert MOTOR_19 not in worker.CASE_PROCS_INFERENCE_VERSIONS
    assert MOTOR_19 not in worker.VMAP64_INFERENCE_VERSIONS


@pytest.mark.skipif(
    MOTOR_19 not in physical_graph_adapter_v2.SPECS,
    reason="1.9's graph Spec lands with its registration head",
)
def test_motor_1_9_gets_the_compiled_program_and_keeps_its_trust_query():
    assert (
        worker.v2_infer_query(*MOTOR_19)["program"]
        == worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    )
    spec = physical_graph_adapter_v2.SPECS[MOTOR_19]
    if spec.trust_outputs:
        query = worker.v2_trust_infer_query(*MOTOR_19, spec.trust_outputs)
        assert query["trust_outputs"] == spec.trust_outputs


def test_limits_are_read_through_physical_material():
    assert physical_material.construction_limits_document(
        *MOTOR_18
    ) == physical_public.construction_limits_document(*MOTOR_18)
    with pytest.raises(ValueError, match="unregistered"):
        physical_material.construction_limits_document("no-such-challenge", "1.0")
