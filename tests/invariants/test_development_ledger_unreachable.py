"""Nothing a miner receives can reach the development ledger.

OWNER-GRAPHITE-TEST-WAVE-03 §1-2 (owner, 2026-10-04): a development-only
contract variant is read only by Carbon's development runners, never by the
miner MCP server, the Launchpad, the validator or the intake, and exploration
on it continues past an open finding. GRAPHITE-CONDITIONAL-EXPLORATION-01
records those development expansions only in the campaign controller's
development ledger (`CampaignController.record_development_expansion`, table
`development_expansions`), apart from Track A's expansions.

This checks, on the code, that the import closure of every miner-facing
surface (the attack-store invariant's `MINER_SURFACES`, plus the validator)
neither contains the controller module nor names the development ledger. The
walk is the attack-store invariant's own. A specimen shows a planted lazy
import of the controller from a miner surface is found.
"""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = "carbon/agent_campaign/controller.py"
#: The ledger's table and its writer, by name.
LEDGER_NAMES = ("development_expansions", "record_development_expansion")


def _walk_module():
    """The attack-store invariant's import walk, loaded from its own file."""
    path = ROOT / "tests/invariants/test_attack_store_unreachable.py"
    spec = importlib.util.spec_from_file_location("_development_ledger_walk", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WALK = _walk_module()
SURFACES = (*WALK.MINER_SURFACES, "carbon/challenge_validator")


def reach(root=ROOT, surfaces=SURFACES):
    """`(file, how)` for every way the surfaces reach the development ledger."""
    found = set()
    for path in WALK.closure(root, surfaces):
        label = path.relative_to(root).as_posix()
        if label == CONTROLLER:
            found.add((label, "is the campaign controller"))
        text = path.read_text(encoding="utf-8", errors="replace")
        for name in LEDGER_NAMES:
            if name in text:
                found.add((label, "names " + name))
    return found


def test_no_miner_surface_reaches_the_development_ledger():
    assert (ROOT / "carbon/challenge_validator").is_dir()
    found = reach()
    assert not found, sorted(found)


def test_the_names_searched_for_are_the_ledgers_own():
    """A rename in the controller fails here before it can empty the check."""
    text = (ROOT / CONTROLLER).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS development_expansions" in text
    assert "def record_development_expansion(" in text


def test_a_planted_controller_import_is_found(tmp_path):
    files = {
        "carbon/__init__.py": "",
        "carbon/agent_campaign/__init__.py": "",
        "carbon/agent_campaign/controller.py": (
            "def record_development_expansion():\n    pass\n"
        ),
        "carbon/miner_mcp/__init__.py": "",
        "carbon/miner_mcp/door.py": (
            "def serve():\n"
            "    from carbon.agent_campaign import controller\n"
            "    return controller\n"
        ),
    }
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    found = reach(tmp_path, ("carbon/miner_mcp",))
    assert (CONTROLLER, "is the campaign controller") in found
