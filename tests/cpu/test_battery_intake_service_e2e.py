"""End to end on loopback: a signed submission through a served intake (LP-PROD-G).

A throwaway deployment is made by `operate init` in a temporary directory -
never an operator's - and the real `intake.serve` runs it on 127.0.0.1: the
listener, the refresher and the worker, through the real NET-2 verifier,
receipt journal, inbox and validator daemon. A miner fixture hotkey signs
with `btauth/1` in its own code; Carbon's client only builds and sends bytes.

**Non-production fixtures, by name:**
- the chain is a fixed metagraph snapshot (`FixedChain`); no request or test
  reads a chain;
- the deployment is `direct` (`DIRECT_TRUSTED_PROCESS`): recipes rebuild in
  this process instead of the pinned worker image, which is too heavy here;
  every outcome says so;
- the pool is opened from the exam-design campaign's published development
  cases, which a deployed validator refuses (`allow_published_cases`).
- every request here comes from one loopback peer, so the per-peer limits
  are widened; `test_battery_intake.py` holds the limits themselves.

Scores here are DEVELOPMENT evidence of nothing: this tests the path, not a
recipe. Not a security audit; the intake is not SECURITY_QUALIFIED.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_intake import (
    MINER,
    OTHER,
    STRATEGY,
    VALIDATOR,
    signed,
    snapshot,
)
from test_battery_validator_daemon import (
    DIGEST,
    batch,
    refs,  # noqa: F401 - fixture
)
from test_battery_validator_service import (
    self_signed,
    throwaway,
)

from carbon.battery import campaign, deployment
from carbon.battery import intake as ib
from carbon.battery import intake_client as ic
from carbon.battery import remote_submission as rs
from carbon.development_session.research_campaign import (
    OperationRefused,
)
from scripts.dev.battery_validator_service import service as svc

BATTERY = STRATEGY["challenge_id"]
NINE_NEIGHBOURS = {**STRATEGY, "parameters": {"neighbours": 9}}
TORCH = {
    **STRATEGY,
    "backbone": "mlp",
    "parameters": {"backend": "pytorch", "width": 16, "depth": 1, "steps": 32},
}


class FixedChain:
    """The refresher's chain reader: one fixed, fresh snapshot per read."""

    def __init__(self):
        self.reads = 0

    async def capture(self, context):
        self.reads += 1
        return snapshot(100)


class Roomy(ib.PeerLimits):
    def __init__(self):
        super().__init__(burst=500, rate=100.0)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    monkeypatch.setattr(ib, "PeerLimits", Roomy)


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def made_here(path, **intake_changes):
    """A throwaway deployment whose intake receives for the fixture validator
    hotkey, on a free loopback port."""
    return throwaway(
        path,
        port=free_port(),
        intake_changes={"receiver": VALIDATOR.ss58_address, **intake_changes},
    )


def open_pool(made, refs):  # noqa: F811
    """NON-PRODUCTION: open the throwaway pool on published development cases."""
    target = deployment.validator(made.deployment, repository=REPOSITORY)
    target.allow_published_cases = True
    for b in range(3):
        fp = target.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
        target.ingest_references(fp, list(refs.values()))
    target.open_pool()
    return target


@contextmanager
def serving(made, chain=None):
    """`intake.serve` on its configured loopback port, until the block ends."""
    stop, ready, failed = threading.Event(), threading.Event(), []

    def run():
        try:
            ib.serve(
                made.intake,
                repository=REPOSITORY,
                stop=stop,
                reader=chain or FixedChain(),
                ready=lambda _address: ready.set(),
            )
        except BaseException as failure:  # noqa: BLE001 - reported below
            failed.append(failure)
            ready.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert ready.wait(60) and not failed, failed
    config = json.loads(made.intake.read_text())
    url = f"http://127.0.0.1:{config['port']}"
    try:
        yield SimpleNamespace(url=url, config=config, stop=stop)
    finally:
        stop.set()
        thread.join(60)
        assert not thread.is_alive()


def facts(url):
    deadline = time.monotonic() + 30
    while True:
        try:
            return ic.read_intake(url)
        except OSError:
            # 503 snapshot_unavailable until the refresher's first read.
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


def send(url, key, body):
    return ic.post(url, body, signed(key, body))


