"""Finite trusted autoresearch controller. No public-network write capability.

run creates one new campaign; resume reuses its exact immutable inputs. Unknown
side effects stop, and completed source handoffs are resolved without rerunning.
reconcile settles a model call whose outcome is unknown at its full
reservation, so a later resume sends it again under a fresh identity.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import dataclasses
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from carbon import research
from carbon.chain.auth import BittensorMessageSigner
from carbon.chain.external_signer import miner_signer
from carbon.chain.models import CARBON_NETUID
from carbon.development_testnet.operator import load_config
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity
from carbon.transport.models import message

from . import research_guidance as guidance
from .data import write_once
from .gpu_research import PublicGPUPractice, registered_gpu_image
from .model_provider import (
    INPUT_DEFAULT_V2,
    INPUT_DEFAULTS,
    MODEL,
    OUTPUT_DEFAULT_V2,
    OUTPUT_DEFAULTS,
    SelectionTransport,
    check_budget,
    select,
    selection_from_record,
)
from .model_provider import ProviderTransport as ResponsesTransport
from .profile import CHALLENGE, canonical, digest
from .research_agent_policy import AUTONOMOUS, LEGACY, binding
from .research_catalog import compile_recipe
from .research_data import PublicReferenceData
from .research_final import prepare_final_inputs
from .research_generation import generate_roles
from .research_image import load_analysis_image, verify_image
from .research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    PRODUCT,
    VERSION,
    CampaignLedger,
)
from .research_loop import run_epoch
from .research_material import PublicMaterial, capabilities, objective
from .research_numerical import CampaignDerivedMeasurements
from .research_profile import document
from .research_provider import PublicPractice
from .research_report import report
from .research_service import make_research_service
from .research_tools import ResearchMinerTools
from .service import LocalMinerConnection

CONTROL = {
    "schema_version": "1.0",
    "challenge_id": CHALLENGE.challenge_id,
    "backbone": "fno",
    "parameters": {
        "steps": 512,
        "width": 32,
        "depth": 3,
        "n_modes": 16,
        "hard_initial_condition": True,
        "enforce_mean": True,
        "batch_size": 8,
        "learning_rate": 0.002,
        "inference_weights": "ema",
    },
}
CONTROL_BASIS = "Prospective moderate FNO control: 32 channels, three layers, 16 spectral modes, 512 update target, AdamW/cosine and EMA; hard initial field and conserved mean. This uses the same public TRAIN and final execution ceilings. No quality claim or equal search-compute claim; compared with actual agent research costs separately."


def accepted_implementation(revision):
    repo = Path(__file__).resolve().parents[2]

    def git(*args):
        return subprocess.check_output(
            ["git", *args], cwd=repo, text=True, timeout=30
        ).strip()

    head = git("rev-parse", "HEAD")
    if (
        head != revision
        or len(revision) != 40
        or git("status", "--porcelain", "--untracked-files=no")
    ):
        raise ValueError("campaign requires the exact clean accepted revision")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision, "origin/main"],
        cwd=repo,
        timeout=30,
        check=False,
    ).returncode:
        raise ValueError("accepted revision is not in fetched main")
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", "HEAD"], cwd=repo, timeout=30
    )
    return {
        "revision": head,
        "tree": git("rev-parse", "HEAD^{tree}"),
        "source_tree_digest": digest(archive),
    }


def verify_current_worker(image, implementation):
    if image.source_tree_digest != implementation["source_tree_digest"]:
        raise ValueError(
            "trusted worker must be built from this exact accepted source revision"
        )


def private_file(path):
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_mode & 0o077
        or path.parent.stat().st_mode & 0o077
    ):
        raise ValueError("owner-only private input required")
    return path


def trust(connection):
    key = connection.signer.verification_key
    return {
        "evidence_ledger": str(connection.root / "evidence.sqlite3"),
        "transport_journal": str(connection.root / "transport.sqlite3"),
        "transport_context": dataclasses.asdict(connection.chain_context),
        "verification_keys": [
            {
                "key_id": key.key_id,
                "public_key_hex": key.public_key.hex(),
                "valid_from_micros": key.valid_from_micros,
                "valid_until_micros": key.valid_until_micros,
                "revoked_at_micros": key.revoked_at_micros,
            }
        ],
    }


async def requester(connection):
    snapshot = await connection.check_registration()
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(CHALLENGE),
    )
    body = message(
        connection.chain_context,
        snapshot.snapshot_id,
        CHALLENGE,
        session="carbon-autoresearch",
        # A fresh request per preparation. Every manual operation and every
        # resume prepares the campaign again, and its receipt journal refuses
        # a reused request id whose body differs (a later registration
        # snapshot) as TRANSPORT_CONFLICT, and an identical one as a replay.
        # The requester comes from the verified hotkey, not this id.
        request="bootstrap-research-owner-" + uuid.uuid4().hex,
        tool=research.RESEARCH_NAMESPACE,
        fields={
            "call_base64": base64.b64encode(research.canonical_bytes(call)).decode()
        },
    )
    headers = BittensorMessageSigner(connection.miner_key).sign(
        body, receiver=connection.publisher, nonce_ns=time.time_ns()
    )
    received = await connection.service.gateway.receive(body, headers)
    return received.requester.value


def frozen_seeds(root):
    path = root / "private-final-seeds.json"
    if not path.exists():
        write_once(
            path,
            canonical(
                {
                    str(e): {
                        label: [os.urandom(32).hex() for _ in range(3)]
                        for label in ("baseline", "challenger")
                    }
                    for e in (1, 2)
                }
            ),
        )
    value = json.loads(path.read_bytes())
    flat = [
        bytes.fromhex(s)
        for epoch in value.values()
        for row in epoch.values()
        for s in row
    ]
    if len(flat) != 12 or len(set(flat)) != 12 or any(len(v) != 32 for v in flat):
        raise ValueError("exact twelve distinct pre-search seeds required")
    return value


def practice_provenances():
    """Service-produced practice provenances that can support selection.

    The historical Burgers value is retained explicitly.  Current Challenge
    values come from their campaign adapters rather than this shared workflow.
    """
    from carbon.challenge_registry.campaigns import practice_provenances as current

    return frozenset({"REAL_JAX_PUBLIC_PRACTICE"}) | current()


def trial_supports_selection(ledger, owner, strategy):
    with ledger.db() as db:
        rows = db.execute(
            "SELECT body,digest FROM research_results WHERE owner=?", (owner,)
        ).fetchall()
    for body, fingerprint in rows:
        if digest(body) != fingerprint:
            raise ValueError("retained practice result changed")
        result = json.loads(body)
        if (
            result.get("provenance") in practice_provenances()
            and result.get("recipe") == strategy
        ):
            return True
    return False


async def final_epoch(
    args,
    ledger,
    owner,
    epoch,
    strategy,
    seeds,
    role_root,
    public_data,
    image,
    key,
    config,
):
    ledger.checkpoint()
    from carbon.development_comparison.acceptance import (
        DevelopmentAcceptanceRef,
        create_report,
        register_fresh_research,
        resolve_acceptance,
    )
    from carbon.orchestration.development_feedback import project_development_acceptance

    root = ledger.root / ("epoch-" + str(epoch)) / "final"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    complete = root / "comparison-ref.json"
    if complete.exists():
        saved = json.loads(complete.read_bytes())
        ref = DevelopmentAcceptanceRef(
            Path(saved["root"]), saved["registration_digest"], saved["report_digest"]
        )
        return project_development_acceptance(ref), ref
    final_data = PublicReferenceData(
        ledger=ledger, owner=owner, image=image, role_root=role_root, phase="final"
    )
    connections = []
    for label, recipe in (("baseline", CONTROL), ("challenger", strategy)):
        print(f"Epoch {epoch}: preparing frozen {label} final inputs", flush=True)
        bound = prepare_final_inputs(
            root=root / label,
            role_root=role_root,
            epoch=epoch,
            ledger=ledger,
            owner=owner,
            strategy=recipe,
            randomness=tuple(bytes.fromhex(v) for v in seeds[str(epoch)][label]),
            public_data=public_data,
            final_data=final_data,
            image=image,
        )
        connection = LocalMinerConnection(
            bound.root,
            args.image_manifest,
            config.context,
            config.publisher_hotkey,
            key,
            research_inputs=bound,
        )
        connections.append(connection)
    comparison = root / "comparison"
    pinfile = root / "registration-pin.json"
    if pinfile.exists():
        pin = json.loads(pinfile.read_bytes())["digest"]
    elif (comparison / "scoring-registration.json").exists():
        # Signing completed before an interrupted pointer write; no new registration.
        pin = digest((comparison / "scoring-registration.json").read_bytes())
        write_once(pinfile, canonical({"digest": pin}))
    else:
        pin = register_fresh_research(
            comparison,
            prepared_roots=tuple(c.root for c in connections),
            quarantine_journal=args.quarantine_journal,
            reference_root=ledger.root,
            sessions={str(c.root): trust(c) for c in connections},
        )
        write_once(pinfile, canonical({"digest": pin}))
    sources = []
    for connection, label, recipe in zip(
        connections, ("baseline", "challenger"), (CONTROL, strategy), strict=True
    ):
        ledger.checkpoint()
        existing = list(connection.root.glob("source-*.json"))
        intent = connection.root / "final-submit-intent.json"
        if existing:
            if len(existing) != 1:
                raise ValueError("ambiguous final source set")
            sources.append(existing[0])
            continue
        if intent.exists():
            raise ValueError(
                "final submission interrupted; reconcile original C-08/C-03 journals without reexecution"
            )
        write_once(
            intent,
            canonical(
                {
                    "strategy_digest": digest(canonical(recipe)),
                    "epoch": epoch,
                    "role": label,
                }
            ),
        )
        print(
            f"Epoch {epoch}: independently reconstructing {label}, three replicas",
            flush=True,
        )
        await connection.call(
            "submit",
            {
                "challenge_id": CHALLENGE.challenge_id,
                "challenge_version": CHALLENGE.version,
                "strategy": recipe,
            },
        )
        existing = list(connection.root.glob("source-*.json"))
        if len(existing) != 1:
            raise ValueError("exact signed final source missing")
        sources.append(existing[0])
    print(f"Epoch {epoch}: signed comparison and reference refinement", flush=True)
    if (comparison / "development-acceptance.json").exists():
        ref = DevelopmentAcceptanceRef(
            comparison,
            pin,
            digest((comparison / "development-acceptance.json").read_bytes()),
        )
    else:
        ref = create_report(
            comparison,
            pin,
            *sources,
            image=image,
            resume_completed=(comparison / "derived-measurements/output.json").exists(),
            research_runner=CampaignDerivedMeasurements(ledger=ledger, owner=owner),
        )
    resolve_acceptance(ref)
    write_once(
        complete,
        canonical(
            {
                "root": str(ref.root),
                "registration_digest": ref.registration_digest,
                "report_digest": ref.report_digest,
            }
        ),
    )
    return project_development_acceptance(ref), ref


def frozen_parallel_calls(manifest):
    """The parallel tool call rule the campaign froze in its provider plan,
    or None: a plan frozen before the rule existed keeps the historical one."""
    plan = manifest.get("provider") if type(manifest) is dict else None
    return plan.get("parallel_calls") if type(plan) is dict else None


def frozen_miner_guidance(manifest):
    """The miner-message rule the campaign froze in its provider plan, or
    None: a campaign launched before RSURF-D13 reads no messages, and nothing
    about it is reinterpreted."""
    plan = manifest.get("provider") if type(manifest) is dict else None
    return plan.get("miner_guidance") if type(plan) is dict else None


def registered_julia_image(root, runtime, analysis):
    """Read the campaign's image record; the caller still verifies its authority.

    A product campaign's record is installed at launch from the miner's own
    profile; a development grant campaign's is written by its operator. Either
    way the record grants nothing: the declared runtime must name this exact
    scope, and the campaign's authority is re-read on every call.
    """
    if "authored_research" not in runtime:
        return None
    from .julia_analysis import (
        authored_julia_scope,
        load_julia_analysis_image,
        verify_julia_image,
    )
    from .private_records import private_json

    path = root / "authored-julia-image.json"
    private_json(path)
    image = load_julia_analysis_image(path)
    if image.parent != analysis or runtime["authored_research"] != [
        authored_julia_scope(image)
    ]:
        raise ValueError("authored Julia operator image or scope differs")
    return verify_julia_image(image)


def available_julia_image(root, analysis):
    """The Julia image installed for this campaign, if any, verified."""
    from .julia_analysis import load_julia_analysis_image, verify_julia_image
    from .private_records import private_json

    path = root / "authored-julia-image.json"
    if not path.exists():
        return None
    private_json(path)
    image = load_julia_analysis_image(path)
    if image.parent != analysis:
        raise ValueError("authored Julia image does not extend this analysis image")
    return verify_julia_image(image)


def research_practice(root, manifest, *, data, role_root, ledger, owner, image):
    """Which runtime the miner's own research runs on.

    Named rather than inlined because it is the one place a campaign decides
    between the CPU and GPU research callbacks, and the decision is worth being
    able to test on its own.

    The choice is made by the frozen manifest's runtime and nothing else: a
    campaign that declares no GPU runtime gets exactly the callback it always
    got. It also decides *only* this. The final DEVELOPMENT comparison keeps its
    own CPU worker image, reference material and accounting, so a miner choosing
    a GPU to research with never chooses or rewrites the evaluator that judges
    the result.
    """
    gpu_image = registered_gpu_image(root, manifest.get("runtime", {}), role_root)
    if gpu_image is None:
        return PublicPractice(data=data, ledger=ledger, owner=owner, image=image)
    return PublicGPUPractice(data=data, image=gpu_image)


async def prepare(args, *, ledger=None):
    """Prepare a campaign for the Challenge it is bound to.

    The Challenge's campaign comes from `challenge_registry.campaigns`, resolved
    exactly; this module names no Challenge-specific path of its own.
    """
    from carbon.challenge_registry.campaigns import campaign_challenge, campaign_for

    campaign = campaign_for(campaign_challenge(args))
    return await campaign.prepare(args, ledger=ledger, campaign=campaign)


async def prepare_burgers(args, *, ledger=None, campaign):
    """Everything a campaign needs before anyone selects: verified images and
    keys, the registration read, the frozen manifest and ledger, generated
    roles and the research service a miner or agent works through.

    Returns a `PreparedCampaign`, or None for a campaign already complete.
    Idempotent on resume: a frozen manifest is checked, never rewritten.
    """
    agent_policy = getattr(args, "agent_policy", LEGACY)
    policy = binding(agent_policy)
    selection = campaign_selection(args)
    supplied_guidance = getattr(args, "research_guidance", None)
    task = guidance.bind(supplied_guidance) if supplied_guidance is not None else None
    manifest_path = args.root / "campaign-manifest.json"
    if manifest_path.exists():
        frozen_manifest = json.loads(manifest_path.read_bytes())
        frozen_task = guidance.verify(frozen_manifest.get("research_guidance"))
        if hasattr(args, "research_guidance") and task != frozen_task:
            raise ValueError("frozen research guidance differs")
        task = frozen_task
        if (
            task is not None
            and frozen_manifest.get("agent_policy", binding(LEGACY)) != policy
        ):
            raise ValueError("guided campaign policy differs")
        if task is not None:
            guidance.verify_history(
                args.root, task, policy, guidance.context(frozen_manifest)
            )
    implementation = accepted_implementation(args.accepted_revision)
    root = args.root
    if args.command == "run" and (root / "campaign-manifest.json").exists():
        raise ValueError("campaign already exists; use resume")
    if args.command == "resume" and not (root / "campaign-manifest.json").exists():
        raise ValueError("no frozen campaign to resume")
    ledger = ledger if ledger is not None else CampaignLedger(root)
    if ledger.root != root:
        raise ValueError("campaign ledger root differs")
    image = load_image_identity(args.image_manifest)
    verify_current_worker(image, implementation)
    eligibility = doctor(image_id=image.image_id, image_identity=image)
    if not eligibility.eligible:
        raise ValueError("accepted numerical host unavailable")
    analysis = load_analysis_image(args.analysis_image_manifest)
    verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise ValueError("analysis/trusted image parent differs")
    grant = None
    authored = None
    product = getattr(args, "product", None)
    frozen_product = None
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_bytes())
        if existing.get("schema") == PRODUCT:
            frozen_product = existing
    if product is not None or frozen_product is not None:
        # A product campaign (C-MLP-02-D11): admitted by registration, never by
        # a grant. The runtime is the one the miner's profile declared - read
        # from the launch the first time and from the frozen manifest after -
        # and the composed runtime must equal it exactly, as it had to equal a
        # grant's.
        if ledger.admission is not None:
            raise ValueError("a product campaign never consumes a development grant")
        declared = (
            frozen_product["runtime"] if frozen_product is not None else product.runtime
        )
        runtime = {
            "implementation": implementation,
            "images": [image.image_id, analysis.image_id],
        }
        authored = registered_julia_image(root, declared, analysis)
        if authored is not None:
            from .julia_analysis import authored_julia_scope

            runtime["authored_research"] = [authored_julia_scope(authored)]
        else:
            # Anytime: a product campaign uses whichever Julia image the host
            # has installed for it, declared or not. It is not part of the
            # frozen runtime; each run's contract records exactly what ran.
            authored = available_julia_image(root, analysis)
        if "gpu_research" in declared:
            from .gpu_research import declared_gpu_runtime

            runtime["gpu_research"] = declared_gpu_runtime(declared)
        if runtime != declared:
            raise ValueError("configured runtime differs from the accepted runtime")
    elif ledger.admission is not None:
        runtime = {
            "implementation": implementation,
            "images": [image.image_id, analysis.image_id],
        }
        authored = registered_julia_image(
            root, ledger.admission.document["runtime"], analysis
        )
        if authored is not None:
            from .julia_analysis import authored_julia_scope

            runtime["authored_research"] = [authored_julia_scope(authored)]
        if "gpu_research" in ledger.admission.document["runtime"]:
            from .gpu_research import declared_gpu_runtime

            # Shape only, and only so the composed runtime can be compared with
            # the granted one before role generation is charged for. The scope's
            # content binds this campaign's public TRAIN material, so it is
            # recomputed and checked further down, once that material exists.
            runtime["gpu_research"] = declared_gpu_runtime(
                ledger.admission.document["runtime"]
            )
        grant = ledger.admission.verify(
            root=root,
            principal=args.principal,
            runtime=runtime,
            now=ledger.clock(),
        )
    # The model-provider key belongs to Carbon's agent. A campaign with no
    # agent - a person driving their own journey - calls no model, so it is
    # never asked for one.
    agent = (
        frozen_product.get("agent", "autonomous")
        if frozen_product is not None
        else (product.agent if product is not None else "autonomous")
    )
    if agent != "none":
        private_file(args.api_key_file)
        if selection.is_historical_default:
            ResponsesTransport(args.api_key_file)
        else:
            SelectionTransport(selection)
    if grant is not None and grant["provider"] != selection.provider_id:
        raise ValueError("the grant names a different model provider")
    if getattr(args, "operator_config", None) is not None:
        config = load_config(args.operator_config)
    else:
        from .miner_network import binding_for

        config = binding_for(args)
    public = json.loads(private_file(args.miner_public).read_bytes())
    if public["netuid"] != CARBON_NETUID or config.netuid != CARBON_NETUID:
        raise ValueError(f"existing subnet {CARBON_NETUID} context required")
    if grant is not None and public["hotkey"] != grant["miner_identity"]:
        raise ValueError("grant miner identity differs")
    registered = (
        frozen_product["admission"]["hotkey"]
        if frozen_product is not None
        else (str(product.miner.hotkey) if product is not None else None)
    )
    if registered is not None and public["hotkey"] != registered:
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
    seeds = frozen_seeds(root)
    manifest_path = root / "campaign-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_bytes())
        if (
            manifest["implementation"] != implementation
            or manifest["owner"] != owner
            or manifest["images"] != [image.image_id, analysis.image_id]
            or manifest.get("agent_policy", binding(LEGACY)) != policy
        ):
            raise ValueError("campaign implementation/owner/image changed")
    else:
        manifest = {
            "schema": VERSION,
            "campaign_id": "cw1-d4-" + uuid.uuid4().hex,
            "authority": "OWNER-C-W1-D4-AUTORESEARCH-01",
            "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "owner": owner,
            "implementation": implementation,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            "objective": document(),
            "sampling": document()["sampling"],
            "control": CONTROL,
            "control_rationale": CONTROL_BASIS,
            "selection": document()["selection"],
            "replica_policy": document()["replicas"],
            "seed_commitment": digest(canonical(seeds)),
            # The miner's model selection. The historical pinned selection
            # records the exact block every earlier manifest carries.
            "provider": selection.manifest_record(),
            "images": [image.image_id, analysis.image_id],
            "new_network_transactions": 0,
        }
        if agent_policy != LEGACY:
            manifest["agent_policy"] = policy
            manifest["authority"] = "OWNER-C-W1-RESEARCH-PROGRAM-01"
        if task is not None:
            manifest["research_guidance"] = task
        if product is not None:
            # No development ceiling and no development deadline: a product
            # manifest carries the miner's budget or none at all.
            del manifest["ceilings"], manifest["elapsed_seconds"]
            manifest.update(product.manifest_fields())
        if grant is not None:
            from .research_admission import MANIFEST

            manifest.update(
                schema=MANIFEST,
                campaign_id=grant["campaign_id"],
                authority=grant["authority"],
                principal=grant["principal"],
                runtime=grant["runtime"],
                grant=ledger.admission.binding(),
                ceilings=grant["ceilings"],
                elapsed_seconds=grant["elapsed_seconds"],
            )
        check_budget(selection, manifest.get("ceilings"))
        compile_recipe(CONTROL)
        write_once(manifest_path, canonical(manifest))
    if (
        manifest["seed_commitment"] != digest(canonical(seeds))
        or manifest["objective"] != document()
        or manifest["control"] != CONTROL
    ):
        raise ValueError("prospective rule/control/seed freeze changed")
    ledger.freeze(manifest)
    print(f"Campaign directory: {root}", flush=True)
    print(
        f"python -m carbon.development_session.research_campaign status --root {root}",
        flush=True,
    )
    composition = None
    try:
        role_root = generate_roles(ledger, owner=owner, image=image)
        data = PublicReferenceData(
            ledger=ledger, owner=owner, image=image, role_root=role_root
        )
        practice = research_practice(
            root,
            manifest,
            data=data,
            role_root=role_root,
            ledger=ledger,
            owner=owner,
            image=image,
        )
        composition = make_research_service(
            julia_image=authored,
            root=root / "research-tasks",
            ledger=ledger,
            owner=owner,
            image=analysis,
            public_material=PublicMaterial(data),
            practice=practice,
        )
        wrapper = AuthenticatedResearchService(
            connection.service.gateway, {owner: composition.service}
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
        seeds=seeds,
        role_root=role_root,
        data=data,
        image=image,
        key=key,
        config=config,
        composition=composition,
        sdk=sdk,
        task=task,
        grant=grant,
        agent_policy=agent_policy,
        campaign=campaign,
        selection=selection,
    )


def supplied_selection(args, *, output_default=None, input_default=None):
    """The miner's `args.model_selection` ({provider_id, model_id, settings?,
    endpoint?, declared_pricing?, credential?}), or the pinned default when
    none is given. A file credential is the `--api-key-file` supplied at run
    time; its path is never recorded. `output_default` and `input_default`
    are how an unset output cap and input window are chosen
    (`model_provider.select`)."""
    supplied = getattr(args, "model_selection", None)
    path = getattr(args, "api_key_file", None)
    spec = (
        {"provider_id": "openai-responses", "model_id": MODEL}
        if supplied is None
        else supplied
    )
    if type(spec) is not dict:
        raise ValueError("model selection must be an object")
    credential = {"kind": "file", "reference": "unset" if path is None else str(path)}
    return select(
        **{
            "credential": credential,
            **spec,
            "output_default": output_default,
            "input_default": input_default,
        }
    )


def new_plan_input_default(args, agent):
    """How a new campaign's input window is chosen when the miner sets none.
    A Graphite miner-edition product campaign reads whole discovery documents
    on the miner's own budget, so it opens with the selected model's
    published context less its output cap (`INPUT_DEFAULT_V2`,
    OWNER-GRAPHITE-MINER-INPUT-WINDOW-01). Every other campaign keeps the
    historical 65,536."""
    if agent == "graphite" and getattr(args, "product", None) is not None:
        return INPUT_DEFAULT_V2
    return None


def new_plan_output_default(args):
    """How a new campaign's agent output cap is chosen when the miner sets
    none. A product campaign is the miner's own, on the miner's own budget,
    so its agent may use the selected model's own maximum output
    (`OUTPUT_DEFAULT_V2`, OWNER-LAUNCHPAD-PROD-02). A campaign admitted by a
    development grant keeps the historical default its grant was sized for."""
    return OUTPUT_DEFAULT_V2 if getattr(args, "product", None) is not None else None


def resolve_selection(args, record):
    """A frozen campaign's selection from its recorded block; a differing
    `model_selection` supplied on resume is refused.

    A supplied choice that sets no output cap or input window names the
    frozen one under either default: the plan recorded the values its own
    rules chose, and resolving it again under today's rules must not refuse
    an earlier plan."""
    path = getattr(args, "api_key_file", None)
    chosen = selection_from_record(
        record, credential_file=None if path is None else str(path)
    )
    if getattr(args, "model_selection", None) is not None and all(
        supplied_selection(
            args, output_default=output_rule, input_default=input_rule
        ).record()
        != chosen.record()
        for output_rule in OUTPUT_DEFAULTS
        for input_rule in INPUT_DEFAULTS
    ):
        raise ValueError("model selection differs from the frozen campaign's")
    return chosen


def campaign_selection(args):
    """The campaign's model selection (`model_provider`). A frozen campaign's
    is the one its manifest records - every campaign frozen before selection
    existed resolves to the pinned default - otherwise the miner's, with a new
    plan's output default (`new_plan_output_default`)."""
    manifest_path = args.root / "campaign-manifest.json"
    if manifest_path.exists():
        frozen = json.loads(manifest_path.read_bytes())
        return resolve_selection(args, frozen["provider"])
    return supplied_selection(args, output_default=new_plan_output_default(args))


