"""Serve an existing admitted Carbon research campaign over standard MCP stdio.

The operator supplies the existing private Launchpad runner profile. This command
attaches to its prepared, frozen campaign; it never creates a grant, starts the
paid agent loop, generates cohorts, or runs final evaluation. The operator host
needs the exact accepted checkout and prepared worker images. Clients need only
the MCP command/connection, not access to that checkout or its private records.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from carbon import research
from carbon.development_session.profile import CHALLENGE
from carbon.development_session.research_admission import (
    MANIFEST,
    Admission,
    private_json,
)
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import ResearchMinerTools
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.miner_mcp.standard import ResearchToolAdapter
from carbon.miner_mcp.standard_server import create_stdio_server


@dataclass(frozen=True)
class OperatorProfile:
    path: Path
    document: dict
    admission: Admission
    root: Path
    manifest: dict


def load_profile(path: Path) -> OperatorProfile:
    """Read existing operator authority; no filesystem or accounting creation."""
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS

    cfg = private_json(path)
    if (
        set(cfg)
        != {
            "schema",
            "profile_id",
            "principal",
            "grant_file",
            "account_ref",
            "enabled",
            "paths",
            "accepted_revision",
        }
        or cfg["schema"] != "carbon.launchpad.runner-profile.v1"
        or cfg["enabled"] is not True
        or type(cfg["paths"]) is not dict
        or set(cfg["paths"]) != PATH_FIELDS
        or any(
            type(v) is not str or not Path(v).is_absolute()
            for v in cfg["paths"].values()
        )
    ):
        raise ValueError("closed enabled operator profile required")
    admission = Admission.load(Path(cfg["grant_file"]))
    grant = admission.document
    root = Path(grant["root"])
    admission.verify(
        root=root, principal=cfg["principal"], runtime=grant["runtime"], now=time.time()
    )
    if (
        cfg["account_ref"] != grant["account_ref"]
        or cfg["accepted_revision"] != grant["runtime"]["implementation"]["revision"]
        or not root.is_dir()
        or (root / "campaign-complete.json").exists()
        or not (root / "campaign.sqlite3").is_file()
        or (root / "campaign.sqlite3").is_symlink()
    ):
        raise ValueError("existing unfinished admitted campaign required")
    manifest = private_json(root / "campaign-manifest.json")
    if (
        manifest.get("schema") != MANIFEST
        or manifest.get("principal") != cfg["principal"]
        or manifest.get("runtime") != grant["runtime"]
        or manifest.get("grant") != admission.binding()
        or manifest.get("campaign_id") != grant["campaign_id"]
    ):
        raise ValueError("prepared campaign differs from operator grant")
    return OperatorProfile(path, cfg, admission, root, manifest)


def _prepared_tasks(root):
    path = root / "research-tasks" / "research-tasks.sqlite3"
    if not path.is_file() or path.is_symlink():
        raise ValueError("existing prepared research tasks required")
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
        for (encoded,) in db.execute("SELECT view FROM tasks"):
            task = research.load_canonical(encoded, research.ResearchTaskView)
            if task.state in {
                research.ResearchTaskState.RUNNING,
                research.ResearchTaskState.CANCEL_REQUESTED,
            }:
                raise ValueError(
                    "uncertain task requires existing controller reconciliation"
                )


def _runtime(profile):
    """Reuse the accepted session's host/image/key and public science services."""
    from carbon.chain.auth import open_external_hotkey
    from carbon.development_session.research_campaign import (
        accepted_implementation,
        private_file,
        verify_current_worker,
    )
    from carbon.development_session.research_image import (
        load_analysis_image,
        verify_image,
    )
    from carbon.development_session.research_profile import document, public_cases
    from carbon.development_session.service import LocalMinerConnection
    from carbon.development_testnet.operator import load_config
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity

    cfg = profile.document
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    implementation = accepted_implementation(cfg["accepted_revision"])
    image = load_image_identity(paths["image_manifest"])
    verify_current_worker(image, implementation)
    if not doctor(image_id=image.image_id, image_identity=image).eligible:
        raise ValueError("accepted numerical host unavailable")
    analysis = load_analysis_image(paths["analysis_image_manifest"])
    verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise ValueError("analysis image parent differs")
    runtime = {
        "implementation": implementation,
        "images": [image.image_id, analysis.image_id],
    }
    grant = profile.admission.verify(
        root=profile.root, principal=cfg["principal"], runtime=runtime, now=time.time()
    )
    if (
        profile.manifest.get("implementation") != implementation
        or profile.manifest.get("images") != runtime["images"]
        or profile.manifest.get("objective") != document()
    ):
        raise ValueError("campaign runtime or objective changed")
    role_root = profile.root / "private-roles"
    if private_json(role_root / "research-profile.json") != document():
        raise ValueError("prepared public material profile changed")
    for role in ("research-train", "research-validation"):
        public_cases(role_root, role)  # Checks existing digests; never draws new cases.
    config = load_config(paths["operator_config"])
    public = json.loads(private_file(paths["miner_public"]).read_bytes())
    if (
        public["netuid"] != 567
        or config.netuid != 567
        or public["hotkey"] != grant["miner_identity"]
    ):
        raise ValueError("existing miner differs from grant")
    key = open_external_hotkey(
        Path(public["key_file"]),
        private_file(paths["miner_password_file"]),
        public["hotkey"],
    )
    session = profile.root / "research-auth"
    if not session.is_dir() or session.is_symlink():
        raise ValueError("prepared authenticated session required")
    connection = LocalMinerConnection(
        session, paths["image_manifest"], config.context, config.publisher_hotkey, key
    )
    return connection, image, analysis, role_root


