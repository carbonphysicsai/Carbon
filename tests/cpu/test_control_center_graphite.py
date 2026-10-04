"""Graphite in the Control Center (GRAPHITE-MINER-S5, OWNER-GRAPHITE-MINER-01).

The page's Graphite views run in Node with the other page checks
(control_center_page_check.cjs, driven by test_control_center_live_page):
the launch wizard's Graphite choices (mode, research share, plan, hunt with
its cost estimate, optional per-epoch limits), the campaign's Graphite part
and the Library (cards with origin and UNCHECKED labels, ranked search with
reasons, pin and ban, import, plans and the plan editor).

Here each boundary those scenarios hold is shown to be held by them: the
page is copied, one boundary is broken in the copy, and the scenario that
holds it must then fail. The page's own files are checked: every script it
loads is one the controller serves, and none names a Challenge or loads
anything from the internet. And the documents the scenarios run on are held
to slice S4's and S3's own code where that code is present: the fixture's
Graphite options, operation rows, capability block, campaign progress and
view section equal S4's, and every plan the page sends passes S3's plan rule.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from control_center_graphite_fixture import (
    CARDS,
    LIBRARY_BLOCK,
    LIBRARY_OPERATIONS,
    PLAN_DIGEST,
    _capabilities,
    _operations,
    campaign_inputs,
    graphite_options,
    plan_document,
)
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
        'some(choice => choice.launch_agent === GRAPHITE || choice.reason === "autonomous_agent_replaced")',
        'some(choice => choice.reason === "autonomous_agent_replaced")',
        "Graphite: offered in place of the autonomous agent",
    ),
    (
        "app.js",
        'if (typeof entry.setup_offers?.graphite === "boolean") return entry.setup_offers.graphite;',
        "",
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
        "const records = hunt.default_records ?? hunt.max_records_default;",
        "const records = hunt.max_records ?? hunt.max_records_default;",
        "Graphite: each mode launches with exactly its own fields",
    ),
    (
        "app.js",
        'plan: "", hunt: false,',
        'plan: "", hunt: true,',
        "Graphite: each mode launches with exactly its own fields",
    ),
    (
        "app.js",
        'return Array.isArray(modes) ? modes.includes(g.mode) : g.mode !== "BUILD";',
        "return true;",
        "Graphite: each mode launches with exactly its own fields",
    ),
    (
        "app.js",
        'if (!parts.length) return "Research may use "',
        'if (false) return "Research may use "',
        "Graphite: each mode launches with exactly its own fields",
    ),
    (
        "app.js",
        "const missing = Object.keys(graphiteFields(g)).filter(key => !declared.has(key));",
        "const missing = [];",
        "Graphite: a choice the controller's launch does not take",
    ),
    (
        "app.js",
        "const problem = queryProblem(huntQueries(g.queries));",
        "const problem = null;",
        "Graphite: the hunt estimate is Carbon's",
    ),
    (
        "app.js",
        'estimate.model === chosen.provider + ":" + chosen.model',
        "false",
        "Graphite: the hunt estimate is Carbon's",
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
        "app.js",
        "if (!ENDED[state]) return graphiteStage(stage);",
        "return graphiteStage(stage);",
        "Graphite: the campaign shows its stage",
    ),
    (
        "research_view.js",
        "box => { if (doc.graphite) drawGraphite(box, doc); }",
        "box => {}",
        "Graphite: the campaign shows its stage",
    ),
    (
        "research_view.js",
        'if (hunt.failed_infra === true || (typeof hunt.failed_infra === "number" && hunt.failed_infra > 0)) {',
        "if (hunt.failed_infra === true) {",
        "Graphite: the campaign shows its stage",
    ),
    (
        "research_view.js",
        'if (stages.length) row("Stages",',
        'if (false) row("Stages",',
        "Graphite: the campaign shows its stage",
    ),
    (
        "research_view.js",
        "const caps = stated ? [",
        "const caps = false ? [",
        "Graphite: the campaign shows its stage",
    ),
    (
        "library_view.js",
        "if (card.capability_request_candidate === true) {",
        "if (false) {",
        "Library: every card says where it came from and UNCHECKED",
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
        'shared: value?.shared_pack && typeof value.shared_pack === "object" ? value.shared_pack : null,',
        "shared: null,",
        "Library: every card says where it came from and UNCHECKED",
    ),
    (
        "library_view.js",
        'if (field === "card_limit") body.card_limit = SEARCH_LIMIT;',
        'if (field === "card_limit") body.limit = SEARCH_LIMIT;',
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
        "CC.releaseHeld?.((slot, action) => {",
        "void ((slot, action) => {",
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
        "const ignored = lib.curation.pins.filter(id => !text(draft.considerations.get(id)).trim());",
        "const ignored = [];",
        "Library: the plan editor checks a plan",
    ),
    (
        "library_view.js",
        "else if (lib.curation.bans.includes(id)) problems.push(",
        "else if (false) problems.push(",
        "Library: the plan editor checks a plan",
    ),
    (
        "library_view.js",
        "rank: index + 1,",
        "",
        "Library: the plan editor checks a plan",
    ),
    (
        "library_view.js",
        ".map(([id, line]) => ({card_id: id, consideration: line}))",
        ".map(([id]) => id)",
        "Library: the plan editor checks a plan",
    ),
    (
        "library_view.js",
        'plan_edit: {route: "/api/v1/plans/edit", fields: ["plan_document"]},',
        'plan_edit: {route: "/api/v1/plans/edit", fields: ["plan"]},',
        "Library: the plan editor checks a plan",
    ),
    (
        "library_view.js",
        "challenge: named || (lib.challenge ? {...lib.challenge} : null),",
        "challenge: named,",
        "Library: a plan written from scratch",
    ),
    (
        "library_view.js",
        "lib.drafts.set(key, {key, parent:",
        "lib.drafts.clear(); lib.drafts.set(key, {key, parent:",
        "Library: a draft is kept",
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
    keeps only what the controller's launch operation declares; and a field
    it does not declare blocks the launch instead (`graphiteUndeclared`)."""
    script = (LAUNCHPAD / "app.js").read_text()
    launch = script[script.index('$("research-launch").addEventListener') :]
    body = launch[: launch.index("sessionStorage.setItem(researchKey")]
    assert "launchFields(graphiteFields())" in body
    assert "composition.agent === GRAPHITE" in body
    assert "graphiteChoiceProblem() || graphiteUndeclared()" in script


