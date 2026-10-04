"""Graphite in the Control Center (GRAPHITE-MINER-S5, OWNER-GRAPHITE-MINER-01).

The page's Graphite views run in Node with the other page checks
(control_center_page_check.cjs, driven by test_control_center_live_page):
the launch wizard's Graphite choices (mode, research share, plan, hunt with
its cost estimate, optional per-epoch limits), the campaign's Graphite part
and the Library (cards with origin and UNCHECKED labels, ranked search with
reasons, pin and ban, import, plans and the plan editor).

Here each boundary those scenarios hold is shown to be held by them: the
page is copied, one boundary is broken in the copy, and the scenario that
holds it must then fail. And the page's own files are checked: every script
it loads is one the controller serves, and none names a Challenge or loads
anything from the internet.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from test_control_center_live_page import (  # noqa: F401 - fixtures
    CHECK,
    LAUNCHPAD,
    documents,
    journey,
)

SCRIPTS = re.compile(r'<script\s+src="/([\w.-]+\.js)"')

#: (file, the line as it is, the line broken, the scenario that must fail).
MUTATIONS = (
    (
        "app.js",
        "function agentChoices() { return caps ? caps.agents.choices.filter(choice => !replacedChoice(choice)) : []; }",
        "function agentChoices() { return caps ? caps.agents.choices : []; }",
        "Graphite: offered in place of the autonomous agent",
    ),
    (
        "app.js",
        "if (composition.agent === GRAPHITE) Object.assign(pendingResearch.body, launchFields(graphiteFields()));",
        "Object.assign(pendingResearch.body, launchFields(graphiteFields()));",
        "Graphite: offered in place of the autonomous agent",
    ),
    (
        "app.js",
        'if (g.mode === "FULL") fields.research_share = shareOf(g.share);',
        "fields.research_share = shareOf(g.share);",
        "Graphite: each mode launches with exactly its own fields",
    ),
    (
        "app.js",
        'if (g.mode === "BUILD" && g.plan) fields.plan = g.plan;',
        "if (g.plan) fields.plan = g.plan;",
        "Graphite: each mode launches with exactly its own fields",
    ),
    (
        "app.js",
        "const problem = queryProblem(huntQueries(g.queries));",
        "const problem = null;",
        "Graphite: the hunt estimate uses the model's listed price",
    ),
    (
        "app.js",
        'if (text !== "") limits[key] = wholeNumber(text); }',
        "limits[key] = wholeNumber(text); }",
        "Graphite: per-epoch limits are optional",
    ),
    (
        "app.js",
        'rebuild(box, "graphite:" + capsVersion, drawGraphiteOptions);',
        'rebuild(box, "graphite:" + capsVersion + Date.now(), drawGraphiteOptions);',
        "a refresh with nothing new changes nothing",
    ),
    (
        "research_view.js",
        "box => { if (doc.graphite) drawGraphite(box, doc); }",
        "box => {}",
        "Graphite: the campaign shows its stage",
    ),
    (
        "library_view.js",
        "pills.append(originPill(card), checkPill(card));",
        "pills.append(originPill(card));",
        "Library: every card says where it came from and UNCHECKED",
    ),
    (
        "library_view.js",
        "const shown = lib.search ? lib.search.results.filter(card => !lib.curation.bans.includes(card.card_id)) : [];",
        "const shown = lib.search ? lib.search.results : [];",
        "Library: every card says where it came from and UNCHECKED",
    ),
    (
        "library_view.js",
        'if (declared(name)?.has("idempotency_key")) {',
        "if (false) {",
        "Library: pin and ban are the controller's operations, under a key",
    ),
    (
        "library_view.js",
        'if (error.status === 404 && error.code === "route_not_found") return',
        'if (error.status === 404 && error.code === "route_not_found" && false) return',
        "Library: a route the controller does not have falls back",
    ),
    (
        "library_view.js",
        "const ignored = lib.curation.pins.filter(id => !draft.considered.has(id));",
        "const ignored = [];",
        "Library: the plan editor checks a plan",
    ),
    (
        "library_view.js",
        "for (const id of citesOf(row)) if (lib.curation.bans.includes(id))",
        "for (const id of citesOf(row)) if (false)",
        "Library: the plan editor checks a plan",
    ),
    (
        "library_view.js",
        'if (!offered("library_search") && !offered("library_list")) return',
        "if (false) return",
        "Library: a controller without it says so",
    ),
)


def _scripts():
    return SCRIPTS.findall((LAUNCHPAD / "index.html").read_text())


def test_every_page_script_is_one_the_controller_serves():
    """A script the page loads and the controller does not serve leaves its
    view empty in a real browser. library_view.js is served once the
    controller's STATIC table names it (an S4 handoff)."""
    from scripts.dev.miner_launchpad import controller

    names = _scripts()
    assert "library_view.js" in names
    for name in names:
        assert (LAUNCHPAD / name).is_file(), name
        assert controller.STATIC.get("/" + name, (None,))[0] == name, (
            "controller.STATIC does not serve /" + name
        )


