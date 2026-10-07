"""`onboard` over scripted commands (VALIDATOR-20).

Every command `onboard` runs is answered by a scripted runner shaped like the
real CLI's output. No producer, solver, chain or systemd is touched. The
checks are order, resume, idempotence, owner stops, refusal mapping, state
and code pinning, and that only named public values are kept.
"""

from __future__ import annotations

import json

import pytest

from carbon.challenge_validator import onboard as ob
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

#: A private-looking value every scripted output carries: it must never reach
#: the state file or the summary.
SECRET = "PRIVATE-CASE-INPUT-0x5eed"


class Script:
    """Answers each command by `(module, subcommand)`, or `systemctl` and its
    query. `queue` overrides a key with answers consumed in order."""

    def __init__(self, queue=None, fail_at=None):
        self.queue = {k: list(v) for k, v in (queue or {}).items()}
        self.calls = []
        self.fail_at = fail_at

    @staticmethod
    def key(argv):
        if argv[0] == "systemctl":
            return ("systemctl", argv[1])
        return (argv[2], argv[3])

    def __call__(self, argv, *, cwd):
        key = self.key(argv)
        self.calls.append(key)
        if self.fail_at is not None and len(self.calls) == self.fail_at:
            raise KeyboardInterrupt
        if self.queue.get(key):
            answer = self.queue[key].pop(0)
        else:
            answer = DEFAULT.get(key, {"ok": True})
        if type(answer) is tuple:
            return answer
        if type(answer) is str:
            return 0, answer
        return (2 if ob._refusal(answer) else 0), json.dumps(
            {**answer, "private": SECRET}
        )


OP, PR, AK = (
    "carbon.battery.operate",
    "carbon.challenge_validator.producer",
    ("carbon.challenge_validator.answer_key"),
)
TU, CO, ST = (
    "carbon.challenge_validator.tuning",
    "carbon.challenge_validator.confirmation",
    "carbon.challenge_validator.study_sets",
)
DEFAULT = {
    (OP, "truth-verify"): {"verified": True},
    (OP, "status"): {"pool": "OPEN"},
    (OP, "init"): {
        "root_commitment": "sha256:" + "a" * 64,
        "seed_pin": "sha256:" + "b" * 64,
    },
    (PR, "tick"): {BATTERY_CHALLENGE: {"filled": [1], "unfilled": [], "block": 5}},
    (AK, "import"): {
        "packages": [{"state": "IMPORTED", "fingerprint": "sha256:" + "c" * 64}]
    },
    (PR, "status"): {"challenges": {BATTERY_CHALLENGE: {"published": 2}}},
    (CO, "seal"): {
        "commitment": {"fingerprint": "sha256:" + "d" * 64, "journal_sequence": 21},
        "inputs": SECRET,
    },
    (TU, "quiz-refine"): {"round": 1, "refine_jobs": 140},
    (TU, "quiz-select"): {
        "digest": "sha256:" + "e" * 64,
        "q2_cases": 80,
        "q3_scenarios": 8,
    },
    (TU, "quiz-seal"): {"digest": "sha256:" + "e" * 64, "journal_sequence": 22},
    (ST, "init"): {
        "root_commitment": "sha256:" + "f" * 64,
        "seed_pin": "sha256:" + "1" * 64,
    },
    (ST, "ingest"): {"set": "x", "state": "COMPLETE", "cases": 10},
    (ST, "manifest"): {
        "fingerprint": "sha256:" + "2" * 64,
        "cases": 10,
        "journal_sequence": 3,
    },
    ("systemctl", "is-enabled"): "enabled",
    ("systemctl", "is-active"): "active",
    ("systemctl", "show"): "success",
}


