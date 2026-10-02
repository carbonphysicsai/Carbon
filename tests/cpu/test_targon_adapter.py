"""The Targon VM adapter against a fake Targon API and a fake SSH client.

C-MLP-03 slice 4b (OWNER-C-MLP-03-ANSWERS-01). No request reaches Targon and
no SSH connection is made. The fake answers the endpoints the adapter's
allow-list names, with the field names docs.targon.com documents (read
2026-10-02). What is held:
- offers come from the inventory by VM type, within the rate ceiling and only
  when in stock;
- create makes one SSH key for the VM, registers the VM with it, the chosen VM
  image and a sudo password, then deploys it; the private key and password
  stay owner-only on the miner's machine;
- the worker starts over SSH on the VM's loopback, and the job is reached
  through a local port forward (`ssh-tunnel`);
- a VM image without Docker or the NVIDIA Container Toolkit is refused by
  name, and nothing is installed;
- teardown deletes the VM, verifies it, deletes its SSH key, and removes the
  local key material; Targon reports no per-VM charge, so none is invented;
- the allow-list, ownership refusal, and that the token never appears in an
  error.
"""

from __future__ import annotations

import json
import re
import stat
import subprocess

import pytest

from carbon.compute import ComputeService, ComputeStore
from carbon.compute.credentials import Secret
from carbon.compute.errors import ComputeError, Execution
from carbon.compute.model import PodSpec, ProvisionRequest, ResourceState
from carbon.compute.targon import (
    API,
    NO_DOCKER,
    NO_NVIDIA_TOOLKIT,
    TargonAdapter,
    targon_state,
    worker_script,
)

TOKEN = "tgn_fixture-token-never-echoed"
IMAGE = "docker.io/miner/carbon-gpu-worker@sha256:" + "a" * 64
ORG = API + "/orgs/miner-personal"


class Credentials:
    def status(self):
        return "configured"

    def load(self):
        return Secret(TOKEN)


class FakeTargon:
    def __init__(self, *, lose_register=False, deploy_status=200):
        self.inventory = [
            {
                "name": "h100-small",
                "type": "vm",
                "gpu": True,
                "spec": {"gpu_type": "NVIDIA-H100", "gpu_count": 1},
                "cost_per_hour": 3.09,
                "available": 15,
            },
            {
                "name": "h200-small",
                "type": "vm",
                "gpu": True,
                "spec": {"gpu_type": "NVIDIA-H200", "gpu_count": 1},
                "cost_per_hour": 3.59,
                "available": 0,
            },
        ]
        self.keys, self.workloads, self.calls = {}, {}, []
        self.lose_register, self.deploy_status = lose_register, deploy_status

    def __call__(self, method, url, *, body, headers, timeout):
        self.calls.append((method, url))
        payload = json.loads(body) if body else None
        if url == API + "/inventory?type=vm&gpu=true":
            assert "Authorization" not in headers  # a public read
            return 200, json.dumps(self.inventory).encode()
        assert headers["Authorization"] == "Bearer " + TOKEN
        if url == API + "/orgs":
            orgs = [
                {"slug": "a-team", "org_type": "TEAM"},
                {"slug": "miner-personal", "org_type": "PERSONAL"},
            ]
            return 200, json.dumps(orgs).encode()
        if url == ORG + "/credits":
            return 200, json.dumps({"credits": 40.0, "currency": "USD"}).encode()
        if url == ORG + "/workloads/vm-images":
            return 200, json.dumps({"items": [{"name": "ubuntu-docker-gpu"}]}).encode()
        if method == "POST" and url == ORG + "/ssh-keys":
            uid = f"shk-{len(self.keys)}"
            self.keys[uid] = payload
            return 201, json.dumps({"uid": uid, "name": payload["name"]}).encode()
        match = re.fullmatch(re.escape(ORG) + r"/ssh-keys/([\w-]+)", url)
        if method == "DELETE" and match:
            self.keys.pop(match.group(1), None)
            return 204, b""
        if method == "POST" and url == ORG + "/workloads":
            if self.lose_register:
                raise TimeoutError("lost answer; token " + headers["Authorization"])
            uid = f"wrk-{len(self.workloads)}"
            self.workloads[uid] = {
                "uid": uid,
                "name": payload["name"],
                "cost_per_hour": 3.09,
                "request": payload,
                "state": {"status": "registered"},
            }
            return 201, json.dumps(self.workloads[uid]).encode()
        match = re.fullmatch(
            re.escape(ORG) + r"/workloads/([\w-]+)(/deploy|/state)?", url
        )
        if match:
            uid, tail = match.groups()
            if uid not in self.workloads:
                return 404, b'{"error":"not found","reason":"NOT_FOUND"}'
            workload = self.workloads[uid]
            if tail == "/deploy":
                if self.deploy_status != 200:
                    return self.deploy_status, b'{"reason":"INSUFFICIENT_CREDITS"}'
                workload["state"] = {
                    "status": "running",
                    "public_ip": "203.0.113.9",
                    "ssh_port": 30022,
                }
                return 200, json.dumps(workload).encode()
            if tail == "/state":
                return 200, json.dumps(workload["state"]).encode()
            if method == "DELETE":
                del self.workloads[uid]
                return 204, b""
            return 200, json.dumps(workload).encode()
        if method == "GET" and url.startswith(ORG + "/workloads?"):
            return (
                200,
                json.dumps(
                    {"items": list(self.workloads.values()), "next_cursor": None}
                ).encode(),
            )
        return 404, b"{}"


