"""LP-PROD-W2: cross-slice handoffs of the Launchpad's campaign runtime.

1. The miner's Reconcile settles a model call whose outcome is unknown
   (LP-PROD-A's settlement, reached from LP-PROD-C's reconcile action): booked
   at the call's full reservation, inside the campaign's owner lock and a
   fresh control generation, so the campaign can resume; what was settled is
   in the campaign's readback, and a refused settlement answers its closed
   code with its next step. Pause and stop never settle one; nor does the
   development CLI for a campaign it does not control.
2. A runner profile that no longer describes what the installer installed
   (LP-PROD-E's staleness check) is never attached: not by the Control
   Center on start or from setup, and not by `carbon-mcp --configuration`
   (both construct the host through `RunnerAdapter.for_profile`).

Every transport here is a FIXTURE: no provider is contacted, no key is real,
no chain is read and nothing is spent.
"""

from __future__ import annotations

import asyncio
import http.client
import json
import socket
import sys
import threading
from pathlib import Path

import pytest
from test_miner_launchpad_environment_setup import (
    CONSENT,
    HOTKEY,
    KEY,
    REVISION,
    RUNTIME,
    Checks,
    Onboarding,
)
from test_model_provider import completed, request

from carbon.development_session import research_agent as ra
from carbon.development_session import research_campaign
from carbon.development_session.profile import canonical
from carbon.development_session.research_agent import (
    RESERVATION_NANO,
    SETTLEMENT_ACCOUNTING,
    SETTLEMENT_REFUSALS,
    ProviderCallFailed,
    request_model,
    uncertain_calls,
)
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import CampaignLedger
from scripts.dev.miner_launchpad import controller
from scripts.dev.miner_launchpad import environment_setup as environment
from scripts.dev.miner_launchpad.campaign_view import reconciliation
from scripts.dev.miner_launchpad.controller import Rejected, error_body, owner_lock
from scripts.dev.miner_launchpad.environment_setup import (
    AUTONOMOUS,
    INSTALLATION_SCHEMA,
    LOCAL_CPU,
    PROFILE_RECHECK_STEP,
    REINSTALL_STEP,
    EnvironmentSetup,
    profile_staleness,
    write_private,
)
from scripts.dev.miner_launchpad.journey_fixture import FIXTURE_CHALLENGE, journey_host
from scripts.dev.miner_launchpad.operations import perform
from scripts.dev.miner_launchpad.runner import (
    CARBON_UPDATED,
    RunnerAdapter,
    install_refusal,
    validated_profile,
)
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

#: The journey fixture's campaign owner (`journey_fixture`).
OWNER = "miner-requester"
NEW = "f" * 40
TOKEN = "w2-fixture-session-token-" + "0" * 16
RECONCILE = {"action": "reconcile", "operation": "halt"}


# --- 1. the reconcile action settles a model call whose outcome is unknown ----


