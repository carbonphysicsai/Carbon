"""The miner edition's driver: `run(prepared)` inside a miner's own campaign.

`research_campaign.execute` hands a campaign whose agent is `graphite` here
(`research_campaign.run_graphite`), so this runs under everything a Launchpad
campaign already has: its owner lock and control generation, the miner's
ledger and ceilings, pause and stop at every ledger checkpoint, resume,
reconcile, `last_refusal` and the campaign's own submit.

**Modes** (frozen at launch in the provider plan's `graphite` block,
`edition.graphite_block`):

- RESEARCH: an optional hunt, then the Planner, whose plan is stored in the
  miner's library by digest. Nothing is practised for selection, frozen or
  submitted; the campaign completes.
- BUILD: the plan the miner chose (frozen at launch by digest), or none - then
  an optional hunt and the Planner run first - and then the Constructor's
  epochs, whose selection goes through `research_campaign.submit_candidate`
  to the Challenge's validator, as Carbon's autonomous agent's does.
- FULL (the default): RESEARCH's stages under the miner's research share of
  the provider ceilings (`budget.StageLedger`: the hunt within its part of
  the share, the Planner within the rest; a stage that reaches its cap stops
  typed `research_share_reached`), then BUILD.

**Stages** are recorded write-once under `<campaign>/graphite/stages/`; a
finished stage is never run again, so a resume makes no hunt, no arXiv and no
model call for it. The hunt runs under one hunt id per campaign, so a resumed
hunt continues where it stopped; its stage record keeps its report's counts.
The Planner runs as the research loop's stage
`plan` of epoch 1 (`epoch-1/plan/`, identities `epoch-1-plan-*`); the
Constructor runs the campaign's epochs as the autonomous agent does
(`epoch-N/`), which the campaign's submit reads. Every role runs under
`edition.agent_policy()` with its frozen prompt and its stage's tools, the
campaign's frozen parallel-call, miner-guidance and research-tools rules, its
frozen limits (`LIMITS_V2`) and compaction rule, and the miner's model
selection and key.

**Frozen inputs.** At the first preparation (`freeze_launch`) the shared card
pack is copied write-once into the campaign root, and the launch's curation
(pins and bans, as the Launchpad admitted them) and its chosen plan are
written once beside the manifest, bound to the frozen block by digest. A run
serves the campaign's own pack copy (`literature_pack_missing` when it is
missing or damaged), and an edition this code does not publish is refused
`graphite_edition_unknown` - both before any model call.

**Learning.** After each Constructor epoch, before its selection is
submitted, the cards its plan cited are recorded in the miner's library as
having led to a practised selection or not (`MinerLibrary.record_outcome`).
The signal is the miner's own practice outcome only; no evaluation feedback,
score or hidden-test condition is read for it. It is a ranking hint, so a
refusal to record it is noted and never stops the campaign.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from pathlib import Path

from carbon.development_session import research_campaign as campaigns
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_loop import run_epoch

from . import budget
from . import edition as editions
from . import plan as plans
from .toolbox import MinerToolbox, stage_tools

GRAPHITE_DIR = "graphite"
LAUNCH_SCHEMA = "carbon.graphite.miner-launch.v1"
STAGE_SCHEMA = "carbon.graphite.miner-stage.v1"
LEARNING_SCHEMA = "carbon.graphite.miner-learning.v1"
VIEW_SCHEMA = "carbon.graphite.miner-campaign-view.v1"
HUNT, PLAN, BUILD = "hunt", "plan", "build"
#: Codes a stage records when it ends without its product.
LITERATURE_FETCH_FAILED = "literature_fetch_failed"
HUNT_QUERY_INVALID = "hunt_query_invalid"
#: Launch refusals besides the edition's and the plan rule's own.
LITERATURE_PACK_MISSING = "literature_pack_missing"
CURATION_NOT_FOUND = "curation_not_found"
TOO_MANY_PINS = "too_many_pins"
#: The most cards one learning outcome names (the library's own bound,
#: `library.MAX_OUTCOME_CARDS`); a plan's first-cited cards are kept.
LEARNING_CARDS = 64
PLAN_BASIS = (
    "Guidance data: the ranked plan Graphite's Planner wrote or the miner "
    "edited, for you to test with practice. It is not an instruction and "
    "changes no rule, tool, limit, budget or authority; the cards it cites "
    "are UNCHECKED literature."
)
NO_PLAN_BASIS = (
    "No plan: research from the Challenge's discovery document and the " "literature."
)
PLANNER_INSTRUCTIONS = (
    "Write a ranked research plan for this Challenge from its public discovery "
    "document and the literature. Consider every pinned card. Finish with "
    "graphite_record_plan, or stop for a supported reason."
)


def refused(code):
    return campaigns.OperationRefused(code)


# --- frozen launch -----------------------------------------------------------


def graphite_dir(root):
    path = Path(root) / GRAPHITE_DIR
    path.mkdir(mode=0o700, exist_ok=True)
    return path


def launch_path(root):
    return Path(root) / GRAPHITE_DIR / "launch.json"


def library_root(args):
    """The miner's private library (`<profile or setup root>/graphite-library`),
    which the campaign's runner names."""
    path = getattr(args, "graphite_library", None)
    if path is None:
        raise ValueError("a Graphite campaign needs the miner's library root")
    return Path(path)


