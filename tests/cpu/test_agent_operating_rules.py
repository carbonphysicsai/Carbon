"""The research agent is told every operating rule before it can hit one.

OWNER-BATTERY-V2-DISCLOSURE-01, items 3-7. Each stated value is checked
against the value that enforces it, so the instructions cannot drift from the
rules. Operating rules only: nothing here is exam material.
"""

import re

import numpy as np

from carbon.development_session.contracts import strategy_limits
from carbon.development_session.model_provider import DEFAULT_SELECTION
from carbon.development_session.research_agent_policy import (
    CHALLENGE_PROMPT,
    CONTEXT_RESERVE_TOKENS,
    MAX_PROVIDER_CALLS,
    MAX_RESEARCH_TRIALS,
    PARALLEL_CALLS,
    operating_rules,
)


def test_the_challenge_prompt_carries_the_operating_rules():
    assert operating_rules() in CHALLENGE_PROMPT


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
