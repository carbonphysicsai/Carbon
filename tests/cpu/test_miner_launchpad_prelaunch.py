"""Non-spending prelaunch diagnostics; no model, numerical or chain dispatch.

The review reports the admission a launch will perform - subnet registration,
read at launch (C-MLP-02-D11) - and never a grant, which no product surface has.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest
from test_miner_launchpad_runner import (
    KEY,
    REVISION,
    RUNTIME,
    Chain,
    adapter,
    product_campaign,
    run_id,
)

from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    SERVICE_LIMITS,
)
from scripts.dev.miner_launchpad.controller import Controller, Rejected, Server
from scripts.dev.miner_launchpad.runner import PATH_FIELDS, RunnerAdapter


def configured_bridge(tmp_path, monkeypatch, *, chain=None):
    tmp_path.chmod(0o700)
    cfg = {
        "schema": "carbon.launchpad.runner-profile.v2",
        "profile_id": "private-fixture",
        "principal": "alice",
        "enabled": False,
        "disabled_reason": "OWNER_EXPERIMENT_PAUSE",
        "accepted_revision": REVISION,
        "campaigns_root": str(tmp_path / "PRIVATE-SENTINEL-campaigns"),
        "runtime": json.loads(json.dumps(RUNTIME)),
        "paths": {
            key: str(tmp_path / ("PRIVATE-SENTINEL-" + key)) for key in PATH_FIELDS
        },
        "research_guidance": "Private fixture objective; retain measured feedback.",
    }
    path = tmp_path / "profile.json"
    path.write_bytes(canonical(cfg))
    path.chmod(0o600)
    bridge = RunnerAdapter(
        tmp_path / "browser.sqlite3",
        configuration=path,
        registration=chain or Chain(),
    )
    monkeypatch.setattr(
        bridge, "_start", lambda *args: pytest.fail("dispatch forbidden")
    )
    return bridge, cfg


def write(bridge, cfg):
    bridge.configuration.write_bytes(canonical(cfg))


def enable(bridge, cfg):
    cfg.pop("disabled_reason", None)
    cfg["enabled"] = True
    write(bridge, cfg)


def test_paused_review_discloses_contract_not_private_inputs(tmp_path, monkeypatch):
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    result = bridge.preflight()
    assert not result["available"] and result["status"] == "OWNER_EXPERIMENT_PAUSE"
    assert result["research_guidance"]["text"] == cfg["research_guidance"]
    review = result["review"]
    assert review["execution"]["device_visibility"] == "NOT_OBSERVED"
    assert review["execution"]["runtime_evidence"] == "NOT_ATTACHED"
    assert review["runtime"]["implementation"] == cfg["runtime"]["implementation"]
    # Specimen: the sentinel really is in the profile the review was built from.
    assert "PRIVATE-SENTINEL" in bridge.configuration.read_text()
    assert "PRIVATE-SENTINEL" not in json.dumps(result)
    for _ in range(2):
        with pytest.raises(Rejected, match="research_dispatch_disabled"):
            bridge.launch({"profile": cfg["profile_id"]}, "fixture-request-0001")
    assert bridge.recent() == []
    restarted = RunnerAdapter(
        bridge.database, configuration=bridge.configuration, registration=Chain()
    )
    assert restarted.preflight() == result


def test_review_names_registration_as_the_gate_and_carries_no_grant(
    tmp_path, monkeypatch
):
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    enable(bridge, cfg)
    result = bridge.preflight()
    assert result["available"] is True
    assert result["admission"] == "SUBNET_REGISTRATION_CHECKED_AT_LAUNCH"
    review = result["review"]
    assert review["admission"]["gate"] == "SUBNET_REGISTRATION"
    assert review["readiness"]["registration_checked"] == "AT_LAUNCH"
    assert "grant" not in review and "grant" not in result
    assert "GRANT" not in json.dumps(review["blockers"])


def test_review_budget_is_the_miners_and_service_limits_are_carbons(
    tmp_path, monkeypatch
):
    """The regression this guards: development ceilings described as a miner's."""
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    enable(bridge, cfg)
    resources = bridge.preflight()["review"]["resources"]
    assert resources["miner_budget"] == "SET_AT_LAUNCH_OR_NONE"
    assert resources["carbon_service_limits"] == SERVICE_LIMITS
    assert "maximum_exploration" not in resources
    assert "configured_ceilings" not in resources
    # The development provider cap was one dollar; it must describe no miner.
    specimen = DEVELOPMENT_CEILINGS["provider_nanodollars"]
    assert str(specimen) in json.dumps(DEVELOPMENT_CEILINGS)
    assert str(specimen) not in json.dumps(resources)


