"""Actual Chromium/HTTP controller checks; no research or provider execution.

Run from the repository root: python scripts/dev/miner_launchpad/browser_smoke.py
Reuses Carbon's dependency-free CDP transport. Missing browser is a failure.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
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


LAUNCH_BUDGET = {"elapsed_seconds": 600, "ceilings": {"research_trials": 5}}


def _challenges():
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        BATTERY_CONTRACT,
        BURGERS_CHALLENGE,
    )

    return BATTERY_CHALLENGE, BATTERY_CONTRACT, BURGERS_CHALLENGE


BATTERY_CHALLENGE, BATTERY_CONTRACT, BURGERS_CHALLENGE = _challenges()


def choose(session, name, value):
    """Pick a wizard choice the way a person does: its radio, by value."""
    selector = f"input[name={name}][value={json.dumps(value)}]"
    wait(
        session,
        f"Boolean(document.querySelector({json.dumps(selector)}))"
        f" && !document.querySelector({json.dumps(selector)}).disabled",
    )
    session.evaluate(f"document.querySelector({json.dumps(selector)}).click()")
    wait(session, f"document.querySelector({json.dumps(selector)}).checked")


def goto(session, hash_):
    session.evaluate(f"location.hash = {json.dumps(hash_)}")
    view = hash_.lstrip("#").split("/")[0]
    wait(session, f"!document.getElementById({json.dumps(view)}).hidden")


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

    # The profile a configured host reads, which the Control Center's
    # capability document needs to offer a Challenge as launchable.
    def configured(self):
        return {
            "profile_id": "engineering-fixture",
            "principal": "fixture",
            "runtime": {},
            "paths": {},
        }

    # The two table methods the options operation needs: the profile gate and
    # its body. The budget vocabulary is the ledger's own, as on a real host.
    def owner(self):
        return {"principal": "fixture", "profile_id": "engineering-fixture"}

    def options_admitted(self, admitted, request):
        from carbon.development_session.product_campaign import BUDGET_KEYS
        from carbon.development_session.research_ledger import DIMENSIONS

        return {
            "schema": "carbon.launchpad.launch-options.v1",
            "agents": [
                {"value": "none", "availability": "available"},
                {"value": "autonomous", "availability": "available"},
            ],
            "families": [],
            "research_lanes": {
                "gpu": {
                    "availability": "unavailable",
                    "reason": "no_gpu_runtime_declared",
                }
            },
            "budget": {
                "availability": "available",
                "keys": sorted(BUDGET_KEYS),
                "ceilings": list(DIMENSIONS),
                "bounds": "none",
            },
        }

    def launch(self, value, key):
        # The page states who selects - the default is Carbon's agent - and
        # the budget is the one the person composed and saved as a template.
        # And the Challenge the person chose, exactly: there is no default.
        # And the model provider and model the person chose for the agent,
        # named on the launch; the credential stays in the runner profile.
        assert value == {
            "profile": "engineering-fixture",
            "review_digest": "fixture-review-pin",
            "agent": "autonomous",
            "budget": LAUNCH_BUDGET,
            "challenge": BATTERY_CHALLENGE,
            "challenge_version": BATTERY_CONTRACT.version,
            "model_provider": "openai-responses",
            "model": "gpt-5-mini-2025-08-07",
        }, value
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


def summary(session):
    return session.evaluate(
        "document.getElementById('composition-summary').textContent"
    )


def set_field(session, identity, value):
    session.evaluate(
        f"(() => {{ const node = document.getElementById({json.dumps(identity)});"
        f" node.value = {json.dumps(value)};"
        " node.dispatchEvent(new Event('input', {bubbles: true})); })()"
    )


def compose_and_template(session):
    """C2: one composition behind both paths, saved and loaded as a template,
    closed and checked against what is available when it is loaded."""
    assert summary(session).endswith("budget: none, no cap"), summary(session)
    click(session, "path-advanced")
    wait(session, "!document.getElementById('launch-advanced').hidden")
    # Every resource the ledger knows is offered, and only those.
    offered = session.evaluate(
        "JSON.stringify([...document.querySelectorAll('[data-ceiling]')]"
        ".map(n => n.dataset.ceiling))"
    )
    from carbon.development_session.research_ledger import DIMENSIONS

    assert json.loads(offered) == list(DIMENSIONS), offered
    assert "Research lane gpu" in session.evaluate(
        "document.getElementById('launch-availability').textContent"
    )
    set_field(session, "budget-elapsed", "0")
    wait(session, "document.getElementById('research-launch').disabled")
    assert "cannot launch: the elapsed limit" in summary(session), summary(session)
    set_field(session, "budget-elapsed", "600")
    set_field(session, "ceiling-research_trials", "5")
    wait(session, "!document.getElementById('research-launch').disabled")
    assert "600 s elapsed" in summary(session) and "research trials" in summary(
        session
    ), summary(session)
    set_field(session, "template-name", "night run")
    click(session, "template-save")
    wait(
        session,
        "[...document.getElementById('template-pick').options].some(o => o.value === 'night run')",
    )
    # Back to the quick path with nothing set: the same composition, now empty.
    set_field(session, "budget-elapsed", "")
    set_field(session, "ceiling-research_trials", "")
    click(session, "path-quick")
    wait(session, "document.getElementById('launch-advanced').hidden")
    assert summary(session).endswith("budget: none, no cap"), summary(session)
    # A template carrying anything a launch composition cannot is refused by
    # name - and the specimen, the saved one, loads.
    session.evaluate(
        "(() => { const all = JSON.parse(localStorage.getItem('carbon.launchpad.launch-templates.v1'));"
        " all['tampered'] = {...all['night run'], official: true};"
        " localStorage.setItem('carbon.launchpad.launch-templates.v1', JSON.stringify(all)); })()"
    )
    click(session, "path-advanced")
    session.evaluate("document.getElementById('template-pick').dataset.names = ''")
    wait(
        session,
        "[...document.getElementById('template-pick').options].some(o => o.value === 'tampered')",
    )
    session.evaluate("document.getElementById('template-pick').value = 'tampered'")
    click(session, "template-load")
    wait(
        session,
        "document.getElementById('message').textContent.includes('which a template cannot carry')",
    )
    assert summary(session).endswith("budget: none, no cap"), summary(session)
    session.evaluate("document.getElementById('template-pick').value = 'night run'")
    click(session, "template-load")
    wait(
        session,
        "document.getElementById('message').textContent.includes('\u201cnight run\u201d loaded')",
    )
    assert session.evaluate("document.getElementById('budget-elapsed').value") == "600"
    click(session, "path-quick")
    assert "600 s elapsed" in summary(session), summary(session)


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
                    goto(session, "#wallet")
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
                    # Every launch choice is rendered from the capability
                    # document; the person picks each one, nothing is defaulted.
                    goto(session, "#launch")
                    choose(session, "wizard-challenge", BATTERY_CHALLENGE)
                    assert session.evaluate(
                        "document.getElementById('wizard-challenge-description').textContent.includes('Objective')"
                    )
                    reserved = session.evaluate(
                        "document.getElementById('wizard-challenges').textContent"
                    )
                    assert "challenge not implemented" in reserved, reserved[:400]
                    choose(session, "research-agent", "autonomous")
                    choose(
                        session,
                        "wizard-model",
                        session.evaluate(
                            "document.querySelector('input[name=wizard-model]').value"
                        ),
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
                    # "grants nothing" (a capability request) is not an
                    # admission grant; the word itself must not appear.
                    assert not re.search(r"\bgrant\b", panel.lower()), panel[:300]
                    compose_and_template(session)

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
                        "document.getElementById('campaign-detail').textContent.includes('UI FIXTURE')",
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
                        "document.querySelector('#campaign-detail details').open = true"
                    )
                    research.record["current_hypothesis"] = {
                        "hypothesis": "UI FIXTURE updated hypothesis"
                    }
                    wait(
                        session,
                        "document.querySelector('#campaign-detail').textContent.includes('UI FIXTURE updated hypothesis')",
                    )
                    assert session.evaluate(
                        "document.querySelector('#campaign-detail details').open"
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
                        "[...document.querySelectorAll('#campaign-detail button')].every(b => b.disabled)"
                    )
                    research.recent = original_research_recent
                    wait(
                        session,
                        "document.getElementById('connection-state').textContent === 'Connected'",
                    )
                    assert session.evaluate(
                        "document.querySelector('#campaign-detail details').open"
                    )
                    for action, observed in (
                        ("pause", "PAUSE_REQUESTED"),
                        ("resume", "RUNNING"),
                        ("stop", "STOPPING"),
                        ("reconcile", "STOPPED"),
                    ):
                        wait(
                            session,
                            "![...document.querySelectorAll('#campaign-detail button')].find(b => b.textContent === "
                            + json.dumps(action)
                            + ").disabled",
                        )
                        session.evaluate(
                            "[...document.querySelectorAll('#campaign-detail button')].find(b => b.textContent === "
                            + json.dumps(action)
                            + ").click()"
                        )
                        wait(
                            session,
                            "document.getElementById('campaign-detail').textContent.includes("
                            + json.dumps(observed)
                            + ")",
                        )
                    assert len(research.keys) == 1
                    assert "UI FIXTURE stop reason" in session.evaluate(
                        "document.getElementById('campaign-detail').textContent"
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
                            "document.getElementById('campaign-detail').textContent"
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

                    campaign_hash = "#campaigns/" + research.record["id"] + "/overview"
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
                        # No horizontal page scroll on any working surface.
                        for surface in (
                            "#overview",
                            "#launch",
                            "#challenges",
                            "#compute",
                            "#wallet",
                            "#setup",
                            "#guide",
                            "#development",
                            campaign_hash,
                        ):
                            goto(session, surface)
                            assert session.evaluate(
                                "document.documentElement.scrollWidth <= innerWidth"
                            ), (width, surface)
                        # Monitoring and stop stay usable: the campaign's own
                        # controls, and the rehearsal's in the Development area.
                        assert session.evaluate(
                            "[...document.querySelectorAll('#campaign-detail button')]"
                            ".find(b => b.textContent === 'stop').getBoundingClientRect().width >= 44"
                        ), width
                        goto(session, "#development")
                        assert session.evaluate(
                            "document.getElementById('stop').getBoundingClientRect().width >= 44"
                        ), width
                        # The navigation lists every marked view, in page
                        # order, and nothing else; each entry is a target a
                        # finger can hit; and a real Enter on one moves the
                        # working surface to that view. Development is listed
                        # apart from the primary views.
                        listed = session.evaluate(
                            "JSON.stringify([...document.querySelectorAll('#tool-nav a')]"
                            ".map(a => [a.getAttribute('href'), a.textContent,"
                            " a.getBoundingClientRect().height >= 44]))"
                        )
                        marked = session.evaluate(
                            "JSON.stringify([...document.querySelectorAll('[data-nav]')]"
                            ".map(s => ['#' + s.id, s.dataset.nav, true]))"
                        )
                        assert json.loads(listed) == json.loads(marked), (width, listed)
                        assert [entry[1] for entry in json.loads(listed)] == [
                            "Overview",
                            "Campaigns",
                            "Challenges",
                            "Agents",
                            "Compute",
                            "Connections",
                            "Wallet & Identity",
                            "Set up your environment",
                            "Settings",
                            "Development",
                        ], listed
                        assert session.evaluate(
                            "[...document.querySelectorAll('#tool-nav .nav-development a')]"
                            ".map(a => a.textContent).join() === 'Development'"
                        )
                        if width == 1440:
                            assert session.evaluate(
                                "document.getElementById('tool-nav').getBoundingClientRect().right"
                                " <= document.querySelector('.shell main').getBoundingClientRect().left + 1"
                            ), "the navigation is not beside the working surface"
                        session.evaluate(
                            "scrollTo(0, 0); document.querySelector("
                            "'#tool-nav a[href=\"#campaigns\"]').focus()"
                        )
                        press(session, "Enter")
                        deadline = time.monotonic() + 3
                        while (
                            session.evaluate("location.hash") != "#campaigns"
                            and time.monotonic() < deadline
                        ):
                            time.sleep(0.05)
                        assert session.evaluate("location.hash") == "#campaigns", width
                        wait(session, "!document.getElementById('campaigns').hidden")
                        # A campaign's deep link opens that campaign.
                        goto(session, campaign_hash)
                        wait(
                            session,
                            "Boolean(document.querySelector('.frozen-guidance'))",
                        )
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
    from scripts.dev.miner_launchpad.journey_fixture import (
        FIXTURE_CHALLENGE,
        journey_host,
    )

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
                    # True availability at the moment of choosing: this host
                    # has no model-provider key, so Carbon's agent is offered
                    # as unavailable with its reason, not as a choice that
                    # would fail later.
                    wait(
                        session,
                        "document.querySelector('input[name=research-agent][value=autonomous]').disabled",
                    )
                    assert "provider key not configured" in session.evaluate(
                        "document.getElementById('research-selects').textContent"
                    )
                    # A template saved where the agent could run is checked
                    # again when it is loaded here, where it cannot: refused
                    # with the reason, and the composition is left unchanged.
                    session.evaluate(
                        "localStorage.setItem('carbon.launchpad.launch-templates.v1',"
                        " JSON.stringify({'with agent': {agent: 'autonomous'}}))"
                    )
                    session.evaluate(
                        "document.getElementById('template-pick').dataset.names = ''"
                    )
                    wait(
                        session,
                        "document.getElementById('template-pick').value === 'with agent'",
                    )
                    click(session, "template-load")
                    wait(
                        session,
                        "document.getElementById('message').textContent.includes("
                        "'not loaded: the autonomous agent is unavailable: model provider key not configured')",
                    )
                    assert not session.evaluate(
                        "document.querySelector('input[name=research-agent][value=autonomous]').checked"
                    )
                    # The fixture host registers the DEVELOPMENT-FIXTURE
                    # reference Challenge (journey_fixture); Burgers itself is
                    # retired, so the person picks the fixture here and the
                    # launch names it exactly.
                    goto(session, "#launch")
                    choose(session, "wizard-challenge", FIXTURE_CHALLENGE["id"])
                    choose(session, "research-agent", "manual")
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
                    families = session.evaluate(
                        "document.querySelector('.journey').textContent"
                    )
                    assert "freeze and submit now: fno" in families, families[:400]
                    assert "Not yet rebuildable (research only):" in families
                    assert "unet1d" in families
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
                        "document.getElementById('campaign-detail').textContent.includes('Submitted epochs: 1')",
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


class SetupChecks:
    """Fixture live checks for the setup smoke: they contact nothing."""

    def published_pricing(self, provider_id, model_id):
        return {
            "unit": "nanodollars per token",
            "input": 240,
            "cached_input": 24,
            "output_including_reasoning": 2200,
            "source": "provider_published",
            "reference": "https://llm.chutes.ai/v1/models",
            "observed": "2026-10-02T00:00:00Z",
            "note": "fixture",
        }

    def inference(self, provider_id, model_id, credential_file, spec=None):
        return {
            "models_source": "fixture",
            "models_listed": 1,
            "completion": "answered",
        }

    def compute(self, image, analysis):
        return {
            "implementation": {
                "revision": "a" * 40,
                "tree": "b" * 40,
                "source_tree_digest": "sha256:" + "c" * 64,
            },
            "images": ["sha256:" + "d" * 64, "sha256:" + "e" * 64],
        }

    def gpu(self, manifest, campaign=None):
        raise AssertionError("the smoke's miner checks the CPU, not a GPU")

    @staticmethod
    def _gpu_image():
        from carbon.reconstruction.accelerators import GPU_PROFILE
        from carbon.reconstruction.worker.model import WorkerImageIdentity

        value = "sha256:" + "9" * 64
        return WorkerImageIdentity(
            image_id=value,
            config_digest=value,
            source_tree_digest="sha256:" + "a" * 64,
            wheel_digest="sha256:" + "b" * 64,
            lock_digest=GPU_PROFILE.environment_lock_digest,
            base_image_digest="sha256:" + "1" * 64,
            build_recipe_digest="sha256:" + "d" * 64,
            entrypoint_digest="sha256:" + "e" * 64,
        )

    def remote(self, manifest, machine, campaign):
        """The miner's own machine with Docker, reached by fixture: it holds
        no worker yet, so the page offers to send it."""
        from carbon.compute.remote_route import remote_scope

        image = self._gpu_image()
        return {
            "scope": campaign.gpu_scope(image),
            "remote_scope": remote_scope(
                campaign.key.challenge_id, image, machine.transport
            ),
            "check": {
                "transport": machine.transport,
                "reached": True,
                "docker": "usable without sudo",
                "nvidia_container_toolkit": "present",
                "worker_image": "missing",
                "image_verified_by": "image-id",
            },
        }

    def send_worker(self, manifest, machine, image_id):
        SENT.append((machine.destination, image_id))
        return "sent"

    @staticmethod
    def hermes_files():
        return [
            "/hermes-fixture/profiles/carbon/config.yaml",
            "/hermes-fixture/profiles/carbon/.env",
        ]

    def hermes(self, document, key):
        raise AssertionError("the smoke's miner uses Carbon's agent")

    def intake(self, url, campaign=None):
        raise AssertionError("the smoke's validator runs beside the campaign")

    def agent(self, hotkey, socket_path=None):
        return {"signing": "carbon-miner-signer holds the registered hotkey"}

    @staticmethod
    def operator_config(path):
        raise AssertionError("the smoke's miner names no operator configuration")

    @staticmethod
    def network():
        """A miner's network read (C-MLP-04): Carbon's testnet constants and a
        fixture publisher; no chain is reached."""
        from carbon.development_session import miner_network
        from carbon.development_session.chain_onboarding import (
            carbon_testnet_context,
        )

        context = carbon_testnet_context()
        bound = miner_network.NetworkBinding(context, "5" + "P" * 47, context.netuid)
        return miner_network.document(bound, 7), 7


#: What "Send your worker" was asked to send: (destination, image ID).
SENT = []


def setup_journey():
    """After registration a person sets up inference, compute and agent in a
    real browser, and the profile is written and loaded without a restart.
    Chain, providers and images are fixtures; no key reaches the page again."""
    from onboarding import BrowserOnboarding

    from carbon.chain.models import Participant

    hotkey = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
    coldkey = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
    key = "sk-browser-smoke-fixture-key-not-real"
    with tempfile.TemporaryDirectory(prefix="carbon-setup-smoke-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        miner = root / "miner"
        miner.mkdir(mode=0o700)
        for name in ("worker.json", "analysis.json", "operator.json", "gpu.json"):
            (miner / name).write_text("{}")
        onboarding = BrowserOnboarding(
            reader=StubReader(
                (Participant(uid=0, hotkey=hotkey, coldkey=coldkey, registered_at=42),)
            ),
            context=stub_onboarding().context,
        )
        token = "browser-smoke-session-token-not-a-real-credential"
        server = controller.Server(
            controller.Controller(root / "runs.sqlite3"),
            token,
            0,
            onboarding=onboarding,
            state_dir=root / "state",
            setup_checks=SetupChecks(),
        )
        attached = []
        server.setup.attach = lambda path: attached.append(path) or True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with cdp.launch_browser(cdp.discover_browser(), 20) as (_, browser_port):
            session = cdp._open_page_session(browser_port, 10)
            try:
                session.command("Page.enable")
                session.command("Runtime.enable")
                load(session, server.origin)
                connect(session, token)
                session.evaluate("location.hash = '#wallet'")
                session.evaluate(
                    "document.getElementById('onboarding-address').value="
                    + json.dumps(hotkey)
                )
                click(session, "onboarding-confirm")
                # Confirmed: the wizard opens at its next step, and the
                # registration step shows done.
                wait(session, "location.hash === '#setup/inference'")
                wait(session, "Boolean(document.getElementById('setup-inference-key'))")
                wait(
                    session,
                    "!document.querySelector('[data-step-panel=inference]').hidden"
                    " && document.getElementById('setup-eyebrow').textContent.includes('Step 3 of 6')",
                )
                assert session.evaluate(
                    "document.querySelector('[data-step-panel=register] .step-done')"
                    ".textContent.includes('Registered')"
                )
                # Until a handshake asks it, the signer is not shown done; this
                # miner registered first, so step 1 is the one next.
                assert (
                    session.evaluate(
                        "document.querySelector('#setup-progress li:first-child').className"
                    )
                    == "is-next"
                ), "the signer is done only once a handshake has asked it"
                assert session.evaluate(
                    "document.getElementById('setup-next').disabled"
                    " && document.getElementById('setup-next-reason').textContent.includes('check')"
                )
                assert session.evaluate(
                    "document.getElementById('setup-body').textContent.includes('billed by')"
                )
                # Engy's Chat Completions route is the default choice.
                assert (
                    session.evaluate(
                        "document.getElementById('setup-inference-provider_id').value"
                    )
                    == "engy-chat"
                )
                # Chutes takes any model id it serves, typed, and is quoted
                # at its published price; it needs no endpoint from the miner.
                session.evaluate(
                    "document.getElementById('setup-inference-provider_id').value = 'chutes';"
                    "document.getElementById('setup-inference-provider_id').dispatchEvent(new Event('change'));"
                    "document.getElementById('setup-inference-model_id').value = 'Qwen/Qwen3.8-27B-TEE';"
                    "document.getElementById('setup-inference-model_id').dispatchEvent(new Event('change'));"
                )
                wait(
                    session,
                    "document.querySelector('label[for=setup-inference-consent]')"
                    ".textContent.includes('at most $')"
                    " && document.getElementById('setup-inference-endpoint').parentElement.hidden",
                )
                # A generic adapter asks for the miner's endpoint before quoting.
                session.evaluate(
                    "document.getElementById('setup-inference-provider_id').value = 'openai-compatible-chat';"
                    "document.getElementById('setup-inference-provider_id').dispatchEvent(new Event('change'));"
                    "document.getElementById('setup-inference-model_id').value = 'my-model';"
                    "document.getElementById('setup-inference-model_id').dispatchEvent(new Event('change'));"
                )
                wait(
                    session,
                    "!document.getElementById('setup-inference-endpoint').parentElement.hidden"
                    " && document.querySelector('label[for=setup-inference-consent]')"
                    ".textContent.includes('endpoint')",
                )
                session.evaluate(
                    "document.getElementById('setup-inference-provider_id').value = 'engy-chat';"
                    "document.getElementById('setup-inference-provider_id').dispatchEvent(new Event('change'));"
                    "document.getElementById('setup-inference-key').value = "
                    + json.dumps(key)
                )
                # The check's maximum cost is quoted before anything is spent,
                # nothing is agreed by default, and the check cannot run until
                # the person agrees to that amount.
                wait(
                    session,
                    "!document.getElementById('setup-inference-consent').disabled"
                    " && document.querySelector('label[for=setup-inference-consent]')"
                    ".textContent.includes('at most $')",
                )
                assert session.evaluate(
                    "!document.getElementById('setup-inference-consent').checked"
                    " && document.querySelector('form[data-step=inference] button').disabled"
                )
                session.evaluate(
                    "document.querySelector('form[data-step=inference]').requestSubmit()"
                )
                assert session.evaluate(
                    "document.getElementById('setup-result').textContent !== 'Checked: inference.'"
                )
                session.evaluate(
                    "document.getElementById('setup-inference-consent').click();"
                    "document.querySelector('form[data-step=inference]').requestSubmit()"
                )
                wait(
                    session,
                    "document.getElementById('setup-result').textContent === 'Checked: inference.'",
                )
                # The step shows done, and Next opens the following step.
                assert session.evaluate(
                    "document.querySelector('[data-step-panel=inference] .step-done')"
                    ".textContent.includes('Done')"
                )
                click(session, "setup-next")
                wait(
                    session,
                    "location.hash === '#setup/compute'"
                    " && !document.querySelector('[data-step-panel=compute]').hidden",
                )
                # No typed paths: with nothing built here, setup names the one
                # command that builds and records the images.
                assert session.evaluate(
                    "document.querySelector('form[data-step=compute]').textContent"
                    '.includes("Carbon hasn\'t found your worker images")'
                    " && document.querySelector('form[data-step=compute] .copy-line code')"
                    ".textContent.includes('install_miner.sh --no-start')"
                )
                # This machine's GPU is offered beside the CPU default, with
                # its own image field and the plain statement that GPU
                # practice is for speed only.
                assert (
                    session.evaluate(
                        "document.getElementById('setup-compute-choice').value"
                    )
                    == "this-machine-cpu"
                )
                session.evaluate(
                    "document.getElementById('setup-compute-choice').value = 'this-machine-gpu';"
                    "document.getElementById('setup-compute-choice').dispatchEvent(new Event('change'));"
                )
                wait(
                    session,
                    "!document.getElementById('setup-compute-gpu_image_manifest').parentElement.hidden"
                    " && document.querySelector('form[data-step=compute]').textContent.includes('speed only')"
                    # GPU practice is set up for a Challenge the miner chooses.
                    " && [...document.getElementById('setup-compute-challenge').options]"
                    ".some(o => JSON.parse(o.value).id === 'battery-fastcharge-ageing-development-v1')",
                )
                # Carbon rents no compute (OWNER-MINER-COMPUTE-LINK-ONLY-01):
                # this machine's CPU and GPU are offered, and the miner's own
                # remote machine or container; nothing asks for a provider
                # key.
                assert (
                    session.evaluate(
                        "[...document.getElementById('setup-compute-choice').options]"
                        ".map(o => o.value).join()"
                    )
                    == "this-machine-cpu,this-machine-gpu,remote-machine"
                )
                assert session.evaluate(
                    "!document.querySelector('form[data-step=compute] input[type=password]')"
                )
                # Where's your GPU? Each provider card sets the remote choice
                # and the transport its guide section names (LINKONLY-D10).
                from scripts.dev.miner_launchpad.environment_setup import REMOTE_GUIDES

                for guide_id, _, transport, _ in REMOTE_GUIDES:
                    click(session, "setup-where-" + guide_id)
                    wait(
                        session,
                        "document.getElementById('setup-compute-choice').value === 'remote-machine'"
                        " && document.getElementById('setup-compute-transport').value === "
                        + json.dumps(transport)
                        + " && !document.getElementById('setup-guide-panel').hidden",
                    )
                # A card shows its guide section, UNVERIFIED marks kept, and
                # the commands to copy, the destination filled in as typed.
                click(session, "setup-where-runpod")
                wait(
                    session,
                    "document.getElementById('setup-guide-panel').textContent.includes('RunPod')",
                )
                panel = session.evaluate(
                    "document.getElementById('setup-guide-panel').textContent"
                )
                assert "UNVERIFIED" in panel and "ssh-container" in panel, panel[:300]
                assert session.evaluate(
                    "document.querySelectorAll('#setup-guide-panel .unverified').length >= 2"
                )
                copies = json.loads(
                    session.evaluate(
                        "JSON.stringify([...document.querySelectorAll('#setup-guide-panel .copy-line')]"
                        ".map(l => [l.querySelector('code').textContent,"
                        " l.querySelector('button').type, l.querySelector('button').textContent]))"
                    )
                )
                assert len(copies) >= 4, copies
                assert all(
                    kind == "button" and text == "Copy" for _, kind, text in copies
                )
                assert "push_worker_image.sh" in copies[0][0], copies[0]
                session.evaluate(
                    "document.getElementById('setup-compute-destination').value = 'root@pod-1';"
                    "document.getElementById('setup-compute-destination').dispatchEvent(new Event('input'))"
                )
                wait(
                    session,
                    "[...document.querySelectorAll('#setup-guide-panel .copy-line code')]"
                    ".some(c => c.textContent === 'ssh -o BatchMode=yes root@pod-1 true')",
                )
                # The guide link opens the guide this controller serves.
                assert (
                    session.evaluate(
                        "document.getElementById('setup-guide-link').getAttribute('href')"
                    )
                    == "#guide/runpod-pods"
                )
                # The miner's own remote setup: the two built transports, and
                # the endpoint transport shown with why it is not built; the
                # wiring guide is named.
                click(session, "setup-where-own-server")
                wait(
                    session,
                    "!document.getElementById('setup-compute-destination').parentElement.hidden"
                    " && !document.getElementById('setup-compute-gpu_image_manifest').parentElement.hidden"
                    " && document.querySelector('form[data-step=compute]').textContent.includes('MINER_REMOTE_SETUP.md')"
                    " && document.getElementById('setup-compute-submit').textContent.includes('my SSH')",
                )
                transports = session.evaluate(
                    "JSON.stringify([...document.getElementById('setup-compute-transport').options]"
                    ".map(o => [o.value, o.disabled]))"
                )
                assert json.loads(transports) == [
                    ["ssh-docker", False],
                    ["ssh-container", False],
                    ["endpoint", True],
                ]
                assert (
                    session.evaluate(
                        "document.getElementById('setup-compute-transport').value"
                    )
                    == "ssh-docker"
                )
                SENT.clear()
                session.evaluate(
                    "document.getElementById('setup-compute-image_manifest').value = "
                    + json.dumps(str(miner / "worker.json"))
                    + ";document.getElementById('setup-compute-analysis_image_manifest').value = "
                    + json.dumps(str(miner / "analysis.json"))
                    + ";document.getElementById('setup-compute-gpu_image_manifest').value = "
                    + json.dumps(str(miner / "gpu.json"))
                    + ";document.getElementById('setup-compute-destination').value = 'miner@gpu-box';"
                    "document.querySelector('form[data-step=compute]').requestSubmit()"
                )
                wait(
                    session,
                    "document.getElementById('setup-result').textContent === 'Checked: compute.'"
                    " && Boolean(document.getElementById('setup-send-worker-consent'))",
                )
                # Checked, but not done until the worker is there: Next waits.
                assert session.evaluate(
                    "document.getElementById('setup-next').disabled"
                    " && document.getElementById('setup-next-reason').textContent.includes('Send your worker')"
                )
                # Sending the worker is its own step: nothing is agreed by
                # default and the consent names the destination and image.
                assert session.evaluate(
                    "!document.getElementById('setup-send-worker-consent').checked"
                    " && document.querySelector('form[data-step=send_worker] button').disabled"
                    " && document.querySelector('label[for=setup-send-worker-consent]')"
                    ".textContent.includes('miner@gpu-box')"
                )
                assert SENT == []
                session.evaluate(
                    "document.getElementById('setup-send-worker-consent').click();"
                    "document.querySelector('form[data-step=send_worker]').requestSubmit()"
                )
                wait(
                    session,
                    "document.getElementById('setup-result').textContent === 'Checked: send_worker.'"
                    " && !document.getElementById('setup-send-worker-consent')",
                )
                assert SENT == [("miner@gpu-box", SetupChecks._gpu_image().image_id)]
                session.evaluate(
                    "document.getElementById('setup-compute-choice').value = 'this-machine-cpu';"
                    "document.getElementById('setup-compute-choice').dispatchEvent(new Event('change'));"
                )
                assert session.evaluate(
                    "document.getElementById('setup-compute-gpu_image_manifest').parentElement.hidden"
                )
                # A missing image is refused by name, with its build step.
                session.evaluate(
                    "document.getElementById('setup-compute-image_manifest').value = "
                    + json.dumps(str(miner / "absent.json"))
                    + ";document.getElementById('setup-compute-analysis_image_manifest').value = "
                    + json.dumps(str(miner / "analysis.json"))
                    + ";document.querySelector('form[data-step=compute]').requestSubmit()"
                )
                wait(
                    session,
                    "document.getElementById('setup-result').textContent.startsWith('image manifest: ')"
                    " && document.getElementById('setup-result').textContent.includes('c03_worker_image.sh')",
                )
                session.evaluate(
                    "document.getElementById('setup-compute-image_manifest').value = "
                    + json.dumps(str(miner / "worker.json"))
                    + ";document.getElementById('setup-compute-analysis_image_manifest').value = "
                    + json.dumps(str(miner / "analysis.json"))
                    + ";document.querySelector('form[data-step=compute]').requestSubmit()"
                )
                wait(
                    session,
                    "document.getElementById('setup-result').textContent === 'Checked: compute.'",
                )
                click(session, "setup-next")
                wait(
                    session,
                    "location.hash === '#setup/agent'"
                    " && !document.querySelector('[data-step-panel=agent]').hidden",
                )
                # Hermes is offered beside Carbon's agent, and names the exact
                # files it would write; nothing is agreed by default.
                session.evaluate(
                    "document.getElementById('setup-agent-choice').value = 'hermes';"
                    "document.getElementById('setup-agent-choice').dispatchEvent(new Event('change'));"
                )
                wait(
                    session,
                    "!document.getElementById('setup-agent-hermes-consent').checked"
                    " && document.querySelector('label[for=setup-agent-hermes-consent]')"
                    ".textContent.includes('profiles/carbon/config.yaml')"
                    " && document.querySelector('label[for=setup-agent-hermes-consent]')"
                    ".textContent.includes('hermes -p carbon chat')",
                )
                session.evaluate(
                    "document.getElementById('setup-agent-choice').value = 'carbon-autonomous';"
                    "document.getElementById('setup-agent-choice').dispatchEvent(new Event('change'));"
                )
                # External signing: the Agent step asks for no hotkey file
                # and no password; it only asks the miner's signer.
                assert (
                    session.evaluate(
                        "document.querySelectorAll('form[data-step=agent] input[type=password],"
                        " #setup-agent-hotkey_file, #setup-agent-password').length"
                    )
                    == 0
                )
                # A miner names no operator file: setup reads the network.
                assert session.evaluate(
                    "document.querySelector('label[for=setup-agent-operator_config]')"
                    ".textContent.includes('operators only')"
                )
                session.evaluate(
                    "document.querySelector('form[data-step=agent]').requestSubmit()"
                )
                wait(
                    session,
                    "document.getElementById('setup-result').textContent === 'Checked: agent.'",
                )
                # The Agent step asked the signer: step 1 is done only now.
                wait(
                    session,
                    "document.querySelector('#setup-progress li:first-child').className === 'is-done'",
                )
                click(session, "setup-next")
                wait(
                    session,
                    "location.hash === '#setup/review'"
                    " && !document.querySelector('[data-step-panel=review]').hidden",
                )
                session.evaluate(
                    "document.querySelector('form[data-step=review]').requestSubmit()"
                )
                wait(
                    session,
                    "document.getElementById('setup-result').textContent.startsWith('Profile written and loaded')",
                )
                assert attached == [server.setup.profile_path]
                # Overview: five steps confirmed, and the sixth is the next,
                # since no campaign is on record yet.
                goto(session, "#overview")
                wait(
                    session,
                    "document.querySelectorAll('#getting-started-steps .gs-step.is-done').length === 5",
                )
                assert (
                    session.evaluate(
                        "document.querySelector('#getting-started-steps .is-current').dataset.step"
                    )
                    == "review"
                )
                page = session.evaluate("document.documentElement.outerHTML")
                assert key not in page
                written = (
                    server.setup.profile_path.read_text(),
                    server.setup.record_path.read_text(),
                )
                assert not any(key in text for text in written)
                # Nothing that could open the miner's key reaches the profile.
                assert not any(
                    field in text
                    for text in written
                    for field in ('"miner_password_file"', '"key_file"')
                )
                exceptions = [
                    event
                    for event in session.events
                    if event["method"] == "Runtime.exceptionThrown"
                ]
                assert not exceptions, exceptions
            finally:
                session.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
    print(
        "Launchpad setup smoke passed: after a confirmed registration a person set up inference, compute and agent in a real browser, one wizard step at a time with each step done only once checked and the signer done only after the Agent step asked it; each Where's your GPU? card set the transport its guide section names and showed that section, UNVERIFIED marks kept, with its commands to copy; they checked their own remote machine and sent it the worker only after agreeing to that destination and image, a missing image was refused by name with its build step, and the profile was written and loaded without a restart; no API key reached the page or the profile, and the Agent step asked only the miner's signer. Chain, providers, SSH and images were fixtures."
    )


def fresh_miner():
    """A brand-new miner lands on the Control Center (LINKONLY-D10): one
    ordered list with its next step, setup that leads with that step, plain
    statuses each with the place that fixes it, the remote route beside this
    machine, and the guide and Carbon's font served by this controller with
    nothing fetched from anywhere else. Chain and checks are fixtures."""
    with tempfile.TemporaryDirectory(prefix="carbon-fresh-miner-smoke-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        token = "browser-smoke-session-token-not-a-real-credential"
        server = controller.Server(
            controller.Controller(root / "runs.sqlite3"),
            token,
            0,
            onboarding=stub_onboarding(),
            state_dir=root / "state",
            setup_checks=SetupChecks(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with cdp.launch_browser(cdp.discover_browser(), 20) as (_, browser_port):
            session = cdp._open_page_session(browser_port, 10)
            try:
                session.command("Page.enable")
                session.command("Runtime.enable")
                session.command("Network.enable")
                load(session, server.origin)
                connect(session, token)
                goto(session, "#overview")
                wait(
                    session,
                    "document.querySelectorAll('#getting-started-steps .gs-step').length === 6",
                )
                steps = json.loads(
                    session.evaluate(
                        "JSON.stringify([...document.querySelectorAll('#getting-started-steps .gs-step')]"
                        ".map(s => [s.dataset.step, s.className, s.querySelector('.gs-state').textContent]))"
                    )
                )
                assert [s[0] for s in steps] == [
                    "signer",
                    "register",
                    "inference",
                    "compute",
                    "agent",
                    "review",
                ], steps
                # Nothing is confirmed yet, so nothing is done. One step reads
                # Next, the signer; registration is open beside it, in either
                # order, and says so.
                assert [s[2] for s in steps] == ["Next", "Open"] + ["Waiting"] * 4
                assert session.evaluate(
                    "document.querySelector('#getting-started-steps [data-step=register]')"
                    ".textContent.includes('either order')"
                )
                assert "is-current" in steps[0][1]
                primary = json.loads(
                    session.evaluate(
                        "JSON.stringify([document.getElementById('overview-primary').textContent,"
                        " document.getElementById('overview-primary').getAttribute('href')])"
                    )
                )
                assert primary == ["Next: Start your signer", "#setup/signer"], primary
                # The same step leads in setup, with its command to copy; the
                # steps after registration are locked until it is confirmed.
                session.evaluate("document.getElementById('overview-primary').click()")
                wait(
                    session,
                    "location.hash === '#setup/signer'"
                    " && !document.querySelector('[data-step-panel=signer]').hidden",
                )
                assert session.evaluate(
                    "document.getElementById('setup-signer-copy').type === 'button'"
                    " && document.querySelector('[data-step-panel=signer] code')"
                    ".textContent.includes('--wallet <your wallet> --hotkey <your hotkey>')"
                )
                locked = json.loads(
                    session.evaluate(
                        "JSON.stringify([...document.querySelectorAll('#setup-progress button')]"
                        ".map(b => b.disabled))"
                    )
                )
                assert locked == [False, False, True, True, True, True], locked
                # The signer is checked here, before registration: its public
                # address names the socket and it says which hotkey it holds.
                session.evaluate(
                    "document.getElementById('setup-signer-address').value = "
                    + json.dumps("5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
                )
                click(session, "setup-signer-check")
                wait(
                    session,
                    "document.getElementById('setup-result').textContent === 'Checked: signer.'"
                    " && document.querySelector('#setup-progress li:first-child').className === 'is-done'"
                    " && document.querySelector('[data-step-panel=signer] .step-done') !== null",
                )
                click(session, "setup-next")
                wait(
                    session,
                    "location.hash === '#setup/register'"
                    " && document.getElementById('setup-next').disabled"
                    " && document.getElementById('setup-next-reason').textContent"
                    ".includes('Confirm your registration first')",
                )
                assert session.evaluate(
                    "Boolean(document.getElementById('setup-register-confirm'))"
                    " && document.querySelector('[data-step-panel=register] a[href=\"#wallet\"]') !== null"
                )
                # The signer answered: step 1 is done, and registration is the
                # one next.
                goto(session, "#overview")
                wait(
                    session,
                    "document.querySelector('#getting-started-steps .is-current').dataset.step === 'register'",
                )
                # A hotkey the chain does not read as registered is refused in
                # place, with where to prepare the registration.
                goto(session, "#setup/register")
                session.evaluate(
                    "document.getElementById('setup-register-address').value = "
                    + json.dumps("5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
                    + ";document.getElementById('setup-register-confirm').click()"
                )
                wait(
                    session,
                    "document.getElementById('setup-result').textContent.includes('Not registered')",
                )
                assert session.evaluate("location.hash") == "#setup/register"
                # Plain statuses: one sentence and the place that fixes it,
                # with the machine code kept behind Details.
                goto(session, "#challenges")
                wait(
                    session,
                    "Boolean(document.querySelector('#challenge-catalog .card'))",
                )
                fixes = json.loads(
                    session.evaluate(
                        "JSON.stringify([...document.querySelectorAll('#challenge-catalog .card')]"
                        ".filter(c => c.querySelector('.pill').textContent === 'Set up first')"
                        ".map(c => [c.querySelector('.status-line').textContent,"
                        " c.querySelector('a.fix').getAttribute('href'),"
                        " c.querySelector('details:last-of-type').textContent]))"
                    )
                )
                assert fixes, "an implemented Challenge waits on setup"
                for sentence, href, hidden in fixes:
                    assert sentence == "Finish setup first." and href == "#setup"
                    assert "research_profile_not_configured" in hidden
                visible = session.evaluate(
                    "[...document.querySelectorAll('#challenge-catalog .status-line')]"
                    ".map(p => p.textContent).join(' ')"
                )
                assert "_" not in visible, visible
                # Compute: this machine and a GPU run elsewhere, side by side.
                goto(session, "#compute")
                wait(
                    session,
                    "document.querySelectorAll('#compute-catalog .card').length >= 2",
                )
                routes = json.loads(
                    session.evaluate(
                        "JSON.stringify([...document.querySelectorAll('#compute-catalog .card')]"
                        ".map(c => [c.querySelector('h3').textContent,"
                        " (c.querySelector('a.button') || {}).getAttribute"
                        " ? c.querySelector('a.button').getAttribute('href') : null]))"
                    )
                )
                assert routes[0] == ["This machine", "#setup"], routes
                assert routes[1] == [
                    "A GPU you run elsewhere",
                    "#setup/compute",
                ], routes
                # The guide opens here, read from this checkout.
                goto(session, "#guide")
                wait(
                    session,
                    "document.getElementById('guide-body').textContent.includes('Per-provider notes')",
                )
                assert session.evaluate(
                    "document.querySelectorAll('#guide-body .unverified').length >= 5"
                    " && document.getElementById('guide-heading').textContent"
                    ".startsWith('Practising on your own remote machine')"
                )
                # Carbon's font, from this controller.
                assert session.evaluate(
                    "document.fonts.ready.then(() => document.fonts.check('600 16px Montreal')"
                    " && getComputedStyle(document.body).fontFamily.startsWith('Montreal'))"
                ), "the Montreal face is declared, loaded and used"
                wait(
                    session,
                    "[...document.fonts].some(f => f.family === 'Montreal' && f.status === 'loaded')",
                )
                fetched = [
                    event["params"]["request"]["url"]
                    for event in session.events
                    if event["method"] == "Network.requestWillBeSent"
                ]
                assert any(
                    url.endswith("/fonts/neue-0.otf") for url in fetched
                ), fetched
                outside = [
                    url
                    for url in fetched
                    if not url.startswith(server.origin + "/")
                    and not url.startswith(("data:", "blob:"))
                ]
                assert not outside, outside
                # Exactly one step reads Next at a time.
                assert (
                    session.evaluate(
                        "[...document.querySelectorAll('#getting-started-steps .gs-state')]"
                        ".filter(p => p.textContent === 'Next').length"
                    )
                    == 1
                )
                for width in (1440, 800, 390):
                    session.command(
                        "Emulation.setDeviceMetricsOverride",
                        {
                            "width": width,
                            "height": 900,
                            "deviceScaleFactor": 1,
                            "mobile": False,
                        },
                    )
                    for surface in ("#overview", "#setup/signer", "#compute", "#guide"):
                        goto(session, surface)
                        assert session.evaluate(
                            "document.documentElement.scrollWidth <= innerWidth"
                        ), (width, surface)
                        # The navigation wraps: no view is cut off or behind
                        # a sideways scroll.
                        assert session.evaluate(
                            "(() => { const nav = document.getElementById('tool-nav');"
                            " return nav.scrollWidth <= nav.clientWidth"
                            " && [...nav.querySelectorAll('a')].every(a =>"
                            " a.getBoundingClientRect().right <= innerWidth + 0.5); })()"
                        ), (width, surface)
                exceptions = [
                    event
                    for event in session.events
                    if event["method"] == "Runtime.exceptionThrown"
                ]
                assert not exceptions, exceptions
            finally:
                session.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
    print(
        "Launchpad fresh-miner smoke passed: a new miner saw six ordered steps with nothing done and one step next (the signer, registration open beside it in either order), setup led with that step, checked the signer before registration by its handshake and locked the steps after registration, the navigation wrapped at 800 and 390 px, a hotkey the chain did not read as registered was refused in place, each blocking Challenge said one plain sentence with its fix and kept its code behind Details, Compute listed this machine and a GPU run elsewhere, the guide and Carbon's font came from this controller, and nothing was fetched from anywhere else."
    )


if __name__ == "__main__":
    run()
    journey()
    setup_journey()
    fresh_miner()