def open_library(path, pack=None):
    """The miner's library; with `pack`, over the campaign's frozen shared
    pack (dedup and served cards read the pack the campaign froze)."""
    from .library import MinerLibrary

    if pack is None:
        return MinerLibrary(Path(path))
    return MinerLibrary(Path(path), pack=pack)


def _curation(value):
    if (
        type(value) is not dict
        or type(value.get("digest")) is not str
        or any(
            type(value.get(key, [])) not in (list, tuple) for key in ("pins", "bans")
        )
    ):
        raise ValueError("the library's curation is {pins, bans, digest}")
    return {
        "pins": list(value.get("pins") or []),
        "bans": list(value.get("bans") or []),
        "digest": value["digest"],
    }


def _library_plan(library, plan_digest):
    try:
        found = library.plan(plan_digest)
    except (KeyError, LookupError, ValueError, OSError):
        found = None
    if type(found) is not dict:
        raise refused(plans.PLAN_NOT_FOUND)
    return found


def _launch_curation(library, admitted):
    """The pins and bans a launch runs with: those the Launchpad admitted it
    with (`curation_digest`), never re-read from the library's current state;
    or, for a launch that names none, the library's current curation."""
    if admitted is None:
        return _curation(library.curation())
    try:
        found = _curation(library.curation_state(admitted))
    except (LookupError, ValueError, OSError):
        raise refused(CURATION_NOT_FOUND) from None
    if found["digest"] != admitted:
        raise refused(CURATION_NOT_FOUND)
    return found


def _check_hunt(hunt):
    """A hunt is checked again by the hunt's own rule (`hunt.validate_hunt`),
    so a launch the hunt would refuse is refused before the manifest
    freezes, never once the hunt runs."""
    if hunt is None:
        return
    from . import hunt as hunts

    validate = getattr(hunts, "validate_hunt", None)
    if validate is None:
        return
    try:
        validate(
            {"queries": hunt["queries"] or None, "max_records": hunt["max_records"]}
        )
    except ValueError:
        raise refused(HUNT_QUERY_INVALID) from None


def _freeze_pack(root):
    """Copy the shipped card pack write-once into the campaign root; its
    digest. `literature_pack_missing` when it is absent or damaged."""
    from . import pack as packs

    try:
        copied = packs.freeze_into(Path(root))
    except (OSError, ValueError, KeyError):
        raise refused(LITERATURE_PACK_MISSING) from None
    if copied != packs.SHARED_PACK_DIGEST:
        raise refused(LITERATURE_PACK_MISSING)
    return copied


def freeze_launch(args, root, *, challenge):
    """At a Graphite campaign's first preparation: the `graphite` block its
    provider plan freezes (`edition.graphite_block`).

    Validates the launch fields the Launchpad admitted (`args.graphite`, with
    `args.graphite_curation_digest` beside them; the hunt also by the hunt's
    own rule), copies the shared card pack into
    the campaign root, reads the miner's library once - the curation the
    launch was admitted with (or, for none, the current one), its private
    snapshot and the chosen plan, which must be this Challenge's and pass
    `plan.validate_plan` against that curation - and writes that curation
    and plan once beside the manifest (`launch.json`), bound to the block by
    digest. A launch whose Planner would have to consider more pins than a
    plan can name is refused `too_many_pins`. Refused by closed code
    (`OperationRefused`) before the manifest freezes."""
    try:
        fields = editions.launch_fields(
            getattr(args, "graphite", None),
            curation_digest=getattr(args, "graphite_curation_digest", None),
        )
    except editions.LaunchRefused as refusal:
        raise refused(refusal.code) from None
    _check_hunt(fields["hunt"])
    library = open_library(library_root(args))
    curation = _launch_curation(library, fields["curation_digest"])
    if editions.plans_first(fields) and len(curation["pins"]) > plans.MAX_PINS:
        raise refused(TOO_MANY_PINS)
    plan_doc = None
    if fields["plan"] is not None:
        plan_doc = _library_plan(library, fields["plan"])
        if plan_doc.get("challenge") != {
            "id": challenge["id"],
            "version": challenge["version"],
        }:
            raise refused(plans.PLAN_INVALID)
        ok, refusal = plans.validate_plan(plan_doc, library=library, curation=curation)
        if not ok:
            raise refused(refusal["code"])
    block = editions.graphite_block(
        fields,
        curation_digest=curation["digest"],
        pack_digest=_freeze_pack(root),
        private_snapshot_digest=library.snapshot(),
    )
    record = {
        "schema": LAUNCH_SCHEMA,
        "block_digest": digest(canonical(block)),
        "curation": curation,
        "plan_digest": fields["plan"],
        "plan": plan_doc,
    }
    path = launch_path(root)
    graphite_dir(root)
    payload = canonical(record)
    if path.exists() and path.read_bytes() != payload:
        if (Path(root) / "campaign-manifest.json").exists():
            raise ValueError("the frozen Graphite launch record differs")
        # An earlier preparation stopped before its manifest froze: nothing
        # ran under that record.
        path.unlink()
    write_once(path, payload)
    return block


