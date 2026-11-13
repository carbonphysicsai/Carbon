"""B1 option (a): the geometric-v1 class rule lives in ONE module, byte-for-byte the receipted code (CV-B V1/V2,
Validator-2B A-1..A-3, 11 Nov).

Claims:
- (i) `klass` is the receipted function: its source text has the sha256 of probe_set.py rev 4's `klass` (both pinned);
- (ii) `klass` reaches all 4 branches on a synthetic region, including the 1e-12 edges;
- (iii) `names_valid` accepts exactly the 4 forms and refuses anything else (no fallback);
- (iv) the guard is EXTENDED: no class-name literal of the rule appears in any carbon/scoring module but this one;
- pool_exam's check only delegates to it.

The region and inputs are SYNTHETIC.
"""

from __future__ import annotations

import hashlib
import inspect
import pkgutil
from pathlib import Path

import pytest

from carbon import scoring
from carbon.scoring import geometric_v1, pool_exam

#: sha256 of the receipted `klass` text: probe_set.py rev 4 (SEP_PROBE_SETS_REV4_20261101, file sha256 7464f4a4...), from
#: its ``def klass(`` line through its last line, with the final newline.
RECEIPTED_KLASS_SHA256 = (
    "62d344890162f5c3292ea77362c4b7cfeaff2d1bf7f757e7199838c2600e5ef2"
)

REGION = {
    "base": {"a": [0.0, 1.0], "b": [10.0, 20.0]},
    "extended": {"a": [-1.0, 3.0], "b": [5.0, 30.0]},
}
NAMES = ("a", "b")


def test_klass_is_byte_for_byte_the_receipted_function():
    source = inspect.getsource(geometric_v1.klass)
    assert hashlib.sha256(source.encode()).hexdigest() == RECEIPTED_KLASS_SHA256
    assert geometric_v1.INNER == 0.5 and geometric_v1.RULE == "geometric-v1"


@pytest.mark.parametrize(
    "inputs, expected",
    [
        ({"a": 0.5, "b": 15.0}, "in_train"),
        (
            {"a": 1.0 + 0.9e-12, "b": 10.0 - 0.9e-12},
            "in_train",
        ),  # inside the 1e-12 edge
        (
            {"a": 1.5, "b": 15.0},
            "regime:inner_band",
        ),  # a beyond base, inside base + 0.5 x extension (2.0)
        ({"a": 2.0, "b": 7.5}, "regime:inner_band"),  # both at the inner band's edges
        ({"a": 2.5, "b": 15.0}, "regime:side_a_high"),
        ({"a": -0.6, "b": 15.0}, "regime:side_a_low"),
        ({"a": 0.5, "b": 26.0}, "regime:side_b_high"),
        ({"a": 0.5, "b": 7.4}, "regime:side_b_low"),
        ({"a": 2.5, "b": 26.0}, "extended_shell"),  # two inputs outside the inner band
        (
            {"a": 1.5, "b": 26.0},
            "extended_shell",
        ),  # two outside TRAIN, one beyond the band
    ],
)
def test_klass_reaches_every_branch(inputs, expected):
    assert geometric_v1.klass(REGION, NAMES, inputs) == expected
    assert geometric_v1.is_name(expected)


def test_the_1e_12_edges_are_the_receipted_tolerance():
    just_out = {"a": 1.0 + 2e-12, "b": 15.0}
    assert geometric_v1.klass(REGION, NAMES, just_out) == "regime:inner_band"
    band_edge = {"a": 2.0 + 0.9e-12, "b": 15.0}
    assert geometric_v1.klass(REGION, NAMES, band_edge) == "regime:inner_band"
    band_out = {"a": 2.0 + 2e-12, "b": 15.0}
    assert geometric_v1.klass(REGION, NAMES, band_out) == "regime:side_a_high"


def test_names_valid_accepts_exactly_the_four_forms():
    good = [
        "in_train",
        "regime:inner_band",
        "regime:side_pole_pairs_high",
        "regime:side_x2_low",
        "extended_shell",
    ]
    assert geometric_v1.names_valid(good) is True
    for bad in (
        "regime:outer_shell",
        "C-1",
        "H-1",
        "",
        "regime:side_A_high",
        "regime:side__high",
        "regime:side_a_mid",
        " in_train",
        "in_train ",
        None,
        3,
        b"in_train",
    ):
        assert geometric_v1.is_name(bad) is False, bad
        assert geometric_v1.names_valid(["in_train", bad]) is False, bad
    assert geometric_v1.names_valid([]) is False


def test_the_exam_check_only_delegates():
    assert pool_exam.geometric_v1_names_valid(["in_train", "extended_shell"]) is True
    assert pool_exam.geometric_v1_names_valid(["regime:outer_shell"]) is False
    assert "geometric_v1.names_valid" in inspect.getsource(
        pool_exam.geometric_v1_names_valid
    )


def test_no_scoring_module_but_the_rule_types_a_class_name():
    """The guard EXTENDED (Validator-2B A-2 (iv)): the rule's name literals live in carbon/scoring/geometric_v1.py only;
    test_pool_multiclass_regions' own pool_grader / pool_exam guard stays as it was."""
    offenders = []
    for info in pkgutil.iter_modules(scoring.__path__):
        if info.name == "geometric_v1":
            continue
        path = Path(info.module_finder.path) / (info.name + ".py")
        if not path.is_file():
            continue  # a subpackage
        text = path.read_text(encoding="utf-8")
        if "regime:" in text or "inner_band" in text:
            offenders.append(info.name)
    assert offenders == []
