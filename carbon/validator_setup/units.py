"""Render explicit image-backed operator units; never install or start them."""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path

from .bundle import SetupRefused, verify
from .weights import load_config as load_weights

SCHEMA = "carbon.validator-runtime-units.v1"
PASSWD = Path("/etc/passwd")


def _account_map(deployment, user):
    """Use the host's public identity map; never trust an environment name."""
    try:
        info = PASSWD.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & 0o022
            or info.st_size > 1024 * 1024
        ):
            raise ValueError
        uid = int(user.split(":")[0])
        if uid == 0:
            raise ValueError
        entries = [
            line.split(":") for line in PASSWD.read_text(encoding="utf-8").splitlines()
        ]
        matches = [row for row in entries if len(row) == 7 and row[2] == str(uid)]
        if len(matches) != 1:
            raise ValueError
        account = matches[0]
        expected = deployment.get("service_account")
        if expected is not None and expected != account[0]:
            raise ValueError
        if not Path(account[5]).is_absolute():
            raise ValueError
        return account[5]
    except (OSError, ValueError, UnicodeError):
        raise SetupRefused("OPERATOR_HOST_ACCOUNT_MAP_REQUIRED") from None


def quoted(argv):
    # systemd ExecStart parses arguments itself; no shell is involved. Prevent
    # specifier/environment expansion of an operator-provided literal path.
    return " ".join(
        json.dumps(str(a).replace("%", "%%").replace("$", "$$")) for a in argv
    )


def _socket_group(socket, user):
    """Bind the mounted endpoint's group without changing primary identity."""
    try:
        info = socket.lstat()
    except OSError:
        raise SetupRefused("DOCKER_SOCKET_METADATA_UNAVAILABLE") from None
    if not stat.S_ISSOCK(info.st_mode):
        raise SetupRefused("DOCKER_SOCKET_REQUIRED")
    if type(info.st_gid) is not int or info.st_gid < 0:
        raise SetupRefused("DOCKER_SOCKET_GROUP_UNAVAILABLE")
    # Unix-socket connect needs write permission. When the configured UID owns
    # the socket, the owner class takes precedence over supplementary groups.
    writable = stat.S_IWUSR if int(user.split(":")[0]) == info.st_uid else stat.S_IWGRP
    if not info.st_mode & writable:
        raise SetupRefused("DOCKER_SOCKET_IDENTITY_NOT_WRITABLE")
    return str(info.st_gid)


