"""Operator setup for the DEVELOPMENT direct receiver: profile, configuration, start.

    .venv/bin/python -B -m carbon.challenge_validator.receiver_setup challenges
    .venv/bin/python -B -m carbon.challenge_validator.receiver_setup prepare \\
        --installed-state STATE --receiver-state DIR --hotkey SS58 \\
        --challenge ID VERSION \\
        [--pack DIR | --pack-store DIR (--pack-digest sha256:... | --pack-set-key KEY)] \\
        [--port N] [--lifetime-seconds N] [--no-construction-runtimes]
    .venv/bin/python -B -m carbon.challenge_validator.receiver_setup start \\
        --receiver-state DIR [--detach]
    .venv/bin/python -B -m carbon.challenge_validator.receiver_setup service \\
        --receiver-state DIR
    .venv/bin/python -B -m carbon.challenge_validator.receiver_setup status \\
        --receiver-state DIR

Run Python with -B, as `install_validator.sh` does: without it Python writes
`carbon/**/__pycache__` into this checkout, and `prepare` refuses a checkout
with untracked runtime files. `start --detach` runs the receiver as a
`systemd --user` unit, which stops when that user logs out unless linger is on:
`loginctl enable-linger "$USER"` once per host.

`scripts/install_miner.sh` (or `install_validator.sh`) installs the checkout and
the pinned worker and analysis images and records them under STATE. This writes
what the drivers wrote by hand: the receiver's runner profile and its closed
configuration, both private (0600) under DIR, and starts the receiver. It builds
no image, builds no pack and holds no key.

The sealed pack arrives through the answer-key route into the validator's pack
store (`sealed_pack_import`); `--pack-store` and `--pack-digest` take it by its
manifest digest, re-verified at use, instead of an operator-typed directory.

The evaluation pack is an input (`--pack`): a pack's leg minimums come from a
baseline run on the judge image, which a validator host does not produce. The
receiver hotkey is the operator's own validator hotkey (`--hotkey`, its public
ss58 address only): Carbon's network publisher, or a hotkey holding a validator
permit on the subnet, read from the chain now and again at every start. The
receiver listens on 127.0.0.1 only.

`challenges` lists every Challenge version the receiver serves and each
Challenge's current (newest) one. Without `--lifetime-seconds` the receiver
runs until it is stopped; `service` installs it as a `systemd --user` service
that restarts on failure and after a reboot (with linger on). `status` reports
the service, the local intake, the selected exam and the last graded
submission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG_NAME = "receiver.json"
PROFILE_NAME = "runner-profile.json"
DEFAULT_PORT = 8769
#: No lifetime: the receiver is a service and runs until it is stopped (E5). A
#: finite run (the drivers used 7200 s) is a deliberate `--lifetime-seconds`.
DEFAULT_LIFETIME_SECONDS = None
MATERIAL_CACHE_BYTES = 192 * 1024 * 1024


class SetupRefused(RuntimeError):
    """A typed refusal naming the field and the next step; never a path or secret."""

    def __init__(self, code: str, next_step: str):
        super().__init__(f"{code}: {next_step}")
        self.code, self.next_step = code, next_step


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def served() -> tuple:
    """The Challenge versions an operator may serve: every version the
    receiver serves, except the synthetic software fixture."""
    from carbon.challenge_kit.synthetic_linear_field_2d import CHALLENGE

    from .direct_receiver import served_challenges

    return tuple(c for c in served_challenges() if c["id"] != CHALLENGE.challenge_id)


def _version_key(version: str) -> tuple:
    return tuple(int(part) for part in version.split("."))


def current() -> tuple:
    """Each served Challenge's newest version, in the registrations' order."""
    newest = {}
    for challenge in served():
        held = newest.get(challenge["id"])
        if held is None or _version_key(challenge["version"]) > _version_key(held):
            newest[challenge["id"]] = challenge["version"]
    return tuple({"id": key, "version": value} for key, value in newest.items())


def _challenge(challenge_id: str, version: str) -> dict:
    selected = {"id": challenge_id, "version": version}
    if selected not in served():
        raise SetupRefused(
            "challenge_not_registered",
            "name a Challenge version this receiver serves; list them with "
            "`receiver_setup challenges`.",
        )
    return selected


def _require_permit(hotkey: str, network: dict, permits=None) -> None:
    """Carbon's network publisher, or a hotkey with a validator permit now."""
    from carbon.development_session.intake_targets import ADDRESS

    if type(hotkey) is not str or not ADDRESS.fullmatch(hotkey):
        raise SetupRefused(
            "hotkey_invalid", "give your validator hotkey's ss58 address (public)."
        )
    if hotkey == network["publisher_hotkey"]:
        return
    from carbon.chain.models import ChainContext
    from carbon.chain.permits import PermitUnavailable, ValidatorPermitReader

    reader = (
        ValidatorPermitReader(ChainContext(**network["context"]))
        if permits is None
        else permits
    )
    try:
        permit = reader.read(hotkey)
    except PermitUnavailable:
        raise SetupRefused(
            "permit_unreadable", "the chain could not be read; try again later."
        ) from None
    if permit is None:
        raise SetupRefused(
            "hotkey_not_registered",
            "register this hotkey on the subnet, then run this again.",
        )
    if permit["permit"] is not True:
        raise SetupRefused(
            "hotkey_no_validator_permit",
            "this hotkey holds no validator permit on the subnet yet; it needs "
            "one to receive submissions.",
        )


