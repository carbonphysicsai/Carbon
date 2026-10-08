"""LAUNCHPAD-FINDINGS-F8-F9: the two defects the 2026-10-08 Launchpad smoke run
found (docs/development/evidence/launchpad-acceptance-2026-10-07/FINDINGS.md).

LA-F9. Every practice result was withheld from Graphite as
`REFUSED_PROTECTED_MATERIAL_IN_RESULT`. The only match was the checkout deny
prefix `docs/development/evidence/` in the result's
`safety.material.path`: the public PRACTICE set's own repository path, pinned
beside its sha256. That exact path is now exempt from the deny rule, and
nothing else is: these tests hold that official seeds, hidden cases,
verification references, the sealed tuning set, canaries, other evidence paths
and the public path inside any longer string are still refused.

LA-F8. Graphite's stages stopped at the context ceiling: the default input
window is 65,536 tokens, and Carbon's sound bound counts a token for every byte
of new tool output. The model's published context (1,048,576 for the default
Engy model) is now one record the Launchpad reads, and both the capability
document and the launch options say so before a launch spends. No default
changes and nothing new is refused.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from carbon.agent_campaign.graphite import protected_material as pm
from carbon.agent_campaign.graphite import roles
from carbon.agent_campaign.graphite.miner import edition as editions
from carbon.agent_campaign.graphite.miner import toolbox
from carbon.development_session import model_provider as mp
from carbon.development_session.research_agent import CONTEXT_RESERVE_TOKENS
from carbon.development_session.research_loop import CONTEXT_CEILING
from scripts.dev.miner_launchpad import capabilities, runner
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS, next_action

BATTERY_PRACTICE = (
    "docs/development/evidence/exam-design-2026-09-24/refs-a-part2/out/records.jsonl"
)
SHA = "7d3955b278b0aab08fe0abc530eded6511531d086e7f0cd94f6c09dc3e98fb8d"


def practice_result(path=BATTERY_PRACTICE):
    """The shape of the run's withheld battery practice result (keys as
    recorded; values synthetic except the public path and its digest)."""
    return {
        "schema": "carbon.battery.practice-feedback.v3",
        "adaptively_seen": True,
        "final_exam": False,
        "official_eligible": False,
        "scientific_qualification": False,
        "seed_source": "carbon_retained_randomness",
        "summary": {"score": 0.5},
        "safety": {
            "schema": "carbon.practice-safety-feedback.v1",
            "challenge": "battery-fastcharge-ageing-development-v1",
            "feedback_only": True,
            "material": {"path": path, "sha256": SHA},
            "metrics": {"B2": {"feedback_only": True, "near_optimism_bands": 1.0}},
            "unmeasured": 0,
            "unresolved": 9,
        },
    }


# --- LA-F9: the public practice path, exactly -------------------------------


def test_the_exempt_paths_are_each_challenges_own_public_practice_path():
    from carbon.battery.practice import PRACTICE_SOURCE_PATH
    from carbon.cold_plate.challenge import PRACTICE_PATH as COLD_PLATE
    from carbon.motor.challenge import PRACTICE_PATH as MOTOR

    assert pm.PUBLIC_PRACTICE_PATHS == {PRACTICE_SOURCE_PATH, MOTOR, COLD_PLATE}
    assert BATTERY_PRACTICE == PRACTICE_SOURCE_PATH
    # Each is exempt only because the deny rule matched it; no marker does.
    for path in pm.PUBLIC_PRACTICE_PATHS:
        assert pm.boundaries._denied(path.lower())
        assert not any(marker in path.lower() for marker in pm.PROTECTED_MARKERS)


@pytest.mark.parametrize("path", sorted(pm.PUBLIC_PRACTICE_PATHS))
def test_a_practice_result_naming_its_public_material_is_served(path):
    result = practice_result(path)
    assert pm.protected(result) is False
    assert pm.marker_classes(result) == []
    # Also inside JSON carried in a string, as a read_file returns a trial.
    assert pm.protected({"content_utf8": json.dumps(result)}) is False


@pytest.mark.parametrize(
    "text",
    [
        # Anything else under the evidence prefix, including the private
        # battery reference pools and sealed confirmation material.
        "docs/development/evidence/exam-design-2026-09-24/refs-b/out/battery_refs/",
        "docs/development/evidence/exam-design-2026-09-24/refs-a-part2/out/config.json",
        "docs/development/evidence/ev5-2026-10-03",
        "docs/development/evidence/motor-pools-v1/baselines.json",
        "docs/development/evidence/motor-pools-v1/train.jsonl",
        # The public path with anything before or after it, or recased.
        BATTERY_PRACTICE + ".bak",
        BATTERY_PRACTICE + " ",
        BATTERY_PRACTICE.upper(),
        "docs/development/evidence/motor-pools-v1/practice.jsonl/../pools.json",
        # Graphite's markers, anywhere.
        "official_seed",
        "derived-seed 12",
        "draw_id",
        "hidden_case",
        "verification_reference",
        "graphite-tuning",
        "tuning_set",
        "private validator",
        pm.boundaries.CANARY_PREFIX + "abc",
        # The other checkout deny rules.
        ".agent/DECISIONS.md",
        "tests/cpu/x.py",
        "carbon/agent_campaign/graphite/tools.py",
        "my secret",
        "credential.json",
        "ev4 freeze",
    ],
)
def test_protected_material_is_still_refused(text):
    assert pm.protected({"x": text}) is True
    assert pm.protected(practice_result(path=text)) is True


def test_the_public_path_never_launders_a_marker_beside_it():
    result = practice_result()
    result["safety"]["note"] = "hidden_case 7"
    assert pm.protected(result) is True
    assert pm.marker_classes(result) == ["exam_material"]
    result = practice_result()
    result["safety"]["material"]["other"] = "docs/development/evidence/ev5-2026-10-03"
    assert pm.protected(result) is True


class FakeLedger:
    def __init__(self):
        self.notes = []

    def note(self, *, owner, kind, body):
        self.notes.append((kind, body))


class FakeSDK:
    def __init__(self, result):
        self.result = result
        self.dispatched = []

    async def call(self, name, arguments, identity):
        self.dispatched.append(name)
        return self.result


def constructor_call(result):
    ledger, sdk = FakeLedger(), FakeSDK(result)
    tools = toolbox.MinerToolbox(
        role=editions.CONSTRUCTOR,
        sdk=sdk,
        literature=None,
        ledger=ledger,
        owner="alice",
        stage="build",
    )
    arguments = {
        "kind": "practice",
        "action": None,
        "hypothesis": "fixture",
        "expected_effect": "fixture",
        "strategy_json": "{}",
    }
    answer = asyncio.run(tools.call(editions.START_TASK, arguments, "tool-1"))
    return answer, sdk, ledger


def test_the_miner_toolbox_returns_a_practice_result_to_its_agent():
    result = practice_result()
    answer, sdk, ledger = constructor_call(result)
    assert answer == result
    assert sdk.dispatched == [editions.START_TASK]
    assert ledger.notes == []


def test_the_miner_toolbox_still_withholds_a_result_naming_protected_material():
    answer, _sdk, ledger = constructor_call(
        practice_result(path="docs/development/evidence/graphite-tuning-set/x.json")
    )
    assert answer["status"] == toolbox.REFUSED_RESULT
    assert "graphite-tuning" not in json.dumps(answer)
    assert [kind for kind, _body in ledger.notes] == ["refusal"]


# --- LA-F8: the input window, said before a launch spends --------------------


def test_the_context_table_is_one_record_read_by_graphite_and_the_launchpad():
    assert roles.ENGY_CONTEXT_TOKENS is mp.ENGY_CONTEXT_TOKENS
    assert roles.ENGY_CONTEXT_OBSERVED == mp.ENGY_CONTEXT_OBSERVED == "2026-10-04"
    # GRAPHITE-D34's values, unchanged by the move.
    assert mp.ENGY_CONTEXT_TOKENS == {
        "deepseek-v4-flash-0731": 1048576,
        "qwen3.8-27b": 1001536,
        "glm-5.3-flash": 262144,
        "glm-5.2": 262144,
        "kimi-k3": 1113088,
    }
    assert mp.published_context("engy-chat", mp.ENGY_DEFAULT_MODEL) == {
        "tokens": 1048576,
        "reference": mp.ENGY_MODELS_URL,
        "observed": "2026-10-04",
    }
    # Never guessed for a model or provider Carbon records none for.
    assert mp.published_context("openai-responses", mp.GPT5_MINI) is None
    assert mp.published_context("engy-chat", "unlisted-model") is None


def test_the_input_bounds_are_selects_own():
    assert mp.INPUT_TOKEN_BOUNDS == (16384, 1048576)
    credential = {"kind": "file", "reference": "/nonexistent/fixture.key"}
    for bad in (16383, 1048577):
        with pytest.raises(mp.ModelSelectionRefused):
            mp.select(
                provider_id="engy-chat",
                credential=credential,
                settings={"max_input_tokens": bad},
            )
    for good in mp.INPUT_TOKEN_BOUNDS:
        chosen = mp.select(
            provider_id="engy-chat",
            credential=credential,
            settings={"max_input_tokens": good},
        )
        assert chosen.settings.max_input_tokens == good


def capability_model():
    options = {
        "agents": [{"value": "graphite", "availability": "available"}],
        "model_providers": [
            {"provider_id": provider_id, "availability": "available"}
            for provider_id in mp.ADAPTERS
        ],
    }
    return capabilities._model(options, capabilities.NO_PROFILE, {})


def test_the_capability_document_states_the_window_and_published_context():
    window = capability_model()["input_window"]
    assert window["launch_field"] == "model_settings.max_input_tokens"
    assert window["bounds"] == list(mp.INPUT_TOKEN_BOUNDS)
    assert window["default"] == mp.DEFAULT_SETTINGS.max_input_tokens == 65536
    assert window["admission_ceiling_at_default"] == 65536 - CONTEXT_RESERVE_TOKENS
    assert window["published_context"], "the specimen offers an Engy model"
    for provider_id, models in window["published_context"].items():
        for model_id, shown in models.items():
            assert shown == mp.published_context(provider_id, model_id)
    advisory = window["graphite_advisory"]
    assert advisory["code"] == capabilities.GRAPHITE_INPUT_WINDOW
    assert advisory["next_step"] == NEXT_ACTIONS[advisory["code"]]


def test_the_launch_options_carry_the_advisory_and_change_no_default():
    block = runner.graphite_options({})["input_window"]
    assert block == {
        "launch_field": "model_settings.max_input_tokens",
        "default": mp.DEFAULT_SETTINGS.max_input_tokens,
        "advisory": "graphite_input_window_too_small",
        "next_step": NEXT_ACTIONS["graphite_input_window_too_small"],
    }
    assert mp.DEFAULT_SETTINGS.max_input_tokens == 65536


def test_the_stop_code_has_its_own_next_step_naming_the_real_values():
    assert CONTEXT_CEILING == "context_ceiling"
    for code in (CONTEXT_CEILING, "graphite_input_window_too_small"):
        step = next_action(code)
        assert step == NEXT_ACTIONS[code]
        assert "model_settings.max_input_tokens" in step
    advisory = NEXT_ACTIONS["graphite_input_window_too_small"]
    assert f"minus {CONTEXT_RESERVE_TOKENS:,}" in advisory
    assert f"default {mp.DEFAULT_SETTINGS.max_input_tokens:,}" in advisory
