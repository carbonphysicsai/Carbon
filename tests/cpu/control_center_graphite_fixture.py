"""Graphite's documents for the Control Center's page checks (GRAPHITE-MINER-S5).

The page consumes the Launchpad's own JSON (slice S4 of the Graphite miner
edition): the capability document's Graphite choice and `graphite` block, the
launch options' `graphite` block, the operation listing with Graphite's
launch fields and the Library's operations, each Challenge's
`setup_offers.graphite`, the campaign view's `graphite` section, the observe
row's `graphite` progress, and the Library's answers.

Each document starts from the one the real code built (the capability
document, the options, the operation listing, the campaign view and its
observe row). Where S4's code is present its own documents and functions are
used: the options and listing as they are, and the campaign's progress and
view section from `projection.graphite_progress` and
`campaign_view.graphite_section`. Where it is not (this slice alone), S4's
part is added in S4's own shape, field for field (`test_control_center_graphite`
holds the two equal once S4 is merged). The Library's answers are S4's shapes,
served by the page check's scripted controller over the store here, with
slice S3's plan rule (`plan.check_shape` and `validate_plan`).

The cards, plans and curation are synthetic fixture values, labelled so in
their titles: never the shared pack, never a hunted paper, never evidence.
"""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

GRAPHITE = "graphite"
EDITION = "carbon.graphite.miner-edition.v1"
PLAN_SCHEMA = "carbon.graphite.miner-plan.v1"
GRAPHITE_LABEL = "Graphite, Carbon's research agent"
#: The launch operation's Graphite fields (S4's launch operation).
LAUNCH_FIELDS = ("graphite_mode", "research_share", "plan", "hunt", "limits")
_READ = ["request", "profile"]
_WRITE = ["request", "profile", "replay"]
#: The Library's rows of S4's operations table, as `describe()` lists them:
#: (name, required, optional, gates).
LIBRARY_OPERATIONS = (
    (
        "library_search",
        ["challenge", "query"],
        ["card_limit", "challenge_version"],
        _READ,
    ),
    ("library_card", ["card_id"], [], _READ),
    ("library_list", [], [], _READ),
    ("plan_list", [], [], _READ),
    ("plan_get", ["plan"], [], _READ),
    ("library_pin", ["card_id"], ["idempotency_key"], _WRITE),
    ("library_unpin", ["card_id"], ["idempotency_key"], _WRITE),
    ("library_ban", ["card_id"], ["idempotency_key"], _WRITE),
    ("library_unban", ["card_id"], ["idempotency_key"], _WRITE),
    ("library_import", ["text", "title"], ["idempotency_key"], _WRITE),
    ("plan_edit", ["plan_document"], ["idempotency_key"], _WRITE),
)
#: S4's mode summaries (`runner.GRAPHITE_MODE_SUMMARIES`).
MODE_SUMMARIES = {
    "RESEARCH": (
        "Hunt (when asked) and read, then write a ranked plan into your "
        "library. Nothing is practised, selected or submitted."
    ),
    "BUILD": (
        "Take a plan - one you edited, one from an earlier Research run, or "
        "none, and the Planner writes one first - then construct, practise, "
        "select and submit."
    ),
    "FULL": "Research within the research share of your budget, then build. The default.",
}
#: S4's planning figures per abstract (`runner.READER_TOKENS_PER_ABSTRACT`).
READER_TOKENS_PER_ABSTRACT = {"input": 1000, "output": 250}
PLAN_DIGEST = "sha256:" + "a1" * 32
SHARED_PACK_DIGEST = "sha256:" + "5f" * 32
PRIVATE_SNAPSHOT = "sha256:" + "0c" * 32
CARDS = [
    {
        "card_id": "fixture-shared-0001",
        "origin": "shared",
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
        # S2's focus ranking: buildable under the Challenge's contract.
        "plan_input": True,
        "capability_request_candidate": False,
    },
    {
        "card_id": "fixture-shared-0002",
        "origin": "shared",
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
        "plan_input": False,
        "capability_request_candidate": True,
    },
    {
        "card_id": "fixture-shared-0003",
        "origin": "shared",
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
        "title": "Fixture card: your imported notes on MLP depth",
        "technique": "deeper MLP",
        "claimed_effect": "your own notes",
        "score": 1,
        "reasons": ["your import"],
    },
]
PINS = ["fixture-shared-0001"]
BANS = ["fixture-shared-0003"]