def test_the_fixture_adds_graphite_only_where_the_real_documents_lack_it():
    real = {
        "agents": {
            "choices": [
                {"id": "graphite", "launch_agent": "graphite", "label": "real"},
                {"id": "manual", "launch_agent": "none", "label": "Manual"},
            ]
        },
        "model": {"used_by": ["graphite"]},
        "graphite": {"real": True},
        "challenges": [
            {"challenge_id": "a", "version": "1", "setup_offers": {"graphite": False}}
        ],
    }
    offer = {"modes": [], "offered_for": [{"id": "a", "version": "1"}]}
    assert _capabilities(json.loads(json.dumps(real)), offer) == real
    listing = [
        {"operation": "launch", "required": ["agent"], "optional": ["budget"]},
        {"operation": "library_search", "required": ["q"], "optional": []},
    ]
    by_name = {op["operation"]: op for op in _operations(listing)}
    assert by_name["library_search"]["required"] == ["q"], "the real shape is kept"
    assert "graphite_mode" in by_name["launch"]["optional"]
    assert by_name["plan_edit"]["required"] == ["plan_document"]


# --- Held to S4's and S3's own code, where it is present ----------------------


def test_the_fixture_is_s4s_own_shape_where_s4_is_present():
    """Once S4 is merged, the fixture's Graphite options, capability block,
    operation rows, campaign progress and view section are S4's, field for
    field: the page checks on this slice alone ran on S4's shapes."""
    runner = pytest.importorskip("scripts.dev.miner_launchpad.runner")
    if not hasattr(runner, "graphite_options"):
        pytest.skip("S4 (Graphite in the Launchpad) is not merged here")
    import control_center_graphite_fixture as fixture

    from scripts.dev.miner_launchpad import capabilities, operations
    from scripts.dev.miner_launchpad.campaign_view import graphite_section

    # A profile that chose no model in setup: the pinned default's price.
    assert graphite_options() == runner.graphite_options({})
    assert fixture.GRAPHITE_LABEL == capabilities.GRAPHITE_LABEL
    assert LIBRARY_BLOCK == capabilities._graphite({"graphite": {}}, None)["library"]
    described = {op["operation"]: op for op in operations.describe()}
    for name, required, optional, gates in LIBRARY_OPERATIONS:
        row = described[name]
        assert (row["required"], row["optional"], row["gates"], row["admits_work"]) == (
            sorted(required),
            sorted(optional),
            gates,
            False,
        ), name
    assert set(fixture.LAUNCH_FIELDS) <= set(described["launch"]["optional"])
    assert fixture.READER_TOKENS_PER_ABSTRACT == runner.READER_TOKENS_PER_ABSTRACT
    # The campaign's progress (S4's projection over S3's view of its records)
    # and view section: S4's functions, and the fixture's own result for the
    # same inputs, agree.
    used, ceiling = 4_000_000, 20_000_000
    _, status, seen = campaign_inputs(used, ceiling)
    real = fixture.graphite_progress(used, ceiling)
    assert real == fixture.emulated_progress(used, ceiling)
    assert real["research_spent"] == seen["research_spent"]
    readers = [
        op for op in status["operations"] if op["id"].startswith("graphite-reader-")
    ]
    assert real["hunt"]["reader_calls"] == len(readers) == 2
    assert graphite_section({"graphite": real}) == fixture.emulated_section(real)


