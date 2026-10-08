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
import datetime
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
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
    # Per Challenge (LAUNCHPAD-ACCEPT-03): {challenge_id: ss58}, the receiver
    # hotkey that Challenge's intake must report before anything is signed
    # for it. Review pins it; a profile written before has none, and its
    # intake is not checked (setup and the prelaunch review warn).
    "receivers",
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


#: An ss58 address, as a pinned receiver hotkey is written.
RECEIVER_ADDRESS = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")


def receivers(cfg):
    """{challenge_id: receiver hotkey} the profile pins (LAUNCHPAD-ACCEPT-03);
    empty for a profile written before receivers were pinned."""
    return dict(cfg.get("receivers") or {})


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
        receivers=receivers(cfg),
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


def miner_hotkey(cfg):
    """The profile's public hotkey; never a key."""
    return json.loads(Path(cfg["paths"]["miner_public"]).read_bytes())["hotkey"]


def sdk_commitment_chain(cfg):
    """The commitment's chain side for the profile's network
    (`commitment_poster.SdkCommitmentChain`): reads at the finalized head,
    prepares, estimates and broadcasts. It never signs."""
    from carbon.chain.commitment_poster import SdkCommitmentChain
    from carbon.development_session.miner_network import binding

    config = binding(
        operator_config=cfg["paths"].get("operator_config"),
        miner_network=cfg["paths"].get("miner_network"),
    )
    return SdkCommitmentChain(config.context)


def signer_commit(cfg):
    """`sign(request)` through the miner's own signer (D2): it rebuilds the
    call, asks the miner on its own terminal and signs. Carbon holds no key."""
    from carbon.chain.external_signer import request_commitment

    def sign(request):
        return request_commitment(signer_ready(cfg), request)

    return sign


class _UnreadableGate:
    """A campaign's commitment gate when the profile's chain could not be
    reached: every submit it gates is refused, nothing sent (fail closed)."""

    @staticmethod
    def before_submit(*_, **__):
        from carbon.chain.commitment_poster import UNREADABLE

        return UNREADABLE


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


def waits_for_its_miner(root):
    """Whether the campaign at `root`, once nothing holds it, settles READY:
    `research_campaign.waits_for_its_miner` - no agent, or a retained
    candidate the validator did not evaluate - asked by every door that
    settles a campaign here (LP-PROD-FIX-01)."""
    from carbon.development_session.research_campaign import (
        waits_for_its_miner as waits,
    )

    return waits(root)


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


def stepped(code, next_step, status=409):
    """A `Rejected` that carries its own next step, which the HTTP door sends
    as `next_step` (`controller.error_body`): for a code whose step depends
    on what was found - a model call's settlement refusal, a profile that no
    longer describes this install - rather than on the code alone."""
    refused = Rejected(code, status)
    refused.next_step = next_step
    return refused


def install_refusal(configuration, cfg):
    """`carbon_updated_rerun_installer`, carrying the step that clears it and
    why, when the runner profile at `configuration` (content `cfg`) no longer
    describes what the installer installed beside it; otherwise None.

    LP-PROD-E's staleness check (`environment_setup.profile_staleness`),
    applied before a profile is attached (LP-PROD-W2): until then the Control
    Center attached `runner-profile.json` on every start, and `carbon-mcp
    --configuration` any profile, whatever the installer had installed since.
    Only `after_install` moved a stale one aside."""
    from scripts.dev.miner_launchpad.environment_setup import profile_staleness

    reasons, step = profile_staleness(configuration, cfg)
    if not reasons:
        return None
    return stepped(CARBON_UPDATED, step + ": " + "; ".join(reasons))


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


#: How a submit through a validator intake ended, when it was not a verdict
#: (LAUNCHPAD-ACCEPT-04): the validator holds it, the validator's side could
#: not serve, or the miner acts.
INTAKE_OUTCOMES = ("QUEUED", "UNAVAILABLE", "REFUSED")


def _intake_outcome(refusal, root):
    """`QUEUED`, `UNAVAILABLE` or `REFUSED` for a campaign's last submit
    refusal that a trip through its Challenge's intake reported, read from
    the Challenge's own campaign (`intake_outcome`); None otherwise. This
    runner names no Challenge's module, so a Challenge with no intake, or a
    code that is not an intake's, is None."""
    from carbon.challenge_registry.campaigns import campaign_for_manifest

    if refusal is None or refusal.get("operation") != "submit":
        return None
    try:
        manifest = json.loads((Path(root) / "campaign-manifest.json").read_bytes())
        classify = campaign_for_manifest(manifest).intake_outcome
        found = classify(refusal["code"]) if classify is not None else None
    except Exception:  # noqa: BLE001 - not readable: not shown, never guessed
        return None
    return found if found in INTAKE_OUTCOMES else None


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
    if "receivers" in cfg:
        _registered_challenge_ids(cfg["receivers"], "receivers")
        if any(
            type(v) is not str or not RECEIVER_ADDRESS.fullmatch(v)
            for v in cfg["receivers"].values()
        ):
            raise ValueError("a receiver is an ss58 hotkey address")
        if not set(cfg["receivers"]) <= set(intakes(cfg)):
            raise ValueError("a receiver is pinned only beside its intake")
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


def setup_selection(cfg, *, settings=None, output_default=None):
    """The profile's setup choice as a validated selection, with its key file.

    Raises `ModelSelectionRefused` when it does not validate.
    """
    from carbon.development_session.model_provider import select

    chosen = cfg["model_selection"]
    path = provider_credential(cfg, chosen["provider_id"])
    return select(
        credential={"kind": "file", "reference": path or "unset"},
        settings=settings,
        output_default=output_default,
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
    file for that provider), the Challenge's feedback mode, and Graphite's
    launch choice. Applied when the campaign is first created, never on
    resume: the manifest is frozen then."""

    selection: object = None
    feedback_mode: str | None = None
    #: The launch's settings overrides, exactly as `select` accepted them.
    #: None keeps the historical args shape and sets nothing: the campaign's
    #: own builder chooses the defaults, a new plan's output cap being the
    #: model's own maximum (OWNER-LAUNCHPAD-PROD-02).
    settings: dict | None = None
    #: Graphite's launch choice (`graphite_launch`, with the curation digest
    #: captured at admission), or None for any other agent: then the args
    #: carry no `graphite`, exactly as before Graphite existed.
    graphite: dict | None = None

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
        if self.graphite is not None:
            # Exactly the launch fields S3's `edition.launch_fields` reads
            # (`driver.freeze_launch` validates them again and freezes the
            # provider plan's graphite block from them), and, beside them,
            # the curation digest admission captured, for the campaign to
            # freeze that curation rather than the library's current one.
            args.graphite = {key: self.graphite[key] for key in GRAPHITE_LAUNCH_KEYS}
            args.graphite_curation_digest = self.graphite["curation_digest"]


# ---- Graphite, the miner edition (OWNER-GRAPHITE-MINER-01, S4).

#: The launch agent that runs Graphite's miner edition. It replaced
#: `autonomous` for new launches: a new launch naming `autonomous` is refused
#: `autonomous_agent_replaced` after the replay gate, so a launch recorded
#: under it still replays, a queued one is still carried out, and a frozen
#: autonomous campaign still runs `run_agent` unchanged.
GRAPHITE = "graphite"
RETIRED_AGENT = "autonomous"
#: The agents whose campaign calls a model, and so takes a model selection.
MODEL_AGENTS = (RETIRED_AGENT, GRAPHITE)
#: The miner edition a new Graphite launch names. What it means - its role
#: prompts and tool manifests by digest - is the edition registry's
#: (`agent_campaign.graphite.miner.edition.MINER_EDITIONS`), which refuses an
#: unknown one (`graphite_edition_unknown`) before any model call.
GRAPHITE_EDITION = "carbon.graphite.miner-edition.v1"
GRAPHITE_MODES = ("RESEARCH", "BUILD", "FULL")
DEFAULT_GRAPHITE_MODE = "FULL"
#: The research share a FULL launch that names none is frozen with (the
#: design's default, tunable by the miner from 0 to 1).
DEFAULT_RESEARCH_SHARE = 0.10
#: The launch fields only Graphite reads.
GRAPHITE_FIELDS = ("graphite_mode", "research_share", "plan", "hunt", "limits")
#: What a Graphite campaign receives as `args.graphite`: exactly the names S3's
#: `edition.launch_fields` reads (`LAUNCH_FIELDS`), which refuses any other
#: (`graphite_launch_invalid`). The edition is the campaign's to name.
GRAPHITE_LAUNCH_KEYS = ("mode", "research_share", "plan", "hunt", "limits")
#: A hunt's shape: at most 8 queries of at most 6 terms, each starting with
#: a letter or digit and holding only letters, digits and -, never an arXiv
#: operator word; and a record count (default 200, at most the arXiv client's
#: 5,000). Raw arXiv query syntax is never accepted; Carbon composes the
#: query. These are S2's own bounds (`focus.parse_miner_queries`,
#: `hunt.MAX_RECORDS`), checked here first so a launch S2's hunt would refuse
#: is refused before its campaign exists; a test pins them equal.
HUNT_MAX_QUERIES, HUNT_MAX_TERMS, HUNT_QUERY_CHARS = 8, 6, 128
HUNT_DEFAULT_RECORDS, HUNT_MAX_RECORDS = 200, 5000
_HUNT_TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,39}")
HUNT_OPERATORS = frozenset({"and", "or", "not", "andnot"})
#: Optional per-epoch and per-stage caps (owner: "generous and tunable
#: limits"); unset, only the campaign's own ceilings bind. At most the
#: engine's own tunable bound (S1's `MAX_TUNABLE_CAP`, as S3's launch fields
#: read it); a test pins them equal.
LIMIT_KEYS = ("calls_per_epoch", "trials_per_epoch", "planner_calls")
LIMIT_MAX = 100_000
#: The most pinned cards one plan can consider (S3's `plan.MAX_PINS`): a
#: launch whose Planner runs first must name every pin in its plan.
MAX_PINS = 64
#: A plan's digest, as the library and S3's launch fields name it.
_PLAN_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
#: Where the miner's private Graphite library lives: beside their runner
#: profile, in the setup root (`<setup root>/graphite-library`).
LIBRARY_DIRECTORY = "graphite-library"
#: The key a launch record keeps what admission captured for Graphite under.
#: Never a request field (the closed-request gate refuses it), so it never
#: joins the launch's identity.
GRAPHITE_ADMISSION = "graphite_admission"


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def hunt_value(value):
    """A launch's `hunt`, validated: {queries (list or None), max_records}."""
    if type(value) is not dict or not set(value) <= {"queries", "max_records"}:
        raise Rejected("hunt_query_invalid")
    queries = value.get("queries")
    if queries is not None:
        if type(queries) is not list or not 1 <= len(queries) <= HUNT_MAX_QUERIES:
            raise Rejected("hunt_query_invalid")
        for query in queries:
            terms = query.split(" ") if type(query) is str else None
            if (
                terms is None
                or len(query) > HUNT_QUERY_CHARS
                or not 1 <= len(terms) <= HUNT_MAX_TERMS
                or not all(_HUNT_TERM.fullmatch(term) for term in terms)
                or any(term.lower() in HUNT_OPERATORS for term in terms)
            ):
                raise Rejected("hunt_query_invalid")
        queries = list(queries)
    records = value.get("max_records", HUNT_DEFAULT_RECORDS)
    if type(records) is not int or not 1 <= records <= HUNT_MAX_RECORDS:
        raise Rejected("hunt_query_invalid")
    return {"queries": queries, "max_records": records}


