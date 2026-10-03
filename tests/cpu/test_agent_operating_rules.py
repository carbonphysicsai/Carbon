"""The research agent is told every operating rule before it can hit one.

OWNER-BATTERY-V2-DISCLOSURE-01, items 3-7. Each stated value is checked
against the value that enforces it, so the instructions cannot drift from the
rules. Operating rules only: nothing here is exam material.
"""

import re

import numpy as np
import pytest

from carbon.development_session.contracts import strategy_limits
from carbon.development_session.model_provider import DEFAULT_SELECTION
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    AUTONOMOUS_PROMPT,
    CHALLENGE_PROMPT,
    CHALLENGE_PROMPT_V2,
    CONTEXT_RESERVE_TOKENS,
    FINISH_NOTICE_CALLS,
    FREE_TEXT_RULE,
    LEGACY,
    MAX_PROVIDER_CALLS,
    MAX_RESEARCH_TRIALS,
    MAX_TOOL_ARGUMENT_BYTES,
    MAX_WORKSPACE_ARGUMENT_BYTES,
    PARALLEL_CALLS,
    PARALLEL_CALLS_V2,
    PROMPT,
    SELECTION_RULE,
    binding,
    burgers_v2_rules,
    every_call_per_turn,
    one_call_per_turn,
    operating_rules,
    prompt_for,
)


def test_the_challenge_prompt_carries_the_operating_rules():
    assert operating_rules() in CHALLENGE_PROMPT
    assert operating_rules(PARALLEL_CALLS_V2) in CHALLENGE_PROMPT_V2


#: The prompts and policy bindings frozen campaigns recorded before LP-PROD-A,
#: computed on main at 4be2642c. A campaign frozen under `PARALLEL_CALLS` or no
#: rule must replay byte-identically, so these never change.
FROZEN = {
    "challenge_prompt": "sha256:21669f272a8d715e1d5a361684969d3a9f8a25e012fca2a92c00c4b3b285a477",
    "autonomous_prompt": "sha256:6f40ebae4ffeffd3bafc4851fd97cf69ac875a7bb143ec5eabe6b77bf2f5789d",
    "legacy_prompt": "sha256:c5fa96176cc176a1d3966c9808961de94f2909e3542feb4ceef7799658b4fadc",
    "operating_rules": "sha256:5c875c88f9bc8093b4fc5d2bfed1bc3f2ae20e5ab35ea77a57d89240e0ebcf44",
    "battery_binding": "sha256:334ccb7818c0c3f7c1caa7b904e893c9dfef98e07038681d90dda5eec78c9b14",
    "legacy_binding": "sha256:b34c71ba6e66ae306f86ecbc42a8e056371b9e52f4ac4ff2d96f0f70c287827b",
    "autonomous_binding": "sha256:9515b9ed8dab4580c473383f886ad2ce3751230dcdcb7dc5530db8fe6268bdaf",
}


def test_v1_and_historical_prompts_replay_byte_identically():
    from carbon.battery.challenge import CHALLENGE

    def text(value):
        return digest(value.encode())

    assert text(CHALLENGE_PROMPT) == FROZEN["challenge_prompt"]
    assert text(AUTONOMOUS_PROMPT) == FROZEN["autonomous_prompt"]
    assert text(PROMPT) == FROZEN["legacy_prompt"]
    assert text(operating_rules()) == FROZEN["operating_rules"]
    assert text(operating_rules(PARALLEL_CALLS)) == FROZEN["operating_rules"]
    for rule in (None, PARALLEL_CALLS):
        assert prompt_for(AUTONOMOUS, CHALLENGE, rule) == CHALLENGE_PROMPT
        assert prompt_for(AUTONOMOUS, None, rule) == AUTONOMOUS_PROMPT
        assert prompt_for(LEGACY, None, rule) == PROMPT
        for (policy, challenge), name in (
            ((AUTONOMOUS, CHALLENGE), "battery_binding"),
            ((LEGACY, None), "legacy_binding"),
            ((AUTONOMOUS, None), "autonomous_binding"),
        ):
            assert digest(canonical(binding(policy, challenge, rule))) == FROZEN[name]


def test_a_v2_plan_states_the_v2_rules():
    from carbon.battery.challenge import CHALLENGE

    assert prompt_for(AUTONOMOUS, CHALLENGE, PARALLEL_CALLS_V2) == CHALLENGE_PROMPT_V2
    v2 = operating_rules(PARALLEL_CALLS_V2)
    assert every_call_per_turn() in v2 and one_call_per_turn() not in v2
    assert one_call_per_turn() in operating_rules()
    # Burgers prompts gain only what v2 changes, after their own text.
    for policy, prompt in ((LEGACY, PROMPT), (AUTONOMOUS, AUTONOMOUS_PROMPT)):
        stated = prompt_for(policy, None, PARALLEL_CALLS_V2)
        assert stated == prompt + burgers_v2_rules(policy)
        assert every_call_per_turn() in stated and SELECTION_RULE in stated
        assert (FREE_TEXT_RULE in stated) == (policy == AUTONOMOUS)
    binding_v2 = binding(AUTONOMOUS, CHALLENGE, PARALLEL_CALLS_V2)
    assert binding_v2["prompt_digest"] == digest(CHALLENGE_PROMPT_V2.encode())


