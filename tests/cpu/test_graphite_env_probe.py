"""Real spec/serializer controls; no provider, key, host ledger or spend."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_graphite_pod_env_size import RECORD, NoProvider, _backend, _job

from carbon.agent_campaign.graphite.preflight import PROBE_COMMAND
from scripts.dev import graphite_env_probe as probe
from scripts.dev.exam_design.runpod import pod_env
from scripts.dev.exam_design.runpod.operator_compute.runpod import RunPodAdapter

TAG = "a" * 24
MANIFEST = {
    "carbon/__init__.py": hashlib.sha256(
        (Path(__file__).resolve().parents[2] / "carbon/__init__.py").read_bytes()
    ).hexdigest()
}


def base(service=None):
    # The real launch spec builder, public KNN fixture and synthetic record.
    return _backend(MANIFEST, service).pod_spec(
        _job(), RECORD, start_command=PROBE_COMMAND
    )


def target(spec, extra=64):
    return pod_env.env_chars(spec.env) + len(probe.PADDING_KEY) + extra


def test_real_builder_adds_only_exact_padding_and_never_calls_provider():
    service = NoProvider()
    backend = _backend(MANIFEST, service)
    original = backend.pod_spec(_job(), RECORD, start_command=PROBE_COMMAND)
    result = probe.prepare_probe(backend, _job(), RECORD, target(original))
    assert pod_env.env_chars(result.env) == target(original)
    assert dict(result.env)[probe.PADDING_KEY] == "A" * 64
    assert replace(result, env=original.env) == original
    assert dict(result.env) == {**dict(original.env), probe.PADDING_KEY: "A" * 64}
    assert service.calls == []
    real = backend.pod_spec(_job(), RECORD)
    assert probe.PADDING_KEY not in dict(real.env)
    with pytest.raises(probe.ProbeRefused, match="fixed-sleep"):
        probe.padded_spec(real, target(original))


@pytest.mark.parametrize("bad", [None, True, 1.5, -1, 0, pod_env.ENV_LIMIT_CHARS + 1])
def test_invalid_or_over_guard_targets_refuse(bad):
    with pytest.raises(probe.ProbeRefused, match="target outside"):
        probe.padded_spec(base(), bad)


def test_padding_rechecks_current_bound_after_the_real_base_guard(monkeypatch):
    service = NoProvider()
    backend = _backend(MANIFEST, service)
    original = base()
    wanted = target(original)
    monkeypatch.setattr(pod_env, "ENV_LIMIT_CHARS", wanted - 1)
    # The base still passes pod_spec, but the padded candidate must refuse.
    assert pod_env.env_chars(backend.pod_spec(_job(), RECORD).env) < wanted - 1
    with pytest.raises(probe.ProbeRefused, match="target outside"):
        probe.prepare_probe(backend, _job(), RECORD, wanted)
    with pytest.raises(probe.ProbeRefused, match="exceeds the current guard"):
        probe.request_metrics(replace(original, env=(("X", "A" * wanted),)), TAG)
    assert service.calls == []


def test_undersized_targets_duplicate_padding_and_duplicate_names_refuse():
    spec = base()
    with pytest.raises(probe.ProbeRefused, match="base plus padding name"):
        probe.padded_spec(spec, pod_env.env_chars(spec.env))
    padded = probe.padded_spec(spec, target(spec))
    with pytest.raises(probe.ProbeRefused, match="padding already"):
        probe.padded_spec(padded, target(spec) + 1)
    with pytest.raises(probe.ProbeRefused, match="unique string"):
        probe.padded_spec(replace(spec, env=(("X", "A"), ("X", "B"))), 500)
    with pytest.raises(probe.ProbeRefused, match="unknown padding"):
        probe.padded_spec(spec, target(spec), pattern="arbitrary-input")


def test_metrics_match_bytes_handed_to_the_actual_adapter_transport():
    spec = probe.padded_spec(base(), target(base()))
    seen = []

    def transport(method, url, *, body, headers, timeout):
        assert method == "POST" and url.endswith("/v1/pods")
        seen.append(body)
        return 200, b'{"id":"fixture123"}'

    key = SimpleNamespace(reveal=lambda: "fixture-key")
    adapter = RunPodAdapter(SimpleNamespace(load=lambda: key), transport)
    adapter.create(spec, ownership_tag=TAG)
    metrics = probe.request_metrics(spec, TAG)
    [wire] = seen
    body = json.loads(wire)
    assert metrics["request_body_bytes"] == len(wire)
    assert metrics["transport_env_json_bytes"] == len(json.dumps(body["env"]).encode())
    assert body["env"]["CARBON_OWNERSHIP_TAG"] == TAG
    assert metrics["transport_env_chars"] == pod_env.env_chars(body["env"])
    assert metrics["transport_env_chars"] > metrics["spec_env_chars"]
    assert metrics["request_body_bytes"] > metrics["transport_env_json_bytes"]
    # A non-env field grows actual body bytes but cannot change env counts.
    changed = replace(spec, ports=("9999/http",) * 10)
    larger = probe.request_metrics(changed, TAG)
    assert larger["request_body_bytes"] > metrics["request_body_bytes"]
    assert larger["spec_env_chars"] == metrics["spec_env_chars"]


def test_equal_character_probes_distinguish_utf8_and_escaped_json_bytes():
    spec = base()
    wanted = target(spec)
    metrics = {
        name: probe.request_metrics(probe.padded_spec(spec, wanted, pattern=name), TAG)
        for name in probe.PATTERNS
    }
    assert {m["spec_env_chars"] for m in metrics.values()} == {wanted}
    assert (
        metrics["ascii"]["spec_env_utf8_bytes"]
        == metrics["escaped"]["spec_env_utf8_bytes"]
    )
    assert (
        metrics["unicode"]["spec_env_utf8_bytes"]
        > metrics["ascii"]["spec_env_utf8_bytes"]
    )
    assert (
        metrics["escaped"]["request_body_bytes"]
        > metrics["ascii"]["request_body_bytes"]
    )
    assert (
        metrics["unicode"]["request_body_bytes"]
        > metrics["escaped"]["request_body_bytes"]
    )


def test_numeric_report_never_contains_environment_or_ownership_values(monkeypatch):
    marker = "private-fixture-marker"
    spec = replace(base(), env=(("PUBLIC_FIXTURE", marker),))
    # If measurement accidentally calls _send/create, even the credential
    # read refuses; no real credential or transport exists in the helper.
    monkeypatch.setattr(
        RunPodAdapter,
        "create",
        lambda *args, **kwargs: pytest.fail("offline create forbidden"),
    )
    monkeypatch.setattr(
        RunPodAdapter,
        "_send",
        lambda *args, **kwargs: pytest.fail("offline send forbidden"),
    )
    report = probe.request_metrics(probe.padded_spec(spec, target(spec)), TAG)
    assert marker not in json.dumps(report) and TAG not in json.dumps(report)
    assert all(type(value) is int for key, value in report.items() if key != "schema")