@pytest.fixture
def host(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    value = journey_host(tmp_path, patch=monkeypatch.setattr)
    monkeypatch.setattr(RunnerAdapter, "spawn", staticmethod(lambda _: None))
    yield value
    value.close()


def launched(host):
    """A miner's campaign (no agent), prepared and READY: its id and root."""
    identity = perform(
        host,
        "launch",
        {
            "challenge": FIXTURE_CHALLENGE["id"],
            "challenge_version": FIXTURE_CHALLENGE["version"],
            "agent": "none",
            "idempotency_key": "w2-launch-key-000001",
        },
    )["id"]
    for thread in list(host.threads.values()):
        thread.join(timeout=30)
        assert not thread.is_alive()
    return identity, Path(host._bound(identity)[2])


def timeout(_request):
    raise TimeoutError("timed out")


def timed_out(root, identity="model-1"):
    """What a run leaves when its model call times out: the call RESERVED at
    its full reservation, nothing resent, and once the run has ended the
    campaign awaiting reconciliation."""
    ledger = CampaignLedger(root)
    ledger.generation = CampaignControl(ledger).acquire()
    with pytest.raises(ProviderCallFailed):
        request_model(
            ledger,
            owner=OWNER,
            identity=identity,
            request=request(),
            credential_file=None,
            transport=timeout,
            sleep=pytest.fail,
        )
    CampaignControl(ledger).settled(ledger.generation, cleanup_verified=False)
    return ledger


def test_reconcile_settles_an_unknown_model_call_and_the_readback_shows_it(host):
    """The integration gap: nothing called LP-PROD-A's settlement, so the
    miner's Reconcile left such a campaign RECONCILIATION_REQUIRED for good
    (`_cleanup` reconciles worker operations only)."""
    identity, root = launched(host)
    ledger = timed_out(root)
    view = host.get(identity)
    assert view["state"] == "RECONCILIATION_REQUIRED"
    assert view["recovery"][0] == RECONCILE
    assert view["unknown_outcome_calls"]["awaiting_settlement"] == [
        {"identity": "model-1", "booked_on_settlement_nanodollars": RESERVATION_NANO}
    ]
    assert reconciliation(view)["awaiting_settlement"][0]["identity"] == "model-1"
    view = host.control(identity, "reconcile")
    # Settled, nothing outstanding: the miner's campaign is theirs again.
    assert view["state"] == "READY"
    assert view["recovery"] == []
    assert uncertain_calls(ledger, owner=OWNER) == []
    settled = {
        "identity": "model-1",
        "reason": "transport_outcome_unknown",
        "booked_nanodollars": RESERVATION_NANO,
        "caveat": None,
    }
    assert view["unknown_outcome_calls"] == {
        "settled": [settled],
        "awaiting_settlement": [],
        "accounting": SETTLEMENT_ACCOUNTING,
    }
    # Booked at the full reservation, as an uncertain charge - never as one
    # the provider reported - journalled beside the call, and nothing resent.
    assert view["usage"]["uncertain"]["provider_nanodollars"] == RESERVATION_NANO
    assert view["usage"]["reported"]["provider_nanodollars"] == 0
    folder = ra._call_directory(ledger, OWNER, "model-1")
    settlement = json.loads((folder / "settlement.json").read_bytes())
    assert settlement["retry_dispatched"] is False
    assert settlement["booked"]["provider_nanodollars"] == RESERVATION_NANO
    # The campaign view carries the same, in its closed shape.
    assert reconciliation(view) == {
        "settled": [settled],
        "booked_nanodollars": RESERVATION_NANO,
        "awaiting_settlement": [],
        "accounting": SETTLEMENT_ACCOUNTING,
    }
    # Reconciling again books nothing more.
    again = host.control(identity, "reconcile")
    assert again["unknown_outcome_calls"]["settled"] == [settled]
    used = ledger.status(owner=OWNER)["used"]
    assert used["provider_attempts"] == 1
    assert used["provider_nanodollars"] == RESERVATION_NANO
    # The next call of that turn goes out under a fresh identity.
    ledger.generation = CampaignControl(ledger).acquire()
    calls = []
    reply = request_model(
        ledger,
        owner=OWNER,
        identity="model-1",
        request=request(),
        credential_file=None,
        transport=lambda value: calls.append(value) or completed(),
        sleep=pytest.fail,
    )
    assert reply == completed() and len(calls) == 1
    states = {op["id"]: op["state"] for op in ledger.status(owner=OWNER)["operations"]}
    assert states == {"model-1": "FAILED_INFRA", "model-1-rl1": "SUCCEEDED"}


def test_a_refused_settlement_answers_its_code_and_next_step(host):
    """A call Carbon will not settle stays unresolved; the reconcile answers
    the settlement's closed code with its own next step, at the HTTP door's
    body too, and the campaign still awaits reconciliation."""
    identity, root = launched(host)
    ledger = timed_out(root)
    retained = ra._call_directory(ledger, OWNER, "model-1") / "request.json"
    retained.chmod(0o600)
    retained.write_bytes(b"{}")
    with pytest.raises(Rejected) as refused:
        host.control(identity, "reconcile")
    assert (refused.value.code, refused.value.status) == ("request_changed", 409)
    step = SETTLEMENT_REFUSALS["request_changed"]
    assert refused.value.next_step == step
    assert error_body(refused.value.code, refused.value) == {
        "error": "request_changed",
        "next_step": step,
    }
    view = host.get(identity)
    assert view["state"] == "RECONCILIATION_REQUIRED"
    assert view["recovery"][0] == RECONCILE
    assert view["unknown_outcome_calls"]["settled"] == []
    assert [
        c["identity"] for c in view["unknown_outcome_calls"]["awaiting_settlement"]
    ] == ["model-1"]
    (row,) = uncertain_calls(ledger, owner=OWNER)
    assert row["refusal"] == "request_changed"


def test_a_call_in_flight_or_a_held_campaign_is_never_settled(host):
    """LP-PROD-A's own fences, through the reconcile action: a call holding
    the provider-call lease is refused `call_in_flight`; a campaign whose
    owner lock is held is `campaign_busy`, before anything is settled."""
    identity, root = launched(host)
    ledger = timed_out(root)
    # A model call of this campaign, still in flight, holds the lease.
    with ra._provider_lease(ledger), pytest.raises(Rejected) as refused:
        host.control(identity, "reconcile")
    assert refused.value.code == "call_in_flight"
    assert refused.value.next_step == SETTLEMENT_REFUSALS["call_in_flight"]
    with owner_lock(root), pytest.raises(Rejected, match="campaign_busy"):
        host.control(identity, "reconcile")
    assert [c["identity"] for c in uncertain_calls(ledger, owner=OWNER)] == ["model-1"]
    assert host.get(identity)["state"] == "RECONCILIATION_REQUIRED"
    # Once the call has ended and the holder has gone, it settles.
    assert host.control(identity, "reconcile")["state"] == "READY"


def test_a_refused_settlement_reads_the_same_at_both_doors(host):
    """Review repair: over MCP, `carbon_halt action=reconcile` answered A's
    settlement refusals with the catalog's fallback ("Read the code ..."),
    because the MCP door read only the catalog, which did not name them, while
    the HTTP door sent A's own step. Both now send A's step; and the catalog,
    which a `last_refusal` reads, names each settlement code with A's step as
    a sentence."""
    from mcp.server.mcpserver.exceptions import ToolError

    from carbon.miner_mcp.mcp_operations import PREFIX, make_operation_tools
    from scripts.dev.miner_launchpad import supervisor as supervision

    identity, root = launched(host)
    ledger = timed_out(root)
    halt = {t.name: t for t in make_operation_tools(host)}[PREFIX + "halt"]
    with ra._provider_lease(ledger):
        with pytest.raises(Rejected) as browser:
            host.control(identity, "reconcile")
        with pytest.raises(ToolError) as agent:
            asyncio.run(halt.fn(campaign=identity, action="reconcile"))
    body = error_body(browser.value.code, browser.value)
    assert body == {
        "error": "call_in_flight",
        "next_step": SETTLEMENT_REFUSALS["call_in_flight"],
    }
    assert json.loads(str(agent.value)) == body
    # Nothing was settled through either door.
    assert [c["identity"] for c in uncertain_calls(ledger, owner=OWNER)] == ["model-1"]
    for code, said in SETTLEMENT_REFUSALS.items():
        assert NEXT_ACTIONS[code] == said[0].upper() + said[1:] + ".", code
        assert supervision.refusal(code)["next_action"] == NEXT_ACTIONS[code]
        assert supervision.refusal(code)["next_action"] != supervision.FALLBACK_ACTION


def test_pause_never_settles_a_model_call(host):
    """Settlement is never automatic: only Reconcile books one. A pause asked
    meanwhile is kept, and the reconciled campaign settles PAUSED."""
    identity, root = launched(host)
    ledger = timed_out(root)
    assert host.control(identity, "pause")["state"] == "RECONCILIATION_REQUIRED"
    assert [c["identity"] for c in uncertain_calls(ledger, owner=OWNER)] == ["model-1"]
    assert host.control(identity, "reconcile")["state"] == "PAUSED"
    assert uncertain_calls(ledger, owner=OWNER) == []


def development_campaign(root, campaign=None):
    """The development CLI's own campaign (no control), with a model call
    whose outcome is unknown and the manifest file the CLI reads."""
    from test_cw1_research_ledger import ledger as development

    meter = campaign or development(root)
    with meter.db() as db:
        (manifest,) = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    (meter.root / "campaign-manifest.json").write_bytes(manifest)
    owner = json.loads(manifest)["owner"]
    with pytest.raises(ProviderCallFailed):
        request_model(
            meter,
            owner=owner,
            identity="model-1",
            request=request(),
            credential_file=None,
            transport=timeout,
            sleep=pytest.fail,
        )
    return meter, owner


def reconcile_cli(monkeypatch, capsys, root):
    monkeypatch.setattr(
        sys, "argv", ["research_campaign", "reconcile", "--root", str(root)]
    )
    try:
        research_campaign.main()
        code = 0
    except SystemExit as exit_:
        code = exit_.code
    return code, json.loads(capsys.readouterr().out)


def test_the_development_cli_reconciles_its_own_campaign(tmp_path, monkeypatch, capsys):
    meter, owner = development_campaign(tmp_path / "campaign")
    code, report = reconcile_cli(monkeypatch, capsys, meter.root)
    assert code == 0
    assert report["schema"] == research_campaign.MODEL_CALL_RECONCILIATION
    assert [c["identity"] for c in report["settled"]] == ["model-1"]
    assert report["booked_nanodollars"] == RESERVATION_NANO
    assert report["refused"] == []
    assert report["accounting"] == SETTLEMENT_ACCOUNTING
    assert uncertain_calls(meter, owner=owner) == []
    # Settled once: a second reconcile settles nothing more.
    code, report = reconcile_cli(monkeypatch, capsys, meter.root)
    assert (code, report["settled"], report["booked_nanodollars"]) == (0, [], 0)


def test_the_development_cli_answers_a_refused_settlement(
    tmp_path, monkeypatch, capsys
):
    meter, owner = development_campaign(tmp_path / "campaign")
    retained = ra._call_directory(meter, owner, "model-1") / "request.json"
    retained.chmod(0o600)
    retained.write_bytes(b"{}")
    code, report = reconcile_cli(monkeypatch, capsys, meter.root)
    assert code == 1
    assert report["settled"] == []
    assert report["refused"] == [
        {
            "identity": "model-1",
            "code": "request_changed",
            "next_step": SETTLEMENT_REFUSALS["request_changed"],
        }
    ]


def test_the_development_cli_never_reconciles_a_controlled_campaign(
    tmp_path, monkeypatch, capsys
):
    """A product (or granted) campaign is reconciled only by its own
    reconcile action, under its owner lock and control generation, which the
    CLI does not hold."""
    from test_product_campaign_ledger import product

    meter, owner = development_campaign(None, product(tmp_path))
    code, report = reconcile_cli(monkeypatch, capsys, meter.root)
    assert code == 1
    assert report == {
        "error": "control_fenced",
        "next_step": SETTLEMENT_REFUSALS["control_fenced"],
    }
    assert [c["identity"] for c in uncertain_calls(meter, owner=owner)] == ["model-1"]


# --- 2. a profile that no longer describes the install is never attached -------


@pytest.fixture
def head(monkeypatch):
    """The checkout's revision, as setup reads it."""
    current = {"revision": REVISION}
    monkeypatch.setattr(
        environment, "checkout_revision", lambda repo=None: current["revision"]
    )
    return current


def installed(tmp_path, *, worker_path=None):
    """A miner's setup as the installer left it: its images, a compute check
    of them, the profile Review wrote, and the installer's record."""
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    worker, analysis, operator = (
        home / "worker.json",
        home / "analysis.json",
        home / "operator.json",
    )
    worker.write_text(json.dumps({"image_id": RUNTIME["images"][0]}))
    analysis.write_text(json.dumps({"image_id": RUNTIME["images"][1]}))
    operator.write_text("{}")
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    setup.begin({"address": HOTKEY})
    setup.inference(
        {
            "provider_id": "engy-chat",
            "model_id": "deepseek-v4-flash-0731",
            "key": KEY,
            "consent": CONSENT,
        }
    )
    setup.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": str(worker),
            "analysis_image_manifest": str(analysis),
        }
    )
    setup.agent({"choice": AUTONOMOUS, "operator_config": str(operator)})
    setup.review({"confirm": True})
    record(setup, REVISION, worker=worker_path or worker, analysis=analysis)
    return setup, worker


