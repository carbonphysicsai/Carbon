"""The v1 practice dual shows a value-only design score, which no miner may see (owner
OWNER-EVALUATION-FOCUS-AND-DATA-CYCLE-01 section 1: every practice is graded by the exam's own v2
grader). A version with no v2 grader refuses with `practice_dual_v1_retired`; each launch version
still returns v2."""

from types import SimpleNamespace

import pytest

from carbon.direct_campaign import practice
from carbon.scoring import practice_dual, practice_grid

LAUNCH = [
    ("motor", "1.5"),
    ("cooling", "1.6"),
    ("f08", "1.7"),
    ("f02", "2.5"),
]


@pytest.mark.parametrize(("kind", "version"), LAUNCH)
def test_each_launch_version_has_a_v2_grader(kind, version):
    assert practice_grid.adapter(kind, version) is not None


@pytest.mark.parametrize(("kind", "version"), [("f08", "1.0"), ("f02", "2.0")])
def test_a_version_with_no_v2_grader_refuses_with_the_typed_reason(kind, version):
    assert practice_grid.adapter(kind, version) is None
    document = practice._dual_feedback(SimpleNamespace(prefix=kind), version, [[0.0]])
    assert document["schema"] == practice_dual.SCHEMA_V2
    assert document["available"] is False
    assert document["reason"] == "practice_dual_v1_retired" == practice_dual.V1_RETIRED
    assert "total" not in document and "design_value" not in document


def test_the_v1_motor_and_validator_paths_name_no_v1_feedback():
    import inspect

    from carbon.challenge_validator import motor as validator_motor
    from carbon.motor import catalog_practice

    for module in (validator_motor, catalog_practice):
        source = inspect.getsource(module)
        assert "practice_dual.feedback(" not in source
        assert "practice_dual.from_rows(" not in source
        assert "V1_RETIRED" in source


def test_f02_design_parts_are_shown_from_the_sealed_pack_record():
    """The F02 sealed pack puts V_pair/V_feas/V_var at the top of design_fidelity, not under "value"."""
    import inspect

    source = inspect.getsource(practice_dual.feedback_v2)
    assert 'fidelity.get("value") or fidelity' in source