def plan_document(challenge, recipe):
    """A planner's plan in S3's closed shape (`plan.check_shape`)."""
    return {
        "schema": PLAN_SCHEMA,
        "challenge": challenge,
        "hypotheses": [
            {
                "rank": 1,
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
                "rank": 2,
                "hypothesis": "A cosine schedule steadies training.",
                "expected_effect": "a smoother learning curve",
                "stopping_rule": "one practice run",
                "cites": [{"card_id": "fixture-shared-0001", "origin": "shared"}],
            },
            {
                "rank": 3,
                "hypothesis": "Fewer epochs keep the score.",
                "expected_effect": "the same score, less worker time",
                "stopping_rule": "one practice run",
                "cites": [],
            },
            {
                "rank": 4,
                "hypothesis": "Fixture hypothesis four.",
                "expected_effect": "none",
                "stopping_rule": "one practice run",
                "cites": [],
            },
        ],
        "pins_considered": [
            {
                "card_id": "fixture-shared-0001",
                "consideration": "Its residual MLP is the first hypothesis's starting point.",
            }
        ],
        "parent": None,
        "created_by": "planner",
    }


def _implemented():
    """{(id, version)} of the Challenges with a registered research campaign:
    where S4 offers Graphite (`runner.graphite_offered`)."""
    from carbon.challenge_registry.campaigns import implemented_campaigns

    return [
        {"id": entry.challenge_id, "version": entry.version}
        for entry, _campaign in implemented_campaigns()
    ]


def _next_step(code):
    """The refusal catalog's next step for `code` (`supervisor.next_action`)."""
    from scripts.dev.miner_launchpad.supervisor import next_action

    return next_action(code)


def hunt_estimate():
    """S4's `runner.hunt_estimate` for a profile that chose no model in
    setup: the pinned default selection's price."""
    from carbon.development_session.model_provider import DEFAULT_SELECTION

    pricing = getattr(DEFAULT_SELECTION, "pricing", None)
    per = (
        None
        if pricing is None
        else READER_TOKENS_PER_ABSTRACT["input"] * pricing.input_nano
        + READER_TOKENS_PER_ABSTRACT["output"] * pricing.output_nano
    )
    return {
        "reader_tokens_per_abstract": dict(READER_TOKENS_PER_ABSTRACT),
        "model": DEFAULT_SELECTION.provider_id + ":" + DEFAULT_SELECTION.model_id,
        "nanodollars_per_abstract": per,
        "basis": (
            "an estimate from the model's price for planning only; a hunt "
            "spends what your provider reports, within your budget, and a "
            "paper already in the pack or your library is never read twice"
        ),
    }