def test_an_unregistered_launch_is_refused_and_writes_nothing(tmp_path, monkeypatch):
    chain = Chain(failure="NOT_REGISTERED")
    bridge, cfg = configured_bridge(tmp_path, monkeypatch, chain=chain)
    enable(bridge, cfg)
    monkeypatch.setattr(bridge, "_start", lambda *args: None)
    body = {
        "profile": cfg["profile_id"],
        "review_digest": bridge.preflight()["review_digest"],
    }
    with pytest.raises(Rejected, match="registration_required"):
        bridge.launch(body, "fixture-request-0001")
    assert bridge.recent() == []
    assert not Path(cfg["campaigns_root"]).exists()
    chain.failure = None
    assert bridge.launch(body, "fixture-request-0001")["id"] == run_id(
        "fixture-request-0001"
    )


def test_a_v1_profile_is_named_as_retired_not_silently_refused(tmp_path, monkeypatch):
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    write(bridge, {**cfg, "schema": "carbon.launchpad.runner-profile.v1"})
    result = bridge.preflight()
    assert result["status"] == "PROFILE_V1_RETIRED"
    assert "registration" in result["reason"]
    with pytest.raises(Rejected, match="runner_profile_v1_retired"):
        bridge.launch({"profile": cfg["profile_id"]}, "fixture-request-0001")


def test_pause_explanation_cannot_enable_or_override_authority(tmp_path, monkeypatch):
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    cfg["enabled"] = True
    write(bridge, cfg)
    assert not bridge.preflight()["available"]
    with pytest.raises(Rejected):
        bridge.launch(
            {"profile": cfg["profile_id"], "enabled": True}, "fixture-request-0001"
        )
    assert bridge.recent() == []


def test_disabled_resume_keeps_status_stop_and_reconciliation(tmp_path, monkeypatch):
    bridge, ledger, control = adapter(tmp_path, monkeypatch)
    run = bridge.launch({"profile": "opaque-profile"}, KEY)

    def disabled():
        raise Rejected("research_dispatch_disabled", 409)

    monkeypatch.setattr(bridge, "configured", disabled)
    monkeypatch.setattr(bridge, "_cleanup", lambda _: True)
    with pytest.raises(Rejected, match="disabled"):
        bridge.control(run["id"], "resume")
    assert bridge.get(run["id"])["id"] == run["id"]
    bridge.control(run["id"], "stop")
    result = bridge.control(run["id"], "reconcile")
    assert result["state"] == "STOPPED"
    assert control.status()["desired"] == "STOP"
    assert not any(
        op["state"] == "RESERVED"
        for op in ledger.status(owner="miner-requester")["operations"]
    )


