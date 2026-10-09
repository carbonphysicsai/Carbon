"""A battery campaign: the shared campaign machinery bound to battery.

`research_campaign.prepare` routes here when the frozen manifest (or the
launch) names the battery Challenge. The shared machinery is used unchanged:
- the verified images and the host doctor;
- the host's research images: authored Julia for `run_julia`, declared and
  frozen or used anytime, exactly as in a Burgers product campaign. They are
  research tools only; evaluation, submission and reconstruction never read
  them. GPU research is not composed: its scope binds Burgers material;
- the registered hotkey and the signed local transport;
- the campaign ledger, its budget and the ownership lock;
- the research SDK and the twelve operations;
- freeze and submit.

Only the Challenge-specific parts differ:
- the composition (`research.make_battery_research_service`);
- a gateway that authenticates battery requests;
- the validator daemon a submission reaches (`deployment`), the same one
  every battery submitter reaches.

The Burgers steps that do not apply are absent rather than stubbed: private
role generation, committed final-exam seeds and the C-04/C-05 final epoch.

Who selects:
- ``none``: the miner drives practice, freeze and submit;
- ``autonomous``: Carbon's research agent, under the autonomous policy with the
  Challenge-neutral prompt, observing battery's own discovery document. It has
  exactly the miner's capabilities - the same twelve operations, the same
  freeze and the same signed submission to the validator daemon - and no
  evaluator access. It is a paid campaign, so it needs the model-provider
  credential and a finite provider budget in the frozen manifest; its run plan
  (model, calls and trials per epoch, epochs) is recorded there too.
- ``graphite``: Graphite's miner edition (OWNER-GRAPHITE-MINER-01), on the
  same terms - the miner's capabilities, freeze and signed submission, no
  evaluator access, a finite provider budget - with its frozen `graphite`
  block (`graphite_plan`) and the miner's library read once at launch.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace

# What an agent campaign must cap before any model call (`AGENT_BUDGET_KEYS`):
# the miner's (or operator's) own ceilings, never a default supplied here. The
# registry's one definition and predicate, which the launch doors read too
# (LA-F4).
from carbon.challenge_registry.agent_plan import (
    AGENT_BUDGET_KEYS,
    CeilingsRequired,
    finite_ceilings,
)

from .challenge import CHALLENGE

REPOSITORY = Path(__file__).resolve().parents[2]
SELECTION = {
    "rule": "the miner freezes one practiced recipe per submission epoch",
    "evidence_required": "a completed battery practice of the same recipe",
}
REPLICAS = {
    "reconstructions_per_submission": 1,
    "seed": "Carbon-derived from the evaluation deployment's private root",
}


def provider_plan(agent, budget, selection=None, graphite=None):
    """The finite run plan a battery campaign freezes in its manifest.

    `selection` is the miner's model selection; the pinned default records the
    plan exactly as before selection existed, any other adds its record.

    `graphite` is the frozen block of a Graphite miner-edition campaign
    (`carbon.agent_campaign.graphite.miner.driver.freeze_launch`), given only
    with `agent="graphite"` (`graphite_plan`)."""
    if agent == "none":
        from carbon.development_session.research_tools import (
            ARGUMENT_NORMALISATION_V2,
        )

        # The miner's own agent calls the miner MCP door, which reads this
        # rule too (AGENT-DOOR-USABILITY-01 A1): a new plan freezes v2. A
        # plan frozen before names none and replays unchanged.
        return {
            "agent": "none",
            "model_calls": 0,
            "argument_normalisation": ARGUMENT_NORMALISATION_V2,
        }
    if agent == "graphite":
        return graphite_plan(budget, selection, graphite)
    if graphite is not None:
        raise ValueError("only a Graphite campaign freezes a Graphite block")
    from carbon.development_session import miner_guidance
    from carbon.development_session.model_provider import (
        DEFAULT_SELECTION,
        check_budget,
    )
    from carbon.development_session.research_agent_policy import (
        AUTONOMOUS,
        PARALLEL_CALLS_V2,
    )
    from carbon.development_session.research_campaign import FINAL_EPOCHS
    from carbon.development_session.research_tools import (
        ARGUMENT_NORMALISATION_V2,
        TOOLS_RULE,
    )

    ceilings = (budget or {}).get("ceilings") or {}
    if any(type(ceilings.get(k)) is not int for k in AGENT_BUDGET_KEYS):
        raise ValueError(
            "an autonomous battery campaign needs finite provider_attempts and "
            "provider_nanodollars ceilings"
        )
    selection = DEFAULT_SELECTION if selection is None else selection
    # A spend ceiling in money needs a price to enforce it against.
    check_budget(selection, ceilings)
    plan = {
        "agent": "autonomous",
        "policy": AUTONOMOUS,
        "model": selection.model_id,
        "epochs": len(FINAL_EPOCHS),
        "max_provider_calls_per_epoch": 48,
        "max_research_trials_per_epoch": 8,
        "ceilings": {k: ceilings[k] for k in AGENT_BUDGET_KEYS},
        "evaluator_access": False,
        # Frozen with the plan: every tool call of a turn runs, in the model's
        # order (`PARALLEL_CALLS_V2`, OWNER-LAUNCHPAD-PROD-01, LP-PROD-A). A
        # plan frozen earlier keeps its own rule (`PARALLEL_CALLS`: the first
        # call runs and the rest are refused) and replays unchanged.
        "parallel_calls": PARALLEL_CALLS_V2,
        # Frozen with the plan (RSURF-D13): the agent reads the miner's
        # Conversation messages at each step as recorded guidance. A plan
        # frozen before the amendment has no rule and reads none.
        "miner_guidance": miner_guidance.RULE,
        # Frozen with the plan (LP-PROD-D, wired by OWNER-LAUNCHPAD-PROD-01):
        # the v2 research tools text, read_file's text-once result
        # (`content_utf8`) and the agent's `research_environment`. A plan
        # frozen earlier names no rule, keeps the historical tools, reads and
        # observation byte for byte, and replays unchanged.
        "research_tools": TOOLS_RULE,
        # Frozen with a new plan (AGENT-DOOR-USABILITY-01 A1): a practice
        # call's action and arguments_json "null" read as JSON null, as in
        # a Graphite plan. A plan frozen before names no rule and replays
        # unchanged.
        "argument_normalisation": ARGUMENT_NORMALISATION_V2,
    }
    if not selection.is_historical_default:
        plan["model_selection"] = selection.record()
    return plan


def graphite_plan(budget, selection, graphite):
    """The run plan a Graphite miner-edition battery campaign freezes
    (OWNER-GRAPHITE-MINER-01).

    Everything an autonomous plan freezes - finite provider ceilings, the
    model selection, `PARALLEL_CALLS_V2`, the miner-guidance rule and the
    research tools rule, no evaluator access - with the argument
    normalisation rule (LP-PROD-FIX-01), the miner edition's
    policy and its `graphite` block (edition and its digest, mode, research
    share, plan, hunt, curation and literature digests, the miner's limits,
    no escalation), and the engine's limits (`LIMITS_V2`) for the Planner
    and the Constructor and its compaction rule (`COMPACTION_V1`). There is
    no per-epoch call or trial count unless the miner set one: the miner's
    own ceilings bind.

    A FULL plan whose research share cannot pay for one research model call
    on the selection is refused `research_share_too_small`
    (`driver.check_research_share`): its research would send nothing."""
    from carbon.agent_campaign.graphite.miner import driver, edition
    from carbon.development_session import miner_guidance
    from carbon.development_session.model_provider import (
        DEFAULT_SELECTION,
        check_budget,
    )
    from carbon.development_session.research_agent_policy import PARALLEL_CALLS_V2
    from carbon.development_session.research_campaign import FINAL_EPOCHS
    from carbon.development_session.research_tools import (
        ARGUMENT_NORMALISATION_V2,
        TOOLS_RULE,
    )

    # The launch doors' own predicate (LA-F4): admission refuses a launch
    # without these, by code, before it is queued; one that still reaches
    # here is typed, so its interruption carries the code.
    if not finite_ceilings(budget):
        raise CeilingsRequired(
            "a Graphite battery campaign needs finite provider_attempts and "
            "provider_nanodollars ceilings"
        )
    ceilings = budget["ceilings"]
    if graphite is None:
        raise ValueError("a Graphite plan freezes its launch block")
    block = edition.check_block(graphite)
    edition.resolve(block["edition"], block["edition_digest"])
    selection = DEFAULT_SELECTION if selection is None else selection
    check_budget(selection, ceilings)
    driver.check_research_share(block, ceilings, selection)
    limits = block["limits"]
    plan = {
        "agent": "graphite",
        "policy": edition.agent_policy(),
        "model": selection.model_id,
        "epochs": len(FINAL_EPOCHS),
        "ceilings": {k: ceilings[k] for k in AGENT_BUDGET_KEYS},
        "evaluator_access": False,
        "parallel_calls": PARALLEL_CALLS_V2,
        "miner_guidance": miner_guidance.RULE,
        "research_tools": TOOLS_RULE,
        # Frozen with a new Graphite plan (LP-PROD-FIX-01): a workspace
        # call's strategy_json "null" reads as JSON null. A plan frozen
        # earlier names no rule, refuses it as before and replays unchanged.
        # Since AGENT-DOOR-USABILITY-01 every new plan freezes v2. v2 (RESEARCH-TOOL-USABILITY-01) also reads a practice call's action
        # and arguments_json "null" as JSON null; a plan that froze v1 keeps
        # v1.
        "argument_normalisation": ARGUMENT_NORMALISATION_V2,
        "limits": {
            "plan": edition.limits_rule(
                limits.get("planner_calls"), limits.get("trials_per_epoch")
            ),
            "build": edition.limits_rule(
                limits.get("calls_per_epoch"), limits.get("trials_per_epoch")
            ),
        },
        "compaction": edition.compaction_rule(),
        "graphite": block,
    }
    if not selection.is_historical_default:
        plan["model_selection"] = selection.record()
    window = getattr(selection, "input_window", None)
    if window is not None:
        # How the window was chosen (OWNER-GRAPHITE-MINER-INPUT-WINDOW-01):
        # the published context it came from and any bound that applied, or
        # that Carbon records none. A plan frozen before has no record.
        plan["input_window"] = window
    return plan


def _agent_policies(agent):
    """The loop policies a battery agent campaign is prepared under. Every
    Launchpad agent campaign is prepared under the autonomous policy; a
    Graphite campaign's roles run under the miner edition's own policy
    (`edition.AGENT_POLICY`), which its frozen plan records, so a door may
    name either."""
    from carbon.development_session.research_agent_policy import AUTONOMOUS

    if agent == "graphite":
        from carbon.agent_campaign.graphite.miner.edition import AGENT_POLICY

        return (AUTONOMOUS, AGENT_POLICY)
    return (AUTONOMOUS,)


def plan_selection(args, plan):
    """The model selection a frozen battery run plan records."""
    from carbon.development_session.model_provider import DEFAULT_SELECTION
    from carbon.development_session.research_campaign import resolve_selection

    record = plan.get("model_selection")
    if record is None:
        if plan.get("model") != DEFAULT_SELECTION.model_id:
            raise ValueError("the frozen battery run plan names no usable model")
        record = DEFAULT_SELECTION.manifest_record()
    return resolve_selection(args, record)


def campaign_challenge(args):
    """The Challenge a campaign is bound to; see `challenge_registry.campaigns`."""
    from carbon.challenge_registry.campaigns import campaign_challenge

    return campaign_challenge(args)


#: What Carbon's agent sees of the prior epoch's evaluation, as a ladder of
#: allow-lists (v2 section 7, the leak ladder; amendment 4). FULL is the
#: daemon's allow-listed outcome. SCORE_WITHHELD is the pre-registered control
#: arm (docs/development/BATTERY_AGENT_CAMPAIGN_PREREGISTRATION.md section 2):
#: admissibility and failed gate names, no score. ELIGIBILITY_ONLY drops the
#: gate names too; AGGREGATE_SCORE adds back the two aggregate scores only.
FEEDBACK_FULL, FEEDBACK_SCORE_WITHHELD = "FULL", "SCORE_WITHHELD"
FEEDBACK_ELIGIBILITY_ONLY, FEEDBACK_AGGREGATE_SCORE = (
    "ELIGIBILITY_ONLY",
    "AGGREGATE_SCORE",
)
FEEDBACK_MODES = (
    FEEDBACK_FULL,
    FEEDBACK_SCORE_WITHHELD,
    FEEDBACK_ELIGIBILITY_ONLY,
    FEEDBACK_AGGREGATE_SCORE,
)

#: Every restricted view is an allow-list: a field added to the outcome later
#: is withheld by default, never shown by accident.
_WITHHELD_OUTCOME_FIELDS = (
    "schema",
    "submission_id",
    "challenge",
    "state",
    "evidence",
    "rule",
    "qualification",
    "reward",
    "failure",
    "recipe_digest",
    "contract_digest",
    "reconstruction",
)
#: The screening fields each restricted rung shows, lowest rung first.
_SCREENING_FIELDS = {
    FEEDBACK_ELIGIBILITY_ONLY: ("eligible",),
    FEEDBACK_SCORE_WITHHELD: ("eligible", "gates_failed"),
    FEEDBACK_AGGREGATE_SCORE: ("eligible", "gates_failed", "score", "important_score"),
}
_WITHHELD_SCREENING_FIELDS = _SCREENING_FIELDS[FEEDBACK_SCORE_WITHHELD]
_WITHHELD_NOTE = {
    FEEDBACK_ELIGIBILITY_ONLY: (
        "failed gate names, scores, case counts, pool version, nomination and finals"
    ),
    FEEDBACK_SCORE_WITHHELD: "scores, case counts, pool version, nomination and finals",
    FEEDBACK_AGGREGATE_SCORE: "case counts, pool version, nomination and finals",
}


def feedback_mode(value):
    """A frozen campaign's feedback mode; anything else is refused by name."""
    if value not in FEEDBACK_MODES:
        raise ValueError(f"unknown battery feedback mode: {value!r}")
    return value


