"""C-MLP-03 slice 5: Hermes configured on the miner's machine, with consent.

Setup writes one dedicated Hermes profile (`carbon`): the setup's inference
choice as a custom OpenAI-compatible model, and Carbon's MCP server over
stdio, each tool that can change anything asking the miner first. These tests
hold that nothing is written without consent to exactly those files, that a
refused step writes nothing, that the key goes only to the owner-only `.env`,
and that the MCP command Hermes is given starts Carbon's server from this
checkout. Hermes itself is a fixture binary here; a real Hermes-driven battery
campaign is the slice's acceptance.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_miner_inference_providers import (
    GENERIC,
    HOTKEY,
    KEY,
    Checks,
    Onboarding,
)

from scripts.dev.miner_launchpad import hermes_setup
from scripts.dev.miner_launchpad.environment_setup import (
    AUTONOMOUS,
    HERMES,
    LOCAL_CPU,
    EnvironmentSetup,
    LiveChecks,
    SetupRefused,
)

REPOSITORY = Path(__file__).resolve().parents[2]


class HermesChecks(Checks):
    """Fixture checks, with the real Hermes writer on a temporary home."""

    def __init__(self, home, *, signer_ok=True):
        super().__init__()
        self.live = LiveChecks(hermes_home=home)
        self.signer_ok = signer_ok

    def hermes_files(self):
        return self.live.hermes_files()

    def hermes(self, document, key):
        return self.live.hermes(document, key)

    def agent(self, hotkey, socket_path=None):
        if not self.signer_ok:
            raise SetupRefused("signer", "signer_unreachable")
        return {"signing": "fixture"}


@pytest.fixture
def installed(monkeypatch):
    monkeypatch.setattr(hermes_setup, "find_hermes", lambda: "/fixture/bin/hermes")
    monkeypatch.setattr(
        hermes_setup, "hermes_version", lambda binary: "Hermes Agent v0.21.5"
    )


def ready(tmp_path, inference=None, **checks):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    for name in ("worker.json", "analysis.json", "operator.json"):
        (home / name).write_text("{}")
    hermes_home = tmp_path / "hermes"
    setup = EnvironmentSetup(
        root, onboarding=Onboarding(), checks=HermesChecks(hermes_home, **checks)
    )
    setup.begin({"address": HOTKEY})
    inference = inference or {
        "provider_id": "engy-chat",
        "model_id": "deepseek-v4-flash-0731",
    }
    quote = setup.quote(inference)
    setup.inference(
        {**inference, "key": KEY, "consent": {"max_cost_nano": quote["max_cost_nano"]}}
    )
    setup.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": str(home / "worker.json"),
            "analysis_image_manifest": str(home / "analysis.json"),
        }
    )
    return setup, home, hermes_home


def choose_hermes(setup, home, writes=None):
    return setup.agent(
        {
            "choice": HERMES,
            "operator_config": str(home / "operator.json"),
            "consent": {
                "writes": setup.checks.hermes_files() if writes is None else writes
            },
        }
    )


def test_hermes_is_offered_with_the_exact_files_it_writes(tmp_path):
    setup, _, hermes_home = ready(tmp_path)
    (choice,) = [c for c in setup.offered()["agent"] if c["id"] == HERMES]
    assert choice["writes"] == [
        str(hermes_home / "profiles" / "carbon" / "config.yaml"),
        str(hermes_home / "profiles" / "carbon" / ".env"),
    ]
    assert choice["needs_consent_to_write"] is True
    assert choice["start"] == "hermes -p carbon chat"


def test_with_consent_setup_writes_the_carbon_hermes_profile(tmp_path, installed):
    setup, home, hermes_home = ready(tmp_path)
    state = choose_hermes(setup, home)
    check = state["steps"]["agent"]["check"]
    assert check["hermes"] == "Hermes Agent v0.21.5"
    assert check["start"] == "hermes -p carbon chat"
    assert check["tools_ask_first"] is True
    profile = hermes_home / "profiles" / "carbon"
    config = json.loads((profile / "config.yaml").read_text())  # JSON is YAML
    assert config["model"] == {
        "default": "deepseek-v4-flash-0731",
        "provider": "custom",
        "base_url": "https://api.engy.ai/v1",
        "key_env": "CARBON_INFERENCE_KEY",
    }
    server = config["mcp_servers"]["carbon"]
    assert server["command"] == sys.executable
    assert server["args"] == [
        "-m",
        "carbon.miner_mcp.standard_cli",
        "--configuration",
        str(setup.profile_path),
    ]
    assert server["trust"] == "untrusted"
    # The key is only in the owner-only .env, never in the config.
    env = profile / ".env"
    assert env.read_text() == f"CARBON_INFERENCE_KEY={KEY}\n"
    assert env.stat().st_mode & 0o777 == 0o600
    assert KEY not in (profile / "config.yaml").read_text()
    assert KEY not in json.dumps(state)
    # The runner profile Hermes' server attaches to is the one review writes.
    setup.review({"confirm": True})
    assert setup.profile_path.exists()


def test_without_exact_consent_nothing_is_written(tmp_path, installed):
    setup, home, hermes_home = ready(tmp_path)
    for writes in ([], ["/elsewhere/config.yaml"], setup.checks.hermes_files()[:1]):
        with pytest.raises(SetupRefused) as refused:
            choose_hermes(setup, home, writes=writes)
        assert (refused.value.field, refused.value.code) == (
            "consent",
            "consent_must_name_the_files",
        )
    assert not hermes_home.exists()


def test_a_refused_signer_leaves_hermes_untouched(tmp_path, installed):
    setup, home, hermes_home = ready(tmp_path, signer_ok=False)
    with pytest.raises(SetupRefused, match="signer_unreachable"):
        choose_hermes(setup, home)
    assert not hermes_home.exists()


def test_hermes_not_installed_names_its_installer(tmp_path, monkeypatch):
    monkeypatch.setattr(hermes_setup, "find_hermes", lambda: None)
    setup, home, hermes_home = ready(tmp_path)
    with pytest.raises(SetupRefused) as refused:
        choose_hermes(setup, home)
    assert refused.value.code == "hermes_not_installed"
    assert "hermes-agent.nousresearch.com/install.sh" in refused.value.next_step
    assert not hermes_home.exists()


def test_hermes_needs_a_chat_completions_model(tmp_path, installed):
    setup, home, hermes_home = ready(
        tmp_path,
        inference={"provider_id": "engy-anthropic", "model_id": "glm-5.3-flash"},
    )
    with pytest.raises(SetupRefused) as refused:
        choose_hermes(setup, home)
    assert (refused.value.field, refused.value.code) == (
        "inference",
        "hermes_needs_a_chat_completions_model",
    )
    assert not hermes_home.exists()


@pytest.mark.parametrize(
    "adapter,endpoint,base",
    [
        ("engy-chat", None, "https://api.engy.ai/v1"),
        ("chutes", None, "https://llm.chutes.ai/v1"),
        ("openai-responses", None, "https://api.openai.com/v1"),
        ("openai-compatible-chat", GENERIC, "https://inference.example.org/v1"),
    ],
)
def test_the_model_base_url_is_the_inference_choice_s_own(adapter, endpoint, base):
    assert hermes_setup.model_base_url(adapter, endpoint) == base


def test_carbon_s_own_agent_takes_no_consent(tmp_path):
    setup, home, _ = ready(tmp_path)
    with pytest.raises(SetupRefused, match="nothing_to_consent_to"):
        setup.agent(
            {
                "choice": AUTONOMOUS,
                "operator_config": str(home / "operator.json"),
                "consent": {"writes": []},
            }
        )


def test_the_mcp_command_hermes_is_given_starts_carbon_s_server(tmp_path):
    command = hermes_setup.mcp_command(tmp_path / "profile.json", REPOSITORY)
    done = subprocess.run(
        [command["command"], *command["args"][:2], "--help"],
        cwd=command["cwd"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert "--configuration" in done.stdout
