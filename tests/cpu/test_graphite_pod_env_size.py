"""GRAPHITE-POD-ENV-SIZE-01: a Graphite pod ships the import closure of what
it runs, its environment is measured before any create, and the launch
preflight's probe creates its pod with the same spec builder as a real run.

RunPod answered every stage-A create with an opaque 500 (recorded as
`pod_launch_ambiguous`): the whole-tree manifest put the pod environment near
131,000 characters, over the provider's limit (about 118,000). The probe passed
because it created an empty-environment pod."""

from __future__ import annotations

import dataclasses
import inspect
import json
import shutil
import subprocess
import sys
import threading
from decimal import Decimal
from pathlib import Path

import pytest
from graphite_phase3_fixtures import BASELINE, BATTERY_CHALLENGE, SCORING

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import pod_phase, pods
from scripts.dev.exam_design.runpod import pod_env

REPOSITORY = Path(__file__).resolve().parents[2]
KNN = {**BASELINE, "backbone": "knn", "parameters": {"neighbours": 6}}


def _head():
    return subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture(scope="module")
def shipped():
    return pods.ship_list(_head(), scoring=SCORING)


def _backend(manifest, service=None):
    """A `RunPodPods` without the provider: the spec builder and the launch's
    order of steps, never a request."""
    backend = object.__new__(pods.RunPodPods)
    backend.code_ref, backend.manifest = _head(), manifest
    backend.economics = pods.prices()
    backend.cuda_versions = ("12.4",)
    backend.boot = (
        REPOSITORY / "scripts/dev/exam_design/runpod/bootstrap.py"
    ).read_text()
    backend.clock = lambda: 1_000_000.0
    backend._record_lock = threading.Lock()
    backend.service = service
    return backend


def _job():
    return pods.PodJob(
        "graphite-env-size", KNN, "sha256:" + "0" * 64, 7, {"files": {}}, 30, 600
    )


RECORD = {
    "intent_id": "graphite-env-size",
    "token": "t" * 32,
    "deadline_at": 1_001_800,
    "allowed_cuda_versions": ["12.4"],
}


# -- the ship -------------------------------------------------------------------------------
def test_the_ship_is_the_closure_and_the_environment_fits(shipped):
    whole = pods.tracked(_head(), pods.SHIP_TREES, REPOSITORY)
    assert len(shipped) < len(whole) * 0.6
    assert not [p for p in shipped if p.startswith(pods.UNSHIPPED_TREES)]
    assert not [p for p in shipped if "/private/" in p.lower()]
    assert not [p for p in shipped if any(f in p.lower() for f in pods.FORBIDDEN_DATA)]
    # The scoring's public data still ships, and every file is sha-pinned.
    assert set(pods.data_paths(SCORING)) <= set(shipped)
    manifest = pods.code_manifest(_head(), shipped, REPOSITORY)
    assert set(manifest) == set(shipped)
    assert all(len(sha) == 64 for sha in manifest.values())
    spec = _backend(manifest).pod_spec(_job(), RECORD)
    # Room is left for a larger strategy in PHASE_CONFIG.
    assert pod_env.env_chars(spec.env) < pod_env.ENV_LIMIT_CHARS - 8_000


