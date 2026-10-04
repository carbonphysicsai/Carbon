"""Graphite's miner edition driver (OWNER-GRAPHITE-MINER-01, slice S3).

DEVELOPMENT FIXTURES ONLY. The literature slice's modules (`pack`, `library`,
`hunt`) and the engine slice's `run_epoch` keywords (`stage`, `finish`,
`limits`, `compaction`) are stood in for by fixtures with exactly their
interface shapes, installed for each test. The campaign ledger, the research
share, the Reader's metered model calls (`research_agent.request_model`), the
toolbox and the campaign's submit (`research_campaign.submit_or_retain`) are
real. Scripted replies test control flow, never agent evidence.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest
from test_cw1_research_loop import response

from carbon.agent_campaign.graphite import miner as miner_package
from carbon.agent_campaign.graphite.miner import budget, driver
from carbon.agent_campaign.graphite.miner import edition as editions
from carbon.agent_campaign.graphite.miner import plan as plans
from carbon.battery.campaign import provider_plan
from carbon.battery.challenge import CHALLENGE
from carbon.development_session import research_campaign
from carbon.development_session.data import write_once
from carbon.development_session.model_provider import DEFAULT_SELECTION
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent import RESERVATION_NANO, request_model
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    PARALLEL_CALLS_V2,
)
from carbon.development_session.research_ledger import PRODUCT, CampaignLedger
from carbon.development_session.research_tools import PREFIX

PACKAGE = "carbon.agent_campaign.graphite.miner"
CHALLENGE_REF = {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version}
PACK_DIGEST = "sha256:" + "5" * 64
START = PREFIX + "start_research_task"
RECIPE = {
    "schema_version": "1.0",
    "challenge_id": CHALLENGE.challenge_id,
    "backbone": "knn",
    "parameters": {"neighbours": 6},
}
UNPRACTISED = {**RECIPE, "parameters": {"neighbours": 3}}


def make_card(card_id, origin, title="A surrogate method"):
    return {
        "card_id": card_id,
        "title": title,
        "abstract": "Fixture abstract for " + title,
        "technique": "neural operator",
        "claimed_effect": "fixture text only",
        "data_regime": "synthetic",
        "cost": "not stated",
        "code_available": False,
        "applicability": "battery surrogate construction",
        "provenance": "DEVELOPMENT FIXTURE",
        "origin": origin,
        "check_status": "UNCHECKED",
    }


SHARED = (
    make_card("arxiv-2401.00001", "shared", "Fourier neural operator for ageing"),
    make_card("arxiv-2401.00002", "shared", "DeepONet surrogate for fast charge"),
)
#: The fixture arXiv feed: one paper already in the shared pack, one new.
FEED = (
    {"arxiv_id": "2401.00001", "title": "Fourier neural operator for ageing"},
    {"arxiv_id": "2402.00009", "title": "Physics-informed battery operator"},
)
HUNTED = "arxiv-2402.00009"


# --- the literature slice's interface, as fixtures ----------------------------


class Library:
    """DEVELOPMENT FIXTURE: `library.MinerLibrary(root)`'s interface shape.
    One instance per root, so a resume meets the same library."""

    opened: ClassVar[dict] = {}

    def __init__(self, root):
        self.root = Path(root)
        self.private = {}
        self.pins, self.bans = [], []
        self.saved = {}
        self.outcomes = []

    @classmethod
    def open(cls, root):
        return cls.opened.setdefault(Path(root), cls(root))

    def curation(self):
        body = {"pins": sorted(self.pins), "bans": sorted(self.bans)}
        return {**body, "digest": digest(canonical(body))}

    def snapshot(self):
        return digest(canonical(sorted(self.private)))

    def card(self, card_id):
        for card in SHARED:
            if card["card_id"] == card_id:
                return dict(card)
        return self.private.get(card_id)

    def add(self, card):
        self.private[card["card_id"]] = card

    def save_plan(self, plan):
        address = digest(canonical(plan))
        self.saved[address] = plan
        return address

    def plan(self, address):
        return self.saved.get(address)

    def plans(self):
        return [
            {"digest": d, "created_by": p["created_by"], "parent": p["parent"]}
            for d, p in self.saved.items()
        ]

    def record_outcome(self, card_ids, improved, evidence):
        self.outcomes.append((list(card_ids), improved, evidence))


class Literature:
    """DEVELOPMENT FIXTURE: `library.MinerLiterature`'s interface shape."""

    def __init__(self, pack, library, *, challenge, private_snapshot_digest, curation):
        assert challenge == CHALLENGE_REF
        self.library = library
        self.bans = set(curation["bans"])
        self.cards = [*pack.cards, *library.private.values()]
        self.snapshot = private_snapshot_digest

    def lit_search(self, arguments):
        words = set(arguments["query"].lower().split())
        return {
            "status": "OK",
            "results": [
                {
                    "card_id": card["card_id"],
                    "title": card["title"],
                    "origin": card["origin"],
                    "check_status": "UNCHECKED",
                    "score": 1,
                    "reasons": ["fixture"],
                }
                for card in self.cards
                if words & set(card["title"].lower().split())
                and card["card_id"] not in self.bans
            ],
        }

    def lit_card(self, arguments):
        for card in self.cards:
            if card["card_id"] == arguments["card_id"]:
                return {"status": "OK", "card": dict(card)}
        return {"status": "NOT_FOUND", "card_id": arguments["card_id"]}


