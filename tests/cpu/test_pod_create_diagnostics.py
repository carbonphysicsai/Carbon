"""PLT-21: ambiguous create disclosure, against synthetic transports only."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_pod_jobs import lifecycle as job_lifecycle_fixture

from scripts.dev.exam_design.runpod.operator_compute import (
    ComputeError,
    Execution,
    PodSpec,
    RunPodAdapter,
)
from scripts.dev.exam_design.runpod.operator_compute.credentials import Secret
from scripts.dev.exam_design.runpod.operator_compute.runpod import (
    ambiguous_create_reason,
)

MARKER = "private-marker"  # Short enough to evade the former token-shape regex.
lifecycle = job_lifecycle_fixture  # Reuse the actual offline receipt/ledger fixture.
SPEC = PodSpec(
    image="example/worker@sha256:" + "0" * 64, gpu_type_id="A40", gpu_count=1
)


def adapter(payload, status=503):
    calls = []

    def transport(method, url, **kwargs):
        calls.append((method, url))
        return status, json.dumps(payload).encode()

    credentials = SimpleNamespace(load=lambda: Secret("SYNTHETIC_ONLY"))
    return RunPodAdapter(credentials, transport), calls


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({"code": "OUT_OF_STOCK"}, "provider_capacity"),
        ({"error": {"code": "QUOTA_EXCEEDED"}}, "provider_quota"),
        ({"reason": "rate_limit_exceeded"}, "provider_rate_limit"),
        ({"message": "invalid_request"}, "provider_bad_request"),
        ({"error": "insufficient capacity"}, "provider_capacity"),
        ({"error": "There are no instances currently available"}, "provider_capacity"),
        ({"reason": MARKER}, "provider_reason_unknown"),
        ({"message": "out_of_stock " + MARKER}, "provider_reason_unknown"),
        ({"account": MARKER}, "provider_reason_missing"),
        (None, "provider_reason_missing"),
        ([{"code": "OUT_OF_STOCK"}], "provider_reason_missing"),
        (
            {"code": "OUT_OF_STOCK", "reason": "QUOTA_EXCEEDED"},
            "provider_reason_unknown",
        ),
    ],
)
def test_exact_closed_projection_retains_evidence_limits(payload, reason):
    assert ambiguous_create_reason(payload) == reason


def test_ambiguous_adapter_error_keeps_status_and_cause_without_response_fields():
    payload = {
        "error": {"code": "OUT_OF_STOCK", "message": MARKER},
        "account_id": MARKER,
        "request": {"Authorization": "Bearer " + MARKER},
    }
    provider, calls = adapter(payload)
    with pytest.raises(ComputeError) as refused:
        provider.create(SPEC, ownership_tag="0" * 24)
    error = refused.value
    assert error.http_status == 503
    assert error.provider_reason_code == "provider_capacity"
    assert "provider_capacity" in error.failed
    assert error.execution is Execution.MAY_HAVE_EXECUTED
    assert error.resources_may_remain and not error.retry_safe
    assert "reconcile" in error.next_action
    for output in (str(error), repr(error), json.dumps(error.as_dict())):
        assert MARKER not in output and "account_id" not in output
        assert "Authorization" not in output and "request" not in output
    assert calls == [("POST", "https://rest.runpod.io/v1/pods")]


def test_unrecognized_reason_cannot_be_inferred_from_http_status():
    provider, _calls = adapter({"message": MARKER})
    with pytest.raises(ComputeError) as refused:
        provider.create(SPEC, ownership_tag="0" * 24)
    assert "provider_reason_unknown" in refused.value.failed
    assert "capacity" not in refused.value.failed and MARKER not in str(refused.value)


def test_real_job_receipt_projects_create_cause_and_keeps_uncertainty(lifecycle):
    from carbon.agent_campaign.graphite import pods

    make, go = lifecycle
    spec, backend, account = make()
    real_transport = account.transport
    creates = []

    def transport(method, url, **kwargs):
        if method == "POST" and url == "https://rest.runpod.io/v1/pods":
            creates.append(url)
            return (
                503,
                json.dumps({"error": "OUT_OF_STOCK", "account_id": MARKER}).encode(),
            )
        return real_transport(method, url, **kwargs)

    backend.adapter._transport = transport

    def unresolved(intent_id, private):
        raise pods.PodFailure("recover", "reconcile not complete", executed=True)

    backend.recover = unresolved
    receipt, ledger = go(spec, backend)
    assert "HTTP 503" in receipt["refusal"]
    assert "provider_capacity" in receipt["refusal"]
    assert MARKER not in json.dumps(receipt) and MARKER not in json.dumps(ledger)
    assert receipt["teardown"]["terminated"] is None
    assert ledger[-1]["pending_usd"] == receipt["cost"]["reserved_usd"]
    assert len(creates) == 1  # No retry inferred from a capacity-shaped reason.


@pytest.mark.parametrize("second_status", [503, 400])
def test_both_create_diagnostics_survive_the_one_resend(lifecycle, second_status):
    make, go = lifecycle
    spec, backend, account = make()
    real_transport = account.transport
    creates = []

    def transport(method, url, **kwargs):
        if method == "POST" and url == "https://rest.runpod.io/v1/pods":
            creates.append(url)
            code = "OUT_OF_STOCK" if len(creates) == 1 else "QUOTA_EXCEEDED"
            status = 503 if len(creates) == 1 else second_status
            return status, json.dumps({"code": code, "account_id": MARKER}).encode()
        return real_transport(method, url, **kwargs)

    backend.adapter._transport = transport
    backend.service.resend_gap_s = (
        0  # Fixture only: two empty reconciles still required.
    )
    receipt, ledger = go(spec, backend)
    assert len(creates) == 2
    assert "first create: provider_capacity (HTTP 503)" in receipt["refusal"]
    assert "repeated create: provider_quota" in receipt["refusal"]
    assert f"HTTP {second_status}" in receipt["refusal"]
    assert MARKER not in json.dumps(receipt) and MARKER not in json.dumps(ledger)
    # A definitive second refusal cannot settle uncertainty about the first.
    assert receipt["teardown"]["terminated"] is None
    assert ledger[-1]["pending_usd"] == receipt["cost"]["reserved_usd"]


def test_provider_reason_field_refuses_unregistered_private_text():
    with pytest.raises(ValueError, match="unregistered provider reason"):
        ComputeError(
            operation="provision",
            failed="fixture",
            execution=Execution.MAY_HAVE_EXECUTED,
            resources_may_remain=True,
            retry_safe=False,
            next_action="reconcile",
            provider_reason_code=MARKER,
        )


@pytest.mark.parametrize("status", [503, None])
def test_graphite_launch_preserves_ambiguous_http_evidence(status):
    from decimal import Decimal

    from carbon.agent_campaign.graphite import pods

    def provision(request, **kwargs):
        raise ComputeError(
            operation="provision",
            failed="provider did not return a resource id: provider_capacity",
            execution=Execution.MAY_HAVE_EXECUTED,
            resources_may_remain=True,
            retry_safe=False,
            next_action="reconcile by ownership tag; do not resend",
            http_status=status,
        )

    holder = SimpleNamespace(
        economics={
            "hourly_usd": Decimal("0.5"),
            "gpu": "A40",
            "rate_ceiling_usd_per_hr": Decimal("0.5"),
        },
        _record=lambda job, private: {"deadline_at": 3600.0},
        pod_spec=lambda job, record: SPEC,
        balance_floor=lambda: Decimal(0),
        CAMPAIGN="fixture",
        service=SimpleNamespace(
            observe_balance=lambda campaign: (100.0, 0), provision=provision
        ),
        adapter=SimpleNamespace(
            offers=lambda *args, **kwargs: [
                SimpleNamespace(usd_per_hr=0.4, stock_status="High")
            ]
        ),
        retry_ambiguous_create=False,
    )
    with pytest.raises(pods.PodFailure) as refused:
        pods.RunPodPods.launch(
            holder, SimpleNamespace(minutes=1, intent_id="fixture"), None
        )
    expected = "HTTP unavailable" if status is None else "HTTP 503"
    assert expected in refused.value.detail
    assert "provider_capacity" in refused.value.detail
    assert refused.value.executed is True
