"""A Graphite campaign that stopped on its own settings says so (M1 S19).

Campaign 55d5c8bf (2026-10-21) finished its plan, then "Build: stopped
(context ceiling)", and read COMPLETED with 0 practice runs. The campaign view
now names such a stop with its registered next step.
"""

from __future__ import annotations

import pytest

from scripts.dev.miner_launchpad import campaign_view as view
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS


def _section(stages):
    return view.graphite_section({"graphite": {"stages": stages, "mode": "FULL"}})


@pytest.mark.parametrize("code", view.EARLY_STOP_CODES)
def test_a_stop_on_the_campaigns_own_settings_is_named_with_its_step(code):
    section = _section(
        [
            {"stage": "plan", "state": "DONE", "code": None},
            {"stage": "build", "state": "STOPPED", "code": code},
        ]
    )
    early = section["ended_early"]
    assert early["stage"] == "build" and early["code"] == code
    assert early["next_step"] == view_next(code)


def view_next(code):
    from scripts.dev.miner_launchpad.supervisor import next_action

    return next_action(code)


def test_every_early_stop_code_has_its_own_next_step():
    assert set(view.EARLY_STOP_CODES) == {
        "context_ceiling",
        "compaction_failed",
        "graphite_plan_output_cap",
        "miner_ceiling_reached",
    }
    for code in view.EARLY_STOP_CODES:
        assert code in NEXT_ACTIONS, code


def test_the_context_ceiling_step_names_the_input_window_setting():
    assert "max_input_tokens" in NEXT_ACTIONS["context_ceiling"]


def test_an_ordinary_stop_or_a_finished_run_is_not_early():
    assert (
        _section([{"stage": "build", "state": "DONE", "code": None}])["ended_early"]
        is None
    )
    assert (
        _section(
            [{"stage": "plan", "state": "STOPPED", "code": "research_share_reached"}]
        )["ended_early"]
        is None
    )


@pytest.mark.parametrize("dimension", sorted(view.STOP_LIMITS))
def test_a_ceiling_stop_names_which_limit_stopped_it(dimension):
    # G1 (Validator): the page names the stopping limit for every dimension; a
    # time stop read as "a ceiling you set" (cmp-b526c4ec, 2026-10-23).
    section = _section(
        [
            {
                "stage": "plan",
                "state": "STOPPED",
                "code": "miner_ceiling_reached",
                "dimension": dimension,
            }
        ]
    )
    early = section["ended_early"]
    words, step = view.STOP_LIMITS[dimension]
    assert early["limit"] == words and early["next_step"] == step
    assert section["stages"][0]["dimension"] == dimension


def test_an_unknown_dimension_is_never_shown_and_keeps_the_generic_step():
    section = _section(
        [
            {
                "stage": "plan",
                "state": "STOPPED",
                "code": "miner_ceiling_reached",
                "dimension": "<script>",
            }
        ]
    )
    early = section["ended_early"]
    assert "limit" not in early and "dimension" not in section["stages"][0]
    assert early["next_step"] == view_next("miner_ceiling_reached")