class Hunt:
    """DEVELOPMENT FIXTURE: `hunt.run_hunt`'s interface shape. Dedups on the
    pack and the library before any Reader call, extracts the rest through
    the driver's Reader, and stores each as a miner_hunt card."""

    def __init__(self):
        self.calls = []

    def run_hunt(
        self,
        library,
        *,
        challenge,
        discovery,
        queries,
        max_records=200,
        reader,
        arxiv_opener,
        clock,
        checkpoint,
    ):
        self.calls.append(
            {"challenge": challenge, "queries": queries, "max_records": max_records}
        )
        assert discovery["contract_digest"]
        feed = arxiv_opener(queries)
        report = {
            "fetched": 0,
            "deduped": 0,
            "triaged_out": 0,
            "extracted": 0,
            "failed_infra": 0,
            "cards": [],
        }
        if feed is None:
            report["failed_infra"] = 1
            return report
        for record in feed[:max_records]:
            checkpoint()
            report["fetched"] += 1
            card_id = "arxiv-" + record["arxiv_id"]
            if library.card(card_id) is not None:
                report["deduped"] += 1
                continue
            reply = reader(
                reader.request(
                    "extract",
                    {
                        "task": "extract_method_card",
                        "content_is_data": True,
                        "paper": record,
                    },
                )
            )
            json.loads(reply["output"][0]["content"][0]["text"])
            library.add(make_card(card_id, "miner_hunt", record["title"]))
            report["extracted"] += 1
            report["cards"].append(card_id)
        return report


def install_literature(monkeypatch):
    """The literature slice's modules, as fixtures with its interface."""
    Library.opened = {}
    hunt = Hunt()
    copies = []

    def freeze_into(root):
        copies.append(Path(root))
        return PACK_DIGEST

    modules = {
        "pack": SimpleNamespace(
            SHARED_PACK_DIGEST=PACK_DIGEST,
            load_shared_pack=lambda: SimpleNamespace(digest=PACK_DIGEST, cards=SHARED),
            freeze_into=freeze_into,
        ),
        "library": SimpleNamespace(
            MinerLibrary=Library.open, MinerLiterature=Literature
        ),
        "hunt": SimpleNamespace(run_hunt=hunt.run_hunt),
    }
    for name, value in modules.items():
        module = types.ModuleType(PACKAGE + "." + name)
        module.__dict__.update(vars(value))
        monkeypatch.setitem(sys.modules, PACKAGE + "." + name, module)
        monkeypatch.setattr(miner_package, name, module, raising=False)
    return SimpleNamespace(hunt=hunt, pack_copies=copies)


# --- the engine slice's interface, as a fixture -------------------------------


def text_reply(text):
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }


EXTRACTION = json.dumps(
    {
        "relevant": True,
        "method_name": "fixture",
        "family": "neural operator",
        "construction_claims": [],
        "required_inputs": [],
        "reported_evidence": [],
        "data_regime": "not stated",
        "cost": "not stated",
        "code_available": False,
        "applicability": "fixture",
    }
)


class Transport:
    """The model provider, scripted: a Reader request (no tools) gets an
    extraction, a role's turn an empty reply. `forbid` fails any call."""

    def __init__(self, forbid=False):
        self.requests = []
        self.forbid = forbid

    def __call__(self, request):
        assert not self.forbid, "no model call is expected here"
        self.requests.append(json.loads(canonical(request)))
        if not request["tools"]:
            return response([text_reply(EXTRACTION)])
        return response([])

    @property
    def reader_calls(self):
        return [r for r in self.requests if not r["tools"]]


class Engine:
    """DEVELOPMENT FIXTURE: `research_loop.run_epoch` with the engine slice's
    keywords. Each scripted turn is one metered model call (identity
    `epoch-N[-<stage>]-provider-NNN`) and then its tool calls, run against
    the stage's toolbox, or locally for a finish, a selection or a stop.
    A finished stage's outcome replays from `outcome.json`."""

    def __init__(self, scripts=None):
        self.scripts = scripts or {}
        self.calls = []
        self.results = []

    async def __call__(
        self,
        ledger,
        *,
        owner,
        epoch,
        sdk,
        credential_file,
        initial_observation,
        transport=None,
        agent_policy=None,
        challenge=None,
        provider=DEFAULT_SELECTION,
        parallel_calls=None,
        instructions=None,
        tools=None,
        miner_guidance=None,
        max_provider_calls=None,
        stage=None,
        finish=None,
        limits=None,
        compaction=None,
    ):
        self.calls.append(
            {
                "ledger": ledger,
                "epoch": epoch,
                "stage": stage,
                "sdk": sdk,
                "observation": initial_observation,
                "agent_policy": agent_policy,
                "challenge": challenge,
                "parallel_calls": parallel_calls,
                "instructions": instructions,
                "tools": tools,
                "miner_guidance": miner_guidance,
                "finish": finish,
                "limits": limits,
                "compaction": compaction,
                "max_provider_calls": max_provider_calls,
            }
        )
        folder = ledger.root / f"epoch-{epoch}" / (stage or "")
        folder.mkdir(parents=True, exist_ok=True)
        if (folder / "outcome.json").exists():
            return json.loads((folder / "outcome.json").read_bytes())
        prefix = f"epoch-{epoch}-{stage}-" if stage else f"epoch-{epoch}-"
        outcome = None
        for index, turn in enumerate(self.scripts.get((stage, epoch), ())):
            request = {
                "model": provider.model_id,
                "instructions": instructions,
                "input": [
                    {
                        "role": "user",
                        "content": canonical(initial_observation).decode(),
                    },
                    {"role": "user", "content": f"turn {index}"},
                ],
                "tools": tools,
                "parallel_tool_calls": True,
                "store": False,
                "max_output_tokens": provider.settings.max_output_tokens,
                "reasoning": None,
            }
            await asyncio.to_thread(
                request_model,
                ledger,
                owner=owner,
                identity=f"{prefix}provider-{index:03d}",
                request=request,
                credential_file=credential_file,
                transport=transport,
                provider=provider,
                accept_incomplete=True,
            )
            for position, (name, arguments) in enumerate(turn):
                identity = f"{prefix}tool-{index:03d}" + (
                    f"-{position:02d}" if position else ""
                )
                if finish is not None and name == finish["tool"]["name"]:
                    ok, refusal = finish["validate"](arguments)
                    result = (
                        {"status": finish["status"], "arguments": arguments}
                        if ok
                        else refusal
                    )
                elif name == editions.SELECT and name in {t["name"] for t in tools}:
                    strategy = json.loads(arguments["strategy_json"])
                    result = {"status": "SELECTED", "strategy": strategy, "reason": "r"}
                    write_once(folder / "selected-recipe.json", canonical(result))
                elif name == editions.STOP and name in {t["name"] for t in tools}:
                    result = {"status": "STOPPED", "reason": "agent reported plateau"}
                else:
                    result = await sdk.call(name, arguments, identity)
                self.results.append((stage, name, result))
                if result.get("status") in ("PLANNED", "SELECTED", "STOPPED"):
                    outcome = result
                    break
            if outcome is not None:
                break
        outcome = outcome or {"status": "STOPPED", "reason": "script ended"}
        report = {
            "schema": "carbon.autoresearch.epoch-outcome.v1",
            "epoch": epoch,
            **outcome,
        }
        write_once(folder / "outcome.json", canonical(report))
        return report

    def stage_calls(self, stage):
        return [call for call in self.calls if call["stage"] == stage]


