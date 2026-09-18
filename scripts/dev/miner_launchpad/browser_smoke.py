"""Actual Chromium/HTTP controller checks; no research or provider execution.

Run from the repository root: python scripts/dev/miner_launchpad/browser_smoke.py
Reuses Carbon's dependency-free CDP transport. Missing browser is a failure.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

import controller

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docs/development/carbon_hub/tools"))
import browser_smoke_test as cdp


def wait(session, expression):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if session.evaluate(expression):
            return
        time.sleep(0.05)
    raise AssertionError(f"Browser condition failed: {expression}")


@contextlib.contextmanager
def serving(store, token, port=0):
    server = controller.Server(store, token, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def connect(session, token):
    session.evaluate(
        f"document.getElementById('token').value={json.dumps(token)};"
        "document.getElementById('connect-form').requestSubmit()"
    )
    wait(
        session,
        "document.getElementById('connection-state').textContent === 'Connected'",
    )


def click(session, name):
    wait(session, f"!document.getElementById({json.dumps(name)}).disabled")
    session.evaluate(f"document.getElementById({json.dumps(name)}).click()")


def state(session, expected):
    wait(
        session,
        f"document.getElementById('run-state').textContent === {json.dumps(expected)}",
    )


def load(session, origin):
    start = len(session.events)
    result = session.command("Page.navigate", {"url": origin})
    assert not result.get("errorText"), result
    session.wait_for_event("Page.loadEventFired", start)
    wait(session, "Boolean(document.getElementById('connect-form'))")


class ReadbackFixture:
    """UI-only failure injection. Never creates a Carbon receipt or research run."""

    valid = True

    def get(self, identity):
        assert identity == "engineering-fixture"
        return {
            "schema": "carbon.launchpad.development-readback.v1",
            "id": identity,
            "status": "VERIFIED_SOURCE" if self.valid else "READBACK_UNAVAILABLE",
            "receipt": (
                {
                    "disposition": "ENGINEERING_FIXTURE_DISPOSITION",
                    "receipt_id": "fixture-no-scientific-evidence",
                }
                if self.valid
                else None
            ),
        }

    def recent(self):
        return [self.get("engineering-fixture")]


class ResearchFixture:
    """Browser-control fixture only. Zero agents, numerical work or grants."""

    def __init__(self):
        self.record = None
        self.keys = set()
        text = "UI ENGINEERING FIXTURE: initial trial → feedback → revision → feedback → revision.\nKeep <script> inert and retain earlier candidates."
        self.guidance = {
            "schema": "carbon.autoresearch.guidance.v1",
            "text": text,
            "digest": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
        }

    def preflight(self):
        return {
            "available": True,
            "profile": "engineering-fixture",
            "status": "ENGINEERING_FIXTURE_ONLY",
            "ceilings": {
                "provider_nanodollars": 500000000,
                "provider_attempts": 24,
                "research_trials": 4,
                "final_replicas": 12,
                "numerical_milliseconds": 14400000,
                "reference_trajectories": 512,
                "reference_invocations": 2048,
                "retained_bytes": 10737418240,
                "epochs": 2,
            },
            "expires_unix": 21600,
            "research_guidance": self.guidance,
            "review_digest": "fixture-review-pin",
            "runtime_revision": "fixture-runtime-no-execution",
            "review": {
                "experiment_pause": "ENGINEERING_FIXTURE_ONLY",
                "challenge": "fixture-challenge",
                "reconstruction": "Unexecuted fixture",
                "execution": {
                    "profile": "carbon_jax_cuda13_rtx3060_laptop_development_v1",
                    "backend": "cuda",
                    "basis": "CONFIGURATION_ONLY",
                    "installed_dependencies": "NOT_INSPECTED",
                    "device_visibility": "NOT_OBSERVED",
                    "runtime_evidence": "NOT_ATTACHED",
                    "admission_readiness": "NOT_ESTABLISHED_BY_REVIEW",
                },
                "capabilities": {
                    "backbones": ["fixture-fno"],
                    "selection": "Unselected",
                    "training": "Unexecuted fixture",
                },
                "grant": {
                    "status": "REQUESTED_NOT_GRANTED",
                    "expired": True,
                    "expires_unix": 21600,
                },
                "resources": {
                    "basis": "Fixture limits only; not remaining balance",
                    "final_evaluation_reserve": {"provider_nanodollars": 163840000},
                },
            },
        }

    def launch(self, value, key):
        assert value == {
            "profile": "engineering-fixture",
            "review_digest": "fixture-review-pin",
        }
        self.keys.add(key)
        if self.record is None:
            self.record = {
                "id": "engineering-research-fixture",
                "state": "RUNNING",
                "agent": "UI FIXTURE",
                "research_guidance": dict(self.guidance),
                "attempted_experiments": 1,
                "completed_experiments": 1,
                "experiments": [
                    {
                        "completed_steps": 12,
                        "worker_seconds": 2.5,
                        "diagnostics": {
                            "descriptive_score": 0.42,
                            "sampled_gate_failures": ["ENGINEERING_FIXTURE_GATE"],
                        },
                        "inline_curve": [
                            {"step": 1, "data_loss": 0.5},
                            {"step": 12, "data_loss": 0.25},
                        ],
                    }
                ],
                "usage": {
                    kind: {"provider_nanodollars": value}
                    for kind, value in [
                        ("available", 490000000),
                        ("reserved", 1000000),
                        ("reported", 2000000),
                        ("uncertain", 3000000),
                    ]
                },
                "final_results": [],
            }
        return self.record

    def get(self, identity):
        assert identity == self.record["id"]
        return self.record

    def control(self, identity, action):
        record = self.get(identity)
        record["state"] = {
            "pause": "PAUSE_REQUESTED",
            "resume": "RUNNING",
            "stop": "STOPPING",
            "reconcile": "STOPPED",
        }[action]
        if action == "reconcile":
            record["epoch_outcomes"] = [
                {
                    "status": "STOPPED",
                    "reason": "UI FIXTURE stop reason",
                    "final_evidence": False,
                }
            ]
        return record

    def recent(self):
        return [self.record] if self.record else []


def run():
    with tempfile.TemporaryDirectory(prefix="carbon-launchpad-smoke-") as temporary:
        root = Path(temporary)
        now = [1000.0]
        token = "browser-smoke-session-token-not-a-real-credential"
        store = controller.Controller(root / "runs.sqlite3", lambda: now[0])
        with cdp.launch_browser(cdp.discover_browser(), 20) as (_, browser_port):
            session = cdp._open_page_session(browser_port, 10)
            try:
                session.command("Page.enable")
                session.command("Runtime.enable")
                session.command(
                    "Browser.setDownloadBehavior",
                    {"behavior": "allow", "downloadPath": str(root)},
                )
                with serving(store, token) as server:
                    port, origin = server.server_port, server.origin
                    load(session, origin)
                    assert session.evaluate(
                        "document.getElementById('launch-fields').disabled"
                    )
                    connect(session, token)
                    assert session.evaluate(
                        "document.getElementById('research-launch').disabled"
                    )
                    click(session, "launch-button")
                    state(session, "QUEUED")
                    run_id = store.recent()[0]["id"]
                    store.tick()
                    state(session, "RUNNING")
                    click(session, "pause")
                    state(session, "PAUSED")
                    steps = store.get(run_id)["steps"]
                    store.tick()
                    assert store.get(run_id)["steps"] == steps
                    click(session, "resume")
                    state(session, "QUEUED")
                    click(session, "stop")
                    state(session, "STOPPED")
                    click(session, "export")
                    exported = root / f"carbon-rehearsal-{run_id}.json"
                    deadline = time.monotonic() + 8
                    while not exported.exists() and time.monotonic() < deadline:
                        time.sleep(0.05)
                    assert json.loads(exported.read_text()) == store.get(run_id)

                    # Commit succeeds, response is lost: reload must retain its key.
                    original_launch = store.launch

                    def lost_response(value, key):
                        original_launch(value, key)
                        raise OSError("simulated lost acknowledgement")

                    store.launch = lost_response
                    click(session, "launch-button")
                    wait(
                        session,
                        "document.getElementById('message').textContent.includes('Launch not confirmed')",
                    )
                    assert len(store.recent()) == 2
                    store.launch = original_launch
                    load(session, origin)
                    assert session.evaluate(
                        "document.getElementById('token').value === ''"
                    )
                    connect(session, token)
                    click(session, "launch-button")
                    wait(
                        session,
                        "sessionStorage.getItem('carbon.launchpad.pending.v1') === null",
                    )
                    assert len(store.recent()) == 2
                    active = next(
                        run for run in store.recent() if run["state"] == "QUEUED"
                    )
                    run_id = active["id"]

                    # A real server-side storage failure disables browser commands.
                    original_recent = store.recent

                    def unavailable():
                        raise sqlite3.OperationalError("private storage detail")

                    store.recent = unavailable
                    wait(
                        session,
                        "document.getElementById('connection-state').textContent === 'Connection interrupted'",
                    )
                    assert session.evaluate(
                        "document.getElementById('launch-fields').disabled && document.getElementById('stop').disabled"
                    )
                    store.recent = original_recent
                    wait(
                        session,
                        "document.getElementById('connection-state').textContent === 'Connected'",
                    )

                    # Rendering/fresh-read failure injection, not scientific evidence.
                    research = ResearchFixture()
                    server.research_runner = research
                    research_launch = research.launch
                    original_preflight = research.preflight
                    research.preflight = lambda: {
                        **original_preflight(),
                        "available": False,
                        "status": "OWNER_EXPERIMENT_PAUSE",
                        "reason": "Owner experiment pause is active. New owner authorization is required.",
                    }
                    wait(
                        session,
                        "document.getElementById('research-preflight').textContent.includes('Owner experiment pause is active')",
                    )
                    assert session.evaluate(
                        "document.getElementById('research-launch').disabled && document.getElementById('research-guidance').value.includes('UI ENGINEERING FIXTURE')"
                    )
                    load(session, origin)
                    connect(session, token)
                    wait(
                        session,
                        "document.getElementById('research-preflight').textContent.includes('Owner experiment pause is active')",
                    )
                    assert not research.keys
                    assert session.evaluate(
                        "document.getElementById('research-review').textContent.includes('NOT_OBSERVED') && document.getElementById('research-review').textContent.includes('REQUESTED_NOT_GRANTED')"
                    )
                    research.preflight = original_preflight
                    wait(
                        session, "!document.getElementById('research-launch').disabled"
                    )

                    def lost_research_response(value, key):
                        research_launch(value, key)
                        raise OSError("injected research acknowledgement loss")

                    research.launch = lost_research_response
                    wait(
                        session,
                        "document.getElementById('research-guidance').value.includes('UI ENGINEERING FIXTURE')",
                    )
                    assert session.evaluate(
                        "document.getElementById('research-guidance').readOnly"
                    )
                    click(session, "research-launch")
                    wait(
                        session,
                        "document.getElementById('message').textContent.includes('Research launch not confirmed')",
                    )
                    research.launch = research_launch
                    load(session, origin)
                    connect(session, token)
                    click(session, "research-launch")
                    wait(
                        session,
                        "document.getElementById('research-runs').textContent.includes('UI FIXTURE')",
                    )
                    assert session.evaluate(
                        "document.querySelectorAll('.practice-result svg circle').length === 2"
                    )
                    assert session.evaluate(
                        "document.querySelector('.practice-result').textContent.includes('ENGINEERING_FIXTURE_GATE')"
                    )
                    assert session.evaluate(
                        "document.querySelector('.research-usage').textContent.includes('uncertain: $0.00300000')"
                    )
                    assert session.evaluate(
                        "document.querySelector('.development-result').textContent.includes('no independent result')"
                    )
                    session.evaluate(
                        "document.querySelector('#research-runs details').open = true"
                    )
                    research.record["current_hypothesis"] = {
                        "hypothesis": "UI FIXTURE updated hypothesis"
                    }
                    wait(
                        session,
                        "document.querySelector('#research-runs').textContent.includes('UI FIXTURE updated hypothesis')",
                    )
                    assert session.evaluate(
                        "document.querySelector('#research-runs details').open"
                    )
                    research.record["experiments"][0]["inline_curve"][0][
                        "data_loss"
                    ] = None
                    wait(
                        session,
                        "document.querySelectorAll('.practice-result svg').length === 0",
                    )
                    assert session.evaluate(
                        "document.querySelector('.practice-result').textContent.includes('Training curve unavailable')"
                    )
                    research.record["experiments"][0]["inline_curve"][0][
                        "data_loss"
                    ] = 0.5
                    original_research_recent = research.recent
                    research.recent = unavailable
                    wait(
                        session,
                        "document.getElementById('connection-state').textContent === 'Connection interrupted'",
                    )
                    assert session.evaluate(
                        "[...document.querySelectorAll('#research-runs button')].every(b => b.disabled)"
                    )
                    research.recent = original_research_recent
                    wait(
                        session,
                        "document.getElementById('connection-state').textContent === 'Connected'",
                    )
                    assert session.evaluate(
                        "document.querySelector('#research-runs details').open"
                    )
                    for action, observed in (
                        ("pause", "PAUSE_REQUESTED"),
                        ("resume", "RUNNING"),
                        ("stop", "STOPPING"),
                        ("reconcile", "STOPPED"),
                    ):
                        wait(
                            session,
                            "![...document.querySelectorAll('#research-runs button')].find(b => b.textContent === "
                            + json.dumps(action)
                            + ").disabled",
                        )
                        session.evaluate(
                            "[...document.querySelectorAll('#research-runs button')].find(b => b.textContent === "
                            + json.dumps(action)
                            + ").click()"
                        )
                        wait(
                            session,
                            "document.getElementById('research-runs').textContent.includes("
                            + json.dumps(observed)
                            + ")",
                        )
                    assert len(research.keys) == 1
                    assert "UI FIXTURE stop reason" in session.evaluate(
                        "document.getElementById('research-runs').textContent"
                    )
                    research.record["final_results"] = [
                        {
                            "status": "VERIFIED_SOURCE",
                            "result": {
                                "disposition": "ENGINEERING_FIXTURE_COMPLETE_UNRESOLVED",
                                "accepted_development_improvement": False,
                            },
                        }
                    ]
                    wait(
                        session,
                        "document.querySelector('.development-result').textContent.includes('ENGINEERING_FIXTURE_COMPLETE_UNRESOLVED')",
                    )
                    assert session.evaluate(
                        "document.querySelector('.development-result').textContent.includes('improvement: false')"
                    )
                    research.record["final_results"] = [
                        {"status": "READBACK_UNAVAILABLE", "result": None}
                    ]
                    wait(
                        session,
                        "document.querySelector('.development-result').textContent.includes('Readback unavailable')",
                    )
                    assert (
                        "ENGINEERING_FIXTURE_COMPLETE_UNRESOLVED"
                        not in session.evaluate(
                            "document.getElementById('research-runs').textContent"
                        )
                    )
                    load(session, origin)
                    connect(session, token)
                    wait(
                        session,
                        "document.getElementById('research-runs').textContent.includes('STOPPED')",
                    )
                    # Reconnect may choose a different rehearsal when creation
                    # timestamps tie. Select the exact retained run under test.
                    session.evaluate(
                        "document.getElementById('run-picker').value="
                        + json.dumps(run_id)
                        + ";document.getElementById('run-picker').dispatchEvent(new Event('change'))"
                    )
                    readback = ReadbackFixture()
                    server.development_sources = readback
                    wait(
                        session,
                        "document.getElementById('development-sources').textContent.includes('ENGINEERING_FIXTURE_DISPOSITION')",
                    )
                    session.evaluate(
                        "document.querySelector('#development-sources button').click()"
                    )
                    receipt_export = (
                        root / "carbon-development-engineering-fixture.json"
                    )
                    deadline = time.monotonic() + 8
                    while not receipt_export.exists() and time.monotonic() < deadline:
                        time.sleep(0.05)
                    assert json.loads(receipt_export.read_text()) == readback.get(
                        "engineering-fixture"
                    )

                    for width in (1440, 390):
                        session.command(
                            "Emulation.setDeviceMetricsOverride",
                            {
                                "width": width,
                                "height": 1000,
                                "deviceScaleFactor": 1,
                                "mobile": False,
                            },
                        )
                        assert session.evaluate(
                            "document.documentElement.scrollWidth <= innerWidth"
                        ), width
                        assert session.evaluate(
                            "document.getElementById('stop').getBoundingClientRect().width >= 44"
                        ), width
                        assert (
                            session.evaluate(
                                "document.getElementById('research-guidance').value"
                            )
                            == research.guidance["text"]
                        )
                        assert (
                            session.evaluate(
                                "document.querySelector('.frozen-guidance').textContent"
                            )
                            == "Frozen research task: "
                            + research.record["research_guidance"]["text"]
                        )
                        assert not session.evaluate(
                            "Boolean(document.querySelector('.frozen-guidance script'))"
                        )
                    readback.valid = False
                    wait(
                        session,
                        "document.getElementById('development-sources').textContent.includes('Readback unavailable')",
                    )
                    assert session.evaluate(
                        "document.querySelector('#development-sources button').disabled"
                    )
                    assert "fixture-no-scientific-evidence" not in session.evaluate(
                        "document.getElementById('development-sources').textContent"
                    )
                    store.tick()

                # Restart the real HTTP server and reopen the same SQLite history.
                recovered = controller.Controller(store.database, lambda: now[0])
                recovered.recover()
                token = "rotated-browser-smoke-token-not-a-real-credential"
                with serving(recovered, token, port):
                    wait(
                        session,
                        "document.getElementById('connection-state').textContent === 'Connection interrupted'",
                    )
                    connect(session, token)
                    state(session, "INTERRUPTED")
                    assert recovered.get(run_id)["steps"] == 1
                    click(session, "resume")
                    state(session, "QUEUED")
                    now[0] += 601
                    state(session, "EXPIRED")
                    assert session.evaluate(
                        "document.getElementById('resume').disabled && document.getElementById('stop').disabled"
                    )
                    assert len(recovered.recent()) == 2
                    assert all(
                        run["scientific_result"] is None for run in recovered.recent()
                    )
                exceptions = [
                    event
                    for event in session.events
                    if event["method"] == "Runtime.exceptionThrown"
                ]
                assert not exceptions, exceptions
            finally:
                session.close()
    print(
        "Launchpad browser/server smoke passed: connect, launch, lost-response/reload retry, pause/resume/stop, export, storage failure, restart, expiry, desktop/mobile, fixture readback/export invalidation. No scientific campaign ran."
    )


if __name__ == "__main__":
    run()
