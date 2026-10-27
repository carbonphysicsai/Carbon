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
#: An outside validator's own hotkey (not Carbon's publisher).
OPERATOR = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
MOTOR = {"id": "electric-motor-magnetics", "version": "1.0"}


class Checks:
    def compute(self, image, analysis):
        return {"implementation": {"revision": "r" * 40}, "images": ["a", "b"]}

    def network(self):
        return {"publisher_hotkey": HOTKEY, "context": {"netuid": 567}}, 4321


class Permits:
    def __init__(self, answer):
        self.answer, self.asked = answer, []

    def read(self, hotkey):
        self.asked.append(hotkey)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


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

    # A built pack (--pack) is a development install's (E4 condition 2).
    monkeypatch.setattr(receiver_setup, "development_install", lambda *a, **k: True)

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
        **{"hotkey": HOTKEY, **extra},
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


def test_every_served_challenge_version_is_accepted_and_nothing_else():
    # E3: every Challenge the receiver serves, Battery included; not the
    # synthetic software fixture, and nothing unregistered.
    for challenge in receiver_setup.served():
        assert receiver_setup._challenge(challenge["id"], challenge["version"])
    assert {c["id"] for c in receiver_setup.served()} >= {
        "battery-fastcharge-ageing-development-v1",
        "electric-motor-magnetics",
        "chip-cold-plate",
        "f08-ribbed-bracket",
        "f02",
    }
    for refused in (("anything-else", "1.0"), ("synthetic-linear-field-2d", "1.3")):
        with pytest.raises(
            receiver_setup.SetupRefused, match="challenge_not_registered"
        ):
            receiver_setup._challenge(*refused)


def test_current_is_each_challenges_newest_served_version():
    current = receiver_setup.current()
    assert len({c["id"] for c in current}) == len(current)
    for challenge in current:
        assert challenge in receiver_setup.served()
        assert all(
            receiver_setup._version_key(other["version"])
            <= receiver_setup._version_key(challenge["version"])
            for other in receiver_setup.served()
            if other["id"] == challenge["id"]
        )


def test_the_receiver_is_the_operators_own_permit_holding_hotkey(
    tmp_path, installed_state, faked
):
    # E2: an outside validator's hotkey, with a validator permit now.
    holder = Permits({"permit": True, "block": 9})
    done = _prepare(tmp_path, installed_state, hotkey=OPERATOR, permits=holder)
    assert done["receiver_hotkey"] == OPERATOR and holder.asked == [OPERATOR]
    config = json.loads(
        (tmp_path / "receiver-state/receiver/receiver.json").read_bytes()
    )
    assert config["receiver_hotkey"] == OPERATOR
    assert config["lifetime_seconds"] is None  # E5: a service by default


@pytest.mark.parametrize(
    "answer, code",
    [
        (None, "hotkey_not_registered"),
        ({"permit": False, "block": 9}, "hotkey_no_validator_permit"),
    ],
)
def test_a_hotkey_without_a_permit_is_refused_before_anything_is_written(
    tmp_path, installed_state, faked, answer, code
):
    with pytest.raises(receiver_setup.SetupRefused, match=code):
        _prepare(tmp_path, installed_state, hotkey=OPERATOR, permits=Permits(answer))
    assert not (tmp_path / "receiver-state" / "environment").exists()


def test_an_unreadable_chain_or_a_malformed_hotkey_is_refused(
    tmp_path, installed_state, faked
):
    from carbon.chain.permits import PermitUnavailable

    with pytest.raises(receiver_setup.SetupRefused, match="permit_unreadable"):
        _prepare(
            tmp_path,
            installed_state,
            hotkey=OPERATOR,
            permits=Permits(PermitUnavailable("x")),
        )
    with pytest.raises(receiver_setup.SetupRefused, match="hotkey_invalid"):
        _prepare(tmp_path, installed_state, hotkey="my-wallet-name")