# --- the campaign, prepared ---------------------------------------------------


def practise(ledger, owner, strategy, task):
    """A completed practice result, as the research service retains one."""
    body = canonical({"provenance": "BATTERY_PUBLIC_PRACTICE", "recipe": strategy})
    with sqlite3.connect(ledger.root / "campaign.sqlite3") as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_results(owner TEXT NOT NULL,task TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(owner,task))"
        )
        db.execute(
            "INSERT OR IGNORE INTO research_results VALUES(?,?,?,?)",
            (owner, task, body, digest(body)),
        )


class SDK:
    """The campaign's research SDK, as a fixture: records what is dispatched;
    a practice retains a completed result."""

    def __init__(self, ledger, owner):
        self.ledger, self.owner = ledger, owner
        self.dispatched = []

    async def call(self, name, arguments, identity):
        self.dispatched.append((name, identity, arguments))
        if name == START and arguments.get("kind") == "practice":
            practise(
                self.ledger,
                self.owner,
                json.loads(arguments["strategy_json"]),
                identity,
            )
            return {"status": "OK", "terminal_task": {"state": "SUCCEEDED"}}
        return {"status": "OK", "fixture": name.removeprefix(PREFIX)}


class Campaign:
    """The Challenge's campaign, as a fixture: its first observation and a
    validator that evaluates (or refuses with `refuse`)."""

    refusal_retains_candidate = True

    def __init__(self, refuse=None):
        self.refuse = refuse
        self.evaluated = []

    def observation(self, prepared, epoch, feedback):
        return {
            "challenge": {"id": CHALLENGE.challenge_id},
            "epoch": epoch,
            "prior_permitted_evaluation_feedback": feedback,
            "instructions": "Select only a recipe you practised.",
        }

    async def evaluate(self, prepared, epoch, strategy):
        if self.refuse is not None:
            raise research_campaign.OperationRefused(self.refuse)
        self.evaluated.append((epoch, strategy))
        feedback = {
            "schema": "fixture.permitted-feedback",
            "epoch": epoch,
            "outcome": {"state": "SCORED", "screening": {"score": 0.25}},
        }
        folder = prepared.ledger.root / ("epoch-" + str(epoch))
        folder.mkdir(mode=0o700, exist_ok=True)
        write_once(folder / "permitted-final-feedback.json", canonical(feedback))
        return feedback


CEILINGS = {
    "provider_attempts": 40,
    "provider_nanodollars": 40 * RESERVATION_NANO,
    "research_trials": 8,
}


class World:
    """A Graphite campaign prepared over the fixtures above."""

    def __init__(self, tmp_path, monkeypatch, *, graphite=None, ceilings=CEILINGS):
        tmp_path.chmod(0o700)
        self.monkeypatch = monkeypatch
        self.literature = install_literature(monkeypatch)
        self.library_root = tmp_path / "graphite-library"
        self.library = Library.open(self.library_root)
        self.root = tmp_path / "campaign"
        self.graphite = graphite or {}
        self.ceilings = ceilings
        self.engine = Engine()
        monkeypatch.setattr(driver, "run_epoch", self.engine)
        self.campaign = Campaign()
        self.feed = list(FEED)
        self.opened = []

    def arxiv(self, queries):
        self.opened.append(queries)
        return self.feed

    def prepare(self):
        self.root.mkdir(mode=0o700, exist_ok=True)
        args = SimpleNamespace(
            root=self.root,
            api_key_file=None,
            graphite=self.graphite,
            graphite_library=self.library_root,
        )
        ledger = CampaignLedger(self.root, clock=lambda: 1000)
        path = self.root / "campaign-manifest.json"
        if path.exists():
            manifest = json.loads(path.read_bytes())
        else:
            block = driver.freeze_launch(args, self.root, challenge=CHALLENGE_REF)
            manifest = {
                "schema": "carbon.autoresearch.campaign.v1",
                "campaign_id": "gm-driver-fixture",
                "implementation": "fixture",
                "objective": "fixture",
                "sampling": "fixture",
                "control": "fixture",
                "selection": "fixture",
                "replica_policy": "fixture",
                "owner": "alice",
                "agent": "graphite",
                "challenge": dict(CHALLENGE_REF),
                "ceilings": self.ceilings,
                "provider": provider_plan(
                    "graphite", {"ceilings": self.ceilings}, None, graphite=block
                ),
            }
            write_once(path, canonical(manifest))
        ledger.freeze(manifest)
        return research_campaign.PreparedCampaign(
            args=args,
            ledger=ledger,
            owner="alice",
            manifest=manifest,
            seeds=None,
            role_root=None,
            data=None,
            image=None,
            key=None,
            config=None,
            composition=None,
            sdk=SDK(ledger, "alice"),
            task=None,
            grant=None,
            agent_policy=AUTONOMOUS,
            campaign=self.campaign,
            challenge=CHALLENGE,
            selection=None,
        )

    def run(self, transport, **extra):
        prepared = self.prepare()
        self.prepared = prepared
        return asyncio.run(
            driver.run(prepared, transport=transport, arxiv_opener=self.arxiv, **extra)
        )

    def spent(self):
        used = CampaignLedger(self.root).status(owner="alice")["used"]
        return {k: used[k] for k in ("provider_attempts", "provider_nanodollars")}

    def stage(self, name):
        return driver.Stages(self.root).finished(name)


