"""GRAPHITE-L4-STAGING-01 (R1), slices 3 and 4: a staged Level 4 submission
travels with its proposal into the rebuilt record and to the pod.

Claims tested:
- Carbon's expected record pins the submission's documents beside the Level 4
  record (`expected.staged`), checked against the digest the record names;
  without them the pins differ, so a pod without the documents fails closed;
- a proposal naming a digest that was never staged is unrebuildable, typed;
  a staged one writes its envelope beside the proposal;
- the job carries the envelope (gzip, base64) under a transport bound, the pod
  unpacks it under a byte bound, and a job without one is unchanged.
"""

from __future__ import annotations

import json
import types

import pytest

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import pod_phase, pods
from carbon.challenge_validator.scoring import Unrebuildable

jax = pytest.importorskip("jax")
CHALLENGE = "battery-fastcharge-ageing-development-v1"


@pytest.fixture(scope="module")
def staged():
    from carbon.battery import level4 as battery
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import intake, staging, submission

    strategy = json.loads(json.dumps(battery.level0_strategies()["scaffold_mlp"]))
    manifest, files = battery.lower_recipe(
        strategy, allowlist_module.load(), max_bytes=intake.BOUNDS["document_bytes"]
    )
    raw = submission.canonical(manifest)
    envelope = staging.envelope(raw, files)
    strategy["parameters"][battery.FIELD] = envelope["submission"]
    kept = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    return strategy, envelope["submission"], kept, staging.workspace(raw, files)


def _variant():
    from carbon.reconstruction import development_variants as dv

    return dv.variant(CHALLENGE, 4)


def test_the_expected_record_pins_the_documents_beside_the_level4_record(staged):
    strategy, _digest, _kept, workspace = staged
    with_docs = ex.admit(strategy, 7, variant=_variant(), workspace=workspace)
    without = ex.admit(strategy, 7, variant=_variant())
    for name in workspace:
        assert name in with_docs["staged"] and name not in without["staged"]
    assert with_docs["staged"] != without["staged"]
    tampered = {**workspace, next(iter(workspace)): b"{}"}
    with pytest.raises(Exception):  # noqa: B017 - StagingCorrupt or its Unrebuildable
        ex.admit(strategy, 7, variant=_variant(), workspace=tampered)


def _holder(tmp_path, kept=None):
    holder = types.SimpleNamespace(root=tmp_path)
    variant = _variant()
    holder.level4_variant_bounds = lambda: json.loads(variant.widened[0].bounds_json)
    holder.level4_staged = lambda s: kept
    return holder


def test_a_proposal_carries_only_a_staged_submission(tmp_path, staged):
    strategy, _digest, kept, workspace = staged
    folder = tmp_path / "proposal"
    folder.mkdir()
    with pytest.raises(Unrebuildable) as refused:
        ex.Experiment._level4_documents(_holder(tmp_path), folder, strategy)
    assert refused.value.code == "level4_submission_not_staged"
    got = ex.Experiment._level4_documents(_holder(tmp_path, kept), folder, strategy)
    assert got == workspace
    assert (folder / "level4-envelope.json").read_bytes() == kept
    plain = json.loads(json.dumps(strategy))
    del plain["parameters"]["composition_graphs"]
    assert (
        ex.Experiment._level4_documents(_holder(tmp_path, kept), folder, plain) is None
    )


def test_the_job_carries_the_envelope_and_the_pod_unpacks_it_bounded(staged):
    _strategy, _digest, kept, workspace = staged
    transport = pod_phase.level4_transport(kept)
    assert len(transport) <= pod_phase.LEVEL4_TRANSPORT_CHARS
    assert pod_phase.level4_workspace(transport) == workspace
    with pytest.raises(ValueError):
        pod_phase.level4_workspace("x" * (pod_phase.LEVEL4_TRANSPORT_CHARS + 1))
    job = pods.PodJob("i", {}, "c", 1, {}, 1, 1, development_variant="v")
    assert "level4_envelope" not in job.config(0)
    carried = pods.PodJob(
        "i", {}, "c", 1, {}, 1, 1, development_variant="v", level4_envelope=transport
    )
    assert carried.config(0)["level4_envelope"] == transport


def test_the_pod_builds_its_record_with_the_carried_documents(monkeypatch, staged):
    _strategy, _digest, kept, workspace = staged
    seen = {}

    def built(strategy, contract, variant, seed, root=".", workspace=None):
        seen["workspace"] = workspace
        raise RuntimeError("stop after the compile step")

    monkeypatch.setattr(pod_phase, "development_built_record", built)
    monkeypatch.setattr(pod_phase, "probe_environment", lambda probe: {"ok": True})
    cfg = {
        "strategy": {},
        "contract_digest": "c",
        "development_variant": "v",
        "seed": 1,
        "expected": {},
        "seconds": 1,
        "level4_envelope": pod_phase.level4_transport(kept),
    }
    import tempfile

    with tempfile.TemporaryDirectory() as out:
        assert pod_phase.run(cfg, out) == 2
    assert seen["workspace"] == workspace