def render(profile):
    from carbon.battery.intake import is_loopback, proxy_header, trusted_proxy_peer
    from carbon.challenge_validator.answer_key import load_fetch_config
    from scripts.dev.battery_validator_service.service import (
        _intake,
        load_service,
        owner_only_file,
    )

    owner_only_file(profile, "runtime_units_profile")
    raw = json.loads(Path(profile).read_bytes())
    expected = {
        "schema",
        "name",
        "bundle",
        "digest",
        "image",
        "user",
        "docker_socket",
        "service_network",
        "state_mounts",
        "service_config",
        "fetch_config",
        "weights",
        "sync_every_s",
        "weights_every_s",
    }
    if (
        type(raw) is not dict
        or set(raw) != expected
        or raw["schema"] != SCHEMA
        or re.fullmatch("[a-z0-9][a-z0-9-]{0,47}", raw["name"]) is None
        or re.fullmatch(r"[0-9]+:[0-9]+", raw["user"]) is None
        or re.fullmatch(r"[A-Za-z0-9._:/-]+@sha256:[0-9a-f]{64}", raw["image"]) is None
    ):
        raise SetupRefused("EXACT_OPERATOR_UNIT_PROFILE_REQUIRED")
    artifact = verify(Path(raw["bundle"]), raw["digest"])
    service = load_service(raw["service_config"])
    intake = _intake(service, artifact.root)
    # load_config also enforces the *current process* account. Rendering may be
    # performed by root for a different numeric operator, so read path references
    # only here; runtime preflight retains the full deployment/account checks.
    owner_only_file(intake["deployment"], "runtime_units_deployment")
    try:
        deployment = json.loads(Path(intake["deployment"]).read_bytes())
        if type(deployment) is not dict:
            raise ValueError
        deployment_paths = [
            deployment[k] for k in ("state", "journal", "work", "private_root")
        ]
        deployment_paths += [
            deployment[k]
            for k in ("image_manifest", "torch_image_manifest", "service_key")
            if deployment.get(k) is not None
        ]
        if any(type(p) is not str or not p for p in deployment_paths):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise SetupRefused("OPERATOR_DEPLOYMENT_PATHS_REQUIRED") from None
    home = _account_map(deployment, raw["user"])
    fetch = load_fetch_config(Path(raw["fetch_config"]))
    network = raw["service_network"]
    header = proxy_header(intake)
    if (
        type(network) is not dict
        or set(network) != {"mode", "listener_host", "listener_port", "proxy_peer"}
        or network["mode"] != "host"
        or network["listener_host"] != intake["host"]
        or type(network["listener_port"]) is not int
        or network["listener_port"] != intake["port"]
        or (
            header is not None
            and (
                not is_loopback(intake["host"])
                or not trusted_proxy_peer(network["proxy_peer"])
            )
        )
        or (header is None and network["proxy_peer"] is not None)
    ):
        raise SetupRefused("EXPLICIT_HOST_LISTENER_PROXY_BINDING_REQUIRED")
    w = raw["weights"]
    if type(w) is not dict or set(w) != {
        "config",
        "standing",
        "journal",
        "ledger",
        "deployment",
        "policy_version",
    }:
        raise SetupRefused("EXACT_OPERATOR_UNIT_PROFILE_REQUIRED")
    weights = load_weights(w["config"])
    if (
        fetch.get("hotkey") != weights.publisher_hotkey
        or intake["receiver"] != weights.publisher_hotkey
        or str(fetch.get("deployment")) != str(intake["deployment"])
        or str(w["deployment"]) != str(intake["deployment"])
    ):
        raise SetupRefused("OPERATOR_RECEIVER_OR_DEPLOYMENT_MISMATCH")
    if type(raw["state_mounts"]) is not list or not raw["state_mounts"]:
        raise SetupRefused("EXPLICIT_OPERATOR_STATE_MOUNTS_REQUIRED")
    mounts = [Path(p) for p in raw["state_mounts"]]
    socket = Path(raw["docker_socket"])
    if (
        not socket.is_absolute()
        or "," in str(socket)
        or "," in str(artifact.root)
        or any(
            not p.is_absolute()
            or p.is_symlink()
            or not p.is_dir()
            or artifact.root.is_relative_to(p)
            or p.is_relative_to(artifact.root)
            or "," in str(p)
            for p in mounts
        )
    ):
        raise SetupRefused("EXPLICIT_SEPARATE_OPERATOR_MOUNTS_REQUIRED")
    socket_group = _socket_group(socket, raw["user"])
    required = [
        Path(raw["service_config"]),
        Path(raw["fetch_config"]),
        Path(service.state_dir),
        Path(service.backups),
        Path(service.intake_path),
        Path(intake["deployment"]),
        Path(intake["inbox"]),
        Path(intake["transport_journal"]),
        *(Path(p) for p in deployment_paths),
        Path(str(deployment["state"]) + ".lock").parent,
        *(Path(p) for p in service.config.get("practice_images", {}).values()),
        weights.wallet_path,
        *(Path(w[k]) for k in ("config", "standing", "journal", "ledger")),
    ]
    signer = fetch.get("signer_socket")
    if type(signer) is not str or not signer:
        raise SetupRefused("EXPLICIT_OPERATOR_SIGNER_SOCKET_REQUIRED")
    material = [(signer, "socket")]
    if fetch.get("ca") is not None:
        material.append((fetch["ca"], "file"))
    for field in ("tls_cert", "tls_key"):
        if field in intake:
            material.append((intake[field], "file"))
    for value, kind in material:
        if type(value) is not str or not value:
            raise SetupRefused("EXPLICIT_OPERATOR_CREDENTIAL_PATH_REQUIRED")
        target = Path(value)
        if (
            not target.is_absolute()
            or target.is_symlink()
            or any(p.is_symlink() for p in target.parents)
            or not any(target.is_relative_to(m) for m in mounts)
        ):
            raise SetupRefused("OPERATOR_CREDENTIAL_NOT_MOUNTED_IDENTICALLY")
        try:
            mode = target.stat().st_mode
        except OSError:
            raise SetupRefused("OPERATOR_CREDENTIAL_UNAVAILABLE") from None
        if not (stat.S_ISSOCK(mode) if kind == "socket" else stat.S_ISREG(mode)):
            raise SetupRefused("OPERATOR_CREDENTIAL_TYPE_DIFFERS")
    if any(
        not p.is_absolute() or not any(p.is_relative_to(m) for m in mounts)
        for p in required
    ):
        raise SetupRefused("OPERATOR_PATH_NOT_MOUNTED_IDENTICALLY")
    if any(
        type(raw[k]) is not int or raw[k] <= 0
        for k in ("sync_every_s", "weights_every_s")
    ):
        raise SetupRefused("EXPLICIT_OPERATOR_TIMER_PERIODS_REQUIRED")
    docker = [
        "/usr/bin/docker",
        "--host",
        "unix://" + str(socket),
        "run",
        "--rm",
        "--read-only",
        "--user",
        raw["user"],
        "--group-add",
        socket_group,
        "--workdir",
        str(artifact.root),
        "--env",
        "DOCKER_HOST=unix://" + str(socket),
        "--env",
        "HOME=" + home,
        "--mount",
        f"type=bind,source={PASSWD},target=/etc/passwd,readonly",
        "--mount",
        f"type=bind,source={artifact.root},target={artifact.root},readonly",
        "--mount",
        f"type=bind,source={socket},target={socket}",
    ]
    for mount in mounts:
        docker += ["--mount", f"type=bind,source={mount},target={mount}"]
    common = ["--bundle", str(artifact.root), "--digest", artifact.digest]
    commands = {
        "service": ["service", "supervise", *common, "--config", raw["service_config"]],
        "sync": [
            "sync",
            *common,
            "--service-config",
            raw["service_config"],
            "--config",
            raw["fetch_config"],
        ],
        "weights": [
            "weights",
            "run",
            *common,
            "--service-config",
            raw["service_config"],
            "--config",
            w["config"],
            "--standing",
            w["standing"],
            "--journal",
            w["journal"],
            "--ledger",
            w["ledger"],
            "--battery-deployment",
            w["deployment"],
        ],
    }
    if w["policy_version"] is not None:
        commands["weights"] += ["--policy-version", w["policy_version"]]
    result = {}
    for role, command in commands.items():
        name = raw["name"] + "-" + role
        kind = "simple" if role == "service" else "oneshot"
        result[name + ".service"] = (
            f"[Unit]\nDescription=Carbon {role} (operator image; not qualification)\nAfter=docker.service\n\n[Service]\nType={kind}\nExecStart={quoted([*docker, *(['--network', network['mode']] if role == 'service' else []), raw['image'], *command])}\n"
            + (
                "Restart=on-failure\nRestartPreventExitStatus=2\n"
                if role == "service"
                else ""
            )
            + "\n[Install]\nWantedBy=default.target\n"
        )
        if role != "service":
            period = raw[role + "_every_s"]
            result[
                name + ".timer"
            ] = f"[Unit]\nDescription=Carbon {role} operator cadence\n\n[Timer]\nOnActiveSec={period}s\nOnUnitInactiveSec={period}s\nUnit={name}.service\n\n[Install]\nWantedBy=timers.target\n"
    return result


def write(profile, destination):
    units = render(profile)
    destination = Path(destination)
    if (
        not destination.is_absolute()
        or destination.exists()
        or destination.is_symlink()
        or any(p.is_symlink() for p in destination.parents)
    ):
        raise SetupRefused("NEW_ABSOLUTE_UNIT_DIRECTORY_REQUIRED")
    destination.mkdir(mode=0o700)
    for name, text in units.items():
        target = destination / name
        target.write_text(text, encoding="utf-8", newline="\n")
        target.chmod(0o600)
    return {
        "status": "IMAGE_BACKED_OPERATOR_UNITS_WRITTEN_NOT_INSTALLED",
        "files": sorted(units),
        "qualification": "NOT_GRANTED",
    }
