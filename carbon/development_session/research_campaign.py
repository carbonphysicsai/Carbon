"""Finite trusted autoresearch controller. No public-network write capability.

run creates one new campaign; resume reuses its exact immutable inputs. Unknown
side effects stop, and completed source handoffs are resolved without rerunning.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import dataclasses
import itertools
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from carbon import research
from carbon.chain.auth import BittensorMessageSigner, open_external_hotkey
from carbon.chain.models import CARBON_NETUID
from carbon.development_testnet.operator import load_config
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity
from carbon.transport.models import message

from . import research_guidance as guidance
from .agent import MODEL, ResponsesTransport
from .data import write_once
from .gpu_research import PublicGPUPractice, registered_gpu_image
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
        request="bootstrap-research-owner",
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
            result.get("provenance") == "REAL_JAX_PUBLIC_PRACTICE"
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


async def execute(args, *, ledger=None):
    agent_policy = getattr(args, "agent_policy", LEGACY)
    policy = binding(agent_policy)
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
    private_file(args.api_key_file)
    ResponsesTransport(args.api_key_file)
    config = load_config(args.operator_config)
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
    key = open_external_hotkey(
        Path(public["key_file"]),
        private_file(args.miner_password_file),
        public["hotkey"],
    )
    session = root / "research-auth"
    session.mkdir(mode=0o700, exist_ok=True)
    connection = LocalMinerConnection(
        session, args.image_manifest, config.context, config.publisher_hotkey, key
    )
    owner = await requester(connection)
    if (root / "campaign-complete.json").exists():
        report(ledger, owner=owner)
        return
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
            "provider": {
                "model": MODEL,
                "input_per_million": 0.25,
                "cached_per_million": 0.025,
                "output_per_million": 2.0,
                "store": False,
                "data": "public synthetic and own permitted research only; standard API abuse monitoring may retain up to 30 days",
            },
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
        feedback = None
        # freeze() validates the immutable limit: v1 remains two epochs, while
        # a narrower v2 grant must finish without preparing an inadmissible epoch.
        # With no epochs budget there is no epoch count: the agent runs until
        # it stops selecting or the miner stops the campaign (C-MLP-02-D11).
        epoch_cap = (manifest.get("ceilings") or {}).get("epochs")
        epochs = itertools.count(1) if epoch_cap is None else range(1, epoch_cap + 1)
        for epoch in epochs:
            ledger.checkpoint()
            observation = {
                "objective": objective(),
                "capabilities": capabilities(),
                "control_recipe": CONTROL,
                "control_basis": CONTROL_BASIS,
                "epoch": epoch,
                "prior_permitted_final_feedback": feedback,
                "instructions": "Record a testable plan. Use real practice, inspect curves and revise or reject hypotheses; do not stop at the first valid recipe. Select only a recipe you actually practiced, or stop for a supported reason.",
            }
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
                sdk=sdk,
                credential_file=args.api_key_file,
                initial_observation=observation,
                agent_policy=agent_policy,
            )
            report(ledger, owner=owner)
            if result["status"] != "SELECTED":
                break
            if not trial_supports_selection(ledger, owner, result["strategy"]):
                ledger.note(
                    owner=owner,
                    kind="decision",
                    body={
                        "epoch": epoch,
                        "stop": "selected recipe has no authentic completed practice observation; no final exam dispatched",
                    },
                )
                break
            feedback, ref = await final_epoch(
                args,
                ledger,
                owner,
                epoch,
                result["strategy"],
                seeds,
                role_root,
                data,
                image,
                key,
                config,
            )
            from .research_rewards import update_simulation

            update_simulation(root, ref, epoch=epoch)
            write_once(
                root / ("epoch-" + str(epoch)) / "permitted-final-feedback.json",
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
        write_once(
            root / "campaign-complete.json",
            canonical(
                {
                    "status": "FINITE_CAMPAIGN_STOPPED",
                    "new_network_transactions": 0,
                    "completed_unix": ledger.clock(),
                }
            ),
        )
    finally:
        if composition is not None:
            composition.tasks.close()
        report(ledger, owner=owner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "resume", "status", "report"))
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
        "miner-password-file",
        "quarantine-journal",
    ):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    if args.command in ("status", "report"):
        manifest = json.loads((args.root / "campaign-manifest.json").read_bytes())
        print(
            json.dumps(
                report(CampaignLedger(args.root), owner=manifest["owner"]), indent=2
            )
        )
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
            "miner_password_file",
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
