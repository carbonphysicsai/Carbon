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
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from carbon import research
from carbon.chain.models import CARBON_NETUID
from carbon.development_session.private_records import private_json
from carbon.development_session.profile import CHALLENGE, canonical, digest
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import PRODUCT, VERSION, CampaignLedger
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_tools import (
    DirectResearchMinerTools,
    ResearchMinerTools,
)
from carbon.miner_mcp.standard import ResearchToolAdapter
from carbon.miner_mcp.standard_server import (
    create_direct_stdio_server,
    create_stdio_server,
)


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


@dataclass(frozen=True)
class DirectDevelopmentAttachment:
    """Trusted operator-selected synthetic kit and existing execution handles.

    This object is supplied by a local operator composition, never parsed from
    MCP arguments or a product campaign profile. Its version is a prospective
    public DEVELOPMENT fixture, not an official served Challenge.
    """

    root: Path
    version: str
    owner: str
    connection: object
    ledger: CampaignLedger
    image: object
    inference_image: object
    image_resolver: object = None


@dataclass(frozen=True)
class DirectInstalledSource:
    """Validated local install inputs, before opening a research task store."""

    root: Path
    cache_root: Path
    version: str
    parent: object
    context: object
    publisher: str
    signer: object
    implementation: dict
    profile_digest: str
    worker_image_id: str
    analysis_image_id: str


DIRECT_KIT_VERSIONS = ("1.1", "1.2", "1.3")


def _direct_material(version):
    """Resolve only a registered kit, without importing a newer kit for old work."""
    from carbon.challenge_kit import synthetic_linear_field_2d as kit

    if type(version) is not str or version not in DIRECT_KIT_VERSIONS:
        raise AttachRefused("direct_development_kit_unavailable", "unknown direct kit")
    selected = {
        "1.1": kit.bundle_material_v3,
        "1.2": kit.bundle_material_v4,
        "1.3": getattr(kit, "bundle_material_v5", None),
    }.get(version)
    if selected is None:
        raise AttachRefused("direct_development_kit_unavailable", "unknown direct kit")
    return selected


def _retained_direct_parent(encoded, expected_image_id):
    """Read the existing bundle or graph task image row for cleanup custody."""
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    identity = json.loads(encoded)
    if type(identity) is not list or (
        len(identity) != 4
        and not (len(identity) == 2 and identity[0] == "GRAPH_PARENT")
    ):
        raise ValueError("prior direct image custody differs")
    candidate = WorkerImageIdentity(**identity[1])
    if candidate.image_id != expected_image_id:
        raise ValueError("prior direct image parent differs")
    return candidate


def _direct_development_parent_compatible(image, implementation):
    """Check an older registered base for this public v1.3 construction route.

    The fixed construction program is staged from the current source. The
    embedded entrypoint still runs, and the embedded exporter must emit the
    C03 v1 stream that the current controller validates during the actual
    bounded run. This check grants no official or general installed-runtime
    compatibility.
    """
    from carbon.development_session.gpu_practice import direct_parent_backend
    from carbon.development_session.research_campaign import verify_direct_v13_worker

    role = {
        "jax": "jax_gpu",
        "pytorch": "torch_gpu",
        "torch_cpu": "torch_cpu",
    }.get(direct_parent_backend(image))
    if role is None:
        raise ValueError("installed direct parent backend is unregistered")
    verify_direct_v13_worker(image, implementation, role=role)


