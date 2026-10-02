"""Carbon's fixed practice on a rented GPU: lifecycle, accounting, teardown.

The compute store, the provisioning service with its spend gate, the ledger
and the durable job record are real. The provider is an in-memory fixture and
the pod's job server is a fixture job, so no account is touched. What these
tests hold:
- a balance is observed and recorded before anything is provisioned, and the
  rate ceiling and the miner's budget bind;
- one pod per trial, tagged, from the pinned image with the job server as its
  start command and a per-job token as its only secret;
- the pod is terminated, and verified gone, whether the job succeeded or not;
- the provider's own charge is recorded when it reports one;
- a restart re-derives the same request and never provisions twice.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from carbon.compute import ComputeService, ComputeStore
from carbon.compute.errors import ComputeError, Execution
from carbon.compute.model import ResourceState
from carbon.compute.provider import (
    BalanceObservation,
    CreateResult,
    ListedResource,
    Observation,
    ProviderCharge,
)
from carbon.compute.remote_job import RemoteJobFailure
from carbon.compute.rented_runner import START_COMMAND, RentedCompute, RentedRunner
from carbon.development_session.profile import canonical
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import CampaignLedger

REPOSITORY = Path(__file__).resolve().parents[2]
IMAGE = "docker.io/miner/carbon-gpu-worker@sha256:" + "a" * 64
COMPUTE = RentedCompute(
    provider="fixture-cloud",
    image_ref=IMAGE,
    gpu_type_id="NVIDIA A40",
    max_rate_usd_per_hr=0.5,
    storage_usd_per_gb_month=0.1,
)


class Cloud:
    """An in-memory provider account."""

    name = "fixture-cloud"

    def __init__(self, *, balance=10.0, rate=0.4, charge=0.03):
        self.balance, self.rate, self.charge = balance, rate, charge
        self.pods, self.created, self.calls = {}, [], []

    def offers(self, gpu_type_ids, *, gpu_count, cloud_type):
        return []

    def read_balance(self):
        self.calls.append("balance")
        return BalanceObservation(self.balance, 1.0, "fixture.balance")

    def create(self, spec, *, ownership_tag):
        self.calls.append("create")
        pod = "pod" + str(len(self.created))
        self.created.append((spec, ownership_tag))
        self.pods[pod] = "carbon-" + ownership_tag
        return CreateResult(pod, self.rate)

    def observe(self, resource_id):
        present = resource_id in self.pods
        return Observation(
            resource_id,
            present,
            ResourceState.RUNNING if present else ResourceState.TERMINATED,
            self.pods.get(resource_id),
            self.rate,
            2.0,
        )

    def list_resources(self):
        return [ListedResource(i, n) for i, n in self.pods.items()]

    def stop(self, owned):
        pass

    def terminate(self, owned):
        self.calls.append("terminate")
        self.pods.pop(owned.resource_id, None)
        return True

    def connect_url(self, owned, port):
        return f"https://{owned.resource_id}-{port}.fixture.example"

    def provider_charge(self, owned):
        if self.charge is None:
            return None
        return ProviderCharge(self.charge, "fixture.billing")


class Job:
    """The pod's job server, as a fixture: it runs nothing, it answers."""

    seen: ClassVar[list] = []

    def __init__(self, base, token, *, fail=None, cancelled=None):
        self.base, self.token, self.fail = base, token, fail
        self.cancelled = cancelled
        Job.seen.append(self)

    @staticmethod
    def clock():
        return 0.0

    def run(self, files, *, ready_deadline, run_deadline):
        self.files = files
        if self.fail:
            raise RemoteJobFailure("run", self.fail)
        return (
            {"state": "DONE", "returncode": 0, "elapsed_s": 1.0},
            {"predictions.json": b"{}", "fit.json": b"{}"},
        )


def manifest():
    """A real frozen battery product manifest (the ledger's own fixture)."""
    from test_battery_research_images import IMAGES, IMPLEMENTATION, launch, runtime

    from carbon.battery import campaign as battery

    return battery.manifest_document(
        launch(runtime()),
        owner="miner",
        implementation=IMPLEMENTATION,
        images=list(IMAGES),
    )


