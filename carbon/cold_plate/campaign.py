"""Launchpad campaign adapter for cold-plate construction.

Cooling 1.0 (Level 0) exposes public construction and practice. Its official
evaluation remains fail closed until the separate Challenge-neutral validator
ticket registers a cooling adapter; a refused submit therefore retains its
frozen candidate instead of manufacturing a score.

Cooling 1.2, the backbone-catalog version (OWNER-BACKBONE-CATALOG-01, as Motor
1.2/1.3): direct catalog recipes, PyTorch CPU practice through the receiver's
own build, submit through the signed construction receiver. The same code
serves it under its research key (`contracts.keyed`); 1.0 is unchanged.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from carbon.challenge_kit import version_registry
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
PRACTICE_PROVENANCE = "COLD_PLATE_PUBLIC_PRACTICE"
BACKENDS = ("numpy",)
RUNTIME_KEYS = frozenset(
    {"implementation", "images", "authored_research", "gpu_research"}
)
#: The backbone-catalog versions. Each serves exactly its own version, by its
#: research key.
#: 1.4 is graph route v2: 1.3 plus Carbon's graph training adapter v2. Read
#: from the version registry: every Cooling version whose campaign is catalog.
CATALOG_VERSIONS = version_registry.versions("chip-cold-plate", campaign="catalog")


def _key():
    from .contracts import research_key

    return research_key()


def _catalog():
    return _key().version in CATALOG_VERSIONS


def _contract_digest():
    if _catalog():
        from carbon.reconstruction.served_recipe_contract import registered

        return registered(CHALLENGE.challenge_id, _key().version).digest
    from carbon.reconstruction.capability_registry import contract_digest

    return contract_digest(CHALLENGE.challenge_id)


def _control():
    if _catalog():
        from carbon.challenge_registry.cold_plate import catalog_recipe

        return catalog_recipe(version=_key().version)
    from .research import SCAFFOLD

    return SCAFFOLD


def _refuse_empty_catalog():
    """A catalog campaign with nothing to practise is refused before anything
    is frozen, connected or charged: no Cooling entry is tested yet (each
    needs its own Cooling pair-identity receipt)."""
    from carbon.backbone_catalog import listing

    if not listing.entries(CHALLENGE.challenge_id, _key().version):
        raise ValueError(
            "cooling " + _key().version + " serves no tested backbone yet "
            "(cooling_catalog_empty)"
        )


def manifest_document(
    product, *, owner, implementation, images, selection=None, graphite=None
):
    from carbon.development_session.research_ledger import VERSION

    from .research import objective

    return {
        "schema": VERSION,
        "campaign_id": product.campaign_id,
        "authority": "OWNER-GRAPHITE-TEST-WAVE-01",
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "owner": owner,
        "implementation": implementation,
        "objective": objective(),
        "contract_digest": _contract_digest(),
        "sampling": {"practice": "100 fixed public PRACTICE cases"},
        "control": _control(),
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
        **({"construction_mode": "direct"} if _catalog() else {}),
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


def research_runtime(declared, *, implementation, images, julia_image, gpu_image=None):
    extra = set(declared) - RUNTIME_KEYS
    if extra:
        raise ValueError(
            "cold-plate has no research composition for " + ", ".join(sorted(extra))
        )
    runtime = {"implementation": implementation, "images": images}
    if julia_image is not None and "authored_research" in declared:
        from carbon.development_session.julia_analysis import authored_julia_scope

        runtime["authored_research"] = [authored_julia_scope(julia_image)]
    # One shared GPU path (catalog_gpu): declared, never per Challenge.
    from carbon.development_session.catalog_gpu import with_gpu

    runtime = with_gpu(runtime, declared, _key().challenge_id, gpu_image)
    return runtime


def check_attached(
    manifest, *, implementation, images, julia_image=None, gpu_image=None
):
    from .research import objective

    expected = {
        "implementation": implementation,
        "images": images,
        "objective": objective(),
        "contract_digest": _contract_digest(),
        "challenge": {"id": _key().challenge_id, "version": _key().version},
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise ValueError("cold-plate campaign " + field + " changed")
    frozen = manifest.get("runtime")
    if type(frozen) is not dict or frozen != research_runtime(
        frozen,
        implementation=implementation,
        images=images,
        julia_image=julia_image,
        gpu_image=gpu_image,
    ):
        raise ValueError("campaign runtime differs from the cold-plate runtime")


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

    from .research import ColdPlatePractice, make_cold_plate_research_service

    if remote is not None:
        raise ValueError("cold-plate Level 0 offers CPU practice only")
    if _catalog():
        from .catalog_practice import CoolingCatalogPractice

        # The campaign's PyTorch CPU worker is the parent of every catalog
        # bundle's child; children are installed by `backbone_catalog.pipeline
        # install` into the owner's library cache beside the campaigns.
        practice = CoolingCatalogPractice(
            ledger=ledger,
            owner=owner,
            parent=image,
            cache_root=ledger.root.parent / ".direct-development" / "library-cache",
            root=REPOSITORY,
            version=_key().version,
            runner=runner,
        )
    else:
        practice = ColdPlatePractice(
            ledger=ledger,
            owner=owner,
            image=image,
            root=REPOSITORY,
            runner=runner,
            backend=backend,
        )
    if gpu_image is not None:
        # The catalog practice's GPU builds (shared GPU path, S3).
        if not _catalog():
            raise ValueError("cold-plate Level 0 offers CPU practice only")
        practice.gpu_image = gpu_image
    composition = make_cold_plate_research_service(
        root=ledger.root / "research-tasks",
        ledger=ledger,
        owner=owner,
        image=analysis,
        practice=practice,
        demand=demand,
        cleanup_only=cleanup_only,
        julia_image=julia_image,
        version=_key().version,
    )
    base = connection.service.gateway
    gateway = AuthenticatedGateway(
        base.context,
        _key(),
        base.receiver,
        base.adapter,
        base.verifier,
        base.journal,
        clock_ns=base.clock_ns,
    )
    return composition, AuthenticatedResearchService(
        gateway, {owner: composition.service}
    )


async def prepare_cold_plate(args, *, ledger=None, campaign):
    """Prepare a registered cold-plate product campaign and public research."""
    from carbon.chain.external_signer import miner_signer
    from carbon.chain.models import CARBON_NETUID
    from carbon.compute.retired import refuse_rented
    from carbon.development_session.data import write_once
    from carbon.development_session.miner_network import binding_for
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_campaign import (
        PreparedCampaign,
        campaign_implementation,
        new_plan_elapsed_seconds,
        new_plan_input_default,
        new_plan_output_default,
        new_plan_timeout_default,
        new_plan_transport,
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
        raise ValueError("a cold-plate campaign is a product campaign")
    refuse_rented(frozen.get("runtime") if frozen is not None else product.runtime)
    ledger = ledger if ledger is not None else CampaignLedger(root)
    if ledger.root != root or ledger.admission is not None:
        raise ValueError("a cold-plate campaign never consumes a development grant")
    if _catalog():
        _refuse_empty_catalog()

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
                timeout_default=new_plan_timeout_default(args),
                transport=new_plan_transport(args),
                elapsed_seconds=new_plan_elapsed_seconds(args),
                input_default=new_plan_input_default(args, agent),
            )
            if agent == "graphite":
                from carbon.agent_campaign.graphite.miner.driver import freeze_launch

                graphite = freeze_launch(
                    args,
                    root,
                    challenge={
                        "id": _key().challenge_id,
                        "version": _key().version,
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

    implementation = campaign_implementation(args, root)
    image = load_image_identity(args.image_manifest)
    verify_current_worker(image, implementation)
    if _catalog():
        from carbon.development_session.gpu_practice import direct_parent_backend

        if direct_parent_backend(image) != "torch_cpu":
            raise ValueError(
                "cooling catalog practice needs the PyTorch CPU worker image"
            )
    if not doctor(image_id=image.image_id, image_identity=image).eligible:
        raise ValueError("accepted numerical host unavailable")
    analysis = load_analysis_image(args.analysis_image_manifest)
    verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise ValueError("analysis/trusted image parent differs")
    declared = frozen["runtime"] if frozen is not None else product.runtime
    julia_image = host_julia_image(root, declared, analysis)
    from carbon.development_session.catalog_gpu import registered_gpu_image

    gpu_image = registered_gpu_image(root, declared, _key().challenge_id)
    runtime = research_runtime(
        declared,
        implementation=implementation,
        images=[image.image_id, analysis.image_id],
        julia_image=julia_image,
        gpu_image=gpu_image,
    )
    if declared != runtime:
        raise ValueError("configured runtime differs from the cold-plate runtime")

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
            raise ValueError("cold-plate campaign owner changed")
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
        challenge=_key(),
        selection=selection,
    )


def _direct_target(args):
    """The signed construction receiver this campaign submits to: the
    profile's per-Challenge intake and receiver (for exactly this version,
    when the profile names it per version), else its direct target."""
    from carbon.development_session.intake_targets import args_for_version, validate

    args = args_for_version(args, CHALLENGE.challenge_id, _key().version)
    url = (getattr(args, "intakes", None) or {}).get(CHALLENGE.challenge_id)
    hotkey = (getattr(args, "receivers", None) or {}).get(CHALLENGE.challenge_id)
    if url is not None and hotkey is not None:
        return validate([{"intake_url": url, "receiver_hotkey": hotkey}])[0]
    target = getattr(args, "direct_intake_target", None)
    return None if target is None else validate([target])[0]


async def evaluate_frozen(prepared, epoch, strategy):
    """1.0: the scoring adapter is deliberately absent (fail closed). The
    catalog version submits the frozen recipe to the signed construction
    receiver, which rebuilds and judges it, and stores its feedback."""
    import asyncio

    from carbon.development_session.research_campaign import OperationRefused

    if not _catalog():
        raise OperationRefused("cooling_validator_not_served")
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.development_session.direct_submission import (
        DirectConstructionPending,
        DirectIntakeRefusal,
        read_exam_feedback,
        submit_and_wait,
    )
    from carbon.reconstruction.served_recipe_contract import registered

    ledger, owner = prepared.ledger, prepared.owner
    folder = ledger.root / ("epoch-" + str(epoch))
    record = json.loads((folder / "selected-recipe.json").read_bytes())
    if record["strategy"] != strategy:
        raise ValueError("submitted strategy differs from the frozen candidate")
    target = _direct_target(prepared.args)
    if target is None:
        raise OperationRefused("construction_intake_unconfigured")
    recipe = ConstructionRecipe.from_dict(strategy)
    contract = registered(CHALLENGE.challenge_id, _key().version)
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
        "schema": "carbon.cold-plate.permitted-feedback.v1",
        "challenge": {"id": CHALLENGE.challenge_id, "version": _key().version},
        "recipe_digest": recipe.digest,
        "result": result,
        "exam_feedback": ladder,
    }
    record_verdict(ledger, owner, epoch, feedback)
    return feedback


def record_verdict(ledger, owner, epoch, feedback):
    """Store an epoch's permitted feedback once, as Motor and Battery do."""
    from carbon.development_session.data import write_once
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_report import report

    write_once(
        ledger.root / ("epoch-" + str(epoch)) / "permitted-final-feedback.json",
        canonical(feedback),
    )
    report(ledger, owner=owner)


def agent_observation(prepared, epoch, feedback):
    from carbon.challenge_registry import describe
    from carbon.development_session.research_tools import frozen_tools_rule

    document = describe(_key().challenge_id, _key().version)
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
        "scaffold_recipe": _control(),
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
            + (
                "Submit the frozen recipe to the signed construction receiver, "
                "which rebuilds and judges it."
                if _catalog()
                else "Submission evaluation remains unavailable until its "
                "adapter is registered."
            )
        ),
    }
