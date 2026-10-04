"""Serve an existing Carbon research campaign over standard MCP stdio.

The miner supplies their private runner profile (v2) and names one of their
campaigns. This command attaches to that prepared, frozen campaign; it never
starts the paid agent loop, generates cohorts, or runs final evaluation.

Registration is the only admission gate (C-MLP-02-D11): the campaign was
admitted by the registration its manifest records, and every research call
re-reads that registration from the chain. No grant exists on this path.

The host needs the exact accepted checkout and prepared worker images. Clients
need only the MCP command/connection, not access to that checkout or its
private records.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import json
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from carbon import research
from carbon.chain.models import CARBON_NETUID
from carbon.development_session.private_records import private_json
from carbon.development_session.profile import CHALLENGE, canonical
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import PRODUCT, CampaignLedger
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_tools import ResearchMinerTools
from carbon.miner_mcp.standard import ResearchToolAdapter
from carbon.miner_mcp.standard_server import create_stdio_server


class AttachRefused(ValueError):
    """An attachment refused by a named check (LP-PROD-C D8).

    `code` is closed and listed in `supervisor.NEXT_ACTIONS`, which says what
    to do next. The message is the historical one, so a caller or test that
    matched it is unchanged; a door shows the code and its next action, never
    the message (which may name a check's internals)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


#: Where `_check` notes which check an unnamed failure happened in.
_CHECK = "_carbon_attach_check"


@contextlib.contextmanager
def _check(code):
    """Name the check a failure inside happened in, as `code`, without
    changing the exception: callers and tests still see its own type. A
    failure that already names itself (a typed code, or an inner check) keeps
    its own name."""
    try:
        yield
    except Exception as exc:
        if refusal_code(exc) is None:
            with contextlib.suppress(Exception):
                setattr(exc, _CHECK, code)
        raise


def refusal_code(exc):
    """Which check refused an attachment: a held campaign lock is
    `campaign_busy`; a typed failure answers its own closed code (an
    `AttachRefused`, a `Rejected`, a signer failure); otherwise the check it
    happened in, or None. Never the message."""
    from scripts.dev.miner_launchpad.controller import LockHeld
    from scripts.dev.miner_launchpad.supervisor import exception_code

    if isinstance(exc, LockHeld):
        return "campaign_busy"
    return exception_code(exc) or getattr(exc, _CHECK, None)


@dataclass(frozen=True)
class OperatorProfile:
    """One attachable campaign and the profile that names it.

    `development_grant` is None for every campaign this door loads: a miner's
    campaign is admitted by registration (C-MLP-02-D11). It is set only by a
    development loader outside this package - Carbon's internal Workbench
    service on Carbon's own granted campaign - which this module neither
    imports nor calls; `load_profile` below can never produce one.
    """

    path: Path
    document: dict
    campaign: str
    root: Path
    manifest: dict
    cleanup_only: bool = False
    development_grant: object = None

    @property
    def registered_hotkey(self) -> str:
        if self.development_grant is not None:
            return self.development_grant.document["miner_identity"]
        return self.manifest["admission"]["hotkey"]


def load_profile(path: Path, campaign: str, *, cleanup_only=False) -> OperatorProfile:
    """Read the miner's profile and one of their campaigns; create nothing."""
    from carbon.compute.retired import refuse_rented
    from scripts.dev.miner_launchpad.runner import validated_profile

    with _check("runner_profile_unusable"):
        cfg = validated_profile(private_json(path))
    if cfg["enabled"] is not True and not cleanup_only:
        raise AttachRefused(
            "research_dispatch_disabled", "closed enabled operator profile required"
        )
    if (
        type(campaign) is not str
        or len(campaign) != 32
        or any(c not in "0123456789abcdef" for c in campaign)
    ):
        raise AttachRefused(
            "campaign_not_found",
            "a campaign id from this profile's campaigns is required",
        )
    root = Path(cfg["campaigns_root"]) / campaign
    unfinished = "existing unfinished campaign required"
    if not root.is_dir():
        raise AttachRefused("campaign_not_found", unfinished)
    if not cleanup_only and (root / "campaign-complete.json").exists():
        raise AttachRefused("campaign_complete", unfinished)
    if (
        not (root / "campaign.sqlite3").is_file()
        or (root / "campaign.sqlite3").is_symlink()
    ):
        raise AttachRefused("campaign_not_prepared", unfinished)
    # A launch that was admitted and never prepared has no frozen manifest.
    with _check("campaign_not_prepared"):
        manifest = private_json(root / "campaign-manifest.json")
    # A campaign frozen for the retired rented GPU is refused by name before
    # anything is opened or reached (OWNER-MINER-COMPUTE-LINK-ONLY-01).
    refuse_rented(manifest.get("runtime"))
    if (
        manifest.get("schema") != PRODUCT
        or manifest.get("principal") != cfg["principal"]
        or manifest.get("campaign_id") != "cmp-" + campaign
    ):
        raise AttachRefused(
            "campaign_manifest_differs", "the campaign differs from this profile"
        )
    if manifest.get("implementation", {}).get("revision") != cfg["accepted_revision"]:
        raise AttachRefused(
            "campaign_revision_differs", "the campaign differs from this profile"
        )
    if cleanup_only:
        with _check("campaign_manifest_differs"):
            meter = CampaignLedger(root)
            meter.generation = CampaignControl(meter).status()["generation"]
            retained = meter.retained_owner(manifest["owner"])
        if retained != manifest:
            raise AttachRefused(
                "campaign_manifest_differs", "retained cleanup profile differs"
            )
    return OperatorProfile(path, cfg, campaign, root, manifest, cleanup_only)


def _prepared_tasks(root, *, cleanup_only=False):
    path = root / "research-tasks" / "research-tasks.sqlite3"
    if not path.is_file() or path.is_symlink():
        raise AttachRefused(
            "campaign_not_prepared", "existing prepared research tasks required"
        )
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
        for (encoded,) in db.execute("SELECT view FROM tasks"):
            task = research.load_canonical(encoded, research.ResearchTaskView)
            if not cleanup_only and task.state in {
                research.ResearchTaskState.RUNNING,
                research.ResearchTaskState.CANCEL_REQUESTED,
            }:
                # Its outcome is unknown: observe and cancel it with
                # --cleanup-only, never by starting new research over it.
                raise AttachRefused(
                    "task_left_running",
                    "uncertain task requires existing controller reconciliation",
                )


def _runtime(profile):
    """Reuse the accepted session's host/image/key and public science services."""
    from carbon.development_session.research_campaign import (
        accepted_implementation,
        verify_current_worker,
    )
    from carbon.development_session.research_image import (
        load_analysis_image,
        verify_image,
    )
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity

    cfg = profile.document
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    # This checkout and its worker images are the ones the profile accepted:
    # not, after an update the installer has not accepted yet.
    with _check("carbon_updated_rerun_installer"):
        implementation = accepted_implementation(cfg["accepted_revision"])
        image = load_image_identity(paths["image_manifest"])
        verify_current_worker(image, implementation)
    with _check("runtime_unavailable"):
        eligible = (
            profile.cleanup_only
            or doctor(image_id=image.image_id, image_identity=image).eligible
        )
    if not eligible:
        raise AttachRefused(
            "runtime_unavailable", "accepted numerical host unavailable"
        )
    with _check("carbon_updated_rerun_installer"):
        analysis = load_analysis_image(paths["analysis_image_manifest"])
        verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise AttachRefused(
            "carbon_updated_rerun_installer", "analysis image parent differs"
        )
    runtime = {
        "implementation": implementation,
        "images": [image.image_id, analysis.image_id],
    }
    from carbon.challenge_registry.campaigns import campaign_for_manifest

    # Each Challenge's campaign re-checks its own frozen binding.
    with _check("campaign_runtime_differs"):
        campaign = campaign_for_manifest(profile.manifest)
        campaign.check_attached(
            profile.manifest,
            implementation=implementation,
            images=runtime["images"],
            julia_image=_authored_image(profile, analysis),
            gpu_image=campaign.gpu_image(profile.root, profile.manifest["runtime"]),
        )
    return _connection(profile, paths), image, analysis, None


def _connection(profile, paths):
    """The existing signed session for this campaign's registered miner."""
    from carbon.chain.external_signer import miner_signer
    from carbon.development_session.miner_network import binding
    from carbon.development_session.research_campaign import private_file
    from carbon.development_session.service import LocalMinerConnection

    # The operator configuration where an operator runs one, otherwise the
    # miner's own network file (C-MLP-04).
    with _check("runner_profile_unusable"):
        config = binding(
            operator_config=paths.get("operator_config"),
            miner_network=paths.get("miner_network"),
        )
        public = json.loads(private_file(paths["miner_public"]).read_bytes())
        # A public record without these is the profile's to fix, not a
        # runtime that is unavailable.
        netuid, hotkey = public["netuid"], public["hotkey"]
    differs = "existing miner differs from the registered miner"
    if netuid != CARBON_NETUID or config.netuid != CARBON_NETUID:
        raise AttachRefused("registration_wrong_network", differs)
    if hotkey != profile.registered_hotkey:
        raise AttachRefused("miner_differs_from_campaign", differs)
    # The miner's own signer holds the hotkey; Carbon only reaches it. A
    # signer failure names itself (`SignerCode`); anything else is the
    # profile's hotkey or socket path.
    with _check("runner_profile_unusable"):
        key = miner_signer(public, paths.get("signer_socket"))
    session = profile.root / "research-auth"
    if not session.is_dir() or session.is_symlink():
        raise AttachRefused(
            "session_unavailable", "prepared authenticated session required"
        )
    return LocalMinerConnection(
        session, paths["image_manifest"], config.context, config.publisher_hotkey, key
    )


def _authored_image(profile, analysis):
    if "authored_research" not in profile.manifest["runtime"]:
        if profile.development_grant is not None:
            return None
        # Anytime, for a product campaign: whichever image the host installed.
        from carbon.development_session.research_campaign import (
            available_julia_image,
        )

        return available_julia_image(profile.root, analysis)
    from carbon.development_session.research_campaign import registered_julia_image

    return registered_julia_image(profile.root, profile.manifest["runtime"], analysis)


def _remote(profile):
    """The campaign's practice runner on the miner's own remote setup, or
    None: built by the Challenge's own campaign from the frozen runtime and
    the profile's `remote_machine` (OWNER-MINER-COMPUTE-LINK-ONLY-01)."""
    from carbon.challenge_registry.campaigns import campaign_for_manifest
    from carbon.compute.remote_route import RUNTIME_KEY

    runtime = profile.manifest["runtime"]
    if RUNTIME_KEY not in runtime:
        # No remote practice: nothing to build, and nothing resolved here.
        return None
    campaign = campaign_for_manifest(profile.manifest)
    return campaign.remote_runner(
        runtime,
        profile.document.get("remote_machine"),
        campaign.gpu_image(profile.root, runtime),
    )


def _gpu_image(root, runtime, role_root):
    """One resolver, shared with the campaign runner that now also composes this."""
    from carbon.development_session.gpu_research import registered_gpu_image

    return registered_gpu_image(root, runtime, role_root)


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
        if self.closed or private_json(self.profile.path) != self.profile.document:
            raise ValueError("operator profile changed or controller closed")
        retained = self.ledger.retained_owner(self.profile.manifest["owner"])
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
        self.ledger.authority(profile.manifest)
        with self.ledger.db() as db:
            started = db.execute("SELECT started FROM campaign WHERE id=1").fetchone()[
                0
            ]
        # The miner's own elapsed budget, if they set one; none is no deadline.
        elapsed = profile.manifest.get("elapsed_seconds")
        if started is not None and (
            now < started or (elapsed is not None and now >= started + elapsed)
        ):
            raise ValueError("campaign elapsed budget reached")
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
        kind, expected = (
            "envelope",
            [
                julia_burgers_scope(image, role_root),
                julia_envelope_scope(image, role_root),
            ],
        )
    else:
        raise ValueError("unsupported scientific scope combination")
    if canonical(scopes) != canonical(expected):
        raise ValueError("registered scientific scope differs")
    return kind, expected


def _science(ledger, owner, image, role_root, *, cleanup_only=False, authored=None):
    from carbon.development_session.research_data import PublicReferenceData
    from carbon.development_session.research_provider import PublicPractice

    # The runtime the campaign was frozen with - never a grant's, which no
    # product campaign has.
    with ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    runtime = json.loads(row[0]).get("runtime", {}) if row else {}
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
    gpu = _gpu_image(ledger.root, runtime, role_root)
    if gpu is not None:
        from carbon.development_session.gpu_research import PublicGPUPractice

        return material, PublicGPUPractice(
            data=data, image=gpu, cleanup_only=cleanup_only
        )
    return material, PublicPractice(data=data, ledger=ledger, owner=owner, image=image)


@contextlib.asynccontextmanager
async def attached(configuration: Path, campaign: str, *, cleanup_only=False):
    """Attach to one of the miner's own campaigns, named by its id.

    Yields ``(adapter, profile)``; see `attached_profile`.
    """
    profile = load_profile(configuration, campaign, cleanup_only=cleanup_only)
    async with attached_profile(profile) as attachment:
        yield attachment


@contextlib.asynccontextmanager
async def attached_profile(profile: OperatorProfile):
    """Hold the existing campaign ownership lock for the whole attachment.

    Yields ``(adapter, profile)``. The caller chooses the surface it is served
    through; this owns the lock, generation, reconciliation and cleanup, so no
    second consumer reimplements campaign ownership.
    """
    from scripts.dev.miner_launchpad.controller import owner_lock
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    if type(profile) is not OperatorProfile:
        raise TypeError("a loaded operator profile is required")
    cleanup_only = profile.cleanup_only
    # A held lock is `LockHeld`: `refusal_code` names it campaign_busy.
    with owner_lock(profile.root):
        if profile.development_grant is None and not cleanup_only:
            from scripts.dev.miner_launchpad.runner import install_research_images

            # The same install the Launchpad does at launch: the host's
            # current image records, available to this campaign now.
            with _check("runtime_unavailable"):
                install_research_images(profile.document, profile.root)
        ledger = CampaignLedger(profile.root, admission=profile.development_grant)
        # A read-only refusal needs no session: unresolved consumption is
        # refused before anything reaches the runtime.
        with ledger.db() as db:
            if (
                not cleanup_only
                and db.execute(
                    "SELECT 1 FROM operations WHERE state='RESERVED' LIMIT 1"
                ).fetchone()
            ):
                raise AttachRefused(
                    "reconciliation_required",
                    "unresolved consumption requires reconciliation",
                )
        # Registration before any write: the campaign's frozen record, its
        # control generation and its prepared tasks are not touched until the
        # authenticated owner is known to be the registered one. The
        # connection's session files already exist from launch.
        with _check("runtime_unavailable"):
            connection, image, analysis, _ = _runtime(profile)
        # Practice on the miner's own remote setup, from their profile: a
        # machine that does not match the frozen campaign is refused here,
        # before any request; nothing is reached until a trial runs.
        with _check("remote_setup_unavailable"):
            remote = None if cleanup_only else _remote(profile)
        with _check("registration_check_failed"):
            owner = await _requester(connection)
        if owner != profile.manifest.get("owner"):
            # Resuming would not fix this: preparation refuses the same
            # change. The campaign needs the miner it was launched under.
            raise AttachRefused(
                "campaign_owner_changed", "authenticated campaign owner changed"
            )
        if not cleanup_only:
            # Must match the existing immutable record.
            with _check("campaign_manifest_differs"):
                ledger.freeze(profile.manifest)
        _prepared_tasks(profile.root, cleanup_only=cleanup_only)
        control = CampaignControl(ledger)
        status = control.status()
        # A miner's own campaign may be attached while paused; a granted
        # development campaign (Carbon's Workbench) keeps the historical rule.
        product = profile.development_grant is None
        if not cleanup_only:
            _refuse_unavailable(status, paused_ok=product)
        # Attaching to a paused campaign does not resume it (D12): its own
        # tools run while attached - the Tools tab of an autonomous campaign
        # the miner paused - and detaching leaves it paused. The pause is
        # lifted for the attachment, whose lock keeps every other holder out,
        # and asked again before it settles.
        repause = not cleanup_only and product and status["desired"] == "PAUSE"
        if repause:
            control.request("resume")
        try:
            ledger.generation = (
                status["generation"] if cleanup_only else control.acquire()
            )
            if cleanup_only:
                ledger.retained_owner(profile.manifest["owner"])
            from carbon.challenge_registry.campaigns import campaign_for_manifest
            from carbon.development_session.capability_demand import DemandStore

            # Capability demand on this host: registry ids and miner digests
            # only. On a miner's machine it stays theirs.
            demand = DemandStore(profile.root / "capability-demand.sqlite")
            with _check("runtime_unavailable"):
                campaign = campaign_for_manifest(profile.manifest)
                composition, wrapper = campaign.compose(
                    ledger=ledger,
                    owner=owner,
                    image=image,
                    analysis=analysis,
                    connection=connection,
                    demand=demand,
                    cleanup_only=cleanup_only,
                    julia_image=_authored_image(profile, analysis),
                    gpu_image=campaign.gpu_image(
                        profile.root, profile.manifest["runtime"]
                    ),
                    remote=remote,
                )
        except BaseException:
            if repause:
                _pause_again(control)
            raise
        bound = None
        try:
            bound = _AdmittedConnection(connection, profile, ledger, control)
            sdk = ResearchMinerTools(
                connection=bound,
                wrapper=wrapper,
                composition=composition,
                ledger=ledger,
                owner=owner,
            )
            adapter = ResearchToolAdapter(sdk, principal=owner)
            try:
                yield adapter, profile
            finally:
                await adapter.shutdown_tasks()
        finally:
            try:
                if bound is None and repause:
                    _pause_again(control)
                if bound is not None:
                    bound.closed = True
                    # A cancelled transport await does not cancel to_thread workers.
                    # Retain ownership until their existing deadline supervisors end.
                    clean = False
                    try:
                        await asyncio.get_running_loop().shutdown_default_executor()
                        clean = RunnerAdapter._cleanup(ledger)
                    finally:
                        if repause:
                            # Asked again before settling, so it settles PAUSED.
                            _pause_again(control)
                        if not cleanup_only or status["state"] not in {
                            "STOPPED",
                            "COMPLETED",
                        }:
                            control.settled(
                                ledger.generation,
                                cleanup_verified=clean,
                                ready=_waits_for_its_miner(profile, control),
                            )
                        elif not clean:
                            raise ValueError(
                                "terminal campaign cleanup requires reconciliation"
                            )
            finally:
                composition.tasks.close()


def _refuse_unavailable(status, *, paused_ok):
    """Refuse, by name, attaching to a campaign that takes no research: one
    awaiting reconciliation, stopped (or stopping) or complete, and - unless
    `paused_ok` - paused. A miner's paused campaign is attachable (D12);
    before 2026-10-03 every campaign not asked to RUN was refused, so the
    Tools tab could not open on an autonomous campaign even after the page
    told its miner to pause it."""
    unavailable = "campaign is not available for research"
    if status["state"] == "RECONCILIATION_REQUIRED":
        raise AttachRefused("reconciliation_required", unavailable)
    if status["state"] == "STOPPED" or status["desired"] == "STOP":
        raise AttachRefused("campaign_stopped", unavailable)
    if status["state"] == "COMPLETED":
        raise AttachRefused("campaign_complete", unavailable)
    if status["desired"] == "PAUSE" and not paused_ok:
        raise AttachRefused("campaign_paused", unavailable)


def _pause_again(control):
    """Ask again for the pause an attachment lifted (D12). A stop asked
    meanwhile stands. A resume the miner asked for meanwhile was refused
    `campaign_busy` while the attachment held the campaign, and its next
    action says to try again after detaching, so the pause is restored."""
    if control.status()["desired"] == "RUN":
        control.request("pause")


def _waits_for_its_miner(profile, control):
    """Whether detaching leaves the campaign READY: one waiting for its miner
    (`research_campaign.waits_for_its_miner`: no agent, or a candidate its
    agent selected that the validator did not evaluate), not complete, and
    not asked to pause or stop meanwhile. Until 2026-10-03 detaching settled
    every campaign INTERRUPTED, so an agent-less campaign looked broken after
    its miner's agent detached; until 2026-10-04 an agent campaign holding a
    retained candidate still did (LP-PROD-FIX-01)."""
    from carbon.development_session.research_campaign import waits_for_its_miner

    return (
        not profile.cleanup_only
        and waits_for_its_miner(profile.root, profile.manifest)
        and control.status()["desired"] == "RUN"
    )


async def serve(configuration: Path, campaign: str, *, cleanup_only=False):
    """Hold the existing campaign ownership lock for the whole stdio lifetime."""
    async with attached(configuration, campaign, cleanup_only=cleanup_only) as (
        adapter,
        _,
    ):
        await create_stdio_server(adapter).run_async()


def _setup_door(server, state_dir=None, *, operations=True):
    """Miner setup on this live server, over the Control Center's own setup
    records (OWNER-MINER-SETUP-AGENT-FIRST-01): status and the open-tier
    steps now, the later steps once registration is confirmed, and, when
    `operations`, the registered tier once review writes the profile.

    Returns the door and what it attached (`host`, `attachment`) for the
    caller to close.
    """
    from carbon.miner_mcp.mcp_setup import SetupDoor
    from scripts.dev.miner_launchpad.environment_setup import (
        DEFAULT_STATE_DIR,
        EnvironmentSetup,
    )
    from scripts.dev.miner_launchpad.onboarding import BrowserOnboarding

    held = {}
    setup = EnvironmentSetup(
        Path(state_dir) if state_dir is not None else DEFAULT_STATE_DIR,
        onboarding=BrowserOnboarding(),
    )

    def attach(profile):
        from carbon.miner_mcp.mcp_operations import Attachment
        from carbon.miner_mcp.open_tier import attach_operations
        from scripts.dev.miner_launchpad.runner import RunnerAdapter

        host = RunnerAdapter.for_profile(profile)
        attachment = Attachment(server, profile)
        names = attach_operations(server, host, attachment)
        held.update(host=host, attachment=attachment)
        door.count = lambda: len(host.recent())
        return names

    door = SetupDoor(server, setup, attach_operations=attach if operations else None)
    door.install()
    return door, held


async def _release(held):
    if "attachment" in held:
        await held["attachment"].detach()
    if "host" in held:
        held["host"].close()


async def serve_operations(configuration: Path, state_dir=None):
    """A miner's own client with their runner profile: the whole journey.

    Onboarding (the open tier, reading Carbon's testnet), every operation in
    the shared table - launch with or without an agent, observe, practice,
    freeze, submit, halt, resume - and attach/detach for deeper research. The
    operation tools are generated from the same table as the browser's routes,
    through the same campaign host over the same records. Nothing on this path
    is issued by Carbon.

    This process is a client of the campaigns' supervisor (LP-PROD-C): it
    admits and queues launch, resume, practice, freeze and submit, and the
    Control Center - or, when none is running, a detached supervisor it
    starts - carries them out. So the client exiting, as stdio clients do,
    leaves every campaign running or settled where it was; it never owns a
    campaign thread. An attached campaign is detached on exit.
    """
    from carbon.miner_mcp.mcp_operations import (
        Attachment,
        make_attachment_tools,
        make_operation_tools,
    )
    from carbon.miner_mcp.open_tier import create_open_tier_server
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    with _check("runner_profile_unusable"):
        host = RunnerAdapter.for_profile(configuration)

    def host_facts():
        # Discovery reports what this operator's host can run: its configured
        # worker image counts only once it loads and passes the doctor.
        from carbon.miner_mcp.mcp_challenges import configured_host_facts

        try:
            profile = host.configured()
        except Exception:  # noqa: BLE001 - an unusable profile configures nothing
            profile = None
        return configured_host_facts(profile)

    from carbon.miner_mcp.mcp_skills import make_skills_extension

    # The research skill is fixed guidance that grants nothing. An MCP
    # extension cannot be added once a client has initialized, so it is
    # registered here, where attach can reach it (RSURF-D6).
    server = create_open_tier_server(
        host_facts=host_facts, extensions=[make_skills_extension(guard=None)]
    )
    attachment = Attachment(server, configuration)
    tools = server._tool_manager._tools
    for tool in [*make_operation_tools(host), *make_attachment_tools(attachment)]:
        tools[tool.name] = tool
    # Setup too, over the same records: the operations are already here.
    door, _ = _setup_door(server, state_dir, operations=False)
    door.count = lambda: len(host.recent())
    try:
        # A raw MCPServer: stdio is `run_stdio_async`. (The `run_async` of
        # `create_stdio_server` belongs to its wrapper, not to this class.)
        await server.run_stdio_async()
    finally:
        await attachment.detach()
        host.close()


async def serve_open_tier(state_dir=None):
    """Serve the open tier: no profile, no grant, no campaign, no lock.

    Deliberately not a degraded version of `serve`. It takes no ownership lock
    because it owns nothing, and it reconciles nothing because it consumes
    nothing - which is the same statement as the tier rule that nothing here
    creates a campaign, consumes compute or touches the ledger.

    Onboarding reads Carbon's own testnet by default - the same context the
    browser door uses (`chain_onboarding.carbon_testnet_context`) - so `status`
    and `confirm` answer from public chain state on either door.

    Setup rides on it (OWNER-MINER-SETUP-AGENT-FIRST-01): status, the signer
    check and the registration confirmation from the start, the later steps
    once registration is confirmed, and the registered tier's operations once
    review writes the profile, all in this one session. Setup writes only its
    own records under `state_dir` (the Control Center's, by default); it
    creates no campaign and touches no ledger.
    """
    from carbon.miner_mcp.open_tier import create_open_tier_server

    # A raw MCPServer, whose stdio entry point is `run_stdio_async`. This read
    # `run_async` - the wrapper method of `create_stdio_server` - so the bare
    # open tier failed as soon as a client connected; its test replaced this
    # function and so never ran it.
    server = create_open_tier_server()
    _, held = _setup_door(server, state_dir)
    try:
        await server.run_stdio_async()
    finally:
        await _release(held)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--configuration",
        type=Path,
        help=(
            "Your private runner profile. With it and no --campaign: onboarding "
            "and every miner operation, including launch. Omit it to serve the "
            "open tier alone: registration onboarding and the published "
            "validator exam environment."
        ),
    )
    parser.add_argument(
        "--campaign",
        help="Which of your campaigns to attach to (its id under campaigns_root).",
    )
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Observe/cancel retained owned tasks; cannot start research",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        help=(
            "Where setup's records live: the Control Center's state directory "
            "(default ~/.carbon/development-launchpad), so the page and your "
            "agent share one setup."
        ),
    )
    args = parser.parse_args(argv)
    if args.configuration is None and (args.cleanup_only or args.campaign):
        parser.error("--campaign and --cleanup-only need your runner profile")
    if args.cleanup_only and not args.campaign:
        parser.error("--cleanup-only needs the --campaign to clean up")
    try:
        if args.configuration is None:
            asyncio.run(
                serve_open_tier()
                if args.state_dir is None
                else serve_open_tier(state_dir=args.state_dir)
            )
        elif not args.campaign:
            # With a profile and no campaign: every operation, including
            # launching one. A miner's own client needs nothing Carbon issues.
            asyncio.run(
                serve_operations(args.configuration)
                if args.state_dir is None
                else serve_operations(args.configuration, state_dir=args.state_dir)
            )
        else:
            asyncio.run(
                serve(args.configuration, args.campaign, cleanup_only=args.cleanup_only)
            )
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001
        # The open tier has no profile, grant or campaign to verify, so it must
        # not be told to go and check them.
        print(
            (
                unavailable_message(exc)
                if args.configuration is not None
                else "Carbon MCP unavailable."
            ),
            file=sys.stderr,
        )
        return 2
    return 0


