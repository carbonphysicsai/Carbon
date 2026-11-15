"""Motor 1.8 grades with A9's per-case compiled program again (owner, Sun 15 Nov 2026, typed in Deploy-B: roll 116 back to A9
behaviour, per-case compiled, no batched grading; Validator-2: a forward revert on 4d30921e).

Claims: Motor 1.8 is in no vmap-64 set; its registered inference program is the per-case compiled one, byte for byte the
program 57af6692 (A9) served (pinned sha256); no version is vmap-64; speed_match treats Motor 1.8 as a non-vmap version
(exact comparison, as on A9).
"""

from __future__ import annotations

import hashlib

from carbon.challenge_validator import speed_match
from carbon.development_session import direct_graph_construction_worker as worker

MOTOR_18 = ("electric-motor-magnetics", "1.8")
#: sha256 of Motor 1.8's registered inference program at 57af6692 (A9), computed there (Linux, 15 Nov 2026).
A9_MOTOR_18_PROGRAM_SHA256 = (
    "512cb25053d6b45b6e0db589618e7da895480f2070640739462dbd0787da248a"
)


def test_no_version_is_vmap64():
    assert worker.VMAP64_INFERENCE_VERSIONS == frozenset()
    assert MOTOR_18 in worker.JIT_INFERENCE_VERSIONS


def test_motor_1_8_serves_a9s_per_case_compiled_program_byte_for_byte():
    program = worker.v2_infer_query(*MOTOR_18)["program"]
    assert program == worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    assert hashlib.sha256(program.encode()).hexdigest() == A9_MOTOR_18_PROGRAM_SHA256


def test_speed_match_sees_motor_1_8_as_a_non_vmap_version():
    assert speed_match.tolerance(*MOTOR_18) is None
    speed_match.require_served(*MOTOR_18)