def failing(base, token, **kwargs):
    return Job(base, token, fail="http 502", **kwargs)


def setup(tmp_path, *, cloud=None, budget=None, job=Job):
    tmp_path.chmod(0o700)
    cloud = cloud or Cloud()
    store = ComputeStore(tmp_path / "compute", clock=lambda: 100.0)
    store.start_campaign("cmp-1", miner_budget_usd=budget)
    service = ComputeService(store, cloud, clock=lambda: 100.0)
    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(manifest())
    ledger.generation = CampaignControl(ledger).acquire()
    runner = RentedRunner(
        compute=COMPUTE,
        service=service,
        tenant="miner-hotkey",
        miner="miner-hotkey",
        campaign_id="cmp-1",
        clock=lambda: 100.0,
        job=job,
    )
    return runner, ledger, cloud, store


def call(runner, ledger, identity="trial-1"):
    return runner(
        ledger,
        owner="miner",
        identity=identity,
        source="print('practice')",
        files={"recipe.json": canonical({"family": "knn"})},
        image=None,
        seconds=120,
        provenance="BATTERY_PUBLIC_PRACTICE",
        extra_resources={},
    )


def test_a_rented_trial_provisions_runs_and_tears_down_one_tagged_pod(tmp_path):
    runner, ledger, cloud, store = setup(tmp_path)
    result = call(runner, ledger)
    # Balance first, then one create, then a verified terminate.
    assert cloud.calls == ["balance", "create", "terminate"]
    assert cloud.pods == {}
    spec, _ = cloud.created[0]
    assert spec.image == IMAGE and spec.gpu_type_id == "NVIDIA A40"
    assert spec.start_command == START_COMMAND
    env = dict(spec.env)
    assert env["JAX_PLATFORMS"] == "cuda"
    # The only secret on the pod is the per-job token, which opens this job.
    assert set(env) == {
        "CARBON_JOB_TOKEN",
        "CARBON_JOB_PORT",
        "CARBON_JOB_SECONDS",
        "CARBON_JOB_LIFETIME",
        "JAX_PLATFORMS",
    }
    job = Job.seen[-1]
    assert job.token == env["CARBON_JOB_TOKEN"] and len(job.token) == 64
    assert job.base == "https://pod0-8000.fixture.example"
    assert job.files["program.py"] == b"print('practice')"
    rented = result["rented"]
    assert rented["teardown"]["verified"] is True
    assert rented["teardown"]["charge"] == {
        "amount_usd": 0.03,
        "basis": "fixture.billing",
    }
    assert store.provider_charges("fixture-cloud", "pod0") == [0.03]
    snapshot = ledger.root / result["operation"] / "snapshot"
    assert (snapshot / "predictions.json").read_bytes() == b"{}"
    assert result["official_eligible"] is False


def test_the_job_record_is_owner_only_and_fixed_before_provisioning(tmp_path):
    runner, ledger, cloud, _ = setup(tmp_path)
    result = call(runner, ledger)
    record = ledger.root / result["operation"] / "rented-job.json"
    assert record.stat().st_mode & 0o777 == 0o600
    body = json.loads(record.read_bytes())
    assert body["token"] == dict(cloud.created[0][0].env)["CARBON_JOB_TOKEN"]


def test_a_failed_job_still_terminates_its_pod_and_is_infrastructure(tmp_path):
    runner, ledger, cloud, _ = setup(tmp_path, job=failing)
    with pytest.raises(RemoteJobFailure):
        call(runner, ledger)
    assert cloud.pods == {}
    assert cloud.calls[-1] == "terminate"
    with ledger.db() as db:
        state = db.execute("SELECT state FROM operations").fetchone()[0]
    assert state == "FAILED_INFRA"


def test_a_rate_above_the_ceiling_is_terminated_and_refused(tmp_path):
    runner, ledger, cloud, _ = setup(tmp_path, cloud=Cloud(rate=0.9))
    with pytest.raises(ComputeError, match="ceiling"):
        call(runner, ledger)
    assert cloud.pods == {}