def _pack_selection(pack: Path | None) -> dict | None:
    if pack is None:
        return None
    if (
        not pack.is_absolute()
        or pack.is_symlink()
        or pack.resolve() != pack
        or not (pack / "evaluation-pack.json").is_file()
    ):
        raise SetupRefused(
            "evaluation_pack_invalid",
            "give the absolute path of a built evaluation pack directory "
            "(it holds evaluation-pack.json).",
        )
    root = str(pack)
    return {
        "root": root,
        "manifest": "evaluation-pack.json",
        "public_root": root,
        "private_root": root,
    }


def _stored_pack(store: Path, digest: str, challenge: dict) -> Path:
    """The verified directory of a delivered pack, by manifest digest."""
    from carbon.challenge_validator.answer_key import AnswerKeyRefused
    from carbon.challenge_validator.sealed_pack_import import SealedPackStore

    try:
        return SealedPackStore(store).pack_directory(
            digest, challenge["id"], challenge["version"]
        )
    except AnswerKeyRefused as refused:
        raise SetupRefused(
            refused.code,
            "run the answer-key sync for this Challenge first; the delivered "
            "pack is missing, altered, or another Challenge's.",
        ) from None


def _stored_pack_set(store: Path, set_key: str, challenge: dict):
    """A delivered pack set, every batch re-verified now: the config block, the
    first batch's digest and its directory (the receiver's primary pack)."""
    from carbon.challenge_validator.answer_key import AnswerKeyRefused
    from carbon.challenge_validator.sealed_pack_import import SealedPackStore

    try:
        batches = SealedPackStore(store).pack_set(
            set_key, challenge["id"], challenge["version"]
        )
    except AnswerKeyRefused as refused:
        raise SetupRefused(
            refused.code,
            "run the answer-key sync for this Challenge first; the pack set or "
            "one of its batches is missing, altered, or another Challenge's.",
        ) from None
    first_digest, first_directory = batches[0]
    block = {
        "store": str(store),
        "set_key": set_key,
        "batches": [digest for digest, _directory in batches],
    }
    return block, first_digest, first_directory


def development_install(installed_state: Path, *, repository: Path = REPO) -> bool:
    """Whether this install carries an explicit DEVELOPMENT candidate profile
    (`install_validator.sh --development-candidate ...`)."""
    from scripts.dev.miner_launchpad import installed

    return (
        installed.candidate_implementation(installed_state, repository=repository)
        is not None
    )


def _gpu_file(name: str, value) -> str:
    """An exact absolute regular file (no symlink): the receiver's own rule for a GPU lane file."""
    selected = Path(value) if isinstance(value, (str, Path)) else None
    if (
        selected is None
        or not selected.is_absolute()
        or selected.is_symlink()
        or not selected.is_file()
        or selected.resolve() != selected
    ):
        raise SetupRefused(
            f"{name}_invalid",
            "give the exact absolute path of an existing regular file (no symlink).",
        )
    return str(selected)


def _gpu_lane_keys(
    graph_gpu_image_manifest,
    graph_gpu_ops,
    gpu_construction_images,
    construction_runtimes,
) -> dict:
    """The receiver-config keys of the GPU lane, validated before anything is written; ``{}`` when none."""
    from carbon.challenge_validator.direct_receiver import CONSTRUCTION_RUNTIMES

    keys: dict = {}
    if (graph_gpu_image_manifest is None) != (graph_gpu_ops is None):
        raise SetupRefused(
            "graph_gpu_lane_incomplete",
            "give both --graph-gpu-image-manifest and --graph-gpu-ops, or neither.",
        )
    if graph_gpu_image_manifest is not None:
        keys["graph_gpu_image_manifest"] = _gpu_file(
            "graph_gpu_image_manifest", graph_gpu_image_manifest
        )
        keys["graph_gpu_ops"] = _gpu_file("graph_gpu_ops", graph_gpu_ops)
    images = tuple(gpu_construction_images)
    if images:
        if len(images) > 2:
            raise SetupRefused(
                "gpu_construction_images_invalid",
                "give one or two GPU worker manifests (one per backend).",
            )
        if not construction_runtimes:
            raise SetupRefused(
                "construction_runtimes_needed",
                "GPU construction images need the full CPU construction set; enable --construction-runtimes.",
            )
        keys["gpu_construction_images"] = [
            _gpu_file("gpu_construction_image", item) for item in images
        ]
    if construction_runtimes:
        keys["construction_runtimes"] = list(CONSTRUCTION_RUNTIMES)
    return keys


