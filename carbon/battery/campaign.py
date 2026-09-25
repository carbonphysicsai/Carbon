"""A battery campaign: the shared campaign machinery bound to battery.

`research_campaign.prepare` routes here when the frozen manifest (or the
launch) names the battery Challenge. The shared machinery is used unchanged:
- the verified images and the host doctor;
- the registered hotkey and the signed local transport;
- the campaign ledger, its budget and the ownership lock;
- the research SDK and the twelve operations;
- freeze and submit.

Only the Challenge-specific parts differ:
- the composition (`research.make_battery_research_service`);
- a gateway that authenticates battery requests;
- the evaluation deployment a submission reaches.

The Burgers steps that do not apply are absent rather than stubbed: private
role generation, committed final-exam seeds and the C-04/C-05 final epoch.
This version admits only a miner-driven campaign (agent ``none``). Carbon's
autonomous agent is written for the Burgers task and is refused here by name,
never run on battery.
"""

from __future__ import annotations

import json
import threading
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
PROVIDER = {"agent": "none", "model_calls": 0}

_DEPLOYMENTS = {}
_LOCK = threading.Lock()


def campaign_challenge(args):
    """The Challenge a campaign is bound to, or None for the historical
    Burgers campaign. The frozen manifest decides once it exists."""
    path = args.root / "campaign-manifest.json"
    if path.exists():
        return json.loads(path.read_bytes()).get("challenge")
    product = getattr(args, "product", None)
    return getattr(product, "challenge", None)


def manifest_document(product, *, owner, implementation, images):
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
        "provider": PROVIDER,
        "images": images,
        "new_network_transactions": 0,
        **product.manifest_fields(),
    }


async def prepare_battery(args, *, ledger=None):
    from carbon.chain.auth import open_external_hotkey
    from carbon.chain.models import CARBON_NETUID
    from carbon.development_session.data import write_once
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
    from carbon.development_testnet.operator import load_config
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
    ledger = ledger if ledger is not None else CampaignLedger(root)
    if ledger.root != root or ledger.admission is not None:
        raise ValueError("a battery campaign never consumes a development grant")
    agent = frozen["agent"] if frozen is not None else product.agent
    if agent != "none":
        raise ValueError("autonomous agent unavailable for this Challenge")
    implementation = accepted_implementation(args.accepted_revision)
    image = load_image_identity(args.image_manifest)
    verify_current_worker(image, implementation)
    if not doctor(image_id=image.image_id, image_identity=image).eligible:
        raise ValueError("accepted numerical host unavailable")
    analysis = load_analysis_image(args.analysis_image_manifest)
    verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise ValueError("analysis/trusted image parent differs")
    runtime = {
        "implementation": implementation,
        "images": [image.image_id, analysis.image_id],
    }
    declared = frozen["runtime"] if frozen is not None else product.runtime
    if declared != runtime:
        # Julia, GPU and other research lanes are not composed for battery.
        raise ValueError("configured runtime differs from the battery runtime")
    config = load_config(args.operator_config)
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
        return None
    if frozen is None:
        manifest = manifest_document(
            product,
            owner=owner,
            implementation=implementation,
            images=runtime["images"],
        )
        write_once(manifest_path, canonical(manifest))
    else:
        manifest = frozen
        if manifest.get("owner") != owner:
            raise ValueError("battery campaign owner changed")
        check_attached(
            manifest, implementation=implementation, images=runtime["images"]
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
        challenge=CHALLENGE,
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
    runner=None,
    backend=None,
):
    """The battery composition and the wrapper that authenticates for it.

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
    )
    composition = make_battery_research_service(
        root=ledger.root / "research-tasks",
        ledger=ledger,
        owner=owner,
        image=analysis,
        practice=practice,
        demand=demand,
        cleanup_only=cleanup_only,
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


def check_attached(manifest, *, implementation, images):
    """An attach re-checks the frozen battery binding it serves."""
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
    if manifest.get("runtime") != {"implementation": implementation, "images": images}:
        raise ValueError("campaign runtime differs from the battery runtime")


def is_battery(manifest):
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    return (manifest.get("challenge") or {}).get("id") == BATTERY_CHALLENGE


def deployment(config_path):
    """One evaluation deployment per configuration for this process, so its
    screening pool rotates across every submission it judges."""
    from .evaluation import EvaluationDeployment

    key = str(Path(config_path).resolve())
    with _LOCK:
        if key not in _DEPLOYMENTS:
            _DEPLOYMENTS[key] = EvaluationDeployment.load(key, repository=REPOSITORY)
        return _DEPLOYMENTS[key]


def evaluate_candidate(prepared, epoch, record):
    """Submit a frozen battery candidate to the evaluation deployment.

    Returns the permitted feedback. Raises `OperationRefused` for an
    evaluation that did not happen - unconfigured deployment or an
    infrastructure failure - so the epoch is not consumed and the frozen
    candidate can be submitted again.
    """
    from carbon.development_session.research_campaign import OperationRefused

    from .evaluation import EvaluationUnavailable

    config = getattr(prepared.args, "battery_evaluation", None)
    if config is None:
        raise OperationRefused("evaluation_unavailable")
    try:
        target = deployment(config)
    except EvaluationUnavailable as unavailable:
        raise OperationRefused(unavailable.code) from None
    with _LOCK:
        outcome = target.evaluate(
            prepared.manifest["campaign_id"] + "/epoch-" + str(epoch),
            record["strategy"],
            record.get("contract_digest"),
        )
    if outcome["status"] == "FAILED_INFRA":
        raise OperationRefused("evaluation_failed_infra")
    return {
        "schema": "carbon.battery.permitted-feedback.v1",
        "epoch": epoch,
        "outcome": outcome,
        "official_eligible": False,
        "reward": False,
    }
