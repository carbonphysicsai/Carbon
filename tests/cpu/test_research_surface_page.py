"""The research surface's page assets (OWNER-MINER-RESEARCH-SURFACE-01).

- The new script and stylesheet are served by the controller, name no
  Challenge and load nothing from the internet.
- Every label is set as text; no HTML is ever parsed (RSURF-D5).
- The JavaScript renderer draws every output kind, for a synthetic second
  Challenge, when Node is installed (RSURF-D8).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_research_surface import own_projection, predicted, synthetic_view, view_of

ROOT = Path(__file__).resolve().parents[2]
LAUNCHPAD = ROOT / "scripts/dev/miner_launchpad"


def test_the_page_sets_text_and_never_parses_html():
    for name in ("research_view.js", "research_charts.js", "research_tools.js"):
        source = (LAUNCHPAD / name).read_text()
        for pattern in (
            "innerHTML",
            "outerHTML",
            "insertAdjacentHTML",
            "document.write",
            "DOMParser",
            "eval(",
            "new Function",
            "createContextualFragment",
        ):
            assert pattern not in source, (name, pattern)
    # Specimen: the same scan finds one where it is.
    specimen = "node.innerHTML = text"
    assert "innerHTML" in specimen


def test_the_research_assets_are_served_locally_and_name_no_challenge():
    from carbon.challenge_registry import catalog
    from scripts.dev.miner_launchpad import controller

    page = (LAUNCHPAD / "index.html").read_text()
    for path, kind in (
        ("/research.css", "text/css"),
        ("/research_charts.js", "text/javascript"),
        ("/research_view.js", "text/javascript"),
        ("/research_tools.js", "text/javascript"),
    ):
        assert controller.STATIC[path][1].startswith(kind)
        assert path in page
    ids = [c["challenge_id"] for c in catalog()["challenges"]]
    pattern = re.compile("|".join(re.escape(i) for i in ids))
    for name in (
        "research.css",
        "research_charts.js",
        "research_view.js",
        "research_tools.js",
    ):
        text = (LAUNCHPAD / name).read_text()
        assert not pattern.search(text), name
        assert "burgers" not in text.lower() and "battery" not in text.lower(), name
        assert not re.search(
            r"https?://", text.replace("http://www.w3.org/2000/svg", "")
        ), name
    css = (LAUNCHPAD / "research.css").read_text()
    # The dark theme follows the system and the toggle, from the same tokens.
    assert "prefers-color-scheme: dark" in css and ':root[data-theme="dark"]' in css


def test_the_renderer_draws_every_kind_for_a_synthetic_challenge():
    view, cases = synthetic_view()
    doc = view_of(
        own_projection(),
        view,
        lambda task: (predicted(cases, 1.1 if task == "run-2" else 1.3), None),
    )
    case_charts = doc["per_case"]["selected"]["charts"]
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    script = ROOT / "tests/cpu/research_charts_check.cjs"
    result = subprocess.run(
        [node, str(script)],
        input=json.dumps(case_charts + doc["charts"]),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["drawn"] == len(case_charts) + len(doc["charts"])
