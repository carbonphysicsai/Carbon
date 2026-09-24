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
# The checkout itself, as the controller's own entry point does: the shared
# operations table and runner import as `scripts.dev.miner_launchpad.*`, and
# `carbon` resolves to this checkout rather than any installed copy. The bare
# `controller` module is the package module too, so a refusal raised through
# either name is the one class the server catches.
sys.path.insert(0, str(ROOT))
sys.modules.setdefault("scripts.dev.miner_launchpad.controller", controller)
sys.path.insert(0, str(ROOT / "docs/development/carbon_hub/tools"))
import browser_smoke_test as cdp


def wait(session, expression):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if session.evaluate(expression):
            return
        time.sleep(0.05)
    raise AssertionError(f"Browser condition failed: {expression}")


class StubReader:
    """A device-free, network-free chain reader.

    The browser door now defaults to Carbon's real testnet, which is right for a
    deployment and wrong for a smoke test: without this the page would make live
    chain calls and the smoke would pass or fail on whether testnet answered.
    """

    def __init__(self, participants=()):
        self.participants = tuple(participants)

    async def capture(self, context):
        from carbon.chain.models import MetagraphSnapshot

        return MetagraphSnapshot(
            context=context,
            finalized_block=100,
            block_hash="0x" + "cd" * 32,
            timestamp_ms=1,
            participants=self.participants,
        )


def stub_onboarding():
    # Imported the way this file already imports `controller`: bare, because
    # this directory is what is on sys.path here. The dotted `scripts.dev...`
    # form resolves only when the repository root is also on the path, which is
    # true of the test suite and not of this script.
    from onboarding import BrowserOnboarding

    from carbon.chain.models import ChainContext
    from carbon.development_session.chain_onboarding import carbon_testnet_context

    live = carbon_testnet_context()
    return BrowserOnboarding(
        reader=StubReader(),
        context=ChainContext(
            network=live.network,
            endpoint=live.endpoint,
            provider=live.provider,
            genesis_hash=live.genesis_hash,
            netuid=live.netuid,
        ),
    )