@dataclasses.dataclass
class PreparedCampaign:
    """A prepared campaign: what freeze, submit and the agent loop act on."""

    args: object
    ledger: object
    owner: str
    manifest: dict
    seeds: dict
    role_root: Path
    data: object
    image: object
    key: object
    config: object
    composition: object
    sdk: object
    task: object
    grant: object
    agent_policy: object
    #: The Challenge's campaign (`challenge_registry.campaigns`): how this
    #: campaign's candidates are evaluated and what its agent is shown.
    campaign: object
    #: What the agent policy is bound to; None keeps the historical Burgers
    #: prompts.
    challenge: object = None
    #: The miner's model selection; None is the pinned historical default.
    selection: object = None

    @property
    def agent(self):
        """Who selects in this campaign. Campaigns frozen before the choice
        existed are the agent's."""
        return self.manifest.get("agent", "autonomous")

    def close(self):
        self.composition.tasks.close()
        report(self.ledger, owner=self.owner)


#: The only epochs with final-exam seeds committed before any search
#: (`frozen_seeds`). A campaign runs at most these final exams, whoever
#: selects: more would need seeds chosen after search began.
FINAL_EPOCHS = (1, 2)


class OperationRefused(ValueError):
    """A miner operation refused for a named, closed reason."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _complete(prepared):
    write_once(
        prepared.ledger.root / "campaign-complete.json",
        canonical(
            {
                "status": "FINITE_CAMPAIGN_STOPPED",
                "new_network_transactions": 0,
                "completed_unix": prepared.ledger.clock(),
            }
        ),
    )


async def submit_candidate(prepared, epoch, strategy):
    """The DEVELOPMENT submit of a frozen candidate, for whoever froze it.

    The candidate must have an authentic completed practice result; without
    one, the decision is noted and nothing is dispatched (returns None). The
    submit is a signed message to the local development service: nothing
    reaches the chain.
    """
    ledger, owner = prepared.ledger, prepared.owner
    if not trial_supports_selection(ledger, owner, strategy):
        ledger.note(
            owner=owner,
            kind="decision",
            body={
                "epoch": epoch,
                "stop": "selected recipe has no authentic completed practice observation; no final exam dispatched",
            },
        )
        return None
    return await prepared.campaign.evaluate(prepared, epoch, strategy)


async def submit_or_retain(prepared, epoch, strategy):
    """An agent's selection through `submit_candidate`, keeping a candidate
    the validator did not evaluate. Shared by Carbon's autonomous agent
    (`run_agent`) and Graphite's miner edition.

    Returns `(feedback, None)` - feedback None when the practice rule left
    nothing to dispatch - or, when the submit was refused before any
    evaluation (no deployment, infrastructure, queued) and the Challenge keeps
    the frozen candidate for a later submit, `(None, code)` with the
    refusal's closed code, after noting the decision. A Challenge that does
    not keep it lets the refusal propagate."""
    ledger, owner = prepared.ledger, prepared.owner
    try:
        return await submit_candidate(prepared, epoch, strategy), None
    except OperationRefused as refused:
        if not prepared.campaign.refusal_retains_candidate:
            raise
        # Nothing was evaluated (no deployment, infrastructure, queued):
        # never a result. The frozen candidate stays for a later submit.
        ledger.note(
            owner=owner,
            kind="decision",
            body={
                "epoch": epoch,
                "stop": "submission not evaluated: " + refused.code,
                "candidate_retained": True,
            },
        )
        report(ledger, owner=owner)
        return None, refused.code


async def evaluate_burgers(prepared, epoch, strategy):
    """The historical Burgers final epoch for a frozen candidate."""
    ledger, owner = prepared.ledger, prepared.owner
    feedback, ref = await final_epoch(
        prepared.args,
        ledger,
        owner,
        epoch,
        strategy,
        prepared.seeds,
        prepared.role_root,
        prepared.data,
        prepared.image,
        prepared.key,
        prepared.config,
    )
    from .research_rewards import update_simulation

    update_simulation(ledger.root, ref, epoch=epoch)
    write_once(
        ledger.root / ("epoch-" + str(epoch)) / "permitted-final-feedback.json",
        canonical(feedback),
    )
    print(
        json.dumps(
            {
                "epoch": epoch,
                "disposition": feedback["disposition"],
                "scores": feedback["scores"],
                "mandatory_failures": feedback["mandatory_failures"],
            },
            allow_nan=False,
        ),
        flush=True,
    )
    report(ledger, owner=owner)
    return feedback


def burgers_observation(prepared, epoch, feedback):
    """What Carbon's agent sees first in a historical Burgers epoch."""
    return {
        "objective": objective(),
        "capabilities": capabilities(),
        "control_recipe": CONTROL,
        "control_basis": CONTROL_BASIS,
        "epoch": epoch,
        "prior_permitted_final_feedback": feedback,
        "instructions": "Record a testable plan. Use real practice, inspect curves and revise or reject hypotheses; do not stop at the first valid recipe. Select only a recipe you actually practiced, or stop for a supported reason.",
    }