def test_paused_direct_http_request_rejects_and_review_requires_auth(
    tmp_path, monkeypatch
):
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    server = Server(
        Controller(tmp_path / "http.sqlite3"),
        "fixture-token-long-enough-for-session",
        0,
        research_runner=bridge,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, authenticated=True):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        headers = {"Host": f"127.0.0.1:{server.server_port}"}
        if authenticated:
            headers["Authorization"] = "Bearer fixture-token-long-enough-for-session"
        body = None
        if method == "POST":
            body = json.dumps({"profile": cfg["profile_id"]})
            headers.update(
                {
                    "Content-Type": "application/json",
                    "Idempotency-Key": "fixture-request-0001",
                }
            )
        try:
            conn.request(method, "/api/v1/research", body, headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    try:
        assert request("GET", False)[0] == 401
        assert request("GET")[1]["preflight"]["status"] == "OWNER_EXPERIMENT_PAUSE"
        assert request("POST") == (409, {"error": "research_dispatch_disabled"})
        assert bridge.recent() == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_gpu_configuration_is_not_cpu_fallback_or_execution_evidence(
    tmp_path, monkeypatch
):
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    cfg["runtime"]["gpu_research"] = []  # Deliberately incomplete engineering fixture.
    # A declared GPU runtime names the miner's built record (C-MLP-02-D11).
    cfg["gpu_image"] = str(tmp_path / "gpu-image-record.json")
    write(bridge, cfg)
    result = bridge.preflight()
    assert not result["available"]
    # A malformed scope is no longer reviewed as a GPU campaign. Advertising a
    # cuda backend the runner refuses to assemble is exactly the mismatch this
    # projection exists to prevent, so the review reports the composition as
    # unavailable and leaves the described research runtime CPU.
    assert result["review"]["execution"]["backend"] == "cpu"
    assert result["review"]["execution"]["assurance"] is None
    assert result["review"]["capabilities"]["gpu_research"] is False
    assert (
        "LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE"
        in result["review"]["blockers"]
    )
    enable(bridge, cfg)
    with pytest.raises(Rejected, match="runtime_interface_unavailable"):
        bridge.launch({"profile": cfg["profile_id"]}, "fixture-request-0001")


def _well_formed_gpu_scope():
    """A structurally valid declared scope, not a bound one.

    Binding the scope to real public TRAIN material needs a generated campaign;
    what this exercises is the review and runner path, which check shape and
    must stop claiming the composition is unavailable once the shape is right.
    """
    from carbon.development_session.gpu_research import SCHEMA

    return {
        "schema": SCHEMA,
        "profile_digest": "sha256:" + "e" * 64,
        "image": "sha256:" + "f" * 64,
        "image_manifest_digest": "sha256:" + "1" * 64,
        "assembly": "sha256:" + "2" * 64,
        "catalogue": "sha256:" + "3" * 64,
        "public_train_digest": "sha256:" + "4" * 64,
        "role": "MINER_RESEARCH",
        "productive_seconds": 600,
        "validation_cleanup_seconds": 120,
        "score": None,
        "official_eligible": False,
    }


def test_declared_gpu_research_is_reviewed_as_its_own_runtime(tmp_path, monkeypatch):
    """The composition banner and the described runtime finally agree.

    Before this, a campaign declaring GPU research was shown with a cuda backend
    *and* a blocker saying the campaign composition was unavailable, because no
    runner could assemble one. A miner could not tell which of the two to
    believe. Now the runner assembles it, so neither statement contradicts the
    other.
    """
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    cfg["runtime"]["gpu_research"] = [_well_formed_gpu_scope()]
    # A declared GPU runtime names the miner's built record (C-MLP-02-D11).
    cfg["gpu_image"] = str(tmp_path / "gpu-image-record.json")
    write(bridge, cfg)

    review = bridge.preflight()["review"]

    assert (
        "LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE" not in review["blockers"]
    )
    assert review["execution"]["backend"] == "cuda"
    assert review["execution"]["lane"] == "MINER_CONTAINED"
    assert review["execution"]["scope"] == "MINER_RESEARCH_ONLY"
    assert review["capabilities"]["gpu_research"] is True
    # The owner's direction, made checkable: research compute is the miner's
    # choice, and choosing it neither selects nor rewrites the evaluator.
    assert review["final_evaluation"]["backend"] == "cpu"
    assert review["final_evaluation"]["selected_by_research_runtime"] is False
    assert review["execution"]["assurance"]["validator_grade"] is False
    assert review["execution"]["assurance"]["official_eligible"] is False
    # A GPU research selection says nothing about Julia, which keeps its own
    # CPU route.
    assert review["capabilities"]["julia_on_gpu"] is False


def test_review_keeps_readiness_states_distinct(tmp_path, monkeypatch):
    """No single green badge. Each state carries its own evidence."""
    bridge, _cfg = configured_bridge(tmp_path, monkeypatch)
    readiness = bridge.preflight()["review"]["readiness"]
    assert readiness["connection_configured"] is False
    assert readiness["device_execution_observed"] is False
    assert readiness["task_admitted"] is False
    assert readiness["cleanup_verified"] is False
    assert readiness["official_qualification"] is False
    assert readiness["compatible_runtime_available"] == "NOT_OBSERVED_BY_REVIEW"
    # Review inspects configuration; it is not permitted to claim observations.
    assert set(readiness) >= {
        "connection_configured",
        "dependencies_inspected",
        "compatible_runtime_available",
        "registration_checked",
        "task_admitted",
        "device_execution_observed",
        "task_completed",
        "cleanup_verified",
        "independent_development_evaluation_available",
        "official_qualification",
    }


def test_pause_at_thread_handoff_never_enters_campaign(tmp_path, monkeypatch):
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    enable(bridge, cfg)
    # Retain the launch record without creating any numerical/model thread.
    monkeypatch.setattr(bridge, "_start", lambda *args: None)
    monkeypatch.setattr(bridge, "get", lambda identity: {"id": identity})
    review = bridge.preflight()
    run = bridge.launch(
        {"profile": cfg["profile_id"], "review_digest": review["review_digest"]},
        "fixture-request-0001",
    )
    root = Path(cfg["campaigns_root"]) / run["id"]
    ledger, _, _ = product_campaign(root, run["id"])
    from carbon.development_session import research_campaign

    monkeypatch.setattr(
        research_campaign,
        "execute",
        lambda *args, **kwargs: pytest.fail("paused dispatch"),
    )
    disabled = {**cfg, "enabled": False, "disabled_reason": "OWNER_EXPERIMENT_PAUSE"}
    write(bridge, disabled)
    before = ledger.status(owner="miner-requester")
    bridge._run(run["id"], cfg, root, None)
    assert ledger.status(owner="miner-requester") == before
    with bridge.db() as db:
        assert (
            db.execute("SELECT state FROM launchpad_campaigns").fetchone()[0]
            == "RECONCILIATION_REQUIRED"
        )


def test_the_review_pin_binds_the_profile_the_miner_reviewed(tmp_path, monkeypatch):
    """Any change to the profile after review invalidates the pin, and a stale
    pin records nothing. A lost response still replays the launch it made."""
    bridge, cfg = configured_bridge(tmp_path, monkeypatch)
    enable(bridge, cfg)
    old_review = bridge.preflight()["review_digest"]
    cfg["runtime"]["images"] = ["sha256:" + "e" * 64]
    write(bridge, cfg)
    monkeypatch.setattr(bridge, "_start", lambda *args: None)
    monkeypatch.setattr(bridge, "get", lambda identity: {"id": identity})
    for stale in (old_review, digest(canonical(cfg))):
        with pytest.raises(Rejected, match="research_review_changed"):
            bridge.launch(
                {"profile": cfg["profile_id"], "review_digest": stale},
                "fixture-request-0001",
            )
    with bridge.db() as db:
        assert db.execute("SELECT COUNT(*) FROM launchpad_campaigns").fetchone()[0] == 0
    fresh = bridge.preflight()["review_digest"]
    assert fresh != old_review
    body = {"profile": cfg["profile_id"], "review_digest": fresh}
    first = bridge.launch(body, "fixture-request-0001")
    assert bridge.launch(body, "fixture-request-0001") == first
