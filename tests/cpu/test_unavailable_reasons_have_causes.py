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

#: Where a launch is decided and dispatched. Wiring a compute provider into a
#: launch means one of these reaching it.
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


#: The provider-API modules OWNER-MINER-COMPUTE-LINK-ONLY-01 removed.
PROVIDER_IMPORT = (
    r"^\s*(from|import) carbon\.compute\.(runpod|lium|targon|providers?|service"
    r"|store|accounting|reconcile|rented_runner)\b"
)


def test_no_rented_compute_provider_is_listed_or_reachable():
    # OWNER-MINER-COMPUTE-LINK-ONLY-01: Carbon rents no compute. RunPod, Lium
    # and Targon are not unavailable integrations to be built: a miner runs
    # their own machine on any provider. The cause holds in code: no provider
    # adapter exists and nothing on the launch path reaches one.
    names = {path.stem for path in (ROOT / "carbon/compute").glob("*.py")}
    assert not {"runpod", "lium", "targon", "providers", "rented_runner"} & names
    # Specimen: the same listing finds the module that is still there.
    assert "job_server" in names
    listed = {item["id"] for item in controller.INTEGRATIONS}
    assert not {"runpod", "lium", "targon"} & listed
    assert _importers(PROVIDER_IMPORT, *LAUNCH_PATH, ROOT / "carbon") == []
    # Specimen: the pattern finds such an import where one is written.
    assert re.search(
        PROVIDER_IMPORT, "x = 1\nfrom carbon.compute.runpod import A\n", re.MULTILINE
    )


def test_chutes_is_a_provider_of_its_own_not_an_unavailable_integration():
    # C-MLP-03 slice 2 added Chutes' own adapter, with the prices it
    # publishes; the unavailable entry that said it had none is gone.
    assert "chutes" in model_provider.ADAPTERS
    assert model_provider.ADAPTERS["chutes"].live_pricing is True
    assert "chutes" not in {item["id"] for item in controller.INTEGRATIONS}
    # Specimen: the same search finds an entry that is still there.
    assert "mira" in {item["id"] for item in controller.INTEGRATIONS}


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