def frozen_launch(root, block):
    """The launch record frozen with `block`, checked against it."""
    path = launch_path(root)
    if not path.exists():
        raise ValueError("the Graphite launch record is missing")
    record = json.loads(path.read_bytes())
    if (
        record.get("schema") != LAUNCH_SCHEMA
        or record.get("block_digest") != digest(canonical(block))
        or _curation(record.get("curation"))["digest"] != block["curation_digest"]
        or record.get("plan_digest") != block["plan_digest"]
        or (block["plan_digest"] is not None and type(record.get("plan")) is not dict)
    ):
        raise ValueError("the Graphite launch record differs from the frozen plan")
    if record["plan"] is not None:
        plans.check_shape(record["plan"])
    return record


def frozen_pack(root, block):
    """The shared card pack this campaign froze, from its own copy in the
    campaign root (`pack.load_frozen`), so a Carbon update that ships another
    pack never changes it. A missing copy is made again only from the very
    pack the campaign froze; a missing or damaged pack is refused
    `literature_pack_missing`."""
    from . import pack as packs

    want = block["literature"]["pack_digest"]
    root = Path(root)
    shared = None
    try:
        shared = packs.load_frozen(root, want)
    except (OSError, ValueError, KeyError):
        shared = None
    if shared is None and want == packs.SHARED_PACK_DIGEST:
        try:
            if not packs.frozen_path(root, want).exists():
                packs.freeze_into(root)
                shared = packs.load_frozen(root, want)
        except (OSError, ValueError, KeyError):
            shared = None
    if shared is None or getattr(shared, "digest", None) != want:
        raise refused(LITERATURE_PACK_MISSING)
    return shared


# --- stage records -----------------------------------------------------------


def _note_stage_end(run, stage, body):
    """A research stage that ended without its product (stopped at the
    research share, refused, arXiv failed) is noted in the campaign ledger,
    where the miner's campaign view and agent read it. Noted before the
    stage record is written, so a resume never loses it."""
    if body.get("code") is not None:
        run.ledger.note(
            owner=run.owner,
            kind="decision",
            body={
                "graphite_stage": stage,
                "status": body["status"],
                "stop": body["code"],
            },
        )


class Stages:
    """Write-once stage records under `<campaign>/graphite/stages/`."""

    def __init__(self, root):
        self.root = Path(root) / GRAPHITE_DIR / "stages"

    def _ensure(self):
        graphite_dir(self.root.parent.parent)
        self.root.mkdir(mode=0o700, exist_ok=True)

    def started(self, name):
        return (self.root / (name + ".started.json")).exists()

    def finished(self, name):
        path = self.root / (name + ".json")
        return json.loads(path.read_bytes()) if path.exists() else None

    def start(self, name):
        self._ensure()
        write_once(
            self.root / (name + ".started.json"),
            canonical({"schema": STAGE_SCHEMA, "stage": name, "started": True}),
        )

    def finish(self, name, body):
        self._ensure()
        record = {"schema": STAGE_SCHEMA, "stage": name, **body}
        write_once(self.root / (name + ".json"), canonical(record))
        return record


def stage_sequence(block):
    """The stages a frozen block runs, in order."""
    research = []
    if editions.plans_first(block):
        research = ([HUNT] if block["hunt"] is not None else []) + [PLAN]
    if block["mode"] == editions.RESEARCH_MODE:
        return research
    return [*research, BUILD]


# --- the Reader --------------------------------------------------------------


class ReaderRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


_CLOSED_REQUEST = (
    "model",
    "instructions",
    "input",
    "tools",
    "parallel_tool_calls",
    "store",
    "max_output_tokens",
    "reasoning",
)


