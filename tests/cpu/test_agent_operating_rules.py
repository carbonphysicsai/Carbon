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
    COMPACTION_ATTEMPTS,
    COMPACTION_SUMMARY_CHARACTERS,
    COMPACTION_V1,
    CONTEXT_RESERVE_TOKENS,
    FINISH_NOTICE_CALLS,
    FREE_TEXT_RULE,
    LEGACY,
    LIMITS_V2,
    MAX_PROVIDER_CALLS,
    MAX_RESEARCH_TRIALS,
    MAX_TOOL_ARGUMENT_BYTES,
    MAX_WORKSPACE_ARGUMENT_BYTES,
    PARALLEL_CALLS,
    PARALLEL_CALLS_V2,
    PROMPT,
    REMINDER,
    SELECTION_RULE,
    STOP_TOOL,
    argument_limits,
    binding,
    burgers_v2_rules,
    capture_limits_rule,
    context_rule,
    every_call_per_turn,
    free_text_rule,
    graphite_miner_reminder,
    graphite_miner_rules,
    limits_v2,
    one_call_per_turn,
    operating_rules,
    prompt_for,
    selection_rule,
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


#: The v2 texts campaigns froze from LP-PROD-A, computed on the Launchpad
#: wiring head (9bfd9add) before the Graphite miner edition's rules existed
#: (OWNER-GRAPHITE-MINER-01). A campaign frozen under `PARALLEL_CALLS_V2`
#: replays byte-identically, so these never change either.
FROZEN_V2 = {
    "challenge_prompt": "sha256:ea70ce29c34597f4c7241a139bfdcc472be1814ae72117ce98e89295a57fe063",
    "autonomous_prompt": "sha256:fcbc0e12f6563f9c10f1126fa238fcd7efd36a92f729b3f2b2ece77962296b8c",
    "legacy_prompt": "sha256:a06eb1cd82b7b62a36c2acaa619c027c7ef5c303fff4da0ef4fc29a04b07cbc8",
    "operating_rules": "sha256:37bd698263a7591515182a2e1d298d963068e3f1d729d0e3ab353031b04d332a",
    "battery_binding": "sha256:3e5586b54d55212e55b9300ce334cf2ec31af6da52897a5382a53c89a5027e64",
    "legacy_binding": "sha256:1993331332b6366f5f0034132814056b4da6466901b52152938d34adb6ee7ec7",
    "autonomous_binding": "sha256:2831ad2e60aaac253a6e35bbd38f6fb4d804150c440b880e4d6717ebc1b47519",
    "burgers_rules_legacy": "sha256:fcd1c26c83ce7fca54b482809e81ae143ad044d78cd19c61cc7fe30f475cabb3",
    "burgers_rules_autonomous": "sha256:eaeed773e3f15ddf0bf1f0bccf7e11ba8e1f42acc418d6271857709f71c15602",
    "argument_limits": "sha256:c6839bccb5107312ca776e1dc3af37975eb3887e48c7d73d33345c52e36e9371",
    "selection_rule": "sha256:5494a5a8db2dd70d82b7d1430facaf60b787cd1e29d1d1a5ba97904f090082b4",
    "free_text_rule": "sha256:629c5a4d7037e4c26714473f5c66dae89d155cb8f64e957da0cf16a768989cfa",
    "reminder": "sha256:2437805dc97bcfa6b8fb5bdd5a45e604d4a5a765371211c1436dff90f2db12cd",
}