def test_spend_beyond_the_balance_or_budget_is_refused_before_any_create(tmp_path):
    for kwargs in ({"cloud": Cloud(balance=0.01)}, {"budget": 0.01}):
        root = tmp_path / str(len(kwargs)) / next(iter(kwargs))
        root.mkdir(parents=True)
        runner, ledger, cloud, _ = setup(root, **kwargs)
        with pytest.raises(ComputeError) as refused:
            call(runner, ledger)
        assert refused.value.execution is Execution.NOT_EXECUTED
        assert "create" not in cloud.calls


def test_a_replayed_trial_returns_its_result_and_provisions_nothing(tmp_path):
    runner, ledger, cloud, _ = setup(tmp_path)
    first = call(runner, ledger)
    again = call(runner, ledger)
    assert again == first
    assert cloud.calls.count("create") == 1


def test_an_unpinned_or_unbounded_rented_choice_is_refused():
    with pytest.raises(ValueError, match="pinned by digest"):
        RentedCompute("x", "docker.io/miner/worker:latest", "A40", 0.5, 0.1)
    with pytest.raises(ValueError, match="rate ceiling"):
        RentedCompute("x", IMAGE, "A40", float("inf"), 0.1)


# --- the battery scope, practice and setup ---------------------------------------


def gpu_worker(tag="9"):
    from test_battery_gpu_practice import gpu_image

    return gpu_image(tag)


def test_the_rented_scope_binds_the_choice_to_the_pinned_gpu_worker():
    from carbon.battery import gpu

    image = gpu_worker()
    runtime = {
        "gpu_research": [gpu.gpu_scope(image)],
        "rented_gpu": [gpu.rented_scope(COMPUTE, image)],
    }
    assert gpu.declared_rented(runtime) == COMPUTE
    scope = runtime["rented_gpu"][0]
    assert (scope["purpose"], scope["score"], scope["official_eligible"]) == (
        "speed_only",
        None,
        False,
    )
    # A rented choice naming another GPU worker than the campaign's is refused,
    # and a rented GPU never runs without the GPU practice scope.
    other = {**runtime, "rented_gpu": [gpu.rented_scope(COMPUTE, gpu_worker("8"))]}
    with pytest.raises(ValueError, match="rented GPU scope"):
        gpu.declared_rented(other)
    with pytest.raises(ValueError, match="GPU practice scope"):
        gpu.declared_rented({"rented_gpu": runtime["rented_gpu"]})


def test_practice_on_a_rented_gpu_records_the_provider_teardown_and_charge(
    tmp_path,
):
    from test_battery_validator_daemon import submission

    from carbon.battery.research import BatteryPractice

    class Practice(Job):
        def run(self, files, *, ready_deadline, run_deadline):
            # Run the real staged program locally, as the pod would.
            import subprocess
            import sys

            work = tmp_path / "pod" / "workspace"
            out = tmp_path / "pod" / "output"
            work.mkdir(parents=True)
            out.mkdir()
            for name, body in files.items():
                if name != "program.py":
                    (work / name).write_bytes(body)
            (tmp_path / "pod" / "program.py").write_bytes(files["program.py"])
            subprocess.run(
                [sys.executable, "-I", str(tmp_path / "pod" / "program.py")],
                cwd=work,
                check=True,
                capture_output=True,
            )
            return (
                {"state": "DONE", "returncode": 0},
                {p.name: p.read_bytes() for p in out.iterdir()},
            )

    runner, ledger, cloud, _ = setup(tmp_path, job=Practice)
    practice = BatteryPractice(
        ledger=ledger,
        owner="miner",
        image=None,
        root=REPOSITORY,
        gpu_image=gpu_worker(),
        rented=runner,
    )
    result = practice("task-rented", submission("hk", "knn", neighbours=8).strategy)
    backend = result["backend"]
    assert backend["kind"] == "RENTED_GPU"
    assert backend["provider"] == "fixture-cloud"
    assert backend["image_ref"] == IMAGE
    assert backend["teardown_verified"] is True
    assert backend["provider_charge"] == {
        "amount_usd": 0.03,
        "basis": "fixture.billing",
    }
    assert backend["purpose"] == "speed_only"
    assert "default_backend" in backend["observed"]
    assert cloud.pods == {}
    assert result["summary"] and result["official_eligible"] is False