class MinerReader:
    """The hunt's `reader`: one closed, tool-less extraction call on the
    miner's model selection, metered against the campaign ledger (the hunt's
    part of the research share, in FULL).

    `prompts` are the edition's Reader prompts (`extract`), the only
    instructions a Reader call may carry: the hunt's requests carry exactly
    that prompt. A request is the closed research request
    (`research_agent.request_model`), or a part of one - `{input,
    instructions?, task?}` - which `complete` fills from the selection. Its
    identity is `graphite-reader-` and its digest, so the same paper's request
    is one call: a resume, or a hunt that meets it again, replays the
    journalled reply and never pays twice.

    A call refused before anything is sent - the research share reached, or
    a request this Reader will not send - raises the hunt's own
    `hunt.ReaderNotSent` with that code, so the hunt releases the paper's
    claim (a later hunt may read it) and stops typed."""

    def __init__(self, *, ledger, owner, selection, credential_file, transport, role):
        self.ledger, self.owner = ledger, owner
        self.selection = selection
        self.credential_file = credential_file
        self.transport = transport
        self.prompts = dict(role.prompts)

    def request(self, task, content):
        """A closed Reader request for `content` (JSON data, sent as text)."""
        if task not in self.prompts:
            raise ReaderRefused("reader_task_unknown")
        return self.complete(
            {
                "instructions": self.prompts[task],
                "input": [{"role": "user", "content": canonical(content).decode()}],
            }
        )

    def complete(self, request):
        if type(request) is not dict or set(request) - {*_CLOSED_REQUEST, "task"}:
            raise ReaderRefused("reader_request_not_closed")
        settings = self.selection.settings
        effort = settings.reasoning_effort
        instructions = request.get("instructions")
        if instructions is None:
            instructions = self.prompts.get(request.get("task") or "extract")
        if instructions not in self.prompts.values():
            raise ReaderRefused("reader_prompt_not_frozen")
        closed = {
            "model": self.selection.model_id,
            "instructions": instructions,
            "input": request.get("input"),
            "tools": [],
            "parallel_tool_calls": False,
            "store": False,
            "max_output_tokens": settings.max_output_tokens,
            "reasoning": None if effort is None else {"effort": effort},
        }
        if type(closed["input"]) is not list or not closed["input"]:
            raise ReaderRefused("reader_input_required")
        for key in _CLOSED_REQUEST:
            if key in request and request[key] != closed[key]:
                raise ReaderRefused("reader_request_not_closed")
        return closed

    def identity(self, closed):
        return budget.READER_PREFIX + digest(canonical(closed))[7:47]

    def __call__(self, request):
        from carbon.development_session.research_agent import request_model

        from .hunt import ReaderNotSent

        try:
            closed = self.complete(request)
        except ReaderRefused as refusal:
            raise ReaderNotSent(refusal.code) from None
        try:
            return request_model(
                self.ledger,
                owner=self.owner,
                identity=self.identity(closed),
                request=closed,
                credential_file=self.credential_file,
                phase="research",
                transport=self.transport,
                provider=self.selection,
            )
        except budget.ResearchShareReached as reached:
            # Refused by the share before anything was reserved or sent.
            raise ReaderNotSent(reached.code) from None


# --- the run -----------------------------------------------------------------


class _LiteratureCards:
    """`validate_plan`'s card lookup over exactly the literature a stage was
    served (lit_card), so a plan cites only cards its Planner could read."""

    def __init__(self, literature):
        self.literature = literature

    def card(self, card_id):
        result = self.literature.lit_card({"card_id": card_id})
        if type(result) is not dict:
            return None
        if type(result.get("card")) is dict and result.get("status", "OK") == "OK":
            card = dict(result["card"])
            for key in ("origin", "check_status"):
                if key in result and key not in card:
                    card[key] = result[key]
            return card
        return None