def test_start_needs_a_prepared_state(tmp_path):
    with pytest.raises(receiver_setup.SetupRefused, match="receiver_config_missing"):
        receiver_setup.start(tmp_path)


def _prepared_state(tmp_path):
    config = tmp_path / "receiver" / receiver_setup.CONFIG_NAME
    config.parent.mkdir(parents=True)
    config.write_text("{}")
    return tmp_path


@pytest.mark.parametrize("linger", ["no", "yes"])
def test_a_detached_start_refuses_without_linger(tmp_path, monkeypatch, linger):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv[0])
        stdout = linger + "\n" if argv[0] == "loginctl" else ""
        return type("Done", (), {"returncode": 0, "stdout": stdout})()

    monkeypatch.setattr(receiver_setup.subprocess, "run", run)
    state = _prepared_state(tmp_path)
    if linger == "no":
        with pytest.raises(receiver_setup.SetupRefused) as refused:
            receiver_setup.start(state, detach=True)
        assert refused.value.code == "receiver_linger_off"
        assert "loginctl enable-linger" in str(refused.value)
        assert calls == ["loginctl"]  # nothing was started
    else:
        assert receiver_setup.start(state, detach=True) == 0
        assert calls == ["loginctl", "systemd-run"]


def test_a_detached_start_proceeds_when_loginctl_cannot_say(tmp_path, monkeypatch):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv[0])
        if argv[0] == "loginctl":
            raise FileNotFoundError("loginctl")
        return type("Done", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(receiver_setup.subprocess, "run", run)
    assert receiver_setup.start(_prepared_state(tmp_path), detach=True) == 0
    assert calls == ["loginctl", "systemd-run"]


def test_a_receiver_with_no_configuration_names_the_missing_file(tmp_path, capsys):
    missing = tmp_path / "receiver.json"
    assert direct_receiver.main(["--config", str(missing)]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["unavailable"] == "receiver_config_missing"
    assert printed["config"] == str(missing)
    assert "receiver_setup prepare" in printed["next"]


class Run:
    """systemctl/loginctl, recorded; `fail` names a systemctl verb that fails."""

    def __init__(self, *, linger="yes", active="active", fail=None):
        self.calls, self.linger, self.active, self.fail = [], linger, active, fail

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if argv[0] == "loginctl":
            stdout = self.linger + "\n"
        elif argv[:3] == ["systemctl", "--user", "is-active"]:
            stdout = self.active + "\n"
        else:
            stdout = ""
        failed = self.fail is not None and self.fail in argv
        return type("Done", (), {"returncode": 1 if failed else 0, "stdout": stdout})()


def _pack(tmp_path):
    pack = tmp_path / "pack"
    pack.mkdir(exist_ok=True)
    (pack / "evaluation-pack.json").write_text("{}")
    return pack


def test_service_installs_a_restarting_user_unit_and_enables_it(
    tmp_path, installed_state, faked, monkeypatch
):
    # E5: a persistent service, restarted on failure and after a reboot.
    _prepare(tmp_path, installed_state, pack=_pack(tmp_path))
    state = tmp_path / "receiver-state"
    run = Run()
    monkeypatch.setattr(receiver_setup.subprocess, "run", run)
    units = tmp_path / "units"
    done = receiver_setup.service(state, unit_dir=units, run=run)
    unit = receiver_setup.unit_name(state)
    assert done["status"] == "RECEIVER_SERVICE_ENABLED" and done["unit"] == unit
    text = (units / (unit + ".service")).read_text()
    assert "Restart=on-failure" in text and "WantedBy=default.target" in text
    assert "carbon.challenge_validator.direct_receiver --config" in text
    assert ["systemctl", "--user", "enable", "--now", unit + ".service"] in run.calls


def test_service_refuses_a_finite_receiver_no_linger_or_a_failed_enable(
    tmp_path, installed_state, faked, monkeypatch
):
    _prepare(tmp_path, installed_state, lifetime_seconds=7200, pack=_pack(tmp_path))
    finite = tmp_path / "receiver-state"
    with pytest.raises(receiver_setup.SetupRefused, match="service_has_lifetime"):
        receiver_setup.service(finite, unit_dir=tmp_path / "u", run=Run())
    other = tmp_path / "other"
    other.mkdir()
    receiver_setup.prepare(
        installed_state=installed_state,
        receiver_state=other / "state",
        challenge=MOTOR,
        checks=Checks(),
        hotkey=HOTKEY,
        pack=_pack(tmp_path),
    )
    lingerless = Run(linger="no")
    monkeypatch.setattr(receiver_setup.subprocess, "run", lingerless)
    with pytest.raises(receiver_setup.SetupRefused, match="receiver_linger_off"):
        receiver_setup.service(other / "state", unit_dir=tmp_path / "u", run=lingerless)
    failing = Run(fail="enable")
    monkeypatch.setattr(receiver_setup.subprocess, "run", failing)
    with pytest.raises(
        receiver_setup.SetupRefused, match="receiver_service_not_started"
    ):
        receiver_setup.service(other / "state", unit_dir=tmp_path / "u", run=failing)


def test_status_reports_service_intake_exam_and_last_graded(
    tmp_path, installed_state, faked
):
    # E7: read-only; healthy only when the service is active, the intake
    # answers and the receiver holds its exam.
    _prepare(tmp_path, installed_state, pack=_pack(tmp_path))
    state = tmp_path / "receiver-state"
    healthy = receiver_setup.status(
        state, run=Run(), fetch=lambda url: {"schema": "intake"}
    )
    assert healthy["status"] == "RECEIVER_HEALTHY"
    assert (healthy["service"], healthy["intake"]) == ("active", "LISTENING")
    assert healthy["challenge"] == MOTOR and healthy["receiver_hotkey"] == HOTKEY
    assert (healthy["graded"], healthy["last_graded_unix"]) == (0, None)
    assert healthy["exam"] == "SELECTED"

    def unreachable(url):
        raise OSError("refused")

    down = receiver_setup.status(state, run=Run(active="inactive"), fetch=unreachable)
    assert down["status"] == "RECEIVER_NOT_HEALTHY"
    assert (down["service"], down["intake"]) == ("inactive", "UNREACHABLE")


def test_status_counts_graded_submissions_from_the_receivers_own_ledger(
    tmp_path, installed_state, faked
):
    from carbon.challenge_validator import exam_cap
    from carbon.challenge_validator.ledger import AttemptLedger

    _prepare(tmp_path, installed_state)
    state = tmp_path / "receiver-state"
    root = state / "receiver" / "state"
    root.mkdir(mode=0o700)
    cap = exam_cap.ExamCap(
        AttemptLedger(root / "attempts.sqlite3"),
        cadence={
            "capacity_cpu_hours_per_day": 270.0,
            "rebuild_cpu_hours_placeholder": {MOTOR["id"]: 1.0},
        },
        clock=lambda: 5_000_000_000_000,
    )
    slot = cap.reserve(
        hotkey=HOTKEY,
        challenge_id=MOTOR["id"],
        challenge_version=MOTOR["version"],
        exam_key="sha256:" + "1" * 64,
        submission_id="rtsk_1",
        block=360,
    )
    cap.settle(slot, "SCORED_DEVELOPMENT_CANDIDATE")
    found = receiver_setup.status(state, run=Run(), fetch=lambda url: {})
    assert (found["graded"], found["last_graded_unix"]) == (1, 5000)


def test_a_receiver_without_an_exam_never_becomes_a_service(
    tmp_path, installed_state, faked, monkeypatch
):
    # Validator, E4 (c): it would spend miners' epoch slots on nothing.
    _prepare(tmp_path, installed_state)
    state = tmp_path / "receiver-state"
    run = Run()
    monkeypatch.setattr(receiver_setup.subprocess, "run", run)
    with pytest.raises(receiver_setup.SetupRefused, match="evaluation_pack_missing"):
        receiver_setup.service(state, unit_dir=tmp_path / "u", run=run)
    assert run.calls == []  # nothing was installed or started
    shown = receiver_setup.status(state, run=Run(), fetch=lambda url: {})
    assert shown["status"] == "RECEIVER_NOT_HEALTHY"
    assert shown["exam"] == "evaluation_pack_missing"


def test_a_built_pack_needs_an_explicit_development_install(
    tmp_path, installed_state, faked, monkeypatch
):
    # Validator, E4 condition 2: an operator-built pack never serves as an
    # official exam; nothing is written.
    monkeypatch.setattr(receiver_setup, "development_install", lambda *a, **k: False)
    with pytest.raises(
        receiver_setup.SetupRefused, match="built_packs_development_only"
    ):
        _prepare(tmp_path, installed_state, pack=_pack(tmp_path))
    assert not (tmp_path / "receiver-state" / "environment").exists()


def test_an_install_without_a_development_pin_is_not_a_development_install(
    installed_state,
):
    assert receiver_setup.development_install(installed_state) is False


def test_status_shows_auto_grade_failures_to_the_operator(
    tmp_path, installed_state, faked
):
    # Validator (via the Test Engineer): a FAILED auto-grade marker shows.
    _prepare(tmp_path, installed_state, pack=_pack(tmp_path))
    state = tmp_path / "receiver-state"
    quiet = receiver_setup.status(state, run=Run(), fetch=lambda url: {})
    assert "auto_grade_failed" not in quiet  # no auto-grade: nothing added
    markers = state / "receiver" / "state" / "auto-grade" / "markers"
    markers.mkdir(parents=True)
    (markers / "a.json").write_text(json.dumps({"state": "FAILED", "code": "x_code"}))
    (markers / "b.json").write_text(json.dumps({"state": "GRADED"}))
    shown = receiver_setup.status(state, run=Run(), fetch=lambda url: {})
    assert shown["auto_grade_failed"] == 1
    assert shown["auto_grade_last_failure"] == "x_code"


def test_prepare_records_the_speed_sample_key_file_and_refuses_a_bad_one(
    tmp_path, installed_state, faked
):
    """The pool versions' K_speed (written beside the signed copy by the issuance job) is recorded in the
    configuration; it must be an exact private file, and nothing but its path is stored.
    """
    key = tmp_path / "k.speed-key"
    key.write_bytes(bytes(range(32)))
    key.chmod(0o600)
    open_key = tmp_path / "open.speed-key"
    open_key.write_bytes(bytes(range(32)))
    open_key.chmod(0o644)
    for bad in (open_key, tmp_path / "missing.speed-key"):
        with pytest.raises(
            receiver_setup.SetupRefused, match="speed_sample_key_file_invalid"
        ):
            _prepare(tmp_path, installed_state, speed_sample_key_file=bad)
        assert not (tmp_path / "receiver-state").exists()
    done = _prepare(tmp_path, installed_state, speed_sample_key_file=key)
    assert done["status"] == "RECEIVER_PROFILE_READY"
    path = tmp_path / "receiver-state/receiver/receiver.json"
    config = json.loads(path.read_bytes())
    assert config["speed_sample_key_file"] == str(key)
    assert bytes(range(32)).hex() not in path.read_text()
    assert direct_receiver._speed_key(config) == bytes(range(32))


def test_prepare_without_the_key_file_records_none(tmp_path, installed_state, faked):
    _prepare(tmp_path, installed_state)
    config = json.loads(
        (tmp_path / "receiver-state/receiver/receiver.json").read_bytes()
    )
    assert "speed_sample_key_file" not in config
    assert direct_receiver._speed_key(config) is None
