"""PLT-36 offline probe preparation. No launch, credentials or network CLI."""

from __future__ import annotations

import json
from dataclasses import replace

from carbon.agent_campaign.graphite.preflight import PROBE_COMMAND
from scripts.dev.exam_design.runpod import pod_env
from scripts.dev.exam_design.runpod.operator_compute.model import PodSpec
from scripts.dev.exam_design.runpod.operator_compute.runpod import RunPodAdapter

PADDING_KEY = "CARBON_ENV_PROBE_PADDING"
PATTERNS = {"ascii": "A", "escaped": '"\\', "unicode": "\u00e9"}


class ProbeRefused(ValueError):
    """Preparation cannot produce the requested controlled probe."""


def _environment(spec):
    if type(spec) is not PodSpec or spec.start_command != PROBE_COMMAND:
        raise ProbeRefused("fixed-sleep probe spec required")
    env = {}
    for key, value in spec.env:
        if type(key) is not str or type(value) is not str or key in env:
            raise ProbeRefused("unique string environment required")
        env[key] = value
    return env


def padded_spec(spec, target_chars, *, pattern="ascii"):
    """Add only probe padding; target uses the unchanged runtime guard's units.

    The upstream spec builder already guards its base; padding must pass the
    same guard again. This never changes a cap or removes existing content.
    """
    env = _environment(spec)
    if PADDING_KEY in env:
        raise ProbeRefused("probe padding already present")
    if type(target_chars) is not int or not 0 < target_chars <= pod_env.ENV_LIMIT_CHARS:
        raise ProbeRefused("target outside the current environment guard")
    if type(pattern) is not str or pattern not in PATTERNS:
        raise ProbeRefused("unknown padding pattern")
    length = target_chars - pod_env.env_chars(env) - len(PADDING_KEY)
    if length < 0:
        raise ProbeRefused("base plus padding name exceeds target")
    filler = PATTERNS[pattern]
    env[PADDING_KEY] = (filler * ((length + len(filler) - 1) // len(filler)))[:length]
    if pod_env.env_chars(env) != target_chars:
        raise ProbeRefused("padding target mismatch")
    # Keep every original field and the exact real environment; no new job
    # payload, envelope, ports, image or bootstrap is introduced.
    return replace(spec, env=tuple(env.items()))


def prepare_probe(pods, job, record, target_chars, *, pattern="ascii"):
    """Wrap the real spec builder, without invoking any provider/service method.

    Caller supplies a frozen public probe job/record. Never load a historical
    private proposal directory to prepare this controlled series.
    """
    spec = pods.pod_spec(job, record, start_command=PROBE_COMMAND)
    return padded_spec(spec, target_chars, pattern=pattern)


class _NoCredentials:
    def load(self):
        raise ProbeRefused("offline preparation cannot read credentials")


def _no_transport(*args, **kwargs):
    raise ProbeRefused("offline preparation cannot issue a provider request")


def request_metrics(spec, ownership_tag):
    """Numeric sizes, including the exact adapter-injected ownership environment.

    _send uses json.dumps(body).encode() with default spacing/ASCII escaping.
    Do not substitute compact JSON or omit fields to estimate wire bytes.
    The adapter here cannot load a credential or issue a request.
    """
    env = _environment(spec)
    if pod_env.env_chars(env) > pod_env.ENV_LIMIT_CHARS:
        raise ProbeRefused("environment exceeds the current guard")
    adapter = RunPodAdapter(_NoCredentials(), _no_transport)
    body = adapter.create_body(spec, ownership_tag)
    wire_env = body["env"]
    return {
        "schema": "carbon.graphite.env-probe-metrics.v1",
        "spec_env_chars": pod_env.env_chars(env),
        "spec_env_utf8_bytes": sum(
            len(k.encode()) + len(v.encode()) for k, v in env.items()
        ),
        "transport_env_chars": pod_env.env_chars(wire_env),
        "transport_env_utf8_bytes": sum(
            len(k.encode()) + len(v.encode()) for k, v in wire_env.items()
        ),
        "transport_env_json_bytes": len(json.dumps(wire_env).encode()),
        "request_body_bytes": len(json.dumps(body).encode()),
        "largest_spec_variable_chars": max(
            (len(k) + len(v) for k, v in env.items()), default=0
        ),
        "padding_chars": len(env.get(PADDING_KEY, "")),
        "runtime_guard_chars": pod_env.ENV_LIMIT_CHARS,
    }
