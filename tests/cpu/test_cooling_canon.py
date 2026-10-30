"""Cooling's canonical batch: one canonical form across the plain versions 1.1-1.4, and the custody builder takes that batch as
the plain A batch for the pool version 1.6 (the same route as Motor's test_motor_canon.py). Offline, on the synthetic sealed
grid the Cooling pool-pack tests use: no re-solve, no production value."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_pack_cooling import COOLING, batch, material  # noqa: E402,F401

from carbon.scoring import copy_package  # noqa: E402
from carbon.scoring import sealed_batch_source as source  # noqa: E402

PLAIN_VERSIONS = ("1.1", "1.2", "1.3", "1.4")


def _builder():
    path = REPOSITORY / "scripts/dev/sealed_exam/pool_pack.py"
    spec = importlib.util.spec_from_file_location("pool_pack_script_cooling_canon", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical(batch, version):
    document, records = batch
    return copy_package.canonical_batch(COOLING, version, document, records)


def test_one_canonical_form_across_the_plain_versions(batch):
    seen = {v: _canonical(batch, v) for v in PLAIN_VERSIONS}
    forms = {(hashlib.sha256(raw).hexdigest(), canonical_fp) for raw, _source_fp, canonical_fp in seen.values()}
    assert len(forms) == 1, {v: (hashlib.sha256(r).hexdigest()[:12], c[:19]) for v, (r, _s, c) in seen.items()}
    assert len({source_fp for _raw, source_fp, _c in seen.values()}) == 1  # one custody batch in


def test_the_canonical_batch_is_deterministic(batch):
    assert _canonical(batch, "1.4") == _canonical(batch, "1.4")


def test_the_builder_accepts_the_canonical_batch_as_the_plain_a_batch_for_1_6(batch, tmp_path):
    raw, _source_fp, _canonical_fp = _canonical(batch, "1.4")
    plain = tmp_path / "canonical"
    plain.mkdir()
    (plain / source.SEALED_BATCH_FILE).write_bytes(raw)
    carried = source.read_batch(plain)
    assert carried is not None and "pool" not in carried[0]
    out = tmp_path / "out"
    built = _builder().build(
        challenge=COOLING,
        version="1.6",
        batch_dir=plain,
        out_dir=out,
        inference_image_id="sha256:" + "1" * 64,
        material=material("1.6"),
    )
    assert built["rows"]["cells"] == len(batch[0]["cases"]) == 16 and built["rows"]["pool"] > 0
    assert (out / "pack" / "evaluation-pack.json").is_file()