def workspace(action, arguments):
    return START, {
        "kind": "workspace",
        "strategy_json": None,
        "action": action,
        "arguments_json": json.dumps(arguments),
        "hypothesis": "fixture step",
        "expected_effect": "an observation",
    }


def practice(recipe):
    return START, {
        "kind": "practice",
        "strategy_json": json.dumps(recipe),
        "action": None,
        "arguments_json": None,
        "hypothesis": "fixture practice",
        "expected_effect": "a practice result",
    }


def record_plan(*cites, pins=()):
    return editions.FINISH, {
        "hypotheses": [
            {
                "hypothesis": "an operator surrogate generalises across protocols",
                "expected_effect": "lower practice error than the scaffold",
                "stopping_rule": "stop after two practices without improvement",
                "recipe_json": json.dumps(RECIPE),
                "cites": [{"card_id": c, "origin": o} for c, o in cites],
            }
        ],
        "pins_considered": [
            {"card_id": pin, "consideration": "read and used as the baseline"}
            for pin in pins
        ],
    }


def select(recipe):
    return editions.SELECT, {
        "strategy_json": json.dumps(recipe),
        "reason": "practised; the only result",
        "used_feedback": False,
    }


PLANNER_TURN = [
    (editions.LIT_SEARCH, {"query": "physics-informed battery operator"}),
    workspace("check_design", {"design": {"strategy": RECIPE}}),
    workspace(
        "capability_request",
        {"request": {"purpose": "fixture", "operation": "a capability"}},
    ),
]
CONSTRUCTOR_TURNS = [
    [(editions.LIT_CARD, {"card_id": HUNTED}), practice(RECIPE)],
    [select(RECIPE)],
]
#: A turn whose one call is the stop tool.
STOP_TURN = [(editions.STOP, {})]


@pytest.fixture
def world(tmp_path, monkeypatch):
    def build(**graphite):
        return World(tmp_path, monkeypatch, graphite=graphite)

    return build


# --- RESEARCH -----------------------------------------------------------------


def test_research_hunts_plans_and_completes_without_selecting(world):
    """8a's stages: a fixture feed of two records, one already in the pack
    (no Reader call), one extracted to a private card; the Planner's
    parallel turn; a plan citing the miner card; no practice, selection or
    submit; the campaign completes. A resume makes no model and no arXiv
    call."""
    w = world(mode="RESEARCH", hunt={})
    w.engine.scripts = {
        ("plan", 1): [PLANNER_TURN, [record_plan((HUNTED, "miner_hunt"))]],
    }
    transport = Transport()
    assert w.run(transport) is None
    # One Reader call, for the paper the pack did not hold.
    assert len(transport.reader_calls) == 1
    hunted = w.stage("hunt")
    assert hunted["status"] == "DONE" and hunted["code"] is None
    assert hunted["report"]["deduped"] == 1 and hunted["report"]["extracted"] == 1
    assert HUNTED in w.library.private
    # The Planner's turn ran all three calls through its toolbox.
    names = [name for stage, name, _ in w.engine.results if stage == "plan"]
    assert names[:3] == [editions.LIT_SEARCH, START, START]
    planned = w.stage("plan")
    assert planned["status"] == "PLANNED"
    assert planned["plan"]["hypotheses"][0]["cites"] == [
        {"card_id": HUNTED, "origin": "miner_hunt"}
    ]
    assert w.library.plan(planned["plan_digest"]) == planned["plan"]
    # Nothing was practised, selected, evaluated or built.
    assert not any(a.get("kind") == "practice" for _, _, a in w.prepared.sdk.dispatched)
    assert w.engine.stage_calls(None) == [] and w.campaign.evaluated == []
    assert (w.root / "campaign-complete.json").exists()
    # A resume replays the recorded stages: no model call, no arXiv request.
    before, opened = w.spent(), len(w.opened)
    assert w.run(Transport(forbid=True)) is None
    assert w.spent() == before and len(w.opened) == opened
    assert len(w.literature.hunt.calls) == 1