def graphite_options():
    """S4's `runner.graphite_options`, field for field."""
    return {
        "agent": GRAPHITE,
        "edition": EDITION,
        "modes": [
            {"id": mode, "summary": MODE_SUMMARIES[mode], "default": mode == "FULL"}
            for mode in ("RESEARCH", "BUILD", "FULL")
        ],
        "research_share": {
            "default": 0.10,
            "minimum": 0,
            "maximum": 1,
            "mode": "FULL",
            "of": ["provider_nanodollars", "provider_attempts"],
        },
        "plan": {
            "mode": "BUILD",
            "from": "your library (plan_list)",
            "omitted": "the Planner writes one first",
        },
        "hunt": {
            # S3 runs a hunt only before RESEARCH's and FULL's Planner.
            "modes": ["RESEARCH", "FULL"],
            "max_queries": 8,
            "max_terms": 6,
            "terms": "letters, digits and -",
            "default_records": 200,
            # S2's hunt.MAX_RECORDS (S4 1bb9c7a2b).
            "max_records": 5000,
            "seconds_between_requests": 3,
            "omitted": (
                "no hunt; the shared pack and your library still serve, and "
                "queued imports wait for a launch that hunts"
            ),
            "estimate": hunt_estimate(),
        },
        "limits": {
            "keys": ["calls_per_epoch", "trials_per_epoch", "planner_calls"],
            "minimum": 1,
            # S3's edition.max_limit() (S4 1bb9c7a2b).
            "maximum": 100000,
            "omitted": "only your campaign ceilings - money, attempts, trials, time - bind",
        },
        # LAUNCHPAD-FINDINGS-F8-F9 (LA-F8): the input window and its advisory.
        "input_window": input_window(),
        "offered_for": _implemented(),
    }


def input_window():
    """S4's `runner.graphite_input_window` for a profile that chose no model
    in setup: the pinned default selection under a new Graphite plan's
    defaults (OWNER-GRAPHITE-MINER-INPUT-WINDOW-01). Carbon records no
    published context for it, so its window is the historical 65,536."""
    from carbon.agent_campaign.graphite.miner import driver
    from carbon.development_session import model_provider as mp

    selection = mp.select(
        provider_id=mp.DEFAULT_SELECTION.provider_id,
        model_id=mp.DEFAULT_SELECTION.model_id,
        credential={"kind": "file", "reference": "unset"},
        output_default=mp.OUTPUT_DEFAULT_V2,
        input_default=mp.INPUT_DEFAULT_V2,
    )
    window = driver.launch_window(selection)
    return {
        "launch_field": "model_settings.max_input_tokens",
        "default_rule": mp.INPUT_DEFAULT_V2,
        "default": 65536,
        "launch_default": {
            "model": selection.provider_id + ":" + selection.model_id,
            **window,
        },
        "advised_at_or_below": 65536,
        "advisory": "graphite_input_window_too_small",
        "next_step": _next_step("graphite_input_window_too_small"),
    }


#: S4's capability document `graphite.library` block.
LIBRARY_BLOCK = {
    "reads": [
        "library_search",
        "library_card",
        "library_list",
        "plan_list",
        "plan_get",
    ],
    "writes": [
        "library_pin",
        "library_unpin",
        "library_ban",
        "library_unban",
        "library_import",
        "plan_edit",
    ],
    "http": {
        "library": "/api/v1/library/<search|card|list|pin|unpin|ban|unban|import>",
        "plans": "/api/v1/plans/<list|get|edit>",
    },
    "check_status": "UNCHECKED",
    "origins": ["shared", "miner_hunt", "miner_import"],
}


def _capabilities(caps, offer):
    """The capability document as S4 builds it: Graphite in the autonomous
    agent's place (which it no longer offers), its `graphite` block, and
    each Challenge's `setup_offers.graphite`."""
    choices = caps["agents"]["choices"]
    if not any(choice.get("launch_agent") == GRAPHITE for choice in choices):
        autonomous = next(c for c in choices if c["launch_agent"] == "autonomous")
        state = {
            k: autonomous[k]
            for k in ("availability", "reason", "next_action")
            if k in autonomous
        }
        graphite = {
            "id": GRAPHITE,
            "label": GRAPHITE_LABEL,
            "summary": (
                "Graphite hunts and reads literature, writes a ranked plan, "
                "then constructs, practises, selects and submits, on your "
                "model within your budget. Choose Research, Build or Full."
            ),
            "launch_agent": GRAPHITE,
            "uses_model": True,
            "modes": offer["modes"],
            "launch_fields": list(LAUNCH_FIELDS),
            **state,
        }
        caps["agents"]["choices"] = [
            graphite if c is autonomous else c for c in choices
        ]
        caps["model"]["used_by"] = [GRAPHITE]
    caps.setdefault("graphite", {**offer, "library": LIBRARY_BLOCK})
    offered = {(item["id"], item["version"]) for item in offer["offered_for"]}
    for entry in caps["challenges"]:
        offers = entry.get("setup_offers")
        if type(offers) is dict and "graphite" not in offers:
            offers["graphite"] = (entry["challenge_id"], entry["version"]) in offered
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
                "summary": "Fixture shape of S4's " + name + ".",
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


