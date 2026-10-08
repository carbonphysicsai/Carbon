"""Setup's MCP client snippets run as written (LA-F12).

The Claude Code snippet once put `--env PYTHONPATH=...` before the server
name. On Claude Code 2.1.294, `--env` takes several values, so it swallowed
the name, and the pasted command failed with "Invalid environment variable
format: carbon". These tests hold every one-line snippet to the order that
cannot be misread:
- the server name comes before any option that takes values;
- `--` comes next, then exactly the server command;
- the config-file snippets name the same command and arguments.
"""

from __future__ import annotations

import json
import shlex

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


@pytest.mark.parametrize("client_id", ["claude-code", "codex"])
def test_the_add_command_names_the_server_before_any_value_option(client_id):
    connect = environment_setup.mcp_connect()
    words = shlex.split(_snippet(_clients()[client_id], "Add it"))
    assert words[1:3] == ["mcp", "add"]
    separator = words.index("--")
    assert words[separator + 1 :] == shlex.split(connect["command"])
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
    assert [server["command"], *server["args"]] == command
    assert server["env"] == {"PYTHONPATH": connect["cwd"]}
    codex = tomllib.loads(_snippet(clients["codex"], "Or in ~/.codex/config.toml"))
    server = codex["mcp_servers"][NAME]
    assert [server["command"], *server["args"]] == command
    hermes_label = next(s["label"] for s in clients["hermes"]["snippets"])
    hermes = yaml.safe_load(_snippet(clients["hermes"], hermes_label))
    server = hermes["mcp_servers"][NAME]
    assert [server["command"], *server["args"]] == command