def restricted_feedback(feedback, mode):
    """The prior epoch's feedback as one restricted rung of the ladder shows it.

    Kept: the outcome's allow-listed identity and state fields, and only the
    screening fields that rung allows. FULL is not a restricted rung."""
    fields = _SCREENING_FIELDS[feedback_mode(mode)]
    outcome = feedback["outcome"]
    shown = {k: outcome[k] for k in _WITHHELD_OUTCOME_FIELDS if k in outcome}
    if isinstance(outcome.get("screening"), dict):
        shown["screening"] = {
            k: outcome["screening"][k] for k in fields if k in outcome["screening"]
        }
    return {
        "schema": feedback["schema"],
        "epoch": feedback["epoch"],
        "outcome": shown,
        "official_eligible": feedback["official_eligible"],
        "reward": feedback["reward"],
        "feedback_mode": mode,
        "withheld": _WITHHELD_NOTE[mode],
    }


def withheld_feedback(feedback):
    """The prior epoch's feedback with every score-bearing value removed.

    Kept: whether the submission was admitted and eligible, and the names of
    any gates it failed. Removed: the pool score, the important-region score,
    case counts, the pool version, nomination and finals.
    """
    return restricted_feedback(feedback, FEEDBACK_SCORE_WITHHELD)


def permitted_feedback(feedback, mode):
    """What the agent may see of the prior epoch's evaluation under `mode`."""
    if feedback is None or feedback_mode(mode) == FEEDBACK_FULL:
        return feedback
    return restricted_feedback(feedback, mode)


