"""The browser's door onto onboarding, over the real loopback server.

Drives the actual HTTP surface rather than the adapter behind it. No chain is
contacted: where a read is exercised, the reader is a device-free stub.

The property under test is the access tier. Onboarding is open, because it
exists for people who are not registered yet, and open means it must not be
possible to reach a campaign, compute or the ledger through it.
"""

import http.client
import importlib.util
import json
import threading
from pathlib import Path

import pytest

from carbon.chain.models import (
    CARBON_NETUID,
    CARBON_NETWORK,
    ChainContext,
    MetagraphSnapshot,
    Participant,
)

MODULE = (
    Path(__file__).resolve().parents[2] / "scripts/dev/miner_launchpad/controller.py"
)
SPEC = importlib.util.spec_from_file_location("carbon_launchpad_onboarding", MODULE)
launchpad = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launchpad)

TOKEN = "x" * 40
HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
COLDKEY = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"


class _Reader:
    def __init__(self, participants=()):
        self.participants = participants

    async def capture(self, context):
        return MetagraphSnapshot(
            context=context,
            finalized_block=100,
            block_hash="0x" + "cd" * 32,
            timestamp_ms=1,
            participants=tuple(self.participants),
        )


def _context():
    return ChainContext(
        network=CARBON_NETWORK,
        endpoint="wss://entrypoint-finney.opentensor.ai:443",
        provider="test",
        genesis_hash="0x" + "ab" * 32,
        netuid=CARBON_NETUID,
    )


@pytest.fixture
def server(tmp_path, request):
    from scripts.dev.miner_launchpad.onboarding import BrowserOnboarding

    # Always a stub, never the default live reader. The door now defaults to
    # Carbon's real testnet, which is right for a deployment and wrong for a
    # test: without this the unparameterised cases would make actual network
    # attempts, and their results would depend on whether testnet answered.
    # That is what this file's "no chain is contacted" promise means, and it
    # has to be kept here rather than relied on from the door's defaults.
    reader = getattr(request, "param", None) or _Reader()
    onboarding = BrowserOnboarding(reader=reader, context=_context())
    controller = launchpad.Controller(tmp_path / "runs.sqlite3")
    server = launchpad.Server(controller, TOKEN, port=0, onboarding=onboarding)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def call(server, path, body=None, token=TOKEN):
    headers = {"Authorization": "Bearer " + token} if token else {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    connection.request(
        "POST" if body is not None else "GET",
        path,
        json.dumps(body) if body is not None else None,
        headers,
    )
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    return response.status, (json.loads(payload) if payload else None)


def test_requirements_answers_for_an_unregistered_visitor(server):
    """The first thing an unregistered visitor meets has to work for them."""
    status, body = call(server, "/api/v1/onboarding/requirements")
    assert status == 200
    assert body["mechanism"] == "BURNED_REGISTRATION"
    assert body["netuid"] == CARBON_NETUID
    assert body["cost"]["value"] == "NOT_READ"
    assert not server.research_runner, "no research profile is configured here"


def test_the_door_defaults_to_carbons_actual_testnet(tmp_path):
    """Replaces an assertion that the chain was unconfigured.

    It was, and it did not need to be: the endpoint, genesis hash and chain id
    were already settled constants in `carbon.development_testnet.operator`,
    and this door simply was not reading them. Reporting CHAIN_NOT_CONFIGURED
    for want of a decision that had already been made is the wrong kind of
    honest - truthful about the door, misleading about the deployment.
    """
    from scripts.dev.miner_launchpad.onboarding import BrowserOnboarding

    door = BrowserOnboarding()
    assert door.chain_configured is True
    assert door.context.netuid == CARBON_NETUID
    assert door.context.network == CARBON_NETWORK
    assert door.context.endpoint.startswith("wss://")


def test_requirements_shows_no_cost_figure(server):
    import re

    _status, body = call(server, "/api/v1/onboarding/requirements")
    numbers = re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])", json.dumps(body))
    assert set(numbers) <= {str(CARBON_NETUID)}, numbers


def test_the_onboarding_door_still_requires_the_session_token(server):
    """Open tier means no registration, not an unauthenticated local server."""
    assert call(server, "/api/v1/onboarding/requirements", token=None)[0] == 401
    assert (
        call(server, "/api/v1/onboarding/status", {"address": HOTKEY}, token=None)[0]
        == 401
    )


def test_an_unconfigured_chain_is_still_a_supported_state():
    """The refusal still exists; the browser door just no longer needs it.

    Kept at the service, where it remains reachable, because an operator can
    still construct a door without a chain and the answer must stay actionable
    rather than becoming an error. Asserted here so removing the path would
    fail rather than pass quietly.
    """
    import asyncio

    from carbon.development_session.chain_onboarding import OnboardingFailure
    from carbon.miner_mcp.mcp_onboarding import onboarding_records

    # The check is the adapter's, not the service's: the service is handed a
    # reader and a context and assumes both, which is why asserting it here
    # rather than one layer down is the truthful placement.
    run = onboarding_records(None, None)
    with pytest.raises(OnboardingFailure) as raised:
        asyncio.run(run("status", HOTKEY))
    assert raised.value.reason == "CHAIN_NOT_CONFIGURED"
    assert "your own wallet tooling" in raised.value.next_action


