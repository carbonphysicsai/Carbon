"""carbon.compute lifecycle, ownership and reconciler - against a MOCK RunPod."""

from __future__ import annotations

import json
import logging
import re
import sqlite3

import pytest
from compute_fake_runpod import MOCK_KEY, Clock, FakeRunPod, key_file

from carbon.compute import (
    CarbonOwnedResource,
    ComputeError,
    ComputeService,
    ComputeStore,
    Execution,
    FileCredentialProvider,
    IntentState,
    PodSpec,
    ProvisionRequest,
    ResourceState,
    RunPodAdapter,
    UserManagedHost,
    reconcile,
)
from carbon.compute.cli import main as cli_main
from carbon.compute.runpod import ALLOWED_OPERATIONS

IMAGE = "ghcr.io/example/worker@sha256:" + "0" * 64


def spec(**overrides) -> PodSpec:
    values = {
        "image": IMAGE,
        "gpu_type_id": "NVIDIA A40",
        "gpu_count": 1,
        "container_disk_gb": 20,
        "max_rate_usd_per_hr": 0.49,
        "storage_usd_per_gb_month": 0.10,
    }
    values.update(overrides)
    return PodSpec(**values)


def request(clock, intent_id="intent-1", campaign="camp-1", hours=2.0, **kw):
    return ProvisionRequest(
        tenant="tenant-1",
        miner="miner-1",
        campaign_id=campaign,
        intent_id=intent_id,
        spec=spec(**kw),
        deadline_at=clock() + hours * 3600,
    )


@pytest.fixture
def env(tmp_path):
    clock = Clock()
    fake = FakeRunPod()
    root = tmp_path / "controller-host-store"
    store = ComputeStore(root, clock=clock)
    adapter = RunPodAdapter(
        FileCredentialProvider(key_file(tmp_path)),
        fake,
        clock=clock,
        sleep=lambda _s: None,
        verify_attempts=2,
    )
    service = ComputeService(store, adapter, clock=clock)
    store.start_campaign("camp-1")
    service.observe_balance("camp-1")
    yield clock, fake, store, adapter, service, root
    store.close()


def intent_state(root, campaign="camp-1", intent="intent-1"):
    db = sqlite3.connect(root / "compute.sqlite3")
    try:
        row = db.execute(
            "SELECT state, ownership_tag FROM intents WHERE campaign_id=? AND intent_id=?",
            (campaign, intent),
        ).fetchone()
    finally:
        db.close()
    return row


def test_intent_is_durable_before_the_provider_request(env):
    clock, fake, _store, _adapter, service, root = env
    seen = []

    def at_request(method, url):
        if method == "POST" and url.endswith("/v1/pods"):
            # Read through a separate connection: the intent must already be
            # committed and marked "may have been sent".
            seen.append(intent_state(root))

    fake.on_request = at_request
    record = service.provision(request(clock))
    assert seen and seen[0][0] == IntentState.DISPATCHED
    tag = seen[0][1]
    assert fake.pods[record.resource_id]["name"] == f"carbon-{tag}"
    assert fake.pods[record.resource_id]["env"]["CARBON_OWNERSHIP_TAG"] == tag
    assert intent_state(root)[0] == IntentState.BOUND


def test_lost_create_response_is_adopted_by_tag_without_a_second_create(env):
    clock, fake, _store, _adapter, service, _root = env
    fake.lose_next_create_response = True
    with pytest.raises(ComputeError) as lost:
        service.provision(request(clock))
    assert lost.value.execution is Execution.MAY_HAVE_EXECUTED
    assert lost.value.resources_may_remain and not lost.value.retry_safe
    assert fake.creates() == 1

    record = service.provision(request(clock))  # same intent: recover, not resend
    assert fake.creates() == 1
    assert record.discovered_via == "tag_reconcile"
    assert record.resource_id in fake.pods


def test_lost_create_response_is_adopted_by_the_independent_reconciler(env):
    clock, fake, store, adapter, _service, _root = env
    fake.lose_next_create_response = True
    with pytest.raises(ComputeError):
        ComputeService(store, adapter, clock=clock).provision(request(clock))
    report = reconcile(store, adapter, clock=clock)
    assert len(report.adopted) == 1 and fake.creates() == 1
    assert store.intent("camp-1", "intent-1").state is IntentState.BOUND


