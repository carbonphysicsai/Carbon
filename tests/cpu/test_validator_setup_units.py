"""Image-backed unit rendering and per-operator identity; no units installed."""

import json
import os
import shlex
import socket
from pathlib import Path

import pytest
from test_validator_setup_bundle import source
from test_validator_setup_weights import config

from carbon.validator_setup import bundle, units
from carbon.validator_setup.bundle import SetupRefused


def arrangement(tmp_path, monkeypatch):
    from scripts.dev.battery_validator_service import service

    repo, revision = source(tmp_path)
    artifact = bundle.materialize(repo, revision, tmp_path / "release")
    state = tmp_path / "operator-state"
    state.mkdir(mode=0o700)
    backups = state / "backups"
    backups.mkdir(mode=0o700)
    weights, _ = config(state)
    deployment = state / "deployment.json"
    intake = state / "intake.json"
    svc = state / "service.json"
    svc.write_text(
        json.dumps(
            {
                "schema": service.SCHEMA,
                "intake": str(intake),
                "state_dir": str(state),
                "backups": str(backups),
            }
        ),
        encoding="utf-8",
    )
    svc.chmod(0o600)
    monkeypatch.setattr(
        service,
        "_intake",
        lambda *_args: {
            "receiver": "fixture-publisher",
            "deployment": str(deployment),
            "inbox": str(state / "inbox.sqlite3"),
            "host": "127.0.0.1",
            "port": 8467,
        },
    )
    fetch = state / "fetch.json"
    signer = state / "signer.sock"
    with monkeypatch.context() as local:
        local.chdir(state)
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind("signer.sock")
    fetch.write_text(
        json.dumps(
            {
                "schema": "carbon.challenge-validator.answer-key-fetch-config.v1",
                "url": "https://fixture.invalid",
                "receiver": "fixture-producer",
                "producer_public_key": "synthetic-public-key",
                "challenge_id": "synthetic-challenge",
                "hotkey": "fixture-publisher",
                "deployment": str(deployment),
                "signer_socket": str(signer),
            }
        ),
        encoding="utf-8",
    )
    fetch.chmod(0o600)
    value = {
        "schema": units.SCHEMA,
        "name": "fixture-validator",
        "bundle": str(artifact.root),
        "digest": artifact.digest,
        "image": "ghcr.io/public-fixture/operator@sha256:" + "a" * 64,
        "user": "1000:1000",
        "docker_socket": str(state / "docker.sock"),
        "service_network": {
            "mode": "host",
            "listener_host": "127.0.0.1",
            "listener_port": 8467,
            "proxy_peer": None,
        },
        "state_mounts": [str(state)],
        "service_config": str(svc),
        "fetch_config": str(fetch),
        "weights": {
            "config": str(weights),
            "standing": str(state / "standing.json"),
            "journal": str(state / "publication.sqlite3"),
            "ledger": str(state / "winner.jsonl"),
            "deployment": str(deployment),
            "policy_version": None,
        },
        "sync_every_s": 60,
        "weights_every_s": 60,
    }
    profile = state / "units.json"
    profile.write_text(json.dumps(value), encoding="utf-8")
    profile.chmod(0o600)
    with monkeypatch.context() as local:
        local.chdir(state)
        with socket.socket(socket.AF_UNIX) as docker_socket:
            docker_socket.bind("docker.sock")
    (state / "docker.sock").chmod(0o660)
    return profile, value, fetch, state


@pytest.mark.parametrize("gid", [413, 23456])
def test_observed_socket_group_reaches_every_role_without_changing_primary_identity(
    tmp_path, monkeypatch, gid
):
    profile, raw, _fetch, _state = arrangement(tmp_path, monkeypatch)
    endpoint = Path(raw["docker_socket"])
    original = Path.lstat
    info = list(original(endpoint))
    info[5] = gid
    observed = os.stat_result(info)
    monkeypatch.setattr(
        Path,
        "lstat",
        lambda path, *a, **kw: (
            observed if path == endpoint else original(path, *a, **kw)
        ),
    )
    rendered = units.render(profile)
    for role in ("service", "sync", "weights"):
        start = next(
            line.removeprefix("ExecStart=")
            for line in rendered[f"fixture-validator-{role}.service"].splitlines()
            if line.startswith("ExecStart=")
        )
        argv = shlex.split(start)
        assert argv[argv.index("--user") + 1] == raw["user"]
        assert argv.count("--group-add") == 1
        assert argv[argv.index("--group-add") + 1] == str(gid)
        assert "--privileged" not in argv
        assert raw["image"] in argv