def test_every_v2_stated_number_is_the_enforced_one():
    """Each value the v2 rules state is checked against the code that
    enforces it: the argument bound against `research_tools._json` (in
    `test_research_loop_recoverable`) and the workspace bound here, against
    the record that refuses it."""
    from carbon.research.model import DevelopmentWorkspaceTaskSpecV1

    rules = operating_rules(PARALLEL_CALLS_V2)
    for phrase in (
        f"allows {MAX_PROVIDER_CALLS} model calls",
        (
            "Starting a practice, run_python or run_julia task spends one of "
            f"{MAX_RESEARCH_TRIALS} research-trial slots"
        ),
        f"at most {MAX_TOOL_ARGUMENT_BYTES} bytes of JSON",
        f"arguments_json at most {MAX_WORKSPACE_ARGUMENT_BYTES} bytes",
        f"with {FINISH_NOTICE_CALLS} model calls left it says so",
        SELECTION_RULE,
        FREE_TEXT_RULE,
    ):
        assert phrase in rules, phrase

    def spec(size):
        body = '{"name":"' + "x" * (size - len('{"name":""}')) + '"}'
        return DevelopmentWorkspaceTaskSpecV1(
            "carbon.autoresearch.workspace.v1", "public_material", body
        )

    assert spec(MAX_WORKSPACE_ARGUMENT_BYTES).arguments_json
    with pytest.raises(ValueError):
        spec(MAX_WORKSPACE_ARGUMENT_BYTES + 1)
    assert FINISH_NOTICE_CALLS == 2  # OWNER-LAUNCHPAD-PROD-01: "2 calls left"


def test_every_stated_number_is_the_enforced_one():
    rules = operating_rules()
    limits = strategy_limits()
    default = DEFAULT_SELECTION.settings.max_input_tokens
    for phrase in (
        f"After {PARALLEL_CALLS['consecutive_limit']} consecutive turns",
        f"allows {MAX_PROVIDER_CALLS} model calls",
        f"one of {MAX_RESEARCH_TRIALS} research-trial slots",
        f"max_input_tokens minus {CONTEXT_RESERVE_TOKENS} tokens",
        f"({default - CONTEXT_RESERVE_TOKENS} tokens at the default {default})",
        f"{limits.max_object_members} members in any JSON object",
        f"{limits.max_list_items} items in any list",
        f"{limits.max_total_value_nodes} values in total",
        f"{limits.max_string_utf8_bytes} UTF-8 bytes in any string",
        f"{limits.max_object_key_utf8_bytes} UTF-8 bytes in any object key",
        f"{limits.max_strategy_identity_bytes} bytes of canonical strategy",
    ):
        assert phrase in rules, phrase


def test_the_loop_enforces_the_stated_call_and_trial_counts():
    import inspect

    from carbon.development_session import research_loop

    source = inspect.getsource(research_loop.run_epoch)
    # The shared cap stands unless a closed role supplies its own
    # (GRAPHITE-D26); both the loop and the plan use the same value.
    flat = " ".join(source.replace("(", " ").replace(")", " ").split())
    assert (
        "call_limit = MAX_PROVIDER_CALLS if max_provider_calls is None "
        "else max_provider_calls" in flat
    )
    assert "range(call_limit)" in source
    assert '"max_provider_calls": call_limit' in source
    assert "min(MAX_RESEARCH_TRIALS," in source
    # Specimen: the literals the constants replaced are gone.
    assert not re.search(r"range\(48\)|min\(8,", source)


def test_both_admission_checks_hold_back_the_stated_reserve():
    import inspect

    from carbon.development_session import research_agent, research_loop

    for source in (
        inspect.getsource(research_loop.run_epoch),
        inspect.getsource(research_agent._request_once),
    ):
        assert "max_input_tokens - CONTEXT_RESERVE_TOKENS" in source
        assert not re.search(r"max_input_tokens\s*-\s*\d", source)


EXAM_MARKERS = ("seed", "hidden case", "private", "final case", "verify case")


def _exam_markers(text):
    return {marker for marker in EXAM_MARKERS if marker in text.lower()}


def test_no_exam_material_is_named_in_the_rules():
    from carbon.battery import seeds

    assert _exam_markers(operating_rules()) == set()
    assert _exam_markers(operating_rules(PARALLEL_CALLS_V2)) == set()
    assert _exam_markers(burgers_v2_rules(AUTONOMOUS)) == set()
    # Specimen: the same check finds markers in text that is about exam
    # material, the private seed service's own description.
    assert {"seed", "private"} <= _exam_markers(seeds.__doc__)


def test_battery_discloses_its_declared_sampling_law():
    from carbon.battery.research import objective, population_and_sampling

    law = objective()["sampling_law"]
    population, _ = population_and_sampling()
    assert law["support"] == "four_input_box"
    assert law["base_measure"] == "uniform_over_input_box"
    assert law["support"] == population.support_contract.membership_rule_ref.object_id
    assert (
        law["base_measure"]
        == population.law_semantics.payload.base_measure_ref.object_id
    )


def test_the_stated_draw_rule_is_the_draw_rule():
    """Uniform within the bounds and rounded to 4 decimal places, as stated,
    checked on the draw function itself with a throwaway root."""
    import hashlib

    from carbon.battery import seeds
    from carbon.battery.challenge import INPUT_BOUNDS
    from carbon.battery.research import sampling_law

    class Root:
        _bytes = hashlib.sha256(b"test-only-root").digest()

    pin = seeds.seed_pin("sha256:" + "0" * 64, "sha256:" + "1" * 64)
    context = seeds._context(Root(), pin)
    law = sampling_law()
    for index in range(200):
        case = seeds.draw_inputs(context, "practice", index)
        for name, value in case.items():
            lo, hi = law["support_bounds"][name]
            assert (lo, hi) == INPUT_BOUNDS[name]
            assert lo <= value <= hi
            assert value == float(np.round(value, 4))
    # Specimen: an unrounded uniform draw fails the same check.
    raw = 0.5 + 1.5 * 0.123456789
    assert raw != float(np.round(raw, 4))
