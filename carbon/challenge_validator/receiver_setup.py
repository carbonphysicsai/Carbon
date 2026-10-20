"""Operator setup for the DEVELOPMENT direct receiver: profile, configuration, start.

    .venv/bin/python -B -m carbon.challenge_validator.receiver_setup prepare \\
        --installed-state STATE --receiver-state DIR --challenge ID VERSION [--pack DIR]
    .venv/bin/python -B -m carbon.challenge_validator.receiver_setup start \\
        --receiver-state DIR [--detach]

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

The evaluation pack is an input (`--pack`): a pack's leg minimums come from a
baseline run on the judge image, which a validator host does not produce. The
receiver hotkey is the network publisher the testnet context resolves, exactly
as the drivers used it; another validator identity is an owner decision this
tool does not make. The receiver listens on 127.0.0.1 only.
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
#: The drivers' value: the receiver stops itself after this long. A longer-lived
#: validator lifetime is a deliberate setting, not a default.
DEFAULT_LIFETIME_SECONDS = 7200
MATERIAL_CACHE_BYTES = 192 * 1024 * 1024


class SetupRefused(RuntimeError):
    """A typed refusal naming the field and the next step; never a path or secret."""

    def __init__(self, code: str, next_step: str):
        super().__init__(f"{code}: {next_step}")
        self.code, self.next_step = code, next_step


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _challenge(challenge_id: str, version: str) -> dict:
    from carbon.challenge_kit import physical_material

    if not physical_material.is_registered(challenge_id, version):
        raise SetupRefused(
            "challenge_not_registered",
            "name a registered lean Challenge (Motor electric-motor-magnetics 1.0 "
            "or Cooling chip-cold-plate 1.0).",
        )
    return {"id": challenge_id, "version": version}


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


def prepare(
    *,
    installed_state: Path,
    receiver_state: Path,
    challenge: dict,
    pack: Path | None = None,
    port: int = DEFAULT_PORT,
    lifetime_seconds: int = DEFAULT_LIFETIME_SECONDS,
    repository: Path = REPO,
    checks=None,
) -> dict:
    """Write the runner profile and receiver configuration; return public facts."""
    from carbon.challenge_validator.direct_receiver import installed_source, load_config
    from carbon.development_session.profile import canonical
    from scripts.dev.miner_launchpad import installed
    from scripts.dev.miner_launchpad.environment_setup import (
        NO_MODEL_KEY,
        PROFILE_ID,
        LiveChecks,
        SetupRefused as EnvironmentRefused,
        write_private,
    )
    from scripts.dev.miner_launchpad.runner import PROFILE_SCHEMA, validated_profile

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
    selection = _pack_selection(pack)
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
    publisher = network["publisher_hotkey"]
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
        canonical({"netuid": network["context"]["netuid"], "hotkey": publisher}),
    )
    profile = {
        "schema": PROFILE_SCHEMA,
        "profile_id": PROFILE_ID,
        "principal": publisher,
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
        "receiver_hotkey": publisher,
        "host": "127.0.0.1",
        "port": port,
        "lifetime_seconds": lifetime_seconds,
        "measure_query": True,
        "material_cache_bytes": MATERIAL_CACHE_BYTES,
        "challenge": challenge,
    }
    if selection is not None:
        config["evaluation_pack"] = selection
    write_private(config_path, canonical(config))
    load_config(config_path)
    return {
        "status": "RECEIVER_PROFILE_READY",
        "source_head": implementation["revision"],
        "challenge": challenge,
        "evaluation_pack": selection is not None,
        "network_block": block,
        "profile_sha256": _sha(profile_path.read_bytes()),
        "config_sha256": _sha(config_path.read_bytes()),
        "config": str(config_path),
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
    unit = "carbon-receiver-" + _sha(str(receiver_state).encode())[:12]
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -B -m carbon.challenge_validator.receiver_setup"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--installed-state", type=Path, required=True)
    prep.add_argument("--receiver-state", type=Path, required=True)
    prep.add_argument("--challenge", nargs=2, metavar=("ID", "VERSION"), required=True)
    prep.add_argument("--pack", type=Path)
    prep.add_argument("--port", type=int, default=DEFAULT_PORT)
    prep.add_argument("--lifetime-seconds", type=int, default=DEFAULT_LIFETIME_SECONDS)
    run = sub.add_parser("start")
    run.add_argument("--receiver-state", type=Path, required=True)
    run.add_argument("--detach", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            return start(args.receiver_state, detach=args.detach)
        result = prepare(
            installed_state=args.installed_state,
            receiver_state=args.receiver_state,
            challenge=_challenge(*args.challenge),
            pack=args.pack,
            port=args.port,
            lifetime_seconds=args.lifetime_seconds,
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
