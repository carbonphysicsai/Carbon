"""Image-backed unit rendering and per-operator identity; no units installed."""

import json

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
        },
    )
    fetch = state / "fetch.json"
    fetch.write_text(
        json.dumps({"hotkey": "fixture-publisher", "deployment": str(deployment)}),
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
    return profile, value, fetch, state


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
