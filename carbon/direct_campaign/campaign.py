"""Launchpad campaign for a direct-recipe-only version (F08 1.4, F02 2.3).

As Motor's and Cooling's catalog versions: direct recipes only (a Carbon-tested
catalog backbone, or a graph trained by Carbon's registered graph training
adapter), practised on the PyTorch CPU worker through the receiver's own
build, frozen from a practice result, and submitted to the signed construction
receiver, which rebuilds and judges it. Every hook runs under the version's
research key (`spec.keyed`); each Challenge binds these with its own spec
(`carbon.f08.campaign`, `carbon.f02.campaign`).

While the version's catalog is empty (no entry has its pair-identity receipt
yet) a campaign is refused before anything is frozen, connected or charged,
with the closed code `<prefix>_catalog_empty`.
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

from .spec import research_key

REPOSITORY = Path(__file__).resolve().parents[2]
SELECTION = {
    "rule": "the miner freezes one practiced recipe per submission epoch",
    "evidence_required": "a completed public-practice run of the same recipe",
}
REPLICAS = {"reconstructions_per_submission": 1, "seed": 0}
FEEDBACK_MODES = ("FULL",)
RUNTIME_KEYS = frozenset({"implementation", "images", "authored_research"})


def _contract_digest(spec):
    from carbon.reconstruction.served_recipe_contract import registered

    key = research_key(spec)
    return registered(key.challenge_id, key.version).digest


def control(spec):
    from carbon.challenge_registry.direct import catalog_recipe

    return catalog_recipe(spec, version=research_key(spec).version)


def catalog_empty_code(spec):
    return spec.prefix + "_catalog_empty"


def refuse_empty_catalog(spec):
    """A campaign with no tested catalog entry is refused before anything is
    frozen, connected or charged (each entry needs its own pair-identity
    receipt)."""
    from carbon.backbone_catalog import listing

    key = research_key(spec)
    if not listing.entries(key.challenge_id, key.version):
        raise ValueError(
            spec.prefix
            + " "
            + key.version
            + " serves no tested backbone yet ("
            + catalog_empty_code(spec)
            + ")"
        )


def manifest_document(
    spec, product, *, owner, implementation, images, selection=None, graphite=None
):
    from carbon.development_session.research_ledger import VERSION

    from .research import bank, objective

    return {
        "schema": VERSION,
        "campaign_id": product.campaign_id,
        "authority": "OWNER-GRAPHITE-TEST-WAVE-01",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "owner": owner,
        "implementation": implementation,
        "objective": objective(spec),
        "contract_digest": _contract_digest(spec),
        "sampling": {"practice": bank(spec)},
        "control": control(spec),
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
        "construction_mode": "direct",
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


def research_runtime(spec, declared, *, implementation, images, julia_image):
    extra = set(declared) - RUNTIME_KEYS
    if extra:
        raise ValueError(
            spec.prefix + " has no research composition for " + ", ".join(sorted(extra))
        )
    runtime = {"implementation": implementation, "images": images}
    if julia_image is not None and "authored_research" in declared:
        from carbon.development_session.julia_analysis import authored_julia_scope

        runtime["authored_research"] = [authored_julia_scope(julia_image)]
    return runtime


def check_attached(
    spec, manifest, *, implementation, images, julia_image=None, gpu_image=None
):
    from .research import objective

    if gpu_image is not None:
        raise ValueError(spec.prefix + " direct practice has no GPU lane")
    key = research_key(spec)
    expected = {
        "implementation": implementation,
        "images": images,
        "objective": objective(spec),
        "contract_digest": _contract_digest(spec),
        "challenge": {"id": key.challenge_id, "version": key.version},
        "construction_mode": "direct",
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise ValueError(spec.prefix + " campaign " + field + " changed")
    frozen = manifest.get("runtime")
    if type(frozen) is not dict or frozen != research_runtime(
        spec,
        frozen,
        implementation=implementation,
        images=images,
        julia_image=julia_image,
    ):
        raise ValueError(
            "campaign runtime differs from the " + spec.prefix + " runtime"
        )


def compose(
    spec,
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

    from .practice import DirectPractice
    from .research import make_research_service

    if gpu_image is not None or remote is not None:
        raise ValueError(spec.prefix + " direct practice is CPU only")
    key = research_key(spec)
    # The campaign's PyTorch CPU worker is the parent of every catalog bundle's
    # child (installed by `backbone_catalog.pipeline install` into the owner's
    # library cache beside the campaigns) and runs the graph adapter.
    practice = DirectPractice(
        spec,
        ledger=ledger,
        owner=owner,
        parent=image,
        cache_root=ledger.root.parent / ".direct-development" / "library-cache",
        root=REPOSITORY,
        version=key.version,
        runner=runner,
    )
    composition = make_research_service(
        spec,
        root=ledger.root / "research-tasks",
        ledger=ledger,
        owner=owner,
        image=analysis,
        practice=practice,
        version=key.version,
        demand=demand,
        cleanup_only=cleanup_only,
        julia_image=julia_image,
    )
    base = connection.service.gateway
    gateway = AuthenticatedGateway(
        base.context,
        key,
        base.receiver,
        base.adapter,
        base.verifier,
        base.journal,
        clock_ns=base.clock_ns,
    )
    return composition, AuthenticatedResearchService(
        gateway, {owner: composition.service}
    )


async def prepare(spec, args, *, ledger=None, campaign):
    """Prepare a registered direct-recipe product campaign and public research."""
    from carbon.chain.external_signer import miner_signer
    from carbon.chain.models import CARBON_NETUID
    from carbon.compute.retired import refuse_rented
    from carbon.development_session.data import write_once
    from carbon.development_session.gpu_practice import direct_parent_backend
    from carbon.development_session.miner_network import binding_for
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_campaign import (
        PreparedCampaign,
        campaign_implementation,
        new_plan_input_default,
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

    key = research_key(spec)
    root = args.root
    manifest_path = root / "campaign-manifest.json"
    if args.command == "run" and manifest_path.exists():
        raise ValueError("campaign already exists; use resume")
    if args.command == "resume" and not manifest_path.exists():
        raise ValueError("no frozen campaign to resume")
    frozen = json.loads(manifest_path.read_bytes()) if manifest_path.exists() else None
    product = getattr(args, "product", None)
    if frozen is None and product is None:
        raise ValueError("a " + spec.prefix + " campaign is a product campaign")
    # Before anything is frozen, connected or charged.
    refuse_empty_catalog(spec)
    refuse_rented(frozen.get("runtime") if frozen is not None else product.runtime)
    ledger = ledger if ledger is not None else CampaignLedger(root)
    if ledger.root != root or ledger.admission is not None:
        raise ValueError(
            "a " + spec.prefix + " campaign never consumes a development grant"
        )

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
                args,
                output_default=new_plan_output_default(args),
                input_default=new_plan_input_default(args, agent),
            )
            if agent == "graphite":
                from carbon.agent_campaign.graphite.miner.driver import freeze_launch

                graphite = freeze_launch(
                    args,
                    root,
                    challenge={"id": key.challenge_id, "version": key.version},
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

    implementation = campaign_implementation(args, root)
    image = load_image_identity(args.image_manifest)
    verify_current_worker(image, implementation)
    if direct_parent_backend(image) != "torch_cpu":
        raise ValueError(
            spec.prefix + " direct practice needs the PyTorch CPU worker image"
        )
    if not doctor(image_id=image.image_id, image_identity=image).eligible:
        raise ValueError("accepted numerical host unavailable")
    analysis = load_analysis_image(args.analysis_image_manifest)
    verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise ValueError("analysis/trusted image parent differs")
    declared = frozen["runtime"] if frozen is not None else product.runtime
    julia_image = host_julia_image(root, declared, analysis)
    runtime = research_runtime(
        spec,
        declared,
        implementation=implementation,
        images=[image.image_id, analysis.image_id],
        julia_image=julia_image,
    )
    if declared != runtime:
        raise ValueError(
            "configured runtime differs from the " + spec.prefix + " runtime"
        )

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
    signer = miner_signer(public, getattr(args, "signer_socket", None))
    session = root / "research-auth"
    session.mkdir(mode=0o700, exist_ok=True)
    connection = LocalMinerConnection(
        session, args.image_manifest, config.context, config.publisher_hotkey, signer
    )
    owner = await requester(connection)
    if (root / "campaign-complete.json").exists():
        report(ledger, owner=owner)
        return None
    if frozen is None:
        manifest = manifest_document(
            spec,
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
            raise ValueError(spec.prefix + " campaign owner changed")
        check_attached(
            spec,
            manifest,
            implementation=implementation,
            images=runtime["images"],
            julia_image=julia_image,
        )
    ledger.freeze(manifest)
    composition = None
    try:
        composition, wrapper = compose(
            spec,
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
        key=signer,
        config=config,
        composition=composition,
        sdk=sdk,
        task=None,
        grant=None,
        agent_policy=getattr(args, "agent_policy", None),
        campaign=campaign,
        challenge=key,
        selection=selection,
    )


def direct_target(spec, args):
    """The signed construction receiver this campaign submits to: the
    profile's per-Challenge intake and receiver (for exactly this version,
    when the profile names it per version), else its direct target."""
    from carbon.development_session.intake_targets import args_for_version, validate

    args = args_for_version(args, spec.challenge_id, research_key(spec).version)
    url = (getattr(args, "intakes", None) or {}).get(spec.challenge_id)
    hotkey = (getattr(args, "receivers", None) or {}).get(spec.challenge_id)
    if url is not None and hotkey is not None:
        return validate([{"intake_url": url, "receiver_hotkey": hotkey}])[0]
    target = getattr(args, "direct_intake_target", None)
    return None if target is None else validate([target])[0]


async def evaluate_frozen(spec, prepared, epoch, strategy, *, record):
    """Submit the frozen recipe to the signed construction receiver, which
    rebuilds and judges it, and store its feedback once (`record`)."""
    import asyncio

    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.development_session.direct_submission import (
        DirectConstructionPending,
        DirectIntakeRefusal,
        read_exam_feedback,
        submit_and_wait,
    )
    from carbon.development_session.research_campaign import OperationRefused
    from carbon.reconstruction.served_recipe_contract import registered

    key = research_key(spec)
    ledger, owner = prepared.ledger, prepared.owner
    folder = ledger.root / ("epoch-" + str(epoch))
    frozen = json.loads((folder / "selected-recipe.json").read_bytes())
    if frozen["strategy"] != strategy:
        raise ValueError("submitted strategy differs from the frozen candidate")
    target = direct_target(spec, prepared.args)
    if target is None:
        raise OperationRefused("construction_intake_unconfigured")
    recipe = ConstructionRecipe.from_dict(strategy)
    contract = registered(key.challenge_id, key.version)
    connection = prepared.sdk.connection
    try:
        result = await asyncio.to_thread(
            submit_and_wait,
            target["intake_url"],
            connection.miner_key,
            root=ledger.root,
            epoch=epoch,
            recipe=recipe,
            contract_digest=contract.digest,
            receiver=target["receiver_hotkey"],
            context=connection.chain_context,
        )
        ladder = await asyncio.to_thread(
            read_exam_feedback,
            target["intake_url"],
            connection.miner_key,
            recipe=recipe,
            contract_digest=contract.digest,
            receiver=target["receiver_hotkey"],
            context=connection.chain_context,
        )
    except DirectConstructionPending:
        raise OperationRefused("evaluation_queued") from None
    except DirectIntakeRefusal as refused:
        raise OperationRefused(refused.code) from None
    except OSError:
        raise OperationRefused("construction_intake_unavailable") from None
    feedback = {
        "schema": spec.feedback_schema,
        "challenge": {"id": key.challenge_id, "version": key.version},
        "recipe_digest": recipe.digest,
        "result": result,
        "exam_feedback": ladder,
    }
    record(ledger, owner, epoch, feedback)
    return feedback


def record_verdict(ledger, owner, epoch, feedback):
    """Store an epoch's permitted feedback once, as Motor and Cooling do."""
    from carbon.development_session.data import write_once
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_report import report

    write_once(
        ledger.root / ("epoch-" + str(epoch)) / "permitted-final-feedback.json",
        canonical(feedback),
    )
    report(ledger, owner=owner)


def agent_observation(spec, prepared, epoch, feedback):
    from carbon.challenge_registry import describe
    from carbon.challenge_registry.direct import graph_recipe
    from carbon.development_session.research_tools import frozen_tools_rule

    key = research_key(spec)
    document = describe(key.challenge_id, key.version)
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
            "read_with": "public_material capabilities",
        },
        **extra,
        "scaffold_recipe": control(spec),
        "graph_recipe_template": graph_recipe(spec, version=key.version),
        "scaffold_basis": "An unexecuted template; it has no measured result.",
        "epoch": epoch,
        "prior_permitted_evaluation_feedback": feedback,
        "run_plan": prepared.manifest["provider"],
        "miner_budget": {
            name: prepared.manifest[name]
            for name in ("ceilings", "elapsed_seconds", "final_reserve")
            if name in prepared.manifest
        }
        or None,
        "instructions": (
            "Use public practice and freeze only a recipe Carbon can rebuild. "
            "Submit the frozen recipe to the signed construction receiver, "
            "which rebuilds and judges it."
        ),
    }