@dataclass
class _Run:
    prepared: object
    edition: object
    block: dict
    launch: dict
    pack: object
    library: object
    transport: object
    arxiv_opener: object
    clock: object

    @property
    def ledger(self):
        return self.prepared.ledger

    @property
    def owner(self):
        return self.prepared.owner

    @property
    def manifest(self):
        return self.prepared.manifest

    @property
    def provider_plan(self):
        return self.manifest["provider"]

    @property
    def challenge(self):
        return dict(self.manifest["challenge"])

    @property
    def stages(self):
        return Stages(self.ledger.root)

    @property
    def curation(self):
        return _curation(self.launch["curation"])

    @property
    def selection(self):
        from carbon.development_session.model_provider import DEFAULT_SELECTION

        return self.prepared.selection or DEFAULT_SELECTION

    def provider_kw(self):
        selection = self.prepared.selection
        return {} if selection is None else {"provider": selection}

    def snapshot(self):
        """The private library snapshot this campaign's stages read: the one
        its hunt left, else the one its launch saw."""
        hunted = self.stages.finished(HUNT)
        if hunted is not None and hunted.get("private_snapshot_digest") is not None:
            return hunted["private_snapshot_digest"]
        return self.block["literature"]["private_snapshot_digest"]

    def literature(self):
        """The literature this campaign's stages serve: its frozen pack, the
        private snapshot, the launch's curation and - as focus terms that
        steer the ranking - the miner's own hunt queries."""
        from .library import MinerLiterature

        focus = list((self.block["hunt"] or {}).get("queries") or [])
        return MinerLiterature(
            self.pack,
            self.library,
            challenge=self.challenge,
            private_snapshot_digest=self.snapshot(),
            curation=self.curation,
            **({"focus_terms": focus} if focus else {}),
        )

    def tools(self, role):
        from carbon.development_session.research_tools import (
            frozen_tools_rule,
            tools_for_sdk,
        )

        schemas = tools_for_sdk(self.prepared.sdk, frozen_tools_rule(self.manifest))
        return stage_tools(role, schemas, guidance=self.guidance is not None)

    @property
    def guidance(self):
        return campaigns.frozen_miner_guidance(self.manifest)

    def toolbox(self, role, stage):
        return MinerToolbox(
            role=role,
            sdk=self.prepared.sdk,
            literature=self.literature(),
            ledger=self.ledger,
            owner=self.owner,
            stage=stage,
            bans=self.curation["bans"],
        )

    def engine(self, stage):
        """The research loop keywords every miner-edition stage shares."""
        return {
            "owner": self.owner,
            "credential_file": self.prepared.args.api_key_file,
            "transport": self.transport,
            "agent_policy": editions.agent_policy(),
            "challenge": self.prepared.challenge,
            "parallel_calls": campaigns.frozen_parallel_calls(self.manifest),
            "miner_guidance": self.guidance,
            "limits": self.provider_plan["limits"][stage],
            "compaction": self.provider_plan["compaction"],
            **self.provider_kw(),
        }

    def observation(self, epoch, feedback):
        """The campaign's own first observation, as Carbon's autonomous agent
        is given it, with the miner's budget beside it."""
        observation = dict(
            self.prepared.campaign.observation(self.prepared, epoch, feedback)
        )
        manifest = self.manifest
        if manifest.get("schema") == campaigns.PRODUCT:
            observation["miner_budget"] = {
                key: manifest[key]
                for key in ("ceilings", "elapsed_seconds", "final_reserve")
                if key in manifest
            } or None
            observation["miner_budget_basis"] = (
                "The miner's own budget, enforced by the controller. None "
                "means the miner set none: there is no limit to infer, and "
                "the miner may stop the campaign at any time."
            )
        return observation

    def hunt_id(self):
        """This campaign's one hunt id: stable across a resume (the hunt
        keeps the queries it started with), distinct across campaigns."""
        bound = {
            "campaign_id": self.manifest.get("campaign_id"),
            "graphite": self.block,
        }
        return "campaign-" + digest(canonical(bound))[7:47]

    def graphite_context(self, role):
        return {
            "edition": self.edition.edition_id,
            "role": role,
            "mode": self.block["mode"],
            "literature": {
                "pack_digest": self.block["literature"]["pack_digest"],
                "private_snapshot_digest": self.snapshot(),
                "origins": list(editions.ORIGINS),
                "check_status": "UNCHECKED",
            },
        }


def _research_ledger(run, stage):
    """A research stage's ledger. In FULL, the share of the provider
    ceilings: the hunt's part of it over the hunt's own calls, the whole
    share over every research call for the Planner. In RESEARCH, and for a
    BUILD whose Planner runs first, the campaign ledger's own ceilings
    alone."""
    if run.block["mode"] != editions.FULL_MODE:
        return budget.StageLedger(run.ledger, owner=run.owner, caps={})
    fraction = editions.share_fraction(run.block)
    namespace = budget.RESEARCH_NAMESPACE
    if stage == HUNT:
        fraction *= editions.HUNT_PART_OF_SHARE
        namespace = budget.HUNT_NAMESPACE
    caps = budget.share_caps(run.manifest.get("ceilings") or {}, fraction)
    return budget.StageLedger(
        run.ledger, owner=run.owner, caps=caps, namespace=namespace
    )


#: What a hunt stage keeps of the hunt's report.
REPORT_KEYS = (
    "hunt_id",
    "status",
    "stop_code",
    "fetched",
    "deduped",
    "triaged_out",
    "withheld_protected",
    "extracted",
    "not_relevant",
    "rejected",
    "failed_infra",
    "cards",
    "reader_calls",
    "arxiv_pages",
)


def _report(report):
    if type(report) is not dict:
        return None
    return {key: report.get(key) for key in REPORT_KEYS if key in report}


class _NoRefusal(Exception):
    """Stands in for a hunt module that types no refusal of its own."""


