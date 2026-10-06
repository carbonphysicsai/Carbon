"""LAUNCHPAD-PAGE-USABILITY-01: the Launch page's output cap (C3) and what a
miner can do while no evaluation endpoint is published (C10).

The page's own behaviour runs in tests/cpu/control_center_page_check.cjs.
These hold what it reads: the capability document's output cap is the
runner's own bounds and defaults, and the text both doors read for a submit
with no validator intake says what still works and what to do next, without
claiming any readiness.
"""

from __future__ import annotations

from carbon.development_session.model_provider import (
    ADAPTERS,
    OUTPUT_DEFAULT_V2,
    OUTPUT_TOKEN_BOUNDS,
    output_maximum,
    select,
)
from carbon.miner_mcp.mcp_operations import PREFIX, make_operation_tools
from scripts.dev.miner_launchpad import capabilities
from scripts.dev.miner_launchpad.operations import FIELDS, OPERATIONS
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

CREDENTIAL = {"kind": "file", "reference": "/nonexistent/fixture.key"}


def _model():
    options = {
        "agents": [{"value": "graphite", "availability": "available"}],
        "model_providers": [
            {"provider_id": provider_id, "availability": "available"}
            for provider_id in ADAPTERS
        ],
    }
    return capabilities._model(options, capabilities.NO_PROFILE, {})


def test_the_output_cap_is_the_runners_bounds_and_defaults():
    model = _model()
    cap = model["output_cap"]
    assert cap["launch_field"] == "model_settings.max_output_tokens"
    assert cap["bounds"] == list(OUTPUT_TOKEN_BOUNDS)
    offered = [
        (row["id"], entry["id"])
        for row in model["providers"]
        for entry in row["models"]
    ]
    assert offered, "the specimen offers models"
    for provider_id, model_id in offered:
        recorded = output_maximum(provider_id, model_id)
        assert cap["defaults"][provider_id][model_id] == {
            "max_output_tokens": recorded["max_output_tokens"],
            "basis": recorded["basis"],
        }


def test_the_default_shown_is_what_a_launch_without_a_cap_gets():
    cap = _model()["output_cap"]
    for provider_id, models in cap["defaults"].items():
        for model_id, shown in models.items():
            chosen = select(
                provider_id=provider_id,
                model_id=model_id,
                credential=CREDENTIAL,
                output_default=OUTPUT_DEFAULT_V2,
            )
            assert chosen.settings.max_output_tokens == shown["max_output_tokens"]


def test_the_cap_travels_in_the_existing_launch_field():
    # The public launch schema already carries it; nothing new is invented.
    assert "model_settings" in OPERATIONS["launch"].optional
    tools = {tool.name: tool for tool in make_operation_tools(object())}
    assert "model_settings" in tools[PREFIX + "launch"].parameters["properties"]
    assert "model_settings" in capabilities._launch()["browser_sends"]
    # Both doors read the bounds the runner validates against.
    low, high = OUTPUT_TOKEN_BOUNDS
    assert f"from {low:,} to {high:,}" in FIELDS["model_settings"][1]


def test_a_submit_with_no_intake_says_what_works_and_what_to_do():
    text = NEXT_ACTIONS["evaluation_unavailable"]
    for said in (
        "frozen candidate is kept",
        "launch, practise, observe, and stop or pause",
        "carbon_setup_review",
        "submit again",
    ):
        assert said in text, said
    tools = {tool.name: tool for tool in make_operation_tools(object())}
    submit = tools[PREFIX + "submit"].description
    assert "evaluation_unavailable" in submit
    assert "launched, practised, observed, stopped or paused" in submit
    # Claim discipline (AGENTS.md section 16): no readiness or qualification.
    for words in (text, submit):
        lowered = words.lower()
        for claim in ("qualified", "ready", "production", "reward"):
            assert claim not in lowered, claim
