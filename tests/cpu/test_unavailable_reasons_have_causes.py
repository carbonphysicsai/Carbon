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


def test_runpod_is_implemented_but_no_launch_path_dispatches_to_it():
    assert _reason("runpod") == "compute_adapter_not_wired_into_launch"
    # The adapter exists: this is not "not implemented".
    from carbon.compute import runpod

    assert hasattr(runpod, "__file__")
    # Specimen: the same search finds the importer that really exists.
    assert "tests/cpu/test_compute_provider.py" in _importers(
        COMPUTE_IMPORT, ROOT / "tests/cpu"
    )
    # The cause: nothing on the launch path reaches it.
    assert _importers(COMPUTE_IMPORT, *LAUNCH_PATH) == []


def test_chutes_has_no_adapter_of_its_own_but_the_generic_one_reaches_it():
    assert _reason("chutes").startswith("no_chutes_adapter")
    ids = set(model_provider.ADAPTERS)
    # Specimen, and the path the next action names.
    assert "openai-compatible-chat" in ids
    assert model_provider.ADAPTERS["openai-compatible-chat"].endpoint is None
    # The cause.
    assert not any("chutes" in adapter_id for adapter_id in ids)


def test_lium_has_no_compute_provider():
    assert _reason("lium") == "provisioning_and_teardown_adapter_not_implemented"
    names = {path.stem for path in (ROOT / "carbon/compute").glob("*.py")}
    assert "runpod" in names  # specimen
    assert not any("lium" in name for name in names)


def test_hermes_has_no_agent_adapter():
    assert _reason("hermes") == "adapter_not_implemented"
    pattern = r"hermes"
    roots = (ROOT / "carbon", ROOT / "scripts/dev/miner_launchpad")
    mentions = _importers(pattern, *roots)
    # Specimen: the list itself names it.
    assert "scripts/dev/miner_launchpad/controller.py" in mentions
    assert mentions == ["scripts/dev/miner_launchpad/controller.py"]


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
