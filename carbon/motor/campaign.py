"""Launchpad campaign adapter for motor Level-0 construction.

The campaign exposes public construction and practice.  Official evaluation
remains fail closed until the separate Challenge-neutral validator ticket
registers a motor adapter; a refused submit therefore retains its frozen
candidate instead of manufacturing a score.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from carbon.challenge_registry.agent_plan import (
    agent_policies,
    plan_selection,
    provider_plan,
)

from .challenge import CHALLENGE

REPOSITORY = Path(__file__).resolve().parents[2]
SELECTION = {
    "rule": "the miner freezes one practiced recipe per submission epoch",
    "evidence_required": "a completed public-practice run of the same recipe",
}
REPLICAS = {
    "reconstructions_per_submission": 1,
    "seed": "none; the registered closed-form reconstruction is deterministic",
}
FEEDBACK_MODES = ("FULL",)
PRACTICE_PROVENANCE = "MOTOR_PUBLIC_PRACTICE"
BACKENDS = ("numpy",)
RUNTIME_KEYS = frozenset({"implementation", "images", "authored_research"})


def manifest_document(
    product, *, owner, implementation, images, selection=None, graphite=None
):
    from carbon.development_session.research_ledger import VERSION
    from carbon.reconstruction.capability_registry import contract_digest

    from .research import SCAFFOLD, objective

    return {
        "schema": VERSION,
        "campaign_id": product.campaign_id,
        "authority": "OWNER-GRAPHITE-TEST-WAVE-01",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "owner": owner,
        "implementation": implementation,
        "objective": objective(),
        "contract_digest": contract_digest(CHALLENGE.challenge_id),
        "sampling": {"practice": "30 fixed public PRACTICE cases"},
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
        "feedback_mode": "FULL",
        **product.manifest_fields(),
    }


def host_julia_image(root, declared, analysis):
    from carbon.development_session.research_campaign import (
        available_julia_image,
        registered_julia_image,
    )

    if "authored_research" in declared:
        return registered_julia_image(root, declared, analysis)
    return available_julia_image(root, analysis)


def research_runtime(declared, *, implementation, images, julia_image):
    extra = set(declared) - RUNTIME_KEYS
    if extra:
        raise ValueError(
            "motor has no research composition for " + ", ".join(sorted(extra))
        )
    runtime = {"implementation": implementation, "images": images}
    if julia_image is not None and "authored_research" in declared:
        from carbon.development_session.julia_analysis import authored_julia_scope

        runtime["authored_research"] = [authored_julia_scope(julia_image)]
    return runtime


def check_attached(
    manifest, *, implementation, images, julia_image=None, gpu_image=None
):
    from carbon.reconstruction.capability_registry import contract_digest

    from .research import objective

    if gpu_image is not None:
        raise ValueError("motor Level 0 has no GPU practice lane")
    expected = {
        "implementation": implementation,
        "images": images,
        "objective": objective(),
        "contract_digest": contract_digest(CHALLENGE.challenge_id),
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise ValueError("motor campaign " + field + " changed")
    frozen = manifest.get("runtime")
    if type(frozen) is not dict or frozen != research_runtime(
        frozen,
        implementation=implementation,
        images=images,
        julia_image=julia_image,
    ):
        raise ValueError("campaign runtime differs from the motor runtime")


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
    from carbon.miner_mcp.research import AuthenticatedResearchService
    from carbon.transport.gateway import AuthenticatedGateway

    from .research import MotorPractice, make_motor_research_service

    if gpu_image is not None or remote is not None:
        raise ValueError("motor Level 0 offers CPU practice only")
    practice = MotorPractice(
        ledger=ledger,
        owner=owner,
        image=image,
        root=REPOSITORY,
        runner=runner,
        backend=backend,
    )
    composition = make_motor_research_service(
        root=ledger.root / "research-tasks",
        ledger=ledger,
        owner=owner,
        image=analysis,
        practice=practice,
        demand=demand,
        cleanup_only=cleanup_only,
        julia_image=julia_image,
    )
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


async def prepare_motor(args, *, ledger=None, campaign):
    """Prepare a registered motor product campaign and public research."""
    from carbon.chain.external_signer import miner_signer
    from carbon.chain.models import CARBON_NETUID
    from carbon.compute.retired import refuse_rented
    from carbon.development_session.data import write_once
    from carbon.development_session.miner_network import binding_for
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_campaign import (
        PreparedCampaign,
        accepted_implementation,
        new_plan_output_default,
        private_file,
        requester,
        supplied_selection,
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
        raise ValueError("a motor campaign is a product campaign")
    refuse_rented(frozen.get("runtime") if frozen is not None else product.runtime)
    ledger = ledger if ledger is not None else CampaignLedger(root)
    if ledger.root != root or ledger.admission is not None:
        raise ValueError("a motor campaign never consumes a development grant")

    agent = frozen["agent"] if frozen is not None else product.agent
    selection = None
    graphite = None
    if agent != "none":
        from carbon.development_session.agent import ResponsesTransport
        from carbon.development_session.model_provider import SelectionTransport

        if getattr(args, "agent_policy", None) not in agent_policies(agent):
            raise ValueError("a campaign agent runs only under its registered policy")
        if frozen is None:
            selection = supplied_selection(
                args, output_default=new_plan_output_default(args)
            )
            if agent == "graphite":
                from carbon.agent_campaign.graphite.miner.driver import freeze_launch

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
            raise ValueError("the frozen campaign agent plan is not runnable")
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
    runtime = research_runtime(
        declared,
        implementation=implementation,
        images=[image.image_id, analysis.image_id],
        julia_image=julia_image,
    )
    if declared != runtime:
        raise ValueError("configured runtime differs from the motor runtime")

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
            graphite=graphite,
        )
        write_once(manifest_path, canonical(manifest))
    else:
        manifest = frozen
        if manifest.get("owner") != owner:
            raise ValueError("motor campaign owner changed")
        check_attached(
            manifest,
            implementation=implementation,
            images=runtime["images"],
            julia_image=julia_image,
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


async def evaluate_frozen(prepared, epoch, strategy):
    """The scoring adapter is deliberately absent from this engineering slice."""
    from carbon.development_session.research_campaign import OperationRefused

    raise OperationRefused("motor_validator_not_served")


def agent_observation(prepared, epoch, feedback):
    from carbon.challenge_registry import describe
    from carbon.development_session.research_tools import frozen_tools_rule

    from .research import SCAFFOLD

    document = describe(CHALLENGE.challenge_id, CHALLENGE.version)
    unsupported = document.pop("unsupported")
    rule = frozen_tools_rule(prepared.manifest)
    extra = {}
    if rule is not None:
        practice = prepared.composition.executor.practice
        extra["research_environment"] = {
            "rule": rule,
            "gpu_lane": None,
            "code_cell_devices": "cpu only",
            "practice_backends": list(practice.backends),
            "practice_device": "cpu",
            "practice_note": (
                "a backend outside practice_backends is refused before dispatch"
            ),
            "authored_julia": prepared.composition.executor.julia_image is not None,
        }
    return {
        "challenge": document,
        "unsupported_capabilities": {
            "count": len(unsupported),
            "read_with": "public_material capabilities or roadmap",
        },
        **extra,
        "scaffold_recipe": SCAFFOLD,
        "scaffold_basis": "An unexecuted template; it has no measured result.",
        "epoch": epoch,
        "prior_permitted_evaluation_feedback": feedback,
        "run_plan": prepared.manifest["provider"],
        "miner_budget": {
            key: prepared.manifest[key]
            for key in ("ceilings", "elapsed_seconds", "final_reserve")
            if key in prepared.manifest
        }
        or None,
        "instructions": (
            "Use public practice and freeze only a recipe Carbon can rebuild. "
            "Submission evaluation remains unavailable until its adapter is registered."
        ),
    }