class Process:
    def __init__(self):
        self.closed = False

    def poll(self):
        return 0 if self.closed else None

    def terminate(self):
        self.closed = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.closed = True


class FakeSSH:
    """Records what would run on the VM; the exit status is the fixture's."""

    def __init__(self, code=0):
        self.code, self.scripts, self.forwards = code, [], []

    def run(self, directory, host, port, script, timeout):
        key = directory / "id_ed25519"
        assert stat.S_IMODE(key.stat().st_mode) == 0o600
        assert key.read_bytes().startswith(b"-----BEGIN OPENSSH PRIVATE KEY-----")
        self.scripts.append((host, port, script))
        return self.code

    def forward(self, directory, host, port, local, remote):
        self.forwards.append((host, port, local, remote))
        return Process()


def spec(rate=3.5, sku="h100-small"):
    return PodSpec(
        image=IMAGE,
        gpu_type_id=sku,
        gpu_count=1,
        ports=("8000/http",),
        env=(("CARBON_JOB_TOKEN", "t" * 64), ("JAX_PLATFORMS", "cuda")),
        start_command=("/opt/carbon-worker/bin/python", "-I", "-m", "x"),
        max_rate_usd_per_hr=rate,
        storage_usd_per_gb_month=0.1,
    )


def adapter(tmp_path, fake, ssh=None, vm_image="ubuntu-docker-gpu"):
    return TargonAdapter(
        Credentials(),
        fake,
        state_dir=tmp_path / "vm-keys",
        vm_image=vm_image,
        ssh=ssh or FakeSSH(),
        clock=lambda: 50.0,
        sleep=lambda _: None,
        listening=lambda port: True,
        free_port=lambda: 41000,
    )


def service(tmp_path, fake, ssh=None):
    store = ComputeStore(tmp_path / "compute", clock=lambda: 100.0)
    store.start_campaign("cmp-1")
    targon = adapter(tmp_path, fake, ssh)
    return ComputeService(store, targon, clock=lambda: 100.0), store, targon


def request(rate=3.5, sku="h100-small"):
    return ProvisionRequest("m", "m", "cmp-1", "job-1", spec(rate, sku), 5000.0)


def test_offers_and_balance_on_the_personal_organisation(tmp_path):
    targon = adapter(tmp_path, FakeTargon())
    small, empty = targon.offers(["h100-small", "h200-small"], gpu_count=1)
    assert (small.usd_per_hr, small.stock_status) == (3.09, "15 available")
    assert small.source == "targon.inventory.cost_per_hour"
    assert (empty.usd_per_hr, empty.stock_status) == (3.59, "None")
    (unknown,) = targon.offers(["a100-huge"], gpu_count=1)
    assert unknown.usd_per_hr is None
    balance = targon.read_balance()
    assert (balance.balance_usd, balance.source) == (40.0, "targon.orgs.credits")
    assert targon.vm_images() == ["ubuntu-docker-gpu"]


