"""X-1: a version-scoped ADMISSION class vocabulary for the coverage plan (Carbon Validator-C, COOL18_CELL_CLASS_RULING
b98e6e19 section 3).

A version that registers ``optimizer.coverage_class_vocabulary`` in the pool constants grades only with a coverage plan
whose classes are exactly those registered names; every version that registers none keeps the geometric-v1 check
unchanged (the guard EXTENDED, not loosened). The labels are read from the registration; no grader module types them.
Synthetic labels only: no registered version's vocabulary is typed here.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_multiclass_regions import (
    BIG,
    SMALL,
    _plan_and_sums,
    plan_document,
    sha,
    sums_text,
)

from carbon.scoring import pool_exam, pool_grader, pool_version
from carbon.scoring.pool_grader import PoolRefused, coverage_plan
from tests.cpu.test_pool_grader import HONESTY

# Synthetic admission labels (not geometric-v1 names, not any registered version's labels).
ADM_A, ADM_B = "fixture-adm-1", "fixture-adm-2"


def _admission_plan(classes=(ADM_A, ADM_B)):
    """The two-target fixture plan re-labelled with admission labels, its SUMS, and a policy set registering them."""
    sets, _document, _sums, _plan, registered = _plan_and_sums()
    document = plan_document(list(classes), {"big0": classes[0], "small0": classes[-1]})
    plan = coverage_plan(document)
    sums = sums_text("c" * 64, plan.sha256)
    policies = dataclasses.replace(
        registered,
        optimizer=dataclasses.replace(
            registered.optimizer,
            coverage_plan_sha256=plan.sha256,
            coverage_plan_sums_sha256=sha(sums),
            coverage_class_vocabulary=tuple(classes),
        ),
    )
    return sets, document, sums, plan, policies


def _with_vocabulary(policies, vocabulary):
    return dataclasses.replace(
        policies,
        optimizer=dataclasses.replace(
            policies.optimizer, coverage_class_vocabulary=vocabulary
        ),
    )


def test_a_registered_vocabulary_admits_exactly_its_labels():
    sets, document, sums, plan, policies = _admission_plan()
    attached = pool_exam.attach_coverage_plan(policies, document, sums, sets)
    assert attached.optimizer.coverage_plan == plan
    assert attached.optimizer.coverage_plan.classes == (ADM_A, ADM_B)


def test_without_a_vocabulary_admission_labels_still_refuse():
    """The guard extended, not loosened: the same admission-labelled plan, registered WITHOUT a vocabulary, refuses."""
    sets, document, sums, _plan, policies = _admission_plan()
    with pytest.raises(
        pool_exam.ExamRefused, match="coverage_plan_class_not_geometric_v1"
    ):
        pool_exam.attach_coverage_plan(
            _with_vocabulary(policies, None), document, sums, sets
        )


@pytest.mark.parametrize(
    "vocabulary",
    [
        (ADM_A,),  # the plan has a label the registration does not name
        (
            ADM_A,
            ADM_B,
            "fixture-adm-3",
        ),  # the registration names a label the plan lacks
        (BIG, SMALL),  # other names entirely
    ],
)
def test_a_plan_off_the_registered_vocabulary_refuses(vocabulary):
    sets, document, sums, _plan, policies = _admission_plan()
    with pytest.raises(
        pool_exam.ExamRefused,
        match="coverage_plan_classes_are_not_the_registered_vocabulary",
    ):
        pool_exam.attach_coverage_plan(
            _with_vocabulary(policies, vocabulary), document, sums, sets
        )


def test_a_vocabulary_version_never_consults_the_geometric_predicate(monkeypatch):
    """With a vocabulary the registration alone decides the class names."""
    sets, document, sums, plan, policies = _admission_plan()

    def never(classes):
        raise AssertionError("geometric-v1 check consulted for a vocabulary version")

    monkeypatch.setattr(pool_exam, "geometric_v1_names_valid", never)
    attached = pool_exam.attach_coverage_plan(policies, document, sums, sets)
    assert attached.optimizer.coverage_plan == plan


@pytest.mark.parametrize(
    "vocabulary",
    [(), (ADM_A, ADM_A), (ADM_A, ""), [ADM_A, ADM_B], (ADM_A, 1)],
)
def test_the_policy_check_refuses_a_malformed_vocabulary(vocabulary):
    *_rest, policies = _admission_plan()
    optimizer = dataclasses.replace(
        policies.optimizer, coverage_class_vocabulary=vocabulary
    )
    with pytest.raises(
        PoolRefused, match="coverage_class_vocabulary_must_be_unique_names"
    ):
        pool_grader._check_policies(optimizer, HONESTY)


def test_the_policy_check_refuses_a_vocabulary_without_a_coverage_plan():
    *_rest, policies = _admission_plan()
    planless = dataclasses.replace(
        policies.optimizer,
        d_aggregate=None,
        coverage_plan_sha256=None,
        coverage_plan_sums_sha256=None,
    )
    pool_grader._check_policies(
        dataclasses.replace(planless, coverage_class_vocabulary=None), HONESTY
    )
    with pytest.raises(
        PoolRefused, match="coverage_class_vocabulary_needs_a_registered_coverage_plan"
    ):
        pool_grader._check_policies(planless, HONESTY)


# --- the registration ----------------------------------------------------------------------------------------------------

#: A fully registered row, used only as a synthetic base written to a temp file under a fixture id.
ROW = "chip-cold-plate 1.6"


def _write(tmp_path, mutate):
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    entry = copy.deepcopy(document["versions"][ROW])
    mutate(entry["optimizer"])
    document["versions"] = {"fixture-challenge 9.9": entry}
    path = tmp_path / "pool_constants.json"
    path.write_bytes(json.dumps(document).encode())
    return path


def _with_plan(optimizer, **extra):
    optimizer.update(
        coverage_plan_sha256="a" * 64, coverage_plan_sums_sha256="b" * 64, **extra
    )


def test_the_registration_absent_is_none_and_present_is_read_as_a_tuple(tmp_path):
    absent = _write(tmp_path, _with_plan)
    policies = pool_version.registered_policies("fixture-challenge", "9.9", path=absent)
    assert policies.optimizer.coverage_class_vocabulary is None
    present = _write(
        tmp_path, lambda o: _with_plan(o, coverage_class_vocabulary=[ADM_A, ADM_B])
    )
    policies = pool_version.registered_policies(
        "fixture-challenge", "9.9", path=present
    )
    assert policies.optimizer.coverage_class_vocabulary == (ADM_A, ADM_B)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "HUMAN_INPUT",
        [],
        [ADM_A, ADM_A],
        [ADM_A, ""],
        ADM_A,
        [ADM_A, 2],
        {"a": ADM_A},
    ],
)
def test_a_malformed_or_unset_registration_refuses(tmp_path, value):
    path = _write(tmp_path, lambda o: _with_plan(o, coverage_class_vocabulary=value))
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version.registered_policies("fixture-challenge", "9.9", path=path)


def test_a_registration_without_a_coverage_plan_refuses(tmp_path):
    path = _write(
        tmp_path, lambda o: o.update(coverage_class_vocabulary=[ADM_A, ADM_B])
    )
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version.registered_policies("fixture-challenge", "9.9", path=path)


def test_no_grader_module_types_a_registered_admission_label():
    """The labels live in the registration only: no grader module names a registered admission label literal."""
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    labels = set()
    for entry in document["versions"].values():
        optimizer = (
            entry.get("optimizer") if type(entry.get("optimizer")) is dict else {}
        )
        vocabulary = optimizer.get("coverage_class_vocabulary")
        if type(vocabulary) is list:
            labels |= {label for label in vocabulary if type(label) is str}
    for module in (pool_exam, pool_grader, pool_version):
        text = inspect.getsource(module)
        for label in labels:
            for quoted in (f'"{label}"', f"'{label}'"):
                assert quoted not in text, (module.__name__, label)