@pytest.mark.parametrize("server", [_Reader()], indirect=True)
def test_status_reports_unregistered_and_keeps_the_environment_locked(server):
    status, body = call(server, "/api/v1/onboarding/status", {"address": HOTKEY})
    assert status == 200
    assert body["registered"] is False
    assert body["research_environment"] == "LOCKED"


@pytest.mark.parametrize(
    "server",
    [_Reader((Participant(uid=0, hotkey=HOTKEY, coldkey=COLDKEY, registered_at=42),))],
    indirect=True,
)
def test_status_unlocks_once_registered(server):
    status, body = call(server, "/api/v1/onboarding/status", {"address": HOTKEY})
    assert status == 200
    assert body["registered"] is True and body["uid"] == 0
    assert body["research_environment"] == "UNLOCKED"


@pytest.mark.parametrize("server", [_Reader()], indirect=True)
def test_prepare_returns_an_unsigned_registration_over_http(server):
    status, body = call(server, "/api/v1/onboarding/prepare", {"address": HOTKEY})
    assert status == 200
    assert body["signed"] is False and body["signed_by_carbon"] is False
    assert body["extrinsic"] == "BurnedRegister"
    assert body["execute_in"] == "your own wallet tooling"


@pytest.mark.parametrize("server", [_Reader()], indirect=True)
def test_a_pasted_seed_phrase_is_refused_and_never_echoed(server):
    """The refusal a miner most needs, exercised through the real request path."""
    phrase = "bottom drive obey lake curtain smoke basket hold race lonely fit walk"
    status, body = call(server, "/api/v1/onboarding/status", {"address": phrase})
    assert status == 409
    assert body["reason"] == "REFUSED_KEY_MATERIAL"
    rendered = json.dumps(body)
    for word in phrase.split():
        assert word not in rendered


@pytest.mark.parametrize(
    "path", ["/api/v1/onboarding/status", "/api/v1/onboarding/prepare"]
)
def test_the_request_shape_is_closed(server, path):
    """A browser cannot smuggle a network, an endpoint or a key into a read."""
    for body in (
        {},
        {"address": HOTKEY, "netuid": 1},
        {"address": HOTKEY, "endpoint": "wss://elsewhere.example"},
        {"address": HOTKEY, "mnemonic": "x"},
    ):
        status, _ = call(server, path, body)
        assert status == 400, body


def test_an_unknown_onboarding_action_is_not_found(server):
    assert call(server, "/api/v1/onboarding/sign", {"address": HOTKEY})[0] == 404


def test_the_open_tier_creates_no_campaign_and_touches_no_ledger(server, tmp_path):
    """The tier boundary as a rule rather than a list of endpoints.

    Stated this way it survives new routes: whatever onboarding grows, it must
    not create a campaign, consume compute or write the ledger.
    """
    call(server, "/api/v1/onboarding/requirements")
    call(server, "/api/v1/onboarding/status", {"address": HOTKEY})
    call(server, "/api/v1/onboarding/prepare", {"address": HOTKEY})

    assert server.controller.recent() == [], "no run was created"
    assert list(tmp_path.glob("**/campaign.sqlite3")) == []
    assert list(tmp_path.glob("**/campaign-manifest.json")) == []


def test_no_test_in_this_file_contacts_a_chain(server):
    """The promise in this file's docstring, made checkable.

    The door defaults to a live reader against Carbon's testnet, which is
    correct for a deployment. A test inheriting that default would make real
    network calls and pass or fail on whether testnet answered - so the fixture
    injects a stub, and this asserts it did rather than trusting that it will
    keep doing so.
    """
    from carbon.chain.sdk import BittensorReader

    assert type(server.onboarding.reader) is _Reader
    assert not isinstance(server.onboarding.reader, BittensorReader)


def test_the_coldkey_requirement_appears_where_a_miner_reads_it():
    """The first thing a new miner gets wrong, put in front of them.

    `requirements()` has always said the balance must be on the coldkey, but it
    said it inside a returned list. "My hotkey has funds" is the natural
    misreading - the transaction is signed for the hotkey being registered and
    the balance is taken from the coldkey that owns it - so the word has to be
    in the surface a person looks at, not only in the payload behind it.

    Asserted on the page rather than on the payload for exactly that reason: a
    test against `requirements()` would have passed all along while no miner
    could see it.
    """
    from pathlib import Path

    page = Path("scripts/dev/miner_launchpad/index.html").read_text()
    assert "COLDKEY" in page.upper()
    assert "onboarding-panel" in page, "the registration step needs a surface"
    # The distinction, not merely the word: hotkey and coldkey named together
    # where the difference is what matters.
    coldkey_notice = page[page.index("onboarding-coldkey") :][:600]
    assert "hotkey" in coldkey_notice.lower()