def manifest_document(
    product,
    *,
    owner,
    implementation,
    images,
    selection=None,
    feedback=FEEDBACK_FULL,
    graphite=None,
    construction_level=None,
):
    from carbon.development_session.research_ledger import VERSION
    from carbon.reconstruction.capability_registry import contract_digest

    from .research import SCAFFOLD, objective

    return {
        "schema": VERSION,
        "campaign_id": product.campaign_id,
        "authority": "OWNER-BATTERY-TESTNET-01",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "owner": owner,
        "implementation": implementation,
        "objective": objective(),
        "contract_digest": contract_digest(CHALLENGE.challenge_id),
        "sampling": {"practice": "200 public PRACTICE cases, fixed"},
        "control": SCAFFOLD,
        "selection": SELECTION,
        "replica_policy": REPLICAS,
        "provider": provider_plan(
            product.agent,
            product.budget,
            selection,
            **({} if graphite is None else {"graphite": graphite}),
        ),
        "images": images,
        "new_network_transactions": 0,
        "feedback_mode": feedback_mode(feedback),
        **product.manifest_fields(),
        # A launch at a construction level (LAUNCHPAD-LEVELS-01 S2): the
        # level's registered variant, frozen by name and digest. Level 0
        # records nothing, so its manifest is what it was.
        **(
            {"construction_level": dict(construction_level)}
            if construction_level
            else {}
        ),
    }


async def prepare_battery(args, *, ledger=None, campaign):
    from carbon.chain.external_signer import miner_signer
    from carbon.chain.models import CARBON_NETUID
    from carbon.compute.retired import refuse_rented
    from carbon.development_session.data import write_once
    from carbon.development_session.miner_network import binding_for
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_campaign import (
        PreparedCampaign,
        accepted_implementation,
        private_file,
        requester,
        verify_current_worker,
    )
    from carbon.development_session.research_image import (
        load_analysis_image,
        verify_image,
    )
    from carbon.development_session.research_ledger import CampaignLedger
    from carbon.development_session.research_report import report
    from carbon.development_session.research_tools import ResearchMinerTools
    from carbon.development_session.service import LocalMinerConnection
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity

    root = args.root
    manifest_path = root / "campaign-manifest.json"
    if args.command == "run" and manifest_path.exists():
        raise ValueError("campaign already exists; use resume")
    if args.command == "resume" and not manifest_path.exists():
        raise ValueError("no frozen campaign to resume")
    frozen = json.loads(manifest_path.read_bytes()) if manifest_path.exists() else None
    product = getattr(args, "product", None)
    if frozen is None and product is None:
        raise ValueError("a battery campaign is a product campaign")
    # A campaign frozen for the retired rented GPU is refused by name before
    # anything is opened or reached (OWNER-MINER-COMPUTE-LINK-ONLY-01).
    refuse_rented(frozen.get("runtime") if frozen is not None else product.runtime)
    ledger = ledger if ledger is not None else CampaignLedger(root)
    if ledger.root != root or ledger.admission is not None:
        raise ValueError("a battery campaign never consumes a development grant")
    agent = frozen["agent"] if frozen is not None else product.agent
    selection = None
    graphite = None
    if agent != "none":
        from carbon.development_session.agent import ResponsesTransport
        from carbon.development_session.model_provider import SelectionTransport
        from carbon.development_session.research_campaign import (
            new_plan_input_default,
            new_plan_output_default,
            supplied_selection,
        )

        if getattr(args, "agent_policy", None) not in _agent_policies(agent):
            raise ValueError("a battery agent runs only under the autonomous policy")
        if frozen is None:
            # A new plan: its agent's output cap defaults to the selected
            # model's own maximum, unless the miner set one
            # (OWNER-LAUNCHPAD-PROD-02), and a Graphite plan's input window
            # to the model's published context less that cap, unless the
            # miner set one (OWNER-GRAPHITE-MINER-INPUT-WINDOW-01). The plan
            # records what it chose.
            selection = supplied_selection(
                args,
                output_default=new_plan_output_default(args),
                input_default=new_plan_input_default(args, agent),
            )
            if agent == "graphite":
                # The miner's launch fields and library, read once and frozen
                # with the plan (OWNER-GRAPHITE-MINER-01).
                from carbon.agent_campaign.graphite.miner.driver import (
                    freeze_launch,
                )

                graphite = freeze_launch(
                    args,
                    root,
                    challenge={
                        "id": CHALLENGE.challenge_id,
                        "version": CHALLENGE.version,
                    },
                )
            plan = provider_plan(
                agent,
                product.budget,
                selection,
                **({} if graphite is None else {"graphite": graphite}),
            )
        else:
            plan = frozen["provider"]
            selection = plan_selection(args, plan)
        if plan.get("agent") != agent or plan.get("evaluator_access"):
            raise ValueError("the frozen battery agent plan is not runnable")
        private_file(args.api_key_file)
        if selection.is_historical_default:
            ResponsesTransport(args.api_key_file)
        else:
            SelectionTransport(selection)
    implementation = accepted_implementation(args.accepted_revision)
    image = load_image_identity(args.image_manifest)
    verify_current_worker(image, implementation)
    if not doctor(image_id=image.image_id, image_identity=image).eligible:
        raise ValueError("accepted numerical host unavailable")
    analysis = load_analysis_image(args.analysis_image_manifest)
    verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise ValueError("analysis/trusted image parent differs")
    declared = frozen["runtime"] if frozen is not None else product.runtime
    julia_image = host_julia_image(root, declared, analysis)
    gpu_image = host_gpu_image(root, declared)
    runtime = research_runtime(
        declared,
        implementation=implementation,
        images=[image.image_id, analysis.image_id],
        julia_image=julia_image,
        gpu_image=gpu_image,
    )
    if declared != runtime:
        raise ValueError("configured runtime differs from the battery runtime")
    # Practice on the miner's own remote setup, when the runtime declares it:
    # built by battery's campaign from the profile's machine, and refused
    # before anything is reached when it differs from the frozen transport
    # (OWNER-MINER-COMPUTE-LINK-ONLY-01).
    remote = None
    if "remote_gpu" in runtime:
        remote = _own_campaign(campaign).remote_runner(
            runtime, getattr(args, "remote_machine", None), gpu_image
        )
    # The operator configuration where an operator runs one, otherwise the
    # miner's own network file (C-MLP-04): the chain context and publisher.
    config = binding_for(args)
    public = json.loads(private_file(args.miner_public).read_bytes())
    if public["netuid"] != CARBON_NETUID or config.netuid != CARBON_NETUID:
        raise ValueError(f"existing subnet {CARBON_NETUID} context required")
    registered = (
        frozen["admission"]["hotkey"]
        if frozen is not None
        else str(product.miner.hotkey)
    )
    if public["hotkey"] != registered:
        raise ValueError("the registered miner differs from this hotkey")
    # The miner's own signer holds the hotkey; Carbon only reaches it.
    key = miner_signer(public, getattr(args, "signer_socket", None))
    session = root / "research-auth"
    session.mkdir(mode=0o700, exist_ok=True)
    connection = LocalMinerConnection(
        session, args.image_manifest, config.context, config.publisher_hotkey, key
    )
    owner = await requester(connection)
    if (root / "campaign-complete.json").exists():
        report(ledger, owner=owner)
        return None
    if frozen is None:
        manifest = manifest_document(
            product,
            owner=owner,
            implementation=implementation,
            images=runtime["images"],
            selection=selection,
            feedback=getattr(args, "feedback_mode", FEEDBACK_FULL),
            graphite=graphite,
            construction_level=getattr(args, "construction_level", None),
        )
        write_once(manifest_path, canonical(manifest))
    else:
        manifest = frozen
        if manifest.get("owner") != owner:
            raise ValueError("battery campaign owner changed")
        check_attached(
            manifest,
            implementation=implementation,
            images=runtime["images"],
            julia_image=julia_image,
            gpu_image=gpu_image,
        )
    ledger.freeze(manifest)
    composition = None
    try:
        composition, wrapper = compose(
            ledger=ledger,
            owner=owner,
            image=image,
            analysis=analysis,
            connection=connection,
            julia_image=julia_image,
            gpu_image=gpu_image,
            remote=remote,
        )
        sdk = ResearchMinerTools(
            connection=connection,
            wrapper=wrapper,
            composition=composition,
            ledger=ledger,
            owner=owner,
        )
    except BaseException:
        if composition is not None:
            composition.tasks.close()
        report(ledger, owner=owner)
        raise
    return PreparedCampaign(
        args=args,
        ledger=ledger,
        owner=owner,
        manifest=manifest,
        seeds=None,
        role_root=None,
        data=None,
        image=image,
        key=key,
        config=config,
        composition=composition,
        sdk=sdk,
        task=None,
        grant=None,
        agent_policy=getattr(args, "agent_policy", None),
        campaign=campaign,
        challenge=CHALLENGE,
        selection=selection,
    )