def record(setup, revision, *, worker, analysis):
    """The installer's record of what it installed (`after_install`)."""
    write_private(
        setup.installation_path,
        canonical(
            {
                "schema": INSTALLATION_SCHEMA,
                "revision": revision,
                "images": {
                    "image_manifest": {"path": str(worker)},
                    "analysis_image_manifest": {"path": str(analysis)},
                },
            }
        ),
    )


def profile_of(setup):
    return validated_profile(json.loads(setup.profile_path.read_bytes()))


def test_a_profile_that_describes_the_install_is_attached(tmp_path, head):
    setup, _ = installed(tmp_path)
    cfg = profile_of(setup)
    assert profile_staleness(setup.profile_path, cfg) == ([], None)
    assert install_refusal(setup.profile_path, cfg) is None
    RunnerAdapter.for_profile(setup.profile_path).close()


def test_an_install_the_profile_was_not_written_for_is_refused_by_name(tmp_path, head):
    """The installer moved Carbon on and rebuilt the worker image in place,
    but the profile written before stayed where the controller looks: a
    compute check and Review clear it, as this checkout is the installed
    one."""
    setup, worker = installed(tmp_path)
    head["revision"] = NEW
    worker.write_text(json.dumps({"image_id": "sha256:" + "9" * 64}))
    analysis = Path(profile_of(setup)["paths"]["analysis_image_manifest"])
    record(setup, NEW, worker=worker, analysis=analysis)
    reasons, step = profile_staleness(setup.profile_path, profile_of(setup))
    assert reasons == [
        "Carbon was installed at "
        + NEW[:12]
        + " and this profile accepts "
        + REVISION[:12],
        "the worker image was rebuilt since this profile was written",
    ]
    assert step == PROFILE_RECHECK_STEP
    with pytest.raises(Rejected) as refused:
        RunnerAdapter.for_profile(setup.profile_path)
    assert (refused.value.code, refused.value.status) == (CARBON_UPDATED, 409)
    assert refused.value.next_step == step + ": " + "; ".join(reasons)
    assert error_body(refused.value.code, refused.value)["next_step"] == (
        refused.value.next_step
    )


