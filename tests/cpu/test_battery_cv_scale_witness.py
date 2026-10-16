"""Synthetic structural and unit controls; no PyBaMM model or physical solve."""

from types import SimpleNamespace

import numpy as np
import pytest

from scripts.dev.battery import feasibility02 as worker
from scripts.dev.battery import guarded_reference as guard


class Scale:
    def __init__(self, value=5.0, constant=True):
        self.value, self.constant = value, constant

    def is_constant(self):
        return self.constant

    def evaluate(self):
        assert self.constant, "a state/input-dependent scale must not be evaluated"
        return self.value


class Expression:
    """Complete structural equality with deliberately lossy printed matrices."""

    def __init__(
        self,
        coefficients=(1.0, 0.0),
        target=0.0,
        factor=1.0,
        domains=("current collector",),
    ):
        self.structure = (coefficients, target, factor)
        self.domains = domains

    def __sub__(self, target):
        return Expression(self.structure[0], target, domains=self.domains)

    def __truediv__(self, scale):
        # Match the actual pinned-library counterexample: overload distributes
        # the factor into coefficients/target instead of retaining an outer node.
        coefficients, target, factor = self.structure
        return Expression(
            tuple(c / scale.evaluate() for c in coefficients),
            target / scale.evaluate(),
            factor,
            self.domains,
        )

    def __eq__(self, other):
        return (
            isinstance(other, Expression)
            and self.structure == other.structure
            and self.domains == other.domains
        )

    def __str__(self):
        return "synthetic Sparse Matrix (1, 2) @ y"

    def evaluate(self, *, t, y, inputs):
        coefficients, target, factor = self.structure
        return factor * (sum(c * v for c, v in zip(coefficients, y[:, 0])) - target)


def explicit_multiplication(scalar, expression):
    coefficients, target, factor = expression.structure
    return Expression(
        coefficients, target, scalar.evaluate() * factor, expression.domains
    )


class Processor:
    """Synthetic current-key broadcast/domain/scale context, never real physics."""

    def __init__(self):
        self.parameter_values = {"Nominal cell capacity [A.h]": 5.0}

    def __call__(self, *, name, symbol):
        if isinstance(name, str):
            return symbol
        result = explicit_multiplication(Scale(1.0 / name.scale.evaluate()), symbol)
        result.domains = ()
        return result


def context():
    variable = type("CurrentVariable", (), {"scale": Scale()})()
    voltage = Expression()
    processor = Processor()
    expression = processor(name=variable, symbol=voltage - guard.CONTROL_V)
    model = SimpleNamespace(
        algebraic={variable: expression},
        get_processed_variable_or_event=lambda _: voltage,
        symbol_processor=processor,
        variables={"Voltage [V]": voltage},
        _resolve_coupled_variables=lambda symbol: symbol,
    )
    return model, variable, expression


def observe(model, variable, expression, residual=2e-8):
    return worker._cv_equation_normalization(
        model,
        variable,
        expression,
        guard.CONTROL_V,
        time_s=1.0,
        state=np.array([[guard.CONTROL_V], [guard.CONTROL_V]]),
        inputs={},
        scaled_residual=residual,
    )


def test_actual_nonunit_scale_preserves_normalized_and_voltage_units():
    model, variable, expression = context()
    witness = observe(model, variable, expression, residual=-2e-8)
    assert witness["status"] == "VERIFIED_SYMBOLIC_RELATION"
    assert witness["scale"] == witness["nominal_capacity_ah"] == 5.0
    assert witness["signed_voltage_residual_v"] == -2e-8 * 5.0
    assert witness["independent_voltage_residual_v"] == 0.0
    assert witness["normalized_residual_units"] == "SOLVER_NORMALIZED"
    assert witness["voltage_residual_units"] == "V"


def test_distributed_overload_and_non_distributed_node_are_structurally_distinct():
    model, variable, equation = context()
    divided = (
        model.get_processed_variable_or_event("Voltage [V]") - guard.CONTROL_V
    ) / variable.scale
    assert divided != equation
    assert str(divided) == str(equation)
    assert observe(model, variable, equation)["status"] == "VERIFIED_SYMBOLIC_RELATION"
    model.algebraic[variable] = divided
    assert observe(model, variable, divided)["status"] == "UNAVAILABLE"


def test_constructor_alone_does_not_reproduce_current_key_domains():
    model, variable, equation = context()
    direct = explicit_multiplication(
        Scale(0.2),
        model.get_processed_variable_or_event("Voltage [V]") - guard.CONTROL_V,
    )
    assert direct.structure == equation.structure
    assert direct.domains != equation.domains
    assert direct != equation
    assert observe(model, variable, equation)["status"] == "VERIFIED_SYMBOLIC_RELATION"
    model.algebraic[variable] = direct
    witness = observe(model, variable, direct)
    assert witness["status"] == "UNAVAILABLE"
    assert witness["reason"] == "NOT_THE_SCALED_PROCESSED_VOLTAGE_RELATION"


def test_independent_raw_voltage_must_reproduce_public_processed_voltage():
    model, variable, equation = context()
    model.variables["Voltage [V]"] = Expression((0.5, 0.5))
    assert (
        observe(model, variable, equation)["reason"]
        == "RAW_VOLTAGE_DOES_NOT_REPRODUCE_PROCESSED_VOLTAGE"
    )


@pytest.mark.parametrize(
    "value,constant",
    [
        (0, True),
        (-5, True),
        (float("nan"), True),
        (float("inf"), True),
        (True, True),
        ([5, 5], True),
        (5, False),
    ],
)
def test_missing_invalid_or_dependent_scale_is_never_a_witness(value, constant):
    model, variable, expression = context()
    variable.scale = Scale(value, constant)
    assert observe(model, variable, expression)["status"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "defect", ["missing_scale", "missing_parameter", "wrong_capacity", "rhs_only"]
)
def test_scale_must_come_from_the_operative_algebraic_key_and_actual_parameters(defect):
    model, variable, expression = context()
    if defect == "missing_scale":
        variable.scale = None
    elif defect == "missing_parameter":
        model.symbol_processor.parameter_values.clear()
    elif defect == "wrong_capacity":
        model.symbol_processor.parameter_values["Nominal cell capacity [A.h]"] = 6.0
    else:
        model.rhs, model.algebraic = model.algebraic, {}
    assert observe(model, variable, expression)["status"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "defect", ["matrix_coefficients", "wrong_target", "zero_equation", "wrong_factor"]
)
def test_zero_residual_or_identical_printed_matrix_is_not_structural_identity(defect):
    model, variable, expression = context()
    if defect == "matrix_coefficients":
        wrong = Expression((0.5, 0.5), guard.CONTROL_V, 0.2, ())
    elif defect == "wrong_target":
        wrong = Expression((1.0, 0.0), 4.2, 0.2, ())
    elif defect == "wrong_factor":
        wrong = Expression((1.0, 0.0), guard.CONTROL_V, 0.25, ())
    else:
        wrong = Expression((0.0, 0.0), 0.0, 0.2, ())
    assert str(expression) == str(wrong)
    assert expression != wrong
    model.algebraic[variable] = wrong
    witness = observe(model, variable, wrong, residual=0.0)
    assert witness["status"] == "UNAVAILABLE"
    assert witness["reason"] == "NOT_THE_SCALED_PROCESSED_VOLTAGE_RELATION"


def test_nonfinite_voltage_conversion_is_unavailable():
    model, variable, expression = context()
    assert (
        observe(model, variable, expression, residual=1e308)["status"] == "UNAVAILABLE"
    )
