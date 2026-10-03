"""C-MLP-03 slice 6: a frozen candidate submitted from the miner's machine.

When the validator runs elsewhere, the campaign submits through the
validator's battery intake (OD-7(b)), signed by the miner's own signer, and
asks for that submission's status until there is a verdict. These tests hold
that:
- an epoch submits at most once: the submission id is recorded (owner-only)
  the moment the intake answers, and a later attempt only asks its status;
- a refusal or a wait that runs out is not a verdict, so the epoch is not
  consumed (`OperationRefused`), and a refused submission records nothing;
- the campaign's feedback names the intake and the submission;
- the profile and setup accept an intake only as https or loopback, and setup
  checks it serves this chain and Challenge.

The intake is a fixture answering in its documented shapes; signing goes
through a stand-in, because Carbon never holds a key.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from carbon.battery import remote_submission as rs

URL = "https://validator.example.org"
FACTS = {"receiver": "5Validator", "snapshot": {"id": "snap-1"}}


class Intake:
    """The validator's intake, as a fixture: it records what it was sent."""

    def __init__(self, submit=(202, {"submission_id": "sub-1", "state": "RECEIVED"})):
        self.submit = submit
        self.states = ["ADMITTED", "RECONSTRUCTED", "SCORED"]
        self.sent = []

    def read(self, url):
        assert url == URL
        return FACTS

    def post(self, url, body, headers):
        tool = json.loads(body)["call"]["tool"]
        self.sent.append((tool, headers))
        if tool == "battery_submit":
            return self.submit
        state = self.states.pop(0) if self.states else "SCORED"
        return 200, {"submission_id": "sub-1", "state": state}


@pytest.fixture
def signed(monkeypatch):
    monkeypatch.setattr(
        rs, "_signed", lambda signer, facts, body: {"X-Fixture-Signed": signer}
    )
    monkeypatch.setattr(
        rs.intake_client,
        "submission_message",
        lambda facts, strategy, digest: json.dumps(
            {"call": {"tool": "battery_submit"}, "strategy": strategy}
        ).encode(),
    )
    monkeypatch.setattr(
        rs.intake_client,
        "status_message",
        lambda facts, submission: json.dumps(
            {"call": {"tool": "battery_status"}, "submission_id": submission}
        ).encode(),
    )


def run(tmp_path, intake, *, epoch=1, wait_s=600.0):
    tmp_path.chmod(0o700)
    ticks = iter(range(0, 10_000, 30))
    return rs.submit_and_wait(
        URL,
        "miner-signer",
        root=tmp_path,
        epoch=epoch,
        strategy={"backbone": "knn"},
        contract_digest="sha256:" + "c" * 64,
        read=intake.read,
        post=intake.post,
        clock=lambda: next(ticks),
        sleep=lambda _: None,
        wait_s=wait_s,
    )


def test_an_epoch_submits_once_and_waits_for_the_verdict(tmp_path, signed):
    intake = Intake()
    status, answer, submission = run(tmp_path, intake)
    assert (status, answer["state"], submission) == (200, "SCORED", "sub-1")
    tools = [tool for tool, _ in intake.sent]
    assert tools == ["battery_submit", *["battery_status"] * 3]
    # Every request is signed by the miner's own signer.
    assert all(h == {"X-Fixture-Signed": "miner-signer"} for _, h in intake.sent)
    record = tmp_path / "intake-submission-epoch-1.json"
    assert json.loads(record.read_bytes())["submission_id"] == "sub-1"
    assert record.stat().st_mode & 0o777 == 0o600
    # A second attempt for the same epoch only asks for its status.
    again = Intake()
    run(tmp_path, again)
    assert [tool for tool, _ in again.sent] == ["battery_status"] * 3


def test_a_refused_submission_records_nothing_and_says_why(tmp_path, signed):
    intake = Intake(
        submit=(
            429,
            {"refused": "hotkey_window_used", "next_block": 9, "retry_after_s": 120},
        )
    )
    with pytest.raises(rs.IntakeRefusal) as refused:
        run(tmp_path, intake)
    assert refused.value.code == "hotkey_window_used"
    assert "Next window: block 9" in refused.value.description
    assert not (tmp_path / "intake-submission-epoch-1.json").exists()