def test_a_trial_rents_one_vm_runs_the_worker_over_ssh_and_deletes_it(tmp_path):
    fake, ssh = FakeTargon(), FakeSSH()
    svc, store, targon = service(tmp_path, fake, ssh)
    svc.observe_balance("cmp-1")
    record = svc.provision(request())
    intent = store.intent("cmp-1", "job-1")
    name = "carbon-" + intent.ownership_tag
    (key,) = fake.keys.values()
    assert key["name"] == name and key["ssh_key"].startswith("ssh-ed25519 ")
    workload = fake.workloads[record.resource_id]
    sent = workload["request"]
    assert sent["type"] == "VM" and sent["name"] == name
    assert (sent["image"], sent["resource_name"]) == ("ubuntu-docker-gpu", "h100-small")
    assert sent["ssh_keys"] == list(fake.keys)
    # The key and the sudo password stay owner-only on this machine.
    directory = tmp_path / "vm-keys" / name
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    password = (directory / "password").read_text()
    assert sent["vm_config"] == {"password": password}
    assert stat.S_IMODE((directory / "password").stat().st_mode) == 0o600

    owned = svc.owned("cmp-1", "job-1", record.resource_id)
    url = targon.connect_url(owned, 8000)
    assert url == "http://127.0.0.1:41000"
    assert targon.job_transport == "ssh-tunnel"
    ((host, port, script),) = ssh.scripts
    assert (host, port) == ("203.0.113.9", 30022)
    # The worker binds the VM's loopback only; it is reached through SSH.
    assert "-p 127.0.0.1:8000:8000" in script and "--gpus all" in script
    assert "CARBON_JOB_TOKEN=" + "t" * 64 in script
    assert ssh.forwards == [("203.0.113.9", 30022, 41000, 8000)]
    # A second call reuses the open forward; nothing runs twice.
    assert targon.connect_url(owned, 8000) == url and len(ssh.scripts) == 1

    svc.terminate("cmp-1", "job-1", record.resource_id)
    assert fake.workloads == {} and fake.keys == {}
    assert not directory.exists()
    # Targon reports no per-VM charge; none is invented.
    assert targon.provider_charge(owned) is None


@pytest.mark.parametrize(
    "code,cause",
    [
        (NO_DOCKER, "no Docker"),
        (NO_NVIDIA_TOOLKIT, "no NVIDIA Container Toolkit"),
    ],
)
def test_a_vm_image_without_docker_or_the_toolkit_is_refused_by_name(
    tmp_path, code, cause
):
    fake = FakeTargon()
    svc, _, targon = service(tmp_path, fake, FakeSSH(code))
    svc.observe_balance("cmp-1")
    record = svc.provision(request())
    owned = svc.owned("cmp-1", "job-1", record.resource_id)
    with pytest.raises(ComputeError) as refused:
        targon.connect_url(owned, 8000)
    assert cause in refused.value.failed and refused.value.retry_safe is False
    assert "NVIDIA Container Toolkit" in refused.value.next_action


def test_an_ssh_run_that_never_ends_is_typed_not_raised(tmp_path, monkeypatch):
    """A timeout or a missing client is a status the adapter refuses by name,
    so the runner's teardown always runs."""
    from carbon.compute import targon as module

    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired("ssh", 1)

    monkeypatch.setattr(module.subprocess, "run", timed_out)
    assert module.SSH().run(tmp_path, "203.0.113.9", 22, "true", 1) == 124
    svc, _, targon = service(tmp_path, FakeTargon(), FakeSSH(124))
    svc.observe_balance("cmp-1")
    record = svc.provision(request())
    with pytest.raises(ComputeError) as refused:
        targon.connect_url(svc.owned("cmp-1", "job-1", record.resource_id), 8000)
    assert refused.value.retry_safe is False
    assert "time allowed" in refused.value.failed


