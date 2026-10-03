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


DIGEST = "sha256:" + "c" * 64
#: The miner's signer as the campaign holds it: a public hotkey, no key.
SIGNER = SimpleNamespace(ss58_address="5FixtureMinerHotkey")
OTHER_SIGNER = SimpleNamespace(ss58_address="5FixtureOtherHotkey")


def prepared(tmp_path, *, url=URL, key=SIGNER):
    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    return SimpleNamespace(
        sdk=SimpleNamespace(connection=SimpleNamespace(miner_key=key)),
        ledger=SimpleNamespace(root=tmp_path),
        manifest={"contract_digest": DIGEST},
        args=SimpleNamespace(
            intakes={"battery-fastcharge-ageing-development-v1": url}, validators={}
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


# --- LP-PROD-G: queued, scored or refused, by closed code ---------------------------


class Admission:
    """An intake fixture whose admission refuses first, as the worker does.

    It names a submission as the intake does, by the signer's hotkey, the
    recipe and the contract (`intake_client.submission_id`), and answers a
    status request from any other hotkey `not_found`."""

    def __init__(self, refusals, *, block=100, then="SCORED"):
        from carbon.battery import intake_client

        self.refusals = list(refusals)  # failure dicts, one per admission pass
        self.block, self.then = block, then
        self.sent, self.state = [], "RECEIVED"
        self.owner = SIGNER.ss58_address
        self.sid = intake_client.submission_id(self.owner, {"backbone": "knn"}, DIGEST)

    def read(self, url):
        return {**FACTS, "snapshot": {"id": "snap-1", "finalized_block": self.block}}

    def post(self, url, body, headers):
        from carbon.battery import intake_client

        tool = json.loads(body)["call"]["tool"]
        hotkey = getattr(headers["X-Fixture-Signed"], "ss58_address", None)
        self.sent.append(tool)
        if tool == "battery_submit":
            strategy = json.loads(body)["strategy"]
            self.state = "RECEIVED"
            sid = intake_client.submission_id(hotkey, strategy, DIGEST)
            return 202, {"submission_id": sid, "state": "RECEIVED"}
        if hotkey != self.owner:
            return 404, {"refused": "not_found"}
        if self.state == "RECEIVED":
            if self.refusals:
                self.state, self.failure = "REFUSED", self.refusals.pop(0)
            else:
                self.state = self.then
        answer = {"submission_id": self.sid, "state": self.state}
        if self.state == "REFUSED":
            answer["failure"] = self.failure
        return 200, answer


def through(intake, monkeypatch):
    real = rs.submit_and_wait

    def fixture(url, signer, **kwargs):
        return real(
            url,
            signer,
            **kwargs,
            read=intake.read,
            post=intake.post,
            sleep=lambda _: None,
        )

    monkeypatch.setattr(rs, "submit_and_wait", fixture)
    monkeypatch.setattr(
        rs.intake_client, "read_intake", lambda url, **_: intake.read(url)
    )
    monkeypatch.setattr(rs.intake_client, "post", intake.post)


def evaluate(tmp_path, record=None, **changes):
    from carbon.battery import campaign

    return asyncio.run(
        campaign.evaluate_candidate(
            prepared(tmp_path, **changes),
            1,
            record or {"strategy": {"backbone": "knn"}},
        )
    )


def test_a_refusal_at_admission_is_never_a_verdict(tmp_path, signed, monkeypatch):
    """Before LP-PROD-G a submission the worker refused at admission came back
    as the epoch's feedback, with state REFUSED: it consumed the epoch with no
    evaluation. It is now an `OperationRefused` by its closed code, after one
    resend of the same candidate (the same submission id)."""
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused

    intake = Admission(
        [{"code": "commitment_required"}, {"code": "commitment_required"}]
    )
    through(intake, monkeypatch)
    with pytest.raises(OperationRefused) as refused:
        evaluate(tmp_path)
    assert refused.value.code == "commitment_required"
    assert campaign.intake_outcome(refused.value.code) == "REFUSED"
    assert intake.sent.count("battery_submit") == 2  # the first send, one resend
    # Once the miner has committed, asking again resends and gets the verdict.
    intake.refusals = []
    feedback = evaluate(tmp_path)
    assert feedback["outcome"]["state"] == "SCORED"
    assert feedback["via"]["submission_id"] == intake.sid


def test_a_window_refusal_waits_for_the_window_and_sends_nothing(
    tmp_path, signed, monkeypatch
):
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused

    window = {"code": "hotkey_window_used", "next_block": 360}
    intake = Admission([window], block=100)
    through(intake, monkeypatch)
    with pytest.raises(OperationRefused) as refused:
        evaluate(tmp_path)
    assert refused.value.code == "hotkey_window_used"
    assert intake.sent.count("battery_submit") == 1  # no resend before block 360
    # The window opens: the same candidate is sent again and scored.
    intake.block = 360
    assert evaluate(tmp_path)["outcome"]["state"] == "SCORED"
    assert intake.sent.count("battery_submit") == 2
    assert campaign.intake_outcome("hotkey_window_used") == "REFUSED"


def test_a_submission_the_intake_lost_is_sent_again(tmp_path, signed, monkeypatch):
    """`not_found` for the epoch's own recorded submission: the validator no
    longer holds it (an inbox restored from an earlier backup)."""
    intake = Admission([])
    through(intake, monkeypatch)
    evaluate(tmp_path)
    lost = {"n": 0}
    real_post = intake.post

    def forgetful(url, body, headers):
        if json.loads(body)["call"]["tool"] == "battery_status" and lost["n"] == 0:
            lost["n"] += 1
            return 404, {"refused": "not_found"}
        return real_post(url, body, headers)

    intake.post = forgetful  # the fixture reads `intake.post` at each call
    assert evaluate(tmp_path)["via"]["submission_id"] == intake.sid
    assert intake.sent.count("battery_submit") == 2


def test_a_changed_signer_sends_nothing(tmp_path, signed, monkeypatch):
    """`not_found` also answers a poll from another hotkey. Before this
    review fix the campaign then resent the candidate under that hotkey, a
    second submission, and only afterwards saw the id differ."""
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused

    intake = Admission([])
    through(intake, monkeypatch)
    assert evaluate(tmp_path)["outcome"]["state"] == "SCORED"
    for key in (OTHER_SIGNER, SimpleNamespace()):  # another hotkey, or none read
        with pytest.raises(OperationRefused) as refused:
            evaluate(tmp_path, key=key)
        assert refused.value.code == "intake_signer_changed"
        assert campaign.intake_outcome(refused.value.code) == "REFUSED"
    assert intake.sent.count("battery_submit") == 1


# --- every way the trip can fail is a closed code -----------------------------------


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        ("http_502_html", "intake_unreachable"),
        ("http_429_rate", "rate"),
        ("http_503_snapshot", "snapshot_unavailable"),
        ("not_json", "intake_unreachable"),
        ("mismatch", "intake_mismatch"),
        ("incomplete", "intake_unreachable"),
        ("refused_connection", "intake_unreachable"),
        ("malformed_facts", "intake_answer_unrecognised"),
        ("malformed_answer", "intake_answer_unrecognised"),
        ("signer", "signer_unavailable"),
    ],
)
def test_no_failure_of_the_trip_ends_the_campaign(tmp_path, monkeypatch, failure, code):
    """Before this review fix only `IntakeRefusal` and `OSError` were mapped:
    every other exception ended the campaign run (which keeps a candidate only
    for `OperationRefused`), and an HTTP refusal of the public facts was
    always `intake_unreachable`, whatever the intake said."""
    import http.client
    import io
    import urllib.error

    from carbon.battery import campaign, intake_client
    from carbon.chain.external_signer import SignerCode, SignerFailure
    from carbon.development_session.research_campaign import OperationRefused

    def refusal(status, body):
        return urllib.error.HTTPError(URL, status, "x", {}, io.BytesIO(body))

    raised = {
        "http_502_html": refusal(502, b"<html>Bad Gateway</html>"),
        "http_429_rate": refusal(429, b'{"refused": "rate"}'),
        "http_503_snapshot": refusal(503, b'{"refused": "snapshot_unavailable"}'),
        "not_json": json.JSONDecodeError("Expecting value", "<html>", 0),
        "mismatch": intake_client.IntakeMismatch("the intake serves another chain"),
        "incomplete": http.client.IncompleteRead(b""),
        "refused_connection": ConnectionRefusedError(111, "refused"),
        "malformed_facts": KeyError("snapshot"),
        "malformed_answer": AttributeError("'list' object has no attribute 'get'"),
        "signer": SignerFailure(SignerCode.NOT_RUNNING),
    }[failure]

    def fail(*args, **kwargs):
        raise raised

    monkeypatch.setattr(rs, "submit_and_wait", fail)
    with pytest.raises(OperationRefused) as refused:
        evaluate(tmp_path)
    assert refused.value.code == code
    assert intake_client.explain(code)
    assert campaign.intake_outcome(code) in {"UNAVAILABLE", "REFUSED"}