@contextlib.contextmanager
def serving(store, token, port=0):
    server = controller.Server(store, token, port, onboarding=stub_onboarding())
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
            "admission": "SUBNET_REGISTRATION_CHECKED_AT_LAUNCH",
            "budget": "SET_BY_MINER_AT_LAUNCH_OR_NONE",
            "research_guidance": self.guidance,
            "review_digest": "fixture-review-pin",
            "runtime_revision": "fixture-runtime-no-execution",
            "review": {
                "experiment_pause": "ENGINEERING_FIXTURE_ONLY",
                "challenge": "fixture-challenge",
                "reconstruction": "Unexecuted fixture",
                "execution": {
                    "profile": "carbon_jax_cuda13_nvidia_development_v1",
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
                "admission": {
                    "gate": "SUBNET_REGISTRATION",
                    "checked": "AT_LAUNCH_BEFORE_ANYTHING_IS_RECORDED",
                    "basis": "Fixture: registration is read at launch.",
                },
                "resources": {
                    "miner_budget": "SET_AT_LAUNCH_OR_NONE",
                    "carbon_service_limits": {"reference_trajectories": 512},
                    "basis": "Fixture: your budget, or none.",
                },
            },
        }

    def launch(self, value, key):
        # The page states who selects; the default is Carbon's agent.
        assert value == {
            "profile": "engineering-fixture",
            "review_digest": "fixture-review-pin",
            "agent": "autonomous",
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


def press(session, key, *, code=None, modifiers=0):
    """Send a real key event rather than calling .focus() or .click().

    The distinction is the whole point of a keyboard assertion: driving the DOM
    directly proves the element can be activated, not that a person using a
    keyboard can reach it. Only a dispatched key exercises the tab order, and
    the tab order is what a keyboard user actually has.
    """
    for kind in ("rawKeyDown", "char", "keyUp"):
        if kind == "char" and key != "Enter":
            continue
        session.command(
            "Input.dispatchKeyEvent",
            {
                "type": kind,
                "key": key,
                "code": code or key,
                "windowsVirtualKeyCode": 13 if key == "Enter" else 9,
                "modifiers": modifiers,
            },
        )


def focused(session):
    """What a keyboard user is currently on, as id or tag."""
    return session.evaluate(
        "(document.activeElement && (document.activeElement.id"
        " || document.activeElement.tagName.toLowerCase())) || ''"
    )


def keyboard_reaches(session, identity, *, limit=40):
    """Tab forward until the element has focus, or report how far we got.

    Bounded rather than looping forever, and it reports the order it saw so a
    failure says where the keyboard path stops instead of only that it did.
    """
    seen = []
    for _ in range(limit):
        current = focused(session)
        if current == identity:
            return seen
        seen.append(current)
        press(session, "Tab")
    raise AssertionError(
        f"{identity} was not reachable by keyboard; tab order visited {seen}"
    )


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
                    # The registration panel before connecting: present, and
                    # refusing rather than erroring. Its endpoints existed long
                    # before anything a person looked at reached them, so this
                    # asserts the surface, not just the route.
                    assert session.evaluate(
                        "document.getElementById('onboarding-status').disabled"
                    ), "registration controls must be disabled before connecting"
                    assert session.evaluate(
                        "document.getElementById('onboarding-coldkey')"
                        ".textContent.toUpperCase().includes('COLDKEY')"
                    ), "the coldkey warning must be on the page a miner reads"

                    connect(session, token)
                    assert session.evaluate(
                        "document.getElementById('research-launch').disabled"
                    )

                    # After connecting the requirements are read and rendered.
                    # Asserted on rendered text rather than on the response,
                    # because a payload nobody can see is what this panel exists
                    # to fix.
                    wait(
                        session,
                        "document.getElementById('onboarding-facts')"
                        ".textContent.includes('567')",
                    )
                    assert not session.evaluate(
                        "document.getElementById('onboarding-status').disabled"
                    )
                    facts = session.evaluate(
                        "document.getElementById('onboarding-facts').textContent"
                    )
                    assert "coldkey" in facts.lower(), facts[:200]
                    # NOT_READ is shown as what it is. A figure here would be
                    # read as a quote.
                    assert "Not read by Carbon" in facts, facts[:200]

                    # A real refusal through the real request path: a phrase in
                    # the address field is rejected and never echoed back.
                    phrase = (
                        "bottom drive obey lake curtain smoke "
                        "basket hold race lonely fit walk"
                    )
                    session.evaluate(
                        "document.getElementById('onboarding-address').value="
                        + json.dumps(phrase)
                        + ";document.getElementById('onboarding-status').click()"
                    )
                    wait(
                        session,
                        "document.getElementById('onboarding-result')"
                        ".textContent.length > 0",
                    )
                    shown = session.evaluate(
                        "document.getElementById('onboarding-result').textContent"
                    )
                    for word in phrase.split():
                        assert word not in shown, shown[:200]

                    # Section 9 case 10: the journey has to be operable without
                    # a mouse. Asserted with dispatched key events, because
                    # calling .click() would prove only that the handler works -
                    # which it already does - and nothing about whether a
                    # keyboard user can ever get there.
                    session.evaluate("document.body.focus()")
                    session.evaluate(
                        "document.getElementById('token').focus();"
                        "document.getElementById('token').blur()"
                    )
                    # Targets an enabled control. `research-launch` is
                    # disabled here by design - no research profile is
                    # configured - and a browser correctly skips disabled
                    # elements in the tab order, so asserting reachability of
                    # one would demand the page break its own semantics. The
                    # registration controls are the ones a miner actually
                    # reaches first, and they are enabled once connected.
                    order = keyboard_reaches(session, "onboarding-status")
                    assert order, "tab order was empty; focus never moved"
                    # Focus must be visible to whoever is driving it. An
                    # outline removed for aesthetics makes the keyboard path
                    # technically present and practically unusable.
                    assert session.evaluate(
                        "(() => {"
                        " const node = document.getElementById('onboarding-status');"
                        " node.focus();"
                        " const style = getComputedStyle(node);"
                        " return style.outlineStyle !== 'none'"
                        "  || style.boxShadow !== 'none'"
                        "  || style.borderStyle !== 'none';"
                        "})()"
                    ), "the focused control shows no visible focus indication"

                    # The public exam disclosure and the miner's own compute
                    # choices, rendered by the page from its own fetches. No
                    # research profile, grant, model key or agent is configured
                    # on this server, which is the point: reading what the exam
                    # runs on must not be gated behind any of them.
                    wait(
                        session,
                        "document.getElementById('exam-environment')"
                        ".textContent.includes('carbon.c03.linux-x86_64-cpu.development.v1')",
                    )
                    exam = session.evaluate(
                        "document.getElementById('exam-environment').textContent"
                    )
                    # Declared, and never dressed up as qualified.
                    assert "declared, not qualified" in exam, exam[:400]
                    assert "UNRESOLVED" in exam
                    # The owner's direction, visible to the miner reading it.
                    assert "does not have to match it" in exam
                    assert "declarative training strategy" in exam
                    # Destinations the miner may actually pick.
                    for choice in ("local cpu", "local gpu", "attach existing remote"):
                        assert choice in exam, choice
                    # What a miner is explicitly not held to.
                    assert "strict host grant" in exam
                    assert "whole device exclusivity" in exam
                    # Nothing private reaches the page.
                    for forbidden in ("/var/lib/carbon", "Bearer", "seed"):
                        assert forbidden not in exam, forbidden

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
                    # Registration is the gate a miner is told about, in rendered
                    # text; no grant is named anywhere in the research panel.
                    assert session.evaluate(
                        "document.getElementById('research-review').textContent.includes('NOT_OBSERVED') && document.getElementById('research-review').textContent.includes('Admission: subnet registration')"
                    )
                    research.preflight = original_preflight
                    wait(
                        session, "!document.getElementById('research-launch').disabled"
                    )
                    assert session.evaluate(
                        "document.getElementById('research-preflight').textContent.includes('your subnet registration, read at launch') && document.getElementById('research-launch').textContent === 'Launch research'"
                    )
                    panel = session.evaluate(
                        "document.getElementById('research-heading').closest('section').textContent"
                    )
                    assert "grant" not in panel.lower(), panel[:300]

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
        "Launchpad browser/server smoke passed: connect, public exam disclosure and research compute choices without a grant or agent, registration onboarding (coldkey warning, requirements, refused recovery phrase), research admission shown as subnet registration with no grant named, launch, lost-response/reload retry, pause/resume/stop, export, storage failure, restart, expiry, desktop/mobile, fixture readback/export invalidation. No scientific campaign ran."
    )