async def _hunt(run, ledger):
    """The hunt, under this campaign's one hunt id. It ends recorded: DONE,
    DONE with `literature_fetch_failed` (arXiv failed; the Planner proceeds),
    or STOPPED with the code that stopped it (the research share, a refusal
    of the hunt's own). A pause, a stop, a provider failure or an unknown
    outcome propagates, and a resume continues the same hunt."""
    done = run.stages.finished(HUNT)
    if done is not None:
        return done
    run.stages.start(HUNT)
    run.ledger.checkpoint()
    from carbon.challenge_registry import describe

    from . import hunt as hunts

    reader = MinerReader(
        ledger=ledger,
        owner=run.owner,
        selection=run.selection,
        credential_file=run.prepared.args.api_key_file,
        transport=run.transport,
        role=run.edition.role("reader"),
    )
    challenge = run.challenge
    hunt = run.block["hunt"]
    keywords = {
        "challenge": challenge,
        "discovery": describe(challenge["id"], challenge["version"]),
        "queries": list(hunt["queries"]) or None,
        "max_records": hunt["max_records"],
        "reader": reader,
        "arxiv_opener": run.arxiv_opener,
        "clock": run.clock,
        "checkpoint": run.ledger.checkpoint,
        "hunt_id": run.hunt_id(),
    }
    report, code = None, None
    try:
        if inspect.iscoroutinefunction(hunts.run_hunt):
            report = await hunts.run_hunt(run.library, **keywords)
        else:
            report = await asyncio.to_thread(hunts.run_hunt, run.library, **keywords)
    except getattr(hunts, "HuntRefused", _NoRefusal) as refusal:
        # The hunt refused to start; nothing was fetched or sent.
        code = getattr(refusal, "code", None) or HUNT_QUERY_INVALID
    reached = getattr(ledger, "reached", None)
    if code is not None:
        status = "STOPPED"
    elif reached is not None:
        status, code = "STOPPED", budget.RESEARCH_SHARE_REACHED
    elif type(report) is dict and report.get("failed_infra"):
        status, code = "DONE", LITERATURE_FETCH_FAILED
    elif type(report) is dict and report.get("status") == "STOPPED":
        status = "STOPPED"
        code = report.get("stop_code") or "hunt_stopped"
    else:
        status = "DONE"
    body = {
        "status": status,
        "code": code,
        "share": reached,
        "report": _report(report),
        "private_snapshot_digest": run.library.snapshot(),
    }
    _note_stage_end(run, HUNT, body)
    return run.stages.finish(HUNT, body)


def _finish_arguments(outcome, folder):
    """The arguments of the Planner's accepted `graphite_record_plan` call:
    from the stage's outcome where the loop carries them, else from the
    stage's own journal (the finishing call's intent beside its PLANNED
    result)."""
    if type(outcome.get("arguments")) is dict:
        return outcome["arguments"]
    if "hypotheses" in outcome and "pins_considered" in outcome:
        return {key: outcome[key] for key in ("hypotheses", "pins_considered")}
    for intent in sorted(Path(folder).glob("*-intent.json")):
        value = json.loads(intent.read_bytes())
        result = intent.with_name(intent.name.replace("-intent.json", "-result.json"))
        if (
            value.get("name") == editions.FINISH
            and result.exists()
            and json.loads(result.read_bytes()).get("status") == "PLANNED"
        ):
            return value["arguments"]
    raise ValueError("the planning stage's outcome does not carry its plan")


async def _plan(run, ledger):
    """The Planner, as the research loop's stage `plan` of epoch 1. In FULL
    it spends what is left of the research share after the hunt; when
    nothing is left, its first model call is refused and it stops typed
    `research_share_reached`, having sent nothing."""
    done = run.stages.finished(PLAN)
    if done is not None:
        return done
    run.stages.start(PLAN)
    hunted = run.stages.finished(HUNT)
    role = run.edition.role("planner")
    toolbox = run.toolbox(role, PLAN)
    cards = _LiteratureCards(toolbox.literature)
    curation = run.curation
    challenge = run.challenge

    def validate(arguments):
        try:
            candidate = plans.from_arguments(
                arguments, challenge=challenge, created_by="planner"
            )
        except plans.PlanInvalid as invalid:
            return False, invalid.refusal()
        return plans.validate_plan(candidate, library=cards, curation=curation)

    observation = run.observation(1, None)
    observation["instructions"] = PLANNER_INSTRUCTIONS
    observation["graphite"] = {
        **run.graphite_context("planner"),
        "pins": curation["pins"],
        "banned_cards": len(curation["bans"]),
        "hunt": (hunted or {}).get("report"),
    }
    outcome = None
    try:
        outcome = await run_epoch(
            ledger,
            epoch=1,
            sdk=toolbox,
            initial_observation=observation,
            instructions=role.prompt,
            tools=run.tools(role),
            stage=PLAN,
            finish={
                "tool": editions.FINISH_TOOL,
                "validate": validate,
                "status": "PLANNED",
            },
            **run.engine(PLAN),
        )
    except budget.ResearchShareReached:
        pass
    reached = getattr(ledger, "reached", None)
    if reached is not None or outcome is None:
        body = {
            "status": "STOPPED",
            "code": budget.RESEARCH_SHARE_REACHED,
            "share": reached,
            "plan_digest": None,
            "plan": None,
        }
    elif outcome.get("status") == "PLANNED":
        folder = run.ledger.root / "epoch-1" / PLAN
        plan_doc = plans.from_arguments(
            _finish_arguments(outcome, folder),
            challenge=challenge,
            created_by="planner",
        )
        body = {
            "status": "PLANNED",
            "code": None,
            "plan_digest": run.library.save_plan(plan_doc),
            "plan": plan_doc,
        }
    else:
        body = {
            "status": outcome.get("status"),
            "code": outcome.get("code"),
            "reason": str(outcome.get("reason") or "")[:300] or None,
            "plan_digest": None,
            "plan": None,
        }
    from carbon.development_session.research_report import report

    _note_stage_end(run, PLAN, body)
    report(run.ledger, owner=run.owner)
    return run.stages.finish(PLAN, body)