def test_the_planner_sees_the_hunted_literature_and_its_pins(world):
    w = world(mode="RESEARCH", hunt={"queries": ["neural operator battery"]})
    w.library.pins = ["arxiv-2401.00002"]
    w.engine.scripts = {
        ("plan", 1): [
            # Leaves out the pin: refused, the stage goes on.
            [record_plan((HUNTED, "miner_hunt"))],
            [record_plan((HUNTED, "miner_hunt"), pins=["arxiv-2401.00002"])],
        ]
    }
    w.run(Transport())
    refused = next(r for _, n, r in w.engine.results if n == editions.FINISH)
    assert (refused["status"], refused["code"]) == (
        "REJECTED_BEFORE_DISPATCH",
        "plan_invalid",
    )
    assert "pinned" in refused["reason"]
    assert w.stage("plan")["status"] == "PLANNED"
    observation = w.engine.stage_calls("plan")[0]["observation"]
    assert observation["graphite"]["pins"] == ["arxiv-2401.00002"]
    assert observation["graphite"]["hunt"]["extracted"] == 1
    assert observation["graphite"]["literature"]["check_status"] == "UNCHECKED"
    assert w.literature.hunt.calls[0]["queries"] == ["neural operator battery"]
    assert w.literature.hunt.calls[0]["max_records"] == editions.DEFAULT_MAX_RECORDS


def test_a_hunt_fetch_failure_is_recorded_and_the_planner_proceeds(world):
    w = world(mode="RESEARCH", hunt={})
    w.feed = None
    w.engine.scripts = {("plan", 1): [[record_plan(("arxiv-2401.00001", "shared"))]]}
    transport = Transport()
    w.run(transport)
    assert w.stage("hunt")["code"] == driver.LITERATURE_FETCH_FAILED
    assert transport.reader_calls == []
    assert w.stage("plan")["status"] == "PLANNED"


# --- BUILD ----------------------------------------------------------------------


def saved_plan(w, *cites):
    plan = plans.from_arguments(
        record_plan(*cites)[1], challenge=CHALLENGE_REF, created_by="planner"
    )
    edited = plans.new_version(
        plan, parent=w.library.save_plan(plan), created_by="miner"
    )
    return w.library.save_plan(edited), edited


def test_build_freezes_the_plan_practises_selects_and_submits(world):
    """8c's stages: the miner's edited plan frozen at launch by digest with
    the curation; the Constructor reads it labelled as guidance, reads the
    cited miner_hunt card, practises, selects the practised recipe and the
    selection goes through the campaign's submit. A resume makes no model
    call."""
    w = world(mode="BUILD")
    w.library.add(make_card(HUNTED, "miner_hunt"))
    address, edited = saved_plan(w, (HUNTED, "miner_hunt"))
    w.graphite["plan"] = address
    w.engine.scripts = {(None, 1): CONSTRUCTOR_TURNS, (None, 2): [[select(RECIPE)]]}
    transport = Transport()
    assert w.run(transport) is None
    block = w.prepared.manifest["provider"]["graphite"]
    assert block["plan_digest"] == address
    assert block["curation_digest"] == w.library.curation()["digest"]
    launch = json.loads(driver.launch_path(w.root).read_bytes())
    assert launch["plan"] == edited and launch["curation"]["digest"] == (
        block["curation_digest"]
    )
    # No Planner: the plan was given.
    assert w.engine.stage_calls("plan") == []
    first = w.engine.stage_calls(None)[0]
    assert first["observation"]["graphite"]["plan"] == edited
    assert first["observation"]["graphite"]["plan_basis"] == driver.PLAN_BASIS
    card = next(r for _, n, r in w.engine.results if n == editions.LIT_CARD)
    assert card["card"]["origin"] == "miner_hunt" and card["content_is_data"]
    assert w.campaign.evaluated == [(1, RECIPE), (2, RECIPE)]
    assert (w.root / "campaign-complete.json").exists()
    assert w.stage("build")["ended"] == "EPOCHS_USED"
    before = w.spent()
    (w.root / "campaign-complete.json").unlink()
    assert w.run(Transport(forbid=True)) is None
    assert w.spent() == before and w.campaign.evaluated == [(1, RECIPE), (2, RECIPE)]


def test_build_without_a_plan_runs_the_planner_first(world):
    w = world(mode="BUILD")
    w.engine.scripts = {
        ("plan", 1): [[record_plan(("arxiv-2401.00002", "shared"))]],
        (None, 1): [[practice(RECIPE)], [select(RECIPE)]],
        (None, 2): [STOP_TURN],
    }
    w.run(Transport())
    planned = w.stage("plan")
    assert planned["status"] == "PLANNED"
    observation = w.engine.stage_calls(None)[0]["observation"]
    assert observation["graphite"]["plan_digest"] == planned["plan_digest"]
    assert w.stage("build")["ended"] == "NOT_SELECTED"
    assert w.campaign.evaluated == [(1, RECIPE)]


def test_a_candidate_the_validator_did_not_evaluate_is_kept(world):
    w = world(mode="BUILD")
    w.campaign.refuse = "evaluation_unavailable"
    w.engine.scripts = {
        ("plan", 1): [STOP_TURN],
        (None, 1): [[practice(RECIPE)], [select(RECIPE)]],
        (None, 2): [STOP_TURN],
    }
    assert w.run(Transport()) == "evaluation_unavailable"
    assert not (w.root / "campaign-complete.json").exists()
    notes = CampaignLedger(w.root).status(owner="alice")["notes"]
    assert notes[-1]["body"] == {
        "epoch": 1,
        "stop": "submission not evaluated: evaluation_unavailable",
        "candidate_retained": True,
    }
    # The validator answers later: the same frozen candidate is submitted
    # from the epoch's journal, with no model call for it; only epoch 2's
    # one turn is new.
    w.campaign.refuse = None
    again = Transport()
    assert w.run(again) is None
    assert w.campaign.evaluated == [(1, RECIPE)]
    assert len(again.requests) == 1
    assert (w.root / "campaign-complete.json").exists()