def limits_value(value):
    """A launch's `limits`, validated: only the keys set, each 1..LIMIT_MAX."""
    if type(value) is not dict or not set(value) <= set(LIMIT_KEYS):
        raise Rejected("graphite_limits_invalid")
    for item in value.values():
        if type(item) is not int or not 1 <= item <= LIMIT_MAX:
            raise Rejected("graphite_limits_invalid")
    return {key: value[key] for key in LIMIT_KEYS if key in value}


def graphite_launch(request):
    """The launch's Graphite choice, validated, with its defaults resolved, or
    None for any other agent.

    {mode, research_share, plan, hunt, limits} - the names S3's launch fields
    take: `mode` FULL by default; `research_share` 0.10 for FULL and None
    otherwise; `plan` (a plan digest) only for BUILD; `hunt` None unless
    asked for, and only where a hunt runs (RESEARCH and FULL: S3 runs no hunt
    in BUILD); `limits` the caps set, possibly none. A Graphite field with
    another agent, or with a mode that does not read it, is refused by name:
    nothing is accepted that nothing uses. A field sent as null is absent
    (the request gate drops it before anything is digested). Pure: the
    library is not read here.
    """
    sent = [field for field in GRAPHITE_FIELDS if request.get(field) is not None]
    if request.get("agent") != GRAPHITE:
        if sent:
            raise Rejected("graphite_fields_need_the_graphite_agent", 409)
        return None
    mode = request.get("graphite_mode")
    if mode is None:
        mode = DEFAULT_GRAPHITE_MODE
    if type(mode) is not str or mode not in GRAPHITE_MODES:
        raise Rejected("graphite_mode_invalid")
    share = request.get("research_share")
    if share is not None:
        if mode != "FULL":
            raise Rejected("graphite_field_not_used_by_mode", 409)
        if not _number(share) or not 0 <= share <= 1:
            raise Rejected("research_share_invalid")
    elif mode == "FULL":
        share = DEFAULT_RESEARCH_SHARE
    plan = request.get("plan")
    if plan is not None:
        if mode != "BUILD":
            raise Rejected("graphite_field_not_used_by_mode", 409)
        if type(plan) is not str or not _PLAN_DIGEST.fullmatch(plan):
            raise Rejected("plan_not_found", 404)
    hunt = None
    if request.get("hunt") is not None:
        if mode == "BUILD":
            # BUILD runs no hunt (S3's stages and `launch_fields`): with a
            # plan the Planner never runs, and without one it plans from the
            # pack and the library as they stand. A hunt sent with BUILD is
            # refused here, before anything is created, not by the campaign
            # after it was.
            raise Rejected("graphite_field_not_used_by_mode", 409)
        hunt = hunt_value(request["hunt"])
    limits = request.get("limits")
    return {
        "mode": mode,
        "research_share": share,
        "plan": plan,
        "hunt": hunt,
        "limits": limits_value({} if limits is None else limits),
    }


#: A hunt's planning figures, per abstract Graphite's Reader reads: an
#: estimate shown before launch from the selection's price, never a cap or a
#: charge. On a cheap model it is about USD 0.0001 an abstract; what a hunt
#: costs is what the miner's provider reports, metered against their budget.
READER_TOKENS_PER_ABSTRACT = {"input": 1000, "output": 250}

GRAPHITE_MODE_SUMMARIES = {
    "RESEARCH": (
        "Hunt (when asked) and read, then write a ranked plan into your "
        "library. Nothing is practised, selected or submitted."
    ),
    "BUILD": (
        "Take a plan - one you edited, one from an earlier Research run, or "
        "none, and the Planner writes one first - then construct, practise, "
        "select and submit."
    ),
    "FULL": (
        "Research within the research share of your budget, then build. The default."
    ),
}


def hunt_estimate(cfg):
    """A hunt's cost per abstract for the model a launch naming none runs
    with (setup's choice, or the pinned default), from its price; None when
    that model has no price."""
    from carbon.development_session.model_provider import (
        DEFAULT_SELECTION,
        ModelSelectionRefused,
    )

    try:
        selection = (
            setup_selection(cfg) if "model_selection" in cfg else DEFAULT_SELECTION
        )
    except (ModelSelectionRefused, KeyError, TypeError, ValueError):
        selection = None
    pricing = getattr(selection, "pricing", None)
    per = (
        None
        if pricing is None
        else READER_TOKENS_PER_ABSTRACT["input"] * pricing.input_nano
        + READER_TOKENS_PER_ABSTRACT["output"] * pricing.output_nano
    )
    return {
        "reader_tokens_per_abstract": dict(READER_TOKENS_PER_ABSTRACT),
        "model": (
            None
            if selection is None
            else selection.provider_id + ":" + selection.model_id
        ),
        "nanodollars_per_abstract": per,
        "basis": (
            "an estimate from the model's price for planning only; a hunt "
            "spends what your provider reports, within your budget, and a "
            "paper already in the pack or your library is never read twice"
        ),
    }