def load_direct_installed_source(configuration: Path, *, version="1.2"):
    """Reuse setup's accepted profile, pinned parent and external signer.

    The synthetic kit is a local DEVELOPMENT lane. This does not remap any
    frozen product campaign to that kit or grant a validator authority.
    """
    from carbon.chain.external_signer import miner_signer
    from carbon.development_session.gpu_practice import (
        direct_parent_backend,
        gpu_image_backend,
    )
    from carbon.development_session.miner_network import binding
    from carbon.development_session.research_campaign import (
        accepted_implementation,
        private_file,
        verify_current_worker,
        verify_direct_v13_worker,
    )
    from carbon.development_session.research_image import (
        load_analysis_image,
        verify_image,
    )
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity
    from scripts.dev.miner_launchpad import installed
    from scripts.dev.miner_launchpad.runner import validated_profile

    _direct_material(version)
    with _check("runner_profile_unusable"):
        cfg = validated_profile(private_json(configuration))
    if cfg["enabled"] is not True:
        raise AttachRefused(
            "research_dispatch_disabled", "closed enabled operator profile required"
        )
    base = Path(cfg["campaigns_root"])
    if not base.is_dir() or base.is_symlink() or base.resolve(strict=True) != base:
        raise AttachRefused("runner_profile_unusable", "private owner root required")
    state = base / ".direct-development"
    if state.is_symlink() or (state.exists() and not state.is_dir()):
        raise AttachRefused("runner_profile_unusable", "private direct root differs")
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    with _check("carbon_updated_rerun_installer"):
        implementation = (
            installed.profile_candidate(configuration, cfg)
            if version == "1.3"
            else None
        )
        development_candidate = implementation is not None
        if implementation is None:
            implementation = accepted_implementation(cfg["accepted_revision"])
        parent = load_image_identity(paths["image_manifest"])
        try:
            verify_current_worker(parent, implementation)
        except ValueError:
            if version != "1.3" or (
                direct_parent_backend(parent) == "torch_cpu"
                and not development_candidate
            ):
                raise
            role = (
                "torch_cpu" if direct_parent_backend(parent) == "torch_cpu" else "cpu"
            )
            verify_direct_v13_worker(parent, implementation, role=role)
        if version == "1.3" and direct_parent_backend(parent) == "torch_cpu":
            verify_direct_v13_worker(parent, implementation, role="torch_cpu")
        analysis = load_analysis_image(paths["analysis_image_manifest"])
        verify_image(analysis)
        if analysis.parent_image != parent.image_id:
            raise ValueError("analysis image parent differs")
        if (
            development_candidate
            or (version == "1.3" and direct_parent_backend(parent) == "torch_cpu")
        ) and cfg["runtime"].get("images") != [parent.image_id, analysis.image_id]:
            raise ValueError("development candidate profile images differ")
        gpu_manifest = cfg.get("gpu_image")
        if (
            gpu_manifest is None
            and version == "1.3"
            and (development_candidate or direct_parent_backend(parent) == "torch_cpu")
        ):
            # A verified primary CPU worker also serves direct inference;
            # selecting it does not acquire GPU authority.
            if "gpu_research" in cfg["runtime"]:
                raise ValueError("declared GPU direct parent is missing")
            direct_parent = parent
        else:
            if type(gpu_manifest) is not str:
                raise ValueError("installed GPU parent required for direct development")
            direct_parent = load_image_identity(Path(gpu_manifest))
            if version == "1.3":
                _direct_development_parent_compatible(direct_parent, implementation)
            else:
                verify_current_worker(direct_parent, implementation)
            registered = (
                direct_parent_backend(direct_parent)
                if version == "1.3"
                else gpu_image_backend(direct_parent)
            )
            if registered not in (
                {"jax", "pytorch", "torch_cpu"}
                if version == "1.3"
                else {"jax", "pytorch"}
            ):
                raise ValueError("installed direct parent backend is unregistered")
    with _check("runtime_unavailable"):
        if not doctor(
            image_id=direct_parent.image_id, image_identity=direct_parent
        ).eligible:
            raise ValueError("installed direct parent unavailable")
    with _check("runner_profile_unusable"):
        network = binding(
            operator_config=paths.get("operator_config"),
            miner_network=paths.get("miner_network"),
        )
        public = json.loads(private_file(paths["miner_public"]).read_bytes())
        if (
            public["netuid"] != CARBON_NETUID
            or network.netuid != CARBON_NETUID
            or public["hotkey"] != cfg["principal"]
        ):
            raise AttachRefused(
                "registration_wrong_network", "installed miner identity differs"
            )
        signer = miner_signer(public, paths.get("signer_socket"))
    return DirectInstalledSource(
        root=state / ("kit-" + version) / direct_parent.image_id[7:],
        cache_root=state / "library-cache",
        version=version,
        parent=direct_parent,
        context=network.context,
        publisher=network.publisher_hotkey,
        signer=signer,
        implementation=implementation,
        profile_digest=digest(
            canonical(
                {
                    "accepted_revision": cfg["accepted_revision"],
                    "principal": cfg["principal"],
                    "implementation": implementation,
                    "worker_image": parent.image_id,
                    "analysis_image": analysis.image_id,
                    "direct_parent_image": direct_parent.image_id,
                    "gpu_research": cfg["runtime"].get("gpu_research"),
                }
            )
        ),
        worker_image_id=parent.image_id,
        analysis_image_id=analysis.image_id,
    )


def _installed_direct_manifest(source: DirectInstalledSource, owner: str) -> dict:
    """Bind a local direct kit to the validated install before worker dispatch."""
    material = _direct_material(source.version)()
    kit = material["construction_kit"]
    if kit["version"] != source.version:
        raise ValueError("installed direct kit version differs")
    return {
        "schema": VERSION,
        "campaign_id": (
            "direct-development-" + source.version + "-" + source.parent.image_id[7:]
        ),
        "owner": owner,
        "implementation": source.implementation,
        "objective": {"scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY", "kit": kit},
        "sampling": {"train_digest": kit["train_digest"]},
        "control": {
            "mode": "installed_direct_development",
            "admission": "chain_registration",
        },
        "selection": {
            "challenge_id": kit["id"],
            "challenge_version": kit["version"],
        },
        "replica_policy": {"mode": "one_recipe_per_task"},
        "provider": {
            "profile_digest": source.profile_digest,
            "publisher_hotkey": source.publisher,
            "network": source.context.network,
            "genesis_hash": source.context.genesis_hash,
            "netuid": source.context.netuid,
        },
        "images": [
            source.worker_image_id,
            source.analysis_image_id,
            source.parent.image_id,
        ],
        "construction_limits_digest": kit["construction_limits_digest"],
        "allowlist_digest": material["allowlist_digest"],
    }


