"""Graphite's miner edition driver (OWNER-GRAPHITE-MINER-01, slice S3).

DEVELOPMENT FIXTURES ONLY. Most tests stand in for the literature slice's
modules (`pack`, `library`, `hunt`, as committed on claude/gm-literature at
5a975f8f) and the engine slice's `run_epoch` keywords (`stage`, `finish`,
`limits`, `compaction`) with fixtures that keep those contracts: the hunt
builds its own Reader requests with the edition's Reader prompt, claims a
paper before its Reader call and releases the claim on `ReaderNotSent`. The
campaign ledger, the research share, the Reader's metered model calls
(`research_agent.request_model`), the toolbox and the campaign's submit
(`research_campaign.submit_or_retain`) are real.

The integration tests at the end run the real literature modules (and the
real research loop) where those slices are present in the tree, and skip,
naming why, where they are not. Scripted replies test control flow, never
agent evidence.
"""

from __future__ import annotations

import asyncio
import importlib
import io
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
from carbon.development_session import research_campaign, research_loop
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
MINER = Path(driver.__file__).resolve().parent
#: The literature slice's modules are in this tree (else its tests skip).
LITERATURE_SLICE = all(
    (MINER / (name + ".py")).exists()
    for name in ("pack", "library", "hunt", "focus", "imports")
)
#: The engine slice's research loop is in this tree.
ENGINE_SLICE = hasattr(research_loop, "CeilingReached")
needs_literature = pytest.mark.skipif(
    not LITERATURE_SLICE,
    reason="the literature slice (S2) is not in this tree; runs at integration",
)
needs_engine = pytest.mark.skipif(
    not (LITERATURE_SLICE and ENGINE_SLICE),
    reason="the engine (S1) and literature (S2) slices are not both in this "
    "tree; runs at integration",
)
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


class LibraryRefused(ValueError):
    """DEVELOPMENT FIXTURE: `library.LibraryError`'s shape (a ValueError
    with a closed code)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Library:
    """DEVELOPMENT FIXTURE: `library.MinerLibrary(root, pack=None)`'s
    interface shape. One instance per root, so a resume meets the same
    library. Like the library, it refuses an outcome naming more than 64
    cards or a card it does not hold, and finds a curation state by digest
    only once that state was recorded."""

    opened: ClassVar[dict] = {}
    MAX_OUTCOME_CARDS = 64

    def __init__(self, root):
        self.root = Path(root)
        self.private = {}
        self.pins, self.bans = [], []
        self.saved = {}
        self.outcomes = []
        self.outcome_challenges = []
        self.claims = {}
        self.hunts = {}
        self.states = {}
        self.packs = []

    @classmethod
    def open(cls, root, pack=None):
        library = cls.opened.setdefault(Path(root), cls(root))
        library.packs.append(pack)
        return library

    def curation(self):
        body = {"pins": sorted(self.pins), "bans": sorted(self.bans)}
        state = {**body, "digest": digest(canonical(body))}
        self.states[state["digest"]] = state
        return state

    def curation_state(self, value):
        if value not in self.states:
            raise LibraryRefused("curation_not_found")
        return dict(self.states[value])

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

    def record_outcome(self, card_ids, improved, evidence, *, challenge):
        if not 1 <= len(card_ids) <= self.MAX_OUTCOME_CARDS:
            raise LibraryRefused("evidence_invalid")
        for card_id in card_ids:
            if self.card(card_id) is None:
                raise LibraryRefused("card_not_found")
        if type(challenge) is not dict or not challenge.get("version"):
            raise LibraryRefused("evidence_invalid")
        self.outcomes.append((list(card_ids), improved, evidence))
        self.outcome_challenges.append(dict(challenge))


class Literature:
    """DEVELOPMENT FIXTURE: `library.MinerLiterature`'s interface shape."""

    built: ClassVar[list] = []

    def __init__(
        self,
        pack,
        library,
        *,
        challenge,
        private_snapshot_digest,
        curation,
        focus_terms=None,
    ):
        assert challenge == CHALLENGE_REF
        self.library = library
        self.bans = set(curation["bans"])
        self.cards = [*pack.cards, *library.private.values()]
        self.snapshot = private_snapshot_digest
        self.focus_terms = focus_terms
        Literature.built.append(self)

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


class ReaderNotSent(Exception):
    """DEVELOPMENT FIXTURE: `hunt.ReaderNotSent`."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class HuntRefused(ValueError):
    """DEVELOPMENT FIXTURE: `hunt.HuntRefused`."""

    def __init__(self, code, detail=""):
        super().__init__(code)
        self.code, self.detail = code, detail


def validate_hunt(hunt):
    """DEVELOPMENT FIXTURE: `hunt.validate_hunt`, with the hunt's own bound."""
    queries = hunt.get("queries") or []
    if not all(editions.check_query(q) for q in queries) or not (
        1 <= hunt.get("max_records", 200) <= 5000
    ):
        raise HuntRefused("hunt_query_invalid")
    return hunt


class Hunt:
    """DEVELOPMENT FIXTURE: the committed `hunt.run_hunt` contract. It
    replays a finished hunt id's report; dedups on the pack, the library and
    its claims before any Reader call (a paper met twice in one hunt is
    decided once); builds each Reader request itself - the edition's Reader
    prompt, the paper as JSON data, no tools, no model fields, which the
    driver's Reader completes from the selection; claims the paper before
    the call and releases the claim on `ReaderNotSent`, stopping typed; and
    stores each extraction as a miner_hunt card. `arxiv_opener(queries)`
    returns the fixture feed, or None for an arXiv FAILED_INFRA."""

    def __init__(self):
        self.calls = []
        self.refuse = None

    def run_hunt(
        self,
        library,
        *,
        challenge,
        discovery,
        queries=None,
        max_records=200,
        reader,
        arxiv_opener=None,
        clock=None,
        checkpoint=None,
        selection=None,
        hunt_id=None,
    ):
        assert type(hunt_id) is str and hunt_id.startswith("campaign-")
        if hunt_id in library.hunts:
            return library.hunts[hunt_id]
        self.calls.append(
            {
                "challenge": challenge,
                "queries": queries,
                "max_records": max_records,
                "hunt_id": hunt_id,
            }
        )
        if self.refuse is not None:
            raise HuntRefused(self.refuse)
        assert discovery["contract_digest"]
        feed = arxiv_opener(queries)
        report = {
            "hunt_id": hunt_id,
            "status": "COMPLETED",
            "stop_code": None,
            "failed_infra": False,
            "fetched": 0,
            "deduped": 0,
            "triaged_out": 0,
            "extracted": 0,
            "cards": [],
            "reader_calls": 0,
        }
        if feed is None:
            report.update(status="FAILED_INFRA", failed_infra=True)
            library.hunts[hunt_id] = report
            return report
        decided = set()
        for record in feed[:max_records]:
            key = record["arxiv_id"]
            if key in decided:
                continue
            decided.add(key)
            report["fetched"] += 1
            card_id = "arxiv-" + key
            if library.card(card_id) is not None or key in library.claims:
                report["deduped"] += 1
                continue
            checkpoint()
            request = {
                "instructions": editions.READER_EXTRACTION_PROMPT,
                "input": [{"role": "user", "content": canonical(record).decode()}],
                "tools": [],
                "parallel_tool_calls": False,
                "store": False,
            }
            library.claims[key] = hunt_id
            try:
                reply = reader(request)
            except ReaderNotSent as stop:
                del library.claims[key]
                report.update(status="STOPPED", stop_code=stop.code)
                break
            report["reader_calls"] += 1
            json.loads(reply["output"][0]["content"][0]["text"])
            library.add(make_card(card_id, "miner_hunt", record["title"]))
            report["extracted"] += 1
            report["cards"].append(card_id)
        library.hunts[hunt_id] = report
        return report


