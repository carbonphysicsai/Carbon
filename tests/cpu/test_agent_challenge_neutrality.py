"""Shared agent paths assume no Challenge; Burgers' own text stays historical."""

import inspect
import re
from types import SimpleNamespace

import pytest

from carbon.development_session import agent as legacy_session
from carbon.development_session import burgers_research_prompt, research_tools
from carbon.development_session.profile import canonical
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    CHALLENGE_PROMPT,
    LEGACY,
    STOP_TOOL,
    binding,
)
from carbon.development_session.research_loop import (
    SELECTION_TOOL,
    CandidateChallengeRequired,
    candidate_record,
)

#: Terms that belong to Burgers' task, model family or exam rule.
BURGERS_TERMS = re.compile(
    r"burgers|\bFNO\b|three-replica|energy evolution|mean preservation",
    re.IGNORECASE,
)


def burgers_terms(text):
    return sorted({match.group(0).lower() for match in BURGERS_TERMS.finditer(text)})


def test_a_challenge_campaign_prompt_and_tools_name_nothing_of_burgers():
    battery_sdk = SimpleNamespace(composition=SimpleNamespace(executor=None))
    surface = canonical(
        [research_tools.tools_for_sdk(battery_sdk), SELECTION_TOOL, STOP_TOOL]
    ).decode()
    assert burgers_terms(CHALLENGE_PROMPT) == []
    assert burgers_terms(surface) == []


def test_the_shared_tool_module_carries_no_burgers_text_or_default():
    source = inspect.getsource(research_tools)
    # Its one mention is the docstring saying Burgers records its own Challenge.
    assert burgers_terms(source.replace("records Burgers for", "")) == []
    assert not hasattr(research_tools, "PROMPT")
    assert not hasattr(research_tools, "CHALLENGE")


def test_the_scan_finds_burgers_where_it_really_is():
    """Specimen: the check above could have failed."""
    assert "burgers" in burgers_terms(legacy_session.PROMPT)
    assert "fno" in burgers_terms(burgers_research_prompt.BURGERS_PROMPT)
    assert "three-replica" in burgers_terms(burgers_research_prompt.BURGERS_PROMPT)


def test_historical_burgers_bindings_are_byte_identical():
    """Frozen Burgers manifests record these digests; resume compares them."""
    assert binding(LEGACY)["prompt_digest"] == (
        "sha256:c5fa96176cc176a1d3966c9808961de94f2909e3542feb4ceef7799658b4fadc"
    )
    assert binding(AUTONOMOUS)["prompt_digest"] == (
        "sha256:6f40ebae4ffeffd3bafc4851fd97cf69ac875a7bb143ec5eabe6b77bf2f5789d"
    )


def test_a_composition_that_names_no_challenge_is_refused_not_given_burgers():
    sdk = research_tools.ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=SimpleNamespace(),
        ledger=None,
        owner="miner",
    )
    with pytest.raises(ValueError, match="names no Challenge"):
        _ = sdk.challenge
    named = research_tools.ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=SimpleNamespace(challenge="battery-key"),
        ledger=None,
        owner="miner",
    )
    assert named.challenge == "battery-key"


BURGERS_RECIPE = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"width": 16},
}


@pytest.mark.parametrize(
    "strategy",
    [
        {k: v for k, v in BURGERS_RECIPE.items() if k != "challenge_id"},
        {**BURGERS_RECIPE, "challenge_id": None},
        {**BURGERS_RECIPE, "challenge_id": ""},
        {**BURGERS_RECIPE, "challenge_id": 7},
        None,
        "burgers-dynamics-v1",
    ],
)
def test_a_candidate_without_its_challenge_is_refused(strategy):
    with pytest.raises(CandidateChallengeRequired):
        candidate_record(strategy, "practiced", False)


def test_a_candidate_naming_its_challenge_is_recorded():
    record = candidate_record(BURGERS_RECIPE, "practiced", False)
    assert record["status"] == "SELECTED"
    assert record["strategy"] == BURGERS_RECIPE
    assert record["final_evidence"] is False