def _frozen_level(root):
    """The frozen manifest's construction-level binding, or None."""
    from carbon.development_session.construction_level import binding

    path = Path(root) / "campaign-manifest.json"
    return binding(json.loads(path.read_bytes())) if path.exists() else None


def compose(
    *,
    ledger,
    owner,
    image,
    analysis,
    connection,
    demand=None,
    cleanup_only=False,
    julia_image=None,
    runner=None,
    backend=None,
    gpu_image=None,
    remote=None,
):
    """The battery composition and the wrapper that authenticates for it.

    `julia_image` is the host's authored Julia image, verified by the caller
    (`host_julia_image`), or None. It reaches only the research executor's
    `run_julia`; practice, the recipe compiler, discovery and submission are
    composed identically with or without it.

    `remote` is the campaign's practice runner on the miner's own remote
    setup (`ChallengeCampaign.remote_runner`), or None. It changes only where
    GPU practice runs, never what it scores.

    The gateway is the connection's own: the same chain context, publisher,
    observed registration, verifier and receipt journal. Only its Challenge
    differs, so a battery request is authenticated as battery and a request
    naming any other Challenge is refused before it reaches a provider.
    """
    from carbon.miner_mcp.research import AuthenticatedResearchService
    from carbon.transport.gateway import AuthenticatedGateway

    from .research import BatteryPractice, make_battery_research_service

    # A campaign launched at a construction level compiles at it, whichever
    # door composes it (its own run or an attachment): read from its frozen
    # manifest (LAUNCHPAD-LEVELS-01 S2).
    level = _frozen_level(ledger.root)
    # `runner`/`backend` exist for tests; every campaign door passes neither,
    # so practice runs in the isolated carrier and says so.
    practice = BatteryPractice(
        level=level,
        ledger=ledger,
        owner=owner,
        image=image,
        root=REPOSITORY,
        runner=runner,
        backend=backend,
        gpu_image=gpu_image,
        remote=remote,
    )
    composition = make_battery_research_service(
        root=ledger.root / "research-tasks",
        ledger=ledger,
        owner=owner,
        image=analysis,
        practice=practice,
        demand=demand,
        cleanup_only=cleanup_only,
        julia_image=julia_image,
    )
    if gpu_image is not None:
        # The code cell's GPU lane (RSURF-D20): the same pinned GPU worker and,
        # when the runtime declares it, the same remote route as practice.
        from carbon.development_session.gpu_code_cell import GpuLane

        composition.executor.gpu = GpuLane(image=gpu_image, remote=remote)
    base = connection.service.gateway
    gateway = AuthenticatedGateway(
        base.context,
        CHALLENGE,
        base.receiver,
        base.adapter,
        base.verifier,
        base.journal,
        clock_ns=base.clock_ns,
    )
    return composition, AuthenticatedResearchService(
        gateway, {owner: composition.service}
    )


#: A battery runtime may name these keys and no others. `gpu_research` is
#: battery's own GPU practice scope (`carbon.development_session.battery_gpu`, C-MLP-03 slice 3);
#: Burgers' GPU scope binds Burgers material and is refused by its schema.
#: `remote_gpu` runs that GPU practice on the miner's own remote machine or
#: container (`carbon.compute.remote_route`, OWNER-MINER-COMPUTE-LINK-ONLY-01).
#: `rented_gpu` is retired and refused by name before a runtime is composed.
RUNTIME_KEYS = frozenset(
    {"implementation", "images", "authored_research", "gpu_research", "remote_gpu"}
)