def test_the_fixture_plan_and_every_plan_the_page_sends_keep_s3s_rule(
    documents,  # noqa: F811 - fixture
    node,
):
    """The page's plan editor sends Graphite's plan in S3's closed shape: run
    the Library's scenarios, collect every plan document the scripted
    controller was sent, and check each with S3's own `check_shape` (and the
    fixture's planner plan with `validate_plan`) where S3 is present."""
    result = subprocess.run(
        [node, str(CHECK), str(documents), str(LAUNCHPAD), "Library: "],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    outcome = json.loads(result.stdout)
    assert outcome["passed"] and not outcome["failed"], outcome["failed"]
    sent = outcome["plans_sent"]
    assert len(sent) >= 3, sent
    try:
        from carbon.agent_campaign.graphite.miner.plan import (
            check_shape,
            validate_plan,
        )
    except ImportError:
        pytest.skip("S3 (the miner plan rule) is not merged here")
    for plan in sent:
        check_shape({**plan, "created_by": "miner"})
    challenge = {"id": "fixture", "version": "1"}
    planner = plan_document(challenge, {"fixture": True})
    check_shape(planner)

    class Library:
        def card(self, card_id):
            for card in CARDS:
                if card["card_id"] == card_id:
                    return card
            raise KeyError(card_id)

        def plan(self, digest):
            raise KeyError(digest)

    ok, refusal = validate_plan(
        planner,
        library=Library(),
        curation={"pins": ["fixture-shared-0001"], "bans": ["fixture-shared-0003"]},
    )
    assert ok, refusal
    assert PLAN_DIGEST.startswith("sha256:")


def test_the_documents_carry_graphite_in_s4s_shape(documents):  # noqa: F811
    """What the page checks run on, from these documents."""
    value = json.loads(documents.read_text())["graphite"]
    choices = {c["id"]: c for c in value["caps"]["agents"]["choices"]}
    assert "graphite" in choices and "autonomous" not in choices
    assert choices["graphite"]["launch_agent"] == "graphite"
    hunt = value["options"]["graphite"]["hunt"]
    assert (hunt["default_records"], hunt["max_records"]) == (200, 5000)
    assert value["options"]["graphite"]["limits"]["maximum"] == 100000
    assert set(hunt["estimate"]) >= {
        "reader_tokens_per_abstract",
        "model",
        "nanodollars_per_abstract",
    }
    assert any(
        entry.get("setup_offers", {}).get("graphite") is True
        for entry in value["caps"]["challenges"]
    )
    assert hunt["modes"] == ["RESEARCH", "FULL"], "S3 runs no hunt in BUILD"
    section = value["view"]["graphite"]
    assert set(section["research_spent"]) == {
        "provider_nanodollars",
        "provider_attempts",
    }
    assert set(section["research_cap"]) == {"provider_nanodollars", "provider_attempts"}
    assert [row["stage"] for row in section["stages"]] == ["hunt", "plan", "build"]
    assert section["hunt"]["failed_infra"] == 0, "counted 0 or 1 by the view"
    assert value["run"]["graphite"]["stage"] == "build"
    rows = {op["operation"]: op for op in value["operations"]}
    assert rows["library_search"]["optional"] == ["card_limit", "challenge_version"]
    assert "plan_document" in rows["plan_edit"]["required"]
    plan = value["library"]["plans"][0]["plan"]
    assert [h["rank"] for h in plan["hypotheses"]] == [1, 2, 3, 4]
    assert set(plan["pins_considered"][0]) == {"card_id", "consideration"}


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
