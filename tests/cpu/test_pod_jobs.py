"""The shared pod launcher (CLOUD-FIRST-COMPUTE-01), with RunPod in memory only."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign import grant_runs, pod_job_phase, pod_jobs
from carbon.agent_campaign.graphite import pods

REPOSITORY = Path(__file__).resolve().parents[2]
HEAD = subprocess.run(
    ["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()


def enable(key, roots=()):
    """The owner's switch beside a test key file."""
    (Path(key).parent / pod_jobs.ENABLE_FILE).write_text(
        json.dumps({"enabled": True, "upload_roots": [str(r) for r in roots]})
    )


def spec_document(**changes):
    document = {
        "schema": pod_jobs.SPEC_SCHEMA,
        "job_id": "pod-job-test",
        "code_ref": HEAD,
        "module": "scripts.dev.exam_design.runner",
        "args": ["value_panel", "--out", "{out}"],
        "inputs": ["docs/development/evidence/public-dev-decisions-01/ship-files.json"],
        "image": "study",
        "overlays": {},
        "compute": {"kind": "cpu", "flavor": "cpu5c", "vcpus": 8},
        "minutes": 30,
        "rate_ceiling_usd_per_hr": "0.50",
        "cap_usd": "1.00",
        "disk_gb": 20,
        "uploads": {},
        "collect": [],
    }
    document.update(changes)
    return document


def test_a_valid_spec_loads_with_its_worst_case_under_its_cap():
    spec = pod_jobs.load_spec(spec_document())
    money = spec.economics()
    assert money["worst_case_usd"] <= money["cap_usd"] == Decimal("1.00")
    assert spec.digest().startswith("sha256:")


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"extra": 1}, "spec_fields"),
        ({"code_ref": "main"}, "spec_code_ref"),
        ({"module": "os.system"}, "spec_module"),
        ({"args": ["{secret}"]}, "spec_args"),
        ({"inputs": ["../outside"]}, "spec_inputs"),
        ({"inputs": ["/etc/passwd"]}, "spec_inputs"),
        ({"image": "latest"}, "spec_image"),
        ({"compute": {"kind": "cpu", "flavor": "cpu9x", "vcpus": 8}}, "spec_compute"),
        ({"compute": {"kind": "tpu"}}, "spec_compute"),
        ({"image": "pytorch"}, "spec_compute"),
        ({"minutes": 0}, "spec_minutes"),
        ({"cap_usd": "51"}, "per_run_cap_exceeded"),
        ({"cap_usd": "0.10"}, "spec_cap_below_worst_case"),
        ({"rate_ceiling_usd_per_hr": "-1"}, "spec_rate_ceiling"),
        ({"args": ["{inputs}/x"]}, "spec_uploads"),
        ({"collect": ["results"]}, "spec_uploads"),
        ({"uploads": {"a": {"sha256": "0" * 64, "bytes": -1}}}, "spec_uploads"),
        ({"uploads": {"../a": {"sha256": "0" * 64, "bytes": 1}}}, "spec_uploads"),
    ],
)
def test_a_spec_outside_the_contract_is_refused_with_a_typed_code(changes, code):
    document = spec_document()
    if "extra" in changes:
        document["extra"] = 1
    else:
        document.update(changes)
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.load_spec(document)
    assert refused.value.code == code


def test_an_input_the_ship_guard_refuses_refuses_the_job(monkeypatch):
    spec = pod_jobs.load_spec(spec_document(inputs=["docs/x"]))
    monkeypatch.setattr(
        pods, "tracked", lambda ref, prefixes, repository: ["docs/x/private/a.json"]
    )
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.ship_list(spec, REPOSITORY)
    assert refused.value.code == "spec_input_not_shippable"


def test_the_ship_list_holds_the_module_closure_and_the_inputs():
    spec = pod_jobs.load_spec(spec_document())
    ships = pod_jobs.ship_list(spec, REPOSITORY)
    assert "scripts/dev/exam_design/runner.py" in ships
    assert spec.document["inputs"][0] in ships
    assert all(pods.shippable(path) for path in ships)


def _ledger(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x]


