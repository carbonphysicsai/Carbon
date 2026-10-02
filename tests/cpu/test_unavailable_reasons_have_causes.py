"""Each unavailable reason is tied to the code fact that makes it true.

The unavailable list has been wrong three times, each time by a reason that
outlived its cause. A reason here is a claim about current code, so each one
that describes code is paired with a probe of that code. When the cause goes
away - an adapter lands, dispatch is wired - the probe fails and the reason has
to be revisited in the same change.

Every probe that asserts an absence also shows its search finding something
that is present, so a green result means the cause still holds rather than
that the search is blind.
"""

from __future__ import annotations

import re
from pathlib import Path

from carbon.development_session import model_provider
from scripts.dev.miner_launchpad import controller

ROOT = Path(__file__).resolve().parents[2]

#: Where a launch is decided and dispatched. Wiring RunPod into a launch means
#: one of these reaching `carbon.compute`.
LAUNCH_PATH = (
    ROOT / "scripts/dev/miner_launchpad",
    ROOT / "carbon/development_session",
    ROOT / "carbon/miner_mcp",
)


def _reason(integration_id):
    return {item["id"]: item["reason"] for item in controller.INTEGRATIONS}[
        integration_id
    ]


def _python_files(*roots):
    for root in roots:
        yield from sorted(root.rglob("*.py"))


def _importers(pattern, *roots):
    found = re.compile(pattern, re.MULTILINE)
    return [
        path.relative_to(ROOT).as_posix()
        for path in _python_files(*roots)
        if found.search(path.read_text(encoding="utf-8"))
    ]


COMPUTE_IMPORT = r"^\s*(from carbon\.compute\b|import carbon\.compute\b)"


def test_runpod_and_lium_launch_from_setup_and_left_the_list():
    # C-MLP-03 slice 4 wired both into launch: battery practice runs on a
    # rented GPU through `carbon.compute.rented_runner`, on the miner's own
    # account. Their unavailable entries are gone.
    from carbon.compute.providers import PROVIDERS

    assert {"runpod", "lium"} <= set(PROVIDERS)
    listed = {item["id"] for item in controller.INTEGRATIONS}
    assert not {"runpod", "lium"} & listed
    # The cause is gone too: the launch path now reaches the compute layer.
    assert _importers(COMPUTE_IMPORT, *LAUNCH_PATH) != []


def test_targon_runs_no_container_image():
    assert _reason("targon") == "provider_runs_no_container_image"
    from carbon.compute.providers import PROVIDERS

    names = {path.stem for path in (ROOT / "carbon/compute").glob("*.py")}
    assert "lium" in names  # specimen: an adapter that does exist
    assert not any("targon" in name for name in names)
    assert "targon" not in PROVIDERS


def test_chutes_is_a_provider_of_its_own_not_an_unavailable_integration():
    # C-MLP-03 slice 2 added Chutes' own adapter, with the prices it
    # publishes; the unavailable entry that said it had none is gone.
    assert "chutes" in model_provider.ADAPTERS
    assert model_provider.ADAPTERS["chutes"].live_pricing is True
    assert "chutes" not in {item["id"] for item in controller.INTEGRATIONS}
    # Specimen: the same search finds an entry that is still there.
    assert "targon" in {item["id"] for item in controller.INTEGRATIONS}


def test_hermes_is_configured_in_setup_and_left_the_list():
    # C-MLP-03 slice 5: setup writes a Hermes profile driving Carbon's MCP
    # server over stdio. The unavailable entry that said no adapter existed is
    # gone, and so is its cause.
    from scripts.dev.miner_launchpad import environment_setup, hermes_setup

    assert "hermes" not in {item["id"] for item in controller.INTEGRATIONS}
    assert "hermes" in {c["id"] for c in environment_setup.choices()["agent"]}
    assert callable(hermes_setup.config_document)


def test_mira_has_no_verified_interface():
    # Specimen: the entry is still there, with its reason.
    assert _reason("mira") == "integration_interface_unverified"
    roots = (ROOT / "carbon", ROOT / "scripts/dev/miner_launchpad")
    # Nothing builds a Mira connection anywhere.
    assert not [
        path
        for path in _importers(r"^\s*(def|class) \w*mira", *roots)
        if "mira" in path.lower()
    ]


def test_the_remote_door_is_built_but_nothing_serves_it():
    assert _reason("personal-agent") == "remote_door_not_hosted"
    roots = (ROOT / "carbon", ROOT / "scripts")
    builders = set(_importers(r"create_access_http_app|standard_http", *roots))
    assert "carbon/miner_mcp/standard_http.py" in builders  # specimen
    servers = set(_importers(r"uvicorn", *roots))
    # Specimen: the search finds a module that really does serve an app.
    assert "carbon/scientific_tasks/workbench_host.py" in servers
    # The cause: nothing that serves an app touches the remote door.
    assert builders.isdisjoint(servers)
