"""Runner bridge fixtures test control/disclosure only; never adaptive evidence.

Registration is the only admission gate (C-MLP-02-D11): these campaigns are
admitted by a real `RegisteredMiner`, built from a real metagraph snapshot, and
no grant appears anywhere on the path. Campaigns launched under the retired
development grant are covered at the end - readable, stoppable and cleanable,
never resumable.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest
from test_miner_launchpad_admission import managed, reserve

from carbon.chain.models import MetagraphSnapshot, Participant
from carbon.development_session.chain_onboarding import (
    OnboardingFailure,
    PublicAddress,
    RegisteredMiner,
    carbon_testnet_context,
)
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import PRODUCT, CampaignLedger
from scripts.dev.miner_launchpad.controller import Controller, Rejected, Server
from scripts.dev.miner_launchpad.runner import RunnerAdapter

HOTKEY = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
KEY = "request-key-000001"
REVISION = "a" * 40
RUNTIME = {
    "implementation": {
        "revision": REVISION,
        "tree": "b" * 40,
        "source_tree_digest": "sha256:" + "c" * 64,
    },
    "images": ["sha256:" + "d" * 64],
}


def registered():
    return RegisteredMiner(
        MetagraphSnapshot(
            context=carbon_testnet_context(),
            finalized_block=100,
            block_hash="0x" + "cd" * 32,
            timestamp_ms=1,
            participants=(
                Participant(
                    uid=0, hotkey=HOTKEY, coldkey="5" + "C" * 47, registered_at=1
                ),
            ),
        ),
        PublicAddress(HOTKEY),
    )


def run_id(key=KEY, principal="alice"):
    return digest(canonical([principal, key]))[7:39]


def product_campaign(root, identity):
    """A product campaign ledger at the root a launch under `identity` uses."""
    value = CampaignLedger(root, clock=lambda: 1000)
    control = CampaignControl(value)
    value.generation = control.acquire()
    manifest = {
        "schema": PRODUCT,
        "authority": "C-MLP-02-D11",
        "campaign_id": "cmp-" + identity,
        "principal": "alice",
        "owner": "miner-requester",
        "runtime": RUNTIME,
        "admission": registered().record(),
        "implementation": RUNTIME["implementation"],
        "images": RUNTIME["images"],
        "objective": "fixture",
        "sampling": "fixture",
        "control": "fixture",
        "selection": "fixture",
        "replica_policy": "three",
        "provider": {"model": "fixture-model"},
    }
    value.freeze(manifest)
    return value, control, manifest


class Chain:
    """Counts admission reads, so a test can say when the chain was consulted."""

    def __init__(self, answer=None, failure=None):
        self.reads, self.answer, self.failure = 0, answer, failure

    def __call__(self, cfg):
        self.reads += 1
        if self.failure is not None:
            raise OnboardingFailure(self.failure, next_action="fixture")
        return self.answer or registered()


def configured(tmp_path):
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir(mode=0o700, exist_ok=True)
    return {
        "profile_id": "opaque-profile",
        "principal": "alice",
        "campaigns_root": str(campaigns),
        "runtime": RUNTIME,
        "accepted_revision": REVISION,
    }


def adapter(tmp_path, monkeypatch, *, chain=None):
    tmp_path.chmod(0o700)
    cfg = configured(tmp_path)
    value, control, _ = product_campaign(
        Path(cfg["campaigns_root"]) / run_id(), run_id()
    )
    chain = chain or Chain()
    bridge = RunnerAdapter(
        tmp_path / "browser.sqlite3", principal="alice", registration=chain
    )
    monkeypatch.setattr(bridge, "configured", lambda: cfg)
    monkeypatch.setattr(bridge, "_start", lambda *args: None)
    return bridge, value, control


def test_disabled_profile_has_no_fallback_or_side_effect(tmp_path):
    bridge = RunnerAdapter(tmp_path / "browser.sqlite3")
    assert bridge.preflight()["available"] is False
    with pytest.raises(Rejected, match="profile_unavailable"):
        bridge.launch({"profile": "anything"}, "request-key-000001")
    assert bridge.recent() == []


def test_opaque_launch_replays_and_another_key_is_another_campaign(
    tmp_path, monkeypatch
):
    """A miner may run more than one campaign; a lost response is still one.

    Under the grant, every key collapsed onto the grant's single campaign - a
    founder's spend cap. Registration admits the miner, not one campaign.
    """
    bridge, _, _ = adapter(tmp_path, monkeypatch)
    first = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")
    assert (
        bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
        == first["id"]
    )
    second = bridge.launch({"profile": "opaque-profile"}, "request-key-000002")
    assert second["id"] != first["id"] == run_id()
    assert len(bridge.recent()) == 2
    with pytest.raises(Rejected, match="replay_conflict"):
        bridge.launch(
            {"profile": "opaque-profile", "budget": {"elapsed_seconds": 60}},
            "request-key-000001",
        )
    for body in (
        {"profile": "wrong"},
        {"profile": "opaque-profile", "command": "arbitrary"},
        {"root": "/private"},
    ):
        with pytest.raises(Rejected):
            bridge.launch(body, "request-key-000003")


def test_projection_withholds_private_operations_and_retains_attempt_failure(
    tmp_path, monkeypatch
):
    bridge, value, _ = adapter(tmp_path, monkeypatch)
    first = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")
    reserve(value)
    value.finish(
        "op",
        owner="miner-requester",
        state="FAILED_INFRA",
        actual={"research_trials": 1},
        result={
            "provider_error": "SECRET-SENTINEL",
            "private_seed": "PROTECTED-SENTINEL",
        },
    )
    value.note(
        owner="miner-requester",
        kind="operational_error",
        body={"raw": "SECRET-SENTINEL"},
    )
    value.note(
        owner="miner-requester",
        kind="hypothesis",
        body={
            "hypothesis": "try a smaller legal model",
            "private_path": "SECRET-SENTINEL",
        },
    )
    result = bridge.get(first["id"])
    raw = json.dumps(result)
    assert "SECRET-SENTINEL" not in raw and "PROTECTED-SENTINEL" not in raw
    assert str(tmp_path) not in raw
    assert result["attempted_experiments"] == 1
    assert result["completed_experiments"] == 0
    assert result["operations"][0]["state"] == "FAILED_INFRA"
    assert result["final_results"] == []


def test_completed_epoch_can_stop_without_candidate_or_improvement(
    tmp_path, monkeypatch
):
    bridge, value, control = adapter(tmp_path, monkeypatch)
    identity = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
    for hypothesis in ("first hypothesis", "revised hypothesis"):
        value.note(
            owner="miner-requester", kind="hypothesis", body={"hypothesis": hypothesis}
        )
    directory = value.root / "epoch-1"
    directory.mkdir()
    path = directory / "outcome.json"
    path.write_bytes(
        canonical(
            {
                "schema": "carbon.autoresearch.epoch-outcome.v1",
                "epoch": 1,
                "status": "STOPPED",
                "reason": "agent reported no_feasible_action",
                "stop_evidence": "No admissible experiment fits the remaining grant",
                "used_feedback": True,
                "agent_output": "PRIVATE-TRANSCRIPT-SENTINEL",
                "accounting": {"private_root": "PRIVATE-PATH-SENTINEL"},
            }
        )
    )
    control.settled(value.generation, completed=True, cleanup_verified=True)
    result = bridge.get(identity)
    assert result["state"] == "COMPLETED"
    assert len(result["hypotheses"]) == 2
    assert result["current_hypothesis"]["hypothesis"] == "revised hypothesis"
    assert result["epoch_outcomes"][0]["status"] == "STOPPED"
    assert result["epoch_outcomes"][0]["used_feedback"] is True
    assert result["epoch_outcomes"][0]["final_evidence"] is False
    assert result["candidate_freezes"] == result["final_results"] == []
    assert "SENTINEL" not in json.dumps(result)
    path.write_bytes(canonical({"status": "IMPROVED", "epoch": 2}))
    assert bridge.get(identity)["epoch_outcomes"] == [
        {"epoch": 1, "status": "READBACK_UNAVAILABLE", "final_evidence": False}
    ]


def test_adapter_dispatches_the_product_launch_with_no_grant(tmp_path, monkeypatch):
    from carbon.development_session import research_campaign
    from carbon.development_session.research_agent_policy import AUTONOMOUS
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS

    bridge, value, _ = adapter(tmp_path, monkeypatch)
    identity = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
    observed = {}

    async def entry(args, *, ledger):
        observed.update(
            policy=args.agent_policy, product=args.product, grant=ledger.admission
        )

    monkeypatch.setattr(research_campaign, "execute", entry)
    monkeypatch.setattr(bridge, "_cleanup", lambda ledger: True)
    cfg = {
        **configured(tmp_path),
        "paths": {key: str(tmp_path / key) for key in PATH_FIELDS},
    }
    product = object()
    bridge._run(identity, cfg, value.root, product)
    assert observed == {"policy": AUTONOMOUS, "product": product, "grant": None}
    result = bridge.get(identity)
    assert result["state"] == "INTERRUPTED"
    assert result["final_results"] == []


def test_stop_and_retained_readback_need_no_chain_read(tmp_path, monkeypatch):
    chain = Chain()
    bridge, _value, control = adapter(tmp_path, monkeypatch, chain=chain)
    identity = bridge.launch({"profile": "opaque-profile"}, KEY)["id"]
    chain.failure = "CHAIN_UNAVAILABLE"
    assert bridge.control(identity, "stop")["state"] == "STOPPING"
    assert control.status()["desired"] == "STOP"
    assert bridge.get(identity)["id"] == identity


def test_changed_final_source_withheld_not_replaced_by_saved_feedback(
    tmp_path, monkeypatch
):
    bridge, value, _ = adapter(tmp_path, monkeypatch)
    identity = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
    directory = value.root / "epoch-1/final"
    directory.mkdir(parents=True)
    (directory / "comparison-ref.json").write_bytes(
        canonical(
            {
                "root": "/unauthorized-private-directory",
                "registration_digest": "fake",
                "report_digest": "fake",
            }
        )
    )
    result = bridge.get(identity)
    assert result["final_results"] == [
        {
            "epoch": 1,
            "mode": "DEVELOPMENT_EVALUATION",
            "status": "READBACK_UNAVAILABLE",
            "result": None,
        }
    ]


def test_restart_fences_stale_state_without_replaying_dispatch(tmp_path, monkeypatch):
    bridge, value, control = adapter(tmp_path, monkeypatch)
    identity = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
    reserve(value)
    recovered = RunnerAdapter(bridge.database, principal="alice")
    assert recovered.get(identity)["state"] == "RECONCILIATION_REQUIRED"
    assert control.status()["generation"] > value.generation
    assert recovered.get(identity)["usage"]["reserved"]["research_trials"] == 1


def test_research_http_authentication_and_closed_requests(tmp_path):
    store = Controller(tmp_path / "browser.sqlite3")
    runner = RunnerAdapter(store.database)
    token = "nonspending-engineering-session-token"
    server = Server(store, token, 0, research_runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, path, authenticated=True):
        client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {
            "Host": server.origin.removeprefix("http://"),
            "Content-Type": "application/json",
            "Idempotency-Key": "fixture-request-001",
        }
        if authenticated:
            headers["Authorization"] = "Bearer " + token
        client.request(
            method,
            path,
            body='{"profile":"fixture"}' if method == "POST" else None,
            headers=headers,
        )
        response = client.getresponse()
        result = response.status, json.loads(response.read())
        client.close()
        return result

    try:
        assert request("GET", "/api/v1/research", False)[0] == 401
        assert request("POST", "/api/v1/research", False)[0] == 401
        assert request("GET", "/api/v1/research")[1]["preflight"]["available"] is False
        assert request("POST", "/api/v1/research")[0] == 409
        assert request("GET", "/api/v1/research/../../private")[0] == 404
        assert runner.recent() == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_another_configured_principal_cannot_read_control_or_recover_campaign(
    tmp_path, monkeypatch
):
    bridge, _, control = adapter(tmp_path, monkeypatch)
    identity = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
    before = control.status()
    other = RunnerAdapter(bridge.database, principal="bob")
    assert other.recent() == []
    with pytest.raises(Rejected, match="unavailable"):
        other.get(identity)
    with pytest.raises(Rejected, match="unavailable"):
        other.control(identity, "stop")
    assert control.status() == before


# --- registration is the gate, and it is read before anything durable -------


@pytest.mark.parametrize(
    "failure,code",
    (
        ("NOT_REGISTERED", "registration_required"),
        ("CHAIN_UNAVAILABLE", "registration_unreadable"),
        ("WRONG_NETWORK", "registration_wrong_network"),
    ),
)
def test_an_unadmitted_launch_writes_nothing(tmp_path, monkeypatch, failure, code):
    """No row, no campaign directory, no thread - and the specimen shows the
    same launch writes all three once registration reads true."""
    chain = Chain(failure=failure)
    bridge, _, _ = adapter(tmp_path, monkeypatch, chain=chain)
    started = []
    monkeypatch.setattr(bridge, "_start", lambda *args: started.append(args))
    fresh = "request-key-unadmitted"
    with pytest.raises(Rejected, match=code):
        bridge.launch({"profile": "opaque-profile"}, fresh)
    campaigns = Path(configured(tmp_path)["campaigns_root"])
    assert bridge.recent() == [] and started == []
    assert not (campaigns / run_id(fresh)).exists()

    chain.failure = None
    admitted = bridge.launch({"profile": "opaque-profile"}, fresh)
    assert admitted["id"] == run_id(fresh)
    assert len(bridge.recent()) == 1 and len(started) == 1


def test_the_launch_carries_the_registration_and_no_grant(tmp_path, monkeypatch):
    bridge, _, _ = adapter(tmp_path, monkeypatch)
    started = []
    monkeypatch.setattr(bridge, "_start", lambda *args: started.append(args))
    bridge.launch({"profile": "opaque-profile"}, KEY)
    _identity, _cfg, root, product = started[0]
    assert root == Path(configured(tmp_path)["campaigns_root"]) / run_id()
    assert product.miner.hotkey == HOTKEY
    assert product.budget == {}
    fields = product.manifest_fields()
    assert fields["schema"] == PRODUCT
    assert fields["admission"]["admission"] == "SUBNET_REGISTRATION"
    assert "grant" not in fields and "ceilings" not in fields
    with bridge.db() as db:
        row = db.execute("SELECT * FROM launchpad_campaigns").fetchone()
    assert json.loads(row["admission"])["hotkey"] == HOTKEY
    assert json.loads(row["budget"]) == {}


def test_a_replayed_launch_reads_no_chain(tmp_path, monkeypatch):
    """Admitted when it was recorded; a lost response is not a second admission."""
    chain = Chain()
    bridge, _, _ = adapter(tmp_path, monkeypatch, chain=chain)
    bridge.launch({"profile": "opaque-profile"}, KEY)
    assert chain.reads == 1
    chain.failure = "CHAIN_UNAVAILABLE"
    assert bridge.launch({"profile": "opaque-profile"}, KEY)["id"] == run_id()
    assert chain.reads == 1


def test_the_budget_is_the_miners_exactly_or_none(tmp_path, monkeypatch):
    bridge, _, _ = adapter(tmp_path, monkeypatch)
    started = []
    monkeypatch.setattr(bridge, "_start", lambda *args: started.append(args))
    chosen = {"ceilings": {"research_trials": 3}, "elapsed_seconds": 900}
    bridge.launch(
        {"profile": "opaque-profile", "budget": chosen}, "request-key-budgeted"
    )
    assert started[0][3].budget == chosen
    assert started[0][3].manifest_fields()["ceilings"] == {"research_trials": 3}
    for incoherent in (
        {"ceilings": {"research_trials": -1}},
        {"ceilings": {"not_a_dimension": 1}},
        {"spend_cap_set_by_carbon": 1},
        [],
    ):
        with pytest.raises(Rejected, match="invalid_budget"):
            bridge.launch(
                {"profile": "opaque-profile", "budget": incoherent},
                "request-key-incoherent",
            )


# --- campaigns launched under the retired development grant -----------------


def retired(tmp_path, bridge):
    """A campaign launched under a grant before C-MLP-02-D11, as recorded then."""
    legacy = tmp_path / "legacy"
    legacy.mkdir(mode=0o700)
    value, control, manifest = managed(legacy)
    # The shape a real launch recorded; the shared grant fixture leaves these
    # as bare strings.
    manifest.update(
        provider={"model": "fixture-model"},
        implementation={"revision": "fixture-revision"},
        images=["fixture-image"],
    )
    with value.db() as db:
        db.execute("UPDATE campaign SET manifest=? WHERE id=1", (canonical(manifest),))
    with bridge.db() as db:
        db.execute(
            "INSERT INTO research_runs (id,request_key,profile,principal,config_digest,grant_digest,campaign,state,created,root,grant_record,grant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "retired-grant-campaign",
                "retired-request-key",
                "opaque-profile",
                "alice",
                "retired-config",
                value.admission.pin,
                manifest["campaign_id"],
                "INTERRUPTED",
                1.0,
                str(value.root),
                canonical(
                    {
                        "path": str(value.admission.path),
                        "document": value.admission.document,
                    }
                ),
                "fixture-grant",
            ),
        )
    return value, control


def test_a_retired_grant_campaign_stays_readable_and_stoppable(tmp_path, monkeypatch):
    bridge, _, _ = adapter(tmp_path, monkeypatch)
    _value, control = retired(tmp_path, bridge)
    assert bridge.get("retired-grant-campaign")["admission"] == (
        "RETIRED_DEVELOPMENT_GRANT"
    )
    assert "retired-grant-campaign" in {run["id"] for run in bridge.recent()}
    assert bridge.control("retired-grant-campaign", "stop")["state"] == "STOPPING"
    assert control.status()["desired"] == "STOP"


def test_a_retired_grant_campaign_is_never_resumed(tmp_path, monkeypatch):
    """Resuming would dispatch new work under a grant, which no product surface
    may do. The specimen: a product campaign resumes through the same call."""
    bridge, _, _ = adapter(tmp_path, monkeypatch)
    retired(tmp_path, bridge)
    with pytest.raises(Rejected, match="retired_grant_campaign"):
        bridge.control("retired-grant-campaign", "resume")
    identity = bridge.launch({"profile": "opaque-profile"}, KEY)["id"]
    with bridge.db() as db:
        db.execute(
            "UPDATE launchpad_campaigns SET config_digest=?",
            (digest(canonical(configured(tmp_path))),),
        )
    bridge.control(identity, "pause")
    assert bridge.control(identity, "resume")["id"] == identity


def test_a_retired_grant_is_held_only_for_cleanup(tmp_path, monkeypatch):
    """Structural, not a remembered check: the only grant a product surface can
    hold refuses every admission, while its ownership proof still holds."""
    from carbon.development_session.research_admission import RetainedGrant

    bridge, _, _ = adapter(tmp_path, monkeypatch)
    retired(tmp_path, bridge)
    row, kind, root = bridge._bound("retired-grant-campaign")
    ledger = bridge._ledger(row, kind, root)
    assert type(ledger.admission) is RetainedGrant
    ledger.generation = CampaignControl(ledger).status()["generation"]
    assert ledger.retained_owner("miner-requester")["owner"] == "miner-requester"
    with pytest.raises(ValueError, match="admits no new work"):
        reserve(ledger, "after-retirement")


# --- research images come from the miner's profile, not a grant --------------


def julia_profile(tmp_path, *, declare=True, name=True):
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS

    record = tmp_path / "authored-julia-image-record.json"
    record.write_bytes(canonical({"schema": "fixture-record", "image": "x"}))
    record.chmod(0o600)
    runtime = json.loads(json.dumps(RUNTIME))
    if declare:
        runtime["authored_research"] = [{"schema": "fixture-scope"}]
    cfg = {
        "schema": "carbon.launchpad.runner-profile.v2",
        "profile_id": "opaque-profile",
        "principal": "alice",
        "enabled": True,
        "accepted_revision": REVISION,
        "campaigns_root": str(tmp_path / "campaigns"),
        "runtime": runtime,
        "paths": {key: str(tmp_path / key) for key in PATH_FIELDS},
    }
    if name:
        cfg["authored_julia_image"] = str(record)
    return cfg, record


def test_a_declared_composition_needs_its_record(tmp_path):
    from scripts.dev.miner_launchpad.runner import validated_profile

    cfg, _ = julia_profile(tmp_path, declare=True, name=False)
    with pytest.raises(ValueError, match="authored_julia_image"):
        validated_profile(cfg)


def test_julia_needs_no_declaration_at_all(tmp_path):
    """Anytime: a profile naming a built Julia image is valid with nothing
    declared in the runtime; every campaign can use it."""
    from scripts.dev.miner_launchpad.runner import validated_profile

    cfg, _ = julia_profile(tmp_path, declare=False, name=True)
    assert validated_profile(cfg) == cfg


def test_a_gpu_record_still_pairs_with_its_declaration(tmp_path):
    """GPU research binds its scope to the campaign's own material, so a GPU
    record with nothing declared is refused - the specimen that the pairing
    check still bites where it applies."""
    from scripts.dev.miner_launchpad.runner import validated_profile

    cfg, _ = julia_profile(tmp_path, declare=False, name=False)
    cfg["gpu_image"] = str(tmp_path / "gpu-record.json")
    with pytest.raises(ValueError, match="gpu_image"):
        validated_profile(cfg)


def test_julia_needs_no_grant_only_the_profile(tmp_path, monkeypatch):
    """The record is installed into the campaign root at launch, before the
    campaign runs - where an operator used to write it by hand per grant."""
    from carbon.development_session import research_campaign
    from scripts.dev.miner_launchpad.runner import validated_profile

    tmp_path.chmod(0o700)
    cfg, record = julia_profile(tmp_path)
    assert validated_profile(cfg) == cfg
    Path(cfg["campaigns_root"]).mkdir(mode=0o700)
    bridge = RunnerAdapter(
        tmp_path / "browser.sqlite3", principal="alice", registration=Chain()
    )
    monkeypatch.setattr(bridge, "configured", lambda: cfg)
    started = []
    monkeypatch.setattr(bridge, "_start", lambda *args: started.append(args))
    bridge.launch({"profile": "opaque-profile"}, KEY)
    identity, _cfg, root, product = started[0]
    seen = {}

    async def entry(args, *, ledger):
        seen["record"] = (root / "authored-julia-image.json").read_bytes()
        seen["grant"] = ledger.admission

    monkeypatch.setattr(research_campaign, "execute", entry)
    monkeypatch.setattr(bridge, "_cleanup", lambda ledger: True)
    bridge._run(identity, cfg, root, product)
    assert seen == {"record": record.read_bytes(), "grant": None}
    assert (root / "authored-julia-image.json").stat().st_mode & 0o777 == 0o600


def test_a_rebuilt_image_reaches_a_running_campaign(tmp_path):
    """Anytime: a newer record replaces the installed one on the next launch,
    resume or attach. Nothing trusts the record's history; each run records
    the image it actually used."""
    from scripts.dev.miner_launchpad.runner import install_research_images

    cfg, record = julia_profile(tmp_path)
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    install_research_images(cfg, root)
    install_research_images(cfg, root)  # Unchanged: nothing rewritten.
    rebuilt = canonical({"schema": "fixture-record", "image": "rebuilt"})
    record.write_bytes(rebuilt)
    install_research_images(cfg, root)
    installed = root / "authored-julia-image.json"
    assert installed.read_bytes() == rebuilt
    assert installed.stat().st_mode & 0o777 == 0o600
    assert not (root / "authored-julia-image.json.installing").exists()


@pytest.fixture(autouse=True)
def _launches_name_a_challenge(monkeypatch):
    """A launch must name its Challenge; these runner tests launch the
    DEVELOPMENT-FIXTURE reference Challenge (journey_fixture)."""
    from scripts.dev.miner_launchpad.journey_fixture import (
        launch_with_fixture_challenge,
    )

    launch_with_fixture_challenge(monkeypatch.setattr)
