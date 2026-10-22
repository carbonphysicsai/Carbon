"""E9 for the pack set (E4 option (1)): two hotkeys' copies of a Challenge version's
batches give the same pack set and the same KOTH evaluation keys, because every shared
identity keys on the canonical manifest digest and the copy digests stay local."""

from __future__ import annotations

import pytest
from test_copy_delivery import HOTKEYS, WINDOW, _issue
from test_koth_pack_set import SET_KEY, per_batch

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import copy_delivery as delivery
from carbon.challenge_validator import sealed_pack_import as spi
from carbon.challenge_validator.answer_key import ProducerKey


@pytest.fixture(scope="module")
def producer(tmp_path_factory):
    return ProducerKey.create(str(tmp_path_factory.mktemp("k") / "producer.key"))


def test_two_hotkeys_get_the_same_pack_set_and_the_same_koth_keys(tmp_path, producer):
    # One Challenge version, two batches (the Motor grid and a second draw of it).
    batches, locals_by_hotkey, stores = [], {}, {}
    for n, hotkey in enumerate(HOTKEYS):
        store = spi.SealedPackStore(tmp_path / f"v{n}")
        stores[hotkey], locals_by_hotkey[hotkey] = store, []
        digests = []
        for name in ("motor-grid", "motor-grid"):
            package, (challenge, version, manifest, _files) = _issue(
                producer, name, hotkey
            )
            digests.append(
                delivery.import_copy(store, package, producer.public_key, hotkey=hotkey)
            )
            locals_by_hotkey[hotkey].append(
                package["manifest"]["commitment"]["manifest_digest"]
            )
        batches.append(digests)
    assert batches[0] == batches[1]
    (digest_one,) = set(batches[0])  # the same exam twice: one canonical batch
    # The signed pack set names canonical batches; both stores resolve it.
    second = digest_one
    commitment = spi.set_commitment_for(challenge, version, [digest_one], WINDOW)
    keys = set()
    for hotkey, store in stores.items():
        store.import_pack_set(commitment, spi.set_payload_for(commitment))
        resolved = store.pack_set(commitment["set_key"], challenge, version)
        assert [d for d, _ in resolved] == [digest_one]
        keys.add(commitment["set_key"])
    assert len(keys) == 1
    # KOTH: the set binding and its evaluation key are the same on both machines.
    del second
    evidences = [bp.build_set_evidence(SET_KEY, [per_batch(digest_one)])] * 2
    assert bp.private_evaluation_key(evidences[0]) == bp.private_evaluation_key(
        evidences[1]
    )
    # No hotkey's copy manifest digest is in the shared evidence.
    shared = repr(evidences[0])
    for local in sum(locals_by_hotkey.values(), []):
        if local != digest_one:
            assert local not in shared