def journey():
    """A person drives the whole journey in a real browser, with no agent."""
    from carbon.development_session.research_loop import candidate_record
    from scripts.dev.miner_launchpad.journey_fixture import journey_host

    with tempfile.TemporaryDirectory(prefix="carbon-launchpad-journey-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        token = "browser-smoke-session-token-not-a-real-credential"
        store = controller.Controller(root / "runs.sqlite3")
        host = journey_host(root)
        with cdp.launch_browser(cdp.discover_browser(), 20) as (_, browser_port):
            session = cdp._open_page_session(browser_port, 10)
            try:
                session.command("Page.enable")
                session.command("Runtime.enable")
                with serving(store, token) as server:
                    server.research_runner = host
                    load(session, server.origin)
                    connect(session, token)
                    session.evaluate(
                        "document.querySelector('input[name=research-agent][value=none]').click()"
                    )
                    click(session, "research-launch")
                    wait(session, "Boolean(document.querySelector('.journey'))")
                    run_id = session.evaluate(
                        "document.querySelector('.journey').id.slice('journey-'.length)"
                    )
                    campaign = root / "campaigns" / run_id
                    # A refusal through the real route: submitting with nothing
                    # frozen is a named 409, never a 500 - the shared table's
                    # refusal is the one class this server catches.
                    import http.client

                    connection = http.client.HTTPConnection(
                        "127.0.0.1", server.server_port, timeout=5
                    )
                    connection.request(
                        "POST",
                        "/api/v1/operations/submit",
                        json.dumps({"campaign": run_id}),
                        {
                            "Authorization": "Bearer " + token,
                            "Content-Type": "application/json",
                        },
                    )
                    response = connection.getresponse()
                    assert (response.status, json.loads(response.read())) == (
                        409,
                        {"error": "freeze_a_candidate_first"},
                    )
                    connection.close()
                    wait(
                        session,
                        f"document.querySelector('.journey') && document.getElementById('journey-practice-{run_id}').disabled === false",
                    )
                    # The freeze is refused before any practice: a candidate
                    # must have a practice result.
                    assert session.evaluate(
                        f"document.getElementById('journey-freeze-{run_id}').disabled"
                    )
                    session.evaluate(
                        f"const h=document.getElementById('journey-hypothesis-{run_id}');"
                        "h.value='wider FNO lowers data loss';h.dispatchEvent(new Event('input'))"
                    )
                    click(session, f"journey-practice-{run_id}")
                    wait(
                        session,
                        f"document.getElementById('journey-freeze-{run_id}') && !document.getElementById('journey-freeze-{run_id}').disabled",
                    )
                    click(session, f"journey-freeze-{run_id}")
                    wait(
                        session,
                        f"document.getElementById('journey-submit-{run_id}') && !document.getElementById('journey-submit-{run_id}').disabled",
                    )
                    selected = json.loads(
                        (campaign / "epoch-1" / "selected-recipe.json").read_bytes()
                    )
                    assert selected == candidate_record(
                        selected["strategy"], "practiced", False
                    ), "a person's freeze writes the agent's record, by the same builder"
                    outcome = json.loads(
                        (campaign / "epoch-1" / "outcome.json").read_bytes()
                    )
                    assert outcome["selected_by"] == "miner"
                    assert outcome["chain_transactions"] == 0
                    click(session, f"journey-submit-{run_id}")
                    wait(
                        session,
                        "document.querySelector('.journey').textContent.includes('Submitted epochs: 1')",
                    )
                    assert (
                        campaign / "epoch-1" / "permitted-final-feedback.json"
                    ).exists()
                    projected = host.get(run_id)
                    assert projected["selects"] == "miner"
                    assert projected["journey"]["submitted_epochs"] == [1]
                    assert projected["state"] == "READY", projected["state"]
                exceptions = [
                    event
                    for event in session.events
                    if event["method"] == "Runtime.exceptionThrown"
                ]
                assert not exceptions, exceptions
            finally:
                session.close()
    print(
        "Launchpad journey smoke passed: with no agent, a person launched, practiced, froze and submitted in a real browser through the shared operations table; the frozen record is the agent's record, the ledger settled READY, and nothing reached the chain. Preparing, training and the final exam were fixtures."
    )


if __name__ == "__main__":
    run()
    journey()