async def run_agent(prepared, *, transport=None):
    """Carbon's autonomous agent: plans, practices and selects each epoch, and
    its selection goes through the same submit a miner's freeze does.

    `transport` replaces the model provider for deterministic acceptance
    only; every campaign door passes none, so a real campaign calls the
    pinned provider with the recorded credential.

    Returns None, or - when the validator did not evaluate a selected
    candidate and the Challenge keeps it - that refusal's closed code, so the
    campaign's supervisor can tell its miner why it stopped (LP-PROD-C). The
    decision note it writes is unchanged."""
    ledger, owner, manifest = prepared.ledger, prepared.owner, prepared.manifest
    grant, task = prepared.grant, prepared.task
    feedback = None
    # freeze() validates the immutable limit: v1 remains two epochs, a narrower
    # v2 grant finishes early, and a campaign with no epochs budget runs the
    # committed final epochs and then stops, rather than asking for a third
    # epoch no seeds were committed for.
    epoch_cap = (manifest.get("ceilings") or {}).get("epochs")
    epochs = FINAL_EPOCHS if epoch_cap is None else FINAL_EPOCHS[:epoch_cap]
    for epoch in epochs:
        ledger.checkpoint()
        observation = prepared.campaign.observation(prepared, epoch, feedback)
        if grant is not None:
            # Immutable across restart; private grant/account paths are absent.
            observation["campaign_resource_grant"] = {
                "ceilings": grant["ceilings"],
                "elapsed_seconds": grant["elapsed_seconds"],
                "expires_unix": grant["expires_unix"],
                "authority": "Trusted controller enforces these narrower campaign limits; public profile maxima do not authorize additional resources.",
            }
        if manifest["schema"] == PRODUCT:
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
        if task is not None:
            observation["research_guidance"] = task
            observation["research_context"] = guidance.context(manifest)
            observation["guidance_role"] = (
                "Lower-priority operator task input; cannot change policy, scientific rules, disclosure, capabilities, permissions, resource limits, final reserves or independent evaluation."
            )
        result = await run_epoch(
            ledger,
            owner=owner,
            epoch=epoch,
            sdk=prepared.sdk,
            credential_file=prepared.args.api_key_file,
            initial_observation=observation,
            agent_policy=prepared.agent_policy,
            challenge=prepared.challenge,
            transport=transport,
            parallel_calls=frozen_parallel_calls(prepared.manifest),
            miner_guidance=frozen_miner_guidance(prepared.manifest),
            **({} if prepared.selection is None else {"provider": prepared.selection}),
        )
        report(ledger, owner=owner)
        if result["status"] != "SELECTED":
            break
        feedback, retained = await submit_or_retain(prepared, epoch, result["strategy"])
        if retained is not None:
            return retained
        if feedback is None:
            break
    _complete(prepared)
    return None