class DirectOwnerImageResolver:
    """Resolve owner-staged source first and a verified child after admission.

    Source inspection reads no image receipt and performs no build. The admitted
    task revalidates the closure and verifies or provisions its chosen child.
    A miner cannot supply a host path or choose the construction parent.
    """

    def __init__(self, cache_root, parent=None, *, material_cache_bytes=None):
        from carbon.reconstruction.worker.model import WorkerImageIdentity

        if (
            not isinstance(cache_root, Path)
            or not cache_root.is_absolute()
            or cache_root.is_symlink()
            or (parent is not None and type(parent) is not WorkerImageIdentity)
            or (
                material_cache_bytes is not None
                and (type(material_cache_bytes) is not int or material_cache_bytes <= 0)
            )
        ):
            raise ValueError("trusted owner cache and optional parent required")
        self.cache_root, self.parent = cache_root, parent
        self.material_cache_bytes = material_cache_bytes

    def inspect_source(self, bundle):
        """Pure preflight: require exact source/lock/wheels, no image receipt."""
        from carbon.development_session.library_environment_cache import (
            inspect_staged_bundle_material,
        )

        inspect_staged_bundle_material(self.cache_root, bundle)
        return bundle

    def provision_admitted(self, bundle, *, parent, cli):
        """Verify a compatible child; bounded cache-miss build is not available."""
        from carbon.development_session.gpu_practice import direct_parent_backend
        from carbon.development_session.library_environment_cache import (
            inspect_staged_bundle_material,
            library_image_cache_paths,
            load_cached_library_worker_image,
        )
        from carbon.development_session.research_image import (
            verify_library_worker_image,
        )
        from carbon.reconstruction.worker.model import WorkerImageIdentity

        if type(parent) is not WorkerImageIdentity:
            raise ValueError("trusted construction parent required")
        expected_backends = {
            "python-cpu-py311": None,
            "jax-cuda13-py311": "jax",
            "torch-cu130-py311": "pytorch",
            "torch-cpu-py311": "torch_cpu",
        }
        if (
            bundle.runtime_profile_id not in expected_backends
            or direct_parent_backend(parent)
            != expected_backends[bundle.runtime_profile_id]
        ):
            raise ValueError("construction parent differs from bundle runtime")
        inspect_staged_bundle_material(self.cache_root, bundle)
        receipt, context = library_image_cache_paths(self.cache_root, bundle, parent)
        if not receipt.is_file() or receipt.is_symlink():
            raise FileNotFoundError(
                "bounded automatic dependency build unavailable; verified child missing"
            )
        image = load_cached_library_worker_image(
            receipt,
            expected_bundle=bundle,
            expected_parent=parent,
            context_root=context.parent,
        )
        return verify_library_worker_image(image, cli)

    def __call__(self, bundle):
        from carbon.development_session.gpu_practice import direct_parent_backend
        from carbon.development_session.library_environment_cache import (
            library_image_cache_paths,
            load_cached_library_worker_image,
        )

        if self.parent is None:
            raise ValueError("trusted construction parent required")
        expected_backends = {
            "python-cpu-py311": None,
            "jax-cuda13-py311": "jax",
            "torch-cu130-py311": "pytorch",
            "torch-cpu-py311": "torch_cpu",
        }
        if (
            bundle.runtime_profile_id not in expected_backends
            or direct_parent_backend(self.parent)
            != expected_backends[bundle.runtime_profile_id]
        ):
            raise ValueError("installed parent backend differs from recipe bundle")
        if not self.cache_root.is_dir():
            raise FileNotFoundError("owner library cache is not installed")
        receipt, context = library_image_cache_paths(
            self.cache_root, bundle, self.parent
        )
        if not receipt.is_file() or receipt.is_symlink():
            raise FileNotFoundError("verified owner bundle receipt is missing")
        return load_cached_library_worker_image(
            receipt,
            expected_bundle=bundle,
            expected_parent=self.parent,
            context_root=context.parent,
        )


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
    from scripts.dev.miner_launchpad import installed

    cfg = profile.document
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    # This checkout and its worker images are the ones the profile accepted:
    # not, after an update the installer has not accepted yet.
    with _check("carbon_updated_rerun_installer"):
        implementation = installed.profile_candidate(profile.path, cfg)
        development_candidate = implementation is not None
        if implementation is None:
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
    if development_candidate and cfg["runtime"].get("images") != [
        image.image_id,
        analysis.image_id,
    ]:
        raise AttachRefused(
            "carbon_updated_rerun_installer", "development candidate images differ"
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


async def _requester(connection, challenge=CHALLENGE, *, expected_hotkey=None):
    """Authenticate a hotkey while preserving its derived A7 requester identity."""
    from carbon.chain.auth import BittensorMessageSigner
    from carbon.transport.models import message

    snapshot = await connection.check_registration()
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(challenge),
    )
    body = message(
        connection.chain_context,
        snapshot.snapshot_id,
        challenge,
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
    received = await connection.service.gateway.receive(body, headers)
    if expected_hotkey is not None and received.receipt.hotkey != expected_hotkey:
        raise AttachRefused(
            "campaign_owner_changed", "authenticated direct owner changed"
        )
    return received.requester.value


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
async def attached_direct_development(attachment: DirectDevelopmentAttachment):
    """Attach one exact synthetic DEVELOPMENT kit with the existing signer.

    Product campaign manifests are intentionally ineligible here. A trusted
    local operator must supply the already provisioned bundle image, parent,
    private ledger/root and connection; the authenticated requester must match
    that operator's owner before the durable provider is opened.
    """
    from carbon.development_session.direct_research_composition import (
        compose_synthetic_direct_development,
    )
    from scripts.dev.miner_launchpad.controller import owner_lock

    if type(attachment) is not DirectDevelopmentAttachment:
        raise TypeError("trusted direct DEVELOPMENT attachment required")
    selected = _direct_material(attachment.version)
    if (
        not isinstance(attachment.root, Path)
        or not attachment.root.is_absolute()
        or attachment.root.is_symlink()
        or type(attachment.owner) is not str
        or not attachment.owner
        or type(attachment.ledger) is not CampaignLedger
        or attachment.ledger.root.parent != attachment.root
    ):
        raise ValueError("private exact direct DEVELOPMENT composition required")
    key = selected()["challenge_key"]
    with owner_lock(attachment.root):
        owner = await _requester(attachment.connection, challenge=key)
        if owner != attachment.owner:
            raise AttachRefused(
                "campaign_owner_changed", "authenticated direct owner changed"
            )
        composition, wrapper = compose_synthetic_direct_development(
            version=attachment.version,
            root=attachment.root / "direct-tasks",
            owner=owner,
            ledger=attachment.ledger,
            image=attachment.image,
            inference_image=attachment.inference_image,
            image_resolver=attachment.image_resolver,
            gateway=attachment.connection.service.gateway,
        )
        adapter = DirectResearchMinerTools(
            connection=attachment.connection,
            wrapper=wrapper,
            composition=composition,
            owner=owner,
        )
        try:
            yield adapter, attachment
        finally:
            try:
                await adapter.shutdown_tasks()
                await asyncio.get_running_loop().shutdown_default_executor()
            finally:
                composition.tasks.close()


@contextlib.contextmanager
def _guard_previous_direct_parents(selected_root: Path):
    """Hold prior parent roots and refuse a switch with unfinished custody.

    A previous parent cannot be reinterpreted under the selected image. Its
    own attachment must first reconcile or finish its retained work.
    """
    import fcntl

    from carbon.research import DirectTaskStateV3, DirectTaskViewV3
    from carbon.research.canonical import load_canonical
    from scripts.dev.miner_launchpad.controller import LockHeld, owner_lock

    terminal = {
        DirectTaskStateV3.SUCCEEDED,
        DirectTaskStateV3.REFUSED,
        DirectTaskStateV3.UNRESOLVED,
        DirectTaskStateV3.FAILED_INFRA,
        DirectTaskStateV3.CANCELLED,
    }
    with contextlib.ExitStack() as held:
        for previous in sorted(selected_root.parent.iterdir()):
            if previous == selected_root:
                continue
            if (
                not re.fullmatch(r"[0-9a-f]{64}", previous.name)
                or previous.is_symlink()
                or not previous.is_dir()
                or previous.resolve(strict=True) != previous
            ):
                raise AttachRefused(
                    "direct_previous_parent_unresolved", "prior direct root differs"
                )
            try:
                held.enter_context(owner_lock(previous))
            except LockHeld:
                raise AttachRefused(
                    "direct_previous_parent_unresolved", "prior direct root is active"
                ) from None
            tasks = previous / "direct-tasks"
            if tasks.is_symlink() or (tasks.exists() and not tasks.is_dir()):
                raise AttachRefused(
                    "direct_previous_parent_unresolved", "prior direct tasks differ"
                )
            if tasks.is_dir():
                supervisor_lock = tasks / "direct-supervisor.lock"
                if supervisor_lock.is_symlink():
                    raise AttachRefused(
                        "direct_previous_parent_unresolved",
                        "prior direct supervisor lock differs",
                    )
                handle = held.enter_context(supervisor_lock.open("a+b"))
                supervisor_lock.chmod(0o600)
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    raise AttachRefused(
                        "direct_previous_parent_unresolved",
                        "prior direct supervisor is active",
                    ) from None
            database = tasks / "direct-tasks.sqlite3"
            if database.is_symlink():
                raise AttachRefused(
                    "direct_previous_parent_unresolved", "prior direct store differs"
                )
            try:
                if database.exists():
                    with sqlite3.connect(
                        database.as_uri() + "?mode=ro", uri=True
                    ) as db:
                        views = db.execute("SELECT view FROM direct_tasks").fetchall()
                    for (body,) in views:
                        view = load_canonical(body, DirectTaskViewV3)
                        if view.state not in terminal:
                            raise AttachRefused(
                                "direct_previous_parent_unresolved",
                                "prior direct work must be reconciled in its own parent",
                            )
                ledger = previous / "ledger"
                if ledger.is_symlink() or (ledger.exists() and not ledger.is_dir()):
                    raise ValueError("prior direct ledger differs")
                ledger_store = ledger / "campaign.sqlite3"
                if ledger_store.is_symlink():
                    raise ValueError("prior direct ledger store differs")
                if ledger_store.exists():
                    with sqlite3.connect(
                        ledger_store.as_uri() + "?mode=ro", uri=True
                    ) as db:
                        reserved = db.execute(
                            "SELECT 1 FROM operations WHERE state='RESERVED' LIMIT 1"
                        ).fetchone()
                    if reserved is not None:
                        raise AttachRefused(
                            "direct_previous_parent_unresolved",
                            "prior direct child reservation is unresolved",
                        )
            except (sqlite3.Error, OSError, TypeError, ValueError) as exc:
                if isinstance(exc, AttachRefused):
                    raise
                raise AttachRefused(
                    "direct_previous_parent_unresolved", "prior direct store unreadable"
                ) from None
        yield


async def cleanup_installed_direct_development(configuration: Path) -> dict:
    """Operator-only reconciliation of retained direct work after an upgrade.

    This opens each original owner/parent task store without an accepted old
    image or a public service. It can settle interrupted children and cancel
    never-dispatched tasks, but it cannot start or observe a new task.
    """
    from carbon.chain.external_signer import miner_signer
    from carbon.development_session.direct_research_composition import (
        DirectDevelopmentConnection,
    )
    from carbon.development_session.miner_network import binding
    from carbon.development_session.research_campaign import private_file
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
    from carbon.research import DirectTaskStateV3
    from scripts.dev.miner_launchpad.controller import LockHeld, owner_lock
    from scripts.dev.miner_launchpad.runner import validated_profile

    with _check("runner_profile_unusable"):
        cfg = validated_profile(private_json(configuration))
        base = Path(cfg["campaigns_root"])
        if not base.is_dir() or base.is_symlink() or base.resolve(strict=True) != base:
            raise ValueError("private owner root required")
        public = json.loads(
            private_file(Path(cfg["paths"]["miner_public"])).read_bytes()
        )
        if (
            public.get("netuid") != CARBON_NETUID
            or public.get("hotkey") != cfg["principal"]
        ):
            raise ValueError("installed owner identity differs")
        paths = {name: Path(value) for name, value in cfg["paths"].items()}
        network = binding(
            operator_config=paths.get("operator_config"),
            miner_network=paths.get("miner_network"),
        )
        if network.netuid != CARBON_NETUID:
            raise ValueError("installed network identity differs")
        signer = miner_signer(public, paths.get("signer_socket"))
    state = base / ".direct-development"
    if state.is_symlink() or (state.exists() and not state.is_dir()):
        raise AttachRefused("direct_previous_parent_unresolved", "direct root differs")
    if not state.exists():
        return {"status": "DIRECT_CLEANUP_COMPLETE", "retained_tasks_checked": 0}
    auth_root = state / "cleanup-auth"
    if auth_root.is_symlink() or (auth_root.exists() and not auth_root.is_dir()):
        raise AttachRefused(
            "direct_previous_parent_unresolved", "direct cleanup auth root differs"
        )
    auth_root.mkdir(mode=0o700, exist_ok=True)
    auth_root.chmod(0o700)
    if auth_root.resolve(strict=True) != auth_root:
        raise AttachRefused(
            "direct_previous_parent_unresolved", "direct cleanup auth root differs"
        )
    checked = 0
    for version in DIRECT_KIT_VERSIONS:
        kit_root = state / ("kit-" + version)
        if kit_root.is_symlink() or (kit_root.exists() and not kit_root.is_dir()):
            raise AttachRefused(
                "direct_previous_parent_unresolved", "direct kit root differs"
            )
        if not kit_root.exists():
            continue
        material = _direct_material(version)
        connection = DirectDevelopmentConnection(
            root=auth_root / ("kit-" + version),
            version=version,
            chain_context=network.context,
            publisher=network.publisher_hotkey,
            miner_key=signer,
        )
        with _check("registration_check_failed"):
            owner = await _requester(connection, challenge=connection.challenge)
        for previous in sorted(kit_root.iterdir()):
            if (
                not re.fullmatch(r"[0-9a-f]{64}", previous.name)
                or previous.is_symlink()
                or not previous.is_dir()
                or previous.resolve(strict=True) != previous
            ):
                raise AttachRefused(
                    "direct_previous_parent_unresolved", "prior direct root differs"
                )
            tasks = previous / "direct-tasks"
            database = tasks / "direct-tasks.sqlite3"
            ledger_root = previous / "ledger"
            ledger_store = ledger_root / "campaign.sqlite3"
            if (
                tasks.is_symlink()
                or database.is_symlink()
                or ledger_root.is_symlink()
                or ledger_store.is_symlink()
                or (tasks.exists() and not tasks.is_dir())
                or (ledger_root.exists() and not ledger_root.is_dir())
            ):
                raise AttachRefused(
                    "direct_previous_parent_unresolved", "prior direct store differs"
                )
            try:
                with owner_lock(previous):
                    if not tasks.exists():
                        # Attachment creates the parent before registration. A
                        # root that never acquired a task store has no task
                        # custody, but a partial ledger still fails closed.
                        if ledger_root.exists():
                            if not ledger_store.is_file():
                                raise ValueError("prior direct ledger incomplete")
                            with sqlite3.connect(
                                ledger_store.as_uri() + "?mode=ro", uri=True
                            ) as db:
                                if db.execute(
                                    "SELECT 1 FROM operations LIMIT 1"
                                ).fetchone():
                                    raise ValueError("prior direct ledger has custody")
                        continue
                    if not database.is_file():
                        raise ValueError("prior direct task store incomplete")
                    with sqlite3.connect(
                        database.as_uri() + "?mode=ro", uri=True
                    ) as db:
                        binding = db.execute(
                            "SELECT identity FROM direct_binding WHERE id=1"
                        ).fetchone()
                        images = db.execute(
                            "SELECT identity FROM direct_task_images"
                        ).fetchall()
                        evidence = db.execute(
                            "SELECT 1 FROM direct_evidence LIMIT 1"
                        ).fetchone()
                        retained = db.execute(
                            "SELECT COUNT(*) FROM direct_tasks"
                        ).fetchone()[0]
                    expected = [
                        owner,
                        owner,
                        "PER_RECIPE_LIBRARY_IMAGE",
                        "sha256:" + previous.name,
                    ]
                    if binding is None or json.loads(binding[0]) != expected:
                        raise ValueError("prior direct owner or parent differs")
                    if not retained:
                        if images or evidence or not ledger_store.is_file():
                            raise ValueError("prior direct empty task custody differs")
                        with sqlite3.connect(
                            ledger_store.as_uri() + "?mode=ro", uri=True
                        ) as db:
                            if db.execute(
                                "SELECT 1 FROM operations LIMIT 1"
                            ).fetchone():
                                raise ValueError("prior direct ledger has custody")
                        continue
                    if not images:
                        raise ValueError("prior direct image custody missing")
                    parent = None
                    for (encoded,) in images:
                        candidate = _retained_direct_parent(encoded, expected[3])
                        if parent is not None and candidate != parent:
                            raise ValueError("prior direct image parent differs")
                        parent = candidate
                    if parent is None or not ledger_store.is_file():
                        raise ValueError("prior direct ledger or image missing")
                    ledger = CampaignLedger(previous / "ledger")
                    discovery = DirectFixtureDiscovery(material(), task_admission=True)

                    def no_dispatch(_bundle):
                        raise FileNotFoundError("cleanup never resolves an image")

                    provider = DirectDevelopmentTasksV3(
                        root=tasks,
                        requester=owner,
                        ledger=ledger,
                        owner=owner,
                        discovery=discovery,
                        image=None,
                        inference_image=parent,
                        image_resolver=no_dispatch,
                    )
                    try:
                        for task_id in provider.queued_tasks():
                            provider.cancel_observed_task(
                                task_id, discovery.info.challenge_key
                            )
                        if any(
                            view.state
                            not in {
                                DirectTaskStateV3.SUCCEEDED,
                                DirectTaskStateV3.REFUSED,
                                DirectTaskStateV3.UNRESOLVED,
                                DirectTaskStateV3.FAILED_INFRA,
                                DirectTaskStateV3.CANCELLED,
                            }
                            for view in provider._views.values()
                        ):
                            raise ValueError("prior direct task cleanup incomplete")
                        with sqlite3.connect(
                            ledger_store.as_uri() + "?mode=ro", uri=True
                        ) as db:
                            if db.execute(
                                "SELECT 1 FROM operations WHERE state='RESERVED' LIMIT 1"
                            ).fetchone():
                                raise ValueError("prior child cleanup incomplete")
                        checked += retained
                    finally:
                        provider.close()
            except LockHeld:
                raise AttachRefused(
                    "direct_previous_parent_unresolved", "prior direct root is active"
                ) from None
            except (sqlite3.Error, OSError, TypeError, ValueError) as exc:
                if isinstance(exc, AttachRefused):
                    raise
                raise AttachRefused(
                    "direct_previous_parent_unresolved",
                    "prior direct cleanup unresolved",
                ) from None
    return {"status": "DIRECT_CLEANUP_COMPLETE", "retained_tasks_checked": checked}


@contextlib.asynccontextmanager
async def attached_installed_direct_development(configuration: Path, *, version="1.2"):
    """Attach the local DEVELOPMENT kit through a miner's installed profile.

    This uses the maintained accepted worker, chain binding, external signer
    and owner root. A recipe chooses only an exact bundle ref; its image is
    resolved from the owner cache and verified by the task provider.
    """
    from carbon.development_session.direct_research_composition import (
        DirectDevelopmentConnection,
    )

    source = load_direct_installed_source(configuration, version=version)
    for directory in (source.root.parent, source.root, source.cache_root):
        if directory.is_symlink():
            raise AttachRefused(
                "runner_profile_unusable", "private direct root differs"
            )
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        if directory.resolve(strict=True) != directory:
            raise AttachRefused(
                "runner_profile_unusable", "private direct root differs"
            )
    with _guard_previous_direct_parents(source.root):
        connection = DirectDevelopmentConnection(
            root=source.root / "research-auth",
            version=source.version,
            chain_context=source.context,
            publisher=source.publisher,
            miner_key=source.signer,
        )
        with _check("registration_check_failed"):
            owner = await _requester(connection, challenge=connection.challenge)
        ledger = CampaignLedger(source.root / "ledger")
        with _check("campaign_manifest_differs"):
            ledger.freeze(_installed_direct_manifest(source, owner))
        attachment = DirectDevelopmentAttachment(
            root=source.root,
            version=source.version,
            owner=owner,
            connection=connection,
            ledger=ledger,
            image=None,
            inference_image=source.parent,
            image_resolver=DirectOwnerImageResolver(source.cache_root, source.parent),
        )
        async with attached_direct_development(attachment) as result:
            yield result


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


async def serve_direct_development(attachment: DirectDevelopmentAttachment):
    """Run direct synthetic DEVELOPMENT MCP from a trusted local attachment."""
    async with attached_direct_development(attachment) as (adapter, _):
        await create_direct_stdio_server(adapter).run_async()


async def serve_installed_direct_development(configuration: Path, *, version="1.2"):
    """Serve the local direct DEVELOPMENT kit from an accepted runner install."""
    async with attached_installed_direct_development(
        configuration, version=version
    ) as (adapter, _):
        await create_direct_stdio_server(adapter).run_async()


class _RemoteBatteryConnection:
    """Signed Battery upload ingress; no local research or worker service."""

    def __init__(self, *, root, chain_context, publisher, miner_key, challenge):
        from types import SimpleNamespace

        from carbon.chain.models import CARBON_NETWORK
        from carbon.development_session.service import authenticated_research_gateway

        if (
            not root.is_absolute()
            or root.is_symlink()
            or chain_context.netuid != CARBON_NETUID
            or chain_context.network != CARBON_NETWORK
            or miner_key.ss58_address == publisher
        ):
            raise ValueError("exact Battery DEVELOPMENT network connection required")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self.chain_context = chain_context
        self.publisher = publisher
        self.miner_key = miner_key
        self.challenge = challenge
        _, self.observed, gateway = authenticated_research_gateway(
            root, chain_context, publisher, challenge
        )
        self.service = SimpleNamespace(gateway=gateway)

    async def check_registration(self):
        from carbon.development_session.service import registered_research_snapshot

        return await registered_research_snapshot(
            self.chain_context, self.miner_key, self.publisher, self.observed
        )


@contextlib.asynccontextmanager
async def attached_remote_material_stage(configuration: Path, *, challenge):
    """Authenticate a signed upload without requiring local execution images."""
    from carbon.chain.external_signer import miner_signer
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.development_session.direct_research_composition import (
        DirectDevelopmentConnection,
    )
    from carbon.development_session.intake_targets import validate
    from carbon.development_session.miner_network import binding
    from carbon.development_session.research_campaign import private_file
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        BATTERY_CONTRACT,
    )
    from carbon.registry.model import ChallengeKey
    from scripts.dev.miner_launchpad.controller import owner_lock
    from scripts.dev.miner_launchpad.runner import validated_profile

    if challenge == ChallengeKey(BATTERY_CHALLENGE, BATTERY_CONTRACT.version):
        synthetic = False
        state_name = "remote-stage-battery-v1.0"
    else:
        synthetic = challenge == bundle_material_v5()["challenge_key"]
        if not synthetic:
            raise AttachRefused(
                "construction_recipe_challenge_mismatch",
                "unregistered recipe challenge",
            )
        _direct_material("1.3")
        state_name = "remote-stage-v1.3"
    with _check("runner_profile_unusable"):
        cfg = validated_profile(private_json(configuration))
    if cfg["enabled"] is not True:
        raise AttachRefused(
            "research_dispatch_disabled", "closed enabled operator profile required"
        )
    base = Path(cfg["campaigns_root"])
    if not base.is_dir() or base.is_symlink() or base.resolve(strict=True) != base:
        raise AttachRefused("runner_profile_unusable", "private owner root required")
    state = base / ".direct-development" / state_name
    if any(part.is_symlink() for part in (state.parent, state)):
        raise AttachRefused("runner_profile_unusable", "private direct root differs")
    if state.exists() and not state.is_dir():
        raise AttachRefused("runner_profile_unusable", "private direct root differs")
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    with _check("runner_profile_unusable"):
        network = binding(
            operator_config=paths.get("operator_config"),
            miner_network=paths.get("miner_network"),
        )
        public = json.loads(private_file(paths["miner_public"]).read_bytes())
        if (
            public["netuid"] != CARBON_NETUID
            or network.netuid != CARBON_NETUID
            or public["hotkey"] != cfg["principal"]
        ):
            raise AttachRefused(
                "registration_wrong_network", "installed miner identity differs"
            )
        signer = miner_signer(public, paths.get("signer_socket"))
    if "direct_intake_target" not in cfg:
        raise AttachRefused(
            "construction_intake_unconfigured", "pinned receiver required"
        )
    with _check("runner_profile_unusable"):
        target = validate([cfg["direct_intake_target"]])[0]
    with owner_lock(state):
        connection_args = {
            "root": state / "research-auth",
            "chain_context": network.context,
            "publisher": network.publisher_hotkey,
            "miner_key": signer,
        }
        connection = (
            DirectDevelopmentConnection(version="1.3", **connection_args)
            if synthetic
            else _RemoteBatteryConnection(challenge=challenge, **connection_args)
        )
        with _check("registration_check_failed"):
            await _requester(
                connection,
                challenge=connection.challenge,
                expected_hotkey=cfg["principal"],
            )
        yield connection, target