def unavailable_message(exc):
    """What a miner's terminal is told when this door cannot serve: the
    check that failed, by its closed code, and the next action for it
    (`supervisor.NEXT_ACTIONS`) - a task left RUNNING, for one, says to attach
    with --cleanup-only. Never the exception's message, a path or a secret.
    Before 2026-10-03 every failure printed one sentence asking the miner to
    verify six things at once (LP-PROD-C D8).

    A refusal that carries its own next step (`runner.stepped`: a runner
    profile that no longer describes this install, with what clears it and
    why) is told that step, as the Control Center prints and its HTTP door
    sends it, rather than the catalog's general one (W1 repair)."""
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.supervisor import FALLBACK_ACTION, NEXT_ACTIONS

    if isinstance(exc, KeyboardInterrupt):
        code = "carbon_mcp_interrupted"
    else:
        code = refusal_code(exc) or "carbon_mcp_failed"
    step = getattr(exc, "next_step", None) if isinstance(exc, Rejected) else None
    if type(step) is str and step:
        return f"Carbon MCP unavailable: {code}. Next: {step.rstrip('.')}."
    return f"Carbon MCP unavailable: {code}. {NEXT_ACTIONS.get(code, FALLBACK_ACTION)}"


if __name__ == "__main__":
    raise SystemExit(main())