class FrozenPack:
    """DEVELOPMENT FIXTURE: `pack`'s freeze and load. `shipped` is the pack
    this tree ships; a campaign's copy is a file named by its digest."""

    def __init__(self):
        self.shipped = PACK_DIGEST
        self.copies = []
        self.damaged = False

    def frozen_path(self, root, value=None):
        value = self.shipped if value is None else value
        return Path(root) / "graphite-literature" / (value[7:] + ".json.gz")

    def freeze_into(self, root):
        if self.damaged:
            raise ValueError("literature_pack_missing: damaged")
        path = self.frozen_path(root)
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            path.write_bytes(self.shipped.encode())
        self.copies.append(Path(root))
        return self.shipped

    def load_frozen(self, root, value=None):
        path = self.frozen_path(root, value)
        if not path.exists() or path.read_bytes() != (value or self.shipped).encode():
            raise ValueError("literature_pack_missing: no frozen copy")
        return SimpleNamespace(digest=value or self.shipped, cards=SHARED)


def install_literature(monkeypatch):
    """The literature slice's modules, as fixtures with its interface."""
    Library.opened = {}
    Literature.built = []
    hunt = Hunt()
    frozen = FrozenPack()
    pack = types.ModuleType(PACKAGE + ".pack")
    pack.__dict__.update(
        SHARED_PACK_DIGEST=PACK_DIGEST,
        load_shared_pack=lambda: SimpleNamespace(digest=pack.SHARED_PACK_DIGEST),
        freeze_into=frozen.freeze_into,
        load_frozen=frozen.load_frozen,
        frozen_path=frozen.frozen_path,
    )
    modules = {
        "pack": pack,
        "library": SimpleNamespace(
            MinerLibrary=Library.open, MinerLiterature=Literature
        ),
        "hunt": SimpleNamespace(
            run_hunt=hunt.run_hunt,
            validate_hunt=validate_hunt,
            ReaderNotSent=ReaderNotSent,
            HuntRefused=HuntRefused,
        ),
    }
    for name, value in modules.items():
        module = value
        if not isinstance(value, types.ModuleType):
            module = types.ModuleType(PACKAGE + "." + name)
            module.__dict__.update(vars(value))
        monkeypatch.setitem(sys.modules, PACKAGE + "." + name, module)
        monkeypatch.setattr(miner_package, name, module, raising=False)
    return SimpleNamespace(hunt=hunt, pack=frozen, pack_copies=frozen.copies)


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
    A model call the ledger refuses typed (the engine's `CeilingReached`;
    here the stage ledger's stops) ends the session STOPPED with its
    outcome, as the engine does. A finished stage's outcome replays from
    `outcome.json`."""

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
            try:
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
            except budget.STOPS as reached:
                outcome = reached.outcome()
                break
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
    """A Graphite campaign prepared over the fixtures above, or - `real` -
    over the literature slice's own modules and, where it is present, the
    engine slice's research loop."""

    def __init__(
        self, tmp_path, monkeypatch, *, graphite=None, ceilings=CEILINGS, real=False
    ):
        tmp_path.chmod(0o700)
        self.monkeypatch = monkeypatch
        self.root = tmp_path / "campaign"
        self.library_root = tmp_path / "graphite-library"
        self.graphite = graphite or {}
        #: What the Launchpad captured at admission (`LaunchChoice.apply`).
        self.curation_digest = None
        self.ceilings = ceilings
        self.campaign = Campaign()
        self.feed = list(FEED)
        self.opened = []
        self.real = real
        if real:
            self.literature = None
            self.library = driver.open_library(self.library_root)
            self.engine = None
            if not ENGINE_SLICE:
                self.engine = Engine()
                monkeypatch.setattr(driver, "run_epoch", self.engine)
            return
        self.literature = install_literature(monkeypatch)
        self.library = Library.open(self.library_root)
        self.engine = Engine()
        monkeypatch.setattr(driver, "run_epoch", self.engine)

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
        if self.curation_digest is not None:
            args.graphite_curation_digest = self.curation_digest
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

    def run(self, transport, *, arxiv_opener=None, **extra):
        prepared = self.prepare()
        self.prepared = prepared
        opener = self.arxiv if arxiv_opener is None else arxiv_opener
        return asyncio.run(
            driver.run(prepared, transport=transport, arxiv_opener=opener, **extra)
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
    # One Reader call, for the paper the pack did not hold, carrying the
    # edition's frozen Reader prompt and completed from the selection.
    assert len(transport.reader_calls) == 1
    sent = transport.reader_calls[0]
    assert sent["instructions"] == editions.READER_EXTRACTION_PROMPT
    assert sent["model"] == DEFAULT_SELECTION.model_id and sent["tools"] == []
    hunted = w.stage("hunt")
    assert hunted["status"] == "DONE" and hunted["code"] is None
    assert hunted["report"]["deduped"] == 1 and hunted["report"]["extracted"] == 1
    assert HUNTED in w.library.private
    # The hunt's report counts are kept in its stage record, where a
    # campaign view reads them.
    assert hunted["report"]["hunt_id"] == w.literature.hunt.calls[0]["hunt_id"]
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
    # The miner's own hunt queries steer the served ranking as focus terms.
    assert Literature.built[-1].focus_terms == ["neural operator battery"]


def test_a_hunt_fetch_failure_is_recorded_and_the_planner_proceeds(world):
    w = world(mode="RESEARCH", hunt={})
    w.feed = None
    w.engine.scripts = {("plan", 1): [[record_plan(("arxiv-2401.00001", "shared"))]]}
    transport = Transport()
    w.run(transport)
    assert w.stage("hunt")["code"] == driver.LITERATURE_FETCH_FAILED
    assert transport.reader_calls == []
    assert w.stage("plan")["status"] == "PLANNED"


def test_a_hunt_the_hunt_refuses_is_recorded_and_the_planner_proceeds(world):
    w = world(mode="RESEARCH", hunt={})
    w.literature.hunt.refuse = "hunt_query_invalid"
    w.engine.scripts = {("plan", 1): [[record_plan(("arxiv-2401.00001", "shared"))]]}
    transport = Transport()
    w.run(transport)
    hunted = w.stage("hunt")
    assert (hunted["status"], hunted["code"]) == ("STOPPED", "hunt_query_invalid")
    assert transport.reader_calls == [] and w.opened == []
    assert w.stage("plan")["status"] == "PLANNED"


def test_an_interrupted_hunt_resumes_under_the_same_hunt_id(world):
    """A pause during the hunt propagates; the resumed hunt runs under the
    campaign's one hunt id, so it continues that hunt (its queries as they
    started), never starts another."""
    w = world(mode="RESEARCH", hunt={})
    w.engine.scripts = {("plan", 1): [STOP_TURN]}
    pauses = []

    class Paused(Exception):
        pass

    original = CampaignLedger.checkpoint

    def checkpoint(ledger):
        # The run's, the hunt stage's, then the hunt's before its first
        # Reader call: the pause lands inside the hunt.
        pauses.append(len(pauses))
        if len(pauses) == 3:
            raise Paused("paused")
        return original(ledger)

    w.monkeypatch.setattr(CampaignLedger, "checkpoint", checkpoint)
    with pytest.raises(Paused):
        w.run(Transport())
    assert w.stage("hunt") is None
    w.monkeypatch.setattr(CampaignLedger, "checkpoint", original)
    w.run(Transport())
    first, second = w.literature.hunt.calls
    assert first["hunt_id"] == second["hunt_id"]
    assert w.stage("hunt")["report"]["hunt_id"] == first["hunt_id"]


# --- BUILD ----------------------------------------------------------------------


def saved_plan(w, *cites):
    plan = plans.from_arguments(
        record_plan(*cites)[1], challenge=CHALLENGE_REF, created_by="planner"
    )
    edited = plans.new_version(
        plan, parent=w.library.save_plan(plan), created_by="miner"
    )
    return w.library.save_plan(edited), edited


def test_a_miner_edit_is_a_new_version_ranked_by_its_order():
    plan = plans.from_arguments(
        record_plan(("arxiv-2401.00001", "shared"))[1], challenge=CHALLENGE_REF
    )
    added = {
        "hypothesis": "A pinned method is worth one practice",
        "expected_effect": "a comparison point",
        "stopping_rule": "one practice",
        "cites": [{"card_id": "arxiv-2401.00002", "origin": "shared"}],
    }
    parent = plans.plan_digest(plan)
    edited = plans.new_version(
        plan,
        parent=parent,
        hypotheses=[added, {**plan["hypotheses"][0], "rank": 7}],
    )
    assert [h["rank"] for h in edited["hypotheses"]] == [1, 2]
    assert edited["hypotheses"][0]["hypothesis"] == added["hypothesis"]
    assert (edited["parent"], edited["created_by"]) == (parent, "miner")
    assert plan["hypotheses"][0]["rank"] == 1  # the edited plan is unchanged
    with pytest.raises(plans.PlanInvalid):
        plans.new_version(plan, parent=parent, hypotheses=[{**added, "x": 1}])


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
    assert w.prepared.manifest["provider"]["graphite"]["research_share"] is None


def test_build_without_a_plan_may_hunt_before_its_planner(world):
    """The Launchpad admits a hunt for a BUILD that names no plan (its
    Planner runs first): the hunt runs, then the Planner, then the build,
    all on the campaign's own ceilings."""
    w = world(mode="BUILD", hunt={"queries": ["battery operator"]})
    w.engine.scripts = {
        ("plan", 1): [[record_plan((HUNTED, "miner_hunt"))]],
        (None, 1): [STOP_TURN],
    }
    transport = Transport()
    w.run(transport)
    assert driver.stage_sequence(w.prepared.manifest["provider"]["graphite"]) == [
        "hunt",
        "plan",
        "build",
    ]
    assert w.stage("hunt")["status"] == "DONE" and len(transport.reader_calls) == 1
    assert w.stage("plan")["status"] == "PLANNED"
    assert w.engine.stage_calls("plan")[0]["ledger"].caps == {}
    assert w.stage("build")["ended"] == "NOT_SELECTED"


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


def test_full_hunt_keeps_to_its_part_and_the_planner_gets_the_rest(world):
    """The hunt may spend half the research share; the paper its share
    refused is released (never claimed unpaid), the hunt stops typed, and
    the Planner still plans on the rest of the share."""
    # 40 attempts at 0.10: a share of 4, of which the hunt may spend 2.
    w = world(mode="FULL", research_share=0.1, hunt={})
    w.feed = [
        {"arxiv_id": "2402.00009", "title": "Physics-informed battery operator"},
        {"arxiv_id": "2402.00010", "title": "Operator learning for cell ageing"},
        {"arxiv_id": "2402.00011", "title": "Fast-charge neural surrogate"},
    ]
    w.engine.scripts = {
        ("plan", 1): [PLANNER_TURN, [record_plan((HUNTED, "miner_hunt"))]],
        (None, 1): [STOP_TURN],
    }
    transport = Transport()
    w.run(transport)
    assert len(transport.reader_calls) == 2
    hunted = w.stage("hunt")
    assert (hunted["status"], hunted["code"]) == ("STOPPED", "research_share_reached")
    assert hunted["share"]["share_cap"] == 2
    assert hunted["report"]["stop_code"] == "research_share_reached"
    # The refused paper's claim was released: a later hunt may read it.
    assert set(w.library.claims) == {"2402.00009", "2402.00010"}
    planned = w.stage("plan")
    assert planned["status"] == "PLANNED"
    spent = budget.namespace_spend(w.prepared.ledger, "alice")
    assert spent["provider_attempts"] == 4
    assert len(w.engine.stage_calls(None)) == 1
    # The hunt's stop is noted in the campaign ledger, where the miner sees it.
    assert graphite_notes(w) == [
        {
            "graphite_stage": "hunt",
            "status": "STOPPED",
            "stop": "research_share_reached",
        }
    ]


def graphite_notes(w):
    return [
        n["body"]
        for n in w.prepared.ledger.status(owner="alice")["notes"]
        if "graphite_stage" in n["body"]
    ]


def test_a_full_launch_whose_share_pays_for_no_research_call_is_refused(world):
    """A share that cannot pay for one research model call would research
    nothing: refused `research_share_too_small` before the manifest
    freezes, never run as a research stage that can send nothing."""
    w = world(mode="FULL", research_share=0.0, hunt={})
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.prepare()
    assert refused.value.code == driver.RESEARCH_SHARE_TOO_SMALL
    assert not (w.root / "campaign-manifest.json").exists()
    assert w.engine.calls == []

    def short(share, hunt=None, ceilings=CEILINGS, selection=DEFAULT_SELECTION):
        launch = {"mode": "FULL", "research_share": share, "hunt": hunt}
        return driver.research_share_shortfall(launch, ceilings, selection)

    # 4% of the ceilings pays for one Planner call; the hunt's half for none
    # (0.8 of a call's cost and of an attempt).
    assert short(0.04) is None
    assert short(0.04, hunt={"queries": [], "max_records": 200}) == {
        "stage": "hunt",
        "dimension": "provider_nanodollars",
        "share_cap": 40 * RESERVATION_NANO // 50,
        "per_call": RESERVATION_NANO,
    }
    attempts_only = {"provider_attempts": 40, "provider_nanodollars": 10**15}
    assert short(0.04, hunt={}, ceilings=attempts_only) == {
        "stage": "hunt",
        "dimension": "provider_attempts",
        "share_cap": 0,
        "per_call": 1,
    }
    # Money binds where one call's whole cost does not fit the share.
    poor = {**CEILINGS, "provider_nanodollars": 5 * RESERVATION_NANO}
    assert short(0.1, ceilings=poor) == {
        "stage": "plan",
        "dimension": "provider_nanodollars",
        "share_cap": RESERVATION_NANO // 2,
        "per_call": RESERVATION_NANO,
    }
    # An unpriced selection reserves no money, so only attempts bind.
    unpriced = SimpleNamespace(reservation_nano=None)
    assert budget.call_reservation(unpriced) == {"provider_attempts": 1}
    assert short(0.1, ceilings=poor, selection=unpriced) is None
    # Only FULL has a research share.
    for mode in ("RESEARCH", "BUILD"):
        launch = {"mode": mode, "research_share": None, "hunt": None}
        assert driver.research_share_shortfall(launch, poor, DEFAULT_SELECTION) is None


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


# --- the miner's own limits: money and time ---------------------------------------


#: A Constructor turn that reads one card and selects nothing.
READ_TURN = [(editions.LIT_CARD, {"card_id": "arxiv-2401.00001"})]


def test_the_build_ends_typed_at_the_miners_own_ceiling(tmp_path, monkeypatch):
    """8e's end: the miner's own ceiling refuses the next model call, so the
    session ends STOPPED `miner_ceiling_reached` with the dimension that
    bound (its outcome recorded), nothing of that call reserved or sent; the
    build records it, the ledger notes it, and the campaign completes - the
    normal end of a miner-edition run, never an interruption."""
    ceilings = {**CEILINGS, "provider_attempts": 3}
    w = World(tmp_path, monkeypatch, graphite={"mode": "BUILD"}, ceilings=ceilings)
    w.engine.scripts = {("plan", 1): [STOP_TURN], (None, 1): [READ_TURN] * 5}
    transport = Transport()
    assert w.run(transport) is None
    # The Planner's call and two of the Constructor's; the third was refused.
    assert len(transport.requests) == 3
    assert w.spent()["provider_attempts"] == 3
    outcome = json.loads((w.root / "epoch-1" / "outcome.json").read_bytes())
    assert (outcome["status"], outcome["code"], outcome["dimension"]) == (
        "STOPPED",
        budget.MINER_CEILING_REACHED,
        "provider_attempts",
    )
    built = w.stage("build")
    assert {k: built[k] for k in ("status", "code", "dimension", "ended")} == {
        "status": "STOPPED",
        "code": budget.MINER_CEILING_REACHED,
        "dimension": "provider_attempts",
        "ended": "NOT_SELECTED",
    }
    assert (w.root / "campaign-complete.json").exists()
    assert w.campaign.evaluated == []
    assert graphite_notes(w) == [
        {
            "graphite_stage": "build",
            "status": "STOPPED",
            "stop": "miner_ceiling_reached",
        }
    ]
    view = driver.view(w.root)
    assert view["stage"] == "complete"
    assert view["stages"][-1] == {
        "stage": "build",
        "state": "STOPPED",
        "code": budget.MINER_CEILING_REACHED,
    }
    # Finished stages never run again: a resume sends and records nothing.
    calls = len(w.engine.calls)
    assert w.run(Transport(forbid=True)) is None
    assert len(w.engine.calls) == calls and len(graphite_notes(w)) == 1


def test_research_stages_stop_typed_at_the_miners_own_ceiling(tmp_path, monkeypatch):
    """The hunt's Reader and the Planner meet the miner's ceiling the same
    way: the hunt releases the paper whose call was refused and stops typed,
    the Planner stops having sent nothing, each noted; RESEARCH completes."""
    ceilings = {**CEILINGS, "provider_attempts": 1}
    w = World(
        tmp_path,
        monkeypatch,
        graphite={"mode": "RESEARCH", "hunt": {}},
        ceilings=ceilings,
    )
    w.feed = [
        {"arxiv_id": "2402.00009", "title": "Physics-informed battery operator"},
        {"arxiv_id": "2402.00010", "title": "Operator learning for cell ageing"},
    ]
    w.engine.scripts = {("plan", 1): [[record_plan((HUNTED, "miner_hunt"))]]}
    transport = Transport()
    assert w.run(transport) is None
    assert len(transport.requests) == 1 and len(transport.reader_calls) == 1
    hunted = w.stage("hunt")
    assert (hunted["status"], hunted["code"], hunted["dimension"]) == (
        "STOPPED",
        budget.MINER_CEILING_REACHED,
        "provider_attempts",
    )
    assert hunted["report"]["stop_code"] == budget.MINER_CEILING_REACHED
    # The refused paper was never paid for, so its claim was released.
    assert set(w.library.claims) == {"2402.00009"}
    planned = w.stage("plan")
    assert (planned["status"], planned["code"], planned["dimension"]) == (
        "STOPPED",
        budget.MINER_CEILING_REACHED,
        "provider_attempts",
    )
    assert planned["plan"] is None
    assert graphite_notes(w) == [
        {"graphite_stage": s, "status": "STOPPED", "stop": "miner_ceiling_reached"}
        for s in ("hunt", "plan")
    ]
    assert (w.root / "campaign-complete.json").exists()


def test_a_call_the_campaigns_time_cannot_fit_ends_its_stage_typed(world, monkeypatch):
    """A model call refuses itself, before it reserves anything, when it
    cannot finish inside the campaign's time (`request_model`'s own check,
    not a ledger reservation). The Reader and every stage end typed there
    too, with the time as the dimension; any other refusal still raises."""
    from carbon.development_session import research_agent

    w = world(mode="BUILD")

    async def late(ledger, **_):
        raise ValueError(budget.CALL_TIME_REFUSAL)

    monkeypatch.setattr(driver, "run_epoch", late)
    assert w.run(Transport(forbid=True)) is None
    for stage in ("plan", "build"):
        stopped = w.stage(stage)
        assert (stopped["status"], stopped["code"], stopped["dimension"]) == (
            "STOPPED",
            budget.MINER_CEILING_REACHED,
            "elapsed_seconds",
        ), stage
    assert (w.root / "campaign-complete.json").exists()

    def refuse(*_, **__):
        raise ValueError(budget.CALL_TIME_REFUSAL)

    monkeypatch.setattr(research_agent, "request_model", refuse)
    reader = driver.MinerReader(
        ledger=w.prepared.ledger,
        owner="alice",
        selection=DEFAULT_SELECTION,
        credential_file=None,
        transport=Transport(forbid=True),
        role=editions.READER,
    )
    request = reader.request("extract", {"paper": {"arxiv_id": "2403.00003"}})
    with pytest.raises(ReaderNotSent) as stopped:
        reader(request)
    assert stopped.value.code == budget.MINER_CEILING_REACHED

    def broken(*_, **__):
        raise ValueError("provider output malformed; retained and stopped")

    monkeypatch.setattr(research_agent, "request_model", broken)
    with pytest.raises(ValueError, match="malformed"):
        reader(request)

    async def failing(ledger, **_):
        raise ValueError("provider output malformed; retained and stopped")

    elsewhere = w.root.parent / "other"
    elsewhere.mkdir()
    other = World(elsewhere, monkeypatch, graphite={"mode": "BUILD"})
    monkeypatch.setattr(driver, "run_epoch", failing)
    with pytest.raises(ValueError, match="malformed"):
        other.run(Transport(forbid=True))
    assert other.stage("plan") is None


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


def test_a_campaign_serves_its_own_frozen_pack_after_an_update(world):
    """The pack is copied into the campaign root at the first preparation.
    A Carbon update that ships another pack changes nothing for a campaign
    that froze this one: it resumes on its own copy."""
    w = world(mode="RESEARCH")
    w.engine.scripts = {("plan", 1): [[record_plan(("arxiv-2401.00001", "shared"))]]}
    w.prepare()
    assert w.literature.pack_copies == [w.root]
    copy = w.literature.pack.frozen_path(w.root, PACK_DIGEST)
    assert copy.exists()
    newer = "sha256:" + "6" * 64
    sys.modules[PACKAGE + ".pack"].SHARED_PACK_DIGEST = newer
    w.literature.pack.shipped = newer
    assert w.run(Transport()) is None
    assert w.stage("plan")["status"] == "PLANNED"
    assert w.library.packs[-1].digest == PACK_DIGEST


def test_a_missing_or_damaged_pack_is_refused_before_any_model_call(world):
    w = world(mode="RESEARCH")
    w.prepare()
    copy = w.literature.pack.frozen_path(w.root, PACK_DIGEST)
    # A damaged copy is never replaced.
    copy.write_bytes(b"damaged")
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.run(Transport(forbid=True))
    assert refused.value.code == "literature_pack_missing"
    # A missing copy is made again only from the very pack the campaign froze.
    copy.unlink()
    w.literature.pack.shipped = "sha256:" + "6" * 64
    sys.modules[PACKAGE + ".pack"].SHARED_PACK_DIGEST = w.literature.pack.shipped
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.run(Transport(forbid=True))
    assert refused.value.code == "literature_pack_missing"
    w.literature.pack.shipped = PACK_DIGEST
    sys.modules[PACKAGE + ".pack"].SHARED_PACK_DIGEST = PACK_DIGEST
    w.engine.scripts = {("plan", 1): [STOP_TURN]}
    assert w.run(Transport()) is None and copy.exists()
    # A launch whose shipped pack is missing or damaged never freezes.
    fresh = world(mode="RESEARCH")
    fresh.root = fresh.root.parent / "fresh"
    fresh.literature.pack.damaged = True
    with pytest.raises(research_campaign.OperationRefused) as refused:
        fresh.prepare()
    assert refused.value.code == "literature_pack_missing"
    assert not (fresh.root / "campaign-manifest.json").exists()


def test_a_changed_launch_record_is_refused(world):
    w = world(mode="RESEARCH")
    w.prepare()
    path = driver.launch_path(w.root)
    record = json.loads(path.read_bytes())
    path.unlink()
    path.write_bytes(canonical({**record, "plan_digest": "sha256:" + "0" * 64}))
    with pytest.raises(ValueError, match="launch record differs"):
        w.run(Transport(forbid=True))


PLAN_X = "sha256:" + "1" * 64


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"mode": "EXPLORE"}, "graphite_mode_invalid"),
        ({"mode": ["FULL"]}, "graphite_mode_invalid"),
        ({"research_share": 1.5}, "research_share_invalid"),
        ({"research_share": True}, "research_share_invalid"),
        ({"research_share": float("nan")}, "research_share_invalid"),
        ({"mode": "RESEARCH", "research_share": 0.2}, "research_share_invalid"),
        ({"hunt": {"queries": ["ti:battery AND au:x"]}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["neural ANDNOT operator"]}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["-- battery"]}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["a" * 41]}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["a b c d e f g"]}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["battery"] * 9}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ""}}, "hunt_query_invalid"),
        ({"hunt": {"queries": 0}}, "hunt_query_invalid"),
        ({"hunt": {"max_records": 5001}}, "hunt_query_invalid"),
        ({"hunt": {"max_records": True}}, "hunt_query_invalid"),
        ({"mode": "BUILD", "plan": PLAN_X, "hunt": {}}, "hunt_query_invalid"),
        ({"limits": {"calls_per_epoch": 0}}, "graphite_limits_invalid"),
        ({"limits": {"calls_per_epoch": 100001}}, "graphite_limits_invalid"),
        ({"limits": {"turns": 5}}, "graphite_limits_invalid"),
        ({"limits": 0}, "graphite_limits_invalid"),
        ({"limits": ""}, "graphite_limits_invalid"),
        ({"limits": False}, "graphite_limits_invalid"),
        ({"plan": PLAN_X}, "plan_invalid"),
        ({"mode": "BUILD", "plan": "not-a-digest"}, "plan_invalid"),
        ({"mode": "BUILD", "plan": PLAN_X}, "plan_not_found"),
        # Names that are not launch fields: never read as one.
        ({"mode": "BUILD", "plan_digest": PLAN_X}, "graphite_launch_invalid"),
        ({"edition": editions.EDITION_ID}, "graphite_launch_invalid"),
        ({"curation_digest": "sha256:" + "2" * 64}, "graphite_launch_invalid"),
        ({"surprise": True}, "graphite_launch_invalid"),
    ],
)
def test_a_launch_is_refused_by_its_closed_code(world, fields, code):
    w = world(**fields)
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.prepare()
    assert refused.value.code == code
    assert not (w.root / "campaign-manifest.json").exists()


