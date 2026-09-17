"""Finite trusted autoresearch controller. No public-network write capability.

run creates one new campaign; resume reuses its exact immutable inputs. Unknown
side effects stop, and completed source handoffs are resolved without rerunning.
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
from carbon.chain.auth import BittensorMessageSigner, open_external_hotkey
from carbon.development_testnet.operator import load_config
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity
from carbon.transport.models import message

from .agent import MODEL, ResponsesTransport
from .data import write_once
from .profile import CHALLENGE, canonical, digest
from .research_catalog import compile_recipe
from .research_data import PublicReferenceData
from .research_final import prepare_final_inputs
from .research_generation import generate_roles
from .research_image import load_analysis_image, verify_image
from .research_ledger import CEILINGS, ELAPSED_SECONDS, VERSION, CampaignLedger
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


async def execute(args):
    implementation = accepted_implementation(args.accepted_revision)
    root = args.root
    if args.command == "run" and (root / "campaign-manifest.json").exists():
        raise ValueError("campaign already exists; use resume")
    if args.command == "resume" and not (root / "campaign-manifest.json").exists():
        raise ValueError("no frozen campaign to resume")
    ledger = CampaignLedger(root)
    image = load_image_identity(args.image_manifest)
    verify_current_worker(image, implementation)
    eligibility = doctor(image_id=image.image_id, image_identity=image)
    if not eligibility.eligible:
        raise ValueError("accepted numerical host unavailable")
    analysis = load_analysis_image(args.analysis_image_manifest)
    verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise ValueError("analysis/trusted image parent differs")
    private_file(args.api_key_file)
    ResponsesTransport(args.api_key_file)
    config = load_config(args.operator_config)
    public = json.loads(private_file(args.miner_public).read_bytes())
    if public["netuid"] != 567 or config.netuid != 567:
        raise ValueError("existing subnet 567 context required")
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
            "ceilings": CEILINGS,
            "elapsed_seconds": ELAPSED_SECONDS,
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
        composition = make_research_service(
            root=root / "research-tasks",
            ledger=ledger,
            owner=owner,
            image=analysis,
            public_material=PublicMaterial(data),
            practice=PublicPractice(data=data, ledger=ledger, owner=owner, image=image),
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
        for epoch in (1, 2):
            observation = {
                "objective": objective(),
                "capabilities": capabilities(),
                "control_recipe": CONTROL,
                "control_basis": CONTROL_BASIS,
                "epoch": epoch,
                "prior_permitted_final_feedback": feedback,
                "instructions": "Record a testable plan. Use real practice, inspect curves and revise or reject hypotheses; do not stop at the first valid recipe. Select only a recipe you actually practiced, or stop for a supported reason.",
            }
            result = await run_epoch(
                ledger,
                owner=owner,
                epoch=epoch,
                sdk=sdk,
                credential_file=args.api_key_file,
                initial_observation=observation,
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
                {"status": "FINITE_CAMPAIGN_STOPPED", "new_network_transactions": 0}
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
    try:
        asyncio.run(execute(args))
    except Exception:  # noqa: BLE001
        # Never echo provider/authentication exception text or private input values.
        print(
            "Campaign stopped. Retained journals and owner report require inspection; no automatic retry.",
            flush=True,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