def test_an_unpractised_selection_is_never_submitted(world):
    w = world(mode="BUILD")
    w.engine.scripts = {
        ("plan", 1): [STOP_TURN],
        (None, 1): [[practice(RECIPE)], [select(UNPRACTISED)]],
    }
    assert w.run(Transport()) is None
    assert w.campaign.evaluated == []
    assert w.stage("build")["ended"] == "NOT_SUBMITTED"


# --- FULL -----------------------------------------------------------------------


def test_full_stops_research_at_the_share_and_builds(world):
    """8d: research stops typed at the miner's research share; the build
    continues on the rest of the budget, never refused by the share."""
    # Two of forty attempts; a hunt that finds nothing new.
    w = world(mode="FULL", research_share=0.05, hunt={})
    w.feed = []
    w.engine.scripts = {
        ("plan", 1): [PLANNER_TURN, PLANNER_TURN, PLANNER_TURN],
        (None, 1): [[practice(RECIPE)], [select(RECIPE)]],
        (None, 2): [STOP_TURN],
    }
    w.run(Transport())
    planned = w.stage("plan")
    assert planned["status"] == "STOPPED"
    assert planned["code"] == budget.RESEARCH_SHARE_REACHED
    assert planned["share"]["dimension"] == "provider_attempts"
    assert planned["share"]["share_cap"] == 2
    ops = CampaignLedger(w.root).status(owner="alice")["operations"]
    research = [o for o in ops if o["id"].startswith(budget.RESEARCH_NAMESPACE)]
    assert len([o for o in research if o["reservation"].get("provider_attempts")]) == 2
    # The build ran on the rest of the budget, with no plan.
    assert w.engine.stage_calls(None)[0]["observation"]["graphite"]["plan"] is None
    assert w.campaign.evaluated == [(1, RECIPE)]
    view = driver.view(w.root)
    assert view["research_share"] == 0.05 and view["stage"] == "complete"
    assert view["research_spent"]["provider_attempts"] == 2
    assert view["stages"][0] == {
        "stage": "hunt",
        "state": "DONE",
        "code": None,
    }
    assert view["stages"][1]["code"] == budget.RESEARCH_SHARE_REACHED


def test_full_share_reached_in_the_hunt_skips_the_planner(world):
    w = world(mode="FULL", research_share=0.0, hunt={})
    w.engine.scripts = {(None, 1): [STOP_TURN]}
    transport = Transport()
    w.run(transport)
    assert transport.reader_calls == []
    assert w.stage("hunt")["code"] == budget.RESEARCH_SHARE_REACHED
    assert w.stage("plan")["code"] == budget.RESEARCH_SHARE_REACHED
    assert w.engine.stage_calls("plan") == []
    assert len(w.engine.stage_calls(None)) == 1


def test_full_runs_hunt_plan_then_build(world):
    w = world(hunt={})
    w.engine.scripts = {
        ("plan", 1): [[record_plan((HUNTED, "miner_hunt"))]],
        (None, 1): CONSTRUCTOR_TURNS,
        (None, 2): [STOP_TURN],
    }
    w.run(Transport())
    assert w.prepared.manifest["provider"]["graphite"]["mode"] == "FULL"
    assert w.stage("plan")["status"] == "PLANNED"
    assert w.campaign.evaluated == [(1, RECIPE)]
    # The plan's cited cards were recorded as having led to a practised
    # selection (epoch 1) and to none (epoch 2): the miner's own practice.
    assert [(cards, improved) for cards, improved, _ in w.library.outcomes] == [
        ([HUNTED], True),
        ([HUNTED], False),
    ]


# --- refusals before any model call ---------------------------------------------


def test_an_unknown_edition_is_refused_before_any_model_call(world, monkeypatch):
    w = world(mode="RESEARCH")
    w.prepare()
    manifest = json.loads((w.root / "campaign-manifest.json").read_bytes())
    monkeypatch.setitem(editions.MINER_EDITIONS, editions.EDITION_ID, None)
    prepared = w.prepare()
    prepared.manifest = manifest
    with pytest.raises(research_campaign.OperationRefused) as refused:
        asyncio.run(driver.run(prepared, transport=Transport(forbid=True)))
    assert refused.value.code == "graphite_edition_unknown"


def test_a_missing_or_changed_pack_is_refused_before_any_model_call(world):
    w = world(mode="RESEARCH")
    w.prepare()
    sys.modules[PACKAGE + ".pack"].freeze_into = lambda root: "sha256:" + "6" * 64
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.run(Transport(forbid=True))
    assert refused.value.code == "literature_pack_missing"

    def missing(root):
        raise FileNotFoundError("pack")

    sys.modules[PACKAGE + ".pack"].freeze_into = missing
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.run(Transport(forbid=True))
    assert refused.value.code == "literature_pack_missing"


def test_a_changed_launch_record_is_refused(world):
    w = world(mode="RESEARCH")
    w.prepare()
    path = driver.launch_path(w.root)
    record = json.loads(path.read_bytes())
    path.unlink()
    path.write_bytes(canonical({**record, "plan_digest": "sha256:" + "0" * 64}))
    with pytest.raises(ValueError, match="launch record differs"):
        w.run(Transport(forbid=True))


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"mode": "EXPLORE"}, "graphite_mode_invalid"),
        ({"research_share": 1.5}, "research_share_invalid"),
        ({"hunt": {"queries": ["ti:battery AND au:x"]}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["a b c d e f g"]}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["battery"] * 9}}, "hunt_query_invalid"),
        ({"mode": "BUILD", "hunt": {}}, "hunt_query_invalid"),
        ({"limits": {"calls_per_epoch": 0}}, "graphite_limits_invalid"),
        ({"limits": {"turns": 5}}, "graphite_limits_invalid"),
        ({"plan": "sha256:" + "1" * 64}, "plan_invalid"),
        ({"mode": "BUILD", "plan": "not-a-digest"}, "plan_invalid"),
        ({"mode": "BUILD", "plan": "sha256:" + "1" * 64}, "plan_not_found"),
        ({"surprise": True}, "graphite_launch_invalid"),
    ],
)
def test_a_launch_is_refused_by_its_closed_code(world, fields, code):
    w = world(**fields)
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.prepare()
    assert refused.value.code == code
    assert not (w.root / "campaign-manifest.json").exists()