def test_the_launchpads_choice_is_what_freezes(world):
    """`args.graphite` as the Launchpad's `LaunchChoice.apply` sets it
    (claude/gm-launchpad 9b9e00b0): `{mode, research_share, plan, hunt,
    limits}`, a research share only in FULL, a hunt `{queries: None,
    max_records}`, and beside them `args.graphite_curation_digest`, the
    curation captured at admission - kept, never re-read, even after the
    miner pins or bans."""
    w = world()
    w.library.pins = ["arxiv-2401.00002"]
    w.curation_digest = w.library.curation()["digest"]
    w.graphite.update(
        mode="RESEARCH",
        research_share=None,
        plan=None,
        hunt={"queries": None, "max_records": 200},
        limits={},
    )
    w.library.pins = []
    w.library.bans = ["arxiv-2401.00002"]
    w.prepare()
    block = json.loads((w.root / "campaign-manifest.json").read_bytes())["provider"][
        "graphite"
    ]
    assert block["curation_digest"] == w.curation_digest
    assert (block["mode"], block["research_share"]) == ("RESEARCH", None)
    assert block["hunt"] == {"queries": [], "max_records": 200}
    launch = json.loads(driver.launch_path(w.root).read_bytes())
    assert launch["curation"]["pins"] == ["arxiv-2401.00002"]
    assert launch["curation"]["bans"] == []