def test_check_runs_the_real_lifecycle_with_no_network_and_no_spend(tmp_path):
    spec = pod_jobs.load_spec(spec_document())
    files = {"job.json": b'{"exit": 0}', "result/values.json": b"[1, 2, 3]"}
    report = pod_jobs.check(
        spec, tmp_path / "check", repository=REPOSITORY, files=files
    )
    receipt = report["receipt"]
    assert receipt["schema"] == pod_jobs.RECEIPT_SCHEMA
    assert receipt["outcome"] == "done" and receipt["ok"] is True
    assert receipt["files"] == {
        path: {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
        for path, body in files.items()
    }
    kept = tmp_path / "check" / "out" / "files" / "result" / "values.json"
    assert kept.read_bytes() == b"[1, 2, 3]"
    assert receipt["teardown"]["terminated"] is True
    assert report["creates"] == [receipt["pod_id"]] and report["pods_left"] == []
    # The real ledger: claimed at the job's cap before any provider call, then
    # settled at the provider's charge.
    entry = grant_runs.entry_id(grant_runs.POD_JOB_STORE, "pod-job-test")
    claim, settle = report["ledger"]
    assert claim["entry"] == entry and claim["cost_usd"] == "1.00"
    assert settle == {"settle": entry, "cost_usd": "0.07", "pending_usd": "0"}
    assert receipt["cost"]["charged_usd"] == "0.07"
    written = json.loads((tmp_path / "check" / "out" / "receipt.json").read_text())
    assert written == json.loads(json.dumps(receipt))


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    """A JobPods over an in-memory RunPod and the real ledger in tmp_path."""
    monkeypatch.setenv(grant_runs.ENV, str(tmp_path / "ledger"))
    key = tmp_path / "key"
    key.write_text(pods.CHECK_KEY + "\n")
    key.chmod(0o600)
    enable(key)

    def make(account=None, **changes):
        account = account or pods.InMemoryRunPod()
        spec = pod_jobs.load_spec(spec_document())
        backend = pod_jobs.JobPods(
            spec,
            root=tmp_path / "pods",
            key_file=key,
            repository=REPOSITORY,
            transport=account.transport,
            http=account.http,
            sleep=lambda _s: None,
            balance_floor=lambda: Decimal(0),
        )
        for name, value in changes.items():
            setattr(backend, name, value)
        return spec, backend, account

    def go(spec, backend):
        receipt = pod_jobs.run(spec, tmp_path / "out", backend=backend)
        on_disk = json.loads((tmp_path / "out" / "receipt.json").read_text())
        assert on_disk == json.loads(json.dumps(receipt))
        weekly = tmp_path / "ledger" / grant_runs.WEEKLY_FILE
        return receipt, _ledger(weekly)

    return make, go


def test_a_launch_refused_before_any_create_settles_at_zero(lifecycle):
    make, go = lifecycle
    spec, backend, account = make(pods.InMemoryRunPod(balance=5.0))
    backend.balance_floor = lambda: Decimal(10)
    receipt, ledger = go(spec, backend)
    assert receipt["outcome"].startswith("launch_refused:") and not receipt["ok"]
    assert account.creates == [] and receipt["pod_id"] is None
    assert ledger[-1]["cost_usd"] == "0" and ledger[-1]["pending_usd"] == "0"
    assert receipt["teardown"]["terminated"] is True


def test_an_unreported_charge_stays_at_the_full_reservation(lifecycle):
    make, go = lifecycle
    spec, backend, _account = make(pods.InMemoryRunPod(charge=None))
    receipt, ledger = go(spec, backend)
    reserved = receipt["cost"]["reserved_usd"]
    assert receipt["ok"] is True and receipt["cost"]["charged_usd"] == "0"
    assert ledger[-1]["cost_usd"] == reserved == ledger[-1]["pending_usd"]


def test_an_unconfirmed_teardown_is_a_failed_run_at_the_full_reservation(lifecycle):
    make, go = lifecycle
    spec, backend, _account = make()
    backend.terminate = lambda handle: False
    receipt, ledger = go(spec, backend)
    assert receipt["teardown"]["terminated"] is False and not receipt["ok"]
    assert "reconcile" in receipt
    assert ledger[-1]["pending_usd"] == receipt["cost"]["reserved_usd"]


def test_an_error_after_the_create_still_tears_down_and_writes_the_receipt(lifecycle):
    make, go = lifecycle
    spec, backend, account = make()

    def broken(handle, **kwargs):
        raise RuntimeError("status read failed")

    backend.wait = broken
    receipt, ledger = go(spec, backend)
    assert receipt["outcome"] == "error" and not receipt["ok"]
    assert receipt["errors"][0]["stage"] == "run"
    assert receipt["teardown"]["terminated"] is True and account.pods == {}
    assert ledger[-1]["settle"]


def test_a_create_that_cannot_be_recovered_is_never_called_terminated(lifecycle):
    make, go = lifecycle
    spec, backend, _account = make()

    def launched_then_lost(private):
        raise pods.PodFailure("launch", "create response lost", executed=True)

    def recover(intent_id, private):
        raise pods.PodFailure("recover", "cannot say yet", executed=True)

    backend.launch_job, backend.recover = launched_then_lost, recover
    receipt, ledger = go(spec, backend)
    assert receipt["teardown"]["terminated"] is None and not receipt["ok"]
    assert "reconcile" in receipt
    assert ledger[-1]["pending_usd"] == receipt["cost"]["reserved_usd"]


def test_duplicates_of_an_ambiguous_create_are_terminated_and_counted(lifecycle):
    make, go = lifecycle
    spec, backend, _account = make()
    killed = []
    real_terminate = backend.terminate

    def terminate(handle):
        killed.append(handle.pod_id)
        return True if handle.pod_id == "dup0001" else real_terminate(handle)

    backend.terminate = terminate
    backend.duplicates = lambda intent_id: [{"pod_id": "dup0001", "charge_usd": None}]
    receipt, ledger = go(spec, backend)
    reserved = Decimal(receipt["cost"]["reserved_usd"])
    assert "dup0001" in killed and receipt["ok"] is True
    assert receipt["duplicates"] == [
        {"pod_id": "dup0001", "charge_usd": None, "terminated": True}
    ]
    assert Decimal(ledger[-1]["pending_usd"]) == reserved
    assert Decimal(ledger[-1]["cost_usd"]) == reserved + Decimal("0.07")


def test_the_real_ledger_refuses_past_the_weekly_cap(tmp_path, monkeypatch):
    monkeypatch.setenv(grant_runs.ENV, str(tmp_path / "ledger"))
    # USD 300 a week less the CONFIRM-02 reserve: five USD 50 jobs, not six.
    for index in range(5):
        grant_runs.claim_pod_job(f"job-{index}", Decimal(50))
    with pytest.raises(grant_runs.SharedRunsError) as refused:
        grant_runs.claim_pod_job("job-5", Decimal(50))
    assert refused.value.code == grant_runs.WEEKLY_LIMIT


def test_run_spends_only_with_the_owners_enabling_file(tmp_path):
    key = tmp_path / "keys" / "api_key"
    key.parent.mkdir()
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.require_enabled(key)
    assert refused.value.code == "pod_jobs_not_enabled"
    enable = key.parent / pod_jobs.ENABLE_FILE
    for document in (
        {"enabled": False, "upload_roots": []},
        {"enabled": True, "upload_roots": ["relative"]},
        {"enabled": True, "upload_roots": [str(tmp_path / "shared" / "evidence")]},
    ):
        enable.write_text(json.dumps(document))
        with pytest.raises(pod_jobs.SpecRefused):
            pod_jobs.require_enabled(key)
    enable.write_text(json.dumps({"enabled": True, "upload_roots": [str(tmp_path)]}))
    assert pod_jobs.require_enabled(key) == [str(tmp_path)]
    # A home-relative root is expanded, never kept as a literal "~" directory.
    enable.write_text(json.dumps({"enabled": True, "upload_roots": ["~/pod-uploads"]}))
    assert pod_jobs.require_enabled(key) == [str(Path("~/pod-uploads").expanduser())]


def test_uploads_come_only_from_an_allowed_public_root(tmp_path):
    public = tmp_path / "public" / "job"
    public.mkdir(parents=True)
    (public / "a.json").write_text("{}")
    spec = pod_jobs.load_spec(spec_document(uploads=pod_jobs.uploads_manifest(public)))
    assert pod_jobs.read_uploads(spec, public, [str(tmp_path / "public")])
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.read_uploads(spec, public, [str(tmp_path / "elsewhere")])
    assert refused.value.code == "uploads_root_not_allowed"
    sealed = tmp_path / "shared" / "evidence" / "job"
    sealed.mkdir(parents=True)
    (sealed / "a.json").write_text("{}")
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.read_uploads(spec, sealed, [str(tmp_path)])
    assert refused.value.code == "uploads_sealed_path"
    linked = tmp_path / "public" / "linked"
    linked.mkdir()
    try:
        (linked / "a.json").symlink_to(public / "a.json")
    except OSError:
        pytest.skip("this host cannot make symbolic links")
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.read_uploads(spec, linked, [str(tmp_path / "public")])
    assert refused.value.code == "uploads_symlink"


@pytest.mark.parametrize(
    "name",
    [
        "a b.json",
        "caf\u00e9.json",
        "x%2e.json",
        "ev4/a.json",
        "private/a.json",
    ],
)
def test_an_upload_name_that_needs_encoding_or_is_forbidden_is_refused(name):
    entry = {"sha256": "0" * 64, "bytes": 1}
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.load_spec(spec_document(uploads={name: entry}))
    assert refused.value.code == "spec_uploads"


def test_the_create_request_pins_image_cpu_placement_phase_and_deadline(tmp_path):
    spec = pod_jobs.load_spec(spec_document())
    key = tmp_path / "key"
    key.write_text(pods.CHECK_KEY + "\n")
    key.chmod(0o600)
    enable(key)
    account = pods.InMemoryRunPod()
    backend = pod_jobs.JobPods(
        spec,
        root=tmp_path / "pods",
        key_file=key,
        repository=REPOSITORY,
        transport=account.transport,
        http=account.http,
        clock=lambda: 1_000_000.0,
    )
    record = backend.record(tmp_path)
    request = backend.job_spec(record)
    body = backend.adapter.create_body(request, "0" * 24)
    env = body["env"]
    assert body["computeType"] == "CPU" and body["vcpuCount"] == 8
    assert body["cpuFlavorIds"] == ["cpu5c"] and "gpuTypeIds" not in body
    # The tagged form of the one pinned study digest (RunPod needs the tag).
    assert body["imageName"] == pod_jobs.STUDY_IMAGE
    assert body["imageName"].split("@")[1] == pods.pod_image("jax").split("@")[1]
    assert env["PHASE_MODULE"] == pod_jobs.PHASE_MODULE
    assert json.loads(env["JOB_CONFIG"])["module"] == "scripts.dev.exam_design.runner"
    assert int(env["PROBE_DEADLINE"]) == 1_000_000 + 35 * 60
    assert env["CODE_REF"] == HEAD and env["JAX_PLATFORMS"] == "cpu"
    # The same job re-derives the same record (a restart sends the same create).
    assert backend.record(tmp_path) == record
    other = copy.deepcopy(spec.document)
    other["minutes"] = 31
    clash = pod_jobs.JobPods(
        pod_jobs.load_spec(other),
        root=tmp_path / "pods2",
        key_file=key,
        repository=REPOSITORY,
        transport=account.transport,
        http=account.http,
    )
    with pytest.raises(pods.PodFailure, match="conflict"):
        clash.record(tmp_path)


def test_the_phase_runs_only_the_named_module_with_its_placeholders(tmp_path):
    out = tmp_path / "out"
    argv = pod_job_phase.command(
        {"module": "scripts.dev.x", "args": ["--out", "{out}/a", "{root}"]},
        out,
        tmp_path,
    )
    assert argv == [
        sys.executable,
        "-m",
        "scripts.dev.x",
        "--out",
        f"{out}/a",
        str(tmp_path),
    ]
    for bad in ({"module": "os", "args": []}, {"module": "carbon.x", "args": "a"}):
        with pytest.raises(SystemExit):
            pod_job_phase.command(bad, out, tmp_path)


def test_the_phase_records_the_jobs_exit(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(REPOSITORY)
    monkeypatch.setenv(
        "JOB_CONFIG",
        json.dumps({"module": "carbon.agent_campaign.pod_jobs", "args": ["--help"]}),
    )
    assert pod_job_phase.main(["pod-job-test", "--out", str(out)]) == 0
    job = json.loads((out / "job.json").read_text())
    assert job["exit"] == 0 and job["command"][:2] == [
        "-m",
        "carbon.agent_campaign.pod_jobs",
    ]
    assert b"usage" in (out / "job.log").read_bytes()


def test_uploads_are_sent_once_the_pod_waits_and_checked_by_digest(tmp_path):
    uploads = tmp_path / "uploads"
    (uploads / "work").mkdir(parents=True)
    (uploads / "work" / "records.jsonl").write_bytes(b'{"case_id": "a"}\n')
    (uploads / "contract.json").write_bytes(b"{}")
    spec = pod_jobs.load_spec(
        spec_document(
            args=["--work", "{inputs}/work"],
            uploads=pod_jobs.uploads_manifest(uploads),
            collect=["work/experiment/results"],
        )
    )
    report = pod_jobs.check(
        spec, tmp_path / "check", repository=REPOSITORY, uploads=uploads
    )
    assert report["received"] == ["contract.json", "work/records.jsonl"]
    assert report["receipt"]["outcome"] == "done"
    assert set(report["receipt"]["uploads"]) == {"contract.json", "work/records.jsonl"}
    env = json.loads(json.dumps(spec.document))
    assert env["collect"] == ["work/experiment/results"]


def test_a_local_directory_that_differs_from_the_declared_uploads_is_refused(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "a.json").write_bytes(b"1")
    spec = pod_jobs.load_spec(spec_document(uploads=pod_jobs.uploads_manifest(uploads)))
    (uploads / "a.json").write_bytes(b"2")
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.read_uploads(spec, uploads, [str(tmp_path)])
    assert refused.value.code == "uploads_differ"
    with pytest.raises(pod_jobs.SpecRefused):
        pod_jobs.read_uploads(spec, None, [str(tmp_path)])
    with pytest.raises(pod_jobs.SpecRefused):
        pod_jobs.read_uploads(pod_jobs.load_spec(spec_document()), uploads, [])


def test_the_bootstrap_accepts_only_declared_inputs_at_their_digest(
    tmp_path, monkeypatch
):
    import base64
    import gzip
    import http.server
    import importlib.util
    import threading
    import urllib.error
    import urllib.request

    body = b"declared bytes"
    declared = {
        "work/a.json": {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    }
    monkeypatch.setenv("PROBE_TOKEN", "tok-123")
    monkeypatch.setenv("INPUT_DIR", str(tmp_path / "inputs"))
    monkeypatch.setenv(
        "INPUTS_MANIFEST_GZ_B64",
        base64.b64encode(gzip.compress(json.dumps(declared).encode())).decode(),
    )
    spec = importlib.util.spec_from_file_location(
        "pod_jobs_bootstrap_under_test",
        REPOSITORY / "scripts/dev/exam_design/runpod/bootstrap.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = http.server.HTTPServer(("127.0.0.1", 0), module.H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def post(path, token, data):
        request = urllib.request.Request(
            base + path, data=data, method="POST", headers={"X-Probe-Token": token}
        )
        try:
            return urllib.request.urlopen(request, timeout=10).status
        except urllib.error.HTTPError as refused:
            return refused.code

    try:
        assert post("/input/work/a.json", "wrong", body) == 404
        assert post("/input/work/other.json", "tok-123", body) == 404
        assert post("/input/work/a.json", "tok-123", b"declared bytez") == 409
        # Larger than any declared input: refused unread, the connection closed.
        assert post("/input/work/a.json", "tok-123", body + b"!") == 404
        assert not (tmp_path / "inputs" / "work" / "a.json").exists()
        assert module.RECEIVED == set()
        assert post("/input/work/a.json", "tok-123", body) == 200
        assert (tmp_path / "inputs" / "work" / "a.json").read_bytes() == body
        assert module.RECEIVED == {"work/a.json"}
        assert post("/go", "tok-123", b"") == 200
    finally:
        server.shutdown()


def test_the_phase_collects_declared_paths_from_the_inputs(tmp_path):
    inputs = tmp_path / "inputs"
    (inputs / "work" / "results").mkdir(parents=True)
    (inputs / "work" / "results" / "results.json").write_text("{}")
    out = tmp_path / "out"
    collected = pod_job_phase.collect(
        ["work/results", "work/missing", "../escape"], inputs, out / "collected"
    )
    assert collected["missing"] == ["work/missing", "../escape"]
    assert (out / "collected" / "work" / "results" / "results.json").read_text() == "{}"
    with pytest.raises(SystemExit):
        pod_job_phase.command(
            {"module": "scripts.x", "args": ["{inputs}"]}, out, tmp_path
        )


def test_the_pod_stops_waiting_for_inputs_at_its_deadline(tmp_path, monkeypatch):
    import base64
    import gzip
    import importlib.util

    declared = {"a.json": {"sha256": "0" * 64, "bytes": 1}}
    monkeypatch.setenv("PROBE_DEADLINE", "1")
    monkeypatch.setenv("INPUT_DIR", str(tmp_path / "inputs"))
    monkeypatch.setenv(
        "INPUTS_MANIFEST_GZ_B64",
        base64.b64encode(gzip.compress(json.dumps(declared).encode())).decode(),
    )
    spec = importlib.util.spec_from_file_location(
        "pod_jobs_bootstrap_deadline",
        REPOSITORY / "scripts/dev/exam_design/runpod/bootstrap.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match="inputs incomplete"):
        module.wait_for_inputs()


def test_run_refuses_without_the_pod_job_grant_kind(tmp_path):
    spec = pod_jobs.load_spec(spec_document())
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.run(spec, tmp_path / "out", backend=None, ledger=object())
    assert refused.value.code == "pod_job_grant_unavailable"
    assert not (tmp_path / "out").exists()


def test_no_backend_exists_without_the_owners_switch(tmp_path):
    key = tmp_path / "key"
    key.write_text(pods.CHECK_KEY + "\n")
    key.chmod(0o600)
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.JobPods(
            pod_jobs.load_spec(spec_document()),
            root=tmp_path / "pods",
            key_file=key,
            repository=REPOSITORY,
        )
    assert refused.value.code == "pod_jobs_not_enabled"


def test_a_library_run_with_the_switch_off_refuses_with_zero_spend(lifecycle, tmp_path):
    make, _go = lifecycle
    spec, backend, account = make()
    (tmp_path / pod_jobs.ENABLE_FILE).write_text(
        json.dumps({"enabled": False, "upload_roots": []})
    )
    with pytest.raises(pod_jobs.SpecRefused) as refused:
        pod_jobs.run(spec, tmp_path / "out", backend=backend)
    assert refused.value.code == "pod_jobs_not_enabled"
    assert account.creates == [] and account.pods == {}
    assert not (tmp_path / "ledger" / grant_runs.WEEKLY_FILE).exists()
    assert not (tmp_path / "out").exists()


def test_a_wait_never_ends_before_its_clock_says_it_has(monkeypatch):
    now = [100.0]

    def early_sleep(seconds):  # wakes 1 ms short, as a slewed wall clock can
        now[0] += max(0.0, seconds - 0.001)

    wait = pod_jobs.sleep_until(lambda: now[0], early_sleep)
    wait(60.0)
    assert now[0] >= 160.0


def test_an_ambiguous_create_reports_the_providers_http_status(lifecycle):
    from scripts.dev.exam_design.runpod.operator_compute import (
        ComputeError,
        Execution,
    )

    make, go = lifecycle
    spec, backend, _account = make()

    def ambiguous(request, retry_ambiguous=False):
        raise ComputeError(
            operation="provision",
            failed="create response unreadable",
            execution=Execution.MAY_HAVE_EXECUTED,
            resources_may_remain=True,
            retry_safe=False,
            next_action="reconcile",
            http_status=500,
        )

    backend.service.provision = ambiguous
    backend.recover = lambda intent_id, private: None
    receipt, _ledger = go(spec, backend)
    assert "(HTTP 500)" in receipt["refusal"]