def _own_campaign(campaign):
    """Battery's `ChallengeCampaign`: the one the research path passed, or
    the registry's own."""
    if campaign is not None:
        return campaign
    from carbon.challenge_registry.campaigns import campaign_for_id

    return campaign_for_id(CHALLENGE.challenge_id)


def host_gpu_image(root, declared):
    """The GPU worker image this campaign's runtime declares, verified against
    the record installed in the campaign root; None without GPU practice."""
    from carbon.development_session.battery_gpu import registered_gpu_image

    return registered_gpu_image(root, declared)


def host_julia_image(root, declared, analysis):
    """The authored Julia image the host installed for this campaign, verified.

    The same resolution as a Burgers product campaign: a runtime that declares
    `authored_research` must name exactly the installed record's scope; one
    that does not still gets whichever image the host has installed (anytime
    Julia), which is then not part of the frozen runtime. None when the host
    has no Julia image.
    """
    from carbon.development_session.research_campaign import (
        available_julia_image,
        registered_julia_image,
    )

    if "authored_research" in declared:
        return registered_julia_image(root, declared, analysis)
    return available_julia_image(root, analysis)


def research_runtime(declared, *, implementation, images, julia_image, gpu_image=None):
    """The runtime this host composes for a battery campaign declaring `declared`.

    The research images are research tools only. Nothing here reaches the
    recipe compiler, the contract digest or a submission. A GPU image changes
    only where practice runs, never what it scores.
    """
    extra = set(declared) - RUNTIME_KEYS
    if extra:
        raise ValueError(
            "battery has no research composition for " + ", ".join(sorted(extra))
        )
    runtime = {"implementation": implementation, "images": images}
    if julia_image is not None and "authored_research" in declared:
        from carbon.development_session.julia_analysis import authored_julia_scope

        runtime["authored_research"] = [authored_julia_scope(julia_image)]
    if "gpu_research" in declared:
        from carbon.development_session.battery_gpu import gpu_scope

        if gpu_image is None:
            raise ValueError("a GPU practice runtime needs its installed GPU image")
        runtime["gpu_research"] = [gpu_scope(gpu_image)]
    if "remote_gpu" in declared:
        from carbon.compute.remote_route import declared_remote, remote_scope

        if gpu_image is None:
            raise ValueError("remote GPU practice needs its installed GPU image")
        # The miner's transport, recomposed against this host's GPU worker:
        # the frozen scope must name the worker it actually runs.
        transport = declared_remote(declared)["transport"]
        runtime["remote_gpu"] = [
            remote_scope(CHALLENGE.challenge_id, gpu_image, transport)
        ]
    return runtime