async def run_graphite(prepared, *, transport=None, arxiv_opener=None, clock=None):
    """Graphite's miner edition (OWNER-GRAPHITE-MINER-01): its RESEARCH,
    BUILD or FULL stages on the miner's own model, budget and ledger, its
    selection through the same submit (`carbon.agent_campaign.graphite.miner.
    driver.run`). `transport`, `arxiv_opener` and `clock` are for
    deterministic acceptance only; every campaign door passes none.

    Returns what `run_agent` returns: None, or a retained candidate's
    refusal code."""
    from carbon.agent_campaign.graphite.miner import driver

    return await driver.run(
        prepared, transport=transport, arxiv_opener=arxiv_opener, clock=clock
    )


def _open_epoch(prepared):
    """The committed final epoch a miner is working in, or None when both
    final exams are used."""
    for epoch in FINAL_EPOCHS:
        folder = prepared.ledger.root / ("epoch-" + str(epoch))
        if not (folder / "permitted-final-feedback.json").exists():
            return epoch
    return None


def _miner_selects(prepared):
    if prepared.agent != "none":
        raise OperationRefused("the_agent_selects_in_this_campaign")


def retained_candidate(root):
    """Whether the campaign at `root` holds a frozen candidate the validator
    has not evaluated: the open committed final epoch - the first with no
    `permitted-final-feedback.json` - has its `selected-recipe.json`. Read
    from the campaign's files, as `freeze_refusal` and the projection read
    them; False once both final exams are used."""
    for epoch in FINAL_EPOCHS:
        folder = Path(root) / ("epoch-" + str(epoch))
        if not (folder / "permitted-final-feedback.json").exists():
            return (folder / "selected-recipe.json").exists()
    return False