def prepare(
    *,
    installed_state: Path,
    receiver_state: Path,
    challenge: dict,
    hotkey: str,
    pack: Path | None = None,
    pack_store: Path | None = None,
    pack_digest: str | None = None,
    pack_set_key: str | None = None,
    port: int = DEFAULT_PORT,
    lifetime_seconds: int | None = DEFAULT_LIFETIME_SECONDS,
    repository: Path = REPO,
    checks=None,
    permits=None,
    speed_sample_key_file: Path | None = None,
    auto_grade: bool = False,
    auto_grade_pool_store: Path | None = None,
    graph_gpu_image_manifest: Path | None = None,
    graph_gpu_ops: Path | None = None,
    gpu_construction_images: tuple = (),
    construction_runtimes: bool = True,
) -> dict:
    """Write the runner profile and receiver configuration; return public facts.

    The GPU lane (a dedicated GPU validator host) is opt-in: ``graph_gpu_image_manifest`` and
    ``graph_gpu_ops`` (both or neither) name the registered JAX GPU worker and the ops record the
    hardware class check wrote; ``gpu_construction_images`` (one or two GPU worker manifests) rebuild
    catalog entries on their GPU twins and need ``construction_runtimes`` (the default full CPU
    construction pair). An explicit false opts out and retains only the installed worker; the returned
    mode and subsequent status report that choice. Paths are checked here; the receiver re-checks the images, the
    ops record and the owner's hardware acceptance at start.

    ``speed_sample_key_file`` is the pool versions' K_speed (the custody job writes it beside the signed copy,
    `copy_issuance`): an exact private file, recorded in the configuration so the receiver times single-design
    calls under it; without it a pool grade has no speed evidence (typed unavailable).
    """
    from carbon.challenge_validator.direct_receiver import (
        installed_source,
        load_config,
        read_speed_sample_key,
    )
    from carbon.development_session.profile import canonical
    from scripts.dev.miner_launchpad import installed
    from scripts.dev.miner_launchpad.environment_setup import (
        NO_MODEL_KEY,
        PROFILE_ID,
        LiveChecks,
        write_private,
    )
    from scripts.dev.miner_launchpad.environment_setup import (
        SetupRefused as EnvironmentRefused,
    )
    from scripts.dev.miner_launchpad.runner import PROFILE_SCHEMA, validated_profile

    if auto_grade_pool_store is not None and not auto_grade:
        raise SetupRefused(
            "auto_grade_pool_store_without_auto_grade",
            "--auto-grade-pool-store only applies together with --auto-grade.",
        )
    if auto_grade and pack_set_key is not None:
        # the receiver refuses this pair at start-up (auto_grade_pack_set_unsupported)
        raise SetupRefused(
            "auto_grade_pack_set_unsupported",
            "a pack-set receiver is graded by the operator step, not by auto-grade.",
        )
    if (
        auto_grade_pool_store is not None
        and not Path(auto_grade_pool_store).is_absolute()
    ):
        raise SetupRefused(
            "auto_grade_pool_store_invalid",
            "give the exact absolute path of the existing pool store.",
        )
    if speed_sample_key_file is not None:
        # validated before anything is written, so a refusal leaves no half-prepared state
        try:
            read_speed_sample_key(str(speed_sample_key_file))
        except ValueError:
            raise SetupRefused(
                "speed_sample_key_file_invalid",
                "give the exact absolute path of an owner-only (0600) K_speed file of 32 to 4096 bytes.",
            ) from None
    gpu_keys = _gpu_lane_keys(
        graph_gpu_image_manifest,
        graph_gpu_ops,
        gpu_construction_images,
        construction_runtimes,
    )
    for name, path in (
        ("installed_state", installed_state),
        ("receiver_state", receiver_state),
    ):
        if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
            raise SetupRefused(f"{name}_invalid", "give an exact absolute directory.")
    records = installed.read(installed_state)
    if not records or not {"image_manifest", "analysis_image_manifest"} <= set(records):
        raise SetupRefused(
            "images_not_installed",
            "run scripts/install_validator.sh (or install_miner.sh) first; no "
            "installed worker and analysis images are recorded.",
        )
    if pack is not None and not development_install(
        installed_state, repository=repository
    ):
        # An operator-built pack never serves as an official exam (Validator,
        # E4 condition 2); a delivered pack comes from --pack-store.
        raise SetupRefused(
            "built_packs_development_only",
            "--pack is for development installs only (an explicit DEVELOPMENT "
            "candidate profile); take the delivered exam with --pack-store.",
        )
    chosen = (
        (pack is not None)
        + (pack_store is not None and pack_digest is not None)
        + (pack_store is not None and pack_set_key is not None)
    )
    if (
        chosen > 1
        or (pack_store is None) != (pack_digest is None and pack_set_key is None)
        or (pack_digest is not None and pack_set_key is not None)
    ):
        raise SetupRefused(
            "evaluation_pack_invalid",
            "give either --pack, or --pack-store with --pack-digest (one "
            "pack), or --pack-store with --pack-set-key (a Challenge "
            "version's whole pack set).",
        )
    pack_set = None
    if pack_set_key is not None:
        pack_set, pack_digest, pack = _stored_pack_set(
            pack_store, pack_set_key, challenge
        )
    elif pack_store is not None:
        pack = _stored_pack(pack_store, pack_digest, challenge)
    selection = _pack_selection(pack)
    if selection is not None and pack_store is not None:
        # Delivery provenance: the receiver re-checks it against the store, so
        # only a pack that came through the answer-key route is sealed.
        selection["sealed_delivery"] = {
            "store": str(pack_store),
            "manifest_digest": pack_digest,
        }
    development = (
        installed.candidate_implementation(installed_state, repository=repository)
        is not None
    )
    checks = checks or LiveChecks(
        repo=repository, candidate_state_dir=installed_state if development else None
    )
    try:
        runtime = checks.compute(
            Path(records["image_manifest"]), Path(records["analysis_image_manifest"])
        )
        network, block = checks.network()
    except EnvironmentRefused as refusal:
        raise SetupRefused(
            f"{refusal.field}_{refusal}",
            refusal.next_step or "fix the named check and run this again.",
        ) from None
    _require_permit(hotkey, network, permits)
    environment = receiver_state / "environment"
    config_path = receiver_state / "receiver" / CONFIG_NAME
    profile_path = environment / PROFILE_NAME
    if environment.exists() or config_path.exists():
        raise SetupRefused(
            "receiver_state_in_use",
            "this receiver state already has a profile; use a new directory.",
        )
    environment.mkdir(mode=0o700, parents=True)
    (receiver_state / "receiver").mkdir(mode=0o700, exist_ok=True)
    campaigns = environment / "campaigns"
    campaigns.mkdir(mode=0o700)
    # The receiver state records the same installed images (and, for a DEVELOPMENT
    # candidate, the same operator source pin) as the install it serves.
    installed.write(
        receiver_state,
        image_manifest=records["image_manifest"],
        analysis_image_manifest=records["analysis_image_manifest"],
    )
    if development:
        pin = json.loads(
            (installed_state / installed.DEVELOPMENT_CANDIDATE_FILE).read_bytes()
        )
        bound = installed.bind_development_candidate(
            receiver_state,
            revision=pin["revision"],
            tree=pin["tree"],
            source_tree_digest=pin["source_tree_digest"],
            repository=repository,
        )
        if bound != runtime["implementation"]:
            raise SetupRefused(
                "candidate_pin_differs", "the install and its source pin disagree."
            )
    write_private(environment / "miner-network.json", canonical(network))
    write_private(
        environment / "miner-public.json",
        canonical({"netuid": network["context"]["netuid"], "hotkey": hotkey}),
    )
    profile = {
        "schema": PROFILE_SCHEMA,
        "profile_id": PROFILE_ID,
        "principal": hotkey,
        "enabled": True,
        "paths": {
            "image_manifest": records["image_manifest"],
            "analysis_image_manifest": records["analysis_image_manifest"],
            "api_key_file": str(environment / "keys" / NO_MODEL_KEY),
            "miner_public": str(environment / "miner-public.json"),
            "quarantine_journal": str(environment / "quarantine-journal.sqlite3"),
            "miner_network": str(environment / "miner-network.json"),
        },
        "accepted_revision": runtime["implementation"]["revision"],
        "campaigns_root": str(campaigns),
        "runtime": runtime,
    }
    write_private(profile_path, canonical(validated_profile(profile)))
    implementation, _, _, _ = installed_source(profile_path)
    if implementation["revision"] != runtime["implementation"]["revision"]:
        raise SetupRefused("source_differs", "the installed source moved; reinstall.")
    config = {
        "schema": "carbon.construction.direct-receiver-operator.v1",
        "root": str(receiver_state / "receiver" / "state"),
        "runner_profile": str(profile_path),
        "receiver_hotkey": hotkey,
        "host": "127.0.0.1",
        "port": port,
        "lifetime_seconds": lifetime_seconds,
        "measure_query": True,
        "material_cache_bytes": MATERIAL_CACHE_BYTES,
        "challenge": challenge,
    }
    if selection is not None:
        config["evaluation_pack"] = selection
    if pack_set is not None:
        config["evaluation_pack_set"] = pack_set
    if speed_sample_key_file is not None:
        config["speed_sample_key_file"] = str(speed_sample_key_file)
    if auto_grade:
        # The serving process retains and grades each SUCCEEDED task itself (auto_grade.py).
        config["auto_grade"] = (
            {}
            if auto_grade_pool_store is None
            else {"pool_store": str(auto_grade_pool_store)}
        )
    config.update(gpu_keys)
    write_private(config_path, canonical(config))
    load_config(config_path)
    return {
        "status": "RECEIVER_PROFILE_READY",
        "source_head": implementation["revision"],
        "challenge": challenge,
        "receiver_hotkey": hotkey,
        "port": port,
        "evaluation_pack": selection is not None,
        "evaluation_pack_set": pack_set is not None,
        "graph_gpu_lane": "graph_gpu_image_manifest" in gpu_keys,
        "gpu_construction_images": len(gpu_keys.get("gpu_construction_images", ())),
        "construction_runtime_mode": (
            "full_cpu" if construction_runtimes else "installed_worker_only"
        ),
        "network_block": block,
        "profile_sha256": _sha(profile_path.read_bytes()),
        "config_sha256": _sha(config_path.read_bytes()),
        "config": str(config_path),
    }


