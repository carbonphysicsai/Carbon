"""Graphite's documents for the Control Center's page checks (GRAPHITE-MINER-S5).

The page consumes the Launchpad's own JSON (slice S4 of the Graphite miner
edition): the capability document's Graphite choice, the launch options, the
operation listing with Graphite's launch fields and the Library's operations,
the campaign view's `graphite` block and the Library's answers. Each document
here starts from the one the real code built (the capability document, the
options, the operation listing, the campaign view and its observe row) and
adds Graphite's part in the shape the cross-slice interface states, only
where the real code does not already carry it: once S4's code is merged, its
own documents are used unchanged.

The cards, plans and curation are synthetic fixture values, labelled so in
their titles: never the shared pack, never a hunted paper, never evidence.
"""

from __future__ import annotations

import copy

GRAPHITE = "graphite"
PLAN_SCHEMA = "carbon.graphite.miner-plan.v1"
#: The launch operation's Graphite fields (S4's launch operation).
LAUNCH_FIELDS = ("graphite_mode", "research_share", "plan", "hunt", "limits")
_READ = ["request", "profile"]
_WRITE = ["request", "profile", "replay"]
#: The Library's operations as the interface names them, with the fields the
#: page sends: reads take no key; writes are replay-gated and take one.
LIBRARY_OPERATIONS = (
    ("library_search", ["query"], ["challenge", "challenge_version", "limit"], _READ),
    ("library_card", ["card_id"], [], _READ),
    ("library_list", [], [], _READ),
    ("plan_list", [], [], _READ),
    ("plan_get", ["plan"], [], _READ),
    ("library_pin", ["card_id"], ["idempotency_key"], _WRITE),
    ("library_unpin", ["card_id"], ["idempotency_key"], _WRITE),
    ("library_ban", ["card_id"], ["idempotency_key"], _WRITE),
    ("library_unban", ["card_id"], ["idempotency_key"], _WRITE),
    ("library_import", ["text", "title"], ["idempotency_key"], _WRITE),
    ("plan_edit", ["plan"], ["idempotency_key"], _WRITE),
)
PLAN_DIGEST = "a1" * 32
CARDS = [
    {
        "card_id": "fixture-shared-0001",
        "origin": "shared",
        "check_status": "UNCHECKED",
        "title": "Fixture card: residual MLP surrogate for a parametric response",
        "abstract": "Synthetic fixture abstract. Not a paper.",
        "technique": "residual MLP with a cosine schedule",
        "claimed_effect": "lower error on smooth regimes",
        "data_regime": "small data",
        "cost": "low",
        "code_available": True,
        "applicability": "buildable under the Challenge's contract",
        "provenance": {"source": "fixture", "id": "fixture.0001"},
        "score": 3,
        "reasons": [
            "matches the Challenge's public design variables",
            "buildable: a supported model family",
        ],
    },
    {
        "card_id": "fixture-shared-0002",
        "origin": "shared",
        "check_status": "UNCHECKED",
        "title": "Fixture card: graph surrogate with message passing",
        "abstract": "Synthetic fixture abstract. Not a paper.",
        "technique": "graph network",
        "claimed_effect": "transfers across meshes",
        "data_regime": "large data",
        "cost": "high",
        "code_available": False,
        "applicability": "not buildable here: a capability request candidate",
        "provenance": "fixture.0002",
        "score": 1,
        "reasons": ["unsupported family: flagged as a capability request candidate"],
    },
    {
        "card_id": "fixture-shared-0003",
        "origin": "shared",
        "check_status": "UNCHECKED",
        "title": "Fixture card: a banned MLP variant",
        "abstract": "Synthetic fixture abstract. Not a paper.",
        "technique": "MLP ensemble",
        "claimed_effect": "unclear",
        "score": 2,
        "reasons": ["matches the Challenge's public task"],
    },
    {
        "card_id": "fixture-hunt-0001",
        "origin": "miner_hunt",
        "check_status": "UNCHECKED",
        "title": "Fixture card: MLP width schedule from a hunt",
        "abstract": "Synthetic fixture abstract. Not a paper.",
        "technique": "progressive MLP widening",
        "claimed_effect": "faster convergence",
        "data_regime": "small data",
        "provenance": {"source": "fixture-hunt", "id": "fixture.0004"},
        "score": 2,
        "reasons": ["cited by your plan whose practice improved"],
    },
    {
        "card_id": "fixture-import-0001",
        "origin": "miner_import",
        "check_status": "UNCHECKED",
        "title": "Fixture card: your imported notes on MLP depth",
        "technique": "deeper MLP",
        "claimed_effect": "your own notes",
        "score": 1,
        "reasons": ["your import"],
    },
]