def waits_for_its_miner(root, manifest=None):
    """Whether the prepared, unfinished campaign at `root` waits for its
    miner - READY rather than INTERRUPTED once nothing holds it: one with no
    agent (the miner selects), or one whose agent selected a candidate the
    validator did not evaluate (`submit_or_retain`'s refusal), kept for a
    later submit. False with no frozen manifest or once complete.
    `manifest` is the campaign's frozen manifest where the caller already
    holds it (an attachment's profile); otherwise it is read from `root`.

    The one rule every settling door asks (LP-PROD-FIX-01): the campaign's
    own run, recovery after a restart, an idle settle and a detach. Until
    2026-10-04 they asked only "no agent", so an agent campaign whose submit
    was refused `evaluation_unavailable` settled INTERRUPTED with no
    interruption recorded, and a restart overwrote its refusal."""
    root = Path(root)
    if (root / "campaign-complete.json").exists():
        return False
    if manifest is None:
        path = root / "campaign-manifest.json"
        if not path.exists():
            return False
        manifest = json.loads(path.read_bytes())
    if manifest.get("agent", "autonomous") == "none":
        return True
    return retained_candidate(root)


def freeze_refusal(root, strategy):
    """Why a miner's freeze of `strategy` would be refused, read from the
    campaign's own records without preparing it - or None.

    The same rules freeze_candidate enforces; this lets a door answer at once.
    freeze_candidate still checks them itself, on the prepared campaign.
    """
    manifest_path = Path(root) / "campaign-manifest.json"
    if not manifest_path.exists():
        return "campaign_not_prepared"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("agent", "autonomous") != "none":
        return "the_agent_selects_in_this_campaign"
    epoch = None
    for candidate in FINAL_EPOCHS:
        folder = Path(root) / ("epoch-" + str(candidate))
        if not (folder / "permitted-final-feedback.json").exists():
            epoch = candidate
            break
    if epoch is None:
        return "final_exams_used"
    if (Path(root) / ("epoch-" + str(epoch)) / "selected-recipe.json").exists():
        return "candidate_awaits_submission"
    if not trial_supports_selection(CampaignLedger(root), manifest["owner"], strategy):
        return "practice_result_required"
    return None


