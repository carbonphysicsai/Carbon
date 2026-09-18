"""Independent official TypeScript SDK stdio interoperability, fixture evidence.

Install the test-only dependencies with ``pnpm install --frozen-lockfile
--ignore-scripts`` in ``tests/service/mcp_typescript``. Set
CARBON_MCP_TYPESCRIPT_NODE to select a Node >=20 executable. Environments without
the optional JS dependencies skip unless CARBON_REQUIRE_TYPESCRIPT_INTEROP=1.
The WSL/Windows runtime bridge is test plumbing, never a production launcher.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
CLIENT_DIRECTORY = Path(__file__).with_name("mcp_typescript")


def test_independent_typescript_sdk_stdio(tmp_path):
    node = os.environ.get("CARBON_MCP_TYPESCRIPT_NODE") or shutil.which("node")
    installed = CLIENT_DIRECTORY / "node_modules/@modelcontextprotocol/client"
    if not node or not installed.is_dir():
        reason = (
            "TypeScript interoperability requires Node >=20 and locked client install"
        )
        if os.environ.get("CARBON_REQUIRE_TYPESCRIPT_INTEROP") == "1":
            pytest.fail(reason)
        pytest.skip(reason)
    launch = {
        "command": sys.executable,
        "args": [
            str(Path(__file__).with_name("test_standard_mcp_stdio.py")),
            "--serve",
            str(tmp_path),
        ],
        "cwd": str(REPOSITORY),
    }
    script = str(CLIENT_DIRECTORY / "client.mjs")
    if os.name != "nt" and str(node).lower().endswith(".exe"):
        # Use the installed Windows runtime from WSL without changing the host
        # configuration. Server and its ledger remain inside this WSL distro.
        script = subprocess.check_output(["wslpath", "-w", script], text=True).strip()
        launch = {
            "command": "wsl.exe",
            "args": [
                "--distribution",
                os.environ["WSL_DISTRO_NAME"],
                "--cd",
                str(REPOSITORY),
                "--",
                sys.executable,
                *launch["args"],
            ],
        }
    result = subprocess.run(
        [str(node), script, json.dumps(launch)],
        cwd=REPOSITORY,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["client"] == "@modelcontextprotocol/client"
    assert evidence["version"] == "2.0.0"
    assert evidence["fixture_only"] is True
    assert evidence["server_restarts"] == evidence["used_trials"] == 1
    assert len(evidence["checks"]) == 9