def test_duplicate_provision_is_idempotent_and_a_changed_request_is_refused(env):
    clock, fake, _store, _adapter, service, _root = env
    req = request(clock)
    first = service.provision(req)
    again = service.provision(req)
    assert first.resource_id == again.resource_id and fake.creates() == 1
    with pytest.raises(ComputeError, match="different request"):
        service.provision(request(clock, container_disk_gb=40))
    assert fake.creates() == 1


def test_definitive_provider_refusal_is_rejected_not_left_ambiguous(env):
    clock, fake, store, _adapter, service, _root = env
    fake.fail_next_create_with = 400
    with pytest.raises(ComputeError) as refused:
        service.provision(request(clock))
    assert refused.value.execution is Execution.EXECUTED
    assert not refused.value.resources_may_remain
    assert store.intent("camp-1", "intent-1").state is IntentState.REJECTED


def test_provision_requires_a_recorded_balance_observation(tmp_path):
    clock, fake = Clock(), FakeRunPod()
    store = ComputeStore(tmp_path / "s", clock=clock)
    adapter = RunPodAdapter(
        FileCredentialProvider(key_file(tmp_path)), fake, clock=clock
    )
    service = ComputeService(store, adapter, clock=clock)
    store.start_campaign("camp-1")
    with pytest.raises(ComputeError, match="no account balance observation") as refused:
        service.provision(request(clock))
    assert refused.value.execution is Execution.NOT_EXECUTED
    assert fake.creates() == 0
    service.observe_balance("camp-1")
    assert store.latest_balance("runpod", "camp-1") == (100.0, clock())
    assert service.provision(request(clock)).resource_id in fake.pods


def test_balance_is_the_cap_and_the_miner_budget_applies_below_it(env, tmp_path):
    clock, fake, store, _adapter, service, _root = env
    # 0.49/h + 20 GB storage for 2h is about 0.99; balance 100 admits it.
    service.provision(request(clock))
    fake.balance = 1.5
    service.observe_balance("camp-1")
    with pytest.raises(ComputeError, match="observed account balance"):
        service.provision(request(clock, intent_id="intent-2"))
    assert fake.creates() == 1

    store.start_campaign("camp-2", miner_budget_usd=0.5)
    fake.balance = 100.0
    service.observe_balance("camp-2")
    with pytest.raises(ComputeError, match="miner's campaign budget"):
        service.provision(request(clock, intent_id="i", campaign="camp-2"))
    with pytest.raises(ComputeError, match="unbounded"):
        service.provision(
            request(clock, intent_id="j", campaign="camp-2", max_rate_usd_per_hr=None)
        )
    assert fake.creates() == 1


def test_stale_balance_observation_is_refused_when_an_age_bound_is_set(env):
    clock, fake, store, adapter, _service, _root = env
    strict = ComputeService(store, adapter, clock=clock, max_balance_age_s=300)
    clock.advance(301)
    with pytest.raises(ComputeError, match="stale"):
        strict.provision(request(clock))
    assert fake.creates() == 0


def test_terminate_refuses_a_user_managed_host_and_a_raw_resource_id(env):
    clock, fake, _store, adapter, service, _root = env
    record = service.provision(request(clock))
    host = UserManagedHost("my-box", "http://10.0.0.5:8000")
    assert not hasattr(host, "terminate")
    with pytest.raises(ComputeError, match="user-managed host"):
        adapter.terminate(host)  # type: ignore[arg-type]
    # A perfectly valid, live pod id is still refused as a raw string.
    with pytest.raises(ComputeError, match="store-issued"):
        adapter.terminate(record.resource_id)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        CarbonOwnedResource(
            provider="runpod",
            campaign_id="camp-1",
            intent_id="intent-1",
            resource_id=record.resource_id,
            ownership_tag="0" * 24,
        )
    assert record.resource_id in fake.pods
    assert (
        "DELETE",
        f"https://rest.runpod.io/v1/pods/{record.resource_id}",
    ) not in fake.calls


