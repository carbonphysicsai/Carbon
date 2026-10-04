"""Graphite's modules import cleanly whichever is imported first.

`tools` imports `literature`, and `literature` builds its fixture index at
import, which runs the protected-material check. While that check lived in
`tools`, a fresh process whose first Graphite import was `tools` (or anything
that imports `tools` before `literature`, such as `miner.imports`, or the
miner edition's lazy `toolbox.protected`) failed with an ImportError from the
partly initialised `tools`. The check now lives in the leaf
`protected_material`.

Each case runs in a fresh interpreter, because a module already imported by
this test process (or by another test) hides the order a real process sees.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
G = "carbon.agent_campaign.graphite"
#: Every Graphite module a process may import first.
FIRST_IMPORTS = (
    "tools",
    "literature",
    "method_cards",
    "roles",
    "provider",
    "level_planner",
    "phase2",
    "phase3",
    "miner.library",
    "miner.toolbox",
    "miner.driver",
    "miner.edition",
    "miner.imports",
    "miner.hunt",
    "miner.pack",
)
#: After the first import, the rest are imported and the shared check runs
#: through each door that exposes it.
CHECKS = (
    f"import {G}.tools as t, {G}.literature as lit\n"
    f"from {G}.miner import toolbox\n"
    "assert t.protected({'q': 'derived-seed'}) is True\n"
    "assert toolbox.protected({'q': 'official_seed'}) is True\n"
    "assert toolbox.protected({'q': 'a spectral operator'}) is False\n"
    "assert lit.FIXTURE_INDEX.cards\n"
)


def _python(code, *args):
    env = {**os.environ, "JAX_PLATFORMS": "cpu"}
    return subprocess.run(
        [sys.executable, *args] if not code else [sys.executable, "-c", code],
        cwd=REPOSITORY,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _assert_clean(done):
    assert done.returncode == 0, done.stderr[-2000:]


@pytest.mark.parametrize("first", FIRST_IMPORTS)
def test_a_graphite_module_imported_first_imports_cleanly(first):
    others = "".join(f"import {G}.{name}\n" for name in FIRST_IMPORTS)
    _assert_clean(_python(f"import {G}.{first}\n" + others + CHECKS))


ENTRY_POINTS = {
    # The miner edition's shared check, called before any library is opened.
    "miner_toolbox_check_first": (
        f"from {G}.miner import toolbox\n"
        "assert toolbox.protected({'q': 'draw_id'}) is True\n"
    ),
    # A Launchpad / Control Center Graphite launch: research_campaign.execute
    # -> run_graphite -> driver.run, which opens the miner's library.
    "launchpad_graphite_launch": (
        "import tempfile\n"
        "from carbon.development_session import research_campaign\n"
        f"from {G}.miner import driver, toolbox\n"
        "driver.open_library(tempfile.mkdtemp())\n"
        "assert toolbox.protected({'q': 'official seed'}) is True\n"
    ),
    # The Launchpad door's own re-check of a served card.
    "launchpad_served_card_check": (
        "from scripts.dev.miner_launchpad import runner\n"
        "assert runner._protected_card({'card_id': 'x', 'title': 'draw_id'})\n"
    ),
    # The standard MCP door.
    "mcp_standard_cli": "import carbon.miner_mcp.standard_cli\n" + CHECKS,
}


@pytest.mark.parametrize("name", sorted(ENTRY_POINTS))
def test_a_real_entry_point_reaches_the_check_cleanly(name):
    _assert_clean(_python(ENTRY_POINTS[name]))


def test_the_internal_phase3_cli_starts():
    _assert_clean(_python(None, "-m", f"{G}.phase3", "--help"))


def test_the_leaf_imports_first_and_tools_re_exports_its_check_unchanged():
    """The leaf imports nothing from Graphite, and `tools` serves the same
    check and markers it always named (`tools.protected`)."""
    _assert_clean(
        _python(
            f"import {G}.protected_material as pm\n"
            "import sys\n"
            f"assert not [m for m in sys.modules if m.startswith('{G}.')"
            " and m != pm.__name__], sorted(sys.modules)\n"
            f"import {G}.tools as t\n"
            "assert t.protected is pm.protected\n"
            "assert t.PROTECTED_MARKERS is pm.PROTECTED_MARKERS\n"
        )
    )
