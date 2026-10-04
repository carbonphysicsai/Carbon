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
  the Planner runs first - and then the Constructor's epochs, whose selection
  goes through `research_campaign.submit_candidate` to the Challenge's
  validator, as Carbon's autonomous agent's does.
- FULL (the default): RESEARCH's stages under the miner's research share of
  the provider ceilings (`budget.StageLedger`; a stage that reaches it stops
  typed `research_share_reached`), then BUILD.

**Stages** are recorded write-once under `<campaign>/graphite/stages/`; a
finished stage is never run again, so a resume makes no hunt, no arXiv and no
model call for it. The Planner runs as the research loop's stage `plan` of
epoch 1 (`epoch-1/plan/`, identities `epoch-1-plan-*`); the Constructor runs
the campaign's epochs as the autonomous agent does (`epoch-N/`), which the
campaign's submit reads. Every role runs under `edition.agent_policy()` with
its frozen prompt and its stage's tools, the campaign's frozen parallel-call,
miner-guidance and research-tools rules, its frozen limits
(`LIMITS_V2`) and compaction rule, and the miner's model selection and key.

**Frozen inputs.** The launch's curation (pins and bans) and its chosen plan
are written once beside the manifest at the first preparation
(`freeze_launch`), bound to the frozen block by digest. The shared card pack
is checked against its frozen digest (`literature_pack_missing` otherwise),
and an edition this code does not publish is refused
`graphite_edition_unknown` - both before any model call.

**Learning.** After each Constructor epoch, the cards its plan cited are
recorded in the miner's library as having led to a practised selection or
not (`MinerLibrary.record_outcome`). The signal is the miner's own practice
outcome only; no evaluation feedback, score or hidden-test condition is read
for it.
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


def open_library(path):
    from .library import MinerLibrary

    return MinerLibrary(Path(path))


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