def graphite_options(cfg):
    """What a Graphite launch may choose, for the launch form and an agent:
    the modes, the research share, a hunt's shape and planning cost, the
    optional limits, and the Challenges Graphite runs on."""
    from carbon.challenge_registry.campaigns import implemented_campaigns

    return {
        "agent": GRAPHITE,
        "edition": GRAPHITE_EDITION,
        "modes": [
            {
                "id": mode,
                "summary": GRAPHITE_MODE_SUMMARIES[mode],
                "default": mode == DEFAULT_GRAPHITE_MODE,
            }
            for mode in GRAPHITE_MODES
        ],
        "research_share": {
            "default": DEFAULT_RESEARCH_SHARE,
            "minimum": 0,
            "maximum": 1,
            "mode": "FULL",
            "of": ["provider_nanodollars", "provider_attempts"],
        },
        "plan": {
            "mode": "BUILD",
            "from": "your library (plan_list)",
            "omitted": "the Planner writes one first",
        },
        "hunt": {
            # S3 runs a hunt only before RESEARCH's and FULL's Planner.
            "modes": ["RESEARCH", "FULL"],
            "max_queries": HUNT_MAX_QUERIES,
            "max_terms": HUNT_MAX_TERMS,
            "terms": "letters, digits and -",
            "default_records": HUNT_DEFAULT_RECORDS,
            "max_records": HUNT_MAX_RECORDS,
            "seconds_between_requests": 3,
            "omitted": (
                "no hunt; the shared pack and your library still serve, and "
                "queued imports wait for a launch that hunts"
            ),
            "estimate": hunt_estimate(cfg),
        },
        "limits": {
            "keys": list(LIMIT_KEYS),
            "minimum": 1,
            "maximum": LIMIT_MAX,
            "omitted": "only your campaign ceilings - money, attempts, trials, time - bind",
        },
        "offered_for": [
            {"id": entry.challenge_id, "version": entry.version}
            for entry, _campaign in implemented_campaigns()
        ],
    }


def graphite_offered(challenge):
    """Whether Graphite runs on `challenge` ({id, version}): only on a
    Challenge with a registered research campaign (`campaign_for`)."""
    from carbon.challenge_registry import ResolutionError
    from carbon.challenge_registry.campaigns import campaign_for

    try:
        campaign_for(challenge)
    except (ResolutionError, TypeError, ValueError, LookupError):
        return False
    return True


def _open_library(root):
    """The miner's library (S2's `MinerLibrary`) at `root`."""
    from carbon.agent_campaign.graphite.miner.library import MinerLibrary

    return MinerLibrary(Path(root))


def _shared_pack():
    """The shared card pack Carbon ships (S2's `pack.load_shared_pack`),
    checked against its pinned digest by the loader."""
    from carbon.agent_campaign.graphite.miner.pack import load_shared_pack

    return load_shared_pack()


def _validate_plan(plan, library, curation):
    """S3's plan rule: (ok, refusal)."""
    from carbon.agent_campaign.graphite.miner.plan import validate_plan

    return validate_plan(plan, library=library, curation=curation)


#: The plan schema the miner edits (S3's `plan.PLAN_SCHEMA`).
PLAN_SCHEMA = "carbon.graphite.miner-plan.v1"
#: What the library and plan operations answer, by schema.
LIBRARY_SEARCH_SCHEMA = "carbon.launchpad.library-search.v1"
LIBRARY_CARD_SCHEMA = "carbon.launchpad.library-card.v1"
LIBRARY_LIST_SCHEMA = "carbon.launchpad.library.v1"
LIBRARY_CURATION_SCHEMA = "carbon.launchpad.library-curation.v1"
LIBRARY_IMPORT_SCHEMA = "carbon.launchpad.library-import.v1"
PLAN_LIST_SCHEMA = "carbon.launchpad.plans.v1"
PLAN_GET_SCHEMA = "carbon.launchpad.plan.v1"
PLAN_EDIT_SCHEMA = "carbon.launchpad.plan-edit.v1"
#: Every served card's status: Carbon checks no card (OWNER-GRAPHITE-MINER-01).
UNCHECKED = "UNCHECKED"
#: Where a card came from: the pack Carbon ships, the miner's hunt, or text
#: the miner imported. A card with any other origin is never served.
CARD_ORIGINS = ("shared", "miner_hunt", "miner_import")
#: A card's own fields, as the pack and the library hold them; nothing else
#: of a card reaches either door.
CARD_FIELDS = (
    "card_id",
    "title",
    "abstract",
    "technique",
    "claimed_effect",
    "data_regime",
    "cost",
    "code_available",
    "applicability",
    "provenance",
)
#: What every card answer says about its text.
CARD_NOTICE = {
    "check_status": UNCHECKED,
    "untrusted": True,
    "rights": (
        "arXiv titles and abstracts are CC0 descriptive metadata; the other "
        "fields are Carbon's extraction, not a claim Carbon makes"
    ),
    "shown_as": "untrusted text",
}
#: S2's typed library refusals (`library.LibraryError.code`) a door answers
#: by name, with its status; every other library failure is
#: `library_unavailable`. S2's `search_invalid` is the door's own
#: `library_query_invalid`.
LIBRARY_REFUSALS = {
    "card_not_found": ("card_not_found", 404),
    "card_banned": ("card_banned", 409),
    "plan_not_found": ("plan_not_found", 404),
    "plan_invalid": ("plan_invalid", 409),
    "import_invalid": ("import_invalid", 400),
    "search_invalid": ("library_query_invalid", 400),
}
#: A search result's buildability under the Challenge's contract (S2's focus
#: ranking): a plan input, or a capability request candidate instead.
BUILDABILITY_FLAGS = ("plan_input", "capability_request_candidate")
_CARD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
LIBRARY_QUERY_MAX = 200
CARD_LIMIT_DEFAULT, CARD_LIMIT_MAX = 10, 50
IMPORT_TITLE_MAX, IMPORT_TEXT_MAX = 300, 20000
#: When a queued import is read: S2's hunt reads the queue before it fetches,
#: and S3 runs a hunt only in a RESEARCH or FULL launch that asks for one.
IMPORT_READ_AT = (
    "the next Graphite launch that hunts (RESEARCH or FULL with hunt set): "
    "its Reader extracts a card from it on your model and budget"
)
LIBRARY_LIST_MAX = 200


def _unsafe(text):
    """Whether `text` holds a control character (newline, tab and carriage
    return aside) or a bidirectional override: the campaign view's own
    rule for journal text (`campaign_view._UNSAFE`)."""
    from scripts.dev.miner_launchpad.campaign_view import _UNSAFE

    return _UNSAFE.search(text.replace("\r", "")) is not None


def _bounded(value, depth=0):
    """A JSON value copied with every string, list and object bounded."""
    if type(value) is str:
        return value[:20000]
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    if depth >= 3:
        return None
    if type(value) in (list, tuple):
        return [_bounded(item, depth + 1) for item in value[:32]]
    if type(value) is dict:
        return {
            str(key)[:64]: _bounded(item, depth + 1)
            for key, item in list(value.items())[:32]
        }
    return None


def _protected_card(card):
    """Whether a card names protected material (Graphite's own filter,
    `agent_campaign.graphite.tools.protected`), checked again at this door:
    the library filters at write and serve; a door that serves cards does not
    rely on that alone."""
    from carbon.agent_campaign.graphite.tools import protected

    return card.get("withheld_protected") is True or protected(
        {k: card.get(k) for k in CARD_FIELDS if k in card}
    )


def served_card(card, curation, *, ranked=False):
    """A card as a door serves it, or None for one it never serves: the
    card's own fields, its origin and UNCHECKED status, whether the miner
    pinned it, and - from a search - its rank for the Challenge with the
    reasons and whether it is buildable under the Challenge's contract
    (`plan_input`) or a capability request candidate instead (S2's focus
    ranking). A banned card, a card of an unknown origin and a card naming
    protected material are never served."""
    if type(card) is not dict or type(card.get("card_id")) is not str:
        return None
    if card["card_id"] in curation["bans"] or card.get("origin") not in CARD_ORIGINS:
        return None
    if _protected_card(card):
        return None
    served = {k: _bounded(card[k]) for k in CARD_FIELDS if k in card}
    served["origin"] = card["origin"]
    served["check_status"] = UNCHECKED
    served["pinned"] = card["card_id"] in curation["pins"]
    if ranked:
        score = card.get("score")
        served["score"] = score if _number(score) else None
        reasons = card.get("reasons")
        served["reasons"] = [
            r[:300]
            for r in (reasons if type(reasons) is list else [])
            if type(r) is str
        ][:8]
        for flag in BUILDABILITY_FLAGS:
            served[flag] = card.get(flag) if type(card.get(flag)) is bool else None
    return served