@pytest.mark.parametrize("bad", ["missing", "file", "directory", "symlink", "denied"])
def test_invalid_socket_metadata_refuses_before_any_units_are_written(
    tmp_path, monkeypatch, bad
):
    profile, raw, _fetch, state = arrangement(tmp_path, monkeypatch)
    endpoint = Path(raw["docker_socket"])
    if bad == "denied":
        original = Path.lstat

        def denied(path, *a, **kw):
            if path == endpoint:
                raise PermissionError("private-marker-not-for-output")
            return original(path, *a, **kw)

        monkeypatch.setattr(Path, "lstat", denied)
    else:
        endpoint.unlink()
        if bad == "file":
            endpoint.write_bytes(b"not-a-socket")
        elif bad == "directory":
            endpoint.mkdir()
        elif bad == "symlink":
            endpoint.symlink_to(state / "signer.sock")
    with pytest.raises(SetupRefused, match="^DOCKER_SOCKET_") as refused:
        units.write(profile, tmp_path / "not-written")
    assert "private-marker" not in str(refused.value)
    assert not (tmp_path / "not-written").exists()


@pytest.mark.parametrize("owner", [True, False])
def test_socket_write_permission_matches_configured_uid_not_rendering_process(
    tmp_path, monkeypatch, owner
):
    profile, raw, _fetch, _state = arrangement(tmp_path, monkeypatch)
    endpoint = Path(raw["docker_socket"])
    uid = endpoint.stat().st_uid + (0 if owner else 1)
    raw["user"] = f"{uid}:23457"
    profile.write_text(json.dumps(raw), encoding="utf-8")
    endpoint.chmod(0o460 if owner else 0o640)
    with pytest.raises(SetupRefused, match="DOCKER_SOCKET_IDENTITY_NOT_WRITABLE"):
        units.write(profile, tmp_path / "not-written")
    assert not (tmp_path / "not-written").exists()
    endpoint.chmod(0o600 if owner else 0o660)
    assert len(units.render(profile)) == 5


def test_public_profile_permissions_refuse_before_unit_output(tmp_path, monkeypatch):
    from scripts.dev.battery_validator_service.service import ServiceRefused

    profile, _raw, _fetch, _state = arrangement(tmp_path, monkeypatch)
    profile.chmod(0o644)
    with pytest.raises(ServiceRefused, match="runtime_units_profile_not_owner_only"):
        units.write(profile, tmp_path / "not-written")
    assert not (tmp_path / "not-written").exists()


def test_all_three_roles_use_same_bound_image_and_operator_route_with_explicit_paths(
    tmp_path, monkeypatch
):
    profile, raw, _fetch, state = arrangement(tmp_path, monkeypatch)
    rendered = units.render(profile)
    assert len(rendered) == 5
    for role in ("service", "sync", "weights"):
        text = rendered["fixture-validator-" + role + ".service"]
        assert raw["image"] in text and raw["digest"] in text
        assert "target=" + str(state) in text and "source=" + raw["bundle"] in text
        if role != "service":
            assert '"--service-config"' in text
        else:
            assert "supervise" in text
            assert '"--network" "host"' in text
        if role != "service":
            assert '"--network" "host"' not in text
        assert "DOCKER_HOST=unix://" + raw["docker_socket"] in text
        assert "private_key" not in text
    result = units.write(profile, tmp_path / "generated")
    assert result["status"] == "IMAGE_BACKED_OPERATOR_UNITS_WRITTEN_NOT_INSTALLED"
    assert result["qualification"] == "NOT_GRANTED"
    with pytest.raises(SetupRefused):
        units.write(profile, tmp_path / "generated")