async def stage_installed_direct_bundle(
    configuration: Path, directory: Path, recipe_path: Path
) -> dict:
    """Keep one attached owner lock for a finite signed bundle upload.

    The CLI process, rather than a short browser request, owns the whole
    transfer. An interruption stops this synchronous upload; a rerun uses
    the receiver's acknowledged digest-bound offsets.
    """
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.development_session.direct_source_submission import stage_bundle
    from carbon.reconstruction.served_recipe_contract import registered

    if (
        not recipe_path.is_absolute()
        or ".." in recipe_path.parts
        or recipe_path.is_symlink()
        or not recipe_path.is_file()
        or recipe_path.resolve(strict=True) != recipe_path
        or not 0 < recipe_path.stat().st_size <= 128 * 1024
    ):
        raise ValueError("bounded regular recipe file required")
    recipe_bytes = recipe_path.read_bytes()
    if not 0 < len(recipe_bytes) <= 128 * 1024:
        raise ValueError("bounded regular recipe file required")
    if not directory.is_absolute() or ".." in directory.parts:
        raise AttachRefused(
            "construction_bundle_directory_invalid",
            "absolute bundle directory required",
        )
    recipe = ConstructionRecipe.from_dict(json.loads(recipe_bytes))
    source = recipe.to_dict()
    if source["source"]["kind"] != "bundle":
        raise AttachRefused(
            "construction_bundle_source_required", "bundle source required"
        )
    challenge = source["challenge"]
    contract = registered(challenge["id"], challenge["version"])
    if challenge != contract.construction_kit:
        raise AttachRefused(
            "construction_recipe_challenge_mismatch", "recipe kit differs"
        )
    from carbon.registry.model import ChallengeKey

    selected = ChallengeKey(challenge["id"], challenge["version"])
    async with attached_remote_material_stage(configuration, challenge=selected) as (
        connection,
        target,
    ):
        if selected != connection.challenge:
            raise AttachRefused(
                "construction_recipe_challenge_mismatch", "recipe challenge differs"
            )
        result = stage_bundle(
            target["intake_url"],
            connection.miner_key,
            directory=directory,
            recipe=recipe,
            contract_digest=contract.digest,
            receiver=target["receiver_hotkey"],
            context=connection.chain_context,
        )
        return {"ok": True, "result": result, "official_eligible": False}


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
        "--direct-development",
        action="store_true",
        help="Open the local synthetic direct construction research kit.",
    )
    parser.add_argument(
        "--direct-version",
        default="1.2",
        help=(
            "Installed direct kit version for serving (default 1.2; 1.3 is "
            "prospective). Bundle staging selects its Challenge from --recipe. "
            "Cleanup reconciles every retained kit version."
        ),
    )
    parser.add_argument(
        "--stage-bundle",
        type=Path,
        help="Transfer one exact local pinned bundle through the signed direct receiver.",
    )
    parser.add_argument(
        "--recipe",
        type=Path,
        help="Exact construction recipe JSON for --stage-bundle.",
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
    if args.cleanup_only and not (args.campaign or args.direct_development):
        parser.error("--cleanup-only needs --campaign or --direct-development")
    if args.direct_development and (args.configuration is None or args.campaign):
        parser.error("--direct-development needs a profile and no campaign")
    if not args.direct_development and args.direct_version != "1.2":
        parser.error("--direct-version needs --direct-development")
    if (args.stage_bundle is None) != (args.recipe is None):
        parser.error("--stage-bundle and --recipe must be supplied together")
    if args.stage_bundle is not None and (
        not args.direct_development or args.cleanup_only
    ):
        parser.error("bundle staging needs --direct-development")
    try:
        if (
            args.direct_development
            and args.stage_bundle is None
            and args.direct_version not in DIRECT_KIT_VERSIONS
        ):
            raise AttachRefused(
                "direct_development_kit_unavailable", "unknown direct kit"
            )
        if args.configuration is None:
            asyncio.run(
                serve_open_tier()
                if args.state_dir is None
                else serve_open_tier(state_dir=args.state_dir)
            )
        elif args.stage_bundle is not None:
            result = asyncio.run(
                stage_installed_direct_bundle(
                    args.configuration, args.stage_bundle, args.recipe
                )
            )
            print(json.dumps(result, sort_keys=True))
            return 0 if result.get("ok") is True else 2
        elif args.direct_development and args.cleanup_only:
            print(
                json.dumps(
                    asyncio.run(
                        cleanup_installed_direct_development(args.configuration)
                    )
                )
            )
        elif args.direct_development:
            asyncio.run(
                serve_installed_direct_development(
                    args.configuration, version=args.direct_version
                )
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