def test_sshd_not_up_yet_is_retried_not_refused(tmp_path):
    svc, _, targon = service(tmp_path, FakeTargon(), FakeSSH(255))
    svc.observe_balance("cmp-1")
    record = svc.provision(request())
    with pytest.raises(ComputeError) as waiting:
        targon.connect_url(svc.owned("cmp-1", "job-1", record.resource_id), 8000)
    assert waiting.value.retry_safe is True


@pytest.mark.parametrize("rate,sku", [(3.0, "h100-small"), (5.0, "h200-small")])
def test_above_the_ceiling_or_out_of_stock_rents_nothing(tmp_path, rate, sku):
    fake = FakeTargon()
    svc, _, _ = service(tmp_path, fake)
    svc.observe_balance("cmp-1")
    with pytest.raises(ComputeError) as refused:
        svc.provision(request(rate, sku))
    assert refused.value.execution is Execution.NOT_EXECUTED
    assert not any(m == "POST" for m, _ in fake.calls)
    assert not (tmp_path / "vm-keys").exists() or not any(
        (tmp_path / "vm-keys").iterdir()
    )


def test_a_lost_register_answer_is_ambiguous_and_never_echoes_the_token(tmp_path):
    svc, _, _ = service(tmp_path, FakeTargon(lose_register=True))
    svc.observe_balance("cmp-1")
    with pytest.raises(ComputeError) as refused:
        svc.provision(request())
    assert refused.value.execution is Execution.MAY_HAVE_EXECUTED
    assert TOKEN not in str(refused.value) and TOKEN not in repr(refused.value)


def test_a_refused_deploy_removes_the_registration(tmp_path):
    fake = FakeTargon(deploy_status=402)
    svc, _, _ = service(tmp_path, fake)
    svc.observe_balance("cmp-1")
    with pytest.raises(ComputeError) as refused:
        svc.provision(request())
    assert refused.value.execution is Execution.EXECUTED
    assert fake.workloads == {}


def test_requests_outside_the_allow_list_are_refused_before_the_token_is_read(
    tmp_path,
):
    targon = adapter(tmp_path, FakeTargon())
    with pytest.raises(ComputeError, match="allow-list"):
        targon._send("provision", "POST", API + "/orgs/x/tokens", mutating=True)


def test_no_vm_image_rents_nothing(tmp_path):
    fake = FakeTargon()
    targon = adapter(tmp_path, fake, vm_image=None)
    with pytest.raises(ComputeError, match="no Targon VM image"):
        targon.create(spec(), ownership_tag="0" * 24)
    assert fake.calls == []


@pytest.mark.parametrize(
    "status,state",
    [
        ("running", ResourceState.RUNNING),
        ("provisioning", ResourceState.STARTING),
        ("registered", ResourceState.STARTING),
        ("deleted", ResourceState.TERMINATED),
        ("error", ResourceState.UNKNOWN),
    ],
)
def test_targon_states_map_conservatively(status, state):
    assert targon_state(status) is state


def test_the_worker_script_refuses_without_docker_and_installs_nothing(tmp_path):
    """The real script, run by bash with no docker on PATH: exit 90, no file."""
    script = worker_script(spec(), "pw", 8000)
    for forbidden in ("apt", "curl", "install", "wget"):
        assert forbidden not in script
    empty = tmp_path / "bin"
    empty.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    completed = subprocess.run(
        ["/bin/bash", "-s"],
        input=script.encode(),
        env={"PATH": str(empty), "HOME": str(home)},
        capture_output=True,
        check=False,
    )
    assert completed.returncode == NO_DOCKER
    assert list(home.iterdir()) == []


def test_the_worker_script_takes_only_plain_environment_values():
    bad = PodSpec(
        image=IMAGE,
        gpu_type_id="h100-small",
        gpu_count=1,
        env=(("CARBON_JOB_TOKEN", "x; rm -rf ~"),),
        start_command=("/bin/true",),
    )
    with pytest.raises(ValueError, match="not plain"):
        worker_script(bad, "pw", 8000)