def gpu_check(
    *,
    graph_gpu_image_manifest: Path | None = None,
    graph_gpu_ops: Path | None = None,
    gpu_construction_images: tuple = (),
    checks=None,
    device=None,
    stack_facts=None,
) -> dict:
    """Is this host ready to serve the GPU lane? Reads only; nothing is written or started.

    Order: the files named (same rules as ``prepare``), this host's installed GPU device record
    (``scripts/dev/carbon_accelerator.py prepare``), and the owner's hardware acceptance for that
    device class on this chain network, and last the host's software stack: the Docker engine
    version and image store and the NVIDIA driver and container toolkit must be the registered, tested
    ones (`carbon.reconstruction.host_stack`), never whatever the box shipped. The receiver re-checks
    the files, the worker images and the ops record's allowlist when it starts; this is the early,
    readable refusal."""
    from carbon.development_session import research_carrier
    from carbon.reconstruction.hardware_acceptance import (
        DeviceClassNotAccepted,
        require_accepted,
    )
    from scripts.dev.miner_launchpad.environment_setup import LiveChecks
    from scripts.dev.miner_launchpad.environment_setup import (
        SetupRefused as EnvironmentRefused,
    )

    keys = _gpu_lane_keys(
        graph_gpu_image_manifest,
        graph_gpu_ops,
        gpu_construction_images,
        bool(gpu_construction_images),
    )
    if "graph_gpu_image_manifest" not in keys and "gpu_construction_images" not in keys:
        raise SetupRefused(
            "no_gpu_lane_named",
            "name the graph GPU lane (--graph-gpu-image-manifest and --graph-gpu-ops) "
            "and/or --gpu-construction-image.",
        )
    if device is None:
        try:
            device = research_carrier._gpu_device()
        except ValueError:
            raise SetupRefused(
                "gpu_device_record_missing",
                "run scripts/dev/carbon_accelerator.py prepare on this host first.",
            ) from None
    try:
        network, _ = (checks or LiveChecks(repo=REPO)).network()
    except EnvironmentRefused as refusal:
        raise SetupRefused(
            f"{refusal.field}_{refusal}",
            refusal.next_step or "fix the named check and run this again.",
        ) from None
    chain = network.get("context", {}).get("network")
    try:
        require_accepted(device.device_kind, research_carrier._gpu_profile_id(), chain)
    except DeviceClassNotAccepted:
        raise SetupRefused(
            "gpu_class_not_accepted",
            "the owner's hardware acceptance does not name this GPU class for this chain network; "
            "this host cannot score on it.",
        ) from None
    from carbon.reconstruction import host_stack

    facts = host_stack.read_facts() if stack_facts is None else stack_facts
    differences = host_stack.problems(facts)
    if differences:
        raise SetupRefused(
            "host_stack_not_tested",
            "this host's software is not the tested stack: "
            + "; ".join(
                f"{row['check']} is {row['found']!r}, needs {row['required']}"
                for row in differences
            )
            + ". Install the registered versions (docs/development/DAY_ONE step 1) and run this again.",
        )
    return {
        "status": "GPU_HOST_READY",
        "device_kind": device.device_kind,
        "device_record": device.digest,
        "chain_network": chain,
        "graph_gpu_lane": "graph_gpu_image_manifest" in keys,
        "gpu_construction_images": len(keys.get("gpu_construction_images", ())),
        "host_stack": facts,
    }