def test_terminate_refuses_an_untagged_pod_and_another_campaigns_intent(env):
    clock, fake, _store, _adapter, service, _root = env
    record = service.provision(request(clock))
    # Another campaign cannot obtain ownership of this campaign's resource.
    with pytest.raises(ComputeError, match="not bound to a Carbon intent"):
        service.terminate("camp-other", "intent-1", record.resource_id)
    # A user's own pod is never bound to an intent, so no handle exists for it.
    fake.add_pod("userpod1", "my-notebook")
    with pytest.raises(ComputeError, match="not bound"):
        service.terminate("camp-1", "intent-1", "userpod1")
    # If the live pod behind a recorded id no longer carries our tag, refuse.
    fake.pods[record.resource_id]["name"] = "renamed-by-user"
    with pytest.raises(ComputeError, match="ownership tag") as refused:
        service.terminate("camp-1", "intent-1", record.resource_id)
    assert refused.value.execution is Execution.NOT_EXECUTED
    assert not any(method == "DELETE" for method, _ in fake.calls)
    assert {"userpod1", record.resource_id} <= set(fake.pods)


def test_stop_keeps_the_resource_and_terminate_verifies_absence(env):
    clock, fake, store, _adapter, service, _root = env
    record = service.provision(request(clock))
    service.stop("camp-1", "intent-1", record.resource_id)
    assert fake.pods[record.resource_id]["desiredStatus"] == "EXITED"
    assert store.resource("runpod", record.resource_id).state is ResourceState.STOPPED
    service.terminate("camp-1", "intent-1", record.resource_id)
    assert record.resource_id not in fake.pods
    assert (
        store.resource("runpod", record.resource_id).state is ResourceState.TERMINATED
    )


def test_unverified_termination_is_reported_as_possibly_still_billing(env):
    clock, fake, store, adapter, service, _root = env
    record = service.provision(request(clock))
    fake.ignore_deletes = True
    with pytest.raises(ComputeError) as failed:
        service.terminate("camp-1", "intent-1", record.resource_id)
    assert failed.value.resources_may_remain and failed.value.retry_safe
    assert (
        store.resource("runpod", record.resource_id).state is ResourceState.TERMINATING
    )
    # An interrupted termination is finished by the reconciler, deadline or not.
    fake.ignore_deletes = False
    report = reconcile(store, adapter, clock=clock)
    assert report.terminated == [
        {"resource_id": record.resource_id, "reason": "termination_incomplete"}
    ]
    assert record.resource_id not in fake.pods


def test_cancel_before_dispatch_sends_nothing(env):
    clock, fake, store, _adapter, service, _root = env
    req = request(clock)
    store.begin_intent(req, provider="runpod")
    assert service.cancel_provisioning("camp-1", "intent-1") is IntentState.CANCELLED
    assert fake.creates() == 0
    with pytest.raises(ComputeError, match="cancelled"):
        service.provision(req)
    assert fake.creates() == 0


def test_reconciler_terminates_only_carbon_owned_expired_resources(env):
    clock, fake, store, adapter, service, _root = env
    expiring = service.provision(request(clock, intent_id="short", hours=1))
    running = service.provision(request(clock, intent_id="long", hours=5))
    fake.add_pod("userpod1", "my-notebook")  # untagged: never touched
    fake.add_pod("userpod2", None)
    fake.add_pod("orphan01", "carbon-" + "a" * 24)  # Carbon-shaped, unknown tag
    clock.advance(2 * 3600)

    report = reconcile(store, adapter, clock=clock)
    assert report.terminated == [
        {"resource_id": expiring.resource_id, "reason": "deadline_passed"}
    ]
    assert report.orphans == [{"resource_id": "orphan01", "name": "carbon-" + "a" * 24}]
    assert report.untagged_ignored == 2
    assert {"userpod1", "userpod2", "orphan01", running.resource_id} == set(fake.pods)
    touched = {
        url.rsplit("/", 1)[-1] for method, url in fake.calls if method == "DELETE"
    }
    assert touched == {expiring.resource_id}
    assert "userpod1" not in json.dumps(report.as_dict())

    store.stop_campaign("camp-1")
    report = reconcile(store, adapter, clock=clock)
    assert report.terminated == [
        {"resource_id": running.resource_id, "reason": "campaign_stopped"}
    ]
    assert set(fake.pods) == {"userpod1", "userpod2", "orphan01"}


def test_reconciler_runs_off_host_from_the_store_and_provider_api_alone(env, tmp_path):
    """The rented pod is unreachable here (the MOCK raises on any pod-proxy URL)."""

    clock, fake, store, _adapter, service, root = env
    record = service.provision(request(clock, hours=1))
    store.close()  # the controller process is gone
    clock.advance(2 * 3600)

    fresh_store = ComputeStore(root, clock=clock)  # the controller host's store path
    fresh_adapter = RunPodAdapter(
        FileCredentialProvider(tmp_path / "runpod_api_key"),
        fake,
        clock=clock,
        sleep=lambda _s: None,
    )
    report = reconcile(fresh_store, fresh_adapter, clock=clock)
    assert report.terminated[0]["resource_id"] == record.resource_id
    assert all("proxy.runpod.net" not in url for _m, url in fake.calls)
    fresh_store.close()


