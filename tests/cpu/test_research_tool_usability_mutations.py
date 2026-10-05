"""Mutation checks for RESEARCH-TOOL-USABILITY-01.

The pattern of `test_graphite_pod_logs_retry_mutations.py`: each case
switches one guard off with monkeypatch and runs the test that guards it. The
guard test passes with the protection in place and must fail without it.
"""

from __future__ import annotations

import pytest
import test_research_tool_usability as t

from carbon import research
from carbon.development_session import research_service, research_tools
from carbon.miner_mcp import standard

ASSERTION = (AssertionError, pytest.fail.Exception)


def _battery(test, *args):
    """Run a guard test that takes the battery composition fixture."""

    def run(tmp):
        sdk, meter, composition = t.battery_composition(tmp)
        try:
            test((sdk, meter, composition), *args)
        finally:
            composition.tasks.close()

    return run


def _with_monkeypatch(test):
    def run(tmp):
        with pytest.MonkeyPatch.context() as patch:
            test(patch)

    return run


def _structural(request):
    return research.A2ValidationProvider().dry_validate(request)


MUTATIONS = {
    # dry_validate runs the submission path's compile, not A2 alone.
    "dry_validate_runs_the_submission_compile": (
        lambda m: m.setattr(research_service, "submission_issues", lambda s, c: ()),
        _battery(
            t.test_dry_validate_refuses_what_the_submission_path_refuses,
            "neighbours_out_of_domain",
            t.battery({"neighbours": -5}),
            (("parameter.domain_mismatch", "/parameters/neighbours"),),
        ),
        ASSERTION,
    ),
    # The composition's validation provider is the contract one.
    "composition_answers_with_the_contract": (
        lambda m: m.setattr(
            research_service.ChallengeContractValidation,
            "dry_validate",
            lambda self, request: _structural(request),
        ),
        _battery(
            t.test_dry_validate_refuses_what_the_submission_path_refuses,
            "excluded_parameter",
            t.battery({"label_method": "x"}, "mlp"),
            (("parameter.not_rebuildable", "/parameters/label_method"),),
        ),
        ASSERTION,
    ),
    # A strategy naming another Challenge is never compiled under it.
    "another_challenge_is_refused": (
        lambda m: m.setattr(
            research_service, "names_another_challenge", lambda s, c: False
        ),
        _battery(
            t.test_a_strategy_naming_another_challenge_is_refused_as_the_compiler_refuses_it
        ),
        ASSERTION,
    ),
    # v2 reads a practice call's action and arguments_json "null" as null.
    "v2_reads_practice_nulls": (
        lambda m: m.setattr(research_tools, "practice_null_fields", lambda rule: ()),
        lambda tmp: t.test_a_practice_null_string_builds_the_real_null_request_under_v2(
            tmp, "null", "null"
        ),
        (*ASSERTION, ValueError, TypeError),
    ),
    # Only v2 reads them: a plan frozen before it refuses as before (SDK).
    "only_v2_reads_practice_nulls_in_the_sdk": (
        lambda m: m.setattr(
            research_tools,
            "practice_null_fields",
            lambda rule: ("action", "arguments_json"),
        ),
        lambda tmp: t.test_an_older_plan_refuses_a_practice_null_in_the_sdk_as_before(
            tmp, t.NORMALISING_V1, "action"
        ),
        # Unrefused, the request reaches the admission check, which stops it.
        (*ASSERTION, ValueError),
    ),
    # ... and at the door.
    "only_v2_reads_practice_nulls_at_the_door": (
        lambda m: m.setattr(
            standard, "practice_null_fields", lambda rule: ("action", "arguments_json")
        ),
        lambda tmp: (
            t.test_an_older_plan_refuses_a_practice_null_at_the_door_with_a_correction(
                tmp, t.NORMALISING_V1, "action", "action"
            )
        ),
        ASSERTION,
    ),
    # The door lets a v2 "null" through to the SDK.
    "door_passes_v2_nulls": (
        lambda m: m.setattr(standard, "_null_read_as_none", lambda *a: False),
        lambda tmp: t.test_a_practice_null_string_passes_the_door_under_v2(
            tmp, {"action": "null", "arguments": "null"}
        ),
        ASSERTION,
    ),
    # A door refusal of a practice field carries its correction.
    "door_refusal_carries_its_correction": (
        lambda m: m.setattr(
            standard,
            "_practice_refused",
            lambda field, value: standard._invalid(),
        ),
        lambda tmp: (
            t.test_an_older_plan_refuses_a_practice_null_at_the_door_with_a_correction(
                tmp, None, "arguments", "arguments_json"
            )
        ),
        (*ASSERTION, AttributeError, TypeError),
    ),
    # An unknown frozen rule reads no "null" as null.
    "unknown_rule_reads_no_null": (
        lambda m: m.setattr(
            standard,
            "campaign_argument_normalisation",
            lambda ledger: research_tools.ARGUMENT_NORMALISATION_V2,
        ),
        t.test_an_unknown_frozen_rule_reads_no_null,
        ASSERTION,
    ),
    # The wire names the corrected field.
    "wire_names_the_field": (
        lambda m: m.setattr(
            standard.AdapterFailure, "field", property(lambda self: None)
        ),
        t.test_the_mcp_tool_names_the_refused_practice_field,
        ASSERTION,
    ),
    # ... on the Tasks start too.
    "tasks_start_names_the_field": (
        lambda m: m.setattr(
            standard.AdapterFailure, "field", property(lambda self: None)
        ),
        lambda tmp: _with_monkeypatch(
            t.test_the_tasks_start_names_the_refused_practice_field
        )(tmp),
        ASSERTION,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_guard_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard, failure = MUTATIONS[name]
    guard(tmp_path / "intact")  # passes with the guard in place
    disable(monkeypatch)
    with pytest.raises(failure):
        guard(tmp_path / "mutated")
