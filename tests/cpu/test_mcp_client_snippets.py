"""Setup's MCP client snippets run as written (LA-F12, LA-F13, LA-F14).

- **LA-F12.** The Claude Code snippet once put `--env PYTHONPATH=...` before
  the server name. On Claude Code 2.1.294, `--env` takes several values, so
  it swallowed the name, and the pasted command failed with "Invalid
  environment variable format: carbon".
- **LA-F13.** `codex exec` cannot answer an approval prompt, so the Codex
  table carries Codex's documented per-server approval setting.
- **LA-F14.** A snippet that names the checkout only by PYTHONPATH starts in
  whatever directory the agent runs in. Inside another Carbon checkout,
  `python -m` put that directory first and loaded the wrong packages, and
  Codex reported "Carbon MCP tool unavailable". Those snippets now pass
  `-P`. Snippets whose `cwd` is this checkout were already right.

These tests hold every snippet to a form that cannot be misread:
- the server name comes before any option that takes values;
- `--` comes next, then exactly the server command;
- the config-file snippets name the same command;
- the server command imports this checkout from a foreign one.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys

import pytest
import tomllib
import yaml

from scripts.dev.miner_launchpad import environment_setup

NAME = "carbon"
#: Options of `<client> mcp add` that take one or more values.
VALUE_OPTIONS = {"--env", "-e", "--header", "-H"}


def _clients():
    return {c["id"]: c for c in environment_setup.mcp_connect()["clients"]}


def _snippet(client, label):
    return next(s["text"] for s in client["snippets"] if s["label"] == label)


def _safe_path_command(connect):
    """The server command for a snippet with no cwd: `-P` before `-m`."""
    python, *args = shlex.split(connect["command"])
    return [python, "-P", *args]


@pytest.mark.parametrize("client_id", ["claude-code", "codex"])
def test_the_add_command_names_the_server_before_any_value_option(client_id):
    connect = environment_setup.mcp_connect()
    words = shlex.split(_snippet(_clients()[client_id], "Add it"))
    assert words[1:3] == ["mcp", "add"]
    separator = words.index("--")
    assert words[separator + 1 :] == _safe_path_command(connect)
    head = words[3:separator]
    assert NAME in head
    name_at = head.index(NAME)
    options = [i for i, word in enumerate(head) if word in VALUE_OPTIONS]
    assert options, "the snippet sets PYTHONPATH"
    assert all(name_at < i for i in options), head
    env = head[head.index("--env") + 1]
    assert env == "PYTHONPATH=" + connect["cwd"]
    if client_id == "claude-code":
        # Claude Code's default scope is the current directory only.
        assert head[head.index("--scope") + 1] == "user"


def test_the_config_snippets_name_the_same_server_command():
    connect = environment_setup.mcp_connect()
    command = shlex.split(connect["command"])
    clients = _clients()
    claude = json.loads(_snippet(clients["claude-code"], "Or in .mcp.json"))
    server = claude["mcpServers"][NAME]
    assert [server["command"], *server["args"]] == _safe_path_command(connect)
    assert server["env"] == {"PYTHONPATH": connect["cwd"]}
    # The cwd-based forms start in this checkout, so plain `-m` is right.
    text = _snippet(clients["codex"], "Or in ~/.codex/config.toml")
    codex = tomllib.loads(text)
    server = codex["mcp_servers"][NAME]
    assert [server["command"], *server["args"]] == command
    assert server["cwd"] == connect["cwd"]
    # LA-F13: the documented per-server approval setting, asking by default,
    # in the one table the snippet gives (no sub-table it could fall into).
    assert server["default_tools_approval_mode"] == "prompt"
    assert set(codex["mcp_servers"]) == {NAME}
    hermes_label = next(s["label"] for s in clients["hermes"]["snippets"])
    hermes = yaml.safe_load(_snippet(clients["hermes"], hermes_label))
    server = hermes["mcp_servers"][NAME]
    assert [server["command"], *server["args"]] == command
    assert server["cwd"] == connect["cwd"]


def test_a_foreign_checkout_cwd_cannot_shadow_this_checkout(tmp_path):
    """LA-F14's specimen: an agent running inside another Carbon checkout.

    The foreign directory has its own `carbon` and `scripts` packages. The
    env-based snippets' interpreter flags, with their PYTHONPATH, still
    import this checkout's packages."""
    connect = environment_setup.mcp_connect()
    for package in ("carbon", "scripts"):
        (tmp_path / package).mkdir()
        (tmp_path / package / "__init__.py").write_text("FOREIGN = True\n")
    _python, *args = _safe_path_command(connect)
    flags = args[: args.index("-m")]
    probe = (
        "import carbon, scripts, sys; print(carbon.__file__); print(scripts.__file__)"
    )
    env = {**os.environ, "PYTHONPATH": connect["cwd"]}
    done = subprocess.run(
        [sys.executable, *flags, "-c", probe],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    loaded = done.stdout.split()
    assert loaded and all(str(tmp_path) not in path for path in loaded), loaded
    # And the specimen itself: without -P the foreign packages win.
    shadowed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert any(str(tmp_path) in path for path in shadowed.stdout.split())
