"""Motor 1.9's public TRAIN (Lead audit #18): Motor 1.8's 194 rows unchanged + magnet_min_b_t at column 240.

No npz is committed: the loader derives the TRAIN from Motor 1.8's TRAIN and the pinned magnet table and writes it with
the canonical writer; those bytes are pinned and equal exam-motor's train241 PUBLIC run (release, RECEIPTS 4465).
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from carbon.challenge_kit import physical_public_train as ppt
from carbon.motor import row19

MOTOR = "electric-motor-magnetics"
NAME = "motor-dev-train-1p9-v1"


def test_the_1p9_train_is_1p8_plus_the_magnet_column():
    got = ppt.load_extended_train(NAME, MOTOR)
    base = ppt.load_extended_train("motor-dev-train-1p8-v1", MOTOR)
    assert got["targets"].shape == (194, row19.WIDTH) == (194, 241)
    assert np.array_equal(got["inputs"], base["inputs"])
    assert np.array_equal(got["targets"][:, :240], base["targets"])
    assert got["case_ids"] == base["case_ids"]
    table = json.loads((ppt._DATA / "motor-dev-train-1p9-magnet-v1.json").read_bytes())
    assert got["targets"][:, 240].tolist() == [
        table[str(i)]["scalar"] for i in range(194)
    ]
    assert hashlib.sha256(got["train"]).hexdigest() == (
        ppt.MAGNET_TRAIN[NAME]["train_sha256"]
    )
    layout = got["provenance"]["numeric_interface"]
    assert layout["target_slices"]["magnet_min_b_t"] == [240, 241]
    assert layout["target_units"]["magnet_min_b_t"] == "tesla"
    assert list(layout["target_slices"]) == list(row19.ROW)


def test_the_1p9_train_is_never_a_fresh_or_extended_train():
    with pytest.raises(ValueError):
        ppt._fresh(NAME, MOTOR)
    with pytest.raises(ValueError):
        ppt._magnet(NAME, "chip-cold-plate")


def _table():
    return json.loads((ppt._DATA / "motor-dev-train-1p9-magnet-v1.json").read_bytes())


@pytest.mark.parametrize(
    "edit",
    [
        lambda t: t.pop("193"),
        lambda t: t.__setitem__("0", {"scalar": None}),
        lambda t: t.__setitem__("0", {"scalar": 1}),
        lambda t: t.__setitem__("194", {"scalar": 0.5}),
    ],
)
def test_a_magnet_table_other_than_the_pinned_one_refuses(edit, monkeypatch):
    table = _table()
    edit(table)
    raw = json.dumps(table).encode()
    # The identity pin refuses first; with the pin moved to the edited bytes, the row check still refuses.
    with pytest.raises(ValueError, match="identity differs"):
        ppt.derive_motor19_public_train(NAME, raw)
    spec = {**ppt.MAGNET_TRAIN[NAME], "magnet_sha256": hashlib.sha256(raw).hexdigest()}
    monkeypatch.setitem(ppt.MAGNET_TRAIN, NAME, spec)
    with pytest.raises(ValueError, match="rows differ"):
        ppt.derive_motor19_public_train(NAME, raw)


def test_no_npz_is_committed_and_a_moved_pin_refuses(monkeypatch):
    # the TRAIN is derived at load and written by the canonical writer (no npz payload in the tree, cauth1 invariant);
    # its bytes are the release run's 095a3ef0
    assert not (ppt._DATA / f"{NAME}.npz").exists()
    got = ppt.load_extended_train(NAME, MOTOR)
    assert got["train"] == ppt._npz(got["inputs"], got["targets"])
    spec = {**ppt.MAGNET_TRAIN[NAME], "train_sha256": "0" * 64}
    monkeypatch.setitem(ppt.MAGNET_TRAIN, NAME, spec)
    with pytest.raises(ValueError, match="differs from its sources"):
        ppt.load_extended_train(NAME, MOTOR)