def _command(receiver_state: Path) -> list[str]:
    config = receiver_state / "receiver" / CONFIG_NAME
    if not config.is_file() or config.is_symlink():
        raise SetupRefused(
            "receiver_config_missing",
            f"{config} does not exist; run `prepare` for this receiver state first.",
        )
    return [
        str(REPO / ".venv" / "bin" / "python"),
        "-B",
        "-m",
        "carbon.challenge_validator.direct_receiver",
        "--config",
        str(config),
    ]


def _lingers(user: str):
    """Whether `user`'s systemd user manager outlives their logout: True,
    False, or None when loginctl cannot say."""
    try:
        shown = subprocess.run(
            ["loginctl", "show-user", user, "--property=Linger", "--value"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if shown.returncode != 0:
        return None
    return shown.stdout.strip() == "yes"


def start(receiver_state: Path, *, detach: bool = False) -> int:
    """Run the receiver here, or as a transient user systemd unit with --detach."""
    command = _command(receiver_state)
    if not detach:
        os.chdir(REPO)
        os.execv(command[0], command)
    import getpass

    user = getpass.getuser()
    if _lingers(user) is False:
        # A user unit stops at logout without linger: refuse before starting it.
        raise SetupRefused(
            "receiver_linger_off",
            f"a detached receiver would stop when {user} logs out; run "
            f"`loginctl enable-linger {shlex.quote(user)}` once on this host, "
            "then start again.",
        )
    unit = unit_name(receiver_state)
    started = subprocess.run(
        [
            "systemd-run",
            "--user",
            "--collect",
            f"--unit={unit}",
            f"--property=WorkingDirectory={REPO}",
            *command,
        ],
        check=False,
    )
    if started.returncode == 0:
        print(
            json.dumps(
                {
                    "status": "RECEIVER_STARTED",
                    "unit": unit,
                    "follow": f"journalctl --user -u {shlex.quote(unit)} -f",
                    "stop": f"systemctl --user stop {shlex.quote(unit)}",
                    # A user unit stops at logout unless the user lingers.
                    "keep_after_logout": 'loginctl enable-linger "$USER"',
                }
            )
        )
    return started.returncode


def unit_name(receiver_state: Path) -> str:
    """The receiver's systemd user unit: one per receiver state."""
    return "carbon-receiver-" + _sha(str(receiver_state).encode())[:12]


#: Characters a unit's command may hold unquoted; anything else is refused.
_UNIT_SAFE = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/._-+=:,@"
)


def _unit_text(receiver_state: Path, challenge: dict) -> str:
    command = _command(receiver_state)
    for part in (*command, str(REPO)):
        if not part or set(part) - _UNIT_SAFE:
            raise SetupRefused(
                "receiver_path_unsupported",
                "install Carbon and the receiver state under paths of letters, "
                "digits and / . _ - only.",
            )
    return "\n".join(
        (
            "[Unit]",
            (
                "Description=Carbon validator receiver "
                f"({challenge['id']} {challenge['version']})"
            ),
            "After=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={REPO}",
            "ExecStart=" + " ".join(command),
            "Restart=on-failure",
            "RestartSec=30",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        )
    )


def service(receiver_state: Path, *, unit_dir: Path | None = None, run=None) -> dict:
    """Install the receiver as a persistent `systemd --user` service (E5): it
    restarts on failure and starts again after a reboot (linger on)."""
    import getpass

    from .direct_receiver import load_config

    run = run or subprocess.run
    config = load_config(receiver_state / "receiver" / CONFIG_NAME)
    if "evaluation_pack" not in config:
        # A validator receiver that cannot grade would spend miners' epoch slots
        # on nothing (Validator, E4 (c)): the service refuses to start.
        raise SetupRefused(
            "evaluation_pack_missing",
            "this receiver has no evaluation pack; fetch the signed exam for its "
            "Challenge and prepare it with the pack.",
        )
    if config["lifetime_seconds"] is not None:
        raise SetupRefused(
            "service_has_lifetime",
            "a service runs until stopped; prepare this receiver without "
            "--lifetime-seconds.",
        )
    user = getpass.getuser()
    if _lingers(user) is False:
        raise SetupRefused(
            "receiver_linger_off",
            f"the service would stop when {user} logs out and not start after a "
            f"reboot; run `loginctl enable-linger {shlex.quote(user)}` once, then "
            "run this again.",
        )
    unit = unit_name(receiver_state)
    text = _unit_text(receiver_state, config["challenge"])
    unit_dir = unit_dir or Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    (unit_dir / (unit + ".service")).write_bytes(text.encode("utf-8"))
    for step in (["daemon-reload"], ["enable", "--now", unit + ".service"]):
        if run(["systemctl", "--user", *step], check=False).returncode != 0:
            raise SetupRefused(
                "receiver_service_not_started",
                f"systemctl --user {' '.join(step)} failed; see "
                f"`journalctl --user -u {unit}`.",
            )
    return {
        "status": "RECEIVER_SERVICE_ENABLED",
        "unit": unit,
        "challenge": config["challenge"],
        "follow": f"journalctl --user -u {unit} -f",
        "stop": f"systemctl --user disable --now {unit}",
    }


def _last_graded(root: Path):
    """The receiver's graded submissions on its own ledger (operator view)."""
    import sqlite3

    ledger = root / "attempts.sqlite3"
    if not ledger.is_file():
        return {"graded": 0, "last_graded_unix": None}
    try:
        with sqlite3.connect(f"file:{ledger}?mode=ro", uri=True) as db:
            count, last = db.execute(
                "SELECT COUNT(*), MAX(settled_ns) FROM exam_graded "
                "WHERE kind='GRADED' AND state='COUNTED'"
            ).fetchone()
    except sqlite3.Error:
        # No grading yet (the cap's table appears with the first exam).
        return {"graded": 0, "last_graded_unix": None}
    return {
        "graded": count,
        "last_graded_unix": None if last is None else last // 1_000_000_000,
    }


def _auto_grade_failures(root: Path) -> dict:
    """Auto-grade's FAILED markers for the operator (``{}`` when this receiver
    does not auto-grade): a count and the last code, never a task's content."""
    from carbon.challenge_validator.auto_grade import failure_summary

    return failure_summary(root)


#: At most this many missing bundles are listed in `status` (the count is whole).
CATALOG_LISTED = 12


def catalog_state(config: dict) -> dict:
    """The receiver's catalog for `status`: how many served bundles it holds and
    which it lacks (`scripts.dev.receiver_catalog.verify`, read-only). The
    receiver is not healthy while any served bundle is missing. A receiver whose
    records cannot be read here reports ``UNVERIFIED``; that unknown inventory
    cannot establish receiver health."""
    try:
        from scripts.dev import receiver_catalog

        if not receiver_catalog.served_runtimes(config):
            # No construction parent can be read from its records: nothing here
            # can say what it would install.
            return {"status": "UNVERIFIED", "ready": None}
        found = receiver_catalog.verify(config)
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        return {"status": "UNVERIFIED", "ready": None}
    return {
        "status": "COMPLETE" if found["ready"] else "INCOMPLETE",
        "ready": found["ready"],
        "served": found["served"],
        "installed": found["installed"],
        "missing_count": len(found["missing"]),
        "missing": [
            {k: row[k] for k in ("catalog_id", "runtime", "kind", "reason")}
            for row in found["missing"][:CATALOG_LISTED]
        ],
        "next": (
            None
            if found["ready"]
            else "run `receiver_setup install-catalog --receiver-state DIR` "
            "(day-one step 8a), then check again"
        ),
    }


def install_catalog(receiver_state: Path, *, wheelhouse: Path | None = None) -> dict:
    """Day-one step 8a: install every served catalog entry into the receiver's
    own library cache and verify them. Not ready (and a non-zero exit) while any
    served bundle is missing."""
    from scripts.dev import receiver_catalog

    from .direct_receiver import load_config

    path = receiver_state / "receiver" / CONFIG_NAME
    return receiver_catalog.install(load_config(path), path, wheelhouse=wheelhouse)


def catalog_status(receiver_state: Path) -> dict:
    from scripts.dev import receiver_catalog

    from .direct_receiver import load_config

    return receiver_catalog.verify(
        load_config(receiver_state / "receiver" / CONFIG_NAME)
    )


def status(receiver_state: Path, *, run=None, fetch=None) -> dict:
    """What a validator checks (E7): the service, the local intake, the exam
    the receiver holds and its last graded submission. Read-only."""
    import urllib.request

    from .direct_receiver import load_config

    run = run or subprocess.run
    config = load_config(receiver_state / "receiver" / CONFIG_NAME)
    unit = unit_name(receiver_state)
    try:
        shown = run(
            ["systemctl", "--user", "is-active", unit + ".service"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        service_state = shown.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        service_state = "unknown"

    def read(url):
        with urllib.request.urlopen(url, timeout=5) as answer:
            return json.loads(answer.read(65536))

    fetch = fetch or read
    try:
        facts = fetch(
            f"http://{config['host']}:{config['port']}/carbon/v1/construction/intake"
        )
        intake = "LISTENING" if type(facts) is dict else "UNREADABLE"
    except (OSError, ValueError):
        intake = "UNREACHABLE"
    root = Path(config["root"])
    binding = root / "receiver-binding.json"
    try:
        exam = json.loads(binding.read_bytes()).get("evaluation_pack_digest")
    except (OSError, ValueError):
        exam = None
    catalog = catalog_state(config)
    healthy = (
        service_state == "active"
        and intake == "LISTENING"
        and "evaluation_pack" in config
        and catalog.get("ready") is True
    )
    return {
        "status": "RECEIVER_HEALTHY" if healthy else "RECEIVER_NOT_HEALTHY",
        "catalog": catalog,
        "challenge": config.get("challenge"),
        "receiver_hotkey": config["receiver_hotkey"],
        "unit": unit,
        "construction_runtime_mode": (
            "full_cpu" if "construction_runtimes" in config else "installed_worker_only"
        ),
        "service": service_state,
        "intake": intake,
        "port": config["port"],
        "exam": (
            "SELECTED" if "evaluation_pack" in config else "evaluation_pack_missing"
        ),
        "exam_digest": exam,
        **_last_graded(root),
        **_auto_grade_failures(root),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -B -m carbon.challenge_validator.receiver_setup"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("challenges")
    prep = sub.add_parser("prepare")
    prep.add_argument("--installed-state", type=Path, required=True)
    prep.add_argument("--receiver-state", type=Path, required=True)
    prep.add_argument("--hotkey", required=True)
    prep.add_argument("--challenge", nargs=2, metavar=("ID", "VERSION"), required=True)
    prep.add_argument("--pack", type=Path)
    prep.add_argument("--pack-store", type=Path)
    prep.add_argument("--pack-digest")
    prep.add_argument("--pack-set-key")
    prep.add_argument(
        "--speed-sample-key-file",
        type=Path,
        help="the pool versions' K_speed file (written beside the signed copy by the issuance job)",
    )
    prep.add_argument(
        "--auto-grade",
        action="store_true",
        help="write auto_grade into the receiver configuration: the serving process retains and grades "
        "each task that reaches SUCCEEDED, so no operator step is needed per miner task",
    )
    prep.add_argument(
        "--auto-grade-pool-store",
        type=Path,
        help="with --auto-grade: the existing pool store (absolute path) the grade is recorded in",
    )
    prep.add_argument(
        "--graph-gpu-image-manifest",
        type=Path,
        help="the registered JAX GPU worker's image manifest (graph GPU lane; with --graph-gpu-ops)",
    )
    prep.add_argument(
        "--graph-gpu-ops",
        type=Path,
        help="the ops record gpu_rebuild_class_check.py --ops-record wrote on this GPU host",
    )
    prep.add_argument(
        "--gpu-construction-image",
        type=Path,
        action="append",
        default=[],
        help="a GPU worker image manifest catalog entries rebuild on (repeat once per backend)",
    )
    prep.add_argument(
        "--construction-runtimes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="serve both CPU construction runtimes (default); --no-construction-runtimes explicitly narrows to the installed worker",
    )
    prep.add_argument("--port", type=int, default=DEFAULT_PORT)
    prep.add_argument("--lifetime-seconds", type=int, default=DEFAULT_LIFETIME_SECONDS)
    gpu = sub.add_parser("gpu-check")
    gpu.add_argument("--graph-gpu-image-manifest", type=Path)
    gpu.add_argument("--graph-gpu-ops", type=Path)
    gpu.add_argument("--gpu-construction-image", type=Path, action="append", default=[])
    run = sub.add_parser("start")
    run.add_argument("--receiver-state", type=Path, required=True)
    run.add_argument("--detach", action="store_true")
    for name in ("service", "status", "catalog-status"):
        sub.add_parser(name).add_argument("--receiver-state", type=Path, required=True)
    installer = sub.add_parser("install-catalog")
    installer.add_argument("--receiver-state", type=Path, required=True)
    installer.add_argument(
        "--wheelhouse",
        type=Path,
        help="the pinned wheels (default: the host's catalog wheelhouse)",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            return start(args.receiver_state, detach=args.detach)
        if args.command == "challenges":
            result = {"served": list(served()), "current": list(current())}
        elif args.command == "gpu-check":
            result = gpu_check(
                graph_gpu_image_manifest=args.graph_gpu_image_manifest,
                graph_gpu_ops=args.graph_gpu_ops,
                gpu_construction_images=tuple(args.gpu_construction_image),
            )
        elif args.command == "service":
            result = service(args.receiver_state)
        elif args.command == "status":
            result = status(args.receiver_state)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["status"] == "RECEIVER_HEALTHY" else 3
        elif args.command in ("install-catalog", "catalog-status"):
            result = (
                install_catalog(args.receiver_state, wheelhouse=args.wheelhouse)
                if args.command == "install-catalog"
                else catalog_status(args.receiver_state)
            )
            print(json.dumps(result, sort_keys=True))
            return 0 if result["ready"] else 3
        else:
            result = prepare(
                installed_state=args.installed_state,
                receiver_state=args.receiver_state,
                challenge=_challenge(*args.challenge),
                hotkey=args.hotkey,
                pack=args.pack,
                pack_store=args.pack_store,
                pack_digest=args.pack_digest,
                pack_set_key=args.pack_set_key,
                port=args.port,
                lifetime_seconds=args.lifetime_seconds,
                speed_sample_key_file=args.speed_sample_key_file,
                auto_grade=args.auto_grade,
                auto_grade_pool_store=args.auto_grade_pool_store,
                graph_gpu_image_manifest=args.graph_gpu_image_manifest,
                graph_gpu_ops=args.graph_gpu_ops,
                gpu_construction_images=tuple(args.gpu_construction_image),
                construction_runtimes=args.construction_runtimes,
            )
    except SetupRefused as refusal:
        print(
            json.dumps({"refused": refusal.code, "next": refusal.next_step}),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
