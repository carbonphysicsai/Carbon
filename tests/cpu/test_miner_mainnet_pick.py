"""A wired mainnet pick for the miner install: ``scripts/install_miner.sh --network finney`` (13 Nov).

A process binds its network once at import from ``CARBON_CHAIN_NETWORK`` (testnet 567 when unset, finney 116 when it says so), and
nothing used to set it for a miner, so mainnet needed a hand-set variable in every process. The installer's ``--network`` now sets it
for the install's own steps, for the Control Center it starts, in the systemd user unit, and in the signer command it prints; an
update that names no network keeps a unit that already runs mainnet; and a testnet install is byte-for-byte what it was.
A finney-bound process reads ONLY the 116 endpoint (`test_published_endpoints_finney`). Stand-ins for Docker and systemd; nothing is built.
"""

from __future__ import annotations

import pytest
from test_miner_install import Sandbox

from scripts.dev.miner_launchpad import environment_setup as environment


@pytest.fixture
def sandbox(tmp_path):
    return Sandbox(tmp_path)


# ---- the unit text --------------------------------------------------------------------------------


def test_the_testnet_unit_is_unchanged_and_the_mainnet_unit_adds_one_line(tmp_path):
    state = tmp_path / "state"
    plain = environment.service_unit(state, 8788, repo=tmp_path / "repo")
    assert "CARBON_CHAIN_NETWORK" not in plain
    # naming the default network, or none, is the same bytes as before
    assert (
        environment.service_unit(state, 8788, repo=tmp_path / "repo", network=None)
        == plain
    )
    assert (
        environment.service_unit(state, 8788, repo=tmp_path / "repo", network="testnet")
        == plain
    )
    mainnet = environment.service_unit(
        state, 8788, repo=tmp_path / "repo", network="finney"
    )
    lines = mainnet.splitlines()
    assert lines.count("Environment=CARBON_CHAIN_NETWORK=finney") == 1
    # the only difference is that one line, inside [Service]
    assert [x for x in lines if x not in plain.splitlines()] == [
        "Environment=CARBON_CHAIN_NETWORK=finney"
    ]
    assert (
        lines.index("[Service]")
        < lines.index("Environment=CARBON_CHAIN_NETWORK=finney")
        < lines.index("[Install]")
    )


def test_an_unknown_network_is_refused_not_written(tmp_path):
    with pytest.raises(ValueError, match="service_network_unknown"):
        environment.service_unit(
            tmp_path / "state", 8788, repo=tmp_path / "repo", network="mainnet"
        )


def test_the_service_unit_command_takes_the_network(tmp_path, capsys):
    state = tmp_path / "state"
    assert (
        environment.main(
            [
                "service-unit",
                "--state-dir",
                str(state),
                "--port",
                "8788",
                "--network",
                "finney",
            ]
        )
        == 0
    )
    assert "Environment=CARBON_CHAIN_NETWORK=finney" in capsys.readouterr().out
    assert (
        environment.main(["service-unit", "--state-dir", str(state), "--port", "8788"])
        == 0
    )
    assert "CARBON_CHAIN_NETWORK" not in capsys.readouterr().out


# ---- the installer ---------------------------------------------------------------------------------

CENTER_THAT_SAYS_ITS_NETWORK = """#!/bin/sh
echo "control center network=${CARBON_CHAIN_NETWORK:-unset} $*" >> "$CARBON_TEST_LOG"
"""


def test_an_unknown_network_stops_the_install_before_anything(sandbox):
    done = sandbox.run("--network", "mainnet")
    assert done.returncode == 2
    assert "testnet or finney" in done.stderr
    assert not any("control center" in line for line in sandbox.logged())


def test_finney_binds_the_control_center_and_the_signer_command(sandbox):
    Sandbox._executable(sandbox.tmp / "control-center", CENTER_THAT_SAYS_ITS_NETWORK)
    done = sandbox.run("--network", "finney")
    assert done.returncode == 0, done.stderr
    assert any(
        line.startswith("control center network=finney") for line in sandbox.logged()
    )
    assert (
        "CARBON_CHAIN_NETWORK=finney "
        in done.stdout.split("carbon-miner-signer")[0].splitlines()[-1]
    )
    assert "registered on subnet 116" in done.stdout
    assert "registered on subnet 567" not in done.stdout
    # the printed start command carries it too
    assert "CARBON_CHAIN_NETWORK=finney PYTHONDONTWRITEBYTECODE=1" in done.stdout


def test_the_default_install_is_the_testnet_install_it_was(sandbox):
    Sandbox._executable(sandbox.tmp / "control-center", CENTER_THAT_SAYS_ITS_NETWORK)
    done = sandbox.run()
    assert done.returncode == 0, done.stderr
    assert any(
        line.startswith("control center network=unset") for line in sandbox.logged()
    )
    assert "CARBON_CHAIN_NETWORK" not in done.stdout
    assert "registered on subnet 567" in done.stdout
    # naming testnet is the same install
    again = sandbox.run("--network", "testnet")
    assert again.returncode == 0, again.stderr
    assert "CARBON_CHAIN_NETWORK" not in again.stdout


def test_the_service_unit_is_written_for_mainnet_and_an_update_keeps_it(sandbox):
    done = sandbox.run("--service", "--network", "finney")
    assert done.returncode == 0, done.stderr
    unit_calls = [line for line in sandbox.logged() if "service-unit" in line]
    assert unit_calls and unit_calls[-1].endswith("--network finney")
    unit = sandbox.tmp / "home/.config/systemd/user/carbon-control-center.service"
    # the stand-in prints a fixture unit; give it the line the real one carries
    unit.write_text(unit.read_text() + "Environment=CARBON_CHAIN_NETWORK=finney\n")
    # an update that names no network keeps mainnet (a missing option never moves a miner back)
    kept = sandbox.run("--update")
    assert kept.returncode == 0, kept.stderr
    assert "stays on mainnet" in kept.stdout
    assert [line for line in sandbox.logged() if "service-unit" in line][-1].endswith(
        "--network finney"
    )
    # naming testnet moves it back, on purpose
    moved = sandbox.run("--update", "--network", "testnet")
    assert moved.returncode == 0, moved.stderr
    assert "stays on mainnet" not in moved.stdout
    assert [line for line in sandbox.logged() if "service-unit" in line][-1].endswith(
        "--network testnet"
    )
