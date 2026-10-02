"""The Lium adapter against a fake Lium API (shapes read 2026-10-02).

No request reaches Lium. The fake answers the endpoints the adapter's
allow-list names, with the field names Lium's OpenAPI documents. What is held:
offers and the rate ceiling, the two-call create with the image by digest and
an idempotency key, the job port reached on the node's IP over plain HTTP,
verified deletion, the ledger's own charge, the allow-list, and that the key
never appears in an error.
"""

from __future__ import annotations

import json
import re

import pytest

from carbon.compute import ComputeService, ComputeStore
from carbon.compute.credentials import Secret
from carbon.compute.errors import ComputeError, Execution
from carbon.compute.lium import API, LiumAdapter, lium_state
from carbon.compute.model import PodSpec, ProvisionRequest, ResourceState

KEY = "lium-fixture-key-never-echoed"
IMAGE = "docker.io/miner/carbon-gpu-worker@sha256:" + "a" * 64


class Credentials:
    def status(self):
        return "configured"

    def load(self):
        return Secret(KEY)


class FakeLium:
    def __init__(self, *, fail_rent=False):
        self.executors = [
            {
                "id": "exec-cheap",
                "price_per_gpu": 0.4,
                "available_gpu_count": 1,
                "min_gpu_count_for_rental": 1,
            },
            {
                "id": "exec-dear",
                "price_per_gpu": 0.9,
                "available_gpu_count": 2,
                "min_gpu_count_for_rental": 1,
            },
        ]
        self.pods, self.templates, self.calls = {}, {}, []
        self.fail_rent = fail_rent

    def __call__(self, method, url, *, body, headers, timeout):
        assert headers["X-API-Key"] == KEY
        self.calls.append((method, url, headers.get("Idempotency-Key")))
        payload = json.loads(body) if body else None
        if method == "GET" and url.startswith(API + "/executors?"):
            return 200, json.dumps(self.executors).encode()
        if method == "GET" and url == API + "/users/me":
            return 200, json.dumps({"balance": 25.0}).encode()
        if method == "POST" and url == API + "/templates":
            template = "tpl-" + str(len(self.templates))
            self.templates[template] = payload
            return 201, json.dumps({"id": template}).encode()
        match = re.fullmatch(re.escape(API) + r"/executors/([\w-]+)/rent", url)
        if method == "POST" and match:
            if self.fail_rent:
                raise TimeoutError("lost answer; key " + headers["X-API-Key"])
            pod = "pod-" + str(len(self.pods))
            self.pods[pod] = {
                "id": pod,
                "pod_name": payload["pod_name"],
                "status": "RUNNING",
                "price": 0.4,
                "ports_mapping": {"8000": 40123},
                "executor": {"executor_ip_address": "203.0.113.7"},
                "template": payload["template_id"],
                "executor_id": match.group(1),
            }
            return 200, json.dumps({"id": pod}).encode()
        if method == "GET" and url == API + "/pods":
            return 200, json.dumps(list(self.pods.values())).encode()
        match = re.fullmatch(re.escape(API) + r"/pods/([\w-]+)(/statement)?", url)
        if match:
            pod, statement = match.groups()
            if statement:
                return 200, json.dumps({"pod_id": pod, "total": 0.07}).encode()
            if pod not in self.pods:
                return 404, b'{"detail":"Pod not found"}'
            if method == "DELETE":
                del self.pods[pod]
                return 204, b""
            return 200, json.dumps(self.pods[pod]).encode()
        return 404, b"{}"


def spec(rate=0.5):
    return PodSpec(
        image=IMAGE,
        gpu_type_id="NVIDIA A40",
        gpu_count=1,
        ports=("8000/http",),
        env=(("CARBON_JOB_TOKEN", "t" * 64),),
        start_command=("/opt/carbon-worker/bin/python", "-I", "-m", "x"),
        max_rate_usd_per_hr=rate,
        storage_usd_per_gb_month=0.1,
    )