def private_file(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path


@pytest.fixture
def inputs(tmp_path):
    etc = tmp_path / "etc"
    deployment = private_file(etc / "deployment.json", {})
    producer = private_file(etc / "producer.json", {})
    panel = private_file(etc / "panel.json", {})
    prior = private_file(etc / "ev5.json", {})
    spec = private_file(etc / "study-spec.json", {})
    return private_file(
        etc / "onboard.json",
        {
            "schema": ob.INPUTS_SCHEMA,
            "challenge_id": BATTERY_CHALLENGE,
            "deployment": str(deployment),
            "overlay": str(tmp_path / "overlay"),
            "producer_config": str(producer),
            "dev_pool": {
                "producer_public_key": "ab" * 32,
                "outbox": str(tmp_path / "out"),
            },
            "tuning": {
                "role": "graphite-tuning-v2",
                "pool_prior": "graphite-hidden-battery-v1-pool",
                "pool_export": str(etc / "hidden-pool.json"),
                "priors": {"ev5-confirmation": str(prior)},
                "quiz_work": str(tmp_path / "quiz"),
                "quiz_panel": str(panel),
            },
            "study": {"spec": str(spec)},
            "units": {
                "timers": ["carbon-producer.timer"],
                "push": "carbon-push.service",
            },
        },
    )


def run(inputs, tmp_path, script, **options):
    options.setdefault("commit", "c" * 40)
    return ob.onboard(
        BATTERY_CHALLENGE,
        inputs,
        tmp_path / "state",
        runner=script,
        python="python",
        **options,
    )


def state(tmp_path):
    return json.loads((tmp_path / "state" / ob.STATE_FILE).read_text())


def test_every_stage_runs_in_order_and_keeps_only_public_values(inputs, tmp_path):
    script = Script()
    summary = run(inputs, tmp_path, script, study=True)
    assert list(summary["stages"]) == [
        "truth",
        "deployment",
        "pool",
        "tuning",
        "study",
        "verify",
    ]
    order = [key[1] for key in script.calls]
    assert order.index("truth-verify") < order.index("tick") < order.index("seal")
    assert order.index("quiz-seal") < order.index("is-enabled")
    send = summary["send_back"]
    assert send["tuning/seal"] == {
        "fingerprint": "sha256:" + "d" * 64,
        "journal_sequence": 21,
    }
    assert send["tuning/quiz-seal"]["journal_sequence"] == 22
    assert send["tuning/quiz-refine-r1a0"] == {"round": 1, "refine_jobs": 140}
    assert send["study/manifest-train"]["journal_sequence"] == 3
    stored = (tmp_path / "state" / ob.STATE_FILE).read_text()
    assert SECRET not in stored and SECRET not in json.dumps(summary)
    assert (tmp_path / "state" / ob.STATE_FILE).stat().st_mode & 0o077 == 0


def test_a_rerun_does_no_work_but_its_reads_and_checks(inputs, tmp_path):
    run(inputs, tmp_path, Script(), study=True)
    again = Script()
    run(inputs, tmp_path, again, study=True)
    assert set(again.calls) == {
        (OP, "truth-verify"),
        (OP, "status"),
        (PR, "status"),
        ("systemctl", "is-enabled"),
        ("systemctl", "is-active"),
        ("systemctl", "show"),
    }


@pytest.mark.parametrize("cut", range(1, 30, 3))
def test_a_killed_run_resumes_to_the_same_state(inputs, tmp_path, cut):
    whole = tmp_path / "whole"
    whole.mkdir()
    run(inputs, whole, Script(), study=True)
    with pytest.raises(KeyboardInterrupt):
        run(inputs, tmp_path, Script(fail_at=cut), study=True)
    run(inputs, tmp_path, Script(), study=True)
    assert state(tmp_path)["steps"].keys() == state(whole)["steps"].keys()


def test_a_missing_truth_environment_is_materialized_first(inputs, tmp_path):
    script = Script({(OP, "truth-verify"): [{"refused": "truth_overlay_missing"}]})
    run(inputs, tmp_path, script)
    calls = [k[1] for k in script.calls]
    assert calls[:3] == ["truth-verify", "truth-materialize", "truth-verify"]


def test_an_uninitialized_deployment_is_initialized_and_sent_back(inputs, tmp_path):
    script = Script({(OP, "status"): [{"unavailable": "root_missing"}]})
    summary = run(inputs, tmp_path, script)
    assert summary["send_back"]["deployment/init"]["seed_pin"] == "sha256:" + "b" * 64


def test_quiz_rounds_and_refine_retries_follow_the_select(inputs, tmp_path):
    script = Script(
        {
            (TU, "quiz-select"): [
                {"status": "REFUSED", "reason": "tuning_quiz_needs_more_q3:--round 2"},
                {"status": "REFUSED", "reason": "tuning_quiz_needs_refine"},
            ]
        }
    )
    run(inputs, tmp_path, script)
    steps = state(tmp_path)["steps"]
    assert "tuning/quiz-jobs-r2" in steps
    assert "tuning/solve-r2a1" in steps and "tuning/quiz-select-r2a1" in steps
    assert "tuning/quiz-seal" in steps


@pytest.mark.parametrize(
    ("queue", "code", "owner"),
    [
        ({(PR, "tick"): [{"refused": "producer_challenge_not_approved"}]}, "onboard_needs_approval", True),
        ({(ST, "draw"): [{"refused": "study_overlaps_prior:ev5"}]}, "onboard_tell_test_lead:study_overlaps_prior:ev5", True),
        ({(TU, "quiz-select"): [{"status": "REFUSED", "reason": "tuning_quiz_q2_pool_short"}]}, "onboard_tell_test_lead:tuning_quiz_q2_pool_short", True),
        ({(PR, "tick"): [{BATTERY_CHALLENGE: {"cadence": None}}]}, "onboard_no_cadence", True),
        ({(PR, "status"): [{"challenges": {}}]}, "onboard_pool_not_published", False),
        ({("systemctl", "is-active"): [(3, "inactive")]}, "onboard_unit_not_running:carbon-producer.timer", True),
        ({("systemctl", "show"): ["failed"]}, "onboard_push_failed", True),
        ({(CO, "seal"): [{"refused": "confirmation_custody_missing"}]}, "onboard_refused:confirmation_custody_missing", False),
    ],
)  # fmt: skip
def test_stops_are_named_with_the_next_command(inputs, tmp_path, queue, code, owner):
    with pytest.raises(ob.OnboardStop) as stopped:
        run(inputs, tmp_path, Script(queue), study=True)
    assert stopped.value.code == code
    assert stopped.value.owner is owner
    assert SECRET not in json.dumps(stopped.value.report())


def test_missing_inputs_are_owner_stops(inputs, tmp_path):
    value = json.loads(inputs.read_text())
    del value["producer_config"]
    private_file(inputs, value)
    with pytest.raises(ob.OnboardStop) as stopped:
        run(inputs, tmp_path, Script())
    assert stopped.value.code == "onboard_needs_input:producer_config"


def test_a_changed_code_commit_or_state_is_refused(inputs, tmp_path):
    run(inputs, tmp_path, Script())
    with pytest.raises(ob.OnboardStop) as stopped:
        run(inputs, tmp_path, Script(), commit="d" * 40)
    assert stopped.value.code == "onboard_code_changed"
    run(inputs, tmp_path, Script(), commit="d" * 40, accept_code="d" * 40)
    assert state(tmp_path)["code"] == "d" * 40
    path = tmp_path / "state" / ob.STATE_FILE
    value = json.loads(path.read_text())
    value["challenge_id"] = "electric-motor-magnetics"
    path.write_text(json.dumps(value))
    with pytest.raises(ob.OnboardStop) as stopped:
        run(inputs, tmp_path, Script(), commit="d" * 40)
    assert stopped.value.code == "onboard_state_mismatch"


def test_a_check_that_changed_is_refused(inputs, tmp_path):
    run(inputs, tmp_path, Script())
    path = tmp_path / "state" / ob.STATE_FILE
    value = json.loads(path.read_text())
    value["steps"]["truth/verify"]["public"] = {"verified": "elsewhere"}
    path.write_text(json.dumps(value))
    with pytest.raises(ob.OnboardStop) as stopped:
        run(inputs, tmp_path, Script())
    assert stopped.value.code == "onboard_state_mismatch"


def test_an_unregistered_challenge_is_refused(inputs, tmp_path):
    with pytest.raises(ob.OnboardStop) as stopped:
        ob.onboard(
            "electric-motor-magnetics", inputs, tmp_path / "state", runner=Script()
        )
    assert stopped.value.code == "onboard_no_adapter"
    assert not (tmp_path / "state").exists()


def test_the_cli_exits_by_stop_kind(inputs, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        ob,
        "default_runner",
        Script({(PR, "tick"): [{"refused": "producer_challenge_not_approved"}]}),
    )
    monkeypatch.setattr(ob, "current_commit", lambda repository: "c" * 40)
    code = ob.main(
        [
            "--challenge",
            BATTERY_CHALLENGE,
            "--inputs",
            str(inputs),
            "--state",
            str(tmp_path / "state"),
        ]
    )
    assert code == 3
    assert json.loads(capsys.readouterr().out)["stopped"] == "onboard_needs_approval"
