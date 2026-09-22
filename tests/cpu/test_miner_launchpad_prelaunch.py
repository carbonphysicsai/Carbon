"""Non-spending prelaunch diagnostics; no model, numerical or chain dispatch."""

import http.client
import json
import threading
import time

import pytest
from test_miner_launchpad_admission import managed
from test_miner_launchpad_runner import adapter

from carbon.development_session.profile import canonical, digest
from scripts.dev.miner_launchpad.controller import Controller, Rejected, Server
from scripts.dev.miner_launchpad.runner import PATH_FIELDS, RunnerAdapter


def configured_bridge(tmp_path, monkeypatch):
    ledger, _, _ = managed(tmp_path)
    doc = dict(ledger.admission.document)
    doc["runtime"] = {
        "implementation": {
            "revision": "a" * 40,
            "tree": "b" * 40,
            "source_tree_digest": "sha256:" + "c" * 64,
        },
        "images": ["sha256:" + "d" * 64],
    }
    doc["expires_unix"] = time.time() + 600
    ledger.admission.path.write_bytes(canonical(doc))
    cfg = {
        "schema": "carbon.launchpad.runner-profile.v1",
        "profile_id": "private-fixture",
        "principal": "alice",
        "grant_file": str(ledger.admission.path),
        "account_ref": doc["account_ref"],
        "enabled": False,
        "disabled_reason": "OWNER_EXPERIMENT_PAUSE",
        "accepted_revision": "a" * 40,
        "paths": {
            key: str(tmp_path / ("PRIVATE-SENTINEL-" + key)) for key in PATH_FIELDS
        },
        "research_guidance": "Private fixture objective; retain measured feedback.",
    }
    path = tmp_path / "profile.json"
    path.write_bytes(canonical(cfg))
    path.chmod(0o600)
    bridge = RunnerAdapter(tmp_path / "browser.sqlite3", configuration=path)
    monkeypatch.setattr(
        bridge, "_start", lambda *args: pytest.fail("dispatch forbidden")
    )
    return bridge, cfg, doc, ledger


def test_paused_review_discloses_contract_not_private_inputs(tmp_path, monkeypatch):
    bridge, cfg, doc, ledger = configured_bridge(tmp_path, monkeypatch)
    before = ledger.admission.path.read_bytes()
    result = bridge.preflight()
    assert not result["available"] and result["status"] == "OWNER_EXPERIMENT_PAUSE"
    assert result["research_guidance"]["text"] == cfg["research_guidance"]
    review = result["review"]
    assert review["execution"]["device_visibility"] == "NOT_OBSERVED"
    assert review["execution"]["runtime_evidence"] == "NOT_ATTACHED"
    assert review["runtime"]["implementation"] == doc["runtime"]["implementation"]
    assert "PRIVATE-SENTINEL" not in json.dumps(result)
    assert cfg["account_ref"] not in json.dumps(result)
    assert ledger.admission.path.read_bytes() == before
    for _ in range(2):
        with pytest.raises(Rejected, match="research_dispatch_disabled"):
            bridge.launch({"profile": cfg["profile_id"]}, "fixture-request-0001")
    assert bridge.recent() == []
    restarted = RunnerAdapter(bridge.database, configuration=bridge.configuration)
    assert restarted.preflight() == result


@pytest.mark.parametrize(
    "state,expiry", [("REQUESTED_NOT_GRANTED", False), ("APPROVED", True)]
)
def test_expired_or_unapproved_grant_remains_reviewable_not_admissible(
    tmp_path, monkeypatch, state, expiry
):
    bridge, cfg, doc, ledger = configured_bridge(tmp_path, monkeypatch)
    doc["status"] = state
    if expiry:
        doc["expires_unix"] = 1
    ledger.admission.path.write_bytes(canonical(doc))
    cfg.pop("disabled_reason")
    cfg["enabled"] = True
    bridge.configuration.write_bytes(canonical(cfg))
    result = bridge.preflight()
    assert not result["available"]
    assert result["review"]["grant"]["expired"] is expiry
    assert result["review"]["grant"]["status"] == state
    with pytest.raises(Rejected, match="admission"):
        bridge.launch({"profile": cfg["profile_id"]}, "fixture-request-0001")


def test_pause_explanation_cannot_enable_or_override_authority(tmp_path, monkeypatch):
    bridge, cfg, _, _ = configured_bridge(tmp_path, monkeypatch)
    cfg["enabled"] = True
    bridge.configuration.write_bytes(canonical(cfg))
    assert not bridge.preflight()["available"]
    with pytest.raises(Rejected):
        bridge.launch(
            {"profile": cfg["profile_id"], "enabled": True}, "fixture-request-0001"
        )
    assert bridge.recent() == []


def test_disabled_resume_keeps_status_stop_and_reconciliation(tmp_path, monkeypatch):
    bridge, ledger, control = adapter(tmp_path, monkeypatch)
    run = bridge.launch({"profile": "opaque-profile"}, "fixture-request-0001")

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


