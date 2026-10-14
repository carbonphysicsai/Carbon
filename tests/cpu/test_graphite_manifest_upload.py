"""Real anchored receiver/bootstrap boundaries; transport and phase are fixtures."""

import ast
import hashlib
import io
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.agent_campaign.graphite import pods
from scripts.dev.exam_design.runpod import pod_control, pod_env

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/dev/exam_design/runpod/bootstrap.py"
FILE = b"# public synthetic phase fixture\n"
MANIFEST = {"fixture.py": hashlib.sha256(FILE).hexdigest()}


def _bootstrap(monkeypatch, manifest=MANIFEST, *, legacy=False):
    for key in list(os.environ):
        if key.startswith("CODE_MANIFEST"):
            monkeypatch.delenv(key)
    env = (
        pod_control.manifest_env(manifest)
        if legacy
        else pod_control.manifest_upload_env(manifest)
    )
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PROBE_TOKEN", "fixture-token")
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    # Load the actual standalone program, avoiding only its top-level mkdir.
    tree.body = [
        n
        for n in tree.body
        if not (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr == "makedirs"
        )
    ]
    namespace = {"__name__": "fixture_bootstrap"}
    # Execute only the trusted tracked bootstrap under test.
    exec(compile(tree, str(SOURCE), "exec"), namespace)  # noqa: S102
    return namespace


def _post(ns, raw, token="fixture-token", length=None):
    handler = object.__new__(ns["H"])
    handler.path = "/code-manifest"
    handler.headers = {
        "X-Probe-Token": token,
        "Content-Length": str(len(raw) if length is None else length),
    }
    handler.rfile = io.BytesIO(raw)
    responses = []
    handler.send_response = responses.append
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None
    handler.do_POST()
    return responses[-1], handler


def test_create_carries_the_exact_anchor_and_env_growth_is_under_200_characters(
    tmp_path,
):
    from test_graphite_pod_env_size import _backend, _job

    manifest = {
        f"public/file-{i}.py": hashlib.sha256(str(i).encode()).hexdigest()
        for i in range(600)
    }
    backend = _backend(manifest)
    record = backend._record(_job(), tmp_path)
    assert (
        json.loads((tmp_path / "pod-job.json").read_bytes())["manifest_transport"]
        == pod_control.MANIFEST_UPLOAD
    )
    first = backend.pod_spec(_job(), record)
    expanded = {**manifest, **{f"public/extra-{i}.py": "1" * 64 for i in range(100)}}
    second = _backend(expanded).pod_spec(_job(), record)
    assert abs(pod_env.env_chars(second.env) - pod_env.env_chars(first.env)) < 200
    env = dict(first.env)
    assert "CODE_MANIFEST" not in env and "CODE_MANIFEST_GZ_B64" not in env
    raw = pod_control.manifest_upload_bytes(manifest)
    assert env["CODE_MANIFEST_SHA256"] == hashlib.sha256(raw).hexdigest()
    assert env["CODE_MANIFEST_SHA256"] == pods.manifest_digest(manifest)
    assert int(env["CODE_MANIFEST_BYTES"]) == len(raw)


def test_receiver_accepts_only_authenticated_exact_bytes_and_replay(monkeypatch):
    ns = _bootstrap(monkeypatch)
    raw = pod_control.manifest_upload_bytes(MANIFEST)
    assert _post(ns, raw, token="wrong")[0] == 404
    assert not ns["MANIFEST_READY"].is_set()
    damaged = raw.replace(MANIFEST["fixture.py"].encode(), b"0" * 64)
    assert _post(ns, damaged)[0] == 409
    assert ns["STATE"]["manifest_refusal"] == "code_manifest_anchor_mismatch"
    assert not ns["MANIFEST_READY"].is_set()
    assert _post(ns, raw)[0] == 200
    assert ns["MANIFEST"] == MANIFEST and ns["MANIFEST_READY"].is_set()
    assert _post(ns, raw)[0] == 200
    assert ns["MANIFEST"] == MANIFEST


def test_body_larger_than_the_anchor_is_refused_before_read(monkeypatch):
    ns = _bootstrap(monkeypatch)
    raw = pod_control.manifest_upload_bytes(MANIFEST)
    code, handler = _post(ns, raw, length=len(raw) + 1)
    assert code == 409 and handler.close_connection
    assert ns["STATE"]["manifest_refusal"] == "code_manifest_anchor_mismatch"
    assert handler.rfile.tell() == 0 and not ns["MANIFEST_READY"].is_set()


