"""The Control Center under a live controller (LP-PROD-F, OWNER-LAUNCHPAD-PROD-01).

The owner, 2026-10-03: the miner front end is "our entire workforce facing
application", to be zero-friction and production-level. These tests hold the
page to that, through its own scripts, without a browser:
- a refresh redraws only what changed, and never the control under a hand:
  a pressed or hovered control, a field being typed into, an unsent edit;
- the Model step passes with the model setup chose, for a provider whose
  adapter lists none;
- a launch is held only while its outcome is unknown, retries with the
  current choices under the same key, and can be discarded;
- a refusal is shown with what to do, and a submit is "submitted" only once
  the campaign's record shows it admitted;
- Reconcile is in reach whenever the state needs it, with why;
- the Tools tab's freeze and submit keep one key until answered and report
  readable text;
- limits are typed in dollars and minutes; old campaign links resolve; the
  Connections page names the real MCP command.

The page scenarios run in Node (tests/cpu/control_center_page_check.cjs over
the small DOM in control_center_dom.cjs) when Node is installed. The
documents they read are built here, by the real capability, setup, options
and campaign-view code. No provider, chain, SSH or container is touched.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHPAD = ROOT / "scripts/dev/miner_launchpad"
CHECK = ROOT / "tests/cpu/control_center_page_check.cjs"
SETUP_MODEL = {"provider_id": "chutes", "model_id": "deepseek-ai/DeepSeek-V3-0324"}


def _plain(value):
    return json.loads(json.dumps(value, default=sorted))


def _open_options():
    """Every agent and provider available: the state a set-up profile reads."""
    from carbon.development_session.model_provider import ADAPTERS

    return {
        "agents": [
            {"value": "autonomous", "availability": "available"},
            {"value": "none", "availability": "available"},
        ],
        "model_providers": [
            {"provider_id": provider_id, "availability": "available"}
            for provider_id in ADAPTERS
        ],
    }


@pytest.fixture
def journey(tmp_path, monkeypatch):
    from scripts.dev.miner_launchpad.journey_fixture import journey_host

    root = tmp_path / "journey"
    root.mkdir(mode=0o700)
    host = journey_host(root, patch=monkeypatch.setattr)
    yield host
    host.close()


def _setup_document(tmp_path):
    """Setup's own state and offer, then a machine with Docker that does not
    hold the pinned GPU worker yet: the step that sends it."""
    from test_miner_launchpad_environment_setup import HOTKEY, Checks, Onboarding

    from scripts.dev.miner_launchpad import setup_operations
    from scripts.dev.miner_launchpad.environment_setup import REMOTE, EnvironmentSetup

    state = tmp_path / "setup-state"
    state.mkdir(mode=0o700)
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    setup.begin({"address": HOTKEY})
    document = _plain(
        {
            **setup.state(),
            "choices": setup.offered(),
            "status": setup_operations.status(
                setup, door=setup_operations.HTTP, campaigns=0
            ),
        }
    )
    document["steps"]["compute"] = {
        "checked": True,
        "choice": REMOTE,
        "remote_machine": {"transport": "ssh-docker", "destination": "me@box"},
        "check": {
            "remote": {"worker_image": "missing"},
            "gpu_image": "sha256:" + "e" * 64,
            "next_step": "send_worker",
        },
    }
    return document


@pytest.fixture
def documents(tmp_path, journey):
    from carbon.development_session.exam_environment import exam_environment
    from scripts.dev.miner_launchpad import capabilities, controller
    from scripts.dev.miner_launchpad.operations import describe, perform
    from scripts.dev.miner_launchpad.research_fixture import FixtureRunner

    caps = capabilities.control_center(journey)
    assert any(entry["selectable"] for entry in caps["challenges"])
    options = perform(journey, "options", {})
    fixture = FixtureRunner()
    try:
        view, run = fixture.view_document(), fixture.own()
    finally:
        fixture.close()
    opened = _open_options()
    setup_model = capabilities._model(
        opened, capabilities.NO_PROFILE, {"model_selection": SETUP_MODEL}
    )
    value = {
        "caps": caps,
        "caps_setup_model": {**caps, "model": setup_model},
        "options": options,
        "options_setup_model": {**options, "agents": opened["agents"]},
        "preflight": journey.preflight(),
        "operations": describe(),
        "catalog": controller.capability_catalog(),
        "exam": exam_environment(),
        "onboarding": {
            "network": "test",
            "netuid": 567,
            "mechanism": "registration",
            "cost": {"value": "NOT_READ"},
            "you_need": [],
            "carbon_never": [],
        },
        "view": view,
        "run": run,
        "setup_send": _setup_document(tmp_path),
    }
    path = tmp_path / "control-center-documents.json"
    path.write_text(json.dumps(_plain(value)))
    return path


# --- The page, through its own scripts ------------------------------------------


def test_the_page_behaves_under_a_live_controller(documents):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    result = subprocess.run(
        [node, str(CHECK), str(documents)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    passed = json.loads(result.stdout)["passed"]
    # Every scenario the script declares ran and passed; the count is the
    # script's own, so a scenario cannot silently drop out.
    source = CHECK.read_text()
    declared = len(re.findall(r"^scenario\(", source, re.MULTILINE))
    # The Reconcile scenario is declared once per state it covers.
    looped = re.search(r"for \(const stateName of (\[[^\]]*\])\)", source)
    declared += len(json.loads(looped.group(1)))
    assert len(passed) == declared and len(set(passed)) == declared, passed


def test_the_page_scripts_set_text_and_never_parse_html():
    for name in ("app.js", "research_view.js", "research_tools.js"):
        source = (LAUNCHPAD / name).read_text()
        for pattern in ("innerHTML", "outerHTML", "insertAdjacentHTML", "DOMParser"):
            assert pattern not in source, (name, pattern)


# --- The capability document ------------------------------------------------------


def test_setup_model_is_offered_for_a_provider_that_lists_none():
    from carbon.development_session.model_provider import (
        ADAPTERS,
        ENGY_DEFAULT_MODEL,
    )
    from scripts.dev.miner_launchpad import capabilities

    # The gap: these adapters list no model, so their Model step had nothing
    # to choose.
    for provider_id in ("chutes", "anthropic", "openai-compatible-chat"):
        assert not ADAPTERS[provider_id].summary_models(), provider_id
    selection = {
        **SETUP_MODEL,
        "endpoint": "https://example.invalid/v1",
        "published_pricing": {"input_nano": 1},
    }
    model = capabilities._model(
        _open_options(), capabilities.NO_PROFILE, {"model_selection": selection}
    )
    rows = {row["id"]: row for row in model["providers"]}
    assert rows["chutes"]["models"] == [
        {"id": SETUP_MODEL["model_id"], "availability": "available", "from_setup": True}
    ]
    # Only the two ids travel: the endpoint and price stay in the profile.
    assert model["setup_choice"] == SETUP_MODEL
    assert "example.invalid" not in json.dumps(model)
    # Other providers are untouched.
    assert rows["anthropic"]["models"] == []
    # A model the adapter already lists is not offered twice.
    listed = capabilities._model(
        _open_options(),
        capabilities.NO_PROFILE,
        {
            "model_selection": {
                "provider_id": "engy-anthropic",
                "model_id": ENGY_DEFAULT_MODEL,
            }
        },
    )
    engy = {row["id"]: row for row in listed["providers"]}["engy-anthropic"]
    assert [m["id"] for m in engy["models"]].count(ENGY_DEFAULT_MODEL) == 1
    assert not any(m.get("from_setup") for m in engy["models"])
    # Without a setup choice there is none, and nothing is added.
    plain = capabilities._model(_open_options(), capabilities.NO_PROFILE, {})
    assert plain["setup_choice"] is None
    assert {row["id"]: row for row in plain["providers"]}["chutes"]["models"] == []


def test_a_malformed_setup_choice_is_ignored():
    from scripts.dev.miner_launchpad import capabilities

    for selection in (None, "chutes", {"provider_id": "chutes"}, {"model_id": "m"}):
        cfg = {"model_selection": selection}
        assert capabilities._setup_choice(cfg) is None, selection


def test_the_mcp_command_names_the_loaded_profile(journey, tmp_path):
    from scripts.dev.miner_launchpad import capabilities

    profile = tmp_path / "runner profile.json"
    journey.configuration = profile
    mcp = {
        c["id"]: c for c in capabilities.control_center(journey)["agents"]["choices"]
    }["external_mcp"]
    assert mcp["profile_path"] == str(profile)
    # A real command: the entry point (or module) and the profile, quoted.
    words = shlex.split(mcp["command"])
    assert words[-2:] == ["--configuration", str(profile)]
    assert "<your runner profile>" not in mcp["command"]
    server = mcp["client_configuration"]["mcpServers"]["carbon"]
    assert [server["command"], *server["args"]] == words
    # The specimen: with no profile loaded, the placeholder, said as such.
    unloaded = capabilities.control_center(None)["agents"]["choices"]
    none = next(c for c in unloaded if c["id"] == "external_mcp")
    assert none["command"] == capabilities.MCP_PLACEHOLDER
    assert none["profile_path"] is None


def test_shared_choices_are_named_as_setup_names_them(journey):
    from scripts.dev.miner_launchpad import capabilities
    from scripts.dev.miner_launchpad.environment_setup import (
        AUTONOMOUS,
        LOCAL_CPU,
        LOCAL_GPU,
        OWN_AGENT,
        REMOTE,
        choices,
    )

    offered = choices()
    named = {
        (group, choice["id"]): choice["display_name"]
        for group in ("agent", "compute")
        for choice in offered[group]
    }
    document = capabilities.control_center(journey)
    labels = {choice["id"]: choice["label"] for choice in document["agents"]["choices"]}
    assert labels["autonomous"] == named[("agent", AUTONOMOUS)]
    assert labels["external_mcp"] == named[("agent", OWN_AGENT)]
    # The journey profile computes on this machine's CPU.
    assert document["compute"]["choices"][0]["label"] == named[("compute", LOCAL_CPU)]
    assert capabilities.LOCAL_GPU_LABEL == named[("compute", LOCAL_GPU)]
    assert capabilities.REMOTE_LABEL == named[("compute", REMOTE)]
