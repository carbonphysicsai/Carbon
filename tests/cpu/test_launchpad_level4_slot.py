"""The Launchpad's Level 4 slot (LAUNCHPAD-LEVELS-01 S3; the Level 4 staging
contract, `carbon.level4.staging`).

Claims tested:

1. Freeze verifies a lowered submission against the Level 4 variant's pinned
   allowlist, its Challenge and the recipe's interface, with `max_bytes` the
   variant's pinned `caps.document_bytes`: a whole submission passes, a
   tampered one is refused, and so are an interface or batch that is not the
   recipe's and a strategy whose Level 4 field is not the submission.
2. While the variant sets no size bound the freeze is refused
   `level4_size_bound_not_set`; no bound is invented.
3. The staging envelope is kept and read back byte for byte: the bytes it
   carries are the directory's, never re-serialized.
4. Submit refuses before anything is signed while no intake carries the
   envelope (`level4_envelope_transport_unavailable`).

The recipe's interface and batch come from a fixture adapter, so the bundle
is a small hand-lowered graph; the real development door is exercised once,
in its own process, for its refusal of an empty directory.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.development_session import construction_level as cl
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import staging, submission
from carbon.level4.tooling import through_bprime
from carbon.level4.validate import Interface
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_level_cli as door

BATTERY = cr.BATTERY_CHALLENGE
BATCH = 4
INTERFACE = Interface(
    inputs=(("inputs/x", "float32", (3,)),), outputs=(("float32", (2,)),)
)
BASE = {
    "schema_version": "1.0",
    "challenge_id": BATTERY,
    "backbone": "mlp",
    "parameters": {"width": 16, "depth": 1, "steps": 48},
}


def _lower(batch, interface_digest):
    import jax
    import jax.numpy as jnp

    allowlist = allowlist_module.load()

    def forward(p, x):
        return jnp.tanh(x @ p[0])

    def init(key):
        return [jax.random.normal(key, (3, 2))]

    _, fwd, _ = through_bprime(
        forward,
        ([jnp.ones((3, 2))], jnp.ones((batch, 3))),
        role="forward",
        allowlist=allowlist,
        input_names=["params/0", "inputs/x"],
        max_bytes=1 << 24,
    )
    _, ini, _ = through_bprime(
        init,
        (jax.random.PRNGKey(0),),
        role="init",
        allowlist=allowlist,
        input_names=["carbon/key"],
        max_bytes=1 << 24,
    )
    manifest, files = submission.build(
        challenge=BATTERY,
        interface=interface_digest,
        allowlist=allowlist,
        forward=fwd,
        init=ini,
    )
    return submission.canonical(manifest), files


@pytest.fixture(scope="module")
def lowered():
    return _lower(BATCH, INTERFACE.digest())


@pytest.fixture
def adapter(monkeypatch):
    fake = SimpleNamespace(
        interface=lambda strategy: INTERFACE,
        training_batch=lambda strategy: BATCH,
    )
    monkeypatch.setitem(sys.modules, "fixture_level4_adapter", fake)
    monkeypatch.setitem(door.LEVEL4_ADAPTERS, BATTERY, "fixture_level4_adapter")
    # The development door, in this process, so it sees the fixture adapter.
    monkeypatch.setattr(
        cl,
        "RUN",
        lambda request: cl.checked(door.answer(json.loads(json.dumps(request)))),
    )
    return fake


def _directory(tmp_path, raw_manifest, files):
    folder = tmp_path / "lowered"
    staging.write_directory(folder, raw_manifest, files)
    return str(folder)


def _strategy(digest):
    value = json.loads(json.dumps(BASE))
    value["parameters"]["composition_graphs"] = digest
    return value


def _found():
    return cl.resolve(BATTERY, 4)


def test_a_whole_submission_passes_and_its_envelope_is_the_directorys_bytes(
    tmp_path, lowered, adapter
):
    raw_manifest, files = lowered
    directory = _directory(tmp_path, raw_manifest, files)
    digest = submission.name(raw_manifest)
    envelope = cl.level4_check(_found(), _strategy(digest), directory)
    assert envelope["submission"] == digest
    assert staging.from_envelope(envelope) == (digest, raw_manifest, files)
    # Kept beside the frozen record and read back unchanged.
    folder = tmp_path / "epoch-1"
    folder.mkdir()
    cl.write_envelope(folder, envelope)
    cl.write_envelope(folder, envelope)  # a retried freeze is the same bytes
    record = {"strategy": _strategy(digest)}
    assert cl.read_envelope(folder, record) == envelope


def test_a_tampered_submission_is_refused(tmp_path, lowered, adapter):
    raw_manifest, files = lowered
    directory = _directory(tmp_path, raw_manifest, files)
    name = min(files)
    path = tmp_path / "lowered" / (name.split(":", 1)[1] + ".json")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(cl.LevelRefused) as refused:
        cl.level4_check(_found(), _strategy(submission.name(raw_manifest)), directory)
    assert refused.value.code == "level4_submission_refused"


def test_the_strategy_must_name_the_submission(tmp_path, lowered, adapter):
    raw_manifest, files = lowered
    directory = _directory(tmp_path, raw_manifest, files)
    with pytest.raises(cl.LevelRefused) as refused:
        cl.level4_check(_found(), _strategy("sha256:" + "0" * 64), directory)
    assert refused.value.code == "level4_submission_not_in_strategy"


def test_another_interface_is_refused(tmp_path, adapter):
    raw_manifest, files = _lower(BATCH, "sha256:" + "1" * 64)
    directory = _directory(tmp_path, raw_manifest, files)
    with pytest.raises(cl.LevelRefused) as refused:
        cl.level4_check(_found(), _strategy(submission.name(raw_manifest)), directory)
    assert refused.value.code == "level4_interface_mismatch"


def test_another_batch_is_refused(tmp_path, adapter):
    raw_manifest, files = _lower(BATCH + 1, INTERFACE.digest())
    directory = _directory(tmp_path, raw_manifest, files)
    with pytest.raises(cl.LevelRefused) as refused:
        cl.level4_check(_found(), _strategy(submission.name(raw_manifest)), directory)
    assert refused.value.code == "level4_batch_mismatch"


def test_an_unset_size_bound_is_refused_never_invented(
    tmp_path, lowered, adapter, monkeypatch
):
    found = _found()
    real = door._variant

    def unbounded(request):
        variant = real(request)
        (widened,) = variant.widened
        bounds = json.loads(widened.bounds_json)
        bounds["caps"] = {**bounds["caps"], "document_bytes": "HUMAN_INPUT"}
        return SimpleNamespace(
            level=variant.level,
            version=variant.version,
            digest=variant.digest,
            challenge=variant.challenge,
            widened=(
                SimpleNamespace(bounds_json=json.dumps(bounds), name=widened.name),
            ),
        )

    monkeypatch.setattr(door, "_variant", unbounded)
    raw_manifest, files = lowered
    directory = _directory(tmp_path, raw_manifest, files)
    with pytest.raises(cl.LevelRefused) as refused:
        cl.level4_check(found, _strategy(submission.name(raw_manifest)), directory)
    assert refused.value.code == "level4_size_bound_not_set"


def test_a_level4_freeze_needs_its_directory():
    with pytest.raises(cl.LevelRefused) as refused:
        cl.level4_check(_found(), _strategy("sha256:" + "0" * 64), None)
    assert refused.value.code == "level4_directory_required"


def test_the_development_door_refuses_an_empty_directory_in_its_own_process(tmp_path):
    with pytest.raises(cl.LevelRefused) as refused:
        cl.level4_check(_found(), _strategy("sha256:" + "0" * 64), str(tmp_path))
    assert refused.value.code == "level4_submission_refused"
    assert {"code": "staging_manifest_missing"} in refused.value.issues


def test_submit_sends_nothing_while_no_intake_carries_the_envelope(
    tmp_path, lowered, adapter
):
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused

    raw_manifest, files = lowered
    digest = submission.name(raw_manifest)
    folder = tmp_path / "epoch-1"
    folder.mkdir()
    cl.write_envelope(folder, staging.envelope(raw_manifest, files))
    record = {
        "strategy": _strategy(digest),
        "contract_digest": _found()["digest"],
        "construction_level": {**cl.practice_label(_found())},
    }
    prepared = SimpleNamespace(ledger=SimpleNamespace(root=tmp_path), args=None)
    with pytest.raises(OperationRefused) as refused:
        asyncio.run(campaign._evaluate_through_intake(prepared, 1, record, "http://x"))
    assert refused.value.code == "level4_envelope_transport_unavailable"


def test_a_listing_target_still_refuses_level_4_before_signing():
    from scripts.dev.miner_launchpad import levels
    from scripts.dev.miner_launchpad.controller import Rejected

    found = _found()
    manifest = {
        "challenge": {"id": BATTERY, "version": "x"},
        "construction_level": found,
    }
    served = {
        "served_contracts": [
            {"level": 4, "variant": found["variant"], "digest": found["digest"]}
        ]
    }
    with pytest.raises(Rejected) as refused:
        levels.require_served(
            {"intakes": {BATTERY: "http://x"}}, manifest, read=lambda url: served
        )
    assert refused.value.code == "level4_envelope_transport_unavailable"