def _cited(plan_doc):
    """The cards a plan cites, best-ranked hypothesis first, each once, at
    most `LEARNING_CARDS` of them."""
    cards = []
    for item in plan_doc["hypotheses"]:
        for cite in item["cites"]:
            if cite["card_id"] not in cards:
                cards.append(cite["card_id"])
    return cards[:LEARNING_CARDS]


def _learn(run, plan_doc, plan_digest, epoch, result):
    """Record whether the plan's cited cards led to a practised selection in
    this epoch - the miner's own practice outcome, nothing else. Recorded
    once per epoch; a library that refuses the record (a card it no longer
    serves, an outcome it cannot hold) is noted as SKIPPED with its code and
    never stops the campaign: a ranking hint must not hold a submit."""
    if plan_doc is None:
        return
    cards = _cited(plan_doc)
    marker = f"learning-epoch-{epoch}"
    if not cards or run.stages.finished(marker) is not None:
        return
    improved = result.get("status") == "SELECTED"
    evidence = {
        "schema": LEARNING_SCHEMA,
        "outcome_id": digest(
            canonical([run.manifest.get("campaign_id"), epoch, plan_digest])
        ),
        "campaign_id": run.manifest.get("campaign_id"),
        "epoch": epoch,
        "plan_digest": plan_digest,
        "basis": "PRACTISED_SELECTION" if improved else "NO_PRACTISED_SELECTION",
        "signal": "the miner's own practice outcome only",
    }
    body = {"status": "RECORDED", "code": None}
    try:
        # Bound to this Challenge and version: the ranking reads a practice
        # outcome only for the Challenge it was practised on.
        run.library.record_outcome(cards, improved, evidence, challenge=run.challenge)
    except (ValueError, LookupError, OSError) as refusal:
        code = getattr(refusal, "code", None)
        body = {
            "status": "SKIPPED",
            "code": code if type(code) is str else "learning_not_recorded",
        }
    run.stages.finish(
        marker,
        {**body, "cards": cards, "improved": improved, "evidence": evidence},
    )


async def _build(run, plan_doc, plan_digest):
    """The Constructor's epochs, then the campaign's submit, as Carbon's
    autonomous agent runs them (`research_campaign.run_agent`)."""
    from carbon.development_session.research_report import report

    run.stages.start(BUILD)
    role = run.edition.role("constructor")
    ledger, owner = run.ledger, run.owner
    feedback = None
    epoch_cap = (run.manifest.get("ceilings") or {}).get("epochs")
    epochs = (
        campaigns.FINAL_EPOCHS
        if epoch_cap is None
        else campaigns.FINAL_EPOCHS[:epoch_cap]
    )
    ended = "EPOCHS_USED"
    for epoch in epochs:
        ledger.checkpoint()
        saved = ledger.root / ("epoch-" + str(epoch)) / "permitted-final-feedback.json"
        if saved.exists():
            # Evaluated already: never submitted again.
            feedback = json.loads(saved.read_bytes())
            continue
        observation = run.observation(epoch, feedback)
        observation["graphite"] = {
            **run.graphite_context("constructor"),
            "plan": plan_doc,
            "plan_digest": plan_digest,
            "plan_basis": PLAN_BASIS if plan_doc is not None else NO_PLAN_BASIS,
        }
        result = await run_epoch(
            ledger,
            epoch=epoch,
            sdk=run.toolbox(role, BUILD),
            initial_observation=observation,
            instructions=role.prompt,
            tools=run.tools(role),
            stage=None,
            finish=None,
            **run.engine(BUILD),
        )
        report(ledger, owner=owner)
        _learn(run, plan_doc, plan_digest, epoch, result)
        if result["status"] != "SELECTED":
            ended = "NOT_SELECTED"
            break
        feedback, retained = await campaigns.submit_or_retain(
            run.prepared, epoch, result["strategy"]
        )
        if retained is not None:
            # Not evaluated; the frozen candidate stays for a later submit.
            return retained
        if feedback is None:
            ended = "NOT_SUBMITTED"
            break
    run.stages.finish(
        BUILD,
        {"status": "DONE", "code": None, "ended": ended, "plan_digest": plan_digest},
    )
    campaigns._complete(run.prepared)
    return None


