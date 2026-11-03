"""A crown-averaging seed reaches a GRAPH rebuild's build child (Validator 05:16, TL 05:10: the F08 graph king's 10 rebuilds came
out identical, sd 0). The seed is set on the host task (`set_rebuild_seed`) and handed to the worker
(`research_tasks`: ``seed=self._seed_for(task_id)``). The worker must write exactly that seed into the build child's
``control.json``, which the child passes to ``model.fit``. That leg is pinned here with the REAL worker program for the served
F08 and F02 graph routes: a non-zero seed is the one written, two seeds give two control files, and nothing else in the staged
child changes. Whether a seed changes the trained state is the recipe's: the default recipe's key-using init gives different
params at seeds 7 and 8 (test_f08_f02_graph_adapters); a recipe whose init ignores its key, at train_fraction 1 and full batch,
rebuilds identically at any seed.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_kit import physical_material
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session.profile import canonical

posix = pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")


class _Captured(Exception):
    pass


def _staged_files(key, seed, tmp_path):
    from test_f08_f02_graph_adapters import PUBLIC, _binding, _case, _image, adapter

    recipe, raw_manifest, files, staging = _case(key, {"steps": 16})
    material = physical_material.bundle_material(*key)
    captured = {}

    def runner(_ledger, *, source, files, **_kwargs):
        captured.update(files)
        raise _Captured

    with pytest.raises(_Captured):
        worker.reconstruct_and_infer_graph_public(
            SimpleNamespace(root=tmp_path),
            owner="test",
            identity=f"seed-{seed}",
            image=_image(),
            recipe=recipe,
            challenge_binding=_binding(key),
            limits_document=PUBLIC[key[0]].construction_limits_document(*key),
            source_envelope=canonical(staging.envelope(raw_manifest, files)),
            train=material["train"],
            inputs=np.ascontiguousarray(material["practice_inputs"]),
            expected_output_shape=tuple(material["expected_output_shape"]),
            allowlist_bytes=adapter.served_allowlist_bytes(*key),
            seed=seed,
            runner=runner,
            adapter_id=adapter.SPECS[key].adapter_id,
        )
    return captured


@posix
@pytest.mark.parametrize("key", [("f08-ribbed-bracket", "1.4"), ("f02", "2.3")])
def test_the_averaging_seed_is_the_one_the_build_child_fits_with(key, tmp_path):
    first = _staged_files(key, 424242, tmp_path / "a")
    second = _staged_files(key, 7, tmp_path / "b")
    assert json.loads(first["control.json"])["seed"] == 424242
    assert json.loads(second["control.json"])["seed"] == 7
    # the seed is the only staged difference between the two rebuilds
    assert {n for n in first if first[n] != second.get(n)} == {"control.json"}
    a, b = (json.loads(f["control.json"]) for f in (first, second))
    assert {k for k in a if a[k] != b[k]} == {"seed"}
    # and the child program reads it into the fit, not the official 0
    program = worker.PHYSICAL_BUILD_PROGRAM
    assert 'seed=control["seed"]' in program