def freeze_launch(args, root, *, challenge):
    """At a Graphite campaign's first preparation: the `graphite` block its
    provider plan freezes (`edition.graphite_block`).

    Validates the miner's launch fields (`args.graphite`), reads the miner's
    library once - its curation, its private snapshot and the chosen plan,
    which must be this Challenge's and pass `plan.validate_plan` - and writes
    that curation and plan once beside the manifest (`launch.json`), bound to
    the block by digest. Refused by closed code (`OperationRefused`)."""
    from .pack import SHARED_PACK_DIGEST

    try:
        fields = editions.launch_fields(getattr(args, "graphite", None))
    except editions.LaunchRefused as refusal:
        raise refused(refusal.code) from None
    library = open_library(library_root(args))
    curation = _curation(library.curation())
    plan_doc = None
    if fields["plan"] is not None:
        plan_doc = _library_plan(library, fields["plan"])
        if (plan_doc.get("challenge") or {}).get("id") != challenge["id"]:
            raise refused(plans.PLAN_INVALID)
        ok, refusal = plans.validate_plan(plan_doc, library=library, curation=curation)
        if not ok:
            raise refused(refusal["code"])
    block = editions.graphite_block(
        fields,
        curation_digest=curation["digest"],
        pack_digest=SHARED_PACK_DIGEST,
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
    """The shared card pack, frozen into the campaign root and checked against
    the digest the campaign froze; `literature_pack_missing` otherwise."""
    from . import pack as packs

    want = block["literature"]["pack_digest"]
    try:
        copied = packs.freeze_into(Path(root))
        shared = packs.load_shared_pack()
    except (OSError, ValueError, KeyError):
        raise refused("literature_pack_missing") from None
    if copied != want or getattr(shared, "digest", None) != want:
        raise refused("literature_pack_missing")
    return shared


# --- stage records -----------------------------------------------------------


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
    hunt = [HUNT] if block["hunt"] is not None else []
    if block["mode"] == editions.RESEARCH_MODE:
        return [*hunt, PLAN]
    if block["mode"] == editions.FULL_MODE:
        return [*hunt, PLAN, BUILD]
    return ([] if block["plan_digest"] is not None else [PLAN]) + [BUILD]


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
    """The hunt's `reader`: one closed, tool-less extraction or triage call
    on the miner's model selection, metered against the campaign ledger
    (the research share's, in FULL).

    `prompts` are the edition's Reader prompts (`extract`, `triage`), the
    only instructions a Reader call may carry. A request is the closed
    research request (`research_agent.request_model`), or a part of one -
    `{input, instructions?, task?}` - which `complete` fills from the
    selection. Its identity is `graphite-reader-` and its digest, so the same
    paper's request is one call: a resume, or a hunt that meets it again,
    replays the journalled reply and never pays twice."""

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

        closed = self.complete(request)
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
        from .library import MinerLiterature

        return MinerLiterature(
            self.pack,
            self.library,
            challenge=self.challenge,
            private_snapshot_digest=self.snapshot(),
            curation=self.curation,
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


def _share_ledger(run):
    """The research stages' ledger: FULL's share of the provider ceilings,
    or - in RESEARCH, and for a BUILD whose Planner runs first - the campaign
    ledger's own ceilings alone."""
    if run.block["mode"] != editions.FULL_MODE:
        return budget.StageLedger(run.ledger, owner=run.owner, caps={})
    caps = budget.share_caps(
        run.manifest.get("ceilings") or {}, editions.share_fraction(run.block)
    )
    return budget.StageLedger(run.ledger, owner=run.owner, caps=caps)


def _report(report):
    if type(report) is not dict:
        return None
    keys = ("fetched", "deduped", "triaged_out", "extracted", "failed_infra", "cards")
    return {key: report.get(key) for key in keys if key in report}


async def _hunt(run, ledger):
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
    }
    report = None
    try:
        if inspect.iscoroutinefunction(hunts.run_hunt):
            report = await hunts.run_hunt(run.library, **keywords)
        else:
            report = await asyncio.to_thread(hunts.run_hunt, run.library, **keywords)
    except budget.ResearchShareReached:
        pass
    reached = getattr(ledger, "reached", None)
    if reached is not None:
        status, code = "STOPPED", budget.RESEARCH_SHARE_REACHED
    elif type(report) is dict and report.get("failed_infra"):
        status, code = "DONE", LITERATURE_FETCH_FAILED
    else:
        status, code = "DONE", None
    return run.stages.finish(
        HUNT,
        {
            "status": status,
            "code": code,
            "share": reached,
            "report": _report(report),
            "private_snapshot_digest": run.library.snapshot(),
        },
    )


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
    """The Planner, as the research loop's stage `plan` of epoch 1."""
    done = run.stages.finished(PLAN)
    if done is not None:
        return done
    run.stages.start(PLAN)
    hunted = run.stages.finished(HUNT)
    if hunted is not None and hunted.get("code") == budget.RESEARCH_SHARE_REACHED:
        # The share is spent: the Planner's first call would be refused too.
        return run.stages.finish(
            PLAN,
            {
                "status": "STOPPED",
                "code": budget.RESEARCH_SHARE_REACHED,
                "share": hunted.get("share"),
                "plan_digest": None,
                "plan": None,
            },
        )
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

    report(run.ledger, owner=run.owner)
    return run.stages.finish(PLAN, body)


def _learn(run, plan_doc, plan_digest, epoch, result):
    """Record whether the plan's cited cards led to a practised selection in
    this epoch - the miner's own practice outcome, nothing else."""
    if plan_doc is None:
        return
    cards = sorted(
        {cite["card_id"] for item in plan_doc["hypotheses"] for cite in item["cites"]}
    )
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
    run.library.record_outcome(cards, improved, evidence)
    run.stages.finish(
        marker,
        {
            "status": "RECORDED",
            "cards": cards,
            "improved": improved,
            "evidence": evidence,
        },
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
        library=open_library(library_root(prepared.args)),
        transport=transport,
        arxiv_opener=arxiv_opener,
        clock=clock,
    )
    prepared.ledger.checkpoint()
    mode = block["mode"]
    plan_doc, plan_digest = launch["plan"], launch["plan_digest"]
    if mode in (editions.RESEARCH_MODE, editions.FULL_MODE):
        research = _share_ledger(graphite)
        if block["hunt"] is not None:
            await _hunt(graphite, research)
        planned = await _plan(graphite, research)
        plan_doc, plan_digest = planned.get("plan"), planned.get("plan_digest")
        if mode == editions.RESEARCH_MODE:
            campaigns._complete(prepared)
            return None
    elif plan_doc is None:
        planned = await _plan(graphite, _share_ledger(graphite))
        plan_doc, plan_digest = planned.get("plan"), planned.get("plan_digest")
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