def test_the_browser_actually_calls_the_onboarding_endpoints():
    """The endpoints existed and nothing a miner looked at reached them.

    A human with no agent could not begin the journey, which is the extreme the
    agent step is required to work at. Asserted over the script rather than
    through a browser, because no browser runs in this suite - so this proves
    the wiring exists, not that it renders.
    """
    from pathlib import Path

    script = Path("scripts/dev/miner_launchpad/app.js").read_text()
    for action in ("requirements", "status", "prepare", "confirm"):
        assert "/api/v1/onboarding/" in script
        assert action in script, action
    assert "onboardingRequirements()" in script, "defined but never invoked"


def test_an_unconfigured_chain_and_an_unreachable_one_stay_distinct():
    """Two different facts that a single reason code would merge.

    CHAIN_NOT_CONFIGURED means this deployment was never pointed at a chain;
    CHAIN_UNAVAILABLE means it was and the chain did not answer. The first is
    Carbon's to fix and the second is not, so collapsing them would send a
    miner to the wrong place. Asserted as distinct refusals rather than as
    distinct strings.
    """
    import asyncio

    from carbon.development_session.chain_onboarding import OnboardingFailure
    from carbon.miner_mcp.mcp_onboarding import onboarding_records

    unconfigured = onboarding_records(None, None)
    with pytest.raises(OnboardingFailure) as absent:
        asyncio.run(unconfigured("status", HOTKEY))
    assert absent.value.reason == "CHAIN_NOT_CONFIGURED"

    class _Unreachable:
        async def capture(self, context):
            from carbon.chain.models import ChainFailure, FailureCode

            raise ChainFailure(FailureCode.UNSUPPORTED)

    reachable_config = onboarding_records(_Unreachable(), _context())
    with pytest.raises(OnboardingFailure) as unreachable:
        asyncio.run(reachable_config("status", HOTKEY))
    assert unreachable.value.reason == "CHAIN_UNAVAILABLE"
    assert unreachable.value.reason != absent.value.reason


def test_locked_is_a_gate_and_not_a_label():
    """LOCKED has to mean a refusal happens, not that a string says so.

    An unregistered address reports LOCKED; the property that matters is that
    nothing downstream treats it as admitted. Asserted by checking the
    registered flag the gate is derived from, so a surface that printed LOCKED
    while admitting the caller would fail here.
    """
    import asyncio

    from carbon.development_session.chain_onboarding import status

    unregistered = asyncio.run(status(_Reader(), _context(), HOTKEY))
    assert unregistered["research_environment"] == "LOCKED"
    assert unregistered["registered"] is False
    assert unregistered.get("uid") is None

    registered = asyncio.run(
        status(
            _Reader(
                (Participant(uid=0, hotkey=HOTKEY, coldkey=COLDKEY, registered_at=42),)
            ),
            _context(),
            HOTKEY,
        )
    )
    assert registered["research_environment"] == "UNLOCKED"
    assert registered["registered"] is True and registered["uid"] == 0


def test_the_registration_panel_obeys_the_pages_connection_state():
    """A control that ignores the connection state fails as a raw 401.

    Every other control on this page is disabled until the browser connects and
    every handler returns early while a request is in flight. The registration
    panel was wired without either, so a click before connecting produced an
    authorization error rather than an explanation, and a double click issued
    concurrent requests.

    Asserted over the script because no browser runs in this suite: this proves
    the panel participates in the same state machine, not that it renders.
    """
    from pathlib import Path

    script = Path("scripts/dev/miner_launchpad/app.js").read_text()

    assert "renderOnboarding();" in script, "the panel must re-render with the page"
    for control in (
        "onboarding-address",
        "onboarding-status",
        "onboarding-prepare",
        "onboarding-confirm",
    ):
        assert control in script, control
    assert "!connected || busy" in script, "controls must disable when disconnected"

    # The handler guard, in the same form the rest of the file uses.
    guarded = script[script.index("async function onboardingCall") :][:200]
    assert "if (busy || !connected) return;" in guarded

    # A disconnected page explains itself rather than showing an empty list.
    assert "local session token" in script


def test_the_registration_controls_are_disabled_before_any_script_runs():
    """The browser caught this; source assertions had passed.

    `renderOnboarding()` disables the controls whenever the page is
    disconnected, but nothing calls `render()` before the first connect - so
    between first paint and connecting they were live, and a click produced the
    raw 401 the state-machine wiring was supposed to prevent.

    The page's own convention is the markup attribute, as `launch-fields`
    already does. Asserted here because a JS-only guard is a guard that has not
    run yet, and that distinction is invisible to a test that reads the script.
    """
    import re
    from pathlib import Path

    page = Path("scripts/dev/miner_launchpad/index.html").read_text()
    for control in (
        "onboarding-address",
        "onboarding-status",
        "onboarding-prepare",
        "onboarding-confirm",
    ):
        element = re.search(r"<(?:input|button) id=\"" + control + r"\"[^>]*>", page)
        assert element, control
        assert "disabled" in element.group(0), control

    # And the script must still be the thing that releases them, or they would
    # stay disabled forever.
    script = Path("scripts/dev/miner_launchpad/app.js").read_text()
    assert "!connected || busy" in script
