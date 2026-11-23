"""Motor 1.9's public TRAIN (Lead audit #18): Motor 1.8's 194 rows unchanged + magnet_min_b_t at column 240.

The served npz is exam-motor's train241 PUBLIC run bytes (release, RECEIPTS 4465); the loader re-derives its arrays from
Motor 1.8's TRAIN and the pinned magnet table and refuses any difference.
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


def test_a_served_npz_that_differs_from_its_sources_refuses(tmp_path, monkeypatch):
    for name in (
        "motor-dev-train-1p8-v1.npz",
        "motor-dev-train-1p8-v1.provenance.json",
        "motor-dev-train-1p8-v1.source.jsonl",
        "motor-dev-train-1p9-magnet-v1.json",
    ):
        (tmp_path / name).write_bytes((ppt._DATA / name).read_bytes())
    good = ppt.load_extended_train(NAME, MOTOR)
    targets = np.array(good["targets"])
    targets[0, 240] += 1e-9
    raw = ppt._npz(np.asarray(good["inputs"]), targets)
    (tmp_path / f"{NAME}.npz").write_bytes(raw)
    monkeypatch.setattr(ppt, "_EXTENDED_DATA", tmp_path)
    with pytest.raises(ValueError, match="identity differs"):
        ppt.load_extended_train(NAME, MOTOR)
    spec = {**ppt.MAGNET_TRAIN[NAME], "train_sha256": hashlib.sha256(raw).hexdigest()}
    monkeypatch.setitem(ppt.MAGNET_TRAIN, NAME, spec)
    with pytest.raises(ValueError, match="differs from its sources"):
        ppt.load_extended_train(NAME, MOTOR)
