"""One safe retry after an ambiguous RunPod create (operator compute layer).

Against the MOCK RunPod only: no network, no credentials, no spend. An ambiguous create is
reconciled by ownership tag first. Found: adopted, never created again. Not found, and the
reconcile itself succeeded: the create is resent ONCE with the same tag (a durable claim, so
two callers cannot both resend). The reconcile failing, a second ambiguity, or a resend
already claimed fails closed: no further create.
"""

from __future__ import annotations

import threading

import pytest
from operator_fake_runpod import Clock, FakeRunPod, key_file
from test_graphite_operator_runpod import request

from scripts.dev.exam_design.runpod.operator_compute import (
    ComputeError,
    ComputeService,
    ComputeStore,
    Execution,
    FileCredentialProvider,
    IntentState,
    RunPodAdapter,
    reconcile,
)
from scripts.dev.exam_design.runpod.operator_compute.model import ownership_name


@pytest.fixture
def env(tmp_path):
    clock, fake = Clock(), FakeRunPod()
    store = ComputeStore(tmp_path / "controller-host-store", clock=clock)
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
    yield clock, fake, store, adapter, service, tmp_path
    store.close()


def test_ambiguous_then_absent_resends_exactly_once_with_the_same_tag(env):
    clock, fake, store, _adapter, service, _root = env
    fake.lose_create_requests = 1
    record = service.provision(request(clock), retry_ambiguous=True)
    assert fake.creates() == 2  # the lost request and the one resend
    assert len(fake.pods) == 1 and record.resource_id in fake.pods
    intent = store.intent("camp-1", "intent-1")
    assert intent.state is IntentState.BOUND
    [pod] = fake.pods.values()
    assert pod["name"] == ownership_name(intent.ownership_tag)


def test_ambiguous_then_present_adopts_and_never_creates_again(env):
    clock, fake, _store, _adapter, service, _root = env
    fake.lose_next_create_response = (
        True  # the pod WAS created; only the reply was lost
    )
    record = service.provision(request(clock), retry_ambiguous=True)
    assert fake.creates() == 1 and len(fake.pods) == 1
    assert record.discovered_via == "tag_reconcile"


def test_a_failed_reconcile_fails_closed_with_no_retry(env):
    clock, fake, _store, _adapter, service, _root = env
    fake.lose_create_requests = 1
    fake.fail_next_list_with = 500
    with pytest.raises(ComputeError) as stopped:
        service.provision(request(clock), retry_ambiguous=True)
    assert stopped.value.execution is Execution.MAY_HAVE_EXECUTED
    assert stopped.value.resources_may_remain and not stopped.value.retry_safe
    assert fake.creates() == 1 and not fake.pods


def test_ambiguous_twice_stops_with_no_third_create(env):
    clock, fake, _store, _adapter, service, _root = env
    fake.lose_create_requests = 2
    with pytest.raises(ComputeError) as stopped:
        service.provision(request(clock), retry_ambiguous=True)
    assert "twice" in stopped.value.failed and stopped.value.resources_may_remain
    assert fake.creates() == 2
    # The same intent again never resends: it only reconciles.
    with pytest.raises(ComputeError):
        service.provision(request(clock), retry_ambiguous=True)
    assert fake.creates() == 2


def test_without_the_option_an_ambiguous_create_is_never_resent(env):
    clock, fake, _store, _adapter, service, _root = env
    fake.lose_create_requests = 1
    with pytest.raises(ComputeError) as lost:
        service.provision(request(clock))
    assert lost.value.execution is Execution.MAY_HAVE_EXECUTED
    assert fake.creates() == 1 and not fake.pods


def test_the_resend_is_claimed_once_across_services_sharing_a_store(env):
    _clock, _fake, store, _adapter, _service, _root = env
    assert store.claim_resend("camp-1", "intent-1") is True
    assert store.claim_resend("camp-1", "intent-1") is False
    assert store.claim_resend("camp-1", "intent-2") is True


