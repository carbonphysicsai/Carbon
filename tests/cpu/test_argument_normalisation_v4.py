"""Argument normalisation v4 (M1 E2E 2026-10-22, F1): Qwen3.5-397B sent the
string "None" for JSON null, so a practice call with arguments_json "None"
was refused practice_recipe_required and a workspace call with strategy_json
"None" workspace_recipe_forbidden; Graphite never practised. v4 reads each
common spelling of null as JSON null wherever v3 reads "null"; v1-v3 are
unchanged, and new Graphite plans freeze v4."""

from __future__ import annotations

import pytest

from carbon.development_session.research_tools import (
    ARGUMENT_NORMALISATION_V3,
    ARGUMENT_NORMALISATION_V4,
    ARGUMENT_NORMALISATIONS,
    NULL_SPELLINGS_V4,
    normalised_task_arguments,
)

RECIPE = '{"schema": "carbon.construction-recipe.v1"}'


def _practice(value):
    return {
        "kind": "practice",
        "strategy_json": RECIPE,
        "action": value,
        "arguments_json": value,
    }


def _workspace(value):
    return {
        "kind": "workspace",
        "strategy_json": value,
        "action": "inventory",
        "arguments_json": "{}",
    }


def test_v4_is_registered_after_v3():
    assert ARGUMENT_NORMALISATIONS[2:4] == (
        ARGUMENT_NORMALISATION_V3,
        ARGUMENT_NORMALISATION_V4,
    )
    assert NULL_SPELLINGS_V4 == {"null", "Null", "NULL", "None", "none"}


@pytest.mark.parametrize("value", sorted(NULL_SPELLINGS_V4))
def test_every_null_spelling_is_json_null_under_v4(value):
    read = normalised_task_arguments(_practice(value), ARGUMENT_NORMALISATION_V4)
    assert read["action"] is None and read["arguments_json"] is None
    assert read["strategy_json"] == RECIPE
    read = normalised_task_arguments(_workspace(value), ARGUMENT_NORMALISATION_V4)
    assert read["strategy_json"] is None


@pytest.mark.parametrize("value", ["None", "none", "NULL", "Null"])
def test_v3_still_reads_only_the_string_null(value):
    sent = _practice(value)
    assert normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V3) == sent
    sent = _workspace(value)
    assert normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V3) == sent


def test_a_practice_recipe_spelled_null_is_still_not_a_recipe():
    sent = {**_practice("None"), "strategy_json": "None"}
    read = normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V4)
    # The recipe field is never nulled on practice: its own check refuses it.
    assert read["strategy_json"] == "None"


def test_other_strings_are_left_as_sent():
    sent = _practice("nothing")
    assert normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V4) == sent