async def freeze_candidate(prepared, *, strategy, reason, used_feedback=False):
    """A miner freezes a practiced recipe as this epoch's candidate.

    The record is the one the agent's SELECT writes, built by the same
    function. Refused, with nothing written, for a recipe with no practice
    result, while a frozen candidate awaits submission, or once both committed
    final exams are used.
    """
    from .research_loop import _epoch_paths, candidate_record

    ledger, owner = prepared.ledger, prepared.owner
    # One checker for these rules, whether a door asks early or this freezes.
    refusal = freeze_refusal(ledger.root, strategy)
    if refusal is not None:
        raise OperationRefused(refusal)
    epoch = _open_epoch(prepared)
    record = candidate_record(strategy, reason, used_feedback)
    ledger.checkpoint()
    folder = _epoch_paths(ledger, epoch)
    write_once(folder / "selected-recipe.json", canonical(record))
    write_once(
        folder / "outcome.json",
        canonical(
            {
                "schema": "carbon.autoresearch.epoch-outcome.v1",
                "epoch": epoch,
                **record,
                "selected_by": "miner",
                "accounting": ledger.status(owner=owner),
                "chain_transactions": 0,
            }
        ),
    )
    report(ledger, owner=owner)
    return {"epoch": epoch, "selection": record}


async def practice_recipe(prepared, *, strategy, hypothesis, expected_effect, identity):
    """A miner's practice trial of a registered recipe on a prepared campaign.

    The same research task the agent's practice runs, through the campaign's
    own research service: real training on public TRAIN data, self-reported,
    and the result a later freeze needs.
    """
    from .research_tools import PREFIX

    return await prepared.sdk.call(
        PREFIX + "start_research_task",
        {
            "kind": "practice",
            "strategy_json": json.dumps(strategy),
            "action": None,
            "arguments_json": None,
            "hypothesis": hypothesis,
            "expected_effect": expected_effect,
        },
        identity,
    )