def check_attached(
    manifest, *, implementation, images, julia_image=None, gpu_image=None
):
    """An attach re-checks the frozen battery binding it serves.

    `julia_image` is the host's verified authored Julia image
    (`host_julia_image`) and `gpu_image` its verified GPU worker
    (`host_gpu_image`); the frozen runtime must equal, exactly, the one this
    host composes with them.
    """
    from carbon.reconstruction.capability_registry import contract_digest

    from .research import objective

    expected = {
        "implementation": implementation,
        "images": images,
        "objective": objective(),
        "contract_digest": contract_digest(CHALLENGE.challenge_id),
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise ValueError("battery campaign " + field + " changed")
    frozen = manifest.get("runtime")
    if type(frozen) is not dict or frozen != research_runtime(
        frozen,
        implementation=implementation,
        images=images,
        julia_image=julia_image,
        gpu_image=gpu_image,
    ):
        raise ValueError("campaign runtime differs from the battery runtime")


def is_battery(manifest):
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    return (manifest.get("challenge") or {}).get("id") == BATTERY_CHALLENGE


def evaluation_config(prepared):
    """The operator's validator deployment for this campaign, or None.

    Read from the profile's per-Challenge `validators` (C-MLP-04), or from a
    profile's legacy `battery_validator` path, interpreted as before."""
    found = (getattr(prepared.args, "validators", None) or {}).get(
        CHALLENGE.challenge_id
    )
    return found or getattr(prepared.args, "battery_validator", None)


def _intake(prepared):
    """The validator intake for this Challenge: the profile's per-Challenge
    `intakes` (C-MLP-04), or a legacy `battery_intake`."""
    found = (getattr(prepared.args, "intakes", None) or {}).get(CHALLENGE.challenge_id)
    return found or getattr(prepared.args, "battery_intake", None)


def _receiver(prepared):
    """The receiver hotkey the profile pins for this Challenge's intake
    (`receivers`, LAUNCHPAD-ACCEPT-03), or None for a profile written before
    receivers were pinned, which is not checked."""
    found = (getattr(prepared.args, "receivers", None) or {}).get(
        CHALLENGE.challenge_id
    )
    return found if type(found) is str else None


async def evaluate_candidate(prepared, epoch, record):
    """Submit a frozen battery candidate to the validator daemon (M3).

    The candidate goes the way an external miner's does: a signed
    `battery_submit` message, authenticated by the battery gateway, admitted
    and screened by the operator's `BatteryValidator`. Nothing here scores it.

    Returns the permitted feedback. Raises `OperationRefused` when no
    evaluation happened - no deployment, infrastructure failure, or a queued
    submission - so the epoch is not consumed; resubmitting the same frozen
    candidate is the same admission (idempotent), never a second one.
    """
    import time

    from carbon.development_session import research_tools
    from carbon.development_session.research_campaign import OperationRefused
    from carbon.transport.models import message

    from .daemon import SUBMIT_TOOL, AuthenticatedSubmission
    from .deployment import EvaluationUnavailable, evaluate, validator

    config = evaluation_config(prepared)
    intake = _intake(prepared)
    if config is None and intake is not None:
        # The validator runs elsewhere: submit through its intake, signed by
        # the miner's own signer (C-MLP-03 slice 6).
        return await _evaluate_through_intake(prepared, epoch, record, intake)
    if config is None:
        raise OperationRefused("evaluation_unavailable")
    try:
        target = validator(config, repository=REPOSITORY)
    except EvaluationUnavailable as unavailable:
        raise OperationRefused(unavailable.code) from None
    sdk = prepared.sdk
    gateway = sdk.wrapper.gateway
    snapshot = await sdk.connection.check_registration()
    body = message(
        sdk.connection.chain_context,
        snapshot.snapshot_id,
        gateway.challenge,
        session="carbon-autoresearch",
        request=f"battery-submit-epoch-{epoch}-{time.time_ns()}",
        tool=SUBMIT_TOOL,
        fields={
            "strategy_json": json.dumps(
                record["strategy"], sort_keys=True, separators=(",", ":")
            ),
            # The contract the campaign froze and practiced under; a changed
            # contract is refused at admission, never silently re-bound.
            "contract_digest": record.get("contract_digest")
            or prepared.manifest["contract_digest"],
        },
    )
    headers = research_tools.BittensorMessageSigner(sdk.connection.miner_key).sign(
        body, receiver=sdk.connection.publisher, nonce_ns=time.time_ns()
    )
    received = await gateway.receive(body, headers)
    submission = AuthenticatedSubmission.from_received(received, gateway)
    try:
        # Rebuilds and inference run for minutes; keep the event loop free.
        outcome = await asyncio.to_thread(evaluate, target, submission)
    except EvaluationUnavailable as unavailable:
        raise OperationRefused(unavailable.code) from None
    if outcome["state"] == "FAILED_INFRA":
        raise OperationRefused("evaluation_failed_infra")
    if outcome.get("waiting"):
        raise OperationRefused("evaluation_queued")
    return {
        "schema": "carbon.battery.permitted-feedback.v1",
        "epoch": epoch,
        "outcome": outcome,
        "official_eligible": False,
        "reward": False,
    }


#: How a frozen candidate's trip through a validator intake ends when it is
#: not a verdict, by closed code (LP-PROD-G). None of these consumes the
#: epoch: the candidate stays frozen, and submitting it again is the same
#: submission (`daemon.submission_identity`: same hotkey, recipe and
#: contract), never a second admission.
#: - QUEUED: the validator holds the submission and has not finished.
#: - UNAVAILABLE: the validator, or the way to it, could not serve. Not a
#:   verdict and nothing for the miner to change; submit again later.
#: - REFUSED: no evaluation happened, for a named reason the miner acts on
#:   (wait for the next window, commit on chain, register, re-sign).
#: Every other code the intake or its transport can answer is REFUSED; an
#: answer outside them all is `intake_answer_unrecognised` (UNAVAILABLE).
#: A trip that ends in an exception has its own closed code (`_failure_code`):
#: the miner's signer not signing (`signer_unavailable`), an intake for
#: another chain or Challenge (`intake_mismatch`), and a resend that would
#: name another hotkey's submission (`intake_signer_changed`) are REFUSED.
#: So is an intake reporting another receiver than the profile pins
#: (`intake_receiver_mismatch`, LAUNCHPAD-ACCEPT-03), refused before anything
#: is signed or sent.
#: `intake_client.explain(code)` gives each one's plain explanation.
INTAKE_QUEUED = frozenset({"evaluation_queued"})
INTAKE_UNAVAILABLE = frozenset(
    {
        "intake_unreachable",
        "intake_answer_unrecognised",
        "evaluation_failed_infra",
        "rate",
        "capacity",
        "inbox_full",
        "snapshot_unavailable",
        "receipt_block_missing",
        "commitment_reader_unavailable",
        "backend_not_served",
        "TRANSPORT_CAPACITY",
        "TRANSPORT_STORE",
        "AUTH_UNAVAILABLE",
    }
)


def intake_code(code):
    """The closed code an intake refusal is reported under."""
    from .intake_client import REFUSALS

    return code if code in REFUSALS else "intake_answer_unrecognised"


def intake_outcome(code):
    """`QUEUED`, `UNAVAILABLE` or `REFUSED` for a closed intake code, so a
    door can show a refused submit as waiting, the validator's state, or
    the miner's to act on."""
    code = intake_code(code)
    if code in INTAKE_QUEUED:
        return "QUEUED"
    return "UNAVAILABLE" if code in INTAKE_UNAVAILABLE else "REFUSED"


def _resend(
    url, signer, submission_id, failure, strategy, contract_digest, io, receiver=None
):
    """Send the epoch's frozen candidate again, so the intake receives it
    again under the same submission id. The intake's facts are read again
    and must report the profile's pinned `receiver` before the resend is
    signed (`remote_submission.check_receiver`).

    Before anything is sent, the id the resend would name is worked out from
    the signer's public hotkey (`intake_client.submission_id`). If it is not
    the epoch's submission - the signer was changed after the epoch was
    recorded, so the status poll was `not_found` for another hotkey's id -
    nothing is sent (`intake_signer_changed`): a resend under the new hotkey
    would be a second submission of the candidate, with its own admission
    and window. A refusal for the hotkey's window is answered here, sending
    nothing, until the intake's chain has reached the window's first block.
    """
    from . import intake_client
    from . import remote_submission as rs

    hotkey = getattr(signer, "ss58_address", None)
    if (
        type(hotkey) is not str
        or intake_client.submission_id(hotkey, strategy, contract_digest)
        != submission_id
    ):
        raise rs.IntakeRefusal("intake_signer_changed")
    facts = rs.check_receiver(io["read"](url), receiver)
    next_block = (failure or {}).get("next_block")
    block = (facts.get("snapshot") or {}).get("finalized_block")
    if next_block is not None and type(block) is int and block < next_block:
        raise rs.IntakeRefusal(
            "hotkey_window_used",
            intake_client.describe(200, {"state": "REFUSED", "failure": failure}),
        )
    body = intake_client.submission_message(facts, strategy, contract_digest)
    status, answer = io["post"](url, body, rs._signed(signer, facts, body))
    if status != 202 or "submission_id" not in answer:
        raise rs.IntakeRefusal(
            answer.get("refused", f"http_{status}"),
            intake_client.describe(status, answer),
        )
    if answer["submission_id"] != submission_id:
        # The id was checked before sending, so only an intake that names
        # submissions some other way answers so: not this protocol, and
        # nothing more is sent to it.
        raise rs.IntakeRefusal("intake_answer_unrecognised")


def submit_through_intake(
    url,
    signer,
    *,
    root,
    epoch,
    strategy,
    contract_digest,
    read=None,
    post=None,
    receiver=None,
):
    """The epoch's frozen candidate through a validator intake, to a verdict.

    `remote_submission.submit_and_wait` submits once per epoch (it records
    the submission id) and polls. Two of its answers are not verdicts and are
    settled here, at most once per call, by resending the same candidate:
    - REFUSED at admission for a reason that is never a judgement of the
      recipe (`intake.RECEIVED_AGAIN`), which the intake receives again;
    - `not_found` for the epoch's recorded submission: the validator no longer
      holds it (an inbox restored from an earlier backup).
    Either resend is sent only when the signer's hotkey names that same
    submission (`_resend`; otherwise `intake_signer_changed`, nothing sent).
    A candidate recorded against another intake is refused
    (`intake_changed_since_submission`): an epoch's submission belongs to the
    validator that received it. `receiver`, the profile's pinned receiver
    hotkey, is checked against the intake's reported one before every submit,
    resend and status poll is signed (`intake_receiver_mismatch`, nothing
    signed or sent; None for a profile written before receivers were
    pinned). Returns `(status, answer, submission_id)`; raises
    `IntakeRefusal` with the intake's or the transport's code.
    """
    from carbon.reconstruction.capability_registry import (
        DEVELOPMENT_VARIANT_NOT_SERVED,
        is_development_variant,
    )

    from . import intake_client
    from . import remote_submission as rs
    from .intake import RECEIVED_AGAIN

    if is_development_variant(contract_digest):
        # A development-only contract variant is never served to a miner, so
        # the Launchpad sends nothing (OWNER-GRAPHITE-TEST-WAVE-03 §1), except
        # to a target whose public facts list it among the variants it serves
        # (OWNER-LADDER-THROUGH-LAUNCHPAD-01's amendment): the development-
        # ladder deployment. Its facts are read, and the receiver checked,
        # before anything is signed.
        from carbon.development_session.construction_level import lists_digest

        facts = rs.check_receiver((read or intake_client.read_intake)(url), receiver)
        if not lists_digest(facts, contract_digest):
            raise rs.IntakeRefusal(DEVELOPMENT_VARIANT_NOT_SERVED)
    passed = {} if read is None else {"read": read, "post": post}
    if receiver is not None:
        passed["receiver"] = receiver
    io = {
        "read": read or intake_client.read_intake,
        "post": post or intake_client.post,
    }
    record = rs._record_path(root, epoch)
    recorded = json.loads(record.read_bytes()) if record.exists() else None
    if recorded is not None and recorded.get("url") != url:
        raise rs.IntakeRefusal("intake_changed_since_submission")

    def wait():
        return rs.submit_and_wait(
            url,
            signer,
            root=root,
            epoch=epoch,
            strategy=strategy,
            contract_digest=contract_digest,
            **passed,
        )

    try:
        status, answer, submission_id = wait()
    except rs.IntakeRefusal as refused:
        if refused.code != "not_found" or recorded is None:
            raise
        sid = recorded["submission_id"]
        _resend(url, signer, sid, None, strategy, contract_digest, io, receiver)
        return wait()
    failure = answer.get("failure") or {}
    if answer.get("state") != "REFUSED" or failure.get("code") not in RECEIVED_AGAIN:
        return status, answer, submission_id
    _resend(
        url, signer, submission_id, failure, strategy, contract_digest, io, receiver
    )
    return wait()


def _failure_code(failure):
    """The closed code for a trip to the intake that ended in an exception.

    - the miner's signer did not sign (`SignerFailure`): `signer_unavailable`;
    - the intake describes another chain or Challenge, or is not a battery
      intake (`IntakeMismatch`): `intake_mismatch`;
    - an HTTP refusal of the intake's public facts (`read_intake` raises it,
      a 429 `rate` or a 503 `snapshot_unavailable` among them): the intake's
      own code when its JSON body names one, else `intake_unreachable`;
    - a body that is not JSON (a proxy's error page, another server), a
      connection that failed or broke mid-answer: `intake_unreachable`;
    - JSON in a shape this client does not read: `intake_answer_unrecognised`.
    """
    import http.client
    import urllib.error

    from carbon.chain.external_signer import SignerFailure

    from .intake_client import IntakeMismatch

    if isinstance(failure, SignerFailure):
        return "signer_unavailable"
    if isinstance(failure, IntakeMismatch):
        return "intake_mismatch"
    if isinstance(failure, urllib.error.HTTPError):
        try:
            body = json.loads(failure.read(65536) or b"{}")
        except (OSError, ValueError, http.client.HTTPException):
            body = None
        code = body.get("refused") if type(body) is dict else None
        return intake_code(code) if type(code) is str else "intake_unreachable"
    if isinstance(failure, (OSError, http.client.HTTPException, json.JSONDecodeError)):
        return "intake_unreachable"
    return "intake_answer_unrecognised"


def frozen_commitment(record, manifest):
    """L1: the digest a miner commits on chain for this frozen candidate
    (`selected-recipe.json`), as the validator recomputes it
    (`daemon.commitment_digest`, through `commitment_poster.expected_digest`):
    its Challenge, the contract it was frozen under and its strategy hash."""
    from carbon.chain.commitment_poster import expected_digest

    if "construction_level" in record:
        # A candidate frozen at a construction level (LAUNCHPAD-LEVELS-01
        # S2): the same digest over the variant's contract digest and the
        # strategy hash the level's compile gives it.
        from carbon.development_session.construction_level import commitment_fields

        from .daemon import commitment_digest

        return commitment_digest(*commitment_fields(record))
    return expected_digest(
        record["strategy"],
        record.get("contract_digest") or manifest["contract_digest"],
    )


def commitment_due(args, root, epoch):
    """Whether the commitment must read back on chain before this epoch's
    candidate is sent: its first send through this Challenge's validator
    intake. A deployment on this machine checks its own `require_commitment`;
    a submission the intake already holds is polled, and any resend is the
    intake's to refuse (`intake.RECEIVED_AGAIN`)."""
    from . import remote_submission as rs

    prepared = SimpleNamespace(args=args)
    if evaluation_config(prepared) is not None or _intake(prepared) is None:
        return False
    return not rs._record_path(root, epoch).exists()


async def _committed(gate, root, epoch, record, manifest, *, request, recommit=False):
    """The commitment gate before a send: `OperationRefused` with its closed
    code unless the frozen candidate's digest reads back as the hotkey's
    commitment at the finalized head (`CommitmentGate.before_submit`)."""
    from carbon.development_session.research_campaign import OperationRefused

    try:
        digest = frozen_commitment(record, manifest)
    except (ValueError, KeyError, TypeError):
        raise OperationRefused("commitment_digest_unavailable") from None
    code = await asyncio.to_thread(
        gate.before_submit,
        root,
        digest,
        request=request,
        epoch=epoch,
        recommit=recommit,
    )
    if code is not None:
        raise OperationRefused(code)


async def _evaluate_through_intake(prepared, epoch, record, url):
    """One frozen candidate through the validator's intake; see
    `submit_through_intake`. The epoch is consumed only by a verdict: SCORED,
    or the daemon's INVALID_CONSTRUCTION or RECONSTRUCTION_FAILED. Anything
    else raises `OperationRefused` with a closed code (`intake_outcome`),
    including every way the trip itself can fail (`_failure_code`), so the
    campaign keeps its frozen candidate instead of ending on an exception.

    With the Launchpad's commitment gate (`args.commitment_gate`,
    LAUNCHPAD-ACCEPT-02), the candidate's first send waits for its
    commitment to read back on chain (`_committed`). A campaign whose agent
    selects asks for the commitment itself, and once for a recommit when the
    validator answers `commitment_stale` (D10, L7); only the miner confirms
    either, on the signer's terminal."""
    import http.client

    from carbon.chain.commitment_poster import STALE
    from carbon.chain.external_signer import SignerFailure
    from carbon.development_session.research_campaign import OperationRefused

    from .intake_client import describe
    from .remote_submission import IntakeRefusal

    root = prepared.ledger.root
    frozen_level = record.get("construction_level")
    if type(frozen_level) is dict and frozen_level.get("level") == 4:
        # A Level 4 candidate travels with its staging envelope beside the
        # signed strategy (LEVEL4_STAGING_CONTRACT §4). It is read and checked
        # here, unchanged; no intake carries it yet (the validator's upload,
        # VALIDATOR-25 slice 4), so nothing is signed or sent.
        from carbon.development_session import construction_level as cl

        try:
            cl.read_envelope(root / ("epoch-" + str(epoch)), record)
        except cl.LevelRefused as refused:
            raise OperationRefused(refused.code) from None
        raise OperationRefused(cl.LEVEL4_TRANSPORT_UNAVAILABLE)
    gate = getattr(prepared.args, "commitment_gate", None)
    asks = getattr(prepared, "agent", "none") != "none"
    if gate is not None and commitment_due(prepared.args, root, epoch):
        await _committed(gate, root, epoch, record, prepared.manifest, request=asks)
    recommitted = False
    while True:
        try:
            status, answer, submission_id = await asyncio.to_thread(
                submit_through_intake,
                url,
                prepared.sdk.connection.miner_key,
                root=root,
                epoch=epoch,
                strategy=record["strategy"],
                contract_digest=record.get("contract_digest")
                or prepared.manifest["contract_digest"],
                receiver=_receiver(prepared),
            )
        except IntakeRefusal as refused:
            raise OperationRefused(intake_code(refused.code)) from None
        except (
            SignerFailure,
            OSError,
            http.client.HTTPException,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ) as failure:
            raise OperationRefused(_failure_code(failure)) from None
        if answer.get("state") != "REFUSED":
            break
        # Refused at admission and not received again: never a verdict.
        code = intake_code((answer.get("failure") or {}).get("code"))
        if code != STALE or gate is None or not asks or recommitted:
            raise OperationRefused(code)
        # The agent asks for the recommit; the intake then receives the same
        # submission again (`intake.RECEIVED_AGAIN`), never a second one.
        recommitted = True
        await _committed(
            gate, root, epoch, record, prepared.manifest, request=True, recommit=True
        )
    state = answer.get("state")
    if state == "FAILED_INFRA_EXHAUSTED":
        raise OperationRefused("evaluation_failed_infra")
    if state not in ("SCORED", "INVALID_CONSTRUCTION", "RECONSTRUCTION_FAILED"):
        raise OperationRefused("intake_answer_unrecognised")
    try:
        description = describe(status, answer)
    except (KeyError, TypeError, AttributeError, ValueError):
        # A verdict this client cannot read is not taken as the epoch's.
        raise OperationRefused("intake_answer_unrecognised") from None
    return {
        "schema": "carbon.battery.permitted-feedback.v1",
        "epoch": epoch,
        "outcome": answer,
        "via": {"intake": url, "submission_id": submission_id},
        "description": description,
        "official_eligible": False,
        "reward": False,
    }


async def evaluate_frozen(prepared, epoch, strategy):
    """This Challenge's validator daemon judges the frozen candidate; the
    Burgers final epoch never sees it."""
    from carbon.development_session.data import write_once
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_report import report

    ledger, owner = prepared.ledger, prepared.owner
    folder = ledger.root / ("epoch-" + str(epoch))
    record = json.loads((folder / "selected-recipe.json").read_bytes())
    if record["strategy"] != strategy:
        raise ValueError("submitted strategy differs from the frozen candidate")
    feedback = await evaluate_candidate(prepared, epoch, record)
    write_once(folder / "permitted-final-feedback.json", canonical(feedback))
    report(ledger, owner=owner)
    return feedback


def agent_observation(prepared, epoch, feedback):
    """What Carbon's agent sees first in a battery epoch: public discovery only.

    The discovery document is the one every miner reads (`challenge_registry`),
    less its long list of unsupported capabilities, which the agent can read
    through `public_material capabilities` or `roadmap`. Nothing private: the
    prior feedback is the daemon's allow-listed outcome.

    A campaign whose run plan froze the research tools rule
    (`research_tools.TOOLS_RULE`, LP-PROD-D) also sees this host's research
    environment, `research_environment`: whether the campaign has a GPU lane
    for its code cells, and which backends its practice serves. A plan frozen
    without the rule sees exactly what it always saw.
    """
    from carbon.challenge_registry import describe
    from carbon.development_session.research_tools import frozen_tools_rule

    from .research import SCAFFOLD

    document = describe(CHALLENGE.challenge_id, CHALLENGE.version)
    unsupported = document.pop("unsupported")
    manifest = prepared.manifest
    mode = feedback_mode(manifest.get("feedback_mode", FEEDBACK_FULL))
    rule = frozen_tools_rule(manifest)
    extra = {}
    if rule is not None:
        extra["research_environment"] = research_environment(prepared, rule)
    return {
        "challenge": document,
        "unsupported_capabilities": {
            "count": len(unsupported),
            "read_with": (
                "workspace public_material {name: capabilities} or roadmap {}"
                if rule is None
                else "start_research_task kind=workspace action=public_material "
                'arguments_json="{\\"name\\":\\"capabilities\\"}", or '
                'action=roadmap arguments_json="{}"'
            ),
        },
        **extra,
        "scaffold_recipe": SCAFFOLD,
        "scaffold_basis": "An unexecuted template; it has no measured result.",
        "epoch": epoch,
        "prior_permitted_evaluation_feedback": permitted_feedback(feedback, mode),
        "run_plan": manifest["provider"],
        "miner_budget": {
            key: manifest[key]
            for key in ("ceilings", "elapsed_seconds", "final_reserve")
            if key in manifest
        }
        or None,
        "instructions": (
            "Record a testable plan. Use real practice, inspect its diagnostics "
            "and revise or reject hypotheses. Select only a recipe you actually "
            "practiced, or stop for a supported reason."
        ),
    }


def research_environment(prepared, rule):
    """What this host gives a campaign's research, as its agent should know it.

    Facts about the miner's own composition only: whether the campaign's
    frozen runtime has a GPU lane for code cells (and which), which backends
    its practice serves on this host, and whether authored Julia is offered.
    Nothing here is evaluation material, and nothing grants anything.
    """
    # The composition's own executor and practice, never a default: a
    # campaign is composed before its agent observes anything, so a missing
    # one is an error here, not a quiet "cpu only".
    executor = prepared.composition.executor
    lane = executor.gpu
    practice = executor.practice
    julia = executor.julia_image is not None
    described = None if lane is None else lane.describe()
    return {
        "rule": rule,
        "gpu_lane": described,
        "code_cell_devices": _code_cell_devices(described, julia),
        "practice_backends": list(practice.backends),
        "practice_device": "gpu" if practice.gpu_image is not None else "cpu",
        "practice_note": (
            "a practice whose recipe names a backend outside practice_backends "
            "is refused before it starts (backend_not_served) and charges "
            "nothing"
        ),
        "authored_julia": julia,
    }


def _code_cell_devices(described, julia):
    """Which code-cell actions take device=gpu here: those the lane's own
    description lists (`GpuLane.describe`) among those this campaign offers
    (run_julia only with authored Julia). Never more than the lane runs: a
    remote lane runs run_python only."""
    offered = ["run_python", "run_julia"] if julia else ["run_python"]

    def said(names, verb):
        return " and ".join(names) + " " + (verb if len(names) > 1 else verb + "s")

    if described is None:
        return (
            "cpu only: this campaign was launched without a GPU lane, so "
            + said(offered, "take")
            + " device=cpu (the default)"
        )
    on_gpu = [name for name in offered if name in described["actions"]]
    text = "cpu (the default) or gpu: " + said(on_gpu, "take") + " device=gpu"
    text += " on the lane above"
    if "run_julia" in on_gpu:
        text += ", run_julia in the lane's julia_environments only"
    cpu_only = [name for name in offered if name not in on_gpu]
    if cpu_only:
        text += "; " + said(cpu_only, "run") + " on cpu only"
    return text