def test_a_checkout_moved_since_the_install_names_the_installer(tmp_path, head):
    """A `git pull` after the install: only the installer clears it."""
    setup, _ = installed(tmp_path)
    head["revision"] = NEW
    reasons, step = profile_staleness(setup.profile_path, profile_of(setup))
    assert reasons == [
        "this checkout is at "
        + NEW[:12]
        + ", not the "
        + REVISION[:12]
        + " Carbon was installed at"
    ]
    assert step == REINSTALL_STEP
    # An unusable record is the installer's to replace, too.
    setup.installation_path.write_text("not json")
    assert profile_staleness(setup.profile_path, profile_of(setup)) == (
        ["the installer's record here is unreadable"],
        REINSTALL_STEP,
    )


def test_images_the_installer_did_not_build_are_named(tmp_path, head):
    elsewhere = tmp_path / "installed-worker.json"
    elsewhere.write_text(json.dumps({"image_id": RUNTIME["images"][0]}))
    setup, _ = installed(tmp_path, worker_path=elsewhere)
    reasons, step = profile_staleness(setup.profile_path, profile_of(setup))
    assert reasons == [
        "this profile names another worker image than the one the installer built"
    ]
    assert step == PROFILE_RECHECK_STEP
    # A manifest the profile names that is gone.
    Path(profile_of(setup)["paths"]["analysis_image_manifest"]).unlink()
    reasons, _ = profile_staleness(setup.profile_path, profile_of(setup))
    assert reasons[-1] == "the analysis image is gone since this profile was written"