def _pending_import(item):
    """An import waiting for the Reader, as the library lists it: its id,
    title and size, never its text."""
    if type(item) is not dict:
        return None
    identity = item.get("import_id", item.get("id"))
    text = item.get("text")
    # S2 lists an import's size as `chars`; its text is never listed.
    characters = (
        len(text) if type(text) is str else item.get("chars", item.get("characters"))
    )
    return {
        "import_id": str(identity)[:128] if identity is not None else None,
        "title": (
            item["title"][:IMPORT_TITLE_MAX] if type(item.get("title")) is str else None
        ),
        "characters": characters if type(characters) is int else None,
        "origin": "miner_import",
    }


#: When a plan was saved, as S2's library records it (UTC, to the second).
_SAVED_AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")


def _saved_at(value):
    """A plan's `created_at`: the library's UTC timestamp text, or a number
    of seconds; anything else is None."""
    if type(value) is str and _SAVED_AT.fullmatch(value):
        return value
    return value if _number(value) else None


def _plan_entry(item):
    """A plan as the list shows it: {digest, created_by, parent, created_at}."""
    if type(item) is not dict or type(item.get("digest")) is not str:
        return None
    created_by = item.get("created_by")
    return {
        "digest": item["digest"][:128],
        "created_by": created_by if created_by in ("planner", "miner") else None,
        "parent": item["parent"][:128] if type(item.get("parent")) is str else None,
        "created_at": _saved_at(item.get("created_at")),
    }


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
    # A plan edit's document counts by value too (S4).
    for name in ("strategy", "plan_document"):
        if type(fields.get(name)) is str:
            try:
                fields[name] = json.loads(fields[name])
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
    #: Graphite's literature (S4 over S2 and S3): the miner's library at a
    #: root, the shared card pack, and the plan rule. A test replaces them.
    open_library = staticmethod(_open_library)
    shared_pack = staticmethod(_shared_pack)
    validate_plan = staticmethod(_validate_plan)

    def __init__(
        self,
        database,
        *,
        configuration=None,
        principal=None,
        registration=None,
        signer=None,
        role=supervision.INLINE,
        commitment_chain=None,
        commitment_signer=None,
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
        #: The miner's private Graphite library: in the setup root, beside
        #: the runner profile, owner-only. Always an absolute path, as S2's
        #: library requires, even for a profile named relatively
        #: (`--profile ./runner-profile.json`); made absolute, not resolved,
        #: as the capability document names the profile. A host with no
        #: profile file (a fixture) has none until a test names one.
        self.library_root = (
            Path(os.path.abspath(configuration)).parent / LIBRARY_DIRECTORY
            if configuration is not None
            else None
        )
        # Injectable so a test reads a device-free stub chain; the default is
        # the real read against the operator's configured context.
        self.registration = registration or chain_registration
        # The early signer answer, beside the real registration read. A test
        # that stubs the chain stubs this too; the signing itself still needs
        # a real `ExternalSigner`, which nothing here can construct.
        self.signer = signer or (signer_ready if registration is None else None)
        #: The strategy commitment (LAUNCHPAD-ACCEPT-02): `cfg -> chain` and
        #: `cfg -> sign`, each from the profile. A test that stubs the chain
        #: names its own or none; a host with none reads no commitment and
        #: gates no submit (the validator still refuses one it requires).
        self.commitment_chain = commitment_chain or (
            sdk_commitment_chain if registration is None else None
        )
        self.commitment_signer = commitment_signer or (
            signer_commit if registration is None else None
        )
        #: The poster's never-resend records, one per hotkey, beside the
        #: runner database, so every process of this principal shares them.
        self.commitment_dir = Path(database).parent / "commitments"
        self._posters = {}
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
            # A library write's answer (S4), kept with its key so a retry
            # replays it exactly; added in place to an older database. A
            # campaign operation's row leaves it NULL, as before.
            if "result" not in {
                r[1] for r in db.execute("PRAGMA table_info(launchpad_operation_keys)")
            }:
                db.execute(
                    "ALTER TABLE launchpad_operation_keys ADD COLUMN result BLOB"
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
                        and waits_for_its_miner(root),
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
                # Carbon's agent for a new launch: Graphite, which replaced
                # the autonomous agent (OWNER-GRAPHITE-MINER-01).
                "agent": "carbon-graphite",
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
        """The browser's launch: a caller of the shared `launch` operation.

        A body naming no agent still means `autonomous`, as it always has, so
        a launch the browser recorded before Graphite replays under its key;
        a new one is refused `autonomous_agent_replaced`, and the page names
        its agent (OWNER-GRAPHITE-MINER-01)."""
        from scripts.dev.miner_launchpad.operations import perform

        if type(value) is not dict or "profile" not in value:
            raise Rejected("closed_research_launch_required")
        request = {"agent": RETIRED_AGENT, **value, "idempotency_key": key}
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

        A profile that no longer describes what the installer installed
        beside it is never attached: `carbon_updated_rerun_installer`, with
        the step that clears it (`install_refusal`, LP-PROD-W2).
        """
        cfg = validated_profile(private_json(Path(configuration)))
        refused = install_refusal(configuration, cfg)
        if refused is not None:
            raise refused
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
            admitted = SimpleNamespace(
                campaign={**dict(row), "kind": kind}, profile=cfg
            )
            function, args = self._dispatch_target(
                operation, admitted, json.loads(item["params"])
            )
            with self.lock:
                previous = self.threads.get(identity)
                if previous is not None and previous.is_alive():
                    raise Rejected("campaign_busy", 409)
                thread = threading.Thread(
                    target=self._tracked,
                    args=(item, function, *args),
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
        # Graphite's fields, by shape, before anything is digested: a value
        # no request may carry (a NaN share) is refused by name, never
        # failed on (S4). Deterministic, so a recorded request passes again.
        graphite_launch(request)
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
            # After the replay lookup, so a launch recorded under the retired
            # agent still replays; a new one is refused before the chain is
            # read (OWNER-GRAPHITE-MINER-01).
            if request["agent"] == RETIRED_AGENT:
                raise Rejected("autonomous_agent_replaced", 409)
            # Refused here, before the registration read, as well as in the
            # body: a choice that cannot run never reaches the chain.
            self._current(cfg)
            challenge = self._challenge(request, cfg["runtime"])
            self._launch_choice(cfg, request, challenge)
            self._graphite_choice(request, challenge)
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
        the campaign it was started on, as it stands now. A keyed library
        write: its own answer, as it was given. The same key with a different
        request is a conflict, never a second dispatch or write."""
        from scripts.dev.miner_launchpad.operations import LIBRARY_WRITES

        if "idempotency_key" not in request:
            return None
        key = _valid_key(request["idempotency_key"])
        if cfg["principal"] != self.principal:
            raise Rejected("research_profile_mismatch", 409)
        with self.db() as db:
            row = self._recorded_row(db, key, operation, request)
        if row is None:
            return None
        if operation in LIBRARY_WRITES:
            return self._recorded_answer(row)
        return self.get(row["campaign"])

    def _recorded_operation(self, db, key, operation, request):
        """The campaign a matching earlier acceptance of `key` started work
        on, or None when the key is unused. Raises the conflict otherwise."""
        row = self._recorded_row(db, key, operation, request)
        return None if row is None else row["campaign"]

    def _recorded_row(self, db, key, operation, request):
        """The matching earlier acceptance of `key`, or None when the key is
        unused; raises the conflict otherwise. A library write names no
        campaign, and is recorded under the empty one."""
        row = db.execute(
            "SELECT operation,campaign,request_digest,result FROM launchpad_operation_keys WHERE principal=? AND request_key=?",
            (self.principal, key),
        ).fetchone()
        if row is None:
            return None
        if (row["operation"], row["campaign"], row["request_digest"]) != (
            operation,
            request.get("campaign", ""),
            _operation_digest(operation, request),
        ):
            raise Rejected("operation_replay_conflict", 409)
        return row

    @staticmethod
    def _recorded_answer(row):
        """A library write's recorded answer. One claimed by a write that has
        not finished (another process, this instant) is not answered as
        done: `operation_not_completed`, and the retry replays it later."""
        if row["result"] is None:
            raise Rejected("operation_not_completed", 409)
        return json.loads(row["result"])

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
        anything is created. None when the launch chose neither: the pinned
        provider and model, whose output cap the campaign's own builder
        chooses (the model's own maximum, OWNER-LAUNCHPAD-PROD-02)."""
        from carbon.development_session.model_provider import (
            ADAPTERS,
            OUTPUT_DEFAULT_V2,
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
            and request.get("agent") in MODEL_AGENTS
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
            if request["agent"] not in MODEL_AGENTS:
                # No agent calls a model; a choice nothing uses is refused.
                # The code keeps its historical name.
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
                # A launch makes a new plan: an unset output cap is the
                # model's own maximum (OWNER-LAUNCHPAD-PROD-02), as the
                # campaign's own builder will choose it.
                selection = (
                    setup_selection(
                        cfg, settings=settings, output_default=OUTPUT_DEFAULT_V2
                    )
                    if same_as_setup
                    else select(
                        provider_id=provider,
                        model_id=model,
                        credential={"kind": "file", "reference": path},
                        settings=settings,
                        output_default=OUTPUT_DEFAULT_V2,
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

    def _graphite_choice(self, request, challenge, *, admitted=None):
        """Graphite's launch choice (`graphite_launch`), checked against what
        it needs to run, or None for any other agent. Refused by name before
        anything is created: a Challenge without a registered campaign
        (`graphite_not_offered_for_challenge`), a missing or changed shared
        card pack (`literature_pack_missing`), a plan not in the miner's
        library (`plan_not_found`), a plan for another Challenge or one the
        plan rule refuses (`plan_invalid`) - what S3's preparation would
        otherwise refuse only after the campaign was created.

        `admitted` is what a launch record kept (`GRAPHITE_ADMISSION`), for a
        launch carried out where it was not received: the curation digest it
        captured is kept, never read again, and its plan's validity is not
        re-judged against pins and bans changed since. Otherwise the miner's
        current curation digest is captured now, at admission (S4)."""
        choice = graphite_launch(request)
        if choice is None:
            return None
        if not graphite_offered(challenge):
            raise Rejected("graphite_not_offered_for_challenge", 409)
        try:
            self.shared_pack()
        except Rejected:
            raise
        except Exception:  # noqa: BLE001 - absent, unreadable or changed
            raise Rejected("literature_pack_missing", 409) from None
        library = self._library()
        if admitted is None:
            curation = self._library_call(library.curation)
            digest_value = curation.get("digest") if type(curation) is dict else None
            if type(digest_value) is not str:
                raise Rejected("library_unavailable", 409)
        else:
            curation, digest_value = None, admitted.get("curation_digest")
            if type(digest_value) is not str:
                raise Rejected("launch_record_differs", 409)
        if (
            curation is not None
            and choice["plan"] is None
            and len(curation.get("pins") or ()) > MAX_PINS
        ):
            # A Planner that runs first must name every pin in its plan, and
            # a plan names at most MAX_PINS: S3 refuses this launch before it
            # freezes, so admission refuses it before it is created.
            raise Rejected("too_many_pins", 409)
        if choice["plan"] is not None:
            plan = self._plan(library, choice["plan"])
            planned_for = plan.get("challenge")
            if (
                type(planned_for) is not dict
                or planned_for.get("id") != challenge["id"]
            ):
                # S3 builds BUILD on a plan of the launch's own Challenge only.
                raise stepped(
                    "plan_invalid",
                    supervision.NEXT_ACTIONS["plan_invalid"]
                    + " Reason: plan_for_another_challenge.",
                )
            if curation is not None:
                self._check_plan(plan, library, curation)
        return {**choice, "curation_digest": digest_value}

    def launch_admitted(self, admitted, request):
        """Record and dispatch an admitted launch."""
        from carbon.development_session.product_campaign import (
            ProductLaunch,
            miner_budget,
        )

        if request["agent"] == RETIRED_AGENT:
            # The replay gate refuses it first; never admitted here either.
            raise Rejected("autonomous_agent_replaced", 409)
        cfg, miner = admitted.profile, admitted.miner
        task = guidance.configured(cfg)
        budget = miner_budget(request.get("budget"))
        challenge = self._challenge(request, cfg["runtime"])
        choice = self._launch_choice(cfg, request, challenge)
        graphite = self._graphite_choice(request, challenge)
        if graphite is not None:
            choice = replace(choice or LaunchChoice(), graphite=graphite)
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
                        # A Graphite launch keeps what admission captured
                        # beside it (its curation digest), under a key that is
                        # never a request field (S4).
                        canonical(
                            {
                                **{
                                    k: v
                                    for k, v in request.items()
                                    if k != "idempotency_key"
                                },
                                **(
                                    {
                                        GRAPHITE_ADMISSION: {
                                            "curation_digest": graphite[
                                                "curation_digest"
                                            ]
                                        }
                                    }
                                    if graphite is not None
                                    else {}
                                ),
                            }
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
            recorded = json.loads(stored)
            # What admission captured is beside the request, never part of
            # its identity (S4).
            captured = recorded.pop(GRAPHITE_ADMISSION, None)
            request = {**recorded, "idempotency_key": row["request_key"]}
            run_id, request_digest, config_pin = self._launch_identity(cfg, request)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise Rejected("launch_record_differs", 409) from None
        if (run_id, request_digest) != (row["id"], row["request_digest"]):
            raise Rejected("launch_record_differs", 409)
        if config_pin != row["config_digest"]:
            # Never prepared: the launch binds the whole profile its miner
            # reviewed, so a changed one cannot carry it out (D10).
            raise Rejected("profile_changed_since_launch", 409)
        challenge = self._challenge(request, cfg["runtime"])
        choice = self._launch_choice(cfg, request, challenge)
        if request.get("agent") == GRAPHITE:
            if type(captured) is not dict:
                raise Rejected("launch_record_differs", 409)
            graphite = self._graphite_choice(request, challenge, admitted=captured)
            choice = replace(choice or LaunchChoice(), graphite=graphite)
        elif captured is not None:
            raise Rejected("launch_record_differs", 409)
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
            # Graphite replaced the autonomous agent for new launches
            # (OWNER-GRAPHITE-MINER-01): it is not offered, and a launch
            # naming it is refused `autonomous_agent_replaced`.
            "agents": [
                {"value": "none", "availability": "available"},
                {
                    "value": GRAPHITE,
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
            "graphite": graphite_options(cfg),
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

    # -- Graphite's library and plans (OWNER-GRAPHITE-MINER-01, S4): the
    # -- shared pack under the miner's private library, read and curated
    # -- through the operations table. Nothing here starts work.

    def _graphite_args(self, args, root, product=None):
        """Where a Graphite campaign's driver finds the miner's library, on
        every run, resume and operation: `args.graphite_library`. Never
        frozen (a path is private and may move); only a Graphite campaign's
        args carry it, so every other campaign's args are as they were."""
        agent = (
            getattr(product, "agent", None)
            if product is not None
            else product_agent(root)
        )
        if agent == GRAPHITE:
            args.graphite_library = self.library_root

    def _library(self):
        """The miner's library, or `library_unavailable` (no setup root)."""
        if self.library_root is None:
            raise Rejected("library_unavailable", 409)
        try:
            return self.open_library(Path(self.library_root))
        except Rejected:
            raise
        except Exception:  # noqa: BLE001 - a closed code, never a path
            raise Rejected("library_unavailable", 409) from None

    @staticmethod
    def _library_call(function, *args, **kwargs):
        """One library call. S2's typed refusal (`LibraryError`, a ValueError
        carrying a closed `.code`) is answered by its own code, for the codes
        a door names (`LIBRARY_REFUSALS`); any other failure is
        `library_unavailable`, never its text. A KeyError or LookupError is
        left for the caller to name."""
        try:
            return function(*args, **kwargs)
        except (Rejected, KeyError, LookupError):
            raise
        except Exception as failure:  # noqa: BLE001 - a closed code, never a path
            refusal = LIBRARY_REFUSALS.get(getattr(failure, "code", None))
            if isinstance(failure, ValueError) and refusal is not None:
                raise Rejected(*refusal) from None
            raise Rejected("library_unavailable", 409) from None

    def _plan(self, library, plan_digest):
        """The plan at `plan_digest` in the miner's library, or
        `plan_not_found`."""
        if type(plan_digest) is not str or not _PLAN_DIGEST.fullmatch(plan_digest):
            raise Rejected("plan_not_found", 404)
        try:
            plan = self._library_call(library.plan, plan_digest)
        except (KeyError, LookupError):
            raise Rejected("plan_not_found", 404) from None
        if type(plan) is not dict:
            raise Rejected("plan_not_found", 404)
        return plan

    def _check_plan(self, plan, library, curation):
        """S3's plan rule, or `plan_invalid` with the rule's own closed reason
        in its next step when it gives one."""
        try:
            ok, refused = self.validate_plan(plan, library, curation)
        except Rejected:
            raise
        except Exception:  # noqa: BLE001 - an unreadable plan is not valid
            ok, refused = False, None
        if ok is True:
            return
        reason = (refused or {}).get("code") if type(refused) is dict else None
        if type(reason) is str and supervision._CODE.fullmatch(reason):
            raise stepped(
                "plan_invalid",
                supervision.NEXT_ACTIONS["plan_invalid"] + " Reason: " + reason + ".",
            )
        raise Rejected("plan_invalid", 409)

    @staticmethod
    def _card_id(value):
        if type(value) is not str or not _CARD_ID.fullmatch(value):
            raise Rejected("card_not_found", 404)
        return value

    def _curation(self, library):
        value = self._library_call(library.curation)
        if (
            type(value) is not dict
            or type(value.get("digest")) is not str
            or type(value.get("pins")) not in (list, tuple)
            or type(value.get("bans")) not in (list, tuple)
        ):
            raise Rejected("library_unavailable", 409)
        return {
            "pins": [p for p in value["pins"] if type(p) is str],
            "bans": [b for b in value["bans"] if type(b) is str],
            "digest": value["digest"],
        }

    def _library_challenge(self, request):
        """The Challenge a search ranks for, resolved exactly: its id, and
        the version sent or the registry's registered one."""
        from carbon.challenge_registry import ResolutionError, resolve
        from carbon.challenge_registry.campaigns import challenge_ref

        identity = request["challenge"]
        if type(identity) is not str:
            raise Rejected("challenge_unknown", 409)
        version = request.get("challenge_version")
        if version is None:
            version = challenge_ref(identity)["version"]
        try:
            resolve(identity, version, "cpu_research")
        except ResolutionError as refused:
            raise Rejected(refused.code, 409) from None
        return {"id": identity, "version": version}

    def library_search_admitted(self, admitted, request):
        query = request["query"]
        if (
            type(query) is not str
            or not 1 <= len(query.strip()) <= LIBRARY_QUERY_MAX
            or len(query) > LIBRARY_QUERY_MAX
            or _unsafe(query)
        ):
            raise Rejected("library_query_invalid")
        limit = request.get("card_limit", CARD_LIMIT_DEFAULT)
        if type(limit) is not int or not 1 <= limit <= CARD_LIMIT_MAX:
            raise Rejected("card_limit_out_of_bounds")
        challenge = self._library_challenge(request)
        library = self._library()
        curation = self._curation(library)
        found = self._library_call(
            library.search,
            query.strip(),
            challenge=challenge,
            limit=limit,
            bans=tuple(curation["bans"]),
            pins=tuple(curation["pins"]),
        )
        cards = [
            served
            for served in (
                served_card(card, curation, ranked=True)
                for card in (found if type(found) is list else [])
            )
            if served is not None
        ][:limit]
        return {
            "schema": LIBRARY_SEARCH_SCHEMA,
            "query": query.strip(),
            "challenge": challenge,
            "cards": cards,
            "curation_digest": curation["digest"],
            **CARD_NOTICE,
        }

    def library_card_admitted(self, admitted, request):
        card_id = self._card_id(request["card_id"])
        library = self._library()
        curation = self._curation(library)
        if card_id in curation["bans"]:
            raise Rejected("card_banned", 409)
        try:
            card = self._library_call(library.card, card_id)
        except (KeyError, LookupError):
            raise Rejected("card_not_found", 404) from None
        served = served_card(card, curation)
        if served is None or served["card_id"] != card_id:
            # Not a card the miner may be served (protected material, an
            # unknown origin): as if it did not exist.
            raise Rejected("card_not_found", 404)
        return {"schema": LIBRARY_CARD_SCHEMA, "card": served, **CARD_NOTICE}

    def library_list_admitted(self, admitted, request):
        library = self._library()
        curation = self._curation(library)
        try:
            pack = self.shared_pack()
            shared = {
                "available": True,
                "digest": str(pack.digest)[:128],
                "cards": len(pack.cards),
                "check_status": UNCHECKED,
            }
        except Exception:  # noqa: BLE001 - said by its closed code
            shared = {"available": False, "code": "literature_pack_missing"}
        pending = self._library_call(library.pending_imports)
        return {
            "schema": LIBRARY_LIST_SCHEMA,
            "shared_pack": shared,
            "private_snapshot": str(self._library_call(library.snapshot))[:128],
            "curation": curation,
            "pending_imports": [
                entry
                for entry in (
                    _pending_import(item)
                    for item in (pending if type(pending) is list else [])
                )
                if entry is not None
            ][:LIBRARY_LIST_MAX],
            "plans": self._plans(library),
            "where": "your own machine, owner-only; nothing is uploaded",
            **CARD_NOTICE,
        }

    def _plans(self, library):
        """The miner's plans, newest first (S2's library lists them oldest
        first, in the order it saved them)."""
        found = self._library_call(library.plans)
        return [
            entry
            for entry in (
                _plan_entry(item)
                for item in reversed(found if type(found) is list else [])
            )
            if entry is not None
        ][:LIBRARY_LIST_MAX]

    def plan_list_admitted(self, admitted, request):
        return {"schema": PLAN_LIST_SCHEMA, "plans": self._plans(self._library())}

    def plan_get_admitted(self, admitted, request):
        library = self._library()
        plan = self._plan(library, request["plan"])
        return {
            "schema": PLAN_GET_SCHEMA,
            "digest": request["plan"],
            "plan": json.loads(json.dumps(plan, allow_nan=False)),
            "untrusted": True,
            "shown_as": "untrusted text",
        }

    def _library_write(self, operation, request, write):
        """One library write, under the replay gate: a keyed write claims
        its key before it writes and keeps its answer with it, so a retry
        replays that answer and a different request under the key is a
        conflict. An unkeyed write is simply never a replay. Starts no work.

        The host's lock is held only while the key is claimed and while its
        answer is kept, never across the write itself: S2's library
        serialises its own writes under its file lock, and a write may read
        the whole card pack, which must not hold up launches."""
        key = request.get("idempotency_key")
        if key is None:
            return write()
        key = _valid_key(key)
        with self.lock, self.db() as db:
            row = self._recorded_row(db, key, operation, request)
            if row is not None:
                return self._recorded_answer(row)
            try:
                db.execute(
                    "INSERT INTO launchpad_operation_keys (principal,request_key,operation,campaign,request_digest,created,result) VALUES(?,?,?,?,?,?,NULL)",
                    (
                        self.principal,
                        key,
                        operation,
                        "",
                        _operation_digest(operation, request),
                        time.time(),
                    ),
                )
            except sqlite3.IntegrityError:
                raise Rejected("operation_not_completed", 409) from None
        try:
            result = write()
        except BaseException:
            with self.lock, self.db() as db:
                db.execute(
                    "DELETE FROM launchpad_operation_keys WHERE principal=? AND request_key=? AND result IS NULL",
                    (self.principal, key),
                )
            raise
        with self.lock, self.db() as db:
            db.execute(
                "UPDATE launchpad_operation_keys SET result=? WHERE principal=? AND request_key=?",
                (canonical(result), self.principal, key),
            )
        return result

    def _curate(self, operation, request):
        card_id = self._card_id(request["card_id"])

        def write():
            library = self._library()
            curation = self._curation(library)
            if operation in ("library_pin", "library_ban"):
                # Only a card the library holds can be pinned or banned.
                if operation == "library_pin" and card_id in curation["bans"]:
                    raise Rejected("card_banned", 409)
                if card_id not in curation["bans"]:
                    try:
                        self._library_call(library.card, card_id)
                    except (KeyError, LookupError):
                        raise Rejected("card_not_found", 404) from None
            action = getattr(library, operation.removeprefix("library_"))
            try:
                changed = self._library_call(action, card_id)
            except (KeyError, LookupError):
                raise Rejected("card_not_found", 404) from None
            after = self._curation(library)
            return {
                "schema": LIBRARY_CURATION_SCHEMA,
                "operation": operation,
                "card_id": card_id,
                "curation_digest": (
                    changed if type(changed) is str else after["digest"]
                ),
                "curation": after,
                "applies_to": (
                    "Graphite launches from now on; a campaign keeps the "
                    "curation frozen at its launch"
                ),
            }

        return self._library_write(operation, request, write)

    def library_pin_admitted(self, admitted, request):
        return self._curate("library_pin", request)

    def library_unpin_admitted(self, admitted, request):
        return self._curate("library_unpin", request)

    def library_ban_admitted(self, admitted, request):
        return self._curate("library_ban", request)

    def library_unban_admitted(self, admitted, request):
        return self._curate("library_unban", request)

    def library_import_admitted(self, admitted, request):
        title, text = request["title"], request["text"]
        if (
            type(title) is not str
            or not 1 <= len(title.strip()) <= IMPORT_TITLE_MAX
            or len(title) > IMPORT_TITLE_MAX
            or _unsafe(title)
            or type(text) is not str
            or not 1 <= len(text.strip())
            or len(text) > IMPORT_TEXT_MAX
            or _unsafe(text)
        ):
            raise Rejected("import_invalid")

        def write():
            library = self._library()
            # S2 refuses a text it will not queue `import_invalid`
            # (`LibraryError`), which `_library_call` answers by name.
            identity = self._library_call(library.import_text, title.strip(), text)
            return {
                "schema": LIBRARY_IMPORT_SCHEMA,
                "import_id": str(identity)[:128],
                "queued": True,
                "origin": "miner_import",
                "check_status": UNCHECKED,
                "read_at": IMPORT_READ_AT,
            }

        return self._library_write("library_import", request, write)

    def plan_edit_admitted(self, admitted, request):
        from scripts.dev.miner_launchpad.operations import plan_document_value

        document = plan_document_value(request)
        if document.get("schema") != PLAN_SCHEMA:
            raise Rejected("plan_invalid", 409)

        def write():
            library = self._library()
            parent = document.get("parent")
            if parent is not None:
                # An edit names the plan it edits, which must be the miner's.
                self._plan(library, parent)
            plan = {**document, "created_by": "miner"}
            self._check_plan(plan, library, self._curation(library))
            saved = self._library_call(library.save_plan, plan)
            if type(saved) is not str:
                raise Rejected("library_unavailable", 409)
            return {
                "schema": PLAN_EDIT_SCHEMA,
                "digest": saved,
                "parent": parent,
                "created_by": "miner",
                "launch_with": {
                    "agent": GRAPHITE,
                    "graphite_mode": "BUILD",
                    "plan": saved,
                },
            }

        return self._library_write("plan_edit", request, write)

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
        self._require_commitment(admitted)
        return self._background(admitted, "submit", {}, "SUBMITTING", request)

    def _require_commitment(self, admitted):
        """`commitment_required` now, before anything is signed or sent, when
        the frozen candidate's first send through its Challenge's validator
        intake needs its commitment on chain and the hotkey's commitment at
        the finalized head is another (LAUNCHPAD-ACCEPT-02). Read-only: the
        hotkey's tempo window is not spent. `commitment_reader_unavailable`
        when that read fails: nothing is sent unread (fail closed). A host
        that reads no chain (a fixture) gates nothing here; the campaign's
        own submit asks the same gate again (`battery.campaign._committed`)."""
        from carbon.chain import commitment_poster as cp
        from carbon.challenge_registry.campaigns import campaign_for_manifest
        from scripts.dev.miner_launchpad.commitment import frozen_candidate

        if self.commitment_chain is None:
            return
        root = Path(admitted.campaign["root"])
        epoch, record, manifest = frozen_candidate(root)
        campaign = campaign_for_manifest(manifest)
        if campaign.commitment is None or campaign.commitment_due is None:
            return
        if not campaign.commitment_due(
            campaign_args(admitted.profile, root=root), root, epoch
        ):
            return
        try:
            digest = campaign.commitment(record, manifest)
        except (ValueError, KeyError, TypeError):
            raise Rejected("commitment_digest_unavailable", 409) from None
        try:
            poster = self._poster(admitted.profile)
        except Exception:  # noqa: BLE001 - its closed code, never its text
            raise Rejected(cp.UNREADABLE, 503) from None
        code = cp.check(poster.chain, poster.hotkey, digest)
        if code is not None:
            raise Rejected(code, 503 if code == cp.UNREADABLE else 409)

    # -- The strategy commitment (OWNER-COMMITMENT-POSTER-01, LAUNCHPAD-ACCEPT-02)

    def _poster(self, cfg):
        """The one poster for the profile's hotkey in this process, so one
        post at a time per hotkey; None on a host that reads no chain."""
        from carbon.chain.commitment_poster import CommitmentPoster

        if self.commitment_chain is None:
            return None
        hotkey = miner_hotkey(cfg)
        with self.lock:
            poster = self._posters.get(hotkey)
            if poster is None:
                poster = CommitmentPoster(
                    hotkey=hotkey,
                    chain=self.commitment_chain(cfg),
                    sign=self.commitment_signer(cfg),
                    state_dir=self.commitment_dir,
                )
                self._posters[hotkey] = poster
            return poster

    def _campaign_gate(self, cfg):
        """The commitment gate a campaign's submit asks before its first send
        (`battery.campaign._committed`): None on a host that reads no chain;
        one that refuses every send when the profile's chain side cannot be
        built (fail closed)."""
        from carbon.chain.commitment_poster import CommitmentGate

        if self.commitment_chain is None:
            return None
        try:
            return CommitmentGate(self._poster(cfg))
        except Exception:  # noqa: BLE001 - refused by code, never by text
            return _UnreadableGate()

    def _candidate_digest(self, root):
        """`(epoch, digest)`: the open epoch's frozen candidate and the digest
        its Challenge commits (`ChallengeCampaign.commitment`, L1)."""
        from carbon.challenge_registry.campaigns import campaign_for_manifest
        from scripts.dev.miner_launchpad.commitment import frozen_candidate

        root = Path(root)
        path = root / "campaign-manifest.json"
        if not path.exists():
            raise Rejected("campaign_not_prepared", 409)
        try:
            campaign = campaign_for_manifest(json.loads(path.read_bytes()))
        except Exception:  # noqa: BLE001 - a retired or unknown Challenge
            raise Rejected("commitment_not_offered", 409) from None
        if campaign.commitment is None:
            raise Rejected("commitment_not_offered", 409)
        epoch, record, manifest = frozen_candidate(root)
        try:
            return epoch, campaign.commitment(record, manifest)
        except (ValueError, KeyError, TypeError):
            raise Rejected("commitment_digest_unavailable", 409) from None

    def _queued_digests(self, identity):
        """The frozen candidates' digests of this principal's other campaigns
        with a submit admitted and not done: what a new commitment would
        strand (L2)."""
        with self.db() as db:
            rows = db.execute(
                "SELECT DISTINCT c.root FROM launchpad_dispatch d JOIN launchpad_campaigns c ON c.id=d.campaign WHERE d.principal=? AND d.state!=? AND d.operation='submit' AND d.campaign!=?",
                (self.principal, supervision.DONE, identity),
            ).fetchall()
        found = []
        for (root,) in rows:
            with contextlib.suppress(Exception):
                found.append(self._candidate_digest(root)[1])
        return found

    def commit_admitted(self, admitted, request):
        """Commit the frozen candidate's digest on chain (LAUNCHPAD-ACCEPT-02).

        The digest is the candidate's own (L1); no request field names one.
        Answered at once with the plan (L2: the digest, the hotkey's current
        commitment and its block, the replacement warning and any queued
        submit it would strand), read at the finalized head. The same digest
        already on chain is not posted again (L3) unless `recommit`. The post
        itself runs on the supervisor's queue, because the miner's signer
        waits on its own terminal: observe shows `human_action_required:
        confirm_commitment` until the miner types there, then what reads back
        at finality (`commitment.view`). No door can confirm it (D10).
        """
        from carbon.chain import commitment_poster as cp

        recommit = request.get("recommit", False)
        if type(recommit) is not bool:
            raise Rejected("recommit_boolean_required")
        self._admissible(admitted)
        identity = admitted.campaign["id"]
        root = Path(admitted.campaign["root"])
        epoch, digest = self._candidate_digest(root)
        try:
            poster = self._poster(admitted.profile)
        except Exception:  # noqa: BLE001 - its closed code, never its text
            raise Rejected(cp.UNREADABLE, 503) from None
        if poster is None:
            raise Rejected(cp.UNREADABLE, 503)
        plan = poster.plan(digest, queued=self._queued_digests(identity))
        if "code" in plan:
            raise Rejected(plan["code"], 503 if plan["code"] == cp.UNREADABLE else 409)
        fields = {
            "hotkey": poster.hotkey,
            "digest": digest,
            "epoch": epoch,
            "recommit": recommit,
            "by": "miner",
            "plan": plan,
            "at": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        if not plan["needed"] and not recommit:
            # L3: already the hotkey's commitment; nothing is asked or sent.
            cp.write_request(root, **fields, outcome=cp.PostCode.ALREADY_ON_CHAIN.value)
            return self.get(identity)
        path = root / cp.REQUEST_FILE
        previous = path.read_bytes() if path.exists() else None
        cp.write_request(root, **fields)
        try:
            return self._background(
                admitted,
                "commit",
                {"digest": digest, "recommit": recommit},
                None,
                request,
                probe_lock=False,
            )
        except BaseException:
            # Not admitted: the campaign's earlier request stands.
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
            raise

    def _commit_thread(self, admitted, params):
        """One commitment post, on its own thread. The poster's record is its
        outcome, which observe shows; a post that did not commit is also the
        campaign's `last_refusal`, by its closed code. Never resent."""
        from carbon.chain import commitment_poster as cp

        identity = admitted.campaign["id"]
        try:
            poster = self._poster(admitted.profile)
            if poster is None:
                raise Rejected(cp.UNREADABLE, 503)
            result = poster.post(params["digest"], recommit=params["recommit"] is True)
        except Rejected as refused:
            self._refused(identity, refused.code, "commit")
            return
        except Exception as exc:  # noqa: BLE001 - its closed code, never its text
            self._refused(
                identity, exception_code(exc) or "operation_refused", "commit"
            )
            return
        if result["code"] not in cp.DONE:
            self._refused(identity, cp.closed_code(result["code"]), "commit")

    def _dispatch_target(self, operation, admitted, params):
        """The thread body for one admitted miner operation, and its arguments."""
        if operation == "commit":
            return self._commit_thread, (admitted, params)
        return self._operation_thread, (admitted, self._work(operation, params))

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

    def _background(self, admitted, operation, params, state, request, probe_lock=True):
        """Run a long miner operation on its own thread; observe reports it.

        A keyed request is claimed in the same critical section that starts
        the thread: a concurrent or later retry under the key finds the claim
        and replays, and a refused request (busy) records nothing. A host
        that does not supervise queues the operation instead, for the
        supervisor to start (LP-PROD-C).

        `state` None leaves the campaign's state as it is; `probe_lock` False
        is for an operation that never takes the campaign's ownership lock (a
        commit touches no campaign record but its own request).
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
            if probe_lock:
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
                if state is not None:
                    self._state(identity, state)
                if self.role == supervision.SUPERVISOR:
                    self.delegated.add(identity)
            else:
                item = self._record(
                    identity, operation, params, admitted.profile, supervision.RUNNING
                )
                function, args = self._dispatch_target(operation, admitted, params)
                thread = threading.Thread(
                    target=self._tracked,
                    args=(item, function, *args),
                    daemon=True,
                )
                self.threads[identity] = thread
                self.thread_operations[identity] = operation
                if state is not None:
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
            self._graphite_args(args, root)
            args.commitment_gate = self._campaign_gate(cfg)

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
                self._graphite_args(args, root, product)
                # Graphite's selection asks for its own commitment (D10).
                args.commitment_gate = self._campaign_gate(cfg)
                outcome = interrupted = None
                try:
                    outcome = asyncio.run(execute(args, ledger=ledger))
                except Exception as exc:  # noqa: BLE001 - kept private
                    interrupted = exc
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
                    # A campaign waiting for its miner - agent-less, or
                    # holding a candidate its agent selected and the
                    # validator did not evaluate (`waits_for_its_miner`) - is
                    # ready, not interrupted, unless a pause or stop was
                    # asked meanwhile, which it then settles to. A run that
                    # raised keeps its interruption: only the agent-less
                    # rule, as before, applies to it (LP-PROD-FIX-01).
                    ready = (
                        not completed
                        and (
                            waits_for_its_miner(root)
                            if interrupted is None
                            else product_agent(root) == "none"
                        )
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
            outcome = self._settle_if_idle(ledger, control, root, reconciling=True)
            if outcome is False:
                raise Rejected("campaign_busy", 409)
            if isinstance(outcome, Rejected):
                raise outcome
            refused = outcome.get("refused") if isinstance(outcome, dict) else None
            if refused:
                # A call Carbon will not settle stays unresolved and the
                # campaign awaits reconciliation: its closed code, with the
                # settlement's own next step (LP-PROD-W2). What was settled
                # meanwhile is booked and shown in the campaign's readback.
                raise stepped(refused[0]["code"], refused[0]["next_step"])
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

    def _settle_if_idle(self, ledger, control, root, *, reconciling=False):
        """Settle the campaign now, with the real cleanup check, if no live
        process holds its ownership lock: PAUSED or STOPPED as asked, or
        RECONCILIATION_REQUIRED while work may be outstanding; reconciled with
        nothing outstanding, a campaign waiting for its miner
        (`waits_for_its_miner`) is READY again.
        False when a live holder (a run, an operation, an attached agent or
        the page's tools) has it; that holder settles it. A finished campaign
        is left as it is.

        `reconciling` is the miner's Reconcile. It first settles every model
        call whose outcome is unknown (`_settle_model_calls`), here, under the
        owner lock and the generation just taken (observed RECONCILING), so
        LP-PROD-A's reconcile fence admits it; it returns that settlement's
        report (or the `Rejected` it ended in) instead of True. Pause, stop
        and recovery never settle a model call."""
        stack = ExitStack()
        try:
            stack.enter_context(owner_lock(root))
        except RuntimeError:
            return False
        settlement = True
        with stack:
            try:
                generation = control.acquire()
            except DispatchStopped:
                return True
            ledger.generation = generation
            if reconciling:
                try:
                    settlement = self._settle_model_calls(ledger)
                except Exception:  # noqa: BLE001 - settled as it stands, by code
                    settlement = Rejected("operation_not_completed", 409)
            completed = (root / "campaign-complete.json").exists()
            control.settled(
                generation,
                completed=completed,
                ready=not completed
                and control.status()["desired"] == "RUN"
                and waits_for_its_miner(root),
                cleanup_verified=self._cleanup(ledger),
            )
        return settlement

    @staticmethod
    def _settle_model_calls(ledger):
        """The reconcile action's settlement of the campaign's model calls
        whose outcome is unknown (LP-PROD-A's `settle_uncertain_calls`,
        through `research_campaign.reconcile_model_calls`): each is booked at
        its full reservation and journalled, and the next resume sends the
        same request under a fresh identity. Nothing is resent here.

        Before LP-PROD-W2 nothing called it: a campaign whose model call's
        outcome was unknown (a timeout, a dropped connection, a 500) stayed
        RECONCILIATION_REQUIRED, because `_cleanup` reconciles worker
        operations only. A product campaign's calls are its manifest owner's
        (`CampaignLedger._reserve`). Its own fences still apply: a call in
        flight (`call_in_flight`) and a holder that is not this reconcile
        (`control_fenced`) are refused, and so is a call whose reported
        charge or usage the ledger cannot book."""
        from carbon.development_session.research_campaign import (
            reconcile_model_calls,
        )

        with ledger.db() as db:
            frozen = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
        # Nothing frozen, nothing dispatched: an empty report.
        owner = json.loads(frozen[0]).get("owner") if frozen is not None else None
        return reconcile_model_calls(ledger, owner=owner)

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
        outcome = _intake_outcome(value["last_refusal"], root)
        if outcome is not None:
            value["last_refusal"]["intake_outcome"] = outcome
        value["in_flight"] = self._in_flight(identity)
        # Only what can succeed: nothing resumes a retired-grant campaign or
        # one on a retired Challenge (`_control`), so neither is offered it.
        value["recovery"] = supervision.recovery_actions(
            value["state"],
            value["in_flight"],
            resumable=kind == "product" and not retired_challenge(root),
        )
        # The strategy commitment, from the campaign's request and the
        # poster's record; no chain read (LAUNCHPAD-ACCEPT-02). Null when none
        # was ever requested.
        from scripts.dev.miner_launchpad.commitment import view as commitment_view

        value["commitment"] = None
        with contextlib.suppress(Exception):
            value["commitment"] = commitment_view(
                root, self.commitment_dir, value["in_flight"]
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
