"""F08 1.4 / F02 2.3 graph route golden (the Validator's condition 1 on
Battery's graph adapter, 2026-10-23): the receiver's graph worker changed, so
F08's and F02's graph predictions and dev grades must be byte-identical before
(8a3426ca7) and after it.

The recorded evidence (`docs/development/evidence/battery22-graph-adapter-
20261023/f08-f02-graph-golden.json`) holds both runs: states, predictions and
dev grades identical. This test pins what determines them, independently of
the machine: each child's exact program and every staged build input equal the
before run's. The one staged difference is `build_refusal.py`, which gained
Battery's graph refusal codes; it only classifies a refusal."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_kit import physical_material
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session.profile import canonical

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (
    ROOT
    / "docs/development/evidence/battery22-graph-adapter-20261023"
    / "f08-f02-graph-golden.json"
)
CHANGED = "carbon.development_session.build_refusal.py"
posix = pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _evidence():
    return json.loads(EVIDENCE.read_bytes())


def test_the_recorded_runs_are_byte_identical_before_and_after():
    evidence = _evidence()
    before, after = evidence["before"]["runs"], evidence["after"]["runs"]
    assert set(before) == set(after) == {"f08-ribbed-bracket@1.4", "f02@2.3"}
    for key in before:
        for field in ("state", "predictions", "dev_grade", "aggregate_error"):
            assert before[key][field] == after[key][field], (key, field)
        build_before, infer_before = before[key]["children"]
        build_after, infer_after = after[key]["children"]
        assert infer_before == infer_after
        assert build_before["source"] == build_after["source"]
        changed = {
            name
            for name in set(build_before["files"]) | set(build_after["files"])
            if build_before["files"].get(name) != build_after["files"].get(name)
        }
        assert changed == {CHANGED}


class _Captured(Exception):
    pass


@posix
@pytest.mark.parametrize("key", [("f08-ribbed-bracket", "1.4"), ("f02", "2.3")])
def test_the_build_child_and_programs_are_the_golden_ones(key, tmp_path):
    from test_f08_f02_graph_adapters import PUBLIC, _binding, _case, _image, adapter

    golden = _evidence()["before"]["runs"]["@".join(key)]["children"]
    recipe, raw_manifest, files, staging = _case(key, {"steps": 16})
    material = physical_material.bundle_material(*key)
    captured = {}

    def runner(_ledger, *, source, files, **_kwargs):
        captured.update(
            source=_sha(source.encode()),
            files={name: _sha(body) for name, body in files.items()},
        )
        raise _Captured

    with pytest.raises(_Captured):
        worker.reconstruct_and_infer_graph_public(
            SimpleNamespace(root=tmp_path),
            owner="test",
            identity="test",
            image=_image(),
            recipe=recipe,
            challenge_binding=_binding(key),
            limits_document=PUBLIC[key[0]].construction_limits_document(*key),
            source_envelope=canonical(staging.envelope(raw_manifest, files)),
            train=material["train"],
            inputs=np.ascontiguousarray(material["practice_inputs"]),
            expected_output_shape=tuple(material["expected_output_shape"]),
            allowlist_bytes=adapter.served_allowlist_bytes(*key),
            seed=0,
            runner=runner,
            adapter_id=adapter.SPECS[key].adapter_id,
        )
    assert captured["source"] == golden[0]["source"]
    assert {n: d for n, d in captured["files"].items() if n != CHANGED} == {
        n: d for n, d in golden[0]["files"].items() if n != CHANGED
    }
    assert _sha(worker.PHYSICAL_INFER_PROGRAM.encode()) == golden[1]["source"]