async def submit_frozen(prepared):
    """A miner's DEVELOPMENT submit of their frozen candidate.

    Refused unless a candidate is frozen and not yet submitted. The practice
    rule is checked again at submission. After the last committed final exam
    the campaign is complete.
    """
    _miner_selects(prepared)
    root = prepared.ledger.root
    epoch = _open_epoch(prepared)
    if epoch is None:
        raise OperationRefused("final_exams_used")
    selected = root / ("epoch-" + str(epoch)) / "selected-recipe.json"
    if not selected.exists():
        raise OperationRefused("freeze_a_candidate_first")
    strategy = json.loads(selected.read_bytes())["strategy"]
    feedback = await submit_candidate(prepared, epoch, strategy)
    if feedback is None:
        raise OperationRefused("practice_result_required")
    if epoch == FINAL_EPOCHS[-1]:
        _complete(prepared)
    return {"epoch": epoch, "feedback": feedback}


#: What a reconcile reports about the model calls whose outcome was unknown
#: (LP-PROD-A's settlement, reached from the reconcile action: LP-PROD-W2).
MODEL_CALL_RECONCILIATION = "carbon.autoresearch.model-call-reconciliation.v1"


def settled_call(settlement):
    """One settled model call as its miner sees it: which call, why its
    outcome was unknown, the charge booked for it - its full reservation, in
    integer nanodollars, or None where the selection was unpriced and money
    is not metered - and any caveat (`research_agent.MODEL_CAVEAT`). Read
    from the settlement `settle_uncertain_call` journals and books, so a
    reconcile's answer and the campaign's later readback are one record."""
    booked = settlement.get("booked") if type(settlement) is dict else None
    booked = booked if type(booked) is dict else {}
    charge = booked.get("provider_nanodollars")
    return {
        "identity": settlement.get("identity"),
        "reason": settlement.get("reason"),
        "booked_nanodollars": charge if type(charge) is int else None,
        "caveat": settlement.get("caveat"),
    }


def unknown_outcome_calls(operations, *, awaiting=True):
    """A campaign's model calls whose outcome was unknown, from its ledger
    operations (`CampaignLedger.status`) alone - no lease, no change: those a
    reconcile settled (`settled`, each as `settled_call`), and with
    `awaiting` those still unresolved (`awaiting_settlement`: each call and
    what settling it would book), with the accounting rule when there are
    any. A caller passes `awaiting=False` while the campaign runs: a call in
    flight is unresolved too, and awaits nothing."""
    from .research_agent import SETTLEMENT_ACCOUNTING

    settled, pending = [], []
    for op in operations:
        result = op.get("result")
        reservation = op.get("reservation") or {}
        if type(result) is dict and type(result.get("provider_settlement")) is dict:
            settled.append(settled_call(result["provider_settlement"]))
        elif (
            awaiting
            and op.get("state") == "RESERVED"
            # What `research_agent.settle_uncertain_calls` settles: a model
            # call is its one provider attempt.
            and reservation.get("provider_attempts") == 1
        ):
            charge = reservation.get("provider_nanodollars")
            pending.append(
                {
                    "identity": op.get("id"),
                    "booked_on_settlement_nanodollars": (
                        charge if type(charge) is int else None
                    ),
                }
            )
    return {
        "settled": settled,
        "awaiting_settlement": pending,
        "accounting": SETTLEMENT_ACCOUNTING if settled or pending else None,
    }