@pytest.mark.parametrize(
    ("admitted", "code"),
    [
        ("pins", "graphite_launch_invalid"),
        (7, "graphite_launch_invalid"),
        # A digest the library never recorded: nothing to freeze.
        ("sha256:" + "2" * 64, "curation_not_found"),
    ],
)
def test_an_admitted_curation_the_library_cannot_name_is_refused(world, admitted, code):
    w = world(mode="RESEARCH")
    w.curation_digest = admitted
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.prepare()
    assert refused.value.code == code
    assert not (w.root / "campaign-manifest.json").exists()


def test_an_admitted_plan_is_judged_against_the_admitted_curation(world):
    w = world(mode="BUILD")
    address, _ = saved_plan(w, ("arxiv-2401.00001", "shared"))
    w.curation_digest = w.library.curation()["digest"]
    w.graphite["plan"] = address
    # Banned after admission: the launch the Launchpad admitted still runs.
    w.library.bans = ["arxiv-2401.00001"]
    w.prepare()
    assert json.loads(driver.launch_path(w.root).read_bytes())["plan_digest"] == (
        address
    )


def test_a_planner_launch_with_more_pins_than_a_plan_names_is_refused(world):
    w = world(mode="RESEARCH")
    w.library.pins = [f"arxiv-2401.{n:05d}" for n in range(plans.MAX_PINS + 1)]
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.prepare()
    assert refused.value.code == driver.TOO_MANY_PINS
    w.library.pins = w.library.pins[: plans.MAX_PINS]
    w.prepare()