def test_only_a_profile_beside_the_installers_record_is_judged(tmp_path, head):
    """A developer checkout the installer never ran in, and an operator's own
    profile kept elsewhere, are held to what execution checks, as before."""
    setup, _ = installed(tmp_path)
    head["revision"] = NEW
    cfg = profile_of(setup)
    elsewhere = tmp_path / "operator" / "runner-profile.json"
    elsewhere.parent.mkdir(mode=0o700)
    assert profile_staleness(elsewhere, cfg) == ([], None)
    setup.installation_path.unlink()
    assert profile_staleness(setup.profile_path, cfg) == ([], None)


def test_the_control_center_never_attaches_a_stale_profile(tmp_path, head):
    """Not on start (`attach_runner`, which `main` uses) and not from setup,
    whose page loads a written profile on every read: the page reads why
    instead, as the preflight it renders for an updated checkout. A current
    profile is attached as before."""
    setup, _ = installed(tmp_path)
    head["revision"] = NEW
    runner, refused = controller.attach_runner(setup.profile_path)
    assert runner is None
    reasons, step = profile_staleness(setup.profile_path, profile_of(setup))
    assert refused == {
        "available": False,
        "profile": None,
        "status": "CARBON_UPDATED",
        "code": CARBON_UPDATED,
        "reason": NEXT_ACTIONS[CARBON_UPDATED],
        "next_step": step + ": " + "; ".join(reasons),
    }
    server = controller.Server(
        controller.Controller(tmp_path / "http.sqlite3"),
        TOKEN,
        0,
        onboarding=Onboarding(),
        state_dir=tmp_path / "state",
        setup_checks=Checks(),
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        status, _ = get(server, "/api/v1/setup")
        assert status == 200
        assert server.research_runner is None
        status, body = get(server, "/api/v1/research")
        assert status == 200
        assert body == {"preflight": refused, "runs": []}
        # The checkout is back at the installed revision: attached.
        head["revision"] = REVISION
        get(server, "/api/v1/setup")
        assert server.research_runner is not None
        assert server.profile_refusal is None
    finally:
        server.shutdown()
        server.server_close()
        if server.research_runner is not None:
            server.research_runner.close()


def test_a_restarted_control_center_names_the_profile_it_did_not_attach(
    tmp_path, head, monkeypatch, capsys
):
    installed(tmp_path)
    head["revision"] = NEW

    def interrupted(self, poll_interval=0.5):
        raise KeyboardInterrupt

    monkeypatch.setattr(controller.Server, "serve_forever", interrupted)
    monkeypatch.setattr(
        sys,
        "argv",
        ["controller", "--state-dir", str(tmp_path / "state"), "--port", str(port())],
    )
    controller.main()
    out = capsys.readouterr().out
    assert "Carbon DEVELOPMENT Control Center:" in out
    assert (
        "Runner profile not attached: carbon_updated_rerun_installer. Next: "
        + REINSTALL_STEP
        + ": this checkout is at "
        + NEW[:12]
    ) in out


def test_carbon_mcp_never_attaches_a_stale_profile(tmp_path, head, capsys):
    """`carbon-mcp --configuration` constructs its host through
    `RunnerAdapter.for_profile`, so it refuses the same profile by name and
    serves nothing over it. It names the step that clears it, and why - the
    step the Control Center prints and its HTTP door sends - not the
    catalog's general one (review repair: it said "re-run the installer"
    where a compute check and Review clear it)."""
    from carbon.miner_mcp import standard_cli

    setup, _ = installed(tmp_path)
    head["revision"] = NEW
    served = standard_cli.main(
        [
            "--configuration",
            str(setup.profile_path),
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )
    assert served == 2
    reasons, step = profile_staleness(setup.profile_path, profile_of(setup))
    assert step == REINSTALL_STEP
    assert capsys.readouterr().err == (
        "Carbon MCP unavailable: carbon_updated_rerun_installer. Next: "
        + step
        + ": "
        + "; ".join(reasons)
        + ".\n"
    )
    # The same step the HTTP door sends for the same profile.
    _, refused = controller.attach_runner(setup.profile_path)
    assert refused["next_step"] == step + ": " + "; ".join(reasons)
    # A refusal that carries no step of its own keeps the catalog's.
    assert standard_cli.unavailable_message(Rejected(CARBON_UPDATED)) == (
        "Carbon MCP unavailable: carbon_updated_rerun_installer. "
        + NEXT_ACTIONS[CARBON_UPDATED]
    )


def port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def get(server, path):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    try:
        connection.request(
            "GET",
            path,
            headers={"Host": server.authority, "Authorization": "Bearer " + TOKEN},
        )
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()
