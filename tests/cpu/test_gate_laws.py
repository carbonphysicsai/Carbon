"""Multi-row law gates (carbon/scoring/gate_laws): the shape, the fail-closed rules and the G3 builder, on synthetic toys.

No exam values: the U, steps and tolerances below are toy numbers for the toys, never a registered value.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from carbon.scoring import gate_laws as gl

BOX = gl.Box(lower=(0.0, -1.0, 10.0), upper=(1.0, 1.0, 20.0))
U = (0.5, 2.0)
RULE = "An answer does not jump when its inputs move by a tiny step."


def _linear(rows):
    """An exact smooth toy: two outputs linear in the three inputs."""
    a = np.array([[1.0, -2.0], [0.5, 3.0], [0.1, 0.0]])
    return rows @ a


def _table_with_fallback(scored, truths):
    """The 1.8-ACC kind: the scored rows answered from a table keyed by exact bytes, an honest-looking fit elsewhere."""
    table = {row.tobytes(): truth for row, truth in zip(scored, truths)}

    def model(rows):
        flat = rows.reshape(-1, rows.shape[-1])
        out = np.array([table.get(r.tobytes(), _linear(r) + 1.5) for r in flat])
        return out.reshape(rows.shape[:-1] + (2,))

    return model


def _scored(n=16, seed=7):
    rng = np.random.default_rng(seed)
    return BOX.lo + rng.random((n, 3)) * BOX.width


def _gate(tol=1.0, steps=("ulp", 1e-6)):
    return gl.smoothness("answer_smooth", steps, U, tol, RULE)


def test_linear_toy_passes_and_row0_is_the_base():
    gate = _gate()
    scored = _scored()
    rows = gl.rows(gate, np.random.default_rng(1), scored, BOX)
    assert rows.shape == (16, 3, 3)
    assert np.array_equal(rows[:, 0, :], scored)
    assert np.all(BOX.contains(rows))
    assert np.all(gl.verdicts(gate, rows, _linear(rows)) == gl.PASS)
    assert np.all(gl.margins(gate, rows, _linear(rows)) < 1.0)


def test_table_with_fallback_fails_on_scored_bases():
    scored = _scored()
    truths = _linear(scored)
    model = _table_with_fallback(scored, truths)
    gate = _gate()
    rows = gl.rows(gate, np.random.default_rng(1), scored, BOX)
    assert np.all(gl.verdicts(gate, rows, model(rows)) == gl.FAIL)
    assert np.all(gl.margins(gate, rows, model(rows)) > 1.0)


def test_one_ulp_alone_catches_the_table():
    scored = _scored()
    model = _table_with_fallback(scored, _linear(scored))
    gate = _gate(steps=("ulp",))
    rows = gl.rows(gate, np.random.default_rng(2), scored, BOX)
    assert not np.array_equal(rows[:, 1, :], rows[:, 0, :])
    assert np.all(gl.verdicts(gate, rows, model(rows)) == gl.FAIL)


def test_partners_are_deterministic_given_the_rng():
    gate = _gate()
    scored = _scored()
    a = gl.rows(gate, np.random.default_rng(5), scored, BOX)
    b = gl.rows(gate, np.random.default_rng(5), scored, BOX)
    assert np.array_equal(a, b)


def test_partners_stay_in_the_box_at_its_edges():
    gate = _gate(steps=("ulp", 0.5))
    edges = np.array([BOX.lo, BOX.hi, (BOX.lo + BOX.hi) / 2])
    rows = gl.rows(gate, np.random.default_rng(3), edges, BOX)
    assert np.all(BOX.contains(rows))


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_a_nonfinite_answer_is_fail_never_not_applicable(bad):
    gate = _gate()
    scored = _scored()
    rows = gl.rows(gate, np.random.default_rng(1), scored, BOX)
    out = _linear(rows)
    out[3, 2, 1] = bad
    got = gl.verdicts(gate, rows, out)
    assert got[3] == gl.FAIL
    assert np.all(np.delete(got, 3) == gl.PASS)
    assert gl.margins(gate, rows, out)[3] == np.inf


def test_unset_tol_refuses_to_grade():
    gate = _gate(tol=None)
    rows = gl.rows(gate, np.random.default_rng(1), _scored(), BOX)
    for fn in (gl.verdicts, gl.margins):
        with pytest.raises(gl.GateRefused) as err:
            fn(gate, rows, _linear(rows))
        assert err.value.code == "tol_unset"


def test_g3_must_tie_the_scored_rows():
    gate = _gate()
    with pytest.raises(gl.GateRefused) as err:
        gl.RelationGate(**{**gate.__dict__, "base": "fresh"})
    assert err.value.code == "base_must_be_scored"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("gate_id", "Answer-Smooth", "gate_id"),
        ("family", "G4", "family"),
        ("arity", 1, "arity"),
        ("base", "public", "base"),
        ("tol", 0.0, "tol"),
        ("tol", float("nan"), "tol"),
        ("rule_text", "", "rule_text"),
        ("rule_text", "two\nlines", "rule_text"),
    ],
)
def test_a_malformed_gate_is_refused(field, value, code):
    gate = _gate()
    with pytest.raises(gl.GateRefused) as err:
        gl.RelationGate(**{**gate.__dict__, field: value})
    assert err.value.code == code


def _with(gate, **changes):
    return gl.RelationGate(**{**gate.__dict__, **changes})


def test_a_partner_of_the_wrong_shape_or_place_refuses_the_gate():
    gate = _gate()
    scored = _scored()
    cases = {
        "partners_shape": lambda rng, base, box: base[:, None, :],
        "partners_row0": lambda rng, base, box: np.stack(
            [base + 1e-9, base, base], axis=1
        ),
        "partners_off_box": lambda rng, base, box: np.stack(
            [base, base + 100.0, base], axis=1
        ),
        "partners_nonfinite": lambda rng, base, box: np.stack(
            [base, base * np.nan, base], axis=1
        ),
    }
    for code, partners in cases.items():
        with pytest.raises(gl.GateRefused) as err:
            gl.rows(
                _with(gate, partners=partners), np.random.default_rng(1), scored, BOX
            )
        assert err.value.code == code


def test_a_check_of_the_wrong_shape_or_value_refuses_the_gate():
    gate = _gate()
    rows = gl.rows(gate, np.random.default_rng(1), _scored(), BOX)
    for check in (lambda i, o, t: np.ones(3), lambda i, o, t: np.full(i.shape[0], 2)):
        with pytest.raises(gl.GateRefused) as err:
            gl.verdicts(_with(gate, check=check), rows, _linear(rows))
        assert err.value.code == "check_shape"


def test_bases_off_the_box_refuse_an_in_box_gate():
    gate = _gate()
    with pytest.raises(gl.GateRefused) as err:
        gl.rows(gate, np.random.default_rng(1), np.array([[2.0, 0.0, 15.0]]), BOX)
    assert err.value.code == "base_off_box"


@pytest.mark.parametrize("steps", [(), (0.0,), (0.6,), ("two_ulp",), (1,)])
def test_smoothness_refuses_steps_it_cannot_take(steps):
    with pytest.raises(gl.GateRefused) as err:
        gl.smoothness("answer_smooth", steps, U, 1.0, RULE)
    assert err.value.code == "steps"


def test_a_box_must_be_finite_and_open():
    for lower, upper in (
        ((0.0,), (0.0,)),
        ((0.0,), (np.inf,)),
        ((0.0, 1.0), (1.0,)),
        ((), ()),
    ):
        with pytest.raises(gl.GateRefused):
            gl.Box(lower=lower, upper=upper)


def test_the_shared_type_names_no_challenge():
    source = Path(gl.__file__).read_text(encoding="utf-8").lower()
    for name in (
        "motor",
        "magnet",
        "cooling",
        "cold-plate",
        "battery",
        "bracket",
        "f08",
        "f02",
        "joint",
        "rb 2",
    ):
        assert name not in source