def reconcile_model_calls(ledger, *, owner):
    """Settle every model call of `owner` whose outcome is unknown, as the
    campaign's reconcile action (`research_agent.settle_uncertain_calls`):
    each is booked at its full reservation and journalled beside it, and the
    next resume sends the same request under a fresh identity. Nothing is
    resent here, and nothing settles a call automatically.

    A controlled campaign's caller holds the campaign's owner lock and has
    just taken a control generation (`CampaignControl.acquire`), as the
    Launchpad's reconcile does; A's fences refuse anything else
    (`control_fenced`), and any call in flight (`call_in_flight`).

    Returns what was settled - each call, the charge booked and any caveat,
    and their total - and each call refused, with its closed code and next
    step (`SETTLEMENT_REFUSALS`); a refused call stays unresolved."""
    from .research_agent import (
        SETTLEMENT_ACCOUNTING,
        SETTLEMENT_REFUSALS,
        SETTLEMENT_RESEND,
        settle_uncertain_calls,
    )

    outcome = settle_uncertain_calls(ledger, owner=owner)
    settled = [settled_call(settlement) for settlement in outcome["settled"]]
    return {
        "schema": MODEL_CALL_RECONCILIATION,
        "settled": settled,
        "booked_nanodollars": sum(call["booked_nanodollars"] or 0 for call in settled),
        "refused": [
            {
                "identity": refused["identity"],
                "code": refused["code"],
                "next_step": SETTLEMENT_REFUSALS.get(refused["code"]),
            }
            for refused in outcome["refused"]
        ],
        "accounting": SETTLEMENT_ACCOUNTING if settled else None,
        "resend": SETTLEMENT_RESEND if settled else None,
    }


def reconcile_command(root):
    """The development CLI's `reconcile`: settle the model calls of the
    campaign at `root` whose outcome is unknown (`reconcile_model_calls`).
    Returns (report, ok).

    Only the CLI's own campaign (no control surface) is reconciled here. A
    controlled campaign - a Launchpad product campaign, or one launched under
    a development grant - is reconciled only by its own reconcile action,
    under its owner lock and control generation, which this process does not
    hold: refused `control_fenced`, nothing settled."""
    from .research_agent import SETTLEMENT_REFUSALS

    manifest = json.loads((root / "campaign-manifest.json").read_bytes())
    if CampaignLedger.controlled(manifest):
        return {
            "error": "control_fenced",
            "next_step": SETTLEMENT_REFUSALS["control_fenced"],
        }, False
    report = reconcile_model_calls(CampaignLedger(root), owner=manifest["owner"])
    return report, not report["refused"]


async def execute(args, *, ledger=None):
    """Prepare a campaign, then let whoever selects in it work.

    With the autonomous agent, Carbon's agent runs the epochs. With Graphite
    (`graphite`), Graphite's miner edition runs its frozen stages
    (`run_graphite`). With no agent, the campaign is left prepared: the miner
    practices through the research tools and freezes and submits through the
    same operations.

    Returns what `run_agent` returns (a retained candidate's refusal code),
    otherwise None.
    """
    prepared = await prepare(args, ledger=ledger)
    if prepared is None:
        return None
    try:
        if prepared.agent == "graphite":
            return await run_graphite(prepared)
        if prepared.agent != "none":
            return await run_agent(prepared)
        return None
    finally:
        prepared.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("run", "resume", "status", "report", "reconcile")
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--accepted-revision")
    parser.add_argument("--agent-policy", choices=(LEGACY, AUTONOMOUS), default=LEGACY)
    # The development path only. A founder capping Carbon's spend on Carbon's
    # accounts for a bounded experiment; no product surface reaches this
    # (C-MLP-02-D11). The principal is what the grant binds.
    parser.add_argument("--grant-file", type=Path)
    parser.add_argument("--principal")
    for name in (
        "image-manifest",
        "analysis-image-manifest",
        "operator-config",
        "api-key-file",
        "miner-public",
        "quarantine-journal",
    ):
        parser.add_argument("--" + name, type=Path)
    # Where the miner's `carbon-miner-signer` listens; omitted, the path it
    # derives from the public hotkey.
    parser.add_argument("--signer-socket", type=Path)
    # The miner's model provider and model (`model_provider.select`), as a
    # JSON object; omitted, the pinned default. A frozen campaign keeps its own.
    parser.add_argument("--model-selection", type=Path)
    args = parser.parse_args()
    if args.model_selection is not None:
        args.model_selection = json.loads(args.model_selection.read_bytes())
    if args.command in ("status", "report"):
        manifest = json.loads((args.root / "campaign-manifest.json").read_bytes())
        print(
            json.dumps(
                report(CampaignLedger(args.root), owner=manifest["owner"]), indent=2
            )
        )
        return
    if args.command == "reconcile":
        # Settles model calls whose outcome is unknown at their full
        # reservation; a later resume sends each again under a fresh
        # identity. Never automatic: only this command does it here.
        outcome, ok = reconcile_command(args.root)
        print(json.dumps(outcome, indent=2))
        if not ok:
            raise SystemExit(1)
        return
    if any(
        getattr(args, n) is None
        for n in (
            "accepted_revision",
            "image_manifest",
            "analysis_image_manifest",
            "operator_config",
            "api_key_file",
            "miner_public",
            "quarantine_journal",
        )
    ):
        parser.error(
            "execution requires accepted revision, both images, existing operator/miner/credential files, and quarantine journal"
        )
    ledger = None
    if args.grant_file is not None:
        if not args.principal:
            parser.error("--grant-file requires the --principal the grant binds")
        from .research_admission import Admission

        ledger = CampaignLedger(args.root, admission=Admission.load(args.grant_file))
    try:
        asyncio.run(execute(args, ledger=ledger))
    except Exception:  # noqa: BLE001
        # Never echo provider/authentication exception text or private input values.
        print(
            "Campaign stopped. Retained journals and owner report require inspection; no automatic retry.",
            flush=True,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
