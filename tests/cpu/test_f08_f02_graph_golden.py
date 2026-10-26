"""F08 1.4 / F02 2.3 graph route golden (the Validator's condition 1 on
Battery's graph adapter, 2026-10-23): the receiver's graph worker changed, so
F08's and F02's graph predictions and dev grades must be byte-identical before
(8a3426ca7; on the round 11b line 7731e4413) and after it.

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
#: The shared Level 4 modules allowlist v8 moved (OWNER-GRAPH-OPS-OPEN-01): new op kinds,
#: nested control-flow graphs, constant accounting v5, stripped debug ops and the
#: init rule, every one gated on a v8 document or allowlist. F08 1.4 and F02 2.3 serve v7
#: and behave exactly as recorded (the byte-identity of the recorded runs' states,
#: predictions and grades above); their staged copies of these files are newer. A
#: pre-publish move, named here so the next unintended one still fails.
V8_MOVED = {
    "carbon.development_session.bundle_graph_state.py",
    "carbon.level4.allowlist.py",
    "carbon.level4.graph.py",
    "carbon.level4.interpret.py",
    "carbon.level4.params.py",
    "carbon.level4.tooling.lower_jax.py",
    "carbon.level4.tooling.lower_torch.py",
    "carbon.level4.train.py",
    "carbon.level4.loss.py",
    "carbon.level4.validate.py",
}
#: The served backbone catalog digest the recorded runs were made under (rc6
#: a454e75e5). The catalog freeze moved it for these two versions
#: (OWNER-CATALOG-LICENCES-01 relicense, 08c1465a9), which moves the kit's
#: construction limits digest and so the staged recipe and control files. The
#: test puts the old catalog digest back: everything else must be byte-identical.
RC6_CATALOG = {
    ("f08-ribbed-bracket", "1.4"): (
        "sha256:b934bba02176ec06593e5cb77cea312298fbc83fd0e840153b9f7330bc0b38b3"
    ),
    ("f02", "2.3"): (
        "sha256:2ff8b82da0f552f26e2797fa865cd023e638b329adb15f5ce5ac8bc1ba7171b0"
    ),
}
#: The inference child's one staged difference on the round 11b line: the TRAIN
#: codec accepts every served Battery version (it decodes Battery TRAIN only).
INFER_CHANGED = "carbon.development_session.construction_tensor_codec.py"
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
        assert infer_before["source"] == infer_after["source"]
        changed_infer = {
            name
            for name in set(infer_before["files"]) | set(infer_after["files"])
            if infer_before["files"].get(name) != infer_after["files"].get(name)
        }
        assert changed_infer <= {INFER_CHANGED}
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
def test_the_build_child_and_programs_are_the_golden_ones(key, tmp_path, monkeypatch):
    from test_f08_f02_graph_adapters import PUBLIC, _binding, _case, _image, adapter

    from carbon.backbone_catalog import served

    served_digest = served.digest
    assert served_digest(*key) != RC6_CATALOG[key]  # the freeze moved it
    monkeypatch.setattr(
        served,
        "digest",
        lambda cid, version: (
            RC6_CATALOG[key] if (cid, version) == key else served_digest(cid, version)
        ),
    )

    # The recorded runs predate the large-profile publication (a separate move,
    # pinned by test_published_policy_is_enforced): the kit, its check and the
    # runner argument are put back on the earlier profile together.
    from carbon.challenge_kit import served_versions

    monkeypatch.setattr(served_versions, "worker_resources", lambda *_: None)
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
    unchanged = lambda files: {  # noqa: E731
        n: d for n, d in files.items() if n != CHANGED and n not in V8_MOVED
    }
    assert unchanged(captured["files"]) == unchanged(golden[0]["files"])
    assert V8_MOVED >= {
        n
        for n in set(captured["files"]) | set(golden[0]["files"])
        if captured["files"].get(n) != golden[0]["files"].get(n)
    } - {CHANGED}
    assert _sha(worker.PHYSICAL_INFER_PROGRAM.encode()) == golden[1]["source"]