def test_a_launch_plan_must_be_this_challenges_and_cite_no_banned_card(world):
    w = world(mode="BUILD")
    address, _ = saved_plan(w, ("arxiv-2401.00001", "shared"))
    w.graphite["plan"] = address
    w.library.bans = ["arxiv-2401.00001"]
    with pytest.raises(research_campaign.OperationRefused) as refused:
        w.prepare()
    assert refused.value.code == "card_banned"
    w.library.bans = []
    for challenge in (
        {"id": "another-challenge", "version": CHALLENGE_REF["version"]},
        {"id": CHALLENGE_REF["id"], "version": "another-version"},
    ):
        other = plans.document(
            challenge=challenge,
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
    # The build has no research share; its ledger types the miner's limits.
    assert isinstance(constructor["ledger"], budget.StageLedger)
    assert constructor["ledger"].ledger is w.prepared.ledger
    assert constructor["ledger"].caps == {}
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
    # The edition has one Reader prompt: the hunt's first pass is free.
    assert set(reader.prompts) == {"extract"}
    # The hunt's own partial request (no model fields) is completed from the
    # selection; a foreign prompt, an offered tool, another model or no input
    # is refused before anything is sent - as the hunt's not-sent stop, so the
    # hunt releases the paper's claim.
    partial = reader.complete(
        {
            "instructions": editions.READER_EXTRACTION_PROMPT,
            "input": [{"role": "user", "content": "x"}],
            "tools": [],
            "parallel_tool_calls": False,
            "store": False,
        }
    )
    assert partial["model"] == DEFAULT_SELECTION.model_id
    for bad, code in (
        (
            {"instructions": "You are another agent.", "input": [{"role": "user"}]},
            "reader_prompt_not_frozen",
        ),
        (
            {"input": [{"role": "user"}], "tools": [{"type": "function"}]},
            "reader_request_not_closed",
        ),
        (
            {"input": [{"role": "user"}], "model": "another-model"},
            "reader_request_not_closed",
        ),
        ({"input": []}, "reader_input_required"),
        ({"input": [{"role": "user"}], "task": "triage"}, "reader_prompt_not_frozen"),
    ):
        with pytest.raises(ReaderNotSent) as stopped:
            reader(bad)
        assert stopped.value.code == code
    assert len(transport.requests) == 1
    # The research share refuses before anything is reserved or sent: the
    # hunt hears it as not sent too.
    share = budget.StageLedger(
        prepared.ledger, owner="alice", caps={"provider_attempts": 1}
    )
    capped = driver.MinerReader(
        ledger=share,
        owner="alice",
        selection=DEFAULT_SELECTION,
        credential_file=None,
        transport=transport,
        role=editions.READER,
    )
    with pytest.raises(ReaderNotSent) as stopped:
        capped(capped.request("extract", {"paper": {"arxiv_id": "2403.00002"}}))
    assert stopped.value.code == "research_share_reached"
    assert share.reached["share_cap"] == 1 and len(transport.requests) == 1


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


# --- integration: the literature slice's modules and the engine's loop ----------
#
# These run the committed modules of the slices this one codes against, where
# they are present in the tree: S2's pack, library and hunt (with a fake arXiv
# opener, a fake clock and a private gate file) and S1's research loop. No
# network, no paid model: the provider is scripted.

#: A paper the hunt reads, fresh to the shared pack.
NEW_PAPER = "2610.99901v1"


def literature_module(name):
    return importlib.import_module(PACKAGE + "." + name)


def pack_paper():
    """An arXiv id the shipped pack already holds a card for."""
    for card in literature_module("pack").load_shared_pack().cards:
        if card["card_id"].startswith("arxiv-"):
            return card["card_id"][len("arxiv-") :]
    raise AssertionError("the shipped pack holds no arXiv card")


def arxiv_entry(arxiv_id, title, abstract):
    return f"""<entry>
<id>http://arxiv.org/abs/{arxiv_id}</id>
<updated>2026-10-01T00:00:00Z</updated>
<published>2026-10-01T00:00:00Z</published>
<title>{title}</title>
<summary>{abstract}</summary>
<author><name>Fixture Author</name></author>
<arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.LG"/>
<category term="cs.LG"/>
</entry>"""


def arxiv_feed():
    """Two records: one the pack holds (never read), one new."""
    entries = (
        arxiv_entry(pack_paper(), "A paper the pack already holds", "Known."),
        arxiv_entry(
            NEW_PAPER,
            "Physics-informed neural operator surrogate for lithium-ion battery "
            "fast charging",
            "We train a Fourier neural operator surrogate of an electrochemical "
            "battery model on simulated cycling data; the learned surrogate "
            "predicts terminal voltage and capacity fade.",
        ),
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
        f"<opensearch:totalResults>{len(entries)}</opensearch:totalResults>"
        + "".join(entries)
        + "</feed>"
    ).encode()


class ArxivResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ArxivOpener:
    """DEVELOPMENT FIXTURE: answers every arXiv request with the fixture
    feed (the hunt's client calls `opener(request, timeout)`)."""

    def __init__(self, forbid=False):
        self.urls = []
        self.forbid = forbid

    def __call__(self, request, timeout):
        assert not self.forbid, "no arXiv request is expected here"
        self.urls.append(request.full_url)
        return ArxivResponse(arxiv_feed())


class FakeClock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def function_call(call_id, name, arguments):
    return {
        "type": "function_call",
        "id": "fc-" + call_id,
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(arguments),
        "status": "completed",
    }


class RoleTransport(Transport):
    """The model provider, scripted per role: a Reader request (no tools)
    gets an extraction; a Planner or Constructor turn gets its next scripted
    tool calls."""

    def __init__(self, planner=(), constructor=()):
        super().__init__()
        self.turns = {"planner": list(planner), "constructor": list(constructor)}

    def __call__(self, request):
        self.requests.append(json.loads(canonical(request)))
        if not request["tools"]:
            return response([text_reply(EXTRACTION)])
        role = (
            "planner"
            if request["instructions"].startswith(editions.PLANNER_PROMPT)
            else "constructor"
        )
        turn = self.turns[role].pop(0)
        index = len(self.requests)
        return response(
            [
                function_call(f"{role}-{index}-{n}", name, arguments)
                for n, (name, arguments) in enumerate(turn)
            ]
        )


#: A stop the research loop accepts.
REAL_STOP = [
    (
        editions.STOP,
        {
            "reason": "plateau",
            "evidence": "fixture: nothing further to try",
            "used_feedback": False,
        },
    )
]


@pytest.fixture
def gate(tmp_path, monkeypatch):
    """The hunt's host-wide arXiv gate, as a private file for this test."""
    monkeypatch.setenv("CARBON_ARXIV_GATE", str(tmp_path / "arxiv-gate"))


def reader_ledger(tmp_path, caps):
    ledger = CampaignLedger(tmp_path / "ledger", clock=lambda: 1000)
    ledger.freeze(
        {
            "schema": "carbon.autoresearch.campaign.v1",
            **dict.fromkeys(
                (
                    "campaign_id",
                    "implementation",
                    "objective",
                    "sampling",
                    "control",
                    "selection",
                    "replica_policy",
                    "provider",
                ),
                "fixture",
            ),
            "owner": "alice",
            "ceilings": CEILINGS,
        }
    )
    share = budget.StageLedger(ledger, owner="alice", caps=caps)
    return ledger, share


@needs_literature
def test_the_literature_slice_sends_and_bounds_what_the_edition_froze():
    hunts = literature_module("hunt")
    focus = literature_module("focus")
    library = literature_module("library")
    pack = literature_module("pack")
    # The prompt every hunt request carries is the edition's frozen one.
    assert hunts.READER_PROMPT == editions.READER_EXTRACTION_PROMPT
    assert hunts.READER_PROMPT_DIGEST == (
        editions.READER.record()["prompt_digests"]["extract"]
    )
    # The launch bounds are the hunt's and the library's own.
    assert hunts.MAX_RECORDS == editions.MAX_HUNT_RECORDS
    assert hunts.DEFAULT_MAX_RECORDS == editions.DEFAULT_MAX_RECORDS
    assert library.MAX_OUTCOME_CARDS == driver.LEARNING_CARDS
    assert focus.MAX_MINER_QUERIES == editions.MAX_QUERIES
    assert focus.MAX_TERMS == editions.MAX_QUERY_TERMS
    assert focus.MAX_TERM_CHARS == editions.MAX_TERM_CHARS
    assert focus.OPERATORS == editions.QUERY_OPERATORS
    assert pack.ORIGINS == editions.ORIGINS
    for query in (
        "neural operator battery",
        "fast-charge  ageing",
        "a b c d e f",
        "neural ANDNOT operator",
        "-- battery",
        "a" * 41,
        "a b c d e f g",
        "ti:battery",
        "",
    ):
        try:
            focus.parse_miner_queries([query])
            accepted = True
        except focus.QueryRefused:
            accepted = False
        assert editions.check_query(query) is accepted, query


@needs_literature
def test_a_real_hunt_reads_once_through_the_miner_reader(tmp_path, gate):
    from carbon.challenge_registry import describe

    hunts = literature_module("hunt")
    library = driver.open_library(tmp_path / "library")
    ledger, share = reader_ledger(tmp_path, {})
    transport = Transport()
    reader = driver.MinerReader(
        ledger=share,
        owner="alice",
        selection=DEFAULT_SELECTION,
        credential_file=None,
        transport=transport,
        role=editions.READER,
    )
    opener = ArxivOpener()
    keywords = {
        "challenge": CHALLENGE_REF,
        "discovery": describe(CHALLENGE_REF["id"], CHALLENGE_REF["version"]),
        "queries": ["neural operator battery"],
        "max_records": 10,
        "reader": reader,
        "arxiv_opener": opener,
        "clock": FakeClock(),
        "checkpoint": ledger.checkpoint,
        "hunt_id": "campaign-integration",
    }
    report = hunts.run_hunt(library, **keywords)
    assert report["status"] == "COMPLETED", report
    assert report["extracted"] == 1 and report["deduped"] >= 1
    assert len(transport.reader_calls) == 1
    sent = transport.reader_calls[0]
    assert sent["instructions"] == editions.READER_EXTRACTION_PROMPT
    assert sent["model"] == DEFAULT_SELECTION.model_id and sent["tools"] == []
    card = library.card("arxiv-" + NEW_PAPER)
    assert card["origin"] == "miner_hunt" and card["check_status"] == "UNCHECKED"
    operations = ledger.status(owner="alice")["operations"]
    assert [op["id"][: len(budget.READER_PREFIX)] for op in operations] == [
        budget.READER_PREFIX
    ]
    # The same hunt again replays its report: no arXiv and no model call.
    fetched = len(opener.urls)
    assert hunts.run_hunt(library, **keywords) == report
    assert len(opener.urls) == fetched and len(transport.requests) == 1


@needs_literature
def test_a_real_hunt_stopped_by_the_share_releases_its_claim(tmp_path, gate):
    from carbon.challenge_registry import describe

    hunts = literature_module("hunt")
    pack = literature_module("pack")
    library = driver.open_library(tmp_path / "library")
    ledger, share = reader_ledger(tmp_path, {"provider_attempts": 0})
    transport = Transport()
    reader = driver.MinerReader(
        ledger=share,
        owner="alice",
        selection=DEFAULT_SELECTION,
        credential_file=None,
        transport=transport,
        role=editions.READER,
    )
    report = hunts.run_hunt(
        library,
        challenge=CHALLENGE_REF,
        discovery=describe(CHALLENGE_REF["id"], CHALLENGE_REF["version"]),
        queries=None,
        max_records=10,
        reader=reader,
        arxiv_opener=ArxivOpener(),
        clock=FakeClock(),
        checkpoint=ledger.checkpoint,
        hunt_id="campaign-share",
    )
    assert (report["status"], report["stop_code"]) == (
        "STOPPED",
        "research_share_reached",
    )
    assert transport.requests == []
    # Nothing was paid, so nothing stays claimed: a later hunt may read it.
    assert library.claim_state(pack.paper_key(NEW_PAPER)) is None
    assert share.reached["share_cap"] == 0


@needs_engine
def test_research_runs_on_the_real_literature_and_research_loop(
    tmp_path, monkeypatch, gate
):
    """8a on the committed slices: a hunt over a fixture feed of two records
    (the pack's paper is never read; the new one is extracted to a private
    card), the Planner's parallel turn through the real research loop, a
    plan citing the miner card, no practice or selection, the campaign
    completes, and a resume makes no model and no arXiv call."""
    w = World(
        tmp_path,
        monkeypatch,
        graphite={"mode": "RESEARCH", "hunt": {"queries": ["neural operator battery"]}},
        real=True,
    )
    hunted = "arxiv-" + NEW_PAPER
    transport = RoleTransport(
        planner=[
            [
                (editions.LIT_SEARCH, {"query": "neural operator battery"}),
                workspace("check_design", {"design": {"strategy": RECIPE}}),
                workspace(
                    "capability_request",
                    {"request": {"purpose": "fixture", "operation": "a capability"}},
                ),
            ],
            [record_plan((hunted, "miner_hunt"))],
        ]
    )
    opener = ArxivOpener()
    assert w.run(transport, arxiv_opener=opener, clock=FakeClock()) is None
    assert len(transport.reader_calls) == 1
    assert transport.reader_calls[0]["instructions"] == (
        editions.READER_EXTRACTION_PROMPT
    )
    hunt = w.stage("hunt")
    assert hunt["status"] == "DONE" and hunt["report"]["extracted"] == 1
    planned = w.stage("plan")
    assert planned["status"] == "PLANNED", planned
    assert planned["plan"]["hypotheses"][0]["cites"] == [
        {"card_id": hunted, "origin": "miner_hunt"}
    ]
    assert w.library.plan(planned["plan_digest"]) == planned["plan"]
    plan_file = json.loads((w.root / "epoch-1" / "plan" / "plan.json").read_bytes())
    assert plan_file["stage"] == "plan"
    assert plan_file["agent_policy"]["version"] == editions.AGENT_POLICY
    dispatched = [a.get("action") for _, _, a in w.prepared.sdk.dispatched]
    assert dispatched == ["check_design", "capability_request"]
    assert (w.root / "campaign-complete.json").exists()
    requests = len(transport.requests)
    assert w.run(Transport(forbid=True), arxiv_opener=ArxivOpener(forbid=True)) is None
    assert len(transport.requests) == requests


@needs_engine
def test_the_research_loop_stops_the_planner_typed_at_the_share(
    tmp_path, monkeypatch, gate
):
    """FULL with a share of two calls (5% of 40 attempts): the share ledger
    refuses the Planner's third call as the engine's typed ceiling, so the
    research loop itself ends the session STOPPED `research_share_reached`,
    journalled, with nothing of that call sent; the build goes on with the
    rest of the budget."""
    w = World(
        tmp_path,
        monkeypatch,
        graphite={"mode": "FULL", "research_share": 0.05},
        real=True,
    )
    search = [(editions.LIT_SEARCH, {"query": "neural operator battery"})]
    transport = RoleTransport(
        planner=[search, search, search], constructor=[REAL_STOP, REAL_STOP]
    )
    assert w.run(transport) is None
    planned = w.stage("plan")
    assert (planned["status"], planned["code"]) == ("STOPPED", "research_share_reached")
    assert planned["share"]["share_cap"] == 2
    outcome = json.loads((w.root / "epoch-1" / "plan" / "outcome.json").read_bytes())
    assert (outcome["status"], outcome["code"]) == ("STOPPED", "research_share_reached")
    sent = [
        r
        for r in transport.requests
        if r["instructions"].startswith(editions.PLANNER_PROMPT)
    ]
    assert len(sent) == 2
    assert w.stage("build")["ended"] == "NOT_SELECTED"


@needs_engine
def test_the_research_loop_stops_the_build_typed_at_the_miners_ceiling(
    tmp_path, monkeypatch, gate
):
    """8e's end on the real research loop: the miner's own ceiling refuses
    the Constructor's next call, the loop records the epoch's outcome
    STOPPED `miner_ceiling_reached` with the dimension, and the campaign
    completes instead of being interrupted."""
    ceilings = {**CEILINGS, "provider_attempts": 3}
    w = World(
        tmp_path, monkeypatch, graphite={"mode": "BUILD"}, ceilings=ceilings, real=True
    )
    read = [(editions.LIT_CARD, {"card_id": "arxiv-" + pack_paper()})]
    transport = RoleTransport(planner=[REAL_STOP], constructor=[read] * 5)
    assert w.run(transport) is None
    assert len(transport.requests) == 3
    assert w.spent()["provider_attempts"] == 3
    outcome = json.loads((w.root / "epoch-1" / "outcome.json").read_bytes())
    assert (outcome["status"], outcome["code"], outcome["dimension"]) == (
        "STOPPED",
        budget.MINER_CEILING_REACHED,
        "provider_attempts",
    )
    built = w.stage("build")
    assert (built["status"], built["code"]) == ("STOPPED", "miner_ceiling_reached")
    assert (w.root / "campaign-complete.json").exists()
    # A resume replays: nothing is sent again.
    assert w.run(Transport(forbid=True)) is None


@needs_engine
def test_the_engine_holds_practice_before_a_miner_selection(
    tmp_path, monkeypatch, gate
):
    """Under the miner policy the research loop itself refuses a selection
    of an unpractised recipe (`selection_not_practiced`), so the Constructor
    learns it while it can still practise; the practised recipe it then
    selects is submitted."""
    w = World(tmp_path, monkeypatch, graphite={"mode": "BUILD"}, real=True)
    transport = RoleTransport(
        planner=[REAL_STOP],
        constructor=[
            [practice(RECIPE)],
            [select(UNPRACTISED)],
            [select(RECIPE)],
            REAL_STOP,
        ],
    )
    assert w.run(transport) is None
    assert w.stage("plan")["status"] == "STOPPED"
    refusals = [
        json.loads(path.read_bytes())
        for path in sorted((w.root / "epoch-1").glob("epoch-1-tool-*-result.json"))
    ]
    assert any(r.get("code") == "selection_not_practiced" for r in refusals)
    assert w.campaign.evaluated == [(1, RECIPE)]
    assert w.stage("build")["ended"] == "NOT_SELECTED"
