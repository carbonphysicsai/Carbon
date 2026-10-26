"""The validator's graph-route GPU lane (GPU-1, GPU_REBUILD_RULINGS_20261026).

Claims: a graph rebuilds on the GPU only when the deployment holds a JAX GPU worker and a record of
ops the hardware class repeats bit for bit, and every op of THAT graph is in it - otherwise it
rebuilds on the CPU exactly as before; the record is checked for shape and for the allowlist it was
measured against; the grade stays on the CPU inference image while the build takes the GPU worker;
nothing about a deployment without a lane changes (its binding and its evidence are what they
were); a graph this module cannot read is a CPU rebuild, never a GPU one.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_battery_gpu_practice import gpu_image
from test_f08_f02_graph_adapters import (
    SERVED,
    _binding,
    _case,
    _image,
    _local_runner,
    _train,
    adapter,
    posix,
)

from carbon.development_session import (
    direct_graph_construction_worker as graph_worker,
)
from carbon.development_session import graph_gpu_lane as lane
from carbon.development_session.construction_recipe import RecipeRefused
from carbon.development_session.profile import canonical
from carbon.development_session.research_carrier import MINER_GPU
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.level4 import allowlist as allowlist_module
from carbon.reconstruction import torch_profile

JAX = gpu_image("9")
TORCH = gpu_image("8", lock=torch_profile.GPU_LOCK_DIGEST)
KEY = SERVED[0]


def _envelope():
    _recipe, raw_manifest, files, staging = _case(KEY, {"steps": 4})
    return canonical(staging.envelope(raw_manifest, files))


def _record(**changes):
    value = {
        "schema": lane.SCHEMA,
        "allowlist_digest": "sha256:" + "1" * 64,
        "class_record_digest": "sha256:" + "2" * 64,
        "ops": ["dot_general", "tanh"],
    }
    value.update(changes)
    return json.dumps(value).encode()


# ---- the record ---------------------------------------------------------------------


def test_a_record_admits_exactly_its_ops_for_its_allowlist():
    assert lane.load_record(_record(), allowlist_digest="sha256:" + "1" * 64) == {
        "dot_general",
        "tanh",
    }


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        _record(schema="other"),
        _record(ops=["tanh", "tanh"]),
        _record(ops=[1]),
        _record(ops="tanh"),
        _record(class_record_digest=5),
        _record(allowlist_digest="sha256:" + "9" * 64),
        json.dumps({"schema": lane.SCHEMA}).encode(),
    ],
)
def test_a_malformed_or_other_allowlist_record_admits_nothing(raw):
    with pytest.raises(lane.GpuOpsRecordInvalid):
        lane.load_record(raw, allowlist_digest="sha256:" + "1" * 64)


# ---- the choice of device -------------------------------------------------------------


def test_a_graph_whose_every_op_repeats_rebuilds_on_the_gpu():
    envelope = _envelope()
    ops = lane.submission_ops(envelope)
    assert ops and "dot_general" in ops
    assert lane.device_for(envelope, gpu_image=JAX, gpu_ops=ops) == MINER_GPU
    assert lane.device_for(envelope, gpu_image=JAX, gpu_ops=ops | {"extra"}) == (
        MINER_GPU
    )


def test_one_op_that_does_not_repeat_sends_the_graph_to_the_cpu():
    envelope = _envelope()
    ops = lane.submission_ops(envelope)
    for left_out in sorted(ops):
        assert (
            lane.device_for(envelope, gpu_image=JAX, gpu_ops=ops - {left_out}) is None
        )


@pytest.mark.parametrize(
    "image, ops",
    [(None, frozenset({"tanh"})), (JAX, frozenset()), (JAX, None), (TORCH, None)],
)
def test_without_a_jax_worker_and_a_record_it_is_the_cpu(image, ops):
    assert lane.device_for(_envelope(), gpu_image=image, gpu_ops=ops) is None


def test_a_pytorch_worker_is_not_a_graph_lane():
    ops = lane.submission_ops(_envelope())
    assert lane.device_for(_envelope(), gpu_image=TORCH, gpu_ops=ops) is None


@pytest.mark.parametrize(
    "envelope", [b"", b"{}", b"[1]", json.dumps({"schema": "x"}).encode()]
)
def test_a_graph_it_cannot_read_is_a_cpu_rebuild(envelope):
    assert lane.submission_ops(envelope) is None
    assert lane.device_for(envelope, gpu_image=JAX, gpu_ops=frozenset({"tanh"})) is None


# ---- the provider -------------------------------------------------------------------


def _provider(**changes):
    values = {
        "graph_gpu_image": JAX,
        "graph_gpu_ops": lane.submission_ops(_envelope()),
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_the_build_takes_the_gpu_worker_and_the_grade_stays_on_the_cpu_image():
    cpu = _image()
    device, arguments = DirectDevelopmentTasksV3._graph_lane(
        _provider(), _envelope(), cpu
    )
    assert device == MINER_GPU
    assert arguments == {
        "image": JAX,
        "accelerator": MINER_GPU,
        "inference_image": cpu,
        "inference_accelerator": None,
    }


def test_a_deployment_without_a_lane_calls_as_before():
    cpu = _image()
    for provider in (
        _provider(graph_gpu_image=None, graph_gpu_ops=None),
        _provider(graph_gpu_ops=frozenset({"tanh"})),
    ):
        assert DirectDevelopmentTasksV3._graph_lane(provider, _envelope(), cpu) == (
            None,
            {"image": cpu},
        )


def test_the_binding_names_the_lane_only_when_there_is_one():
    bound = DirectDevelopmentTasksV3._graph_gpu_binding(_provider())
    assert bound[:2] == ["GRAPH_GPU_LANE", JAX.image_id]
    assert bound[2].startswith("sha256:")
    other = DirectDevelopmentTasksV3._graph_gpu_binding(
        _provider(graph_gpu_ops=frozenset({"tanh"}))
    )
    assert other[2] != bound[2]
    assert (
        DirectDevelopmentTasksV3._graph_gpu_binding(
            _provider(graph_gpu_image=None, graph_gpu_ops=None)
        )
        == []
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"graph_gpu_image": JAX},
        {"graph_gpu_ops": frozenset({"tanh"})},
        {"graph_gpu_image": TORCH, "graph_gpu_ops": frozenset({"tanh"})},
        {"graph_gpu_image": JAX, "graph_gpu_ops": frozenset()},
        {"graph_gpu_image": JAX, "graph_gpu_ops": {"tanh"}},
        {"graph_gpu_image": JAX, "graph_gpu_ops": frozenset({1})},
    ],
)
def test_a_half_or_wrong_lane_is_refused_before_anything_is_created(extra, tmp_path):
    with pytest.raises(ValueError, match="graph GPU lane"):
        DirectDevelopmentTasksV3(
            root=tmp_path / "t",
            requester="miner",
            ledger=None,
            owner="miner",
            discovery=None,
            inference_image=_image(),
            **extra,
        )
    assert not (tmp_path / "t").exists()


# ---- the worker: build and grade on different workers --------------------------------


def _run(tmp_path, **extra):
    import numpy as np

    recipe, raw_manifest, files, staging = _case(KEY, {"steps": 16})
    raw_train, inputs, _targets = _train(KEY)
    query = np.ascontiguousarray(inputs[:3])
    spec = adapter.SPECS[KEY]
    local = _local_runner()
    seen = []

    def runner(ledger, *, identity, **kwargs):
        seen.append(
            (
                kwargs["provenance"],
                kwargs["image"].image_id,
                kwargs.pop("accelerator", None),
            )
        )
        return local(ledger, identity=identity, **kwargs)

    from test_f08_f02_graph_adapters import PUBLIC

    graph_worker.reconstruct_and_infer_graph_public(
        SimpleNamespace(root=tmp_path),
        owner="test",
        identity="test",
        recipe=recipe,
        challenge_binding=_binding(KEY),
        limits_document=PUBLIC[KEY[0]].construction_limits_document(*KEY),
        source_envelope=canonical(staging.envelope(raw_manifest, files)),
        train=raw_train,
        inputs=query,
        expected_output_shape=(3, spec.outputs),
        allowlist_bytes=adapter.served_allowlist_bytes(*KEY),
        seed=0,
        runner=runner,
        adapter_id=spec.adapter_id,
        **extra,
    )
    return seen


@posix
def test_the_build_runs_on_the_gpu_worker_and_the_inference_on_the_cpu_image(tmp_path):
    cpu = _image()
    seen = _run(
        tmp_path,
        image=JAX,
        accelerator=MINER_GPU,
        inference_image=cpu,
        inference_accelerator=None,
    )
    assert seen == [
        (graph_worker.BUILD_PROVENANCE, JAX.image_id, MINER_GPU),
        (graph_worker.INFERENCE_PROVENANCE, cpu.image_id, None),
    ]


@posix
def test_a_call_without_a_split_is_what_it_was(tmp_path):
    cpu = _image()
    assert _run(tmp_path, image=cpu) == [
        (graph_worker.BUILD_PROVENANCE, cpu.image_id, None),
        (graph_worker.INFERENCE_PROVENANCE, cpu.image_id, None),
    ]


def test_an_inference_accelerator_without_its_image_is_refused(tmp_path):
    with pytest.raises(RecipeRefused):
        _run(
            tmp_path, image=JAX, accelerator=MINER_GPU, inference_accelerator=MINER_GPU
        )


# ---- the receiver's configuration ----------------------------------------------------


def _config(tmp_path, **extra):
    from test_direct_receiver import _config as base

    return {**base(tmp_path), **extra}


def test_the_lane_is_configured_with_both_its_worker_and_its_ops_or_neither(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import direct_receiver as receiver

    worker, ops = tmp_path / "jax-gpu.json", tmp_path / "ops.json"
    worker.write_text("{}")
    ops.write_text("{}")
    both = _config(
        tmp_path, graph_gpu_image_manifest=str(worker), graph_gpu_ops=str(ops)
    )
    monkeypatch.setattr(receiver, "private_json", lambda _: both)
    assert receiver.load_config(tmp_path / "c.json") == both
    for only in ("graph_gpu_image_manifest", "graph_gpu_ops"):
        half = {k: v for k, v in both.items() if k != only}
        monkeypatch.setattr(receiver, "private_json", lambda _, half=half: half)
        with pytest.raises(ValueError, match="needs both"):
            receiver.load_config(tmp_path / "c.json")
    missing = {**both, "graph_gpu_ops": str(tmp_path / "missing.json")}
    monkeypatch.setattr(receiver, "private_json", lambda _: missing)
    with pytest.raises(ValueError, match="graph gpu ops"):
        receiver.load_config(tmp_path / "c.json")


def _other_allowlist():
    # Whichever of v7/v8 the served version is NOT.
    served = adapter.served_allowlist_bytes(*KEY)
    for name in ("allowlist_v7.json", "allowlist_v8.json"):
        raw = Path(allowlist_module.__file__).with_name(name).read_bytes()
        if raw != served:
            return raw
    raise AssertionError("no other allowlist")


def _lane_setup(
    monkeypatch,
    tmp_path,
    *,
    image=JAX,
    eligible=True,
    allowlist=None,
    device_kind="NVIDIA GeForce RTX 4090",
):
    from carbon.challenge_validator import direct_receiver as receiver
    from carbon.development_session import research_campaign
    from carbon.level4.allowlist import Allowlist
    from carbon.reconstruction.worker import docker_runtime

    allowlist_bytes = adapter.served_allowlist_bytes(*KEY)
    record = {
        "schema": lane.SCHEMA,
        "allowlist_digest": Allowlist(allowlist or allowlist_bytes).digest,
        "class_record_digest": "sha256:" + "2" * 64,
        "ops": ["dot_general", "tanh"],
    }
    monkeypatch.setattr(receiver, "private_json", lambda _: record)
    from carbon.development_session import research_carrier

    monkeypatch.setattr(
        research_carrier,
        "_gpu_device",
        lambda: SimpleNamespace(device_kind=device_kind, digest="sha256:" + "4" * 64),
    )
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda _path: image)
    monkeypatch.setattr(
        docker_runtime, "doctor", lambda **_: SimpleNamespace(eligible=eligible)
    )
    monkeypatch.setattr(research_campaign, "verify_current_worker", lambda *_: None)
    monkeypatch.setattr(
        research_campaign, "verify_direct_v13_worker", lambda *_a, **_k: None
    )
    cfg = {
        "graph_gpu_image_manifest": str(tmp_path / "w.json"),
        "graph_gpu_ops": str(tmp_path / "o.json"),
    }
    return receiver, cfg, allowlist_bytes


def test_a_configured_lane_yields_its_worker_ops_and_record_digest(
    tmp_path, monkeypatch
):
    receiver, cfg, allowlist_bytes = _lane_setup(monkeypatch, tmp_path)
    image, ops, record_digest, device = receiver.graph_gpu_lane(
        cfg, {}, allowlist_bytes, "testnet"
    )
    assert device.device_kind == "NVIDIA GeForce RTX 4090"
    assert image == JAX and ops == {"dot_general", "tanh"}
    assert record_digest.startswith("sha256:")


def test_no_lane_configured_is_no_lane(tmp_path, monkeypatch):
    receiver, _cfg, allowlist_bytes = _lane_setup(monkeypatch, tmp_path)
    assert receiver.graph_gpu_lane({}, {}, allowlist_bytes, "testnet") == (
        None,
        None,
        None,
        None,
    )


def test_a_wrong_worker_record_or_host_is_refused(tmp_path, monkeypatch):
    from carbon.challenge_validator.direct_receiver import ReceiverUnavailable

    receiver, cfg, allowlist_bytes = _lane_setup(monkeypatch, tmp_path, image=TORCH)
    with pytest.raises(ValueError, match="JAX GPU worker"):
        receiver.graph_gpu_lane(cfg, {}, allowlist_bytes, "testnet")
    receiver, cfg, allowlist_bytes = _lane_setup(monkeypatch, tmp_path, eligible=False)
    with pytest.raises(ReceiverUnavailable):
        receiver.graph_gpu_lane(cfg, {}, allowlist_bytes, "testnet")
    receiver, cfg, allowlist_bytes = _lane_setup(
        monkeypatch, tmp_path, allowlist=_other_allowlist()
    )
    with pytest.raises(lane.GpuOpsRecordInvalid):
        receiver.graph_gpu_lane(cfg, {}, allowlist_bytes, "testnet")
    receiver, cfg, _ = _lane_setup(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="graph-route version"):
        receiver.graph_gpu_lane(cfg, {}, None, "testnet")


# ---- the repeat check: two more GPU rebuilds must match before the GPU serves ------------


class _Ledger:
    def __init__(self, states=None):
        self.states = states or {}
        self.root = Path("/nonexistent")

    def operation_state(self, identity, *, owner):
        return self.states.get(identity)


def _repeat_provider(ledger=None):
    provider = SimpleNamespace(
        graph_gpu_image=JAX,
        graph_gpu_ops=frozenset({"tanh"}),
        ledger=ledger or _Ledger(),
        owner="miner",
        discovery=SimpleNamespace(
            _material={
                "construction_limits_document": {
                    "reconstruction_resource_policy": {"build_wall_seconds_max": 321}
                },
                "train": b"train",
                "allowlist_bytes": b"allow",
            },
            graph_adapter_for=lambda _key: "adapter",
        ),
    )
    provider._probe_children = lambda task: DirectDevelopmentTasksV3._probe_children(
        provider, task
    )
    provider._reconcile_probes = (
        lambda task: DirectDevelopmentTasksV3._reconcile_probes(provider, task)
    )
    return provider


def _check(provider, monkeypatch, builds):
    from carbon.development_session.research_carrier import PRECHARGED_TRIAL

    calls = []

    def fake(ledger, **kwargs):
        calls.append((kwargs["identity"], kwargs["image"], kwargs["accelerator"]))
        assert PRECHARGED_TRIAL.get() is not None  # not a trial of the miner's
        outcome = builds[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(state_digest=outcome)

    monkeypatch.setattr(graph_worker, "reconstruct_public_graph", fake)
    task = SimpleNamespace(value="direct-task")
    result = DirectDevelopmentTasksV3._graph_gpu_repeats(
        provider,
        task,
        SimpleNamespace(challenge_key="k"),
        object(),
        {"challenge_id": "c"},
        b"envelope",
        MINER_GPU,
    )
    assert PRECHARGED_TRIAL.get() is None
    return result, calls


def test_two_matching_gpu_rebuilds_let_the_gpu_serve(monkeypatch):
    result, calls = _check(_repeat_provider(), monkeypatch, ["sha256:a", "sha256:a"])
    assert result == (True, None)
    assert calls == [
        ("direct-task~gpu1", JAX, MINER_GPU),
        ("direct-task~gpu2", JAX, MINER_GPU),
    ]


def test_two_rebuilds_that_differ_send_the_graph_to_the_cpu(monkeypatch):
    result, _ = _check(_repeat_provider(), monkeypatch, ["sha256:a", "sha256:b"])
    assert result == (False, "graph_gpu_rebuild_not_repeatable")


def test_a_device_failure_is_a_cpu_rebuild_and_settles_what_it_held(monkeypatch):
    from carbon.development_session import research_carrier

    settled = []
    monkeypatch.setattr(
        research_carrier,
        "reconcile_worker",
        lambda ledger, *, owner, identity: settled.append(identity),
    )
    ledger = _Ledger({"direct-task~gpu1": "RESERVED"})
    result, calls = _check(
        _repeat_provider(ledger), monkeypatch, [RuntimeError("no device")]
    )
    assert result == (False, "graph_gpu_attempt_failed")
    assert len(calls) == 1 and settled == ["direct-task~gpu1"]


def test_the_campaigns_own_limits_are_never_swallowed(monkeypatch):
    from carbon.development_session.research_ledger import (
        MINER_CEILING_REACHED,
        LedgerRefusal,
    )

    refusal = LedgerRefusal(
        "budget", code=MINER_CEILING_REACHED, dimension="elapsed_seconds"
    )
    with pytest.raises(LedgerRefusal):
        _check(_repeat_provider(), monkeypatch, [refusal])


def test_there_are_no_probes_without_a_lane():
    provider = SimpleNamespace(graph_gpu_image=None)
    assert (
        DirectDevelopmentTasksV3._probe_children(
            provider, SimpleNamespace(value="direct-task")
        )
        == ()
    )


def test_a_device_class_without_the_owners_acceptance_never_starts_the_lane(
    tmp_path, monkeypatch
):
    from carbon.reconstruction.hardware_acceptance import DeviceClassNotAccepted

    receiver, cfg, allowlist_bytes = _lane_setup(
        monkeypatch, tmp_path, device_kind="NVIDIA H100 PCIe"
    )
    with pytest.raises(DeviceClassNotAccepted):
        receiver.graph_gpu_lane(cfg, {}, allowlist_bytes, "testnet")
    # An acceptance names its network: the testnet record admits no other.
    receiver, cfg, allowlist_bytes = _lane_setup(monkeypatch, tmp_path)
    with pytest.raises(DeviceClassNotAccepted):
        receiver.graph_gpu_lane(cfg, {}, allowlist_bytes, "mainnet")
    with pytest.raises(DeviceClassNotAccepted):
        receiver.graph_gpu_lane(cfg, {}, allowlist_bytes, None)


def test_a_host_without_a_gpu_record_refuses_the_lane(tmp_path, monkeypatch):
    from carbon.development_session import research_carrier

    receiver, cfg, allowlist_bytes = _lane_setup(monkeypatch, tmp_path)

    def absent():
        raise ValueError("no GPU device record is installed on this host")

    monkeypatch.setattr(research_carrier, "_gpu_device", absent)
    with pytest.raises(ValueError, match="no GPU device record"):
        receiver.graph_gpu_lane(cfg, {}, allowlist_bytes, "testnet")