def service(tmp_path, fake):
    store = ComputeStore(tmp_path / "compute", clock=lambda: 100.0)
    store.start_campaign("cmp-1")
    adapter = LiumAdapter(Credentials(), fake, clock=lambda: 50.0, sleep=lambda _: None)
    return ComputeService(store, adapter, clock=lambda: 100.0), store, adapter


def request(rate=0.5):
    return ProvisionRequest("m", "m", "cmp-1", "job-1", spec(rate), 5000.0)


def test_offers_are_the_cheapest_node_for_the_gpu():
    adapter = LiumAdapter(Credentials(), FakeLium(), clock=lambda: 1.0)
    (offer,) = adapter.offers(["NVIDIA A40"], gpu_count=1)
    assert (offer.usd_per_hr, offer.source) == (0.4, "lium.executors.price_per_gpu")
    assert adapter.read_balance().balance_usd == 25.0


def test_create_rents_the_cheapest_node_with_a_one_time_template(tmp_path):
    fake = FakeLium()
    svc, store, adapter = service(tmp_path, fake)
    svc.observe_balance("cmp-1")
    record = svc.provision(request())
    (template,) = fake.templates.values()
    assert template["docker_image"] == "docker.io/miner/carbon-gpu-worker"
    assert template["docker_image_digest"] == "sha256:" + "a" * 64
    assert template["entrypoint"] == "/opt/carbon-worker/bin/python -I -m x"
    assert template["internal_ports"] == [8000]
    assert template["one_time_template"] is True
    assert template["environment"]["CARBON_JOB_TOKEN"] == "t" * 64
    rent = next(c for c in fake.calls if c[1].endswith("/rent"))
    assert rent[1] == API + "/executors/exec-cheap/rent"
    intent = store.intent("cmp-1", "job-1")
    assert rent[2] == intent.ownership_tag  # the idempotency key
    pod = fake.pods[record.resource_id]
    assert pod["pod_name"] == "carbon-" + intent.ownership_tag
    owned = svc.owned("cmp-1", "job-1", record.resource_id)
    # Lium documents no HTTPS proxy: the node's IP, plain HTTP, said so.
    assert adapter.connect_url(owned, 8000) == "http://203.0.113.7:40123"
    assert adapter.job_transport == "http-direct"
    svc.terminate("cmp-1", "job-1", record.resource_id)
    assert fake.pods == {}
    charge = adapter.provider_charge(owned)
    assert charge.amount_usd == 0.07 and charge.basis.startswith("lium.pods.statement")


def test_no_node_within_the_ceiling_refuses_before_any_rent(tmp_path):
    fake = FakeLium()
    svc, _, _ = service(tmp_path, fake)
    svc.observe_balance("cmp-1")
    with pytest.raises(ComputeError) as refused:
        svc.provision(request(rate=0.3))
    assert refused.value.execution is Execution.NOT_EXECUTED
    assert not any(c[1].endswith("/rent") for c in fake.calls)


def test_a_lost_rent_answer_is_ambiguous_and_never_echoes_the_key(tmp_path):
    fake = FakeLium(fail_rent=True)
    svc, _, _ = service(tmp_path, fake)
    svc.observe_balance("cmp-1")
    with pytest.raises(ComputeError) as refused:
        svc.provision(request())
    assert refused.value.execution is Execution.MAY_HAVE_EXECUTED
    assert KEY not in str(refused.value) and KEY not in repr(refused.value)


def test_requests_outside_the_allow_list_are_refused_before_the_key_is_read():
    adapter = LiumAdapter(Credentials(), FakeLium())
    with pytest.raises(ComputeError, match="allow-list"):
        adapter._send("provision", "POST", API + "/docker-credentials/", mutating=True)


@pytest.mark.parametrize(
    "status,state",
    [
        ("RUNNING", ResourceState.RUNNING),
        ("PENDING", ResourceState.STARTING),
        ("STOPPED", ResourceState.STOPPED),
        ("DELETING", ResourceState.TERMINATING),
        ("BROKEN", ResourceState.UNKNOWN),
    ],
)
def test_lium_states_map_conservatively(status, state):
    assert lium_state(status) is state
