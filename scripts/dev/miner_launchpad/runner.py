"""Loopback control adapter over Carbon's existing finite research runner.

Only the local operator - the miner, on their own machine - supplies
configuration and paths. Browser callers select an opaque profile. No
scientific loop, evaluator or consumption ledger lives here.

**Registration is the only admission gate (C-MLP-02-D11).** A launch reads the
chain for the miner's hotkey *before* anything durable is written, and admits
the campaign with the `RegisteredMiner` that read produced. There is no grant
anywhere on this path: the development grant is development machinery, and the
only form of it this module may hold is `RetainedGrant`, which proves ownership
of a campaign launched under one before the decision so it can still be cleaned
up, and structurally admits no new work.

A budget is the miner's to set, at launch, or not at all. Its absence blocks
nothing.

**One supervisor owns campaign threads (LP-PROD-C).** Which process runs a
campaign's work is this host's `role` (`supervisor.ROLES`): the Control
Center supervises while it runs; an MCP client only admits, queues and
observes, and a detached supervisor process carries its work out when no
Control Center is running. Closing any of them pauses or detaches, never
stops, a campaign.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from carbon.compute import retired
from carbon.development_session import research_guidance as guidance
from carbon.development_session.private_records import private_json
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_control import CampaignControl, DispatchStopped
from carbon.development_session.research_ledger import CampaignLedger
from scripts.dev.miner_launchpad import supervisor as supervision
from scripts.dev.miner_launchpad.controller import Rejected, owner_lock

PROFILE_SCHEMA = "carbon.launchpad.runner-profile.v2"
RETIRED_PROFILE_SCHEMA = "carbon.launchpad.runner-profile.v1"

PATH_FIELDS = {
    "image_manifest",
    "analysis_image_manifest",
    "api_key_file",
    "miner_public",
    "quarantine_journal",
}
#: Retired with external signing: Carbon no longer reads a password to decrypt
#: the miner's key. A profile naming it is refused with this code, so the
#: miner learns to start `carbon-miner-signer` instead of it being ignored.
#: `compute_credential` was the rented-GPU provider key file (C-MLP-03 slice
#: 4), retired by OWNER-MINER-COMPUTE-LINK-ONLY-01: Carbon rents no compute.
RETIRED_PATH_FIELDS = {
    "miner_password_file": "miner_password_file_retired_start_signer",
    "compute_credential": retired.RENTED_GPU_RETIRED,
}
#: Paths a profile may add. `battery_validator` is the legacy (C-MLP-03) name
#: of an operator's validator deployment for the one Challenge it was written
#: for; a profile now names deployments per Challenge in `validators`. Without
#: one, a submission is refused as evaluation_unavailable, never scored
#: another way.
#: `signer_socket` is where the miner's `carbon-miner-signer` listens, when
#: not at the path derived from their public hotkey.
#: `operator_config` (an operator's own deployment) or `miner_network` (the
#: chain context and publisher setup reads for a miner, C-MLP-04): exactly one
#: names the network a campaign talks to.
NETWORK_PATH_FIELDS = {"operator_config", "miner_network"}
OPTIONAL_PATH_FIELDS = {
    "battery_validator",
    "signer_socket",
} | NETWORK_PATH_FIELDS

PROFILE_FIELDS = {
    "schema",
    "profile_id",
    "principal",
    "enabled",
    "paths",
    "accepted_revision",
    "campaigns_root",
    "runtime",
}
OPTIONAL_PROFILE_FIELDS = {
    "research_guidance",
    "disabled_reason",
    "authored_julia_image",
    "gpu_image",
    "provider_credentials",
    "model_selection",
    # Per Challenge (C-MLP-04): {challenge_id: url}, the validator intake a
    # frozen candidate is submitted to when the validator does not run beside
    # the campaign; an https URL (an exposed intake terminates TLS,
    # OWNER-INTAKE-EXPOSURE-01), or loopback. And {challenge_id: absolute path}, an operator's own validator
    # deployment for that Challenge.
    "intakes",
    "validators",
    # Legacy names from C-MLP-03, still read exactly as before: the intake and
    # the validator deployment of the one Challenge they were written for.
    "battery_intake",
    # Where the miner's own remote machine or container is: the transport,
    # the SSH destination and an optional port (OWNER-MINER-COMPUTE-LINK-ONLY-01,
    # LINKONLY-D9). Required exactly when the runtime declares `remote_gpu`;
    # never frozen into a campaign, because its address can change.
    "remote_machine",
}
#: The Challenge each legacy per-Challenge field was written for.
LEGACY_INTAKE, LEGACY_VALIDATOR = "battery_intake", "battery_validator"

#: The provider every campaign was pinned to before selection existed. Its key
#: is the profile's `api_key_file`, unless `provider_credentials` names one.
DEFAULT_PROVIDER = "openai-responses"


def _legacy_challenge():
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    return BATTERY_CHALLENGE


def intakes(cfg):
    """{challenge_id: intake URL} from the profile, with a legacy
    `battery_intake` read as the intake of the Challenge it was written for."""
    found = dict(cfg.get("intakes") or {})
    if LEGACY_INTAKE in cfg:
        found.setdefault(_legacy_challenge(), cfg[LEGACY_INTAKE])
    return found


def validators(cfg):
    """{challenge_id: validator deployment path}, with a legacy
    `battery_validator` path read the same way."""
    found = {k: Path(v) for k, v in (cfg.get("validators") or {}).items()}
    if LEGACY_VALIDATOR in cfg["paths"]:
        found.setdefault(_legacy_challenge(), Path(cfg["paths"][LEGACY_VALIDATOR]))
    return found


def campaign_args(cfg, **fields):
    """A campaign's arguments from a profile: its paths, its per-Challenge
    intakes and validators, from which each campaign reads its own, and where
    the miner's remote setup is, when they practise on one."""
    return SimpleNamespace(
        **{k: Path(v) for k, v in cfg["paths"].items() if k != LEGACY_VALIDATOR},
        intakes=intakes(cfg),
        validators=validators(cfg),
        remote_machine=cfg.get("remote_machine"),
        **fields,
    )


def _registered_challenge_ids(values, field):
    from carbon.challenge_registry import ResolutionError
    from carbon.challenge_registry.campaigns import campaign_for_id

    if type(values) is not dict:
        raise ValueError(f"{field} maps Challenge ids to values")
    for challenge_id in values:
        try:
            campaign_for_id(challenge_id)
        except (ResolutionError, TypeError):
            raise ValueError(f"{field} names an unregistered Challenge") from None


def feedback_modes(challenge=None):
    """A Challenge's own feedback modes, read from its campaign; with no
    Challenge, every mode any implemented Challenge offers.

    Read from the campaign code that applies them, so a mode cannot exist in
    one place and not the other. Validated here, before dispatch. A campaign
    that declares none knows only FULL: fail closed, never run a mode it would
    silently ignore."""
    from carbon.challenge_registry.campaigns import (
        campaign_for,
        implemented_campaigns,
    )

    if challenge is not None:
        return tuple(campaign_for(challenge).feedback_modes)
    modes = ["FULL"]
    for _entry, campaign in implemented_campaigns():
        modes += [m for m in campaign.feedback_modes if m not in modes]
    return tuple(modes)


#: Image records a campaign's runtime can require, keyed by the profile field
#: that names the miner's built record. Under the grant each had to be written
#: by hand into one campaign's root; a product campaign's root is created at
#: launch, so the runner installs the record there from the miner's profile.
#: A record grants nothing by existing - the runtime still has to declare the
#: composition, and the campaign recomputes and checks the scope itself.
RESEARCH_IMAGE_RECORDS = {
    "authored_julia_image": ("authored_research", "authored-julia-image.json"),
    "gpu_image": ("gpu_research", "gpu-worker-image.json"),
}

# The runtime compositions this runner can actually assemble and dispatch.
#
# `implementation` and `images` are what every campaign runs on. The rest are
# optional research compositions the campaign runner knows how to build: an
# authored Julia analysis image, the scientific task selection, GPU research
# on the miner lane, and that GPU practice on the miner's own remote machine
# or container (`remote_gpu`, beside `gpu_research`). A key outside this set
# means the profile describes something this runner cannot assemble, which is
# refused before launch rather than discovered after the miner has started
# spending.
REQUIRED_RUNTIME_KEYS = frozenset({"implementation", "images"})
SUPPORTED_RUNTIME_KEYS = REQUIRED_RUNTIME_KEYS | {
    "authored_research",
    "scientific_tasks",
    "gpu_research",
    "remote_gpu",
}


def _intake_url(value):
    """An https URL, or http to this machine's loopback (the intake binds
    loopback until its exposure is recorded)."""
    from urllib.parse import urlsplit

    if type(value) is not str or len(value) > 512:
        return False
    try:
        url = urlsplit(value)
    except ValueError:
        return False
    if url.query or url.fragment or not url.hostname:
        return False
    return url.scheme == "https" or (
        url.scheme == "http" and url.hostname in ("127.0.0.1", "localhost")
    )


def review_pin(cfg):
    """Opaque v3 review: the profile the miner reviewed, nothing else."""
    return "review-v3:" + digest(canonical(cfg))


def chain_registration(cfg):
    """The admission read: is the configured hotkey registered, right now.

    The same read the onboarding `status` answers from, through the operator's
    configured chain context. Returns a `RegisteredMiner` or raises the closed
    onboarding failure that says why not.
    """
    from carbon.chain.sdk import BittensorReader
    from carbon.development_session.chain_onboarding import registered_miner
    from carbon.development_session.miner_network import binding

    config = binding(
        operator_config=cfg["paths"].get("operator_config"),
        miner_network=cfg["paths"].get("miner_network"),
    )
    public = json.loads(Path(cfg["paths"]["miner_public"]).read_bytes())
    return asyncio.run(
        registered_miner(BittensorReader(), config.context, public["hotkey"])
    )


def signer_ready(cfg):
    """Reach the miner's `carbon-miner-signer` for the configured hotkey.

    Carbon holds no key; every request a campaign sends is signed by the
    miner's own signer process. Asked before work is admitted so a miner who
    has not started it is told so at once, with `SignerFailure`'s closed code,
    rather than finding the campaign interrupted later.
    """
    from carbon.chain.external_signer import connect_signer

    public = json.loads(Path(cfg["paths"]["miner_public"]).read_bytes())
    socket_path = cfg["paths"].get("signer_socket")
    return connect_signer(
        public["hotkey"],
        socket_path=Path(socket_path) if socket_path is not None else None,
    )


def runner_database(cfg):
    """Where both doors record this profile's campaigns: beside them, so a
    campaign launched from a browser and one launched from a miner's own MCP
    client are one list, read and controlled the same way."""
    return Path(cfg["campaigns_root"]) / "launchpad-campaigns.sqlite3"


def product_agent(root):
    """Who selects in the campaign at `root`, from its frozen manifest."""
    manifest = Path(root) / "campaign-manifest.json"
    if not manifest.exists():
        return None
    return json.loads(manifest.read_bytes()).get("agent", "autonomous")


def retired_challenge(root):
    """Whether the campaign at `root` was frozen before Challenges were named:
    the Burgers campaign, retired from the research path."""
    manifest = Path(root) / "campaign-manifest.json"
    return manifest.exists() and "challenge" not in json.loads(manifest.read_bytes())


#: Carbon was updated after the installer wrote the runner profile (D9).
CARBON_UPDATED = "carbon_updated_rerun_installer"