#: A Graphite campaign's hunt report, as S3's hunt stage record keeps it
#: (`<campaign>/graphite/stages/hunt.json`, its `report`: S2's HuntReport).
HUNT_REPORT = {
    "fetched": 2,
    "deduped": 1,
    "triaged_out": 0,
    "extracted": 1,
    "failed_infra": False,
    "cards": ["fixture-hunt-0001"],
}
_HUNT_COUNTS = ("fetched", "deduped", "triaged_out", "extracted", "failed_infra")


def campaign_inputs(used, ceiling):
    """A FULL campaign that hunted, stopped its Planner at the research share
    and is building: its frozen provider plan, its ledger operations (the
    hunt's Reader calls `graphite-reader-*`, S1's stage identities for the
    Planner, an unstaged epoch for the build) and S3's own view of its
    records (`miner.driver.view`). A quarter of the model spend `used` is
    research's; the share caps a tenth of the model-spend `ceiling`."""
    research = max(used // 4, 3)
    hunt = research // 4
    block = {
        "edition": EDITION,
        "mode": "FULL",
        "research_share": 0.1,
        "plan_digest": None,
        "hunt": {"queries": None, "max_records": 200},
    }
    manifest = {"agent": GRAPHITE, "provider": {"graphite": block}}

    def op(identity, nanodollars):
        return {
            "id": identity,
            "reservation": {
                "provider_nanodollars": nanodollars,
                "provider_attempts": 1,
            },
            "actual": {"provider_nanodollars": nanodollars, "provider_attempts": 1},
        }

    operations = [
        op("graphite-reader-fixture-0001", hunt),
        op("graphite-reader-fixture-0002", hunt),
        {"id": "research-epoch-1-plan", "reservation": {}, "actual": None},
        op("epoch-1-plan-provider-001", research - 2 * hunt),
        op("epoch-2-provider-001", max(used - research, 0)),
    ]
    seen = {
        "schema": "carbon.graphite.miner-view.v1",
        "edition": EDITION,
        "mode": "FULL",
        "stage": "build",
        "stages": [
            {"stage": "hunt", "state": "DONE", "code": None},
            {"stage": "plan", "state": "STOPPED", "code": "research_share_reached"},
            {"stage": "build", "state": "RUNNING", "code": None},
        ],
        # The plan this campaign's Planner wrote.
        "plan_digest": PLAN_DIGEST,
        "research_share": 0.1,
        "research_spent": {"provider_nanodollars": research, "provider_attempts": 3},
        # S3's `budget.share_caps`: only the dimensions the miner capped.
        "research_cap": (
            {"provider_nanodollars": int(ceiling * 0.1)} if type(ceiling) is int else {}
        ),
        "hunt": {"extracted": 1, "deduped": 1, "cost_nanodollars": 2 * hunt},
    }
    return manifest, {"operations": operations}, seen


def graphite_progress(used, ceiling):
    """The observe row's `graphite` (S4's `projection.graphite_progress`):
    S4's own function when present, over S3's view of its records as
    `campaign_inputs` states it (S4's `_graphite_view` seam), else its
    result for the same inputs."""
    try:
        from scripts.dev.miner_launchpad import projection
    except ImportError:
        projection = None
    if projection is None or not hasattr(projection, "_graphite_view"):
        return emulated_progress(used, ceiling)
    manifest, status, seen = campaign_inputs(used, ceiling)
    original = projection._graphite_view
    projection._graphite_view = lambda root, operations: copy.deepcopy(seen)
    try:
        with tempfile.TemporaryDirectory() as root:
            stages = Path(root) / "graphite" / "stages"
            stages.mkdir(parents=True)
            (stages / "hunt.json").write_text(json.dumps({"report": HUNT_REPORT}))
            return projection.graphite_progress(manifest, status, root)
    finally:
        projection._graphite_view = original


def emulated_progress(used, ceiling):
    """What S4's `projection.graphite_progress` gives for `campaign_inputs`."""
    manifest, status, seen = campaign_inputs(used, ceiling)
    readers = [
        op for op in status["operations"] if op["id"].startswith("graphite-reader-")
    ]
    return {
        "edition": EDITION,
        "mode": "FULL",
        "stage": seen["stage"],
        "stages": copy.deepcopy(seen["stages"]),
        "plan_digest": seen["plan_digest"],
        "research_share": manifest["provider"]["graphite"]["research_share"],
        "research_spent": dict(seen["research_spent"]),
        "research_cap": {
            "provider_nanodollars": seen["research_cap"].get("provider_nanodollars"),
            "provider_attempts": None,
        },
        "hunt": {
            **{name: int(HUNT_REPORT[name]) for name in _HUNT_COUNTS},
            "reader_calls": len(readers),
            "cost_nanodollars": sum(
                op["actual"]["provider_nanodollars"] for op in readers
            ),
        },
    }


def graphite_section(progress):
    """The campaign view's `graphite` (S4's `campaign_view.graphite_section`)."""
    try:
        from scripts.dev.miner_launchpad.campaign_view import graphite_section as real
    except ImportError:
        return emulated_section(progress)
    return real({"graphite": progress})


def emulated_section(progress):
    """What S4's `campaign_view.graphite_section` gives for `progress`."""
    return {
        "edition": progress["edition"],
        "mode": progress["mode"],
        "stage": progress["stage"],
        "stages": copy.deepcopy(progress["stages"]),
        "plan_digest": progress["plan_digest"],
        "research_share": progress["research_share"],
        "research_spent": dict(progress["research_spent"]),
        "research_cap": dict(progress["research_cap"]),
        "hunt": {
            key: progress["hunt"].get(key)
            for key in (
                "fetched",
                "deduped",
                "triaged_out",
                "extracted",
                "failed_infra",
                "reader_calls",
                "cost_nanodollars",
            )
        },
        "cards": "UNCHECKED: the agent's literature is never checked by Carbon",
    }


def graphite_documents(base):
    """Graphite's documents, from the live page check's real ones (`base`)."""
    options = copy.deepcopy(base["options_setup_model"])
    offer = options.get("graphite") or graphite_options()
    options["graphite"] = offer
    options["agents"] = [
        {"value": "none", "availability": "available"},
        {"value": GRAPHITE, "availability": "available"},
    ]
    caps = _capabilities(copy.deepcopy(base["caps_setup_model"]), offer)
    view = copy.deepcopy(base["view"])
    spend = view["tiles"]["spend"]
    progress = graphite_progress(
        spend["used_nanodollars"], spend["ceiling_nanodollars"]
    )
    if view.get("graphite") is None:
        view["graphite"] = graphite_section(progress)
    run = copy.deepcopy(base["run"])
    if run.get("graphite") is None:
        run["graphite"] = progress
    challenge = next(entry for entry in caps["challenges"] if entry["selectable"])
    recipe = challenge.get("example_strategy") or {"fixture": True}
    named = {"id": challenge["challenge_id"], "version": challenge["version"]}
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
            "pins": list(PINS),
            "bans": list(BANS),
            "shared_pack": {
                "available": True,
                "digest": SHARED_PACK_DIGEST,
                "cards": 1773,
                "check_status": "UNCHECKED",
            },
            "private_snapshot": PRIVATE_SNAPSHOT,
            "plans": [
                {
                    "digest": PLAN_DIGEST,
                    "created_by": "planner",
                    "parent": None,
                    "created_at": 1800000000,
                    "plan": plan_document(named, recipe),
                }
            ],
        },
    }