def test_the_pod_phase_runs_from_the_shipped_files_alone(shipped, tmp_path):
    """The real entry (`runner graphite_practice`) in a directory holding only
    the shipped files: it rebuilds what Carbon pinned and predicts PRACTICE.
    Each registered battery development variant resolves and builds there as
    it does in the repository."""
    sandbox = tmp_path / "pod"
    for path in shipped:
        target = sandbox / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / path, target)
    contract = ex.recorded_contract(SCORING)["contract_digest"]
    built, _files, _program = pod_phase.built_record(KNN, contract, 7, REPOSITORY)
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "strategy": KNN,
                "contract_digest": contract,
                "seed": 7,
                "expected": {"files": built["staged"], "program": built["program"]},
                "seconds": 600,
            }
        )
    )
    script = tmp_path / "in_pod.py"
    script.write_text(inspect.getsource(_variant_builds) + _IN_POD)
    done = subprocess.run(
        [
            sys.executable,
            str(script),
            str(sandbox),
            str(config),
            str(tmp_path / "out"),
            BATTERY_CHALLENGE,
        ],
        cwd=sandbox,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    assert done.returncode == 0, done.stderr[-1500:]
    report = json.loads(done.stdout.strip().splitlines()[-1])
    assert report["rc"] == 0
    assert json.loads((tmp_path / "out" / "built.json").read_text()) == built
    assert len(json.loads((tmp_path / "out" / "predictions.json").read_text())) == 200
    assert report["variants"] == _variant_builds(REPOSITORY, BATTERY_CHALLENGE)
    assert report["variants"], "no registered battery development variant"


#: Run inside the sandbox, after `_variant_builds`'s source: only the shipped
#: files are importable as Carbon.
_IN_POD = """
import json, sys
root, config, out, challenge = sys.argv[1:5]
sys.path[0] = root
import carbon
assert carbon.__file__.startswith(root), carbon.__file__
from scripts.dev.exam_design import runner
rc = runner.main(["graphite_practice", "--out", out, "--config", config])
print(json.dumps({"rc": rc, "variants": _variant_builds(root, challenge)}))
"""


def _variant_builds(root, challenge):
    from carbon.battery.research import SCAFFOLD
    from carbon.reconstruction import development_variants as dv

    out = {}
    for level in range(1, 8):
        try:
            variant = dv.variant(challenge, level)
        except dv.VariantRefused:
            continue
        found = dv.registered(variant.digest)
        try:
            record = dv.built_record(SCAFFOLD, found.digest, 7, root)
            out[str(level)] = record[0]["program"]
        except Exception as refused:  # noqa: BLE001 -- compared, never raised
            out[str(level)] = type(refused).__name__
    return out


# -- the guard ------------------------------------------------------------------------------
class NoProvider:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        self.calls.append(name)
        raise AssertionError(f"provider called: {name}")


def test_an_oversized_environment_is_refused_before_any_provider_call(tmp_path):
    big = {f"carbon/f{i:05d}.py": "0" * 64 for i in range(4000)}
    service = NoProvider()
    backend = _backend(big, service)
    with pytest.raises(pods.PodFailure) as refused:
        backend.launch(_job(), tmp_path)
    assert refused.value.executed is False
    assert refused.value.detail.startswith(pods.ENV_TOO_LARGE + ":")
    assert "CODE_MANIFEST_GZ_B64" in refused.value.detail
    assert service.calls == []


def test_the_guard_counts_names_and_values():
    assert pod_env.env_chars({"AB": "xyz", "C": ""}) == 6
    assert pod_env.largest_variable({"A": "x", "B": "xyz"}) == "B"
    assert pod_env.ENV_LIMIT_CHARS == 90_000


def test_the_a40_harness_shares_the_same_closure_and_limit():
    from scripts.dev.exam_design.runpod import a40_acceptance as a40

    assert a40.import_closure is pod_env.import_closure
    assert a40.ENV_LIMIT_CHARS == pod_env.ENV_LIMIT_CHARS
    with pytest.raises(a40.Refused):
        a40.read_blobs(_head(), REPOSITORY, ["no/such/file.py"])


def test_a_real_launch_and_the_probe_differ_only_in_the_start_command(shipped):
    from carbon.agent_campaign.graphite import preflight

    backend = _backend(pods.code_manifest(_head(), shipped, REPOSITORY))
    real = backend.pod_spec(_job(), RECORD)
    probe = backend.pod_spec(_job(), RECORD, start_command=preflight.PROBE_COMMAND)
    assert real.start_command[0] == "/opt/carbon-worker/bin/python"
    assert probe.start_command == preflight.PROBE_COMMAND
    assert dataclasses.replace(probe, start_command=real.start_command) == real
    assert (
        Decimal(str(real.max_rate_usd_per_hr))
        == backend.economics["rate_ceiling_usd_per_hr"]
    )