@pytest.mark.parametrize(
    "manifest", [{"../escape.py": "0" * 64}, {"fixture.py": "bad"}]
)
def test_an_anchored_malformed_document_cannot_enable_code(monkeypatch, manifest):
    ns = _bootstrap(monkeypatch, manifest)
    assert _post(ns, pod_control.manifest_upload_bytes(manifest))[0] == 409
    assert ns["STATE"]["manifest_refusal"] == "code_manifest_document_invalid"
    assert not ns["MANIFEST_READY"].is_set()


class Finished(Exception):
    pass


def _main(ns, tmp_path, *, expired=False, file_bytes=FILE):
    fetches, phases = [], []
    code = tmp_path / "code"
    out = tmp_path / "out"
    out.mkdir()
    ns.update(ROOT=str(code), OUT=str(out), OVL=str(tmp_path / "overlay"), INPUTS={})
    ns["threading"] = SimpleNamespace(
        Thread=lambda **kwargs: SimpleNamespace(start=lambda: None)
    )
    ns["http"] = SimpleNamespace(
        server=SimpleNamespace(
            ThreadingHTTPServer=lambda *args: SimpleNamespace(
                serve_forever=lambda: None
            )
        )
    )

    def fetch(url, *args):
        fetches.append(url)
        return file_bytes

    def phase(args, **kwargs):
        # The real bootstrap wrote the verified bytes before reaching this boundary.
        phases.append(args)
        assert (
            hashlib.sha256((code / "fixture.py").read_bytes()).hexdigest()
            == MANIFEST["fixture.py"]
        )
        assert not any(k.startswith("CODE_MANIFEST") for k in kwargs["env"])
        return SimpleNamespace(returncode=0)

    def done(seconds):
        raise Finished

    ns["fetch"] = fetch
    ns["subprocess"] = SimpleNamespace(run=phase, STDOUT=-2)
    ns["time"] = SimpleNamespace(
        time=lambda: 100.0, sleep=done, strftime=time.strftime, gmtime=time.gmtime
    )
    ns["DEADLINE"] = 99.0 if expired else 101.0
    with pytest.raises(Finished):
        ns["main"]()
    return fetches, phases, code


def test_post_create_tamper_reaches_no_fetch_write_or_phase(monkeypatch, tmp_path):
    ns = _bootstrap(monkeypatch)
    raw = pod_control.manifest_upload_bytes(MANIFEST)
    assert _post(ns, raw.replace(MANIFEST["fixture.py"].encode(), b"0" * 64))[0] == 409
    # Expired fixture deadline: run the real main refusal path without a wait.
    ns["MANIFEST_READY"] = SimpleNamespace(wait=lambda **kwargs: False)
    fetched, phases, code = _main(ns, tmp_path, expired=True)
    assert fetched == phases == [] and not code.exists()
    assert ns["STATE"]["stage"] == "bootstrap_failed"
    assert "code_manifest_deadline_expired" in ns["STATE"]["error"]


def test_a_valid_anchor_reaches_existing_file_checks_then_the_phase(
    monkeypatch, tmp_path
):
    ns = _bootstrap(monkeypatch)
    assert _post(ns, pod_control.manifest_upload_bytes(MANIFEST))[0] == 200
    fetched, phases, code = _main(ns, tmp_path)
    assert len(fetched) == len(phases) == 1
    assert (code / "fixture.py").read_bytes() == FILE
    assert ns["STATE"]["stage"] == "done"


def test_valid_manifest_keeps_each_file_hash_check_before_write_or_phase(
    monkeypatch, tmp_path
):
    ns = _bootstrap(monkeypatch)
    assert _post(ns, pod_control.manifest_upload_bytes(MANIFEST))[0] == 200
    fetched, phases, code = _main(ns, tmp_path, file_bytes=b"tampered file")
    assert len(fetched) == 1 and phases == [] and not code.exists()
    assert "code hash mismatch: fixture.py" in ns["STATE"]["error"]


