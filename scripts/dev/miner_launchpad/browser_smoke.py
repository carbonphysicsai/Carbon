"""Actual Chromium/HTTP controller checks; no research or provider execution.

Run from the repository root: python scripts/dev/miner_launchpad/browser_smoke.py
Reuses Carbon's dependency-free CDP transport. Missing browser is a failure.
"""

from __future__ import annotations

import contextlib
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
        "Launchpad browser/server smoke passed: connect, launch, lost-response/reload retry, pause/resume/stop, export, storage failure, restart, expiry, desktop/mobile."
    )


if __name__ == "__main__":
    run()