def until_terminal(url, key, submission_id):
    deadline = time.monotonic() + 120
    while True:
        status, answer = send(url, key, ic.status_message(facts(url), submission_id))
        if answer.get("state") in rs.TERMINAL or "refused" in answer:
            return status, answer
        assert time.monotonic() < deadline, answer
        time.sleep(0.2)


@pytest.fixture
def served(tmp_path, refs):  # noqa: F811
    made = made_here(tmp_path)
    target = open_pool(made, refs)
    with serving(made) as live:
        yield SimpleNamespace(made=made, target=target, **vars(live))


def test_a_signed_submission_is_scored_and_read_back_over_loopback(served):
    url = served.url
    public = facts(url)
    assert public["receiver"] == VALIDATOR.ss58_address
    assert public["tools"] == ["battery_submit", "battery_status"]
    assert (public["qualification"], public["reward"]) == (False, False)
    status, answer = send(url, MINER, ic.submission_message(public, STRATEGY, DIGEST))
    assert (status, answer["state"]) == (202, "RECEIVED")
    sid = answer["submission_id"]
    status, outcome = until_terminal(url, MINER, sid)
    assert (status, outcome["state"]) == (200, "SCORED")
    # The miner's allow-listed outcome: development evidence, never a reward.
    assert outcome["qualification"] is False and outcome["reward"] is False
    assert outcome["reconstruction"]["backend"] == "DIRECT_TRUSTED_PROCESS"
    text = json.dumps(outcome)
    for private in ("pscreen", "pfinal", "seed", "root"):
        assert private not in text
    assert ic.describe(status, outcome).startswith("Scored on pool version")
    # Another hotkey's probe finds nothing, not "exists but not yours".
    probe = ic.status_message(facts(url), sid)
    assert send(url, OTHER, probe) == (404, {"refused": "not_found"})
    # The same recipe again is the same submission: one admission.
    status, again = send(
        url, MINER, ic.submission_message(facts(url), STRATEGY, DIGEST)
    )
    assert (status, again["submission_id"]) == (202, sid)
    inbox = ib.Inbox(served.config["inbox"])
    assert inbox.counts() == {"RECEIVED": 0, "ADMITTED": 1, "REFUSED": 0}
    with served.target.store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM submissions").fetchone() == (1,)
    # The operator's status reads the live intake over its bound address.
    found = svc.status(served.made.service, repository=REPOSITORY)
    assert found["healthy"] is True and found["intake"]["answer"] == "ok"
    assert found["inbox"]["ADMITTED"] == 1
    assert found["deployment"]["pool"]["admitted"] == 1


def prepared(root, url):
    root.mkdir(mode=0o700)
    return SimpleNamespace(
        sdk=SimpleNamespace(connection=SimpleNamespace(miner_key="miner-signer")),
        ledger=SimpleNamespace(root=root),
        manifest={"contract_digest": DIGEST},
        args=SimpleNamespace(intakes={BATTERY: url}, validators={}),
    )


@pytest.fixture
def miner_signs(monkeypatch):
    """The miner's signer, as a fixture: the test hotkey signs in test code.
    Carbon's own path never holds a key."""
    monkeypatch.setattr(rs, "_signed", lambda signer, facts, body: signed(MINER, body))
    monkeypatch.setattr(rs, "POLL_S", 0.3)


def test_the_launchpad_intake_path_reports_a_verdict_and_stays_one_admission(
    served, tmp_path, miner_signs
):
    ready = prepared(tmp_path / "campaign", served.url)
    record = {"strategy": NINE_NEIGHBOURS}
    first = asyncio.run(campaign.evaluate_candidate(ready, 1, record))
    assert first["outcome"]["state"] == "SCORED"
    assert first["via"]["intake"] == served.url
    assert (first["official_eligible"], first["reward"]) == (False, False)
    # Asking again for the same epoch reads the same submission's verdict.
    again = asyncio.run(campaign.evaluate_candidate(ready, 1, record))
    assert again["via"] == first["via"]
    assert ib.Inbox(served.config["inbox"]).counts()["ADMITTED"] == 1
    # The epoch's submission belongs to the intake that received it.
    elsewhere = SimpleNamespace(**vars(ready))
    elsewhere.args = SimpleNamespace(
        intakes={BATTERY: "http://127.0.0.1:9"}, validators={}
    )
    with pytest.raises(OperationRefused) as refused:
        asyncio.run(campaign.evaluate_candidate(elsewhere, 1, record))
    assert refused.value.code == "intake_changed_since_submission"
    assert campaign.intake_outcome(refused.value.code) == "REFUSED"


