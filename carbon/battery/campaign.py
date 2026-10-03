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
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

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
#: What an autonomous battery campaign must cap before any model call: the
#: miner's (or operator's) own ceilings, never a default supplied here.
AGENT_BUDGET_KEYS = ("provider_attempts", "provider_nanodollars")


def provider_plan(agent, budget, selection=None):
    """The finite run plan a battery campaign freezes in its manifest.

    `selection` is the miner's model selection; the pinned default records the
    plan exactly as before selection existed, any other adds its record."""
    if agent == "none":
        return {"agent": "none", "model_calls": 0}
    from carbon.development_session import miner_guidance
    from carbon.development_session.model_provider import (
        DEFAULT_SELECTION,
        check_budget,
    )
    from carbon.development_session.research_agent_policy import (
        AUTONOMOUS,
        PARALLEL_CALLS,
    )
    from carbon.development_session.research_campaign import FINAL_EPOCHS

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
        # Frozen with the plan: a provider that returns several tool calls in
        # one turn gets the first run and the rest refused, not a stopped run.
        "parallel_calls": PARALLEL_CALLS,
        # Frozen with the plan (RSURF-D13): the agent reads the miner's
        # Conversation messages at each step as recorded guidance. A plan
        # frozen before the amendment has no rule and reads none.
        "miner_guidance": miner_guidance.RULE,
    }
    if not selection.is_historical_default:
        plan["model_selection"] = selection.record()
    return plan


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
        "provider": provider_plan(product.agent, product.budget, selection),
        "images": images,
        "new_network_transactions": 0,
        "feedback_mode": feedback_mode(feedback),
        **product.manifest_fields(),
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
    if agent != "none":
        from carbon.development_session.agent import ResponsesTransport
        from carbon.development_session.model_provider import SelectionTransport
        from carbon.development_session.research_agent_policy import AUTONOMOUS
        from carbon.development_session.research_campaign import supplied_selection

        if getattr(args, "agent_policy", None) != AUTONOMOUS:
            raise ValueError("a battery agent runs only under the autonomous policy")
        if frozen is None:
            selection = supplied_selection(args)
            plan = provider_plan(agent, product.budget, selection)
        else:
            plan = frozen["provider"]
            selection = plan_selection(args, plan)
        if plan.get("agent") != "autonomous" or plan.get("evaluator_access"):
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

    # `runner`/`backend` exist for tests; every campaign door passes neither,
    # so practice runs in the isolated carrier and says so.
    practice = BatteryPractice(
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


async def _evaluate_through_intake(prepared, epoch, record, url):
    """One frozen candidate through the validator's intake; see
    `remote_submission`. The epoch is consumed only by a verdict."""
    from carbon.development_session.research_campaign import OperationRefused

    from .remote_submission import IntakeRefusal, submit_and_wait

    try:
        status, answer, submission_id = await asyncio.to_thread(
            submit_and_wait,
            url,
            prepared.sdk.connection.miner_key,
            root=prepared.ledger.root,
            epoch=epoch,
            strategy=record["strategy"],
            contract_digest=record.get("contract_digest")
            or prepared.manifest["contract_digest"],
        )
    except IntakeRefusal as refused:
        raise OperationRefused(refused.code) from None
    except OSError:
        raise OperationRefused("intake_unreachable") from None
    if answer.get("state") == "FAILED_INFRA_EXHAUSTED":
        raise OperationRefused("evaluation_failed_infra")
    from .intake_client import describe

    return {
        "schema": "carbon.battery.permitted-feedback.v1",
        "epoch": epoch,
        "outcome": answer,
        "via": {"intake": url, "submission_id": submission_id},
        "description": describe(status, answer),
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
    executor = getattr(getattr(prepared, "composition", None), "executor", None)
    lane = getattr(executor, "gpu", None)
    practice = getattr(executor, "practice", None)
    backends = getattr(practice, "backends", None)
    gpu_practice = getattr(practice, "gpu_image", None) is not None
    return {
        "rule": rule,
        "gpu_lane": None if lane is None else lane.describe(),
        "code_cell_devices": (
            "cpu only: this campaign was launched without a GPU lane, so "
            "run_python and run_julia take device=cpu (the default)"
            if lane is None
            else "cpu (the default) or gpu: run_python and run_julia take "
            "device=gpu on the lane above"
        ),
        "practice_backends": None if backends is None else list(backends),
        "practice_device": "gpu" if gpu_practice else "cpu",
        "practice_note": (
            "a practice whose recipe names a backend outside practice_backends "
            "is refused before it starts (backend_not_served) and charges "
            "nothing"
        ),
        "authored_julia": getattr(executor, "julia_image", None) is not None,
    }