async def _requester(connection):
    """Use the existing signed gateway with a fresh bootstrap transmission ID."""
    from carbon.chain.auth import BittensorMessageSigner
    from carbon.transport.models import message

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
        request="mcp-bootstrap-" + uuid.uuid4().hex,
        tool=research.RESEARCH_NAMESPACE,
        fields={
            "call_base64": base64.b64encode(research.canonical_bytes(call)).decode(
                "ascii"
            )
        },
    )
    headers = BittensorMessageSigner(connection.miner_key).sign(
        body, receiver=connection.publisher, nonce_ns=time.time_ns()
    )
    return (await connection.service.gateway.receive(body, headers)).requester.value


class _AdmittedConnection:
    def __init__(self, connection, profile, ledger, control):
        self.connection, self.profile, self.ledger, self.control = (
            connection,
            profile,
            ledger,
            control,
        )
        self.chain_context, self.publisher, self.miner_key = (
            connection.chain_context,
            connection.publisher,
            connection.miner_key,
        )
        self.closed = False

    async def check_registration(self):
        profile = self.profile
        if self.closed or private_json(profile.path) != profile.document:
            raise ValueError("operator profile changed or controller closed")
        now = self.ledger.clock()
        profile.admission.verify(
            root=profile.root,
            principal=profile.document["principal"],
            runtime=profile.manifest["runtime"],
            now=now,
        )
        with self.ledger.db() as db:
            started = db.execute("SELECT started FROM campaign WHERE id=1").fetchone()[
                0
            ]
        if started is not None and (
            now < started or now >= started + profile.manifest["elapsed_seconds"]
        ):
            raise ValueError("original campaign elapsed deadline reached")
        status = self.control.status()
        if (
            status["generation"] != self.ledger.generation
            or status["desired"] != "RUN"
            or status["state"] in {"RECONCILIATION_REQUIRED", "COMPLETED", "STOPPED"}
        ):
            raise ValueError("campaign admission stopped")
        return await self.connection.check_registration()


def _science(ledger, owner, image, role_root):
    from carbon.development_session.research_data import PublicReferenceData
    from carbon.development_session.research_provider import PublicPractice

    data = PublicReferenceData(
        ledger=ledger, owner=owner, image=image, role_root=role_root
    )
    return PublicMaterial(data), PublicPractice(
        data=data, ledger=ledger, owner=owner, image=image
    )


async def serve(configuration: Path):
    """Hold the existing campaign ownership lock for the whole stdio lifetime."""
    from scripts.dev.miner_launchpad.controller import owner_lock
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    profile = load_profile(configuration)
    with owner_lock(profile.root):
        ledger = CampaignLedger(profile.root, admission=profile.admission)
        ledger.freeze(profile.manifest)  # Must match the existing immutable record.
        with ledger.db() as db:
            if db.execute(
                "SELECT 1 FROM operations WHERE state='RESERVED' LIMIT 1"
            ).fetchone():
                raise ValueError("unresolved consumption requires reconciliation")
        _prepared_tasks(profile.root)
        control = CampaignControl(ledger)
        status = control.status()
        if status["desired"] != "RUN" or status["state"] in {
            "RECONCILIATION_REQUIRED",
            "STOPPED",
            "COMPLETED",
        }:
            raise ValueError("campaign is not available for research")
        connection, image, analysis, role_root = _runtime(profile)
        owner = await _requester(connection)
        if owner != profile.manifest.get("owner"):
            raise ValueError("authenticated campaign owner changed")
        material, practice = _science(ledger, owner, image, role_root)
        composition = make_research_service(
            root=profile.root / "research-tasks",
            ledger=ledger,
            owner=owner,
            image=analysis,
            public_material=material,
            practice=practice,
        )
        bound = None
        try:
            ledger.generation = control.acquire()
            bound = _AdmittedConnection(connection, profile, ledger, control)
            sdk = ResearchMinerTools(
                connection=bound,
                wrapper=AuthenticatedResearchService(
                    connection.service.gateway, {owner: composition.service}
                ),
                composition=composition,
                ledger=ledger,
                owner=owner,
            )
            await create_stdio_server(
                ResearchToolAdapter(sdk, principal=owner)
            ).run_async()
        finally:
            try:
                if bound is not None:
                    bound.closed = True
                    # A cancelled transport await does not cancel to_thread workers.
                    # Retain ownership until their existing deadline supervisors end.
                    clean = False
                    try:
                        await asyncio.get_running_loop().shutdown_default_executor()
                        clean = RunnerAdapter._cleanup(ledger)
                    finally:
                        control.settled(ledger.generation, cleanup_verified=clean)
            finally:
                composition.tasks.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        asyncio.run(serve(args.configuration))
    except (Exception, KeyboardInterrupt):  # noqa: BLE001
        print(
            "Carbon MCP unavailable: verify the existing private profile, grant, prepared campaign, accepted runtime and reconciliation state.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
