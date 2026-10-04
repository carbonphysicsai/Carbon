"""The Control Center names no Challenge itself (C-MLP-04).

The owner's direction: miners reach the Control Center and then decide what
Challenge to mine; nothing there is battery-only. So everything that differs
by Challenge (feedback modes and their schema, the validator intake, the GPU
practice scope) is read from that Challenge's campaign in
`carbon.challenge_registry.campaigns`. These tests hold that:

- no Launchpad or MCP module imports a Challenge's own modules; the one
  allowed reference is the legacy-field mapping in the runner, which reads a
  C-MLP-03 profile's `battery_intake`/`battery_validator` exactly as before;
- the catalog reports every Challenge the same way, with its provisions and
  what setup offers for it, and a non-implemented one offers nothing;
- GPU practice set up for one Challenge never launches another.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOORS = [
    *sorted((ROOT / "scripts/dev/miner_launchpad").glob("*.py")),
    *sorted((ROOT / "carbon/miner_mcp").glob("*.py")),
]
#: Fixtures and smokes exercise a real Challenge on purpose.
FIXTURES = {"journey_fixture.py", "browser_smoke.py"}
CHALLENGE_MODULES = ("carbon.battery", "carbon.development_session.battery_gpu")


def _imports(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
            yield from (node.module + "." + alias.name for alias in node.names)


@pytest.mark.parametrize("path", DOORS, ids=lambda p: p.name)
def test_no_door_imports_a_challenges_own_modules(path):
    if path.name in FIXTURES:
        pytest.skip("fixtures exercise a real Challenge")
    found = [
        name
        for name in _imports(path)
        if name.startswith(CHALLENGE_MODULES) or name.endswith(".BATTERY_CHALLENGE")
    ]
    if path.name == "runner.py":
        # The legacy-field mapping: a C-MLP-03 profile's battery_* fields are
        # read as that one Challenge's, exactly as before.
        assert found == ["carbon.reconstruction.capability_registry.BATTERY_CHALLENGE"]
        return
    assert found == []


def test_the_check_finds_a_challenge_import():
    """Specimen: the same scan flags a module that imports one."""
    source = ROOT / "carbon/challenge_registry/campaigns.py"
    assert any(name.startswith(CHALLENGE_MODULES) for name in _imports(source))


def test_every_challenge_reports_its_provisions_and_offers_alike():
    from scripts.dev.miner_launchpad import capabilities

    challenges = capabilities.control_center(None)["challenges"]
    assert {"provisions", "setup_offers", "profiles"} <= set(challenges[0])
    for entry in challenges:
        offers = entry["setup_offers"]
        if not entry["implemented"]:
            assert offers == {
                "gpu": False,
                "remote_gpu": False,
                "intake": False,
                "feedback_modes": [],
                # Graphite runs only where a campaign is registered
                # (OWNER-GRAPHITE-MINER-01).
                "graphite": False,
            }
        else:
            assert offers["feedback_modes"][0] == "FULL"
            # Remote practice runs the GPU practice program: never offered
            # without it, and read from the Challenge's own campaign.
            assert offers["remote_gpu"] <= offers["gpu"]


def test_gpu_practice_for_one_challenge_never_launches_another():
    from carbon.challenge_registry import registry
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    runtime = {"gpu_research": [{"challenge": "another-challenge"}]}
    request = {
        "challenge": "battery-fastcharge-ageing-development-v1",
        "challenge_version": "1.0",
    }
    assert registry.GPU_RESEARCH in {
        p.name
        for e in registry.entries()
        if e.challenge_id == request["challenge"]
        for p in e.profiles
    }
    with pytest.raises(Rejected) as refused:
        RunnerAdapter._challenge(request, runtime)
    assert refused.value.code == "gpu_scope_is_for_another_challenge"
    # Specimen: the scope's own Challenge is accepted.
    runtime["gpu_research"][0]["challenge"] = request["challenge"]
    assert RunnerAdapter._challenge(request, runtime) == {
        "id": request["challenge"],
        "version": "1.0",
    }