class Answering:
    """A loopback HTTP server answering every GET and POST with a fixed
    `(status, content type, body)`: a proxy's error page, another server."""

    def __init__(self, get, post=None):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        def send(handler, answer):
            status, kind, body = answer
            handler.send_response(status)
            handler.send_header("Content-Type", kind)
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                send(self, get)

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                send(self, post)

            def log_message(self, *_args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def public_facts(**changes):
    from carbon.battery.intake import PUBLIC_SCHEMA

    value = {"schema": PUBLIC_SCHEMA, "receiver": "5V", "snapshot": {"id": "s"}}
    return json.dumps({**value, **changes}).encode()


def test_over_http_a_proxy_page_or_another_chain_is_a_closed_code(tmp_path):
    """The same through the real client, over loopback HTTP."""
    from carbon.development_session.research_campaign import OperationRefused

    html = (502, "text/html", b"<html>Bad Gateway</html>")
    other_chain = public_facts(network="elsewhere", genesis="0x0", netuid=1)
    cases = [
        (Answering(html), "intake_unreachable"),
        (Answering((200, "application/json", other_chain)), "intake_mismatch"),
    ]
    for n, (server, code) in enumerate(cases):
        try:
            with pytest.raises(OperationRefused) as refused:
                evaluate(tmp_path / str(n), url=server.url)
            assert refused.value.code == code
        finally:
            server.close()


def test_over_http_a_proxy_page_answering_a_post_is_unreachable(
    tmp_path, signed, monkeypatch
):
    from carbon.development_session.research_campaign import OperationRefused

    monkeypatch.setattr(
        rs,
        "_signed",
        lambda signer, facts, body: {"X-Fixture-Signed": signer.ss58_address},
    )
    server = Answering(
        (200, "application/json", public_facts()),
        (502, "text/html", b"<html>Bad Gateway</html>"),
    )
    try:
        with pytest.raises(OperationRefused) as refused:
            evaluate(tmp_path, url=server.url)
        assert refused.value.code == "intake_unreachable"
    finally:
        server.close()
    assert not (tmp_path / "intake-submission-epoch-1.json").exists()


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("evaluation_queued", "QUEUED"),
        ("backend_not_served", "UNAVAILABLE"),
        ("intake_unreachable", "UNAVAILABLE"),
        ("snapshot_unavailable", "UNAVAILABLE"),
        ("TRANSPORT_IDENTITY", "REFUSED"),
        ("AUTH_STALE", "REFUSED"),
        ("http_500", "UNAVAILABLE"),
    ],
)
def test_every_code_has_a_closed_status_and_an_explanation(code, status):
    from carbon.battery import campaign, intake_client

    assert campaign.intake_outcome(code) == status
    closed = campaign.intake_code(code)
    assert intake_client.explain(closed)
    assert closed == (code if code != "http_500" else "intake_answer_unrecognised")


def test_every_closed_code_is_explained_and_classified():
    from carbon.battery import campaign, intake_client

    for code in campaign.INTAKE_QUEUED | campaign.INTAKE_UNAVAILABLE:
        assert intake_client.explain(code), code
    statuses = {campaign.intake_outcome(code) for code in intake_client.REFUSALS}
    assert statuses == {"QUEUED", "UNAVAILABLE", "REFUSED"}


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