def test_rented_practice_needs_the_pinned_gpu_worker(tmp_path):
    from carbon.battery.research import BatteryPractice

    runner, ledger, _, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="pinned GPU worker"):
        BatteryPractice(
            ledger=ledger, owner="miner", image=None, root=REPOSITORY, rented=runner
        )


def rented_setup(tmp_path):
    from test_battery_gpu_practice import GpuChecks, gpu_setup

    from carbon.battery import gpu

    class Checks(GpuChecks):
        def rented(self, rented, credential, manifest):
            self.calls.append(("rented", rented["provider"], credential.name))
            assert credential.read_text() == "rk-fixture-compute-key"
            image = gpu_worker()
            return {
                "scope": gpu.rented_scope(COMPUTE, image),
                "gpu_scope": gpu.gpu_scope(image),
                "balance_usd": 12.5,
                "balance_source": "fixture.balance",
                "offer_usd_per_hr": 0.44,
                "offer_source": "fixture.offers",
                "stock": "High",
            }

    setup, _, home, paths = gpu_setup(tmp_path)
    setup.checks = Checks(gpu_worker())
    return setup, home, paths


RENTED_CHOICE = {
    "provider": "runpod",
    "image_ref": IMAGE,
    "gpu_type_id": "NVIDIA A40",
    "max_rate_usd_per_hr": 0.5,
    "storage_usd_per_gb_month": 0.1,
    "cloud_type": "SECURE",
}


def test_setup_with_a_rented_gpu_writes_a_launchable_profile(tmp_path):
    from scripts.dev.miner_launchpad import runner
    from scripts.dev.miner_launchpad.environment_setup import AUTONOMOUS, RENTED_GPU

    setup, home, paths = rented_setup(tmp_path)
    state = setup.compute(
        {
            "choice": RENTED_GPU,
            **paths,
            "gpu_image_manifest": str(home / "gpu.json"),
            "rented": RENTED_CHOICE,
            "key": "rk-fixture-compute-key",
        }
    )
    check = state["steps"]["compute"]["check"]
    assert (check["provider"], check["offer_usd_per_hr"], check["balance_usd"]) == (
        "runpod",
        0.44,
        12.5,
    )
    assert "speed only" in check["note"]
    assert "rk-fixture" not in json.dumps(state)
    setup.agent({"choice": AUTONOMOUS, "operator_config": str(home / "operator.json")})
    setup.review({"confirm": True})
    cfg = runner.validated_profile(json.loads(setup.profile_path.read_bytes()))
    assert cfg["runtime"]["rented_gpu"][0]["image_ref"] == IMAGE
    key = Path(cfg["paths"]["compute_credential"])
    assert key.stat().st_mode & 0o777 == 0o600
    assert "rk-fixture" not in setup.profile_path.read_text()


def test_the_rented_choice_is_closed_and_needs_its_key(tmp_path):
    from scripts.dev.miner_launchpad.environment_setup import (
        LOCAL_CPU,
        RENTED_GPU,
        SetupRefused,
    )

    setup, home, paths = rented_setup(tmp_path)
    base = {"choice": RENTED_GPU, **paths, "gpu_image_manifest": str(home / "gpu.json")}
    for value, field in (
        (base, "rented"),
        ({**base, "rented": {**RENTED_CHOICE, "extra": 1}}, "rented"),
        ({**base, "rented": {**RENTED_CHOICE, "provider": "elsewhere"}}, "provider"),
        ({**base, "rented": RENTED_CHOICE}, "key"),
        ({"choice": LOCAL_CPU, **paths, "rented": RENTED_CHOICE}, "rented"),
    ):
        with pytest.raises(SetupRefused) as refused:
            setup.compute(value)
        assert refused.value.field == field, value
