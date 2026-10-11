"""EVIDENCE-ENTRYPOINTS-01, f02: registered decks, TRAIN draw, image pin and
the kit TRAIN format (checked with the f02 kit's own loader)."""

from __future__ import annotations

import collections
import json
import subprocess
from pathlib import Path

import pytest

from scripts.dev.evidence_runs import common, f02

ROOT = Path(__file__).resolve().parents[2]


def test_train_draw_is_registered_disjoint_and_deterministic():
    draws = f02.train_draws()
    assert len(draws) == 960 and draws == f02.train_draws()
    per = collections.Counter(c for c, *_ in draws)
    assert len(per) == 24 and set(per.values()) == {40}
    assert not {(p, d) for _, _, p, d in draws} & f02.MENU_POINTS
    assert all(80 <= p <= 140 and 5 <= d <= 20 for _, _, p, d in draws)


def test_registered_train_manifest_matches_the_draw():
    manifest = json.loads((ROOT / f02.MANIFESTS["train"]).read_text())["cases"]
    assert [(e["context"], e["peak_w"], e["on_time_s"]) for e in manifest] == [
        (c, p, d) for c, _, p, d in f02.train_draws()
    ]


def test_check_refuses_an_unregistered_manifest(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(common.Refused) as refused:
        f02.check("train", tmp_path, inspect=lambda r: None)
    assert refused.value.code == "PLAN_SHA256_MISMATCH"


def _inspect(image_id, digests=()):
    body = json.dumps([{"Id": image_id, "RepoDigests": list(digests)}])
    return lambda ref: subprocess.CompletedProcess([], 0, body, "")


def test_image_pin_accepts_only_the_pinned_digest():
    common.require_image("x", f02.IMAGE_DIGEST, _inspect(f02.IMAGE_DIGEST))
    with pytest.raises(common.Refused) as refused:
        common.require_image("x", f02.IMAGE_DIGEST, _inspect("sha256:" + "0" * 64))
    assert refused.value.code == "IMAGE_DIGEST_MISMATCH"
    with pytest.raises(common.Refused):
        common.require_image(
            "x",
            f02.IMAGE_DIGEST,
            lambda r: subprocess.CompletedProcess([], 1, "", "no such image"),
        )


def test_train_records_load_in_the_f02_kit():
    arm = pytest.importorskip("carbon.development_comparison.carbon_arm")
    kit = pytest.importorskip("carbon.development_comparison.f02_kit").KIT
    rows = []
    for i, (ctx, base, peak, on) in enumerate(f02.train_draws()[:6]):
        entry = {
            "case": f"{ctx}-p{peak:g}-d{on:g}-train",
            "peak_w": peak,
            "on_time_s": on,
        }
        rows.append(
            f02.train_record(
                entry, base, {"peak_top_c": 90.0 + i, "extra_energy_j": 100.0 * (i + 1)}
            )
        )
    data = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
    train = arm.load_train(kit, data, arm.sha256(data))
    assert len(train.records) == 6