def test_a_launch_plan_must_be_this_challenges_and_cite_no_banned_card(world):
    w = world(mode="BUILD")
    address, _ = saved_plan(w, ("arxiv-2401.00001", "shared"))
    w.graphite["plan"] = address
    w.library.bans = ["arxiv-2401.00001"]
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.prepare()
    assert refused.value.code == "card_banned"
    w.library.bans = []
    other = plans.document(
        challenge={"id": "another-challenge", "version": "1"},
        hypotheses=[
            {
                "rank": 1,
                "hypothesis": "h",
                "expected_effect": "e",
                "stopping_rule": "s",
                "cites": [],
            }
        ],
        pins_considered=[],
        parent=None,
        created_by="miner",
    )
    w.graphite["plan"] = w.library.save_plan(other)
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.prepare()
    assert refused.value.code == "plan_invalid"


def test_an_interrupted_first_preparation_is_replaced_until_the_manifest_freezes(
    world,
):
    w = world(mode="RESEARCH")
    w.root.mkdir(mode=0o700)
    args = SimpleNamespace(
        graphite={"mode": "RESEARCH"}, graphite_library=w.library_root
    )
    driver.freeze_launch(args, w.root, challenge=CHALLENGE_REF)
    w.library.pins = ["arxiv-2401.00001"]
    block = driver.freeze_launch(args, w.root, challenge=CHALLENGE_REF)
    record = json.loads(driver.launch_path(w.root).read_bytes())
    assert record["curation"]["pins"] == ["arxiv-2401.00001"]
    assert record["block_digest"] == digest(canonical(block))
    (w.root / "campaign-manifest.json").write_bytes(b"{}")
    w.library.pins = []
    with pytest.raises(ValueError, match="frozen Graphite launch record differs"):
        driver.freeze_launch(args, w.root, challenge=CHALLENGE_REF)


# --- the engine keywords ----------------------------------------------------------


def test_every_stage_runs_under_the_frozen_engine_rules(world):
    w = world(hunt={}, limits={"calls_per_epoch": 90, "planner_calls": 12})
    w.engine.scripts = {
        ("plan", 1): [[record_plan(("arxiv-2401.00001", "shared"))]],
        (None, 1): [STOP_TURN],
    }
    w.run(Transport())
    plan = w.prepared.manifest["provider"]
    planner, constructor = (
        w.engine.stage_calls("plan")[0],
        w.engine.stage_calls(None)[0],
    )
    for call in (planner, constructor):
        assert call["agent_policy"] == editions.AGENT_POLICY
        assert call["challenge"] is CHALLENGE
        assert call["parallel_calls"] == PARALLEL_CALLS_V2
        assert call["miner_guidance"] == plan["miner_guidance"]
        assert call["compaction"] == editions.COMPACTION_V1
        assert call["max_provider_calls"] is None
    assert planner["instructions"] == editions.PLANNER_PROMPT
    assert planner["finish"]["tool"] == editions.FINISH_TOOL
    assert planner["finish"]["status"] == "PLANNED"
    assert planner["limits"] == {
        "schema": editions.LIMITS_SCHEMA,
        "calls_per_epoch": 12,
        "trials_per_epoch": None,
    }
    assert isinstance(planner["ledger"], budget.StageLedger)
    assert constructor["instructions"] == editions.CONSTRUCTOR_PROMPT
    assert constructor["stage"] is None and constructor["finish"] is None
    assert constructor["limits"]["calls_per_epoch"] == 90
    assert constructor["ledger"] is w.prepared.ledger
    planner_tools = [t["name"] for t in planner["tools"]]
    assert planner_tools == list(editions.PLANNER.tools)
    task = next(t for t in planner["tools"] if t["name"] == START)
    assert task["parameters"]["properties"]["kind"]["enum"] == ["workspace"]
    assert set(task["parameters"]["properties"]["action"]["enum"]) == {
        *editions.PLANNER_ACTIONS,
        None,
    }
    constructor_tools = [t["name"] for t in constructor["tools"]]
    assert editions.SELECT in constructor_tools and editions.FINISH not in (
        constructor_tools
    )


# --- the Reader -------------------------------------------------------------------