def test_a_wait_that_runs_out_keeps_the_submission(tmp_path, signed):
    intake = Intake()
    intake.states = ["ADMITTED"] * 100
    with pytest.raises(rs.IntakeRefusal) as refused:
        run(tmp_path, intake, wait_s=60.0)
    assert refused.value.code == "evaluation_queued"
    assert (tmp_path / "intake-submission-epoch-1.json").exists()


def prepared(tmp_path):
    tmp_path.chmod(0o700)
    return SimpleNamespace(
        sdk=SimpleNamespace(connection=SimpleNamespace(miner_key="miner-signer")),
        ledger=SimpleNamespace(root=tmp_path),
        manifest={"contract_digest": "sha256:" + "c" * 64},
        args=SimpleNamespace(
            intakes={"battery-fastcharge-ageing-development-v1": URL}, validators={}
        ),
    )


def test_the_campaign_reports_the_verdict_with_its_intake(
    tmp_path, signed, monkeypatch
):
    from carbon.battery import campaign

    intake = Intake()
    real = rs.submit_and_wait

    def through_fixture(url, signer, **kwargs):
        return real(
            url,
            signer,
            **kwargs,
            read=intake.read,
            post=intake.post,
            sleep=lambda _: None,
        )

    monkeypatch.setattr(rs, "submit_and_wait", through_fixture)
    feedback = asyncio.run(
        campaign.evaluate_candidate(
            prepared(tmp_path), 1, {"strategy": {"backbone": "knn"}}
        )
    )
    assert feedback["via"] == {"intake": URL, "submission_id": "sub-1"}
    assert feedback["outcome"]["state"] == "SCORED"
    assert (feedback["official_eligible"], feedback["reward"]) == (False, False)


@pytest.mark.parametrize(
    "code",
    ["hotkey_window_used", "evaluation_queued", "TRANSPORT_IDENTITY"],
)
def test_no_verdict_consumes_no_epoch(tmp_path, monkeypatch, code):
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused

    def refuse(*args, **kwargs):
        raise rs.IntakeRefusal(code)

    monkeypatch.setattr(rs, "submit_and_wait", refuse)
    with pytest.raises(OperationRefused, match=code):
        asyncio.run(
            campaign.evaluate_candidate(
                prepared(tmp_path), 1, {"strategy": {"backbone": "knn"}}
            )
        )


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://validator.example.org", True),
        ("http://127.0.0.1:8090", True),
        ("http://localhost:8090", True),
        ("http://validator.example.org", False),
        ("https://validator.example.org/?x=1", False),
        ("ftp://validator.example.org", False),
        (17, False),
    ],
)
def test_an_intake_is_https_or_loopback(url, ok):
    from scripts.dev.miner_launchpad.runner import _intake_url

    assert _intake_url(url) is ok


def test_setup_checks_the_intake_and_writes_it_to_the_profile(tmp_path):
    from test_miner_inference_providers import KEY, Checks, setup_with

    from scripts.dev.miner_launchpad import runner
    from scripts.dev.miner_launchpad.environment_setup import SetupRefused

    calls = []

    def intake(self, url, campaign=None):
        assert campaign.intake_check is not None  # the Challenge's own check
        calls.append(url)
        return {"receiver": "5V"}

    Checks.intake = intake
    try:
        setup, _, _ = setup_with(
            tmp_path,
            {
                "provider_id": "engy-chat",
                "model_id": "deepseek-v4-flash-0731",
                "key": KEY,
            },
        )
        with pytest.raises(SetupRefused) as refused:
            setup.review({"confirm": True, "battery_intake": "http://example.org"})
        assert refused.value.field == "intakes"
        with pytest.raises(SetupRefused) as refused:
            setup.review({"confirm": True, "intakes": {"nowhere": URL}})
        assert refused.value.field == "intakes"
        # A legacy `battery_intake` is read as the battery Challenge's intake.
        setup.review({"confirm": True, "battery_intake": URL})
    finally:
        del Checks.intake
    assert calls == [URL]
    cfg = runner.validated_profile(json.loads(setup.profile_path.read_bytes()))
    assert cfg["intakes"] == {"battery-fastcharge-ageing-development-v1": URL}
    assert runner.intakes(cfg) == cfg["intakes"]