def test_v2_texts_replay_byte_identically():
    from carbon.battery.challenge import CHALLENGE

    def text(value):
        return digest(value.encode())

    v2 = PARALLEL_CALLS_V2
    assert text(prompt_for(AUTONOMOUS, CHALLENGE, v2)) == FROZEN_V2["challenge_prompt"]
    assert text(prompt_for(AUTONOMOUS, None, v2)) == FROZEN_V2["autonomous_prompt"]
    assert text(prompt_for(LEGACY, None, v2)) == FROZEN_V2["legacy_prompt"]
    assert text(operating_rules(v2)) == FROZEN_V2["operating_rules"]
    for (policy, challenge), name in (
        ((AUTONOMOUS, CHALLENGE), "battery_binding"),
        ((LEGACY, None), "legacy_binding"),
        ((AUTONOMOUS, None), "autonomous_binding"),
    ):
        assert digest(canonical(binding(policy, challenge, v2))) == FROZEN_V2[name]
    assert text(burgers_v2_rules(LEGACY)) == FROZEN_V2["burgers_rules_legacy"]
    assert text(burgers_v2_rules(AUTONOMOUS)) == FROZEN_V2["burgers_rules_autonomous"]
    assert text(argument_limits()) == FROZEN_V2["argument_limits"]
    assert text(SELECTION_RULE) == FROZEN_V2["selection_rule"]
    assert text(FREE_TEXT_RULE) == FROZEN_V2["free_text_rule"]
    assert text(REMINDER) == FROZEN_V2["reminder"]
    # The epoch is the default unit: the shared texts are the historical ones.
    assert selection_rule() == SELECTION_RULE and free_text_rule() == FREE_TEXT_RULE
    assert context_rule() in operating_rules() and capture_limits_rule() in (
        operating_rules()
    )


def test_every_number_a_miner_role_is_told_is_the_enforced_one():
    """OWNER-GRAPHITE-MINER-01: a miner role is told every rule the loop
    enforces on it, from the values that enforce each."""
    limits = strategy_limits()
    rules = graphite_miner_rules(
        limits=limits_v2(calls_per_epoch=60, trials_per_epoch=4),
        compaction=COMPACTION_V1,
        select=True,
        stop=True,
        finish="graphite_record_plan",
    )
    percent = round(COMPACTION_V1["trigger_fraction"] * 100)
    kept = COMPACTION_V1["keep_last_turns"]
    for phrase in (
        every_call_per_turn("session"),
        "This session also allows at most 60 model calls",
        "at most 4 research-trial slots",
        "and so does each compaction request",
        f"when at most {FINISH_NOTICE_CALLS} model calls are left",
        f"max_input_tokens minus {CONTEXT_RESERVE_TOKENS} tokens",
        f"would pass {percent}% of that ceiling",
        f"holds more than {kept} turns",
        f"the last {kept} turns unchanged",
        (
            "in at most the characters Carbon's request states, never more than "
            f"{COMPACTION_SUMMARY_CHARACTERS} in all"
        ),
        "is accepted only if the conversation then fits under the ceiling",
        "When the last turns leave no room for a summary Carbon does not ask",
        f"after {COMPACTION_ATTEMPTS} requests",
        f"at most {MAX_TOOL_ARGUMENT_BYTES} bytes of JSON",
        f"arguments_json at most {MAX_WORKSPACE_ARGUMENT_BYTES} bytes",
        "and the session goes on.",
        selection_rule("session"),
        free_text_rule("session"),
        (
            "select a practiced recipe, finish with graphite_record_plan or stop "
            "with carbon_autoresearch_stop"
        ),
        f"{limits.max_strategy_identity_bytes} bytes of canonical strategy",
    ):
        assert phrase in rules, phrase
    # Unset caps leave only the campaign's ceilings, and say so.
    generous = graphite_miner_rules(limits=LIMITS_V2)
    assert (
        "There is no separate per-session model-call cap and no separate "
        "per-session research-trial cap." in generous
    )
    assert context_rule("session") in generous
    assert "Past the ceiling the session stops" in generous
    assert selection_rule("session") not in generous
    # No limits rule: the historical caps, stated as such.
    historical = graphite_miner_rules()
    assert (
        f"This session allows {MAX_PROVIDER_CALLS} model calls and "
        f"{MAX_RESEARCH_TRIALS} research-trial slots" in historical
    )
    reminder = graphite_miner_reminder(select=True, stop=True)
    assert "select a practiced recipe" in reminder
    assert "carbon_autoresearch_stop" in reminder
    assert _exam_markers(rules) == set() and _exam_markers(reminder) == set()
    assert STOP_TOOL["name"] == "carbon_autoresearch_stop"


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
    # A limits rule (OWNER-GRAPHITE-MINER-01) replaces both caps with its own,
    # where None leaves only the ledger's ceilings.
    assert 'call_limit = limits["calls_per_epoch"]' in source
    assert 'MAX_RESEARCH_TRIALS if limits is None else limits["trials_per_epoch"]' in (
        " ".join(source.split())
    )
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
