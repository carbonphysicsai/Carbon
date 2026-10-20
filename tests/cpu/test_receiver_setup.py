"""The receiver setup tool writes the closed profile and configuration, privately.

Checks and the chain read are fixtures; no image, key or network is touched.
"""

from __future__ import annotations

import json
import stat

import pytest

from carbon.challenge_validator import direct_receiver, receiver_setup
from scripts.dev.miner_launchpad import installed

HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
MOTOR = {"id": "electric-motor-magnetics", "version": "1.0"}


class Checks:
    def compute(self, image, analysis):
        return {"implementation": {"revision": "r" * 40}, "images": ["a", "b"]}

    def network(self):
        return {"publisher_hotkey": HOTKEY, "context": {"netuid": 567}}, 4321


@pytest.fixture
def installed_state(tmp_path):
    state = tmp_path / "installed"
    state.mkdir(mode=0o700)
    manifests = []
    for name in ("worker.json", "analysis.json"):
        path = tmp_path / name
        path.write_text("{}")
        manifests.append(path)
    installed.write(
        state, image_manifest=manifests[0], analysis_image_manifest=manifests[1]
    )
    return state


@pytest.fixture
def faked(monkeypatch):
    from scripts.dev.miner_launchpad import runner

    monkeypatch.setattr(runner, "validated_profile", lambda profile: profile)
    monkeypatch.setattr(
        direct_receiver,
        "installed_source",
        lambda path: ({"revision": "r" * 40}, None, None, None),
    )


def _prepare(tmp_path, state, **extra):
    return receiver_setup.prepare(
        installed_state=state,
        receiver_state=tmp_path / "receiver-state",
        challenge=MOTOR,
        checks=Checks(),
        **extra,
    )


def test_prepare_writes_a_private_closed_configuration(
    tmp_path, installed_state, faked
):
    done = _prepare(tmp_path, installed_state)
    assert done["status"] == "RECEIVER_PROFILE_READY"
    config_path = tmp_path / "receiver-state" / "receiver" / "receiver.json"
    config = json.loads(config_path.read_bytes())
    assert config["host"] == "127.0.0.1" and config["challenge"] == MOTOR
    assert config["receiver_hotkey"] == HOTKEY
    assert "evaluation_pack" not in config
    for path in (
        config_path,
        tmp_path / "receiver-state/environment/runner-profile.json",
    ):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_prepare_selects_a_given_pack_and_refuses_a_bad_one(
    tmp_path, installed_state, faked
):
    bad = tmp_path / "no-pack"
    bad.mkdir()
    with pytest.raises(receiver_setup.SetupRefused, match="evaluation_pack_invalid"):
        _prepare(tmp_path, installed_state, pack=bad)
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "evaluation-pack.json").write_text("{}")
    done = _prepare(tmp_path, installed_state, pack=pack)
    assert done["evaluation_pack"] is True
    config = json.loads(
        (tmp_path / "receiver-state/receiver/receiver.json").read_bytes()
    )
    assert config["evaluation_pack"]["private_root"] == str(pack)


def test_prepare_refuses_an_install_with_no_recorded_images(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(receiver_setup.SetupRefused, match="images_not_installed"):
        _prepare(tmp_path, empty)


def test_prepare_does_not_overwrite_a_prepared_receiver_state(
    tmp_path, installed_state, faked
):
    _prepare(tmp_path, installed_state)
    with pytest.raises(receiver_setup.SetupRefused, match="receiver_state_in_use"):
        _prepare(tmp_path, installed_state)


def test_only_registered_lean_challenges_are_accepted():
    assert receiver_setup._challenge(
        **{"challenge_id": "chip-cold-plate", "version": "1.0"}
    )
    with pytest.raises(receiver_setup.SetupRefused, match="challenge_not_registered"):
        receiver_setup._challenge("anything-else", "1.0")


def test_start_needs_a_prepared_state(tmp_path):
    with pytest.raises(receiver_setup.SetupRefused, match="receiver_config_missing"):
        receiver_setup.start(tmp_path)


def test_a_receiver_with_no_configuration_names_the_missing_file(tmp_path, capsys):
    missing = tmp_path / "receiver.json"
    assert direct_receiver.main(["--config", str(missing)]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["unavailable"] == "receiver_config_missing"
    assert printed["config"] == str(missing)
    assert "receiver_setup prepare" in printed["next"]
