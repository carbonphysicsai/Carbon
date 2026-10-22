"""`receiver_setup --pack-set-key` and the receiver configuration's pack-set block
(OWNER-FULL-EXAM-BANK-01 item 3, step c). The setup takes a Challenge version's
whole delivered pack set (every batch re-verified), names its first batch as the
receiver's primary pack, and records the set for the receiver's per-batch grading;
a config whose set block is malformed or disagrees with the primary pack is refused."""

from __future__ import annotations

import json
import os

import pytest
from test_sealed_pack_set import (
    CHALLENGE,
    VERSION,
    _batch_package,
    _Fetcher,
    _set_package,
)

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import direct_receiver, receiver_setup
from carbon.challenge_validator import sealed_pack_import as sp
from carbon.development_session.profile import canonical

HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"


@pytest.fixture
def delivered(tmp_path):
    key = ak.ProducerKey.create(str(tmp_path / "producer.key"))
    one, package_one = _batch_package(key, 1)
    two, package_two = _batch_package(key, 2)
    digests = [one["manifest_digest"], two["manifest_digest"]]
    set_commitment, set_package = _set_package(key, digests)
    adapter = sp.SealedPackAdapter(
        CHALLENGE, VERSION, sp.SealedPackStore(tmp_path / "packs")
    )
    ak.sync(
        adapter,
        _Fetcher(set_package, package_one, package_two),
        key.public_key,
        CHALLENGE,
    )
    return adapter.store, set_commitment, sorted(digests)


def test_the_setup_takes_the_whole_delivered_set_and_names_its_primary_pack(delivered):
    store, commitment, digests = delivered
    block, first_digest, first_directory = receiver_setup._stored_pack_set(
        store.root, commitment["set_key"], {"id": CHALLENGE, "version": VERSION}
    )
    assert block == {
        "store": str(store.root),
        "set_key": commitment["set_key"],
        "batches": digests,
    }
    assert first_digest == digests[0]
    assert first_directory == store.pack_directory(digests[0], CHALLENGE, VERSION)


def test_a_set_with_a_batch_missing_from_the_store_is_refused(delivered):
    store, commitment, digests = delivered
    record = store.root / ".delivered" / (digests[1].removeprefix("sha256:") + ".json")
    record.unlink()
    with pytest.raises(receiver_setup.SetupRefused) as refused:
        receiver_setup._stored_pack_set(
            store.root, commitment["set_key"], {"id": CHALLENGE, "version": VERSION}
        )
    assert refused.value.code == "answer_key_pack_set_batch_missing"
    with pytest.raises(receiver_setup.SetupRefused):
        receiver_setup._stored_pack_set(
            store.root, "sha256:" + "0" * 64, {"id": CHALLENGE, "version": VERSION}
        )


def _write(path, value):
    path.write_bytes(canonical(value))
    os.chmod(path, 0o600)


def _config(tmp_path, delivered, **override):
    store, commitment, digests = delivered
    directory = store.pack_directory(digests[0], CHALLENGE, VERSION)
    root = tmp_path / "state"
    root.mkdir(exist_ok=True)
    profile = tmp_path / "profile.json"
    profile.write_text("{}")
    value = {
        "schema": direct_receiver.SCHEMA,
        "root": str(root),
        "runner_profile": str(profile),
        "receiver_hotkey": HOTKEY,
        "host": "127.0.0.1",
        "port": 8801,
        "lifetime_seconds": 3600,
        "measure_query": True,
        "evaluation_pack": {
            "root": str(directory),
            "manifest": "evaluation-pack.json",
            "public_root": str(directory),
            "private_root": str(directory),
            "sealed_delivery": {
                "store": str(store.root),
                "manifest_digest": digests[0],
            },
        },
        "evaluation_pack_set": {
            "store": str(store.root),
            "set_key": commitment["set_key"],
            "batches": digests,
        },
    }
    value.update(override)
    path = tmp_path / "receiver.json"
    _write(path, value)
    return path