def test_received_manifest_cannot_start_code_after_deadline(monkeypatch, tmp_path):
    ns = _bootstrap(monkeypatch)
    assert _post(ns, pod_control.manifest_upload_bytes(MANIFEST))[0] == 200
    fetched, phases, code = _main(ns, tmp_path, expired=True)
    assert fetched == phases == [] and not code.exists()
    assert "code_manifest_deadline_expired" in ns["STATE"]["error"]


def test_actual_oversized_phase_env_is_refused_before_provider_call(tmp_path):
    from test_graphite_pod_env_size import NoProvider, _backend, _job

    service = NoProvider()
    original = _job()
    job = SimpleNamespace(
        intent_id=original.intent_id,
        backend=original.backend,
        minutes=original.minutes,
        config=lambda stop: {"synthetic_payload": "x" * pod_env.ENV_LIMIT_CHARS},
    )
    backend = _backend(MANIFEST, service)
    with pytest.raises(pods.PodFailure, match="pod_env_too_large") as refused:
        backend.launch(job, tmp_path)
    assert refused.value.executed is False and service.calls == []


def test_manifest_transport_bound_refuses_before_provider_call(tmp_path):
    from test_graphite_pod_env_size import NoProvider, _backend, _job

    service = NoProvider()
    manifest = {"x" * pod_control.MANIFEST_UPLOAD_LIMIT: "0" * 64}
    backend = _backend(manifest, service)
    with pytest.raises(
        pods.PodFailure, match="code_manifest_upload_too_large"
    ) as refused:
        backend.launch(_job(), tmp_path)
    assert refused.value.executed is False and service.calls == []


def test_empty_manifest_is_refused_before_provider_call(tmp_path):
    from test_graphite_pod_env_size import NoProvider, _backend, _job

    service = NoProvider()
    backend = _backend({}, service)
    with pytest.raises(pods.PodFailure, match="code_manifest_empty") as refused:
        backend.launch(_job(), tmp_path)
    assert refused.value.executed is False and service.calls == []


def test_legacy_bootstrap_keeps_its_original_manifest_and_no_upload_route(monkeypatch):
    ns = _bootstrap(monkeypatch, legacy=True)
    assert ns["MANIFEST"] == MANIFEST
    assert _post(ns, pod_control.manifest_upload_bytes(MANIFEST))[0] == 404
    ns["wait_for_manifest"]()


def test_private_record_version_preserves_old_encoding_without_rewriting(tmp_path):
    from test_graphite_pod_env_size import RECORD, _backend, _job

    old = json.dumps(RECORD, sort_keys=True).encode()
    path = tmp_path / "pod-job.json"
    path.write_bytes(old)
    backend = _backend(MANIFEST)
    record = backend._record(_job(), tmp_path)
    assert record["manifest_transport"] == "legacy-env-v1"
    assert path.read_bytes() == old
    env = dict(backend.pod_spec(_job(), record).env)
    assert env["CODE_MANIFEST"] == pod_control.manifest_env(MANIFEST)["CODE_MANIFEST"]
    assert "CODE_MANIFEST_SHA256" not in env


def test_backend_wait_uploads_the_pinned_body_and_keeps_failure_typed():
    backend = object.__new__(pods.RunPodPods)
    backend.manifest = MANIFEST
    backend.clock = lambda: 100.0
    backend.sleep = lambda seconds: None
    backend.adapter = SimpleNamespace(
        connect_url=lambda resource, port: "https://fixture.test"
    )
    backend._owned = lambda handle: "fixture-owned-resource"
    backend._token = lambda handle: "fixture-token"
    calls = []
    backend.http_post = lambda url, token, raw, timeout: (
        calls.append((url, token, hashlib.sha256(raw).hexdigest())) or (200, b"")
    )
    states = iter(["waiting_code_manifest", "done"])
    backend._get = lambda *args: (200, json.dumps({"stage": next(states)}).encode())
    handle = pods.PodHandle("fixture-intent", "fixture-pod", 0.44)
    assert backend.wait(handle, deadline=200, cancelled=lambda: False) == "done"
    assert calls == [
        (
            "https://fixture.test/code-manifest",
            "fixture-token",
            pods.manifest_digest(MANIFEST),
        )
    ]
    backend.http_post = lambda *args: (409, b"untrusted response")
    with pytest.raises(
        pods.PodFailure, match="code_manifest_anchor_upload_refused"
    ) as refused:
        backend._upload_manifest(handle)
    assert refused.value.executed is True