def test_the_reader_meters_one_closed_call_per_paper_and_replays(tmp_path, world):
    w = world(mode="RESEARCH")
    prepared = w.prepare()
    transport = Transport()
    reader = driver.MinerReader(
        ledger=prepared.ledger,
        owner="alice",
        selection=DEFAULT_SELECTION,
        credential_file=None,
        transport=transport,
        role=editions.READER,
    )
    paper = {"paper": {"arxiv_id": "2403.00001", "title": "t"}}
    first = reader(reader.request("extract", paper))
    again = reader(reader.request("extract", paper))
    assert first == again and len(transport.requests) == 1
    sent = transport.requests[0]
    assert sent["instructions"] == editions.READER_EXTRACTION_PROMPT
    assert sent["tools"] == [] and sent["store"] is False
    identity = reader.identity(reader.request("extract", paper))
    assert identity.startswith(budget.READER_PREFIX) and len(identity) <= 128
    assert prepared.ledger.operation_state(identity, owner="alice") == "SUCCEEDED"
    # A partial request is completed from the selection; a foreign prompt,
    # an offered tool or another model is refused before anything is sent.
    partial = reader.complete(
        {"task": "triage", "input": [{"role": "user", "content": "x"}]}
    )
    assert partial["instructions"] == editions.READER_TRIAGE_PROMPT
    for bad in (
        {"instructions": "You are another agent.", "input": [{"role": "user"}]},
        {"input": [{"role": "user"}], "tools": [{"type": "function"}]},
        {"input": [{"role": "user"}], "model": "another-model"},
        {"input": []},
    ):
        with pytest.raises(driver.ReaderRefused):
            reader(bad)
    assert len(transport.requests) == 1


# --- the shared helper and the dispatch ---------------------------------------------


def test_submit_or_retain_keeps_a_candidate_with_the_historical_note(world):
    w = world(mode="BUILD")
    prepared = w.prepare()
    practise(prepared.ledger, "alice", RECIPE, "task-1")
    w.campaign.refuse = "evaluation_queued"
    feedback, code = asyncio.run(
        research_campaign.submit_or_retain(prepared, 1, RECIPE)
    )
    assert (feedback, code) == (None, "evaluation_queued")
    note = prepared.ledger.status(owner="alice")["notes"][-1]
    assert note == {
        "sequence": note["sequence"],
        "kind": "decision",
        "body": {
            "epoch": 1,
            "stop": "submission not evaluated: evaluation_queued",
            "candidate_retained": True,
        },
    }
    w.campaign.refusal_retains_candidate = False
    with pytest.raises(research_campaign.OperationRefused):
        asyncio.run(research_campaign.submit_or_retain(prepared, 1, RECIPE))
    w.campaign.refuse = None
    feedback, code = asyncio.run(
        research_campaign.submit_or_retain(prepared, 1, RECIPE)
    )
    assert code is None and feedback["epoch"] == 1


def test_execute_dispatches_graphite_and_leaves_the_other_agents_alone(monkeypatch):
    ran = []

    def prepared(agent):
        return SimpleNamespace(
            manifest={"agent": agent},
            agent=agent,
            close=lambda: ran.append(("close", agent)),
        )

    async def run_graphite(value, **_):
        ran.append(("graphite", value.agent))
        return "evaluation_queued"

    async def run_agent(value, **_):
        ran.append(("autonomous", value.agent))

    monkeypatch.setattr(research_campaign, "run_graphite", run_graphite)
    monkeypatch.setattr(research_campaign, "run_agent", run_agent)
    for agent in ("graphite", "autonomous", "none"):

        async def prepare(args, *, ledger=None, agent=agent):
            return prepared(agent)

        monkeypatch.setattr(research_campaign, "prepare", prepare)
        outcome = asyncio.run(research_campaign.execute(SimpleNamespace()))
        assert outcome == ("evaluation_queued" if agent == "graphite" else None)
    assert ran == [
        ("graphite", "graphite"),
        ("close", "graphite"),
        ("autonomous", "autonomous"),
        ("close", "autonomous"),
        ("close", "none"),
    ]


def test_run_graphite_reaches_the_driver(monkeypatch):
    seen = []

    async def run(prepared, **keywords):
        seen.append((prepared, keywords))

    monkeypatch.setattr(driver, "run", run)
    asyncio.run(research_campaign.run_graphite("p", transport="t"))
    assert seen == [("p", {"transport": "t", "arxiv_opener": None, "clock": None})]


# --- the view ---------------------------------------------------------------------


def test_the_view_names_the_stage_and_the_research_spend(world):
    w = world(mode="RESEARCH", hunt={})
    w.engine.scripts = {("plan", 1): [[record_plan((HUNTED, "miner_hunt"))]]}
    w.prepare()
    view = driver.view(w.root)
    assert view["stage"] == "hunt" and view["mode"] == "RESEARCH"
    assert [row["state"] for row in view["stages"]] == ["PENDING", "PENDING"]
    assert view["research_share"] is None and view["research_cap"] is None
    w.run(Transport())
    view = driver.view(w.root)
    assert view["stage"] == "complete"
    assert view["plan_digest"] == w.stage("plan")["plan_digest"]
    assert view["hunt"]["extracted"] == 1 and view["hunt"]["deduped"] == 1
    reader_cost = view["hunt"]["cost_nanodollars"]
    assert 0 < reader_cost < view["research_spent"]["provider_nanodollars"]
    assert view["research_spent"]["provider_attempts"] == 2
    # Another campaign has no Graphite view.
    other = w.root.parent / "other"
    other.mkdir()
    (other / "campaign-manifest.json").write_bytes(
        canonical({"provider": {"agent": "autonomous"}, "owner": "alice"})
    )
    assert driver.view(other) is None


def test_a_product_campaign_shows_the_miner_budget_beside_the_plan(world):
    w = world(mode="BUILD")
    w.engine.scripts = {
        ("plan", 1): [STOP_TURN],
        (None, 1): [STOP_TURN],
    }
    prepared = w.prepare()
    prepared.manifest = {**prepared.manifest, "schema": PRODUCT}
    asyncio.run(driver.run(prepared, transport=Transport()))
    observation = w.engine.stage_calls(None)[0]["observation"]
    assert observation["miner_budget"] == {"ceilings": CEILINGS}
    assert observation["graphite"]["plan"] is None
    assert observation["graphite"]["plan_basis"] == driver.NO_PLAN_BASIS