def test_a_refusal_at_admission_is_not_a_verdict_and_resubmits_as_one(
    served, tmp_path, miner_signs
):
    """This validator serves JAX only, so a PyTorch recipe is refused at
    admission (`backend_not_served`): the validator's own state. The epoch is
    not used; asking again resends the same candidate, which the intake
    receives again under the same id, and it is refused again by name."""
    served.target.backend.backends = ("jax",)
    ready = prepared(tmp_path / "campaign", served.url)
    record = {"strategy": TORCH}
    for _ in range(2):
        with pytest.raises(OperationRefused) as refused:
            asyncio.run(campaign.evaluate_candidate(ready, 1, record))
        assert refused.value.code == "backend_not_served"
        assert campaign.intake_outcome(refused.value.code) == "UNAVAILABLE"
        assert ic.explain(refused.value.code).startswith("This validator has no")
    counts = ib.Inbox(served.config["inbox"]).counts()
    assert counts == {"RECEIVED": 0, "ADMITTED": 0, "REFUSED": 1}
    with served.target.store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM submissions").fetchone() == (0,)


def test_the_intake_logs_events_and_never_a_peer(tmp_path, refs, capsys):  # noqa: F811
    made = made_here(tmp_path)
    open_pool(made, refs)
    with serving(made) as live:
        public = facts(live.url)
        status, answer = send(
            live.url, MINER, ic.submission_message(public, STRATEGY, DIGEST)
        )
        assert status == 202
        until_terminal(live.url, MINER, answer["submission_id"])
    lines = [
        json.loads(line)
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("{")
    ]
    events = [line["event"] for line in lines if line["service"] == "battery-intake"]
    assert events[0] == "listening" and events[-1] == "stopped"
    assert "worker_pass" in events
    text = json.dumps(lines)
    assert MINER.ss58_address not in text and answer["submission_id"] not in text


def test_a_silent_connection_never_stalls_the_tls_listener(
    tmp_path,
    refs,  # noqa: F811
):
    """Before LP-PROD-G every TLS handshake ran inside `accept`, in the one
    serving thread: a client that connected and sent nothing stopped the
    intake for everyone. The handshake now runs in the connection's own
    thread under its socket timeout."""
    tls = tmp_path / "tls"
    tls.mkdir(mode=0o700)
    cert, key = self_signed(tls)
    made = made_here(tmp_path / "service", tls_cert=str(cert), tls_key=str(key))
    open_pool(made, refs)
    with serving(made) as live:
        assert svc.probe_intake(live.config)["answer"] == "ok"
        silent = socket.create_connection(("127.0.0.1", live.config["port"]))
        try:
            started = time.monotonic()
            answer = svc.probe_intake(live.config, timeout=5.0)
            assert answer["answer"] == "ok", answer
            assert time.monotonic() - started < 5.0
        finally:
            silent.close()


def test_the_listener_refuses_what_it_must_before_listening(tmp_path):
    made = made_here(tmp_path)
    # Unreadable TLS material is refused by name, before anything listens.
    value = json.loads(made.intake.read_text())
    value.update(
        tls_cert=str(tmp_path / "none.crt"), tls_key=str(tmp_path / "none.key")
    )
    made.intake.write_text(json.dumps(value))
    with pytest.raises(ib.IntakeUnavailable) as refused:
        ib.serve(made.intake, repository=REPOSITORY, reader=FixedChain())
    assert refused.value.code == "intake_tls_unreadable"
    # A public bind of a deployment that rebuilds in process is never served.
    with pytest.raises(ib.IntakeUnavailable) as refused:
        ib.require_isolation({"host": "0.0.0.0"}, {"backend": "direct"})
    assert refused.value.code == "intake_exposure_needs_carrier"
    ib.require_isolation({"host": "127.0.0.1"}, {"backend": "direct"})
    ib.require_isolation({"host": "0.0.0.0"}, {"backend": "carrier"})