def test_reconcile_cli_refuses_on_a_rented_pod_and_without_a_store(
    env, tmp_path, capsys
):
    clock, fake, _store, _adapter, service, root = env
    service.provision(request(clock))
    key = tmp_path / "runpod_api_key"
    args = ["reconcile", "--root", str(root), "--runpod-key-file", str(key)]
    assert cli_main(args, transport=fake, environ={"RUNPOD_POD_ID": "x"}) == 2
    assert "off_the_rented_pod" in capsys.readouterr().out
    empty = [
        "reconcile",
        "--root",
        str(tmp_path / "nowhere"),
        "--runpod-key-file",
        str(key),
    ]
    assert cli_main(empty, transport=fake, environ={}) == 2
    assert "no_compute_store" in capsys.readouterr().out
    assert cli_main(args, transport=fake, environ={}) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["terminated"] == [] and out["untagged_ignored"] == 0


def test_adapter_requests_stay_inside_the_pod_lifecycle_allow_list(env):
    clock, fake, _store, adapter, service, _root = env
    record = service.provision(request(clock))
    adapter.offers(["NVIDIA A40"])
    service.stop("camp-1", "intent-1", record.resource_id)
    service.terminate("camp-1", "intent-1", record.resource_id)
    for method, url in fake.calls:
        assert any(
            m == method and re.fullmatch(p, url) for _o, m, p in ALLOWED_OPERATIONS
        ), (method, url)
    before = len(fake.calls)
    with pytest.raises(ComputeError, match="allow-list"):
        adapter._send(
            "status", "GET", "https://rest.runpod.io/v1/networkvolumes", mutating=False
        )
    with pytest.raises(ComputeError, match="allow-list"):
        adapter._send(
            "balance",
            "POST",
            "https://api.runpod.io/graphql",
            {"query": "mutation { podTerminate }"},
            mutating=True,
        )
    assert len(fake.calls) == before  # refused before anything was sent


def _contains_key(text: str) -> bool:
    return MOCK_KEY in text


def test_credential_never_appears_in_errors_or_logs(env, caplog):
    clock, fake, _store, _adapter, service, _root = env
    caplog.set_level(logging.DEBUG)
    fake.echo_key_in_next_failure = True
    with pytest.raises(ComputeError) as failed:
        service.provision(request(clock))
    specimen = f"reset while sending Bearer {MOCK_KEY}"
    # Positive control: the scan finds the key where it really is - the mock's
    # own exception text and the header the transport received.
    assert _contains_key(specimen)
    assert _contains_key(fake.headers_seen[-1]["Authorization"])
    rendered = [
        str(failed.value),
        repr(failed.value),
        json.dumps(failed.value.as_dict()),
        caplog.text,
        repr(FileCredentialProvider(None)),
    ]
    assert not any(_contains_key(text) for text in rendered)
    # The echoing exception is not chained, so no traceback can print it.
    assert failed.value.__cause__ is None and failed.value.__context__ is None


def test_credential_file_checks(tmp_path):
    good = key_file(tmp_path)
    assert FileCredentialProvider(good).status() == "configured"
    assert repr(FileCredentialProvider(good).load()) == "Secret(<redacted>)"
    assert str(FileCredentialProvider(good).load()) == "Secret(<redacted>)"
    assert FileCredentialProvider(None).status() == "credential_not_configured"
    assert (
        FileCredentialProvider(tmp_path / "missing").status()
        == "credential_not_configured"
    )
    loose = tmp_path / "loose"
    loose.write_text(MOCK_KEY)
    loose.chmod(0o644)
    assert FileCredentialProvider(loose).status() == "credential_file_unsafe"
    link = tmp_path / "link"
    link.symlink_to(good)
    assert FileCredentialProvider(link).status() == "credential_file_unsafe"
    big = tmp_path / "big"
    big.write_text("x" * 2000)
    big.chmod(0o600)
    assert FileCredentialProvider(big).status() == "credential_file_invalid"
    two = tmp_path / "two"
    two.write_text("a b")
    two.chmod(0o600)
    assert FileCredentialProvider(two).status() == "credential_file_invalid"