def _block(manifest):
    plan = manifest.get("provider") if type(manifest) is dict else None
    block = plan.get("graphite") if type(plan) is dict else None
    if type(plan) is not dict or plan.get("agent") != "graphite" or block is None:
        raise ValueError("not a Graphite miner campaign")
    return plan, block


async def run(prepared, *, transport=None, arxiv_opener=None, clock=None):
    """Run (or resume) a Graphite miner campaign's stages.

    `transport`, `arxiv_opener` and `clock` replace the model provider, the
    arXiv opener and the hunt's clock for deterministic acceptance only;
    every campaign door passes none. Returns None, or - when the validator
    did not evaluate a selected candidate and the Challenge keeps it - that
    refusal's closed code, exactly as `research_campaign.run_agent` does."""
    _, block = _block(prepared.manifest)
    try:
        edition = editions.resolve(block.get("edition"), block.get("edition_digest"))
    except editions.EditionUnknown:
        raise refused(editions.EditionUnknown.code) from None
    editions.check_block(block)
    root = prepared.ledger.root
    launch = frozen_launch(root, block)
    pack = frozen_pack(root, block)
    graphite = _Run(
        prepared=prepared,
        edition=edition,
        block=block,
        launch=launch,
        pack=pack,
        library=open_library(library_root(prepared.args), pack=pack),
        transport=transport,
        arxiv_opener=arxiv_opener,
        clock=clock,
    )
    prepared.ledger.checkpoint()
    plan_doc, plan_digest = launch["plan"], launch["plan_digest"]
    if editions.plans_first(block):
        if block["hunt"] is not None:
            await _hunt(graphite, _research_ledger(graphite, HUNT))
        planned = await _plan(graphite, _research_ledger(graphite, PLAN))
        plan_doc, plan_digest = planned.get("plan"), planned.get("plan_digest")
    if block["mode"] == editions.RESEARCH_MODE:
        campaigns._complete(prepared)
        return None
    return await _build(graphite, plan_doc, plan_digest)


# --- what a campaign view reads ----------------------------------------------


def _spend(operations, namespace):
    spent = dict.fromkeys(budget.SHARE_DIMENSIONS, 0)
    for op in operations:
        if not str(op.get("id", "")).startswith(tuple(namespace)):
            continue
        vector = (
            op.get("actual") if op.get("actual") is not None else op.get("reservation")
        )
        for key in budget.SHARE_DIMENSIONS:
            spent[key] += (vector or {}).get(key, 0)
    return spent


def view(root, *, operations=None):
    """A Graphite campaign's stages and research spend, for a campaign view;
    None for any other campaign. `operations` is the campaign ledger's
    `status(owner)["operations"]`; read from the ledger when omitted."""
    root = Path(root)
    path = root / "campaign-manifest.json"
    if not path.exists():
        return None
    manifest = json.loads(path.read_bytes())
    try:
        _, block = _block(manifest)
    except ValueError:
        return None
    if operations is None:
        from carbon.development_session.research_ledger import CampaignLedger

        operations = CampaignLedger(root).status(owner=manifest["owner"])["operations"]
    stages = Stages(root)
    rows, current = [], None
    for name in stage_sequence(block):
        done = stages.finished(name)
        if done is not None:
            state = "DONE" if done.get("status") in ("DONE", "PLANNED") else "STOPPED"
        else:
            state = "RUNNING" if stages.started(name) else "PENDING"
        rows.append(
            {
                "stage": name,
                "state": state,
                "code": None if done is None else done.get("code"),
            }
        )
        if current is None and done is None:
            current = name
    if (root / "campaign-complete.json").exists():
        current = "complete"
    planned = stages.finished(PLAN)
    hunted = stages.finished(HUNT)
    report = (hunted or {}).get("report") or {}
    full = block["mode"] == editions.FULL_MODE
    return {
        "schema": VIEW_SCHEMA,
        "edition": block["edition"],
        "mode": block["mode"],
        "stage": current,
        "stages": rows,
        "plan_digest": (
            planned.get("plan_digest")
            if planned is not None and planned.get("plan_digest")
            else block["plan_digest"]
        ),
        "research_share": block["research_share"] if full else None,
        "research_spent": _spend(operations, budget.RESEARCH_NAMESPACE),
        "research_cap": (
            budget.share_caps(
                manifest.get("ceilings") or {}, editions.share_fraction(block)
            )
            if full
            else None
        ),
        "hunt": (
            None
            if block["hunt"] is None
            else {
                "extracted": report.get("extracted"),
                "deduped": report.get("deduped"),
                "cost_nanodollars": _spend(operations, (budget.READER_PREFIX,))[
                    "provider_nanodollars"
                ],
            }
        ),
    }
