"""An accuracy-only target may be declared OUT OF RANGE with no shell (mc-exam-C, Thu 12 Nov; the conformance tool's STOP).

Motor 1.8's H-1 class holds shelled (extended) targets and the 13 inner-band rows, which are unshelled by a CV ruling: no
shell-mode check, because they lie past TRAIN but inside the OOD shell's inner half. ``extended`` was defined as "has
a shell", so those 13 read as in range. `pool_physics_score.class_ranges` then refused H-1 as a mixed class, and every
1.8 grade refused at `pool_exam.attach_physics`.

Claims:
- ``build_accuracy_target(extended=True)`` makes an unshelled target extended. The flag is part of its identity, but
  only when set: every target built without it keeps its digest and document byte for byte.
- The flag never rides with a shell (one form), is a bool, and round-trips through `dump_pool` / `load_pool` and the
  pool source (`pool_plugin.spec_from_source`). A document carrying ``"extended": false`` refuses (never ignored).
- A class of shelled targets plus declared-extended unshelled targets is ONE out-of-range class. A class mixing shelled
  with plain unshelled targets still refuses, so the rule itself is unchanged.

Every target and value here is a SYNTHETIC fixture (the toy targets of test_pool_plugin).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_pool_exam import toy_binding
from test_pool_plugin import SHELL, toy_target

from carbon.scoring import pool_grader, pool_plugin
from carbon.scoring import pool_physics_score as pps


def _acc(target_id, seed, *, shell=None, extended=None):
    base = toy_target(target_id, seed, shell=SHELL)
    kwargs = {} if extended is None else {"extended": extended}
    return pool_grader.build_accuracy_target(
        target_id=target_id,
        conditions=base.conditions,
        outputs=base.outputs,
        u=base.u,
        box=base.box,
        designs=[list(base.designs[i]) for i in base.agen],
        truths=[dict(base.truths[i]) for i in base.agen],
        shell=shell,
        **kwargs,
    )


def _plan(by_class):
    return pool_grader.coverage_plan(
        {
            "schema": "carbon.pool.coverage-plan.v1",
            "classes": sorted(by_class),
            "targets": {s.target_id: c for c, specs in by_class.items() for s in specs},
        }
    )


def test_without_the_flag_nothing_changes():
    plain = _acc("p0", 3)
    explicit_false = _acc("p0", 3, extended=False)
    assert not plain.extended and not plain.declared_extended
    assert plain.digest == explicit_false.digest
    assert "extended" not in pool_grader.dump_pool(plain)


def test_a_declared_extended_target_is_extended_and_its_identity_says_so():
    plain = _acc("x0", 4)
    declared = _acc("x0", 4, extended=True)
    assert declared.extended and declared.declared_extended and declared.shell is None
    assert declared.digest != plain.digest
    document = pool_grader.dump_pool(declared)
    assert document["extended"] is True
    back = pool_grader.load_pool(json.loads(json.dumps(document)))
    assert back.extended and back.digest == declared.digest


def test_the_flag_is_one_form_a_bool_and_never_false_in_a_document():
    with pytest.raises(
        pool_grader.PoolRefused, match="a_shelled_target_is_already_extended"
    ):
        _acc("s0", 5, shell=SHELL, extended=True)
    with pytest.raises(pool_grader.PoolRefused, match="extended_must_be_a_bool"):
        _acc("s1", 5, extended=1)
    document = pool_grader.dump_pool(_acc("s2", 5, extended=True))
    with pytest.raises(
        pool_grader.PoolRefused, match="accuracy_only_pool_document_malformed"
    ):
        pool_grader.load_pool({**document, "extended": False})


def test_the_pool_source_carries_the_flag():
    base = toy_target("ps0", 6, shell=SHELL)
    source = {
        "design_names": list(toy_binding().design_names),
        "target_id": "ps0",
        "conditions": base.conditions,
        "accuracy_only": True,
        "outputs": list(base.outputs),
        "u": base.u,
        "box": [list(b) for b in base.box],
        "designs": [list(base.designs[i]) for i in base.agen],
        "truths": [dict(base.truths[i]) for i in base.agen],
    }
    assert not pool_plugin.spec_from_source(source, toy_binding()).extended
    spec = pool_plugin.spec_from_source({**source, "extended": True}, toy_binding())
    assert spec.extended and spec.declared_extended
    with pytest.raises(pool_plugin.PluginRefused):
        pool_plugin.spec_from_source({**source, "extended": False}, toy_binding())


def test_shelled_plus_declared_extended_is_one_out_of_range_class():
    shelled = [_acc(f"h{i}", 10 + i, shell=SHELL) for i in range(3)]
    inner = [_acc(f"i{i}", 20 + i, extended=True) for i in range(2)]
    specs = shelled + inner
    assert pps.class_ranges(specs, _plan({"H-1": specs})) == {"H-1": pps.OUT_OF_RANGE}


def test_shelled_plus_plain_unshelled_still_refuses():
    shelled = [_acc(f"h{i}", 30 + i, shell=SHELL) for i in range(3)]
    inner = [_acc(f"i{i}", 40 + i) for i in range(2)]
    specs = shelled + inner
    with pytest.raises(
        pool_grader.PoolRefused,
        match="physics_class_mixes_in_range_and_out_of_range_targets",
    ):
        pps.class_ranges(specs, _plan({"H-1": specs}))


def test_the_flag_on_any_other_target_refuses_never_ignored():
    """CV-Motor-C E-1: only an accuracy-only target may carry it; a multi-design pool document or source refuses."""
    multi = toy_target("m0", 3)
    with pytest.raises(
        pool_grader.PoolRefused, match="extended_flag_is_for_accuracy_only_targets"
    ):
        pool_grader.load_pool({**pool_grader.dump_pool(multi), "extended": True})
    source = {
        "design_names": list(toy_binding().design_names),
        "target_id": multi.target_id,
        "conditions": multi.conditions,
        "objective": multi.objective,
        "sense": "max",
        "limits": [],
        "u": multi.u,
        "box": [list(b) for b in multi.box],
        "designs": [list(d) for d in multi.designs],
        "truths": [dict(t) for t in multi.truths],
        "extended": True,
    }
    with pytest.raises(
        pool_plugin.PluginRefused, match="extended_flag_is_for_accuracy_only_targets"
    ):
        pool_plugin.spec_from_source(source, toy_binding())


def test_every_other_reader_of_extended_sees_the_declared_target_out_of_range():
    """CV-Motor-C E-3: the grader's other readers go through the same property. The plan names the region class (never
    the 'extended_shell' fallback), the A_gen buckets accept its reserved slice, and a plain unshelled one still refuses
    there."""
    shelled = [_acc(f"h{i}", 50 + i, shell=SHELL) for i in range(2)]
    declared = _acc("d0", 60, extended=True)
    plan = _plan({"H-1": [*shelled, declared]})
    assert pool_grader.region_class(declared, plan) == "H-1"
    assert pool_grader.region_class(declared) == "extended_shell"
    pool_grader.agen_buckets([*shelled, declared], plan, 1)
    plain = _acc("d1", 61)
    with pytest.raises(
        pool_grader.PoolRefused, match="a_gen_slice_on_an_in_range_target"
    ):
        pool_grader.agen_buckets(
            [*shelled, plain], _plan({"H-1": [*shelled, plain]}), 1
        )