def test_final_reserve_projection_uses_existing_ledger_contract(tmp_path, monkeypatch):
    bridge, _, doc, _ = configured_bridge(tmp_path, monkeypatch)
    from carbon.development_session.research_ledger import SUGGESTED_FINAL_RESERVE

    review = bridge.preflight()["review"]["resources"]
    assert review["final_evaluation_reserve"] == SUGGESTED_FINAL_RESERVE
    for dimension, ceiling in doc["ceilings"].items():
        assert (
            review["maximum_exploration"][dimension]
            + SUGGESTED_FINAL_RESERVE.get(dimension, 0)
            == ceiling
        )


def test_paused_direct_http_request_rejects_and_review_requires_auth(
    tmp_path, monkeypatch
):
    bridge, cfg, _, _ = configured_bridge(tmp_path, monkeypatch)
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
    bridge, cfg, doc, ledger = configured_bridge(tmp_path, monkeypatch)
    doc["runtime"]["gpu_research"] = []  # Deliberately incomplete engineering fixture.
    ledger.admission.path.write_bytes(canonical(doc))
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
    cfg.pop("disabled_reason")
    cfg["enabled"] = True
    bridge.configuration.write_bytes(canonical(cfg))
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

    Before this, a grant declaring GPU research was shown with a cuda backend
    *and* a blocker saying the campaign composition was unavailable, because no
    runner could assemble one. A miner could not tell which of the two to
    believe. Now the runner assembles it, so neither statement contradicts the
    other.
    """
    bridge, _cfg, doc, ledger = configured_bridge(tmp_path, monkeypatch)
    doc["runtime"]["gpu_research"] = [_well_formed_gpu_scope()]
    ledger.admission.path.write_bytes(canonical(doc))

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
    bridge, _cfg, _doc, _ledger = configured_bridge(tmp_path, monkeypatch)
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
        "user_consent_active",
        "task_admitted",
        "device_execution_observed",
        "task_completed",
        "cleanup_verified",
        "independent_development_evaluation_available",
        "official_qualification",
    }


def test_pause_at_thread_handoff_never_enters_campaign(tmp_path, monkeypatch):
    bridge, cfg, _, ledger = configured_bridge(tmp_path, monkeypatch)
    cfg.pop("disabled_reason")
    cfg["enabled"] = True
    bridge.configuration.write_bytes(canonical(cfg))
    # Retain the launch record without creating any numerical/model thread.
    monkeypatch.setattr(bridge, "_start", lambda *args: None)
    monkeypatch.setattr(bridge, "get", lambda identity: {"id": identity})
    review = bridge.preflight()
    run = bridge.launch(
        {"profile": cfg["profile_id"], "review_digest": review["review_digest"]},
        "fixture-request-0001",
    )
    from carbon.development_session import research_campaign

    monkeypatch.setattr(
        research_campaign,
        "execute",
        lambda *args, **kwargs: pytest.fail("paused dispatch"),
    )
    disabled = {**cfg, "enabled": False, "disabled_reason": "OWNER_EXPERIMENT_PAUSE"}
    bridge.configuration.write_bytes(canonical(disabled))
    before = ledger.status(owner="miner-requester")
    bridge._run(run["id"], cfg, ledger.admission, ledger.root)
    assert ledger.status(owner="miner-requester") == before
    with bridge.db() as db:
        assert (
            db.execute("SELECT state FROM research_runs").fetchone()[0]
            == "RECONCILIATION_REQUIRED"
        )


def test_guided_review_binds_grant_and_legacy_token_only_recovers_existing_run(
    tmp_path, monkeypatch
):
    bridge, cfg, doc, ledger = configured_bridge(tmp_path, monkeypatch)
    cfg.pop("disabled_reason")
    cfg["enabled"] = True
    bridge.configuration.write_bytes(canonical(cfg))
    old_review = bridge.preflight()["review_digest"]
    legacy = digest(canonical(cfg))
    doc["ceilings"]["provider_attempts"] -= 1
    ledger.admission.path.write_bytes(canonical(doc))
    monkeypatch.setattr(bridge, "_start", lambda *args: None)
    monkeypatch.setattr(bridge, "get", lambda identity: {"id": identity})
    for stale in (old_review, legacy):
        with pytest.raises(Rejected, match="research_review_changed"):
            bridge.launch(
                {"profile": cfg["profile_id"], "review_digest": stale},
                "fixture-request-0001",
            )
    with bridge.db() as db:
        assert db.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0] == 0
    fresh = bridge.preflight()["review_digest"]
    assert fresh != old_review
    first = bridge.launch(
        {"profile": cfg["profile_id"], "review_digest": fresh}, "fixture-request-0001"
    )
    assert (
        bridge.launch(
            {"profile": cfg["profile_id"], "review_digest": legacy},
            "fixture-request-0001",
        )
        == first
    )