def test_the_receiver_config_accepts_a_set_whose_first_batch_is_the_primary_pack(
    tmp_path, delivered
):
    loaded = direct_receiver.load_config(_config(tmp_path, delivered))
    assert loaded["evaluation_pack_set"]["batches"] == delivered[2]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: {**s, "batches": list(reversed(s["batches"]))},
        lambda s: {**s, "batches": []},
        lambda s: {**s, "batches": [s["batches"][0], s["batches"][0]]},
        lambda s: {**s, "set_key": 5},
        lambda s: {**s, "store": "relative/path"},
        lambda s: {**s, "extra": 1},
        lambda s: {k: v for k, v in s.items() if k != "set_key"},
    ],
)
def test_a_malformed_pack_set_block_is_refused(tmp_path, delivered, mutate):
    store, commitment, digests = delivered
    block = {
        "store": str(store.root),
        "set_key": commitment["set_key"],
        "batches": digests,
    }
    path = _config(tmp_path, delivered, evaluation_pack_set=mutate(block))
    with pytest.raises(ValueError, match="evaluation pack set selection"):
        direct_receiver.load_config(path)


def test_a_set_block_needs_its_primary_pack_and_must_name_it_first(tmp_path, delivered):
    store, commitment, digests = delivered
    path = _config(tmp_path, delivered)
    config = json.loads(path.read_text())
    del config["evaluation_pack"]
    _write(path, config)
    with pytest.raises(ValueError, match="evaluation pack set selection"):
        direct_receiver.load_config(path)
    config = json.loads(_config(tmp_path, delivered).read_text())
    config["evaluation_pack"]["sealed_delivery"]["manifest_digest"] = digests[1]
    _write(path, config)
    with pytest.raises(ValueError, match="evaluation pack set selection"):
        direct_receiver.load_config(path)


def test_each_batch_gets_its_own_adapter_and_the_primary_keeps_its_discovery(
    tmp_path, delivered, monkeypatch
):
    from types import SimpleNamespace

    store, commitment, digests = delivered
    prepared = []

    def fake_sealed(root, selection, challenge, *, bound=True):
        digest = selection["sealed_delivery"]["manifest_digest"]
        prepared.append((digest, bound, selection["root"]))
        return (
            "sha256:" + digest[-1] * 64,
            "check-" + digest[-4:],
            "snapshot-" + digest[-4:],
        )

    class Discovery:
        def __init__(self, material, **kwargs):
            self.material, self.kwargs = material, kwargs

    class Adapter:
        def __init__(
            self, discovery, providers, ledger, *, measure_query, copy_hotkey=None
        ):
            self.discovery, self.providers = discovery, providers
            self.ledger, self.measure_query = ledger, measure_query
            self.copy_hotkey = copy_hotkey

    monkeypatch.setattr(direct_receiver, "_sealed_pack", fake_sealed)
    monkeypatch.setattr(direct_receiver, "_delivered_sealed", lambda *_a: True)
    monkeypatch.setattr(
        "carbon.development_session.research_service.DirectFixtureDiscovery", Discovery
    )
    monkeypatch.setattr(
        "carbon.challenge_validator.lean_recipe.LeanRecipeAdapter", Adapter
    )
    cfg = {
        "measure_query": True,
        "receiver_hotkey": HOTKEY,
        "evaluation_pack_set": {
            "store": str(store.root),
            "set_key": commitment["set_key"],
            "batches": digests,
        },
    }
    primary, providers, ledger = object(), object(), object()
    adapters = direct_receiver._set_batch_adapters(
        cfg,
        tmp_path,
        SimpleNamespace(challenge_id=CHALLENGE, version=VERSION),
        {"material": 1},
        primary,
        providers,
        ledger,
    )
    assert list(adapters) == digests
    assert adapters[digests[0]].discovery is primary
    other = adapters[digests[1]].discovery
    assert isinstance(other, Discovery) and other is not primary
    assert other.kwargs["evaluation_pack_digest"] == "sha256:" + digests[1][-1] * 64
    assert other.kwargs["evaluation_pack_sealed"] is True
    assert all(
        a.providers is providers and a.ledger is ledger for a in adapters.values()
    )
    assert all(a.measure_query is True for a in adapters.values())
    # Every batch adapter requires the traceable copy for this receiver.
    assert all(a.copy_hotkey == HOTKEY for a in adapters.values())
    # Only the non-primary batch is prepared, and never from the binding's digest.
    assert prepared == [
        (digests[1], False, str(store.pack_directory(digests[1], CHALLENGE, VERSION)))
    ]