def checkout_refusal(cfg, repository=None):
    """`carbon_updated_rerun_installer` when this checkout, or a worker image
    the profile names, is not what the profile accepted; otherwise None
    (LP-PROD-C D9).

    The common case it catches: Carbon was updated (a pull, a new release)
    after the installer wrote the profile, so every launch, resume and
    operation would fail inside the campaign on a source tree that is no
    longer the accepted one - before 2026-10-03, as INTERRUPTED with no
    reason. Cheap enough for every preflight: two `git` reads and two small
    image records, never the archive digest, which execution still checks
    (`research_campaign.accepted_implementation`). Judged only on what can be
    read: a revision this checkout has never seen, or an image record that
    cannot be loaded, is left to execution, which refuses it by its own
    check.
    """
    import subprocess

    repository = Path(repository or supervision.repository_root())

    def git(*argv):
        return subprocess.run(
            ["git", *argv],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    accepted = cfg.get("accepted_revision")
    if type(accepted) is str and re.fullmatch(r"[0-9a-f]{40}", accepted):
        try:
            head = git("rev-parse", "HEAD")
            known = git("cat-file", "-e", accepted + "^{commit}")
        except (OSError, subprocess.SubprocessError):
            head = known = None
        if (
            head is not None
            and head.returncode == 0
            and known.returncode == 0
            and head.stdout.strip() != accepted
        ):
            return CARBON_UPDATED
    runtime = cfg.get("runtime") if type(cfg.get("runtime")) is dict else {}
    images = runtime.get("images") if type(runtime.get("images")) is list else []
    paths = cfg.get("paths") if type(cfg.get("paths")) is dict else {}
    for position, field, load in (
        (0, "image_manifest", _worker_image),
        (1, "analysis_image_manifest", _analysis_image),
    ):
        image = _readable(load, paths.get(field))
        if image is None:
            continue  # Unreadable here: execution judges it.
        if images[position : position + 1] != [image.image_id]:
            return CARBON_UPDATED
        declared = (runtime.get("implementation") or {}).get("source_tree_digest")
        built = getattr(image, "source_tree_digest", None)
        if built is not None and declared is not None and declared != built:
            return CARBON_UPDATED
    return None


def _readable(load, path):
    """An image record loaded from `path`, or None when it cannot be."""
    try:
        return load(Path(path))
    except Exception:  # noqa: BLE001 - a record that cannot be read is not judged
        return None


def _worker_image(path):
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    return load_image_identity(path)


def _analysis_image(path):
    from carbon.development_session.research_image import load_analysis_image

    return load_analysis_image(path)


def binding_changes(cfg, row, manifest):
    """What a prepared campaign was frozen with that the runner profile no
    longer matches (LP-PROD-C D10): a list drawn from `principal`,
    `revision`, `images`, `hotkey` and `research_guidance`; empty when the
    profile can carry it on.

    Exactly what a resume's preparation would refuse: the frozen principal,
    implementation revision and images (`prepare` compares them with the
    host), the registered hotkey the campaign was admitted under (`prepare`
    compares it with the profile's public hotkey), and the research guidance
    frozen with it (the run compares it before anything starts). The hotkey
    is compared only when the profile's public record can be read here; one
    that cannot is left to preparation, which refuses it by its own check.
    Everything else in a profile may change under an existing campaign.
    """
    runtime = cfg.get("runtime") if type(cfg.get("runtime")) is dict else {}
    changed = []
    if manifest.get("principal") != cfg.get("principal"):
        changed.append("principal")
    if (manifest.get("implementation") or {}).get("revision") != cfg.get(
        "accepted_revision"
    ):
        changed.append("revision")
    if manifest.get("images") != runtime.get("images"):
        changed.append("images")
    frozen_hotkey = (manifest.get("admission") or {}).get("hotkey")
    try:
        public = json.loads(Path(cfg["paths"]["miner_public"]).read_bytes())
        hotkey = public["hotkey"]
    except Exception:  # noqa: BLE001 - unreadable: preparation judges it
        hotkey = None
    if hotkey is not None and frozen_hotkey is not None and hotkey != frozen_hotkey:
        changed.append("hotkey")
    stored = row.get("research_guidance")
    frozen_task = guidance.verify(json.loads(stored) if stored is not None else None)
    if frozen_task != guidance.configured(cfg):
        changed.append("research_guidance")
    return changed


def evaluation_refusal(cfg, manifest):
    """`evaluation_unavailable` when the campaign's Challenge is evaluated by
    a validator and the profile configures none for it - neither a deployment
    (`validators`) nor an intake (`intakes`, and their legacy names) - else
    None (LP-PROD-C D11).

    Asked before a submit is admitted, so the miner is told at once instead
    of reading "Submitted" and finding the refusal later. It mirrors what
    the Challenge's campaign reads when it submits
    (`carbon.battery.campaign.evaluation_config` and `_intake`, through
    `campaign_args`) rather than importing them: this runner names no
    Challenge's own module. Two tests hold the mirror to them: the same
    answer for every profile shape, and a recording test that fails as soon
    as the battery campaign reads an argument this mirror does not know. A
    Challenge whose campaign returns no validator feedback (`feedback_schema`
    None) needs no deployment here. A deployment that is configured but
    unusable is still refused by the campaign, by its own code."""
    from carbon.challenge_registry.campaigns import campaign_for_manifest

    challenge = (manifest.get("challenge") or {}).get("id")
    if campaign_for_manifest(manifest).feedback_schema is None:
        return None
    if validators(cfg).get(challenge) or intakes(cfg).get(challenge):
        return None
    return "evaluation_unavailable"


def validated_profile(cfg):
    """A runner profile v2, closed, or the reason it is not one.

    Shared by both front doors - this runner and the MCP registered tier - so
    the two cannot disagree about what a miner's profile is.
    """
    if cfg.get("schema") == RETIRED_PROFILE_SCHEMA:
        raise Rejected("runner_profile_v1_retired", 409)
    if set(cfg) - OPTIONAL_PROFILE_FIELDS != PROFILE_FIELDS or (
        cfg["schema"] != PROFILE_SCHEMA
    ):
        raise ValueError("closed operator configuration required")
    guidance.configured(cfg)  # Validate before registration or dispatch.
    if type(cfg["enabled"]) is not bool or (
        "disabled_reason" in cfg
        and (cfg["disabled_reason"] != "OWNER_EXPERIMENT_PAUSE" or cfg["enabled"])
    ):
        raise ValueError("invalid disabled profile explanation")
    if type(cfg["paths"]) is dict:
        for field, code in RETIRED_PATH_FIELDS.items():
            if field in cfg["paths"]:
                raise Rejected(code, 409)
    if retired.declares_rented(cfg["runtime"]):
        # A rented GPU is refused by name, never read as another runtime.
        raise Rejected(retired.RENTED_GPU_RETIRED, 409)
    if (
        type(cfg["paths"]) is not dict
        or set(cfg["paths"]) - OPTIONAL_PATH_FIELDS != PATH_FIELDS
    ):
        raise ValueError("closed runner inputs required")
    if len(NETWORK_PATH_FIELDS & set(cfg["paths"])) != 1:
        raise ValueError("exactly one of operator_config or miner_network required")
    if any(
        type(v) is not str or not Path(v).is_absolute()
        for v in [*cfg["paths"].values(), cfg["campaigns_root"]]
    ):
        raise ValueError("operator paths must be absolute")
    runtime = cfg["runtime"]
    if (
        type(runtime) is not dict
        or type(runtime.get("implementation")) is not dict
        or runtime["implementation"].get("revision") != cfg["accepted_revision"]
    ):
        raise ValueError("the runtime must name the accepted revision")
    for field, (composition, _name) in RESEARCH_IMAGE_RECORDS.items():
        # A declared composition needs its record, or it would fail after the
        # miner had launched. A Julia record needs no declaration: Julia is
        # available to every campaign whenever the host has it built. GPU
        # research still binds its scope to the campaign's own material, so a
        # GPU record still pairs with its declaration.
        if composition in runtime and field not in cfg:
            raise ValueError(
                f"{field} is required when the runtime declares {composition}"
            )
        if field == "gpu_image" and field in cfg and composition not in runtime:
            raise ValueError(
                f"{field} is required exactly when the runtime declares {composition}"
            )
        if field in cfg and (
            type(cfg[field]) is not str or not Path(cfg[field]).is_absolute()
        ):
            raise ValueError("operator paths must be absolute")
    _remote_machine(cfg, runtime)
    if LEGACY_INTAKE in cfg and not _intake_url(cfg[LEGACY_INTAKE]):
        raise ValueError("battery_intake is an https URL or a loopback URL")
    if "intakes" in cfg:
        _registered_challenge_ids(cfg["intakes"], "intakes")
        if not all(map(_intake_url, cfg["intakes"].values())):
            raise ValueError("an intake is an https URL or a loopback URL")
    if "validators" in cfg:
        _registered_challenge_ids(cfg["validators"], "validators")
        if any(
            type(v) is not str or not Path(v).is_absolute()
            for v in cfg["validators"].values()
        ):
            raise ValueError("operator paths must be absolute")
    if "provider_credentials" in cfg:
        from carbon.development_session.model_provider import ADAPTERS

        credentials = cfg["provider_credentials"]
        # Shape only: whether each file is usable is read at launch, so a key
        # file removed later refuses its provider rather than the profile.
        if (
            type(credentials) is not dict
            or not set(credentials) <= set(ADAPTERS)
            or any(
                type(v) is not str or len(v) > 4096 or not Path(v).is_absolute()
                for v in credentials.values()
            )
        ):
            raise ValueError("provider_credentials maps provider ids to key files")
    if "model_selection" in cfg:
        from carbon.development_session.model_provider import (
            ADAPTERS,
            ModelSelectionRefused,
        )

        # The miner's setup choice (C-MLP-03): what an autonomous launch that
        # names no provider runs with. It must name a launchable provider whose
        # key the profile configures, so the choice can never reach the pinned
        # default's key instead.
        chosen = cfg["model_selection"]
        if (
            type(chosen) is not dict
            or not {"provider_id", "model_id"} <= set(chosen)
            or not set(chosen) <= MODEL_SELECTION_FIELDS
            or chosen["provider_id"] not in ADAPTERS
            or chosen["provider_id"] not in (cfg.get("provider_credentials") or {})
            or type(chosen["model_id"]) is not str
            or not 1 <= len(chosen["model_id"]) <= 128
        ):
            raise ValueError("model_selection names a configured provider and model")
        # Everything else it carries (a generic adapter's endpoint, a declared
        # or published price) is validated exactly as a launch will use it.
        try:
            setup_selection(cfg)
        except ModelSelectionRefused:
            raise ValueError("model_selection does not validate") from None
    return cfg


def _remote_machine(cfg, runtime):
    """The profile's `remote_machine`: present exactly when the runtime
    declares remote GPU practice, and closed. The `endpoint` transport is not
    built and is refused by name (LINKONLY-D7)."""
    if ("remote_gpu" in runtime) != ("remote_machine" in cfg):
        raise ValueError(
            "remote_machine is required exactly when the runtime declares remote_gpu"
        )
    if "remote_machine" not in cfg:
        return
    from carbon.compute.remote_machine import RemoteMachineError
    from carbon.compute.remote_transport import RemoteMachine

    try:
        RemoteMachine.from_document(cfg["remote_machine"])
    except RemoteMachineError as refused:
        raise Rejected(refused.code, 409) from None


#: What a profile's `model_selection` (written by setup) may carry.
MODEL_SELECTION_FIELDS = frozenset(
    {"provider_id", "model_id", "endpoint", "declared_pricing", "published_pricing"}
)


def setup_selection(cfg, *, settings=None):
    """The profile's setup choice as a validated selection, with its key file.

    Raises `ModelSelectionRefused` when it does not validate.
    """
    from carbon.development_session.model_provider import select

    chosen = cfg["model_selection"]
    path = provider_credential(cfg, chosen["provider_id"])
    return select(
        credential={"kind": "file", "reference": path or "unset"},
        settings=settings,
        **chosen,
    )


def provider_credential(cfg, provider_id):
    """The key file the runner profile configures for `provider_id`, or None.

    The request never supplies it. The pinned default provider's key is the
    profile's `api_key_file` when no entry names another; no other provider
    ever falls back to that key.
    """
    credentials = cfg.get("provider_credentials") or {}
    path = credentials.get(provider_id)
    if path is None and provider_id == DEFAULT_PROVIDER:
        path = (cfg.get("paths") or {}).get("api_key_file")
        if path in credentials.values():
            # A key file named for another provider is that provider's key.
            return None
    return path


def foreign_default_key(cfg):
    """Whether `api_key_file` is another provider's key, so the pinned default
    must not be sent it."""
    return (cfg.get("paths") or {}).get("api_key_file") in (
        cfg.get("provider_credentials") or {}
    ).values() and provider_credential(cfg, DEFAULT_PROVIDER) is None


def credential_refusal(path):
    """Why a configured key file cannot be used, or None when it can.

    Read from metadata only - `model_provider`'s own check (a regular file,
    not a symlink, bounded) and the campaign's owner-only rule. The key itself
    is never read here.
    """
    from carbon.development_session.model_provider import provider_summary
    from carbon.development_session.research_campaign import private_file

    if path is None:
        return "model_provider_credential_not_configured"
    row = provider_summary({DEFAULT_PROVIDER: path})[0]
    if not row["available"]:
        return (
            "model_provider_credential_not_configured"
            if row["reason"] == "credential_not_configured"
            else "model_provider_credential_unusable"
        )
    try:
        private_file(Path(path))
    except (OSError, ValueError):
        return "model_provider_credential_unusable"
    return None


def frozen_provider(root):
    """The provider a frozen campaign's manifest records, or None before one
    exists. A block without a selection schema is the pinned default."""
    manifest = Path(root) / "campaign-manifest.json"
    if not manifest.exists():
        return None
    block = json.loads(manifest.read_bytes()).get("provider") or {}
    # A battery run plan nests the selection; a Burgers manifest is it.
    record = block.get("model_selection", block)
    if type(record) is dict and "schema" in record:
        return record.get("provider_id")
    return DEFAULT_PROVIDER


@dataclass(frozen=True)
class LaunchChoice:
    """What a launch chose beyond the product admission: the validated model
    selection (built only by `model_provider.select`, with the profile's key
    file for that provider) and the Challenge's feedback mode. Applied when the
    campaign is first created, never on resume: the manifest is frozen then."""

    selection: object = None
    feedback_mode: str | None = None
    #: The launch's settings overrides, exactly as `select` accepted them.
    #: None keeps the pinned defaults and the historical args shape.
    settings: dict | None = None

    def apply(self, args):
        if self.selection is not None:
            from carbon.development_session.model_provider import selection_spec

            # The whole validated choice travels: a generic adapter's endpoint
            # and a declared or published price, not only the provider and model.
            args.model_selection = selection_spec(
                self.selection, settings=self.settings
            )
            args.api_key_file = Path(self.selection.credential.reference)
        if self.feedback_mode is not None:
            args.feedback_mode = self.feedback_mode


def install_research_images(cfg, root):
    """Put the host's current image records where the campaign looks for them.

    Every launch, resume and attach installs the current records, so a rebuilt
    image - new packages, a newer Julia environment - reaches running campaigns
    too. Swapping is safe because nothing trusts the record's history: each run
    records in its own execution contract exactly which image it used.
    """
    import os

    for field, (_composition, name) in RESEARCH_IMAGE_RECORDS.items():
        if field not in cfg:
            continue
        source = Path(cfg[field])
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 65536:
            raise ValueError(f"{field} must be a bounded image record file")
        data = source.read_bytes()
        target = root / name
        if target.is_symlink():
            raise ValueError("an image record must not be a symlink")
        if target.exists() and target.read_bytes() == data:
            continue
        staged = root / (name + ".installing")
        staged.unlink(missing_ok=True)
        handle = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(handle, "wb") as record:
            record.write(data)
        os.replace(staged, target)


def _valid_key(key):
    """An idempotency key: 16-80 ASCII letters, digits, - or _."""
    if (
        type(key) is not str
        or not 16 <= len(key) <= 80
        or not all(c.isascii() and (c.isalnum() or c in "-_") for c in key)
    ):
        raise Rejected("invalid_idempotency_key")
    return key


def _operation_digest(operation, request):
    """What a keyed operation's request asked for. The key is how it is named,
    not part of it; a strategy counts by value, whether a door sent it as an
    object or as JSON text, so the browser and MCP retry the same request."""
    fields = {k: v for k, v in request.items() if k != "idempotency_key"}
    if type(fields.get("strategy")) is str:
        try:
            fields["strategy"] = json.loads(fields["strategy"])
        except ValueError:
            pass
    return digest(canonical([operation, fields]))


#: A typed failure's closed code (its `code`, or that code's `value`), or
#: None; never the message. One definition, shared with the doors' answers.
exception_code = supervision.exception_code


def record_interruption(root, stage, exc):
    """Keep why a campaign was interrupted, privately, for its owner.

    The page still shows only INTERRUPTED. This appends one line to the
    campaign's owner-only interruptions.jsonl: the exception's type and, for
    a typed failure, its code. Never its message or traceback, which could
    carry a provider response or a path. Recording never masks the
    interruption itself.
    """
    entry = {
        "at_unix": round(time.time(), 3),
        "stage": stage,
        "error_type": type(exc).__module__ + "." + type(exc).__qualname__,
        "code": exception_code(exc),
    }
    try:
        path = Path(root) / "interruptions.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError:
        pass


class RunnerAdapter:
    #: How a client starts a detached supervisor; a test replaces it.
    spawn = staticmethod(supervision.spawn_detached)
    #: Whether this checkout is still the one the profile accepted (D9); a
    #: test replaces it.
    checkout_refusal = staticmethod(checkout_refusal)
    #: How long a campaign thread keeps trying for its campaign's lock before
    #: answering `campaign_busy`: long enough to outlast a door's instant
    #: probe (`_probe_lock`), short enough that a real holder is reported.
    LOCK_WAIT_SECONDS = 1.0

    def __init__(
        self,
        database,
        *,
        configuration=None,
        principal=None,
        registration=None,
        signer=None,
        role=supervision.INLINE,
    ):
        if role not in supervision.ROLES:
            raise ValueError("unknown runner role")
        if role != supervision.INLINE and configuration is None and not principal:
            # The supervisor lock and the queue are per principal.
            raise ValueError("a supervised runner needs its principal")
        self.database = database
        self.configuration = configuration
        self.principal = (
            private_json(configuration)["principal"]
            if configuration is not None
            else principal
        )
        # Injectable so a test reads a device-free stub chain; the default is
        # the real read against the operator's configured context.
        self.registration = registration or chain_registration
        # The early signer answer, beside the real registration read. A test
        # that stubs the chain stubs this too; the signing itself still needs
        # a real `ExternalSigner`, which nothing here can construct.
        self.signer = signer or (signer_ready if registration is None else None)
        self.threads = {}
        #: What each campaign thread here carries out: "run" or an operation.
        self.thread_operations = {}
        #: SUPERVISOR: campaigns it admitted work for while another process
        #: held the supervisor lock, so closing it pauses or withdraws that
        #: work as it would its own (D4).
        self.delegated = set()
        self.lock = threading.RLock()
        #: Who runs this host's campaign threads (LP-PROD-C). INLINE: this
        #: process, as before supervision existed (fixtures and tests).
        #: SUPERVISOR/DETACHED: this process, while it holds the supervisor
        #: lock. CLIENT: never this process.
        self.role = role
        #: Names this process's claims in the dispatch queue.
        self.token = "sup-" + secrets.token_hex(8)
        #: When this client last started a detached supervisor.
        self._spawned_at = float("-inf")
        self.supervisor = (
            supervision.Supervisor(self)
            if role in (supervision.SUPERVISOR, supervision.DETACHED)
            else None
        )
        # The page's research tool sessions, each holding its campaign's
        # ownership lock while open (RSURF-D15, D16).
        from scripts.dev.miner_launchpad.tool_door import ToolSessions, runner_opener

        self.tool_sessions = ToolSessions(
            runner_opener(self), busy_hint=self.tools_busy_hint
        )
        with self.db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS launchpad_campaigns (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, request_digest TEXT NOT NULL, profile TEXT NOT NULL, principal TEXT NOT NULL, config_digest TEXT NOT NULL, campaign TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, root TEXT NOT NULL, admission BLOB NOT NULL, budget BLOB NOT NULL, research_guidance BLOB)"
            )
            # Campaigns launched under the retired development grant. Kept so
            # their evidence stays readable and their work can be cleaned up;
            # nothing new is ever written here.
            db.execute(
                "CREATE TABLE IF NOT EXISTS research_runs (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, profile TEXT NOT NULL, principal TEXT NOT NULL, config_digest TEXT NOT NULL, grant_digest TEXT NOT NULL, campaign TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, root TEXT NOT NULL, grant_record BLOB NOT NULL, grant_id TEXT UNIQUE NOT NULL)"
            )
            # One row per accepted keyed miner operation (practice, freeze,
            # submit): what a retry under the same key replays. Written in the
            # same critical section that dispatches the operation, so a key is
            # recorded exactly when its work was started, and kept in this
            # database so a restarted controller replays rather than redoes.
            db.execute(
                "CREATE TABLE IF NOT EXISTS launchpad_operation_keys (principal TEXT NOT NULL, request_key TEXT NOT NULL, operation TEXT NOT NULL, campaign TEXT NOT NULL, request_digest TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(principal, request_key))"
            )
            if "research_guidance" not in {
                r[1] for r in db.execute("PRAGMA table_info(research_runs)")
            }:
                db.execute(
                    "ALTER TABLE research_runs ADD COLUMN research_guidance BLOB"
                )
            # The dispatch queue, what a launch chose, and the last refusal
            # (LP-PROD-C); added in place to an older database.
            supervision.ensure_schema(db)
        if role == supervision.INLINE:
            # A supervised host recovers when it takes the supervisor lock,
            # the only moment every earlier holder is known to be gone; a
            # client never recovers. INLINE keeps recovering at construction.
            self.recover()

    def recover(self, *, redispatch=False):
        """Settle what a process that died left behind, truthfully.

        For each of this principal's campaigns whose ownership lock is free:
        a settled campaign (READY, PAUSED, INTERRUPTED, COMPLETED, STOPPED or
        RECONCILIATION_REQUIRED) is left exactly as it is. One whose ledger
        still says some process was working (`supervisor.IN_FLIGHT`) is
        settled with the real cleanup check: reconciliation only when work
        may be outstanding or cleanup is not verified, otherwise what was
        asked of it (READY or INTERRUPTED; PAUSED or STOPPED when that was
        requested). Before 2026-10-03 every start settled every campaign not
        COMPLETED, STOPPED or PAUSED with cleanup assumed failed, which
        flagged idle READY campaigns RECONCILIATION_REQUIRED.

        With `redispatch` (a supervisor that has just taken the lock): queue
        items a dead supervisor had claimed are marked interrupted - never
        replayed - and a launch that was admitted but never prepared (QUEUED,
        no frozen manifest, nothing refused before) is queued again as a new
        item, once, to be carried out with its own recorded choices
        (`_redispatch_stranded`).
        """
        orphans, waiting = {}, set()
        with self.db() as db:
            if redispatch:
                for item in supervision.orphaned(
                    db, principal=self.principal, supervisor=self.token
                ):
                    orphans.setdefault(item["campaign"], item["operation"])
                waiting = {
                    r[0]
                    for r in db.execute(
                        "SELECT campaign FROM launchpad_dispatch WHERE principal=? AND state=?",
                        (self.principal, supervision.QUEUED),
                    )
                }
            rows = [
                (dict(r), table)
                for table in ("launchpad_campaigns", "research_runs")
                for r in db.execute(
                    f"SELECT * FROM {table} WHERE principal=?", (self.principal,)
                )
            ]
        for row, table in rows:
            kind = "product" if table == "launchpad_campaigns" else "retired_grant"
            orphan = orphans.get(row["id"])
            # One campaign that cannot be recovered never blocks the rest; it
            # stays as it is for its miner or the next supervisor.
            with contextlib.suppress(Exception):
                settled = self._recover_one(row, kind, orphan, row["id"] in waiting)
                if redispatch and kind == "product" and settled:
                    # `row` is as it was before this recovery, on purpose: a
                    # refusal in it was kept by an earlier attempt; the one
                    # recovery just recorded is this interruption's own.
                    self._redispatch_stranded(row, orphan)

    def _recover_one(self, row, kind, orphan, waiting=False):
        """Settle one campaign if a dead process left it in flight. True when
        no live process holds it (so it may be redispatched).

        `waiting`: work is queued for it. With nothing outstanding that work
        settles it when it runs, so it is not settled (and told it was
        interrupted) first."""
        root = Path(row["root"])
        if not (root / "campaign.sqlite3").exists():
            return True
        try:
            with owner_lock(root):
                ledger = self._ledger(row, kind, root)
                control = CampaignControl(ledger)
                status = control.status()
                state, settled_now = status["state"], False
                if state in supervision.IN_FLIGHT:
                    if waiting and orphan is None and not self._outstanding(ledger):
                        return True
                    try:
                        generation = control.acquire()
                    except DispatchStopped:
                        return True
                    ledger.generation = generation
                    completed = (root / "campaign-complete.json").exists()
                    state = control.settled(
                        generation,
                        completed=completed,
                        ready=not completed
                        and status["desired"] == "RUN"
                        and product_agent(root) == "none",
                        cleanup_verified=self._cleanup(ledger),
                    )
                    settled_now = True
        except RuntimeError:
            return False  # Another live owner still holds the exact campaign lock.
        self._recovered(row, orphan, state, settled_now)
        return True

    def _recovered(self, row, orphan, state, settled_now):
        """What recovery tells the miner, as `last_refusal`.

        A campaign settled before this recovery is left as it is, except an
        operation a dead process left waiting at a pause: it never ran, so it
        is `operation_interrupted` (send it again). A campaign settled now is
        told why: its interrupted run or operation, or the reconciliation it
        needs - except a run settled PAUSED that already says why it was
        paused (its supervisor closed, a handover), which keeps that reason.
        """
        identity = row["id"]
        if not settled_now:
            if orphan not in (None, "run") and state == "PAUSED":
                self._refused(
                    identity, "operation_interrupted", orphan, kind="interrupted"
                )
            return
        if orphan is not None:
            kept = supervision.read_refusal(row.get("last_refusal"))
            if (
                orphan == "run"
                and state == "PAUSED"
                and kept is not None
                and kept["kind"] == "paused"
            ):
                return
            self._refused(
                identity,
                "campaign_interrupted" if orphan == "run" else "operation_interrupted",
                orphan,
                kind="interrupted",
            )
        elif state == "RECONCILIATION_REQUIRED":
            self._refused(identity, "reconciliation_required", None, kind="interrupted")
        elif state == "INTERRUPTED":
            self._refused(identity, "campaign_interrupted", None, kind="interrupted")

    @staticmethod
    def _outstanding(ledger):
        """Whether any operation may still be out: RESERVED or HELD."""
        with ledger.db() as db:
            return (
                db.execute(
                    "SELECT 1 FROM operations WHERE state IN ('RESERVED','HELD') LIMIT 1"
                ).fetchone()
                is not None
            )

    def _settle_stale(self, identity):
        """After queued work was refused: a campaign its dead holder left in
        flight, and nobody holds now, is settled truthfully rather than left
        reading as busy."""
        with contextlib.suppress(Exception):
            row, kind, root = self._bound(identity)
            if not (root / "campaign.sqlite3").exists():
                return
            ledger = self._ledger(row, kind, root)
            control = CampaignControl(ledger)
            if control.status()["state"] in supervision.IN_FLIGHT:
                self._settle_if_idle(ledger, control, root)

    def _redispatch_stranded(self, row, orphan=None):
        """Queue again a launch admitted and never prepared (D5): QUEUED, its
        choices recorded, no frozen manifest, not paused, stopped or awaiting
        reconciliation, nothing queued for it, and nothing refused it before
        this recovery (`row` is read before it).

        This is the live failure's own case - the process carrying a launch
        died before preparing it - and nothing can have been dispatched for
        it: there is no manifest, and recovery found nothing outstanding (it
        would be awaiting reconciliation otherwise). A new item carries it
        out; the queue item that died is never replayed. Once only: a run
        interrupted again after that may be one preparation itself ends, so
        it keeps its `campaign_interrupted` and waits for its miner's Resume.
        Re-queued, the interruption recovery just recorded is history, so the
        campaign does not read as interrupted while it is carried out.
        """
        root = Path(row["root"])
        if (
            row["state"] != "QUEUED"
            or row.get("last_refusal") is not None
            or row.get("launch_request") is None
            or (root / "campaign-manifest.json").exists()
        ):
            return
        if orphan == "run":
            with self.db() as db:
                again = supervision.interrupted_runs(
                    db, principal=self.principal, campaign=row["id"]
                )
            if again > 1:
                return
        if (root / "campaign.sqlite3").exists():
            status = CampaignControl(CampaignLedger(root)).status()
            if status["desired"] != "RUN" or status["state"] in {
                "RECONCILIATION_REQUIRED",
                *supervision.TERMINAL,
            }:
                return
        with self.db() as db:
            if supervision.active(db, principal=self.principal, campaign=row["id"]):
                return
            supervision.enqueue(
                db,
                principal=self.principal,
                campaign=row["id"],
                operation="run",
                params={},
                config_digest=row["config_digest"],
                state=supervision.QUEUED,
            )
            db.execute(
                "UPDATE launchpad_campaigns SET last_refusal=NULL WHERE id=?",
                (row["id"],),
            )

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _configuration(self):
        if self.configuration is None:
            raise ValueError("operator configuration absent")
        cfg = validated_profile(private_json(self.configuration))
        if cfg["principal"] != self.principal:
            raise ValueError("operator principal mismatch")
        return cfg

    def configured(self):
        cfg = self._configuration()
        if not cfg["enabled"]:
            raise Rejected("research_dispatch_disabled", 409)
        runtime = cfg["runtime"]
        if not set(runtime) <= SUPPORTED_RUNTIME_KEYS:
            # Closed rather than permissive: a runtime naming a composition this
            # runner cannot actually assemble is refused here instead of being
            # carried to a campaign that would fail after the miner had started.
            raise Rejected("research_runtime_interface_unavailable", 409)
        if not REQUIRED_RUNTIME_KEYS <= set(runtime):
            raise Rejected("research_runtime_interface_unavailable", 409)
        if "gpu_research" in runtime:
            from carbon.challenge_registry.campaigns import declared_gpu

            # Shape, here: the GPU practice scope of the Challenge it names,
            # checked by that Challenge's campaign (C-MLP-04). The campaign
            # recomputes the scope from the installed GPU image record; this
            # only refuses a runtime the runner could never assemble.
            try:
                declared_gpu(runtime)
            except (ValueError, KeyError, TypeError, LookupError):
                raise Rejected("research_runtime_interface_unavailable", 409) from None
        if "remote_gpu" in runtime:
            from carbon.challenge_registry.campaigns import declared_remote

            # Shape, here: remote practice beside the GPU scope, for a
            # Challenge whose campaign offers it. The campaign recomputes the
            # scope from its GPU worker and checks the profile's machine.
            try:
                declared_remote(runtime)
            except (ValueError, KeyError, TypeError, LookupError):
                raise Rejected("research_runtime_interface_unavailable", 409) from None
        return cfg

    def preflight(self):
        from scripts.dev.miner_launchpad.prelaunch import review

        try:
            cfg = self.configured()
            stale = self.checkout_refusal(cfg)
            if stale is not None:
                # Caught here, before a launch, rather than as an interrupted
                # campaign (D9).
                return {
                    "available": False,
                    "profile": cfg["profile_id"],
                    "status": "CARBON_UPDATED",
                    "code": stale,
                    "reason": supervision.NEXT_ACTIONS[stale],
                    "research_guidance": guidance.configured(cfg),
                    "runtime_revision": cfg["accepted_revision"],
                    "review": review(cfg),
                }
            value = {
                "available": True,
                "profile": cfg["profile_id"],
                "mode": "LIVE_PRACTICE_RESEARCH",
                # The miner chooses the Challenge at launch, from the catalog
                # (C-MLP-04); a profile binds none.
                "challenge": "CHOSEN_AT_LAUNCH_FROM_THE_CATALOG",
                "agent": "carbon-autoresearch",
                # The miner's own setup choice, or the pinned default for a
                # profile written before setup chose one.
                "reasoning": (
                    "{provider_id}:{model_id}".format(**cfg["model_selection"])
                    if "model_selection" in cfg
                    else DEFAULT_PROVIDER
                ),
                "compute": (
                    "remote-gpu:" + cfg["remote_machine"]["transport"]
                    if "remote_gpu" in cfg["runtime"]
                    else (
                        "local-isolated-gpu"
                        if "gpu_research" in cfg["runtime"]
                        else "local-isolated-cpu"
                    )
                ),
                # Registration is read at launch, before anything is recorded.
                # A budget is the miner's to set at launch or not at all.
                "admission": "SUBNET_REGISTRATION_CHECKED_AT_LAUNCH",
                "budget": "SET_BY_MINER_AT_LAUNCH_OR_NONE",
                "status": "PROFILE_CONFIGURED_REGISTRATION_CHECK_AT_LAUNCH",
                "review_digest": review_pin(cfg),
            }
            task = guidance.configured(cfg)
            if task is not None:
                value.update(
                    research_guidance=task,
                    runtime_revision=cfg["accepted_revision"],
                )
            value["review"] = review(cfg)
            return value
        except Rejected as refused:
            if refused.code == "runner_profile_v1_retired":
                return {
                    "available": False,
                    "profile": None,
                    "status": "PROFILE_V1_RETIRED",
                    "reason": "This profile names a development grant. Launching needs only subnet registration now: replace grant_file and account_ref with campaigns_root and the runtime your campaign runs on (runner-profile v2).",
                }
            if refused.code == retired.RENTED_GPU_RETIRED:
                return {
                    "available": False,
                    "profile": None,
                    "status": "RENTED_GPU_RETIRED",
                    "reason": "This profile names a GPU rented with your provider key. Set up compute again in Set up your environment. "
                    + retired.NEXT_STEP,
                }
            return self._unavailable()
        except Exception:  # noqa: BLE001 - private configuration errors stay private.
            return self._unavailable()

    def _unavailable(self):
        try:
            cfg = self._configuration()
            paused = cfg.get("disabled_reason") == "OWNER_EXPERIMENT_PAUSE"
            return {
                "available": False,
                "profile": cfg["profile_id"],
                "status": ("OWNER_EXPERIMENT_PAUSE" if paused else "DISPATCH_DISABLED"),
                "reason": (
                    "Owner experiment pause is active. New owner authorization is required before research can resume. Status, export, stop and reconciliation remain available."
                    if paused
                    else "Research dispatch is disabled in this profile, or its runtime is one this runner cannot assemble."
                ),
                "research_guidance": guidance.configured(cfg),
                "runtime_revision": cfg["accepted_revision"],
                "review": self._review(cfg),
            }
        except Exception:  # noqa: BLE001 - no private paths or errors disclosed.
            return {
                "available": False,
                "profile": None,
                "status": "DISPATCH_DISABLED",
                "reason": "A runner profile with your registered miner and the exact accepted runtime and images is required.",
            }

    @staticmethod
    def _review(cfg):
        from scripts.dev.miner_launchpad.prelaunch import review

        return review(cfg)

    def launch(self, value, key):
        """The browser's launch: a caller of the shared `launch` operation."""
        from scripts.dev.miner_launchpad.operations import perform

        if type(value) is not dict or "profile" not in value:
            raise Rejected("closed_research_launch_required")
        request = {"agent": "autonomous", **value, "idempotency_key": key}
        return perform(self, "launch", request)

    # -- The campaign host: what the operations table's gates and bodies ask of
    # -- whichever door is calling. Both doors construct this same class.

    @classmethod
    def for_profile(
        cls,
        configuration,
        *,
        legacy_database=None,
        registration=None,
        role=supervision.CLIENT,
    ):
        """The campaign host both doors construct for one runner profile.

        Its records live beside the profile's campaigns. `legacy_database` is a
        browser database from before the doors shared one: its campaign rows
        are copied across once, so nothing launched earlier is lost.

        `role` is who runs its campaign threads (LP-PROD-C). A door is a
        CLIENT unless it says otherwise: it admits and queues, and wakes a
        supervisor when work is waiting. The Control Center passes SUPERVISOR
        and supervises from a daemon thread until closed; the detached
        supervisor process passes DETACHED and runs its own loop.
        """
        cfg = validated_profile(private_json(Path(configuration)))
        database = runner_database(cfg)
        database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        host = cls(
            database, configuration=configuration, registration=registration, role=role
        )
        if legacy_database is not None and Path(legacy_database).exists():
            host._adopt(Path(legacy_database))
        database.chmod(0o600)
        if role == supervision.SUPERVISOR:
            host.supervisor.start()
        elif role == supervision.CLIENT:
            with contextlib.suppress(Exception):
                host.wake_if_stranded()
        return host

    # -- Supervision (LP-PROD-C): who runs a campaign's threads, and how a
    # -- door that does not run them hands work over.

    def _delegating(self):
        """Whether work admitted here is queued for another process: always
        for a client; for a supervisor, until it holds the lock."""
        if self.role == supervision.CLIENT:
            return True
        return self.supervisor is not None and not self.supervisor.held

    def _lock_directory(self):
        return supervision.lock_directory(self.database, self.principal)

    def _supervisor_running(self):
        if self.supervisor is not None and self.supervisor.held:
            return True
        return supervision.supervisor_alive(self._lock_directory())

    def _wake(self):
        """Make sure someone carries out queued work: this process's own
        loop, or else a detached supervisor started for this profile. A
        client starts at most one per `supervisor.ACQUIRE_SECONDS`, however
        often it is asked, so polling never fans out processes (one that
        loses the lock race exits by itself).

        Never raises: it is called after work was recorded, and that work is
        admitted whether or not a process could be started now (the host out
        of processes, say). It waits in the queue, and the next observe or
        client start wakes a supervisor for it."""
        try:
            if self.supervisor is not None:
                self.supervisor.wake()
                return
            if self.role != supervision.CLIENT or self._supervisor_running():
                return
            now = time.monotonic()
            if now - self._spawned_at < supervision.ACQUIRE_SECONDS:
                return
            self._spawned_at = now
            self.spawn(self.configuration)
        except Exception:  # noqa: BLE001 - admitted work is never answered as failed
            return

    def wake_if_stranded(self):
        """At a client's start: wake a supervisor when work is waiting or a
        campaign was left mid-flight by a process that died, so recovery
        does not wait for the next request."""
        with self.db() as db:
            waiting = supervision.queued(db, principal=self.principal)
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM launchpad_campaigns WHERE principal=? AND state NOT IN ('COMPLETED','STOPPED')",
                    (self.principal,),
                )
            ]
        if waiting or any(self._stranded(row) for row in rows):
            self._wake()

    @staticmethod
    def _stranded(row):
        """Whether a supervisor has something to do for this campaign: its
        ledger says a process was working (recovery settles it), or it is a
        launch recovery would carry out - the same checks
        `_redispatch_stranded` applies, so a paused, stopped or
        reconciliation-bound launch wakes nothing. A campaign held live (an
        attached agent) also reads as in flight; telling the two apart would
        mean probing its lock on every client start, which could refuse that
        agent's own attach, so it costs one detached supervisor that finds
        nothing to do and exits."""
        root = Path(row["root"])
        if (root / "campaign.sqlite3").exists():
            status = CampaignControl(CampaignLedger(root)).status()
            if status["state"] in supervision.IN_FLIGHT:
                return True
            if status["desired"] != "RUN" or status["state"] in {
                "RECONCILIATION_REQUIRED",
                *supervision.TERMINAL,
            }:
                return False
        return (
            row["state"] == "QUEUED"
            and row.get("last_refusal") is None
            and row.get("launch_request") is not None
            and not (root / "campaign-manifest.json").exists()
        )

    def live_threads(self):
        return [i for i, t in tuple(self.threads.items()) if t.is_alive()]

    def busy_threads(self):
        """Live campaign threads here that are still working: every live one
        except a thread parked at its campaign's checkpoint while the
        campaign is paused - settled PAUSED, nothing reserved or held.

        A parked thread holds nothing a process must keep: a parked run is
        carried on by a new run when the campaign is resumed, anywhere; a
        parked operation never dispatched, and recovery reports it
        (`operation_interrupted`) so it is sent again. So a supervisor may
        exit, or hand over, with parked threads alive."""
        return [i for i in self.live_threads() if not self._parked(i)]

    def _parked(self, identity):
        try:
            row, kind, root = self._bound(identity)
            if not (root / "campaign.sqlite3").exists():
                return False
            ledger = self._ledger(row, kind, root)
            status = CampaignControl(ledger).status()
            return (status["desired"], status["state"]) == (
                "PAUSE",
                "PAUSED",
            ) and not self._outstanding(ledger)
        except Exception:  # noqa: BLE001 - unreadable: treated as working
            return False

    # -- The handover (LP-PROD-C, review repair): a Control Center that starts
    # -- while a detached supervisor holds the lock becomes the supervisor.

    def hand_over(self):
        """DETACHED, while a Control Center is running: pause Carbon's agent
        in each campaign this process runs (`paused_for_handover`), so the
        Control Center can carry it on, and let everything else here finish -
        a launch still being prepared, a miner's practice, freeze or submit.
        True once nothing here is working, so the lock can be released.

        An agent's run pauses at its next checkpoint, between bounded
        operations: a paid model call or a training run under way finishes
        first, and nothing is cut off mid-flight."""
        for identity in self.live_threads():
            if self.thread_operations.get(identity) == "run":
                with contextlib.suppress(Exception):
                    self._pause_for_handover(identity)
        return not self.busy_threads()

    def _pause_for_handover(self, identity):
        row, kind, root = self._bound(identity)
        if product_agent(root) in (None, "none"):
            # Still being prepared, or nobody's agent runs in it: it ends on
            # its own.
            return
        control = CampaignControl(self._ledger(row, kind, root))
        status = control.status()
        if status["desired"] != "RUN" or status["state"] in supervision.TERMINAL:
            return
        control.request("pause")
        self._refused(identity, supervision.HANDED_OVER, None, kind="paused")

    def _handed_over(self):
        """The campaigns whose last refusal is the handover's pause."""
        with self.db() as db:
            rows = db.execute(
                "SELECT id,last_refusal FROM launchpad_campaigns WHERE principal=? AND last_refusal IS NOT NULL",
                (self.principal,),
            ).fetchall()
        return [
            r["id"]
            for r in rows
            if (supervision.read_refusal(r["last_refusal"]) or {}).get("code")
            == supervision.HANDED_OVER
        ]

    def take_over(self):
        """SUPERVISOR, on each pass while it holds the lock: carry on each
        campaign a detached supervisor paused so this Control Center could
        take it over, exactly as a Resume would - so opening the Control
        Center never leaves a running campaign paused. One that changed since
        (stopped, resumed, awaiting reconciliation) is left to that; one whose
        resume is refused (its profile changed, say) stays paused with that
        code.

        Only once the campaign's own lock is free. The agent's run parked in
        the detached process holds it until that process has exited, and a
        resume asked before then would wake that run in a process about to
        end - cutting off whatever it started next. Until then it is left for
        a later pass."""
        self.delegated.clear()
        for identity in self._handed_over():
            with contextlib.suppress(Exception):
                row, kind, root = self._bound(identity)
                status = CampaignControl(self._ledger(row, kind, root)).status()
                if (status["desired"], status["state"]) != ("PAUSE", "PAUSED"):
                    continue
                try:
                    with owner_lock(root):
                        pass
                except RuntimeError:
                    continue  # Its parked run's process has not exited yet.
                try:
                    self._control(identity, "resume")
                except Rejected as refused:
                    self._refused(identity, refused.code, "run")

    def release_handover_pauses(self):
        """No Control Center will take them over (it closed first): each
        campaign paused for a handover stays paused, and says so as closing
        the Control Center would (`paused_when_supervisor_closed`, D4)."""
        for identity in self._handed_over():
            self._refused(
                identity, "paused_when_supervisor_closed", None, kind="paused"
            )

    def _withdraw_or_pause(self, identity):
        """A Control Center closing before it took over: the work it admitted
        for `identity` that no supervisor started is withdrawn, and work
        already started elsewhere is asked to pause - as closing pauses what
        a supervising Control Center runs (D4). A withdrawn launch or resume
        leaves its campaign paused; a withdrawn practice, freeze or submit
        never ran and is sent again."""
        with self.db() as db:
            item = supervision.active(db, principal=self.principal, campaign=identity)
            withdrawn = (
                item is not None
                and item["state"] == supervision.QUEUED
                and supervision.withdraw(db, item["seq"])
            )
        if item is None:
            return
        if not withdrawn:
            self._pause_for_close(identity)
            return
        if item["operation"] != "run":
            self._refused(
                identity, "withdrawn_when_supervisor_closed", item["operation"]
            )
            return
        row, kind, root = self._bound(identity)
        if (root / "campaign.sqlite3").exists():
            ledger = self._ledger(row, kind, root)
            control = CampaignControl(ledger)
            status = control.status()
            if status["desired"] == "RUN" and status["state"] not in (
                supervision.TERMINAL
            ):
                control.request("pause")
                self._settle_if_idle(ledger, control, root)
        self._refused(identity, "paused_when_supervisor_closed", "run", kind="paused")

    def _record(self, identity, operation, params, cfg, state):
        with self.db() as db:
            return {
                "seq": supervision.enqueue(
                    db,
                    principal=self.principal,
                    campaign=identity,
                    operation=operation,
                    params=params,
                    config_digest=digest(canonical(cfg)),
                    state=state,
                    supervisor=self.token if state == supervision.RUNNING else None,
                ),
                "campaign": identity,
                "operation": operation,
            }

    def _finish(self, item, outcome):
        with contextlib.suppress(Exception), self.db() as db:
            supervision.finish(db, item["seq"], outcome)

    def _tracked(self, item, function, *args):
        """Run one dispatch's thread, then mark its queue item done."""
        try:
            function(*args)
        finally:
            self._finish(item, "finished")

    def _refused(self, identity, code, operation, kind="refused"):
        """Keep `code` as the campaign's last refusal (`supervisor.refusal`)."""
        entry = supervision.refusal(code, operation=operation, kind=kind)
        with contextlib.suppress(Exception), self.db() as db:
            db.execute(
                "UPDATE launchpad_campaigns SET last_refusal=? WHERE id=?",
                (canonical(entry), identity),
            )

    def _accepted(self, identity):
        """A new attempt was admitted: the earlier refusal is history."""
        with self.db() as db:
            db.execute(
                "UPDATE launchpad_campaigns SET last_refusal=NULL WHERE id=?",
                (identity,),
            )

    def start_item(self, item):
        """Start one queued item a client admitted, in this supervisor.

        The profile is read again here, and an item admitted under another
        one is refused, not run under this one. A refusal is kept as the
        campaign's `last_refusal`; nothing is retried.
        """
        identity, operation = item["campaign"], item["operation"]
        try:
            row, kind, root = self._bound(identity)
            if kind != "product":
                raise Rejected("retired_grant_campaign", 409)
            try:
                cfg = self.configured()
            except Rejected:
                raise
            except Exception:  # noqa: BLE001 - an unreadable profile, never its content
                raise Rejected("research_profile_unavailable", 409) from None
            if digest(canonical(cfg)) != item["config_digest"]:
                raise Rejected("profile_differs_from_request", 409)
            if operation == "run":
                self._start(identity, cfg, root, None, None, item)
                return
            work = self._work(operation, json.loads(item["params"]))
            admitted = SimpleNamespace(
                campaign={**dict(row), "kind": kind}, profile=cfg
            )
            with self.lock:
                previous = self.threads.get(identity)
                if previous is not None and previous.is_alive():
                    raise Rejected("campaign_busy", 409)
                thread = threading.Thread(
                    target=self._tracked,
                    args=(item, self._operation_thread, admitted, work),
                    daemon=True,
                )
                self.threads[identity] = thread
                self.thread_operations[identity] = operation
                thread.start()
        except Rejected as refused:
            self._refused(identity, refused.code, operation)
            self._finish(item, "refused")
            self._settle_stale(identity)
        except Exception:  # noqa: BLE001 - never a trace or a path
            self._refused(identity, "operation_refused", operation)
            self._finish(item, "refused")
            self._settle_stale(identity)

    def _adopt(self, legacy):
        with self.db() as db:
            db.execute("ATTACH DATABASE ? AS legacy", (str(legacy),))
            try:
                tables = {
                    r[0]
                    for r in db.execute(
                        "SELECT name FROM legacy.sqlite_master WHERE type='table'"
                    )
                }
                for table in ("launchpad_campaigns", "research_runs"):
                    if table in tables:
                        columns = ",".join(
                            r[1]
                            for r in db.execute(f"PRAGMA legacy.table_info({table})")
                        )
                        db.execute(
                            f"INSERT OR IGNORE INTO main.{table} ({columns}) "
                            f"SELECT {columns} FROM legacy.{table}"
                        )
            finally:
                db.commit()
                db.execute("DETACH DATABASE legacy")

    def replayed(self, cfg, request, operation="launch"):
        """The read-only replay gate: validates the request's key, and returns
        what a lost response already started, reading no chain; or None."""
        if operation != "launch":
            return self._operation_replayed(cfg, request, operation)
        from carbon.development_session.product_campaign import AGENTS, miner_budget

        key = _valid_key(request["idempotency_key"])
        if request["agent"] not in AGENTS:
            raise Rejected("invalid_agent")
        try:
            miner_budget(request.get("budget"))
        except ValueError:
            raise Rejected("invalid_budget") from None
        if cfg["principal"] != self.principal:
            raise Rejected("research_profile_mismatch", 409)
        task = guidance.configured(cfg)
        if (task is not None or "review_digest" in request) and request.get(
            "review_digest"
        ) != review_pin(cfg):
            raise Rejected("research_review_changed", 409)
        run_id, digest_value, config_pin = self._launch_identity(cfg, request)
        with self.db() as db:
            previous = db.execute(
                "SELECT * FROM launchpad_campaigns WHERE request_key=? OR id=?",
                (key, run_id),
            ).fetchall()
        if not previous:
            # Refused here, before the registration read, as well as in the
            # body: a choice that cannot run never reaches the chain.
            self._current(cfg)
            self._launch_choice(cfg, request, self._challenge(request, cfg["runtime"]))
            return None
        # A lost response replays the campaign it created. It was admitted
        # when it was recorded; replaying it reads no chain and starts
        # nothing new.
        if len(previous) != 1 or any(
            previous[0][k] != v
            for k, v in {
                "id": run_id,
                "request_digest": digest_value,
                "principal": cfg["principal"],
                "config_digest": config_pin,
            }.items()
        ):
            raise Rejected("research_launch_replay_conflict", 409)
        return self.get(run_id)

    def _operation_replayed(self, cfg, request, operation):
        """A keyed practice, freeze or submit already accepted under this key:
        the campaign it was started on, as it stands now. The same key with a
        different request is a conflict, never a second dispatch."""
        if "idempotency_key" not in request:
            return None
        key = _valid_key(request["idempotency_key"])
        if cfg["principal"] != self.principal:
            raise Rejected("research_profile_mismatch", 409)
        with self.db() as db:
            recorded = self._recorded_operation(db, key, operation, request)
        return None if recorded is None else self.get(recorded)

    def _recorded_operation(self, db, key, operation, request):
        """The campaign a matching earlier acceptance of `key` started work
        on, or None when the key is unused. Raises the conflict otherwise."""
        row = db.execute(
            "SELECT operation,campaign,request_digest FROM launchpad_operation_keys WHERE principal=? AND request_key=?",
            (self.principal, key),
        ).fetchone()
        if row is None:
            return None
        if (row["operation"], row["campaign"], row["request_digest"]) != (
            operation,
            request.get("campaign"),
            _operation_digest(operation, request),
        ):
            raise Rejected("operation_replay_conflict", 409)
        return row["campaign"]

    def _current(self, cfg):
        """Refuse new work, by name, on a checkout or worker image the profile
        did not accept (D9): `carbon_updated_rerun_installer`."""
        stale = self.checkout_refusal(cfg)
        if stale is not None:
            raise Rejected(stale, 409)

    def _launch_identity(self, cfg, request):
        # The browser's request digest is of the launch fields it historically
        # sent, so a replay of a launch recorded before operations existed still
        # matches. The agent choice joins it only when it is not the default.
        fields = {
            k: v for k, v in request.items() if k not in {"idempotency_key", "agent"}
        }
        if request["agent"] != "autonomous":
            fields["agent"] = request["agent"]
        run_id = digest(canonical([cfg["principal"], request["idempotency_key"]]))[7:39]
        return run_id, digest(canonical(fields)), digest(canonical(cfg))

    @staticmethod
    def _challenge(request, runtime=None):
        """The launch's Challenge, resolved exactly for the profile's compute
        (`gpu_research` when the runtime declares GPU practice). There is no
        default: a launch naming none, or an unknown, reserved, deferred,
        retired or wrong-version Challenge, or one without that compute, is
        refused by its code; nothing falls back to another Challenge."""
        if "challenge" not in request and "challenge_version" not in request:
            raise Rejected("challenge_required", 409)
        from carbon.challenge_registry import ResolutionError, resolve

        challenge = {
            "id": request.get("challenge"),
            "version": request.get("challenge_version"),
        }
        try:
            resolve(
                challenge["id"],
                challenge["version"],
                "gpu_research" if "gpu_research" in (runtime or {}) else "cpu_research",
            )
        except ResolutionError as refused:
            raise Rejected(refused.code, 409) from None
        from carbon.challenge_registry.campaigns import runtime_challenge

        bound = runtime_challenge(runtime)
        if bound is not None and bound != challenge["id"]:
            # GPU practice was set up for one Challenge; it never runs another.
            raise Rejected("gpu_scope_is_for_another_challenge", 409)
        return challenge

    @staticmethod
    def _launch_choice(cfg, request, challenge):
        """The launch's model and feedback choice, refused by name before
        anything is created. None when the launch chose neither, which is
        exactly today's pinned default."""
        from carbon.development_session.model_provider import (
            ADAPTERS,
            ModelSelectionRefused,
            check_budget,
            select,
        )
        from carbon.development_session.product_campaign import miner_budget

        mode = request.get("feedback_mode")
        if mode is not None:
            if type(mode) is not str or mode not in feedback_modes():
                raise Rejected("invalid_feedback_mode")
            if challenge is None or mode not in feedback_modes(challenge):
                # Each Challenge offers its own modes; FULL is every one's.
                raise Rejected("feedback_mode_not_offered_by_challenge", 409)
        provider, model = request.get("model_provider"), request.get("model")
        settings = request.get("model_settings")
        from_setup = False
        if (
            provider is None
            and model is None
            and settings is None
            and request.get("agent") == "autonomous"
            and "model_selection" in cfg
        ):
            # The miner chose a model in setup; a launch that names none runs
            # with it, never with the pinned default and another's key.
            provider = cfg["model_selection"]["provider_id"]
            model = cfg["model_selection"]["model_id"]
            from_setup = True
        if settings is not None:
            # Settings modify a selection; without a provider nothing uses them.
            if provider is None:
                raise Rejected("model_provider_required")
            if type(settings) is not dict:
                raise Rejected("model_selection_refused")
        selection = None
        if provider is not None or model is not None:
            if provider is None:
                raise Rejected("model_provider_required")
            if type(provider) is not str or provider not in ADAPTERS:
                raise Rejected("unknown_model_provider")
            if model is not None and type(model) is not str:
                raise Rejected("model_selection_refused")
            if request["agent"] != "autonomous":
                # No agent calls a model; a choice nothing uses is refused.
                raise Rejected("model_selection_needs_the_autonomous_agent", 409)
            chosen = cfg.get("model_selection") or {}
            same_as_setup = from_setup or (
                chosen.get("provider_id") == provider
                and chosen.get("model_id") == model
            )
            if ADAPTERS[provider].endpoint is None and not same_as_setup:
                # A generic adapter's endpoint is configured in setup, never
                # in a launch request.
                raise Rejected("model_provider_endpoint_not_configured", 409)
            path = provider_credential(cfg, provider)
            refusal = credential_refusal(path)
            if refusal is not None:
                raise Rejected(refusal, 409)
            try:
                selection = (
                    setup_selection(cfg, settings=settings)
                    if same_as_setup
                    else select(
                        provider_id=provider,
                        model_id=model,
                        credential={"kind": "file", "reference": path},
                        settings=settings,
                    )
                )
                budget = miner_budget(request.get("budget"))
                check_budget(selection, budget.get("ceilings"))
            except ModelSelectionRefused:
                raise Rejected("model_selection_refused", 409) from None
        if selection is None and mode is None:
            return None
        return LaunchChoice(
            selection=selection,
            feedback_mode=mode,
            settings=None if settings is None else dict(settings),
        )

    def launch_admitted(self, admitted, request):
        """Record and dispatch an admitted launch."""
        from carbon.development_session.product_campaign import (
            ProductLaunch,
            miner_budget,
        )

        cfg, miner = admitted.profile, admitted.miner
        task = guidance.configured(cfg)
        budget = miner_budget(request.get("budget"))
        challenge = self._challenge(request, cfg["runtime"])
        choice = self._launch_choice(cfg, request, challenge)
        run_id, request_digest, config_pin = self._launch_identity(cfg, request)
        root = Path(cfg["campaigns_root"]) / run_id
        product = ProductLaunch(
            campaign_id="cmp-" + run_id,
            principal=cfg["principal"],
            miner=miner,
            runtime=cfg["runtime"],
            budget=budget,
            agent=request["agent"],
            challenge=challenge,
        )
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO launchpad_campaigns (id,request_key,request_digest,profile,principal,config_digest,campaign,state,created,root,admission,budget,research_guidance,launch_request) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        request["idempotency_key"],
                        request_digest,
                        cfg["profile_id"],
                        cfg["principal"],
                        config_pin,
                        product.campaign_id,
                        "QUEUED",
                        time.time(),
                        str(root),
                        canonical(miner.record()),
                        canonical(budget),
                        canonical(task) if task is not None else None,
                        # What this launch chose, exactly as admitted, so a
                        # supervisor elsewhere or after a restart carries it
                        # out with these choices and no others (LP-PROD-C).
                        canonical(
                            {k: v for k, v in request.items() if k != "idempotency_key"}
                        ),
                    ),
                )
            except sqlite3.IntegrityError:
                raise Rejected("research_launch_replay_conflict", 409) from None
        self._dispatch_run(run_id, cfg, root, product, choice)
        return self.get(run_id)

    def _dispatch_run(self, run_id, cfg, root, product=None, choice=None):
        """Carry out a launch or resume: on a thread here when this process
        supervises, otherwise queued for the supervisor, which rebuilds the
        launch from its record (`_recorded_launch`)."""
        self._accepted(run_id)
        if not self._delegating():
            self._start(run_id, cfg, root, product, choice)
            return
        with self.db() as db:
            supervision.enqueue(
                db,
                principal=self.principal,
                campaign=run_id,
                operation="run",
                params={},
                config_digest=digest(canonical(cfg)),
                state=supervision.QUEUED,
            )
        if self.role == supervision.SUPERVISOR:
            self.delegated.add(run_id)
        self._wake()

    def _recorded_launch(self, row, cfg):
        """A launch's admission and choices, rebuilt from its record for a run
        that starts where the launch was not received: a supervisor in another
        process, or a restart before the campaign was prepared.

        The recorded request must still produce the recorded identity under
        today's profile; its choices are validated again exactly as at launch;
        and registration is read again, because the `RegisteredMiner` that
        admitted the launch lived in the process that received it and can only
        be built by a read. Raises `Rejected` with the reason otherwise.
        """
        from carbon.development_session.product_campaign import (
            ProductLaunch,
            miner_budget,
        )
        from scripts.dev.miner_launchpad.operations import (
            _registered,
            _signer_reachable,
        )

        stored = row.get("launch_request")
        if stored is None:
            raise Rejected("launch_choices_unrecorded", 409)
        try:
            request = {**json.loads(stored), "idempotency_key": row["request_key"]}
            run_id, request_digest, config_pin = self._launch_identity(cfg, request)
        except (ValueError, TypeError, KeyError):
            raise Rejected("launch_record_differs", 409) from None
        if (run_id, request_digest) != (row["id"], row["request_digest"]):
            raise Rejected("launch_record_differs", 409)
        if config_pin != row["config_digest"]:
            # Never prepared: the launch binds the whole profile its miner
            # reviewed, so a changed one cannot carry it out (D10).
            raise Rejected("profile_changed_since_launch", 409)
        challenge = self._challenge(request, cfg["runtime"])
        choice = self._launch_choice(cfg, request, challenge)
        miner = _registered(self, cfg)
        _signer_reachable(self, cfg)
        product = ProductLaunch(
            campaign_id=row["campaign"],
            principal=cfg["principal"],
            miner=miner,
            runtime=cfg["runtime"],
            budget=miner_budget(request.get("budget")),
            agent=request["agent"],
            challenge=challenge,
        )
        return product, choice

    def owner(self):
        """Whose campaigns this host serves, for operations that read or
        withdraw: no enabled or runnable profile is required for those."""
        if type(self.principal) is not str or not self.principal:
            raise Rejected("research_profile_unavailable", 409)
        return {"principal": self.principal}

    def owned_campaign(self, identity):
        """The campaign gate: a campaign this principal owns, and its kind."""
        if type(identity) is not str:
            raise Rejected("research_run_unavailable", 404)
        row, kind, _ = self._bound(identity)
        return {**dict(row), "kind": kind}

    def options_admitted(self, admitted, request):
        """What a miner can choose at launch, and whether it can run now.

        The vocabulary is check-design's (supported, not_yet_rebuildable,
        needs_owner_decision, excluded) for what Carbon can rebuild, and
        configured / unavailable-with-reason for what this host has. Built
        from the capability registry and the profile, never from a static list,
        so no option is offered that cannot run.
        """
        from carbon.development_session.design_check import availability
        from carbon.development_session.product_campaign import BUDGET_KEYS
        from carbon.development_session.research_ledger import DIMENSIONS
        from carbon.reconstruction.capability_registry import (
            CONTRACTS,
            REGISTRY,
            Dimension,
        )

        # The gate established whose profile this is; its content is read here.
        cfg = self.configured()
        paths = cfg.get("paths", {})
        runtime = cfg.get("runtime", {})
        key = paths.get("api_key_file")
        agent_ready = type(key) is str and Path(key).is_file()

        def host(present, reason):
            return (
                {"availability": "configured"}
                if present
                else {
                    "availability": "unavailable",
                    "reason": reason,
                }
            )

        return {
            "schema": "carbon.launchpad.launch-options.v1",
            "agents": [
                {"value": "none", "availability": "available"},
                {
                    "value": "autonomous",
                    **(
                        {"availability": "available"}
                        if agent_ready
                        else {
                            "availability": "unavailable",
                            "reason": "model_provider_key_not_configured",
                        }
                    ),
                },
            ],
            "model_providers": self._model_providers(cfg),
            "families": [
                {
                    "id": c.capability_id,
                    "selector": c.selector,
                    "summary": c.summary,
                    **availability(c),
                }
                for c in REGISTRY
                if c.dimension is Dimension.MODEL_FAMILY
            ],
            # Each Challenge's own families, from its own construction contract
            # (OD-8): a battery launch lists battery's, never Burgers'.
            "families_by_challenge": {
                token: [
                    {
                        "id": c.capability_id,
                        "selector": c.selector,
                        "summary": c.summary,
                        **availability(c),
                    }
                    for c in item.capabilities
                    if c.dimension is Dimension.MODEL_FAMILY
                ]
                for token, item in CONTRACTS.items()
            },
            "research_lanes": {
                "julia": host(
                    "authored_research" in runtime or "authored_julia_image" in cfg,
                    "no_julia_image_installed_for_this_profile",
                ),
                "gpu": host("gpu_research" in runtime, "no_gpu_runtime_declared"),
                # GPU practice on the miner's own remote machine or container.
                "remote_gpu": host("remote_gpu" in runtime, "no_remote_machine_set_up"),
            },
            # The miner's own budget: every part optional, no bound to be
            # outside of. Read from the ledger's own vocabulary, so a launch
            # form built from it offers exactly what a launch accepts.
            "budget": {
                "availability": "available",
                "keys": sorted(BUDGET_KEYS),
                "ceilings": list(DIMENSIONS),
                "bounds": "none: a ceiling is any whole number >= 0, elapsed_seconds any whole number >= 1; blank is no cap",
            },
            "vocabulary": {
                "supported": "Carbon rebuilds it in DEVELOPMENT; not official qualification",
                "not_yet_rebuildable": "explore it in research; engineering has not registered it",
                "needs_owner_decision": "research-only until the owner decides; see its trigger",
                "excluded": "outside the declarative rule",
                "configured": "this host has it",
                "unavailable": "this host does not, for the reason given",
            },
        }

    @staticmethod
    def _model_providers(cfg):
        """Each provider a launch may name, and whether this profile has its
        key file - judged from metadata only; no key is read and no provider
        contacted. Only an available one can launch."""
        from carbon.development_session.model_provider import ADAPTERS

        rows = []
        configured = (cfg.get("model_selection") or {}).get("provider_id")
        for provider_id, adapter in ADAPTERS.items():
            if adapter.endpoint is None and provider_id != configured:
                # Launchable once setup configures its endpoint.
                reason = "model_provider_endpoint_not_configured"
            else:
                reason = credential_refusal(provider_credential(cfg, provider_id))
            rows.append(
                {
                    "provider_id": provider_id,
                    "display_name": adapter.display_name,
                    "models": [m["model_id"] for m in adapter.summary_models()],
                    "default_model": adapter.default_model,
                    "any_model_id": adapter.allowed_models is None,
                    **(
                        {"availability": "available"}
                        if reason is None
                        else {"availability": "unavailable", "reason": reason}
                    ),
                }
            )
        return rows

    def _design_refusal(self, strategy):
        """Check-design's verdict for a recipe about to be practiced or frozen:
        refused now, by name, rather than failing at submission."""
        from carbon.development_session.design_check import check_design

        try:
            verdict = check_design({"strategy": strategy})
        except ValueError:
            raise Rejected("design_malformed") from None
        if verdict["verdict"] != "submittable":
            raise Rejected("design_" + verdict["verdict"], 409)

    def observe_admitted(self, admitted, request):
        return self.get(admitted.campaign["id"])

    def campaign_view_admitted(self, admitted, request):
        # The research surface's one document (RSURF-D1).
        from scripts.dev.miner_launchpad.campaign_view import ledger_view

        return ledger_view(self, admitted, request)

    def note_admitted(self, admitted, request):
        # A journal entry through the existing journal path (RSURF-D5).
        from scripts.dev.miner_launchpad.campaign_view import post_note

        return post_note(self, admitted, request)

    def messages_admitted(self, admitted, request):
        # The miner's messages to their own agent (RSURF-D12).
        from scripts.dev.miner_launchpad.campaign_view import ledger_messages

        return ledger_messages(self, admitted, request)

    def toolbox_admitted(self, admitted, request):
        # Everything the miner and their agent can use (RSURF-D11).
        from scripts.dev.miner_launchpad.toolbox import for_request

        return for_request(self, request)

    def run_output_admitted(self, admitted, request):
        # A finished workspace run's own output (RSURF-D17).
        from scripts.dev.miner_launchpad.campaign_view import _journal
        from scripts.dev.miner_launchpad.run_output import check_task, for_campaign

        task = check_task(request["task"])
        ledger, owner, _ = _journal(admitted)
        return for_campaign(ledger.root, owner, task)

    def tools_busy_hint(self, identity):
        """Who can hold a campaign's lock, as far as this host knows: its own
        agent or operation thread, the supervisor's when that is another
        process (LP-PROD-C), or another session (RSURF-D16). A paused agent's
        run still holds the campaign while it waits at its checkpoint, here
        or in the supervisor, so "pause it" is not the advice then (D12)."""
        thread = self.threads.get(identity)
        if thread is None or not thread.is_alive():
            try:
                elsewhere = self._in_flight(identity) is not None
            except Exception:  # noqa: BLE001 - unknown: no claim about who
                elsewhere = False
            if not elsewhere:
                return "another_session"
        with contextlib.suppress(Exception):
            row, kind, root = self._bound(identity)
            control = CampaignControl(self._ledger(row, kind, root))
            if control.status()["desired"] == "PAUSE":
                return "carbon_agent_paused"
        return "carbon_agent_or_operation"

    def miner_message(self, identity, value):
        """The page's own route for the miner's message (RSURF-D12)."""
        from scripts.dev.miner_launchpad.campaign_view import miner_message

        return miner_message(self, identity, value)

    def halt_admitted(self, admitted, request):
        if request["action"] not in {"stop", "pause", "reconcile"}:
            raise Rejected("invalid_research_control")
        return self._control(admitted.campaign["id"], request["action"])

    def resume_admitted(self, admitted, request):
        return self._control(admitted.campaign["id"], "resume")

    def practice_admitted(self, admitted, request):
        """One practice trial of a registered recipe, run in the background:
        real training takes minutes, and observe shows the result."""
        import uuid

        from scripts.dev.miner_launchpad.operations import strategy_value

        strategy = strategy_value(request)
        self._design_refusal(strategy)
        hypothesis = request["hypothesis"]
        expected = request.get("expected_effect", hypothesis)
        for text in (hypothesis, expected):
            if type(text) is not str or not 1 <= len(text) <= 2048:
                raise Rejected("bounded_hypothesis_required")
        params = {
            "strategy": strategy,
            "hypothesis": hypothesis,
            "expected_effect": expected,
            "identity": "miner-practice-" + uuid.uuid4().hex[:16],
        }
        return self._background(admitted, "practice", params, "PRACTICING", request)

    def freeze_candidate_admitted(self, admitted, request):
        """Freeze a practiced recipe. Its refusals - agent-selected campaign,
        no practice result, a candidate awaiting submission, final exams used -
        are read from the campaign's own records before anything starts, so a
        person gets the named reason at once; the freeze itself then runs in
        the background, because preparing the campaign can take a while."""
        from carbon.development_session.research_campaign import freeze_refusal
        from scripts.dev.miner_launchpad.operations import strategy_value

        strategy = strategy_value(request)
        used = request.get("used_feedback", False)
        if type(used) is not bool:
            raise Rejected("used_feedback_boolean_required")
        reason = request["reason"]
        if type(reason) is not str or not 1 <= len(reason) <= 4096:
            raise Rejected("bounded_reason_required")
        self._design_refusal(strategy)
        refusal = freeze_refusal(Path(admitted.campaign["root"]), strategy)
        if refusal is not None:
            raise Rejected(refusal, 409)
        params = {"strategy": strategy, "reason": reason, "used_feedback": used}
        return self._background(
            admitted, "freeze_candidate", params, "FREEZING", request
        )

    def submit_admitted(self, admitted, request):
        # Checked before the thread starts, so a submit that cannot be
        # evaluated - nothing frozen, both final exams used, Carbon's agent
        # selects, no validator configured for the Challenge - is refused to
        # the caller rather than answered SUBMITTING and refused where no one
        # sees it (LP-PROD-C D11; observed live: the page said "Submitted").
        self._admissible(admitted)
        self._require_frozen(admitted)
        self._require_evaluation(admitted)
        return self._background(admitted, "submit", {}, "SUBMITTING", request)

    @staticmethod
    def _require_evaluation(admitted):
        """`evaluation_unavailable` now, when the profile configures no
        validator deployment or intake for the campaign's Challenge
        (`evaluation_refusal`)."""
        root = Path(admitted.campaign["root"])
        manifest = json.loads((root / "campaign-manifest.json").read_bytes())
        if "challenge" not in manifest:
            raise Rejected("challenge_retired", 409)
        try:
            refusal = evaluation_refusal(admitted.profile, manifest)
        except Exception as exc:  # noqa: BLE001 - its closed code, never its text
            raise Rejected(
                exception_code(exc) or "evaluation_unavailable", 409
            ) from None
        if refusal is not None:
            raise Rejected(refusal, 409)

    @staticmethod
    def _work(operation, params):
        """The body of one miner operation, from what was admitted. The same
        `research_campaign` functions whether it runs here or in a supervisor
        that read it from the queue."""
        from carbon.development_session import research_campaign

        if operation not in ("practice", "freeze_candidate", "submit"):
            raise ValueError("unknown miner operation")

        async def work(prepared):
            if operation == "practice":
                return await research_campaign.practice_recipe(prepared, **params)
            if operation == "freeze_candidate":
                return await research_campaign.freeze_candidate(prepared, **params)
            return await research_campaign.submit_frozen(prepared)

        work.operation = operation
        return work

    @staticmethod
    def _admissible(admitted):
        """Refuse at once an operation the campaign's own state cannot take:
        not yet prepared, finished, stopped, paused (resume first), or waiting
        for reconciliation. Without this a paused campaign's operation would
        wait on the pause, and a stopped one's would fail where no one sees."""
        root = Path(admitted.campaign["root"])
        if not (root / "campaign-manifest.json").exists():
            raise Rejected("campaign_not_prepared", 409)
        if not (root / "campaign.sqlite3").exists():
            return
        status = CampaignControl(CampaignLedger(root)).status()
        if status["state"] == "COMPLETED":
            raise Rejected("campaign_complete", 409)
        if status["state"] == "STOPPED" or status["desired"] == "STOP":
            raise Rejected("campaign_stopped", 409)
        if status["desired"] == "PAUSE":
            raise Rejected("campaign_paused", 409)
        if status["state"] == "RECONCILIATION_REQUIRED":
            raise Rejected("reconciliation_required", 409)

    def _busy_elsewhere(self, identity):
        """Whether a supervisor already holds work for this campaign: queued,
        or running under a supervisor that is still alive."""
        with self.db() as db:
            item = supervision.active(db, principal=self.principal, campaign=identity)
        if item is None:
            return False
        return item["state"] == supervision.QUEUED or self._supervisor_running()

    def _background(self, admitted, operation, params, state, request):
        """Run a long miner operation on its own thread; observe reports it.

        A keyed request is claimed in the same critical section that starts
        the thread: a concurrent or later retry under the key finds the claim
        and replays, and a refused request (busy) records nothing. A host
        that does not supervise queues the operation instead, for the
        supervisor to start (LP-PROD-C).
        """
        identity = admitted.campaign["id"]
        key = request.get("idempotency_key")
        delegating = self._delegating()
        with self.lock:
            if key is not None:
                with self.db() as db:
                    if self._recorded_operation(db, key, operation, request):
                        return self.get(identity)
            self._admissible(admitted)
            self._current(admitted.profile)
            previous = self.threads.get(identity)
            if delegating:
                if self._busy_elsewhere(identity):
                    raise Rejected("campaign_busy", 409)
            elif previous is not None and previous.is_alive():
                # A finished operation settles the campaign READY and then its
                # thread exits: give it a moment to, so a client that saw
                # READY is not told busy. A running one still answers busy.
                previous.join(timeout=2)
                if previous.is_alive():
                    raise Rejected("campaign_busy", 409)
            # Held by an attached agent, the page's tools or Carbon's agent:
            # refused now, rather than answered PRACTICING and refused on the
            # thread (D11).
            self._probe_lock(Path(admitted.campaign["root"]))
            if key is not None:
                with self.db() as db:
                    try:
                        db.execute(
                            "INSERT INTO launchpad_operation_keys (principal,request_key,operation,campaign,request_digest,created) VALUES(?,?,?,?,?,?)",
                            (
                                self.principal,
                                key,
                                operation,
                                identity,
                                _operation_digest(operation, request),
                                time.time(),
                            ),
                        )
                    except sqlite3.IntegrityError:
                        # Another controller process claimed it first.
                        if self._recorded_operation(db, key, operation, request):
                            return self.get(identity)
                        raise
            self._accepted(identity)
            if delegating:
                # Queued for the supervisor, under the profile this request
                # was admitted with; it starts nothing admitted under another.
                self._record(
                    identity, operation, params, admitted.profile, supervision.QUEUED
                )
                self._state(identity, state)
                if self.role == supervision.SUPERVISOR:
                    self.delegated.add(identity)
            else:
                item = self._record(
                    identity, operation, params, admitted.profile, supervision.RUNNING
                )
                thread = threading.Thread(
                    target=self._tracked,
                    args=(
                        item,
                        self._operation_thread,
                        admitted,
                        self._work(operation, params),
                    ),
                    daemon=True,
                )
                self.threads[identity] = thread
                self.thread_operations[identity] = operation
                self._state(identity, state)
                thread.start()
        if delegating:
            self._wake()
        return self.get(identity)

    @staticmethod
    def _probe_lock(root):
        """`campaign_busy` now when a live process holds the campaign's
        ownership lock: an attached agent (detach it), the Control Center's
        tools (close them), or Carbon's agent at work. Takes the lock for an
        instant only; a campaign thread starting in that instant waits for it
        (`LOCK_WAIT_SECONDS`) rather than answering busy."""
        try:
            with owner_lock(root):
                return
        except RuntimeError:
            raise Rejected("campaign_busy", 409) from None

    def _hold(self, stack, root):
        """Enter the campaign's ownership lock on `stack`, trying for
        `LOCK_WAIT_SECONDS`. Raises `LockHeld` (a RuntimeError) while a live
        holder keeps it."""
        deadline = time.monotonic() + self.LOCK_WAIT_SECONDS
        while True:
            try:
                stack.enter_context(owner_lock(root))
                return
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    @staticmethod
    def _require_frozen(admitted):
        """The rules `research_campaign.submit_frozen` enforces, read from the
        campaign's files: the miner selects in it, a final exam is left, and
        a candidate is frozen for it. Until 2026-10-03 a campaign whose agent
        selects, or whose final exams were both used, was answered SUBMITTING
        and refused on the thread."""
        from carbon.development_session.research_campaign import FINAL_EPOCHS

        root = Path(admitted.campaign["root"])
        if product_agent(root) not in (None, "none"):
            raise Rejected("the_agent_selects_in_this_campaign", 409)
        for epoch in FINAL_EPOCHS:
            folder = root / ("epoch-" + str(epoch))
            if (folder / "permitted-final-feedback.json").exists():
                continue
            if (folder / "selected-recipe.json").exists():
                return
            break
        else:
            raise Rejected("final_exams_used", 409)
        raise Rejected("freeze_a_candidate_first", 409)

    def _operation_thread(self, admitted, work):
        """One miner operation's thread. Where no caller is waiting, its
        outcome is kept: a named refusal as the campaign's `last_refusal`
        (nothing was dispatched, and the campaign is settled as it stood), an
        interruption as INTERRUPTED, privately recorded, with its typed code.
        Until 2026-10-03 a refusal here was recorded as an interruption."""
        identity = admitted.campaign["id"]
        operation = getattr(work, "operation", None)
        try:
            self._operate(admitted, work)
        except Rejected as refused:
            self._refused(identity, refused.code, operation)
        except Exception as exc:  # noqa: BLE001 - never publish provider/key errors.
            record_interruption(Path(admitted.campaign["root"]), "operation", exc)
            self._state(identity, "INTERRUPTED")
            self._refused(
                identity,
                exception_code(exc) or "operation_interrupted",
                operation,
                kind="interrupted",
            )

    @staticmethod
    def _settle_ready(control, generation, ledger, cleanup, *, completed=False):
        """Settle a dispatch that leaves its campaign waiting for its miner:
        READY, unless a pause or stop was asked for meanwhile, which is then
        what it settles to (PAUSED, STOPPED). `settled` ranks READY above a
        pending pause, so the ask is checked here."""
        desired = control.status()["desired"]
        return control.settled(
            generation,
            completed=completed,
            ready=not completed and desired == "RUN",
            cleanup_verified=cleanup(ledger),
        )

    def _operate(self, admitted, work):
        """Run one miner operation on a prepared campaign, under its owner lock
        and a fresh control generation, and settle it afterwards.

        A refusal changes nothing, so the campaign settles READY again (or
        PAUSED or STOPPED, if that was asked meanwhile); only an unexpected
        failure leaves it for reconciliation.
        """
        from carbon.chain.external_signer import SignerFailure, signatures_obtained
        from carbon.development_session.research_agent_policy import AUTONOMOUS
        from carbon.development_session.research_campaign import (
            OperationRefused,
            prepare,
        )

        row, cfg = admitted.campaign, admitted.profile
        root = Path(row["root"])
        task = guidance.verify(
            json.loads(row["research_guidance"])
            if row["research_guidance"] is not None
            else None
        )
        stack = ExitStack()
        try:
            self._hold(stack, root)
        except RuntimeError:
            raise Rejected("campaign_busy", 409) from None
        with stack:
            ledger = CampaignLedger(root)
            control = CampaignControl(ledger)
            try:
                generation = control.acquire()
            except DispatchStopped:
                stopped = control.status()["state"] == "STOPPED"
                raise Rejected(
                    "campaign_stopped" if stopped else "campaign_complete", 409
                ) from None
            ledger.generation = generation
            args = campaign_args(
                cfg,
                root=root,
                accepted_revision=cfg["accepted_revision"],
                principal=cfg["principal"],
                agent_policy=AUTONOMOUS,
                product=None,
                research_guidance=task["text"] if task is not None else None,
                command="resume",
            )
            try:
                desired = control.status()["desired"]
                if desired != "RUN":
                    # Paused or stopped after admission: nothing starts.
                    raise Rejected(
                        "campaign_paused" if desired == "PAUSE" else "campaign_stopped",
                        409,
                    )
                if self._outstanding(ledger):
                    # As a run does: ambiguous work never resumes on its own.
                    raise Rejected("unresolved_operation", 409)
                credential = self._frozen_credential(cfg, root)
            except Rejected:
                # Nothing was dispatched; settle as it stood rather than leave
                # this generation in flight.
                self._settle_ready(control, generation, ledger, self._cleanup)
                raise
            if credential is not None:
                args.api_key_file = credential

            async def run():
                prepared = await prepare(args, ledger=ledger)
                if prepared is None:
                    raise OperationRefused("campaign_complete")
                try:
                    return await work(prepared)
                finally:
                    prepared.close()

            refused = None
            signed_before = signatures_obtained()
            try:
                result = asyncio.run(run())
            except OperationRefused as exc:
                refused = exc.code
            except SignerFailure as exc:
                # A signer that is not running, refuses, holds another hotkey
                # or times out sent nothing - but only if no earlier request of
                # this operation was signed. One that was may have been
                # delivered, so that is left for reconciliation, not refused.
                if signatures_obtained() != signed_before:
                    control.settled(generation, cleanup_verified=self._cleanup(ledger))
                    raise
                refused = exc.code
            except BaseException:
                control.settled(generation, cleanup_verified=self._cleanup(ledger))
                raise
            complete = (root / "campaign-complete.json").exists()
            state = self._settle_ready(
                control, generation, ledger, self._cleanup, completed=complete
            )
            self._state(row["id"], state)
        if refused is not None:
            raise Rejected(refused, 409)
        return result

    @staticmethod
    def _frozen_credential(cfg, root):
        """The key file for the provider a frozen campaign records, from the
        runner profile. A resumed campaign never sends one provider's key to
        another: an unconfigured provider is refused, not substituted."""
        provider = frozen_provider(root)
        if provider in (None, DEFAULT_PROVIDER):
            # Every campaign frozen before selection existed, unchanged: the
            # campaign checks this key itself when its agent needs one.
            if foreign_default_key(cfg):
                raise Rejected("model_provider_credential_not_configured", 409)
            path = provider_credential(cfg, DEFAULT_PROVIDER)
            return None if path is None else Path(path)
        path = provider_credential(cfg, provider)
        refusal = credential_refusal(path)
        if refusal is not None:
            raise Rejected(refusal, 409)
        return Path(path)

    def _start(self, run_id, cfg, root, product=None, choice=None, item=None):
        """Start the campaign's run (a launch or resume) on a thread here.

        `item` is the queue item a supervisor claimed for it; without one the
        run is recorded as started here, so every door can see it in flight.
        A run already alive here is the one a resume continues: nothing new
        starts.
        """
        with self.lock:
            if run_id in self.threads and self.threads[run_id].is_alive():
                if item is not None:
                    self._finish(item, "superseded")
                return
            if item is None:
                item = self._record(run_id, "run", {}, cfg, supervision.RUNNING)
            thread = threading.Thread(
                target=self._tracked,
                args=(item, self._run, run_id, cfg, root, product, choice),
                daemon=True,
            )
            self.threads[run_id] = thread
            self.thread_operations[run_id] = "run"
            thread.start()

    def _run(self, run_id, cfg, root, product, choice=None):
        """A campaign's run: prepare it (freezing the launch's choices the
        first time) and let whoever selects in it work, under its ownership
        lock and a fresh control generation.

        Its outcome is kept where no caller waits for it (LP-PROD-C): a named
        refusal before anything was dispatched settles the campaign as it
        stood and is kept as `last_refusal`; another holder of the campaign's
        lock is `campaign_busy` and changes nothing; a campaign stopped or
        complete before the run began is left so; a pause asked before the
        run began settles PAUSED rather than starting work.
        """
        from carbon.development_session.research_agent_policy import AUTONOMOUS
        from carbon.development_session.research_campaign import execute

        generation = None
        try:
            # Recheck the real operator profile at the thread handoff. A
            # disabled profile must not slip through a queued HTTP request.
            if self.configuration is not None and self.configured() != cfg:
                raise ValueError("dispatch configuration changed")
            row, kind, _ = self._bound(run_id)
            row = dict(row)
            if kind != "product":
                raise ValueError("a retired grant campaign is never dispatched")
            task = guidance.verify(
                json.loads(row["research_guidance"])
                if row["research_guidance"] is not None
                else None
            )
            if task != guidance.configured(cfg):
                # Frozen with other guidance than the profile now gives (D10).
                raise Rejected("profile_changed_since_launch", 409)
            stack = ExitStack()
            try:
                self._hold(stack, root)
            except RuntimeError:
                # An attached agent, the page's tools or another run holds
                # the campaign: nothing here changed it.
                self._refused(run_id, "campaign_busy", "run")
                return
            with stack:
                ledger = CampaignLedger(root)
                control = CampaignControl(ledger)
                try:
                    generation = control.acquire()
                except DispatchStopped:
                    # Stopped or complete before this run began.
                    self._state(run_id, control.status()["state"])
                    return
                ledger.generation = generation
                # Ambiguous work never resumes automatically, even under a new
                # generation. Completed observations remain replayable by runner.
                with ledger.db() as db:
                    pending = db.execute(
                        "SELECT 1 FROM operations WHERE state IN ('RESERVED','HELD') LIMIT 1"
                    ).fetchone()
                if pending:
                    self._refused(run_id, "unresolved_operation", "run")
                    raise DispatchStopped("unresolved operation")
                creating = not (root / "campaign-manifest.json").exists()
                try:
                    if control.status()["desired"] != "RUN":
                        # Paused or stopped before it began: settle to that.
                        control.settled(
                            generation, cleanup_verified=self._cleanup(ledger)
                        )
                        return
                    install_research_images(cfg, root)
                    if creating and product is None:
                        # Started where the launch was not received: rebuilt
                        # from its record, never from defaults (whose absence
                        # sent a resume of an unprepared launch down the
                        # retired grant path before 2026-10-03).
                        product, choice = self._recorded_launch(row, cfg)
                    credential = (
                        None if creating else self._frozen_credential(cfg, root)
                    )
                except Rejected as refused:
                    # Refused before anything was dispatched.
                    control.settled(generation, cleanup_verified=self._cleanup(ledger))
                    self._refused(run_id, refused.code, "run")
                    return
                args = campaign_args(
                    cfg,
                    root=root,
                    accepted_revision=cfg["accepted_revision"],
                    principal=cfg["principal"],
                    agent_policy=AUTONOMOUS,
                    product=product,
                    research_guidance=task["text"] if task is not None else None,
                    command="run" if creating else "resume",
                )
                if creating:
                    # The launch's choice freezes into the manifest now.
                    if choice is not None:
                        choice.apply(args)
                elif credential is not None:
                    # A resume keeps the frozen choice; only its key file is
                    # read again, from the profile, for the frozen provider.
                    args.api_key_file = credential
                outcome = None
                try:
                    outcome = asyncio.run(execute(args, ledger=ledger))
                except Exception as exc:  # noqa: BLE001 - kept private
                    # Never published; record_interruption keeps only its type.
                    record_interruption(root, "run" if creating else "resume", exc)
                    self._state(run_id, "INTERRUPTED")
                    self._refused(
                        run_id,
                        exception_code(exc) or "campaign_interrupted",
                        "run",
                        kind="interrupted",
                    )
                finally:
                    clean = self._cleanup(ledger)
                    completed = (root / "campaign-complete.json").exists()
                    # An agent-less campaign is prepared and waiting for its
                    # miner: ready, not interrupted - unless a pause or stop
                    # was asked meanwhile, which it then settles to.
                    ready = (
                        not completed
                        and product_agent(root) == "none"
                        and control.status()["desired"] == "RUN"
                    )
                    state = control.settled(
                        generation,
                        completed=completed,
                        ready=ready,
                        cleanup_verified=clean,
                    )
                    if state == "READY":
                        self._state(run_id, "READY")
                if type(outcome) is str:
                    # Carbon's agent selected a candidate the validator did
                    # not evaluate (`run_agent`): the code says why.
                    self._refused(run_id, outcome, "submit")
        except Exception as exc:  # noqa: BLE001
            self._state(run_id, "RECONCILIATION_REQUIRED")
            if generation is not None:
                control.settled(generation, cleanup_verified=False)
            if isinstance(exc, Rejected):
                self._refused(run_id, exc.code, "run")
            elif not isinstance(exc, DispatchStopped):
                code = (
                    "dispatch_configuration_changed"
                    if str(exc) == "dispatch configuration changed"
                    else exception_code(exc) or "reconciliation_required"
                )
                self._refused(run_id, code, "run", kind="interrupted")

    def _state(self, run_id, state):
        with self.db() as db:
            for table in ("launchpad_campaigns", "research_runs"):
                db.execute(
                    f"UPDATE {table} SET state=? WHERE id=?",
                    (state, run_id),
                )

    @staticmethod
    def _cleanup(ledger):
        """Use domain cleanup journals; absence of a browser process proves nothing."""
        from carbon.development_session.research_carrier import reconcile_worker
        from carbon.execution import DurableWorkerLaunchStore
        from carbon.reconstruction.worker.docker_runtime import (
            DockerCLI,
            remove_exact_container,
        )
        from carbon.reconstruction.worker.operator import _stores

        clean = True
        # HELD is capacity, never a worker. Release through the same sequence
        # transaction; dispatched children still need their actual domain journal.
        with ledger.db() as db:
            sequences = db.execute(
                "SELECT parent,owner FROM operation_sequences"
            ).fetchall()
        for parent, owner in sequences:
            try:
                ledger.cancel_sequence_held(parent, owner=owner)
                ledger.settle_sequence(parent, owner=owner)
            except Exception:  # noqa: BLE001
                clean = False
        with ledger.db() as db:
            rows = db.execute(
                "SELECT id,owner FROM operations WHERE state='RESERVED'"
            ).fetchall()
        # Every RESERVED operation goes to reconcile_worker, which keys on the
        # durable worker intent rather than reserved milliseconds - the miner's
        # own run with no wall allowance reserves none. One it cannot settle
        # stays RESERVED, and a skipped operation is never counted as clean.
        for identity, owner in rows:
            try:
                reconcile_worker(ledger, owner=owner, identity=identity)
            except Exception:  # noqa: BLE001
                clean = False
        for path in _stores(ledger.root):
            store = DurableWorkerLaunchStore(path)
            for item in store.reconciliation_targets():
                try:
                    cli = DockerCLI()
                    remove_exact_container(
                        cli=cli,
                        container_name=item["container_name"],
                        launch_digest=item["launch_digest"],
                    )
                    if cli.run(
                        [
                            "ps",
                            "-aq",
                            "--filter",
                            "name=^" + item["container_name"] + "$",
                        ],
                        timeout=10,
                    ).stdout.strip():
                        raise ValueError("owned worker remains")
                    store.record_operator_cleanup(
                        execution_id=item["execution_id"],
                        launch_digest=item["launch_digest"],
                        cleaned=True,
                    )
                except Exception:  # noqa: BLE001
                    clean = False
        return clean

    def _bound(self, identity):
        """The campaign row, which kind it is, and its root.

        Product campaigns and retired-grant campaigns are separate records, so
        a retired one can never be mistaken for something to dispatch.
        """
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM launchpad_campaigns WHERE id=?", (identity,)
            ).fetchone()
            kind = "product"
            if row is None:
                row = db.execute(
                    "SELECT * FROM research_runs WHERE id=?", (identity,)
                ).fetchone()
                kind = "retired_grant"
        if row is None or row["principal"] != self.principal:
            raise Rejected("research_run_unavailable", 404)
        return row, kind, Path(row["root"])

    def _ledger(self, row, kind, root):
        """The campaign's ledger. A retired grant is held only for cleanup."""
        if kind == "product":
            return CampaignLedger(root)
        from carbon.development_session.research_admission import (
            retained_grant_ledger,
        )

        return retained_grant_ledger(
            root, json.loads(row["grant_record"]), row["grant_digest"]
        )

    def control(self, identity, action):
        """The browser's control route: a caller of halt or resume."""
        from scripts.dev.miner_launchpad.operations import perform

        if action == "resume":
            return perform(self, "resume", {"campaign": identity})
        return perform(self, "halt", {"campaign": identity, "action": action})

    def _control(self, identity, action):
        row, kind, root = self._bound(identity)
        if action == "resume" and kind != "product":
            # Resuming would dispatch new work under a grant, which no product
            # surface may do. Observe, pause, stop and reconcile still work.
            raise Rejected("retired_grant_campaign", 409)
        if action == "resume" and retired_challenge(root):
            # Burgers is retired from the research path: nothing resumes it.
            # Observe, pause, stop and reconcile still settle what it holds.
            raise Rejected("challenge_retired", 409)
        ledger = self._ledger(row, kind, root)
        control = CampaignControl(ledger)
        if action == "reconcile":
            if not self._settle_if_idle(ledger, control, root):
                raise Rejected("campaign_busy", 409)
        else:
            if action == "resume":
                try:
                    cfg = self.configured()
                except Rejected:
                    raise
                except Exception:  # noqa: BLE001 - never the profile's content
                    raise Rejected("research_profile_unavailable", 409) from None
                # Each refused by name now, rather than after the thread
                # starts: a checkout the profile did not accept (D9), a
                # profile that no longer matches what the campaign was frozen
                # with (D10), the frozen provider's key.
                self._current(cfg)
                self._resume_binding(cfg, dict(row), root)
                self._frozen_credential(cfg, root)
            try:
                control.request(action)
            except ValueError:
                # A stop cannot be reversed: resume and pause refused by name.
                raise Rejected("campaign_stopped", 409) from None
            if action == "stop":
                ledger.generation = control.status()["generation"]
                from carbon.development_session.research_carrier import request_cancel

                with ledger.db() as db:
                    sequences = db.execute(
                        "SELECT parent,owner FROM operation_sequences"
                    ).fetchall()
                    operations = db.execute(
                        "SELECT id,owner FROM operations WHERE state='RESERVED'"
                    ).fetchall()
                for parent, owner in sequences:
                    ledger.cancel_sequence_held(parent, owner=owner)
                for operation, owner in operations:
                    request_cancel(ledger, owner=owner, identity=operation)
            if action in ("pause", "stop"):
                # Nothing running holds an idle campaign, so nothing would
                # ever act on the request: settle it now (LP-PROD-C). A live
                # holder settles it at its next checkpoint instead.
                self._settle_if_idle(ledger, control, root)
            if action == "resume":
                # Resumes the frozen campaign; its manifest carries everything
                # the launch admitted, so no new admission is constructed. One
                # never prepared is carried out from its launch record.
                self._dispatch_run(identity, cfg, root)
        return self.get(identity)

    @staticmethod
    def _resume_binding(cfg, row, root):
        """Refuse a resume, `profile_changed_since_launch` ("launch a new
        campaign"), when the profile no longer matches what the campaign
        needs (LP-PROD-C D10).

        A prepared campaign is bound to its frozen manifest, not to the whole
        profile: only what it was frozen with is compared
        (`binding_changes`), so changing an unrelated setting - a model
        choice for new launches, a validator intake, the remote machine's
        address, the profile's name - no longer orphans every existing
        campaign. Until 2026-10-03 any change to the profile digest refused
        every resume, as `research_reconciliation_required`. A launch never
        prepared has no manifest yet: it is carried out from its record under
        the profile its miner reviewed, so that whole profile still binds it.
        """
        manifest = Path(root) / "campaign-manifest.json"
        if not manifest.exists():
            if digest(canonical(cfg)) != row["config_digest"]:
                raise Rejected("profile_changed_since_launch", 409)
            return
        if binding_changes(cfg, row, json.loads(manifest.read_bytes())):
            raise Rejected("profile_changed_since_launch", 409)

    def _settle_if_idle(self, ledger, control, root):
        """Settle the campaign now, with the real cleanup check, if no live
        process holds its ownership lock: PAUSED or STOPPED as asked, or
        RECONCILIATION_REQUIRED while work may be outstanding; reconciled with
        nothing outstanding, a campaign whose miner selects is READY again.
        False when a live holder (a run, an operation, an attached agent or
        the page's tools) has it; that holder settles it. A finished campaign
        is left as it is."""
        stack = ExitStack()
        try:
            stack.enter_context(owner_lock(root))
        except RuntimeError:
            return False
        with stack:
            try:
                generation = control.acquire()
            except DispatchStopped:
                return True
            ledger.generation = generation
            completed = (root / "campaign-complete.json").exists()
            control.settled(
                generation,
                completed=completed,
                ready=not completed
                and control.status()["desired"] == "RUN"
                and product_agent(root) == "none",
                cleanup_verified=self._cleanup(ledger),
            )
        return True

    def get(self, identity):
        """The campaign as its owner observes it: the projection, the last
        refusal no caller saw (`last_refusal`), the work admitted for it and
        not yet done (`in_flight`), and what gets it moving again
        (`recovery`), all null or empty when there is none."""
        from scripts.dev.miner_launchpad.projection import project

        row, kind, root = self._bound(identity)
        row = dict(row)
        value = project(row, root)
        # A retired-grant row has no such column: never refused here.
        value["last_refusal"] = supervision.read_refusal(row.get("last_refusal"))
        value["in_flight"] = self._in_flight(identity)
        # Only what can succeed: nothing resumes a retired-grant campaign or
        # one on a retired Challenge (`_control`), so neither is offered it.
        value["recovery"] = supervision.recovery_actions(
            value["state"],
            value["in_flight"],
            resumable=kind == "product" and not retired_challenge(root),
        )
        return value

    def _in_flight(self, identity):
        """The newest dispatch admitted for the campaign and not yet done:
        {operation, state (QUEUED or RUNNING), since, supervisor_running}."""
        with self.db() as db:
            item = supervision.active(db, principal=self.principal, campaign=identity)
        if item is None:
            return None
        running = item["supervisor"] == self.token or self._supervisor_running()
        if item["state"] == supervision.QUEUED and not running:
            # Observed waiting with nobody to carry it out (the Control
            # Center closed, say): a client starts a supervisor for it.
            with contextlib.suppress(Exception):
                self._wake()
        return {
            "operation": item["operation"],
            "state": item["state"],
            "since": round(item["claimed"] or item["created"], 3),
            "supervisor_running": running,
        }

    def recent(self):
        with self.db() as db:
            ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM (SELECT id,created FROM launchpad_campaigns WHERE principal=? UNION ALL SELECT id,created FROM research_runs WHERE principal=?) ORDER BY created DESC LIMIT 100",
                    (self.principal, self.principal),
                )
            ]
        result = []
        for identity in ids:
            # One campaign whose records cannot be read back is one row that
            # says so; the list, and the page built on it, stays up (D13).
            # Until 2026-10-03 only a `Rejected` was caught, so one bad
            # projection failed GET /api/v1/research and the whole page read
            # "Connection interrupted". Records that disagree with each other
            # (`projection.RecordsDiffer`) are `campaign_readback_unavailable`;
            # anything else may pass - a busy database, a bug - so it is the
            # milder `campaign_read_failed`, never advice to abandon it.
            try:
                result.append(self.get(identity))
            except Exception as exc:  # noqa: BLE001 - never a trace or a path
                code = (
                    "campaign_readback_unavailable"
                    if exception_code(exc) == "campaign_readback_unavailable"
                    else "campaign_read_failed"
                )
                result.append(
                    {
                        "id": identity,
                        "state": "READBACK_UNAVAILABLE",
                        "mode": "LIVE_PRACTICE_RESEARCH",
                        "code": code,
                        "next_action": supervision.NEXT_ACTIONS[code],
                    }
                )
        return result

    def close(self):
        """Close this door. Never stops a campaign (LP-PROD-C).

        A client owns no campaign thread, so closing it leaves every campaign
        to its supervisor: it detaches. A process that runs campaign threads
        (the Control Center, a detached supervisor) asks each live campaign to
        pause - reversible, resumed with one call - waits briefly for them to
        settle, then releases the supervisor lock for the next supervisor.
        One that does not settle in time is settled by that supervisor's
        recovery from its ledger. Before 2026-10-03 closing sent every live
        campaign an irreversible stop, so closing an agent mid-practice
        stopped its campaign for good.

        A Control Center closing before it took over from a detached
        supervisor does the same for the work it admitted meanwhile: what no
        supervisor started is withdrawn, what started is asked to pause
        (`_withdraw_or_pause`), and what was paused to hand over to it stays
        paused (`release_handover_pauses`). Closing it never leaves work it
        admitted running unattended (D4).

        It waits until each live thread has ended or is parked at its
        campaign's pause (`busy_threads`): a parked run never ends on its own,
        and waiting for it only delayed the next supervisor.
        """
        # The page's tool sessions release their campaigns first (RSURF-D16).
        self.tool_sessions.close_all()
        if self.supervisor is not None:
            self.supervisor.stop()
        live = [
            (identity, thread)
            for identity, thread in tuple(self.threads.items())
            if thread.is_alive()
        ]
        for identity, _thread in live:
            with contextlib.suppress(Exception):
                self._pause_for_close(identity)
        if self.role == supervision.SUPERVISOR:
            for identity in tuple(self.delegated):
                with contextlib.suppress(Exception):
                    self._withdraw_or_pause(identity)
        deadline = time.monotonic() + supervision.CLOSE_JOIN_SECONDS
        while live and time.monotonic() < deadline:
            busy = set(self.busy_threads())
            live = [
                (i, t)
                for i, t in live
                if i in busy and t.is_alive() and hasattr(t, "join")
            ]
            if live:
                live[0][1].join(timeout=0.05)
        if self.role == supervision.SUPERVISOR:
            with contextlib.suppress(Exception):
                self.release_handover_pauses()
        if self.supervisor is not None:
            self.supervisor.release()

    def _pause_for_close(self, identity):
        """Ask a live campaign to pause because its supervisor is closing,
        and say so in its `last_refusal`. A stop already asked for stands."""
        row, kind, root = self._bound(identity)
        control = CampaignControl(self._ledger(row, kind, root))
        status = control.status()
        if status["desired"] != "RUN" or status["state"] in supervision.TERMINAL:
            return
        control.request("pause")
        self._refused(identity, "paused_when_supervisor_closed", None, kind="paused")