@pytest.mark.parametrize("bad", ["receiver", "mount", "tag", "period", "extra"])
def test_substituted_identity_missing_mount_tag_or_unspecified_cadence_refuses_before_output(
    tmp_path, monkeypatch, bad
):
    profile, raw, fetch, _state = arrangement(tmp_path, monkeypatch)
    if bad == "receiver":
        changed = json.loads(fetch.read_bytes())
        changed["hotkey"] = "different-validator"
        fetch.write_text(json.dumps(changed), encoding="utf-8")
    elif bad == "mount":
        raw["state_mounts"] = [str(tmp_path / "source")]
    elif bad == "tag":
        raw["image"] = "fixture:latest"
    elif bad == "period":
        raw["sync_every_s"] = None
    else:
        raw["miner_api_key"] = "synthetic-private-marker"
    profile.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SetupRefused):
        units.write(profile, tmp_path / "never-written")
    assert not (tmp_path / "never-written").exists()


@pytest.mark.parametrize("bad", ["missing", "bridge", "host", "port", "proxy_peer"])
def test_unbound_listener_or_proxy_namespace_refuses(tmp_path, monkeypatch, bad):
    from scripts.dev.battery_validator_service import service

    profile, raw, _fetch, _state = arrangement(tmp_path, monkeypatch)
    intake = service._intake(None, None)
    intake["exposure"] = {
        "via": "trusted_proxy",
        "header": "CF-Connecting-IP",
        "record": "OWNER-FIXTURE-INTAKE-EXPOSURE-99",
    }
    monkeypatch.setattr(service, "_intake", lambda *_args: intake)
    raw["service_network"]["proxy_peer"] = "127.0.0.1"
    if bad == "missing":
        del raw["service_network"]
    else:
        field, value = {
            "bridge": ("mode", "bridge"),
            "host": ("listener_host", "0.0.0.0"),
            "port": ("listener_port", 1),
            "proxy_peer": ("proxy_peer", "172.17.0.1"),
        }[bad]
        raw["service_network"][field] = value
    profile.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SetupRefused):
        units.write(profile, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def materials(tmp_path, monkeypatch):
    from scripts.dev.battery_validator_service import service

    profile, raw, fetch, state = arrangement(tmp_path, monkeypatch)
    intake = service._intake(None, None)
    for field in ("tls_cert", "tls_key"):
        target = state / field
        target.write_bytes(b"public-synthetic-material-not-a-real-credential")
        target.chmod(0o600)
        intake[field] = str(target)
    ca = state / "producer-ca.pem"
    ca.write_bytes(b"public-synthetic-ca")
    ca.chmod(0o600)
    body = json.loads(fetch.read_bytes())
    body["ca"] = str(ca)
    fetch.write_text(json.dumps(body), encoding="utf-8")
    monkeypatch.setattr(service, "_intake", lambda *_args: intake)
    return profile, raw, fetch, state, intake


def test_explicit_signer_ca_and_tls_paths_under_identical_mount_are_prepared(
    tmp_path, monkeypatch
):
    profile, _raw, _fetch, _state, _intake = materials(tmp_path, monkeypatch)
    assert len(units.render(profile)) == 5


@pytest.mark.parametrize("field", ["signer_socket", "ca", "tls_cert", "tls_key"])
@pytest.mark.parametrize("bad", ["outside_mount", "missing", "wrong_type", "symlink"])
def test_signer_ca_tls_path_requires_real_correct_type_and_identical_mount(
    tmp_path, monkeypatch, field, bad
):
    profile, _raw, fetch, state, intake = materials(tmp_path, monkeypatch)
    body = json.loads(fetch.read_bytes())
    target = (
        tmp_path / "not-mounted" if bad == "outside_mount" else state / "bad-material"
    )
    if bad == "wrong_type":
        if field == "signer_socket":
            target.write_bytes(b"not-a-socket")
        else:
            target.mkdir()
    elif bad == "symlink":
        target.symlink_to(state / "producer-ca.pem")
    if field in ("signer_socket", "ca"):
        body[field] = str(target)
        fetch.write_text(json.dumps(body), encoding="utf-8")
    else:
        intake[field] = str(target)
    with pytest.raises(SetupRefused, match="^OPERATOR_CREDENTIAL_"):
        units.write(profile, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("value", [None, "", "relative.sock"])
def test_signer_home_fallback_is_never_an_image_route(tmp_path, monkeypatch, value):
    profile, _raw, fetch, _state = arrangement(tmp_path, monkeypatch)
    body = json.loads(fetch.read_bytes())
    if value is None:
        del body["signer_socket"]
    else:
        body["signer_socket"] = value
    fetch.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(SetupRefused):
        units.render(profile)