def test_a_claimed_resend_means_the_next_ambiguity_fails_closed(env):
    clock, fake, store, _adapter, service, _root = env
    store.claim_resend("camp-1", "intent-1")  # e.g. a controller that already resent
    fake.lose_create_requests = 1
    with pytest.raises(ComputeError) as stopped:
        service.provision(request(clock), retry_ambiguous=True)
    assert "already claimed" in stopped.value.failed
    assert fake.creates() == 1


def test_concurrent_controllers_on_one_store_create_at_most_twice(tmp_path, env):
    clock, fake, store, adapter, _service, _root = env
    fake.lose_create_requests = 1
    barrier = threading.Barrier(2)
    outcomes = []

    def controller():
        service = ComputeService(store, adapter, clock=clock)
        barrier.wait()
        try:
            outcomes.append(
                ("bound", service.provision(request(clock), retry_ambiguous=True))
            )
        except ComputeError as error:
            outcomes.append(("stopped", error))

    threads = [threading.Thread(target=controller) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert fake.creates() <= 2  # the lost request and at most the one resend
    assert len(fake.pods) <= 1
    assert [kind for kind, _ in outcomes].count("bound") >= 1


def test_a_stray_first_pod_is_flagged_duplicate_and_terminated_by_the_reconciler(env):
    # Worst case the retry accepts: the first create did land but was not listed yet.
    # Both pods then carry the tag; the second is a duplicate and the reconciler ends it.
    clock, fake, store, adapter, service, _root = env
    fake.lose_create_requests = 1
    record = service.provision(request(clock), retry_ambiguous=True)
    intent = store.intent("camp-1", "intent-1")
    fake.add_pod("latefirst", ownership_name(intent.ownership_tag))
    report = reconcile(store, adapter, clock=clock)
    assert record.role == "primary"
    assert {"resource_id": "latefirst", "reason": "duplicate_for_intent"} in (
        report.terminated
    )


# -- the live Graphite backend asks for the retry only when told to ----------------------------
def _live_backend(tmp_path, fake, clock, **options):
    from decimal import Decimal

    from test_graphite_pod_store_threads import SCORING, _head

    from carbon.agent_campaign.graphite import pods

    return pods.RunPodPods(
        root=tmp_path / "pods",
        key_file=key_file(tmp_path),
        code_ref=_head(),
        clock=clock,
        transport=fake,
        http=lambda *_args: (0, b""),
        sleep=lambda _seconds: None,
        balance_floor=lambda: Decimal(0),
        scoring=SCORING,
        **options,
    )


def _job():
    from carbon.agent_campaign.graphite import pods

    return pods.PodJob(
        intent_id="retry-0",
        strategy={"index": 0},
        contract_digest="sha256:" + "0" * 64,
        seed=0,
        expected={"files": {}},
        minutes=30,
        seconds=600,
    )


def test_the_live_backend_retries_once_when_asked(tmp_path):
    from carbon.agent_campaign.graphite import pods

    clock, fake = Clock(), FakeRunPod()
    fake.lose_create_requests = 1
    backend = _live_backend(tmp_path, fake, clock, retry_ambiguous_create=True)
    handle = backend.launch(_job(), pods.private_dir(tmp_path / "private" / "retry-0"))
    assert fake.creates() == 2 and len(fake.pods) == 1 and handle.pod_id in fake.pods


def test_the_live_backend_does_not_retry_by_default(tmp_path):
    from carbon.agent_campaign.graphite import pods

    clock, fake = Clock(), FakeRunPod()
    fake.lose_create_requests = 1
    backend = _live_backend(tmp_path, fake, clock)
    with pytest.raises(pods.PodFailure) as ambiguous:
        backend.launch(_job(), pods.private_dir(tmp_path / "private" / "retry-0"))
    assert ambiguous.value.executed is True and fake.creates() == 1


def test_the_live_phase3_command_enables_the_retry():
    import inspect

    from carbon.agent_campaign.graphite import phase3

    assert "retry_ambiguous_create=True" in inspect.getsource(phase3)
