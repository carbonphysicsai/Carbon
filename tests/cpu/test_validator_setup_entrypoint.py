"""Operator route controls; public fixtures do not earn installed/HTTPS parity."""

import argparse
import json
from types import SimpleNamespace

import pytest
from test_validator_setup_bundle import source

from carbon.validator_setup import __main__ as cli
from carbon.validator_setup import bundle as b


def test_verification_is_not_qualification_and_foreign_executed_source_cannot_start(
    tmp_path, capsys
):
    repo, revision = source(tmp_path)
    bundle = b.materialize(repo, revision, tmp_path / "release")
    assert (
        cli.main(["verify", "--bundle", str(bundle.root), "--digest", bundle.digest])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["qualification"] == "NOT_GRANTED"
    assert (
        cli.main(
            [
                "service",
                "preflight",
                "--bundle",
                str(bundle.root),
                "--digest",
                bundle.digest,
                "--config",
                str(tmp_path / "private-marker.json"),
            ]
        )
        == 2
    )
    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "REFUSED", "reason": "EXECUTED_SOURCE_NOT_BOUND_BUNDLE"}
    assert not (tmp_path / "private-marker.json").exists()


@pytest.mark.parametrize("import_only", [False, True])
def test_fresh_remote_initialization_uses_explicit_init_open_and_never_local_draw(
    tmp_path, monkeypatch, import_only
):
    from carbon.battery import deployment, operate

    calls = []
    monkeypatch.setattr(
        deployment,
        "load_config",
        lambda _path: {"batch_source": "answer_key" if import_only else "local"},
    )
    monkeypatch.setattr(operate, "init", lambda *_args, **_kwargs: calls.append("init"))

    class Target:
        def open_pool(self):
            calls.append("open")
            return {"status": "ROTATION_PENDING"}

    monkeypatch.setattr(deployment, "validator", lambda *_args, **_kwargs: Target())
    args = argparse.Namespace(config=tmp_path / "fixture.json")
    artifact = SimpleNamespace(root=tmp_path)
    if import_only:
        result = cli.initialize(args, artifact)
        assert calls == ["init", "open"]
        assert (
            result["pool"] == "ROTATION_PENDING" and result["evaluation_ready"] is False
        )
    else:
        with pytest.raises(
            b.SetupRefused, match="REMOTE_VALIDATOR_REQUIRES_SHARED_ANSWER_KEY"
        ):
            cli.initialize(args, artifact)
        assert calls == []


def test_runtime_lease_releases_on_exception_and_mutual_exclusion_is_real(
    tmp_path, monkeypatch
):
    from scripts.dev.battery_validator_service import service

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    monkeypatch.setattr(
        service, "load_service", lambda _path: SimpleNamespace(state_dir=state)
    )
    with pytest.raises(RuntimeError), b.runtime_lease(tmp_path / "fixture.json"):
        with (
            pytest.raises(
                b.SetupRefused, match="OPERATOR_RUNTIME_OR_RELEASE_SWITCH_ACTIVE"
            ),
            b.held_lock(state / "operator-runtime.lock", exclusive=True),
        ):
            pytest.fail("exclusive update must refuse during operation")
        raise RuntimeError("fixture exception")
    with b.held_lock(state / "operator-runtime.lock", exclusive=True):
        pass


@pytest.mark.parametrize(
    "action,ready,code",
    [
        ("preflight", False, 2),
        ("preflight", True, 0),
        ("status", False, 3),
        ("status", True, 0),
    ],
)
def test_service_route_preserves_refusal_and_unhealthy_exit_codes(
    tmp_path, monkeypatch, action, ready, code
):
    from scripts.dev.battery_validator_service import service

    monkeypatch.setattr(service, "preflight", lambda *_a, **_k: {"ready": ready})
    monkeypatch.setattr(service, "status", lambda *_a, **_k: {"healthy": ready})
    args = argparse.Namespace(
        command="service", action=action, config=tmp_path / "fixture.json"
    )
    returned, _ = cli.delegate(args, SimpleNamespace(root=tmp_path))
    assert returned == code