def test_the_library_names_no_challenge_and_loads_nothing_from_the_internet():
    from carbon.challenge_registry import catalog

    ids = [c["challenge_id"] for c in catalog()["challenges"]]
    pattern = re.compile("|".join(re.escape(i) for i in ids))
    for name in ("library_view.js", "research_view.js", "app.js"):
        text = (LAUNCHPAD / name).read_text()
        assert not pattern.search(text), (name, pattern.search(text))
    library = (LAUNCHPAD / "library_view.js").read_text()
    assert not re.search(r"https?://", library)
    for pattern_text in ("innerHTML", "outerHTML", "insertAdjacentHTML", "DOMParser"):
        assert pattern_text not in library


def test_graphite_fields_are_sent_only_as_the_launch_declares_them():
    """The launch body takes Graphite's fields through `launchFields`, which
    keeps only what the controller's launch operation declares."""
    script = (LAUNCHPAD / "app.js").read_text()
    launch = script[script.index('$("research-launch").addEventListener') :]
    body = launch[: launch.index("sessionStorage.setItem(researchKey")]
    assert "launchFields(graphiteFields())" in body
    assert "composition.agent === GRAPHITE" in body


def test_the_fixture_adds_graphite_only_where_the_real_documents_lack_it():
    from control_center_graphite_fixture import GRAPHITE, _choices, _operations

    real = {
        "agents": {
            "choices": [
                {"id": "graphite", "launch_agent": GRAPHITE, "label": "real"},
                {"id": "manual", "launch_agent": "none", "label": "Manual"},
            ]
        }
    }
    assert _choices(json.loads(json.dumps(real))) == real
    listing = [
        {"operation": "launch", "required": ["agent"], "optional": ["budget"]},
        {"operation": "library_search", "required": ["q"], "optional": []},
    ]
    by_name = {op["operation"]: op for op in _operations(listing)}
    assert by_name["library_search"]["required"] == ["q"], "the real shape is kept"
    assert "graphite_mode" in by_name["launch"]["optional"]


@pytest.fixture
def node():
    found = shutil.which("node")
    if found is None:
        pytest.skip("node is not installed here")
    return found


def test_each_graphite_boundary_is_held_by_its_scenario(
    documents,  # noqa: F811 - fixture
    node,
    tmp_path,
):
    """Break each boundary in a copy of the page: its scenario fails."""
    source = {name: (LAUNCHPAD / name).read_text() for name in _scripts()}
    for index, (name, before, after, scenario) in enumerate(MUTATIONS):
        assert source[name].count(before) == 1, (name, before)
        root = tmp_path / ("page-" + str(index))
        root.mkdir()
        shutil.copy(LAUNCHPAD / "index.html", root / "index.html")
        for script, text in source.items():
            changed = text.replace(before, after) if script == name else text
            (root / script).write_text(changed)
        result = subprocess.run(
            [node, str(CHECK), str(documents), str(root), scenario],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        assert result.returncode == 0, result.stderr[-2000:]
        outcome = json.loads(result.stdout)
        ran = outcome["passed"] + outcome["failed"]
        assert any(item.startswith(scenario) or scenario in item for item in ran), (
            scenario,
            outcome,
        )
        assert outcome["failed"], (
            "the scenario held with its boundary broken: " + before,
            outcome,
        )
        assert not outcome["passed"], (before, outcome)