def _plan(recipe):
    return {
        "schema": PLAN_SCHEMA,
        "hypotheses": [
            {
                "hypothesis": "A wider residual MLP lowers the practice error.",
                "expected_effect": "a lower descriptive practice score",
                "stopping_rule": "two practice runs without improvement",
                "recipe": recipe,
                "cites": [
                    {"card_id": "fixture-hunt-0001", "origin": "miner_hunt"},
                    {"card_id": "fixture-shared-0001", "origin": "shared"},
                ],
            },
            {
                "hypothesis": "A cosine schedule steadies training.",
                "expected_effect": "a smoother learning curve",
                "stopping_rule": "one practice run",
                "cites": [{"card_id": "fixture-shared-0001", "origin": "shared"}],
            },
            {
                "hypothesis": "Fewer epochs keep the score.",
                "expected_effect": "the same score, less worker time",
                "stopping_rule": "one practice run",
                "cites": [],
            },
            {
                "hypothesis": "Fixture hypothesis four.",
                "expected_effect": "none",
                "stopping_rule": "one practice run",
                "cites": [],
            },
        ],
        "pins_considered": ["fixture-shared-0001"],
        "parent": None,
        "created_by": "planner",
    }


def _choices(caps):
    """Graphite in the capability document; the autonomous choice kept beside
    it, as a controller between versions might list it: the page must not
    offer it once Graphite is there."""
    choices = caps["agents"]["choices"]
    if any(choice.get("launch_agent") == GRAPHITE for choice in choices):
        return caps
    autonomous = next(c for c in choices if c["launch_agent"] == "autonomous")
    graphite = {
        **autonomous,
        "id": GRAPHITE,
        "label": "Graphite, Carbon's research agent",
        "summary": (
            "Reads the literature, writes a plan, then builds, practises, "
            "selects and submits within your budget."
        ),
        "launch_agent": GRAPHITE,
        "uses_model": True,
    }
    caps["agents"]["choices"] = [graphite, *choices]
    return caps


def _operations(listing):
    """The operation listing with Graphite's launch fields and the Library's
    operations, where the real listing does not have them yet."""
    by_name = {op["operation"]: copy.deepcopy(op) for op in listing}
    launch = by_name["launch"]
    launch["optional"] = sorted(set(launch["optional"]) | set(LAUNCH_FIELDS))
    for name, required, optional, gates in LIBRARY_OPERATIONS:
        by_name.setdefault(
            name,
            {
                "operation": name,
                "summary": "Fixture shape of the Library's " + name + ".",
                "required": sorted(required),
                "optional": sorted(optional),
                "gates": list(gates),
                "admits_work": False,
            },
        )
    return list(by_name.values())


def _without_library(listing):
    """A listing without any of the Library's operations: a controller that
    predates the miner edition."""
    names = {name for name, *_ in LIBRARY_OPERATIONS}
    return [op for op in listing if op["operation"] not in names]


def graphite_documents(base):
    """Graphite's documents, from the live page check's real ones (`base`)."""
    caps = _choices(copy.deepcopy(base["caps_setup_model"]))
    options = copy.deepcopy(base["options_setup_model"])
    options["agents"] = [
        {"value": GRAPHITE, "availability": "available"},
        {"value": "none", "availability": "available"},
    ]
    view = copy.deepcopy(base["view"])
    used = view["tiles"]["spend"]["used_nanodollars"]
    view.setdefault(
        "graphite",
        {
            "mode": "FULL",
            "stage": "build",
            "plan_digest": PLAN_DIGEST,
            "research_spent": used // 4,
            "research_share": 0.1,
            "hunt": {
                "fetched": 2,
                "deduped": 1,
                "triaged_out": 0,
                "extracted": 1,
                "failed_infra": 0,
                "cost_nanodollars": 90000,
            },
        },
    )
    run = copy.deepcopy(base["run"])
    run.setdefault("graphite", {"mode": "FULL", "stage": "build"})
    challenge = next(entry for entry in caps["challenges"] if entry["selectable"])
    recipe = challenge.get("example_strategy") or {"fixture": True}
    listing = _operations(base["operations"])
    return {
        "caps": caps,
        "options": options,
        "operations": listing,
        "operations_without_library": _without_library(listing),
        "view": view,
        "run": run,
        "library": {
            "cards": CARDS,
            "pins": ["fixture-shared-0001"],
            "bans": ["fixture-shared-0003"],
            "shared": {"cards": 1773, "digest": "fixture-pack-digest"},
            "plans": [
                {
                    "digest": PLAN_DIGEST,
                    "created_by": "planner",
                    "parent": None,
                    "created_at": 1800000000,
                    "plan": _plan(recipe),
                }
            ],
        },
    }
