"""Hermes Agent, configured on the miner's machine with their consent (C-MLP-03 slice 5).

Hermes (Nous Research) runs on the miner's machine and drives the Challenge's
research tools through Carbon's own MCP server over stdio
(`carbon-mcp --configuration <runner profile>`), with the miner's inference
choice as its model. Setup writes one dedicated Hermes profile, `carbon`, so
the miner's own Hermes configuration is never touched:

- `<HERMES_HOME>/profiles/carbon/config.yaml`: the custom OpenAI-compatible
  model (the setup's inference provider and model, its key read from the
  profile's environment) and one `mcp_servers` stdio entry for Carbon;
- `<HERMES_HOME>/profiles/carbon/.env`: the inference key, owner-only.

Nothing is written without the miner's consent to that exact list of files.
The Carbon server is marked `trust: untrusted`, so Hermes asks the miner
before every tool call that can change anything (launch, practice, freeze,
submit). The miner may change that in their own copy.

Hermes facts, read 2026-10-02 from the Hermes Agent documentation and
repository (v0.21.5): profiles live in `~/.hermes/profiles/<name>/` (selected
with `hermes -p <name>`), `HERMES_HOME` moves the root, config is YAML (JSON is
YAML), `mcp_servers.<name>` takes `command`, `args`, `cwd`, `timeout`,
`connect_timeout` and `trust`, a stdio server receives only a filtered
environment, and `model.provider: custom` takes `base_url` and `key_env`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROFILE = "carbon"
SERVER = "carbon"
KEY_ENV = "CARBON_INFERENCE_KEY"
#: How a miner installs Hermes (its documented installer; PyPI is unsupported).
INSTALL_STEP = (
    "install Hermes Agent: curl -fsSL "
    "https://hermes-agent.nousresearch.com/install.sh | bash"
)
#: What a miner runs once setup has written the profile.
START = "hermes -p " + PROFILE + " chat"


class HermesUnavailable(Exception):
    """Hermes cannot be configured for this choice; `code` says why."""

    def __init__(self, field, code, next_step=None):
        super().__init__(code)
        self.field, self.code, self.next_step = field, code, next_step


def hermes_home():
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def profile_files(home):
    """The files setup writes, in the order it writes them."""
    root = Path(home) / "profiles" / PROFILE
    return [root / "config.yaml", root / ".env"]


def model_base_url(adapter_id, endpoint=None):
    """The OpenAI-compatible base URL Hermes calls for this inference choice.

    Hermes' custom provider speaks Chat Completions. The Engy chat route,
    Chutes and a generic chat endpoint do; OpenAI serves Chat Completions at
    the same base as its Responses API. The Anthropic-shaped routes do not.
    """
    from carbon.development_session.model_provider import ADAPTERS

    adapter = ADAPTERS[adapter_id]
    if adapter.protocol.startswith("openai.chat-completions"):
        if adapter.base_url is not None:
            return adapter.base_url
        suffix = "/chat/completions"
        if endpoint and endpoint.endswith(suffix):
            return endpoint[: -len(suffix)]
    elif adapter_id == "openai-responses":
        return adapter.base_url
    raise HermesUnavailable(
        "inference",
        "hermes_needs_a_chat_completions_model",
        "choose Engy (Chat Completions), Chutes, OpenAI or a Chat Completions "
        "endpoint under Inference",
    )


def mcp_command(runner_profile, repo):
    """How Hermes starts Carbon's MCP server: this checkout's own interpreter."""
    return {
        "command": sys.executable,
        "args": [
            "-m",
            "carbon.miner_mcp.standard_cli",
            "--configuration",
            str(runner_profile),
        ],
        "cwd": str(repo),
    }


def config_document(*, model_id, base_url, runner_profile, repo):
    return {
        "model": {
            "default": model_id,
            "provider": "custom",
            "base_url": base_url,
            "key_env": KEY_ENV,
        },
        "mcp_servers": {
            SERVER: {
                **mcp_command(runner_profile, repo),
                # Research calls can run for minutes; connecting reads the
                # chain and checks the accepted runtime.
                "timeout": 1800,
                "connect_timeout": 180,
                "trust": "untrusted",
            }
        },
    }


def find_hermes():
    for candidate in (
        shutil.which("hermes"),
        str(Path.home() / ".local" / "bin" / "hermes"),
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def hermes_version(binary, *, run=subprocess.run):
    try:
        done = run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    line = (done.stdout or "").strip().splitlines()
    return line[0][:120] if line else None


def write_profile(home, document, key, write_private):
    """Write the consented files; the key only into the owner-only `.env`."""
    config, env = profile_files(home)
    write_private(config, (json.dumps(document, indent=2) + "\n").encode())
    write_private(env, f"{KEY_ENV}={key}\n".encode())
    return [str(config), str(env)]
