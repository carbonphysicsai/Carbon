"""Two research-tool findings from the M1 rehearsal (2026-10-21).

- A Graphite planner's workspace calls were refused workspace_field_missing
  29 times: run_python without hypothesis/expected_effect inside
  arguments_json (the call already carries both), read_file without offset
  and count. A new plan freezes argument-normalisation.v3, which fills
  exactly those fields and never changes a field that was sent.
- With no backbone catalog entry installed, every catalog practice was
  refused backend_not_served with an empty list. It is now refused
  catalog_not_installed, which names the miner's install step.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_lp_prod_research_tools import BATTERY, ledger, refused

from carbon.development_session.profile import canonical
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import (
    ARGUMENT_NORMALISATION_V2,
    ARGUMENT_NORMALISATION_V3,
    ResearchMinerTools,
    frozen_argument_normalisation,
    normalised_task_arguments,
)


def workspace(action, arguments, **call):
    return {
        "kind": "workspace",
        "strategy_json": None,
        "action": action,
        "arguments_json": (
            arguments if type(arguments) is str else json.dumps(arguments)
        ),
        "hypothesis": "inspect the public inputs",
        "expected_effect": "a corrected request",
        **call,
    }


def _arguments(args):
    return json.loads(args["arguments_json"])


@pytest.mark.parametrize("action", ["run_python", "run_julia"])
def test_v3_fills_a_script_s_text_fields_from_the_call(action):
    sent = workspace(action, {"source": "print(1)", "files": []})
    read = normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V3)
    assert _arguments(read) == {
        "source": "print(1)",
        "files": [],
        "hypothesis": "inspect the public inputs",
        "expected_effect": "a corrected request",
    }
    # What was sent is never changed: it is what is journalled and bound.
    assert _arguments(sent) == {"source": "print(1)", "files": []}


def test_v3_never_replaces_a_field_that_was_sent():
    sent = workspace(
        "run_python",
        {"source": "x", "files": [], "hypothesis": "mine", "expected_effect": "mine"},
    )
    assert normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V3) == sent
    one = workspace("run_python", {"source": "x", "files": [], "hypothesis": "mine"})
    filled = _arguments(normalised_task_arguments(one, ARGUMENT_NORMALISATION_V3))
    assert filled["hypothesis"] == "mine"
    assert filled["expected_effect"] == "a corrected request"


def test_v3_reads_a_file_from_its_start_up_to_the_campaign_maximum():
    sent = workspace("read_file", {"name": "notes.txt"})
    read = normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V3, read_max=8192)
    assert _arguments(read) == {"name": "notes.txt", "offset": 0, "count": 8192}
    asked = workspace("read_file", {"name": "notes.txt", "offset": 10, "count": 5})
    assert normalised_task_arguments(asked, ARGUMENT_NORMALISATION_V3, 8192) == asked
    # No known maximum: count stays the caller's to send.
    unknown = _arguments(normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V3))
    assert unknown == {"name": "notes.txt", "offset": 0}


@pytest.mark.parametrize(
    "text",
    [
        '{"source": "a", "source": "b", "files": []}',  # a repeated key
        "[1, 2]",
        "not json",
    ],
)
def test_v3_leaves_an_unreadable_arguments_json_for_its_own_checks(text):
    sent = workspace("run_python", text)
    assert normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V3) == sent


def test_v2_and_other_actions_are_read_exactly_as_before():
    sent = workspace("run_python", {"source": "x", "files": []})
    assert normalised_task_arguments(sent, ARGUMENT_NORMALISATION_V2) == sent
    other = workspace("public_material", {"name": "objective"})
    assert normalised_task_arguments(other, ARGUMENT_NORMALISATION_V3) == other
    nulled = {**sent, "strategy_json": "null"}
    assert (
        normalised_task_arguments(nulled, ARGUMENT_NORMALISATION_V3)["strategy_json"]
        is None
    )


def test_a_plan_that_froze_v3_reads_as_v3():
    assert (
        frozen_argument_normalisation(
            {"provider": {"argument_normalisation": ARGUMENT_NORMALISATION_V3}}
        )
        == ARGUMENT_NORMALISATION_V3
    )


def test_with_nothing_installed_a_catalog_practice_names_the_install_step(tmp_path):
    meter = ledger(tmp_path / "ledger")

    class CatalogPractice:
        construction_mode = "direct"

        def backend_refusal(self, strategy):
            return ()

        def __call__(self, *args):
            pytest.fail("refused practice executed")

    composition = make_research_service(
        root=tmp_path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=CatalogPractice(),
    )
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    recipe = {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {},
    }
    args = {
        "kind": "practice",
        "strategy_json": canonical(recipe).decode(),
        "action": None,
        "arguments_json": None,
        "hypothesis": "h",
        "expected_effect": "e",
    }
    try:
        result = refused(sdk, meter, args)
        assert (result["correction_code"], result["field"]) == (
            "catalog_not_installed",
            "strategy_json",
        )
        assert "scripts.dev.catalog_install" in result["correction"]
    finally:
        composition.tasks.close()
