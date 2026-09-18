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
from carbon.development_session.profile import CHALLENGE, canonical
from carbon.development_session.research_admission import (
    MANIFEST,
    Admission,
    private_json,
    verify_cleanup_owner,
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
    cleanup_only: bool = False


def load_profile(path: Path, *, cleanup_only=False) -> OperatorProfile:
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
    if not cleanup_only:
        admission.verify(
            root=root,
            principal=cfg["principal"],
            runtime=grant["runtime"],
            now=time.time(),
        )
    if (
        cfg["account_ref"] != grant["account_ref"]
        or cfg["accepted_revision"] != grant["runtime"]["implementation"]["revision"]
        or not root.is_dir()
        or (not cleanup_only and (root / "campaign-complete.json").exists())
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
    if cleanup_only:
        meter = CampaignLedger(root, admission=admission)
        meter.generation = CampaignControl(meter).status()["generation"]
        if verify_cleanup_owner(meter, manifest["owner"]) != manifest:
            raise ValueError("retained cleanup profile differs")
    return OperatorProfile(path, cfg, admission, root, manifest, cleanup_only)


def _prepared_tasks(root, *, cleanup_only=False):
    path = root / "research-tasks" / "research-tasks.sqlite3"
    if not path.is_file() or path.is_symlink():
        raise ValueError("existing prepared research tasks required")
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
        for (encoded,) in db.execute("SELECT view FROM tasks"):
            task = research.load_canonical(encoded, research.ResearchTaskView)
            if not cleanup_only and task.state in {
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
    if (
        not profile.cleanup_only
        and not doctor(image_id=image.image_id, image_identity=image).eligible
    ):
        raise ValueError("accepted numerical host unavailable")
    analysis = load_analysis_image(paths["analysis_image_manifest"])
    verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise ValueError("analysis image parent differs")
    runtime = {
        "implementation": implementation,
        "images": [image.image_id, analysis.image_id],
    }
    role_root = profile.root / "private-roles"
    authored = _authored_image(profile, analysis)
    _, scientific = _scientific_selection(
        profile.manifest["runtime"], image, role_root, authored
    )
    if scientific is not None:
        runtime["scientific_tasks"] = scientific
    if authored is not None:
        from carbon.development_session.julia_analysis import authored_julia_scope

        runtime["authored_research"] = [authored_julia_scope(authored)]
    if profile.cleanup_only:
        if runtime != profile.manifest["runtime"]:
            raise ValueError("retained runtime differs")
        grant = profile.admission.document
    else:
        grant = profile.admission.verify(
            root=profile.root,
            principal=cfg["principal"],
            runtime=runtime,
            now=time.time(),
        )
    if (
        profile.manifest.get("implementation") != implementation
        or profile.manifest.get("images") != runtime["images"]
        or profile.manifest.get("objective") != document()
    ):
        raise ValueError("campaign runtime or objective changed")
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


def _authored_image(profile, analysis):
    if "authored_research" not in profile.manifest["runtime"]:
        return None
    from carbon.development_session.research_campaign import registered_julia_image

    return registered_julia_image(profile.root, profile.manifest["runtime"], analysis)


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

    async def check_cleanup_registration(self):
        from carbon.development_session.research_admission import verify_cleanup_owner

        if self.closed or private_json(self.profile.path) != self.profile.document:
            raise ValueError("operator profile changed or controller closed")
        retained = verify_cleanup_owner(self.ledger, self.profile.manifest["owner"])
        if retained != self.profile.manifest:
            raise ValueError("retained campaign differs from connection")
        return await self.connection.check_registration()

    async def check_registration(self):
        profile = self.profile
        if profile.cleanup_only:
            raise ValueError("cleanup-only attachment cannot admit research")
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


def _scientific_selection(runtime, image, role_root, authored=None):
    """Recompute one closed registered combination; no schema label grants access."""
    if "scientific_tasks" not in runtime:
        return "legacy", None
    scopes = runtime["scientific_tasks"]
    if (
        type(scopes) is not list
        or not scopes
        or any(type(s) is not dict for s in scopes)
    ):
        raise ValueError("closed registered scientific scopes required")
    from carbon.development_session.advection_research import advection_scope
    from carbon.development_session.julia_analysis import authored_julia_scope
    from carbon.development_session.julia_envelope import julia_envelope_scope
    from carbon.development_session.julia_research import julia_burgers_scope
    from carbon.development_session.research_sequences import SCOPE as ENVELOPE_SCOPE

    schemas = [s.get("schema") for s in scopes]
    if schemas == ["carbon.public-advection-study.scope.v1"]:
        expected_authored = [authored_julia_scope(authored)]
        if (
            canonical(runtime.get("authored_research")) != canonical(expected_authored)
            or authored.parent.parent_image != image.image_id
        ):
            raise ValueError("separately bound advection analysis image required")
        kind, expected = "advection", [advection_scope(authored)]
    elif schemas == ["carbon.public-julia-study.scope.v1"]:
        kind, expected = "burgers", [julia_burgers_scope(image, role_root)]
    elif schemas == ["carbon.public-julia-study.scope.v1", ENVELOPE_SCOPE]:
        kind, expected = "envelope", [
            julia_burgers_scope(image, role_root),
            julia_envelope_scope(image, role_root),
        ]
    else:
        raise ValueError("unsupported scientific scope combination")
    if canonical(scopes) != canonical(expected):
        raise ValueError("registered scientific scope differs")
    return kind, expected


def _science(ledger, owner, image, role_root, *, cleanup_only=False, authored=None):
    from carbon.development_session.research_data import PublicReferenceData
    from carbon.development_session.research_provider import PublicPractice

    runtime = (
        ledger.admission.document["runtime"] if ledger.admission is not None else {}
    )
    kind, scopes = _scientific_selection(runtime, image, role_root, authored)
    data = PublicReferenceData(
        ledger=ledger, owner=owner, image=image, role_root=role_root
    )
    material = PublicMaterial(data)
    if kind in {"burgers", "envelope"}:
        from carbon.development_session.julia_research import (
            JuliaPublicMaterial,
            PublicJuliaStudy,
        )

        material = JuliaPublicMaterial(
            material,
            PublicJuliaStudy(
                data,
                cleanup=cleanup_only,
                envelope_scope=scopes[1] if kind == "envelope" else None,
            ),
        )
        if kind == "envelope":
            from carbon.development_session.julia_envelope import JuliaEnvelopeMaterial

            material = JuliaEnvelopeMaterial(material, cleanup=cleanup_only)
    elif kind == "advection":
        from carbon.development_session.advection_research import (
            PublicAdvectionMaterial,
        )

        material = PublicAdvectionMaterial(
            material, ledger=ledger, owner=owner, image=authored, cleanup=cleanup_only
        )
    return material, PublicPractice(data=data, ledger=ledger, owner=owner, image=image)


async def serve(configuration: Path, *, cleanup_only=False):
    """Hold the existing campaign ownership lock for the whole stdio lifetime."""
    from scripts.dev.miner_launchpad.controller import owner_lock
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    profile = load_profile(configuration, cleanup_only=cleanup_only)
    with owner_lock(profile.root):
        ledger = CampaignLedger(profile.root, admission=profile.admission)
        if not cleanup_only:
            ledger.freeze(profile.manifest)  # Must match the existing immutable record.
        with ledger.db() as db:
            if (
                not cleanup_only
                and db.execute(
                    "SELECT 1 FROM operations WHERE state='RESERVED' LIMIT 1"
                ).fetchone()
            ):
                raise ValueError("unresolved consumption requires reconciliation")
        _prepared_tasks(profile.root, cleanup_only=cleanup_only)
        control = CampaignControl(ledger)
        status = control.status()
        if not cleanup_only and (
            status["desired"] != "RUN"
            or status["state"]
            in {
                "RECONCILIATION_REQUIRED",
                "STOPPED",
                "COMPLETED",
            }
        ):
            raise ValueError("campaign is not available for research")
        ledger.generation = status["generation"] if cleanup_only else control.acquire()
        if cleanup_only:
            verify_cleanup_owner(ledger, profile.manifest["owner"])
        connection, image, analysis, role_root = _runtime(profile)
        owner = await _requester(connection)
        if owner != profile.manifest.get("owner"):
            raise ValueError("authenticated campaign owner changed")
        authored = _authored_image(profile, analysis)
        material, practice = _science(
            ledger,
            owner,
            image,
            role_root,
            **({"authored": authored} if authored is not None else {}),
            **({"cleanup_only": True} if cleanup_only else {}),
        )
        composition = make_research_service(
            cleanup_only=cleanup_only,
            julia_image=authored,
            root=profile.root / "research-tasks",
            ledger=ledger,
            owner=owner,
            image=analysis,
            public_material=material,
            practice=practice,
        )
        bound = None
        try:
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
            adapter = ResearchToolAdapter(sdk, principal=owner)
            try:
                await create_stdio_server(adapter).run_async()
            finally:
                await adapter.shutdown_tasks()
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
                        if not cleanup_only or status["state"] not in {
                            "STOPPED",
                            "COMPLETED",
                        }:
                            control.settled(ledger.generation, cleanup_verified=clean)
                        elif not clean:
                            raise ValueError(
                                "terminal campaign cleanup requires reconciliation"
                            )
            finally:
                composition.tasks.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True, type=Path)
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Observe/cancel retained owned tasks; cannot start research",
    )
    args = parser.parse_args(argv)
    try:
        asyncio.run(serve(args.configuration, cleanup_only=args.cleanup_only))
    except (Exception, KeyboardInterrupt):  # noqa: BLE001
        print(
            "Carbon MCP unavailable: verify the existing private profile, grant, prepared campaign, accepted runtime and reconciliation state.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
