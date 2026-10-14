"""Render explicit image-backed operator units; never install or start them."""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path

from .bundle import SetupRefused, verify
from .weights import load_config as load_weights

SCHEMA = "carbon.validator-runtime-units.v1"


def quoted(argv):
    # systemd ExecStart parses arguments itself; no shell is involved. Prevent
    # specifier/environment expansion of an operator-provided literal path.
    return " ".join(
        json.dumps(str(a).replace("%", "%%").replace("$", "$$")) for a in argv
    )


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
        or socket.is_symlink()
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
    required = [
        Path(raw["service_config"]),
        Path(raw["fetch_config"]),
        Path(service.state_dir),
        Path(service.backups),
        Path(service.intake_path),
        Path(intake["deployment"]),
        Path(intake["inbox"]),
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
        "--workdir",
        str(artifact.root),
        "--env",
        "DOCKER_HOST=unix://" + str(socket),
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
            result[name + ".timer"] = (
                f"[Unit]\nDescription=Carbon {role} operator cadence\n\n[Timer]\nOnActiveSec={period}s\nOnUnitInactiveSec={period}s\nUnit={name}.service\n\n[Install]\nWantedBy=timers.target\n"
            )
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
