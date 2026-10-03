"""What a Challenge's research surface can draw, declared by the Challenge.

Challenge-neutral (OWNER-MINER-RESEARCH-SURFACE-01, RSURF-D8). A Challenge
with a research campaign declares, through its `ChallengeCampaign`:
- its outputs, each by kind, with names, units and axes read from its own I/O
  description;
- the aggregate practice components its practice summary reports;
- whether a miner's own practice predictions may be compared with its public
  practice references case by case (RSURF-D2), read from its practice
  population's disclosure contract;
- what its evaluation feedback shows under each feedback mode (RSURF-D4).

The Control Center and the MCP research view draw from this declaration
alone. A second Challenge supplies its own `ResearchView` and nothing in the
doors changes.

Charts are plain data: a kind, axes, units and named series. Every number is
finite or null. Nothing here reads a private pool, a seed or an evaluation
case; the references a view may name are public practice references only.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

#: The output kinds a Challenge may declare, and so the kinds the renderer
#: draws. `bars` is the renderer's comparison of aggregates, not an output.
OUTPUT_KINDS = ("time_series", "scalar", "checkpoint_vector", "field_2d")
CHART_KINDS = (*OUTPUT_KINDS, "bars")
#: Series roles the renderer styles: never a colour per rank.
ROLES = ("reference", "current", "previous", "series")
#: Bounds on one chart, so a view stays small enough for any MCP client.
MAX_SERIES = 12
MAX_POINTS = 4096
MAX_FIELD_SIDE = 256

#: The disclosure that permits per-case public practice detail: the practice
#: labels are public and the aggregation policy is the miner's own detailed
#: public practice (RSURF-D2). Anything else fails closed to aggregates.
PER_CASE_PUBLIC_FIELD = "public_practice_labels"
PER_CASE_AGGREGATION = "detailed_own_public_practice"


@dataclass(frozen=True)
class Axis:
    name: str
    unit: str | None
    #: Coordinates, numbers or labels, in order.
    values: tuple

    def document(self):
        return {"name": self.name, "unit": self.unit, "values": list(self.values)}


@dataclass(frozen=True)
class OutputSpec:
    """One output the Challenge's predictions carry, and how to draw it."""

    #: The output's own field name in a prediction.
    name: str
    kind: str
    unit: str | None
    label: str
    #: time_series and checkpoint_vector: one axis. field_2d: rows, columns.
    #: scalar: none.
    axes: tuple = ()

    def __post_init__(self):
        if self.kind not in OUTPUT_KINDS:
            raise ValueError(f"unknown output kind: {self.kind!r}")
        expected = {"scalar": 0, "time_series": 1, "checkpoint_vector": 1}.get(
            self.kind, 2
        )
        if len(self.axes) != expected:
            raise ValueError(f"{self.name}: a {self.kind} takes {expected} axes")

    @property
    def shape(self):
        return tuple(len(axis.values) for axis in self.axes)

    def document(self):
        return {
            "name": self.name,
            "kind": self.kind,
            "unit": self.unit,
            "label": self.label,
            "axes": [axis.document() for axis in self.axes],
        }


@dataclass(frozen=True)
class PerCasePolicy:
    allowed: bool
    #: Why, in one sentence a miner can read; names the contract it came from.
    basis: str


@dataclass(frozen=True)
class ResearchView:
    """A Challenge's research-surface declaration."""

    challenge_id: str
    outputs: tuple
    #: (summary component key, label) for the aggregate practice components.
    components: tuple
    #: "lower_is_better" or "higher_is_better", for score and components.
    direction: str
    per_case: PerCasePolicy
    #: {"recorded": bool, "basis": str}: whether practice records a curve.
    learning_curve: dict
    #: () -> the public practice case ids, in order.
    case_ids: Callable | None = None
    #: (case id) -> {"inputs": {...}, "outputs": {name: value}} for a public
    #: practice case, or None.
    reference: Callable | None = None
    #: (feedback mode) -> (outcome fields, screening fields) the mode shows,
    #: or None for a mode the Challenge does not know (show the state only).
    feedback_fields: Callable = field(default=lambda mode: None)
    #: The worker output a practice trial's predictions are read from.
    prediction_file: str = "predictions.json"
    #: The inputs of a case, in order, for labelling a chosen case.
    inputs: tuple = ()

    def document(self):
        """The declaration as the view carries it: no callable, no data."""
        return {
            "challenge_id": self.challenge_id,
            "outputs": [output.document() for output in self.outputs],
            "components": [{"key": k, "label": label} for k, label in self.components],
            "direction": self.direction,
            "per_case": {
                "allowed": self.per_case.allowed,
                "basis": self.per_case.basis,
            },
            "learning_curve": dict(self.learning_curve),
            "inputs": list(self.inputs),
        }


def per_case_policy(disclosure, *, population="public PRACTICE"):
    """Whether per-case predicted-vs-reference detail may be shown.

    `disclosure` is the practice population's `DisclosureContract`. Only a
    contract that makes the practice labels public and declares the miner's
    own detailed public practice as its aggregation policy allows it.
    """
    public = tuple(getattr(disclosure, "public_field_ids", ()) or ())
    aggregation = getattr(
        getattr(disclosure, "aggregation_policy_ref", None), "object_id", None
    )
    if PER_CASE_PUBLIC_FIELD in public and aggregation == PER_CASE_AGGREGATION:
        return PerCasePolicy(
            True,
            f"The {population} disclosure contract makes its labels public and "
            "aggregates the miner's own detailed public practice; curves are "
            "drawn on this machine from your own predictions.",
        )
    return PerCasePolicy(
        False,
        f"The {population} disclosure contract does not make per-case detail "
        "public, so only aggregates are shown.",
    )


def finite(value):
    """A JSON number, or None for anything non-finite or not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return round(value, 9) if math.isfinite(value) else None


def _vector(value, length):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    return [finite(v) for v in value]


def _field(value, rows, columns):
    if not isinstance(value, (list, tuple)) or len(value) != rows:
        return None
    out = []
    for row in value:
        row = _vector(row, columns)
        if row is None:
            return None
        out.append(row)
    return out


def values_for(output, value):
    """A prediction's or reference's value for one output, in the output's
    shape with every entry finite or null; None when it has another shape."""
    if output.kind == "scalar":
        return None if isinstance(value, (list, tuple, dict)) else finite(value)
    if output.kind == "field_2d":
        rows, columns = output.shape
        return _field(value, rows, columns)
    return _vector(value, output.shape[0])


def output_chart(output, series, *, chart_id=None, title=None):
    """One output drawn by its kind. `series` is [(label, role, raw value)];
    a series whose value has another shape is kept with values None, so the
    chart says it is missing rather than dropping it."""
    return {
        "id": chart_id or output.name,
        "kind": output.kind,
        "title": title or output.label,
        "unit": output.unit,
        "axes": [axis.document() for axis in output.axes],
        "series": [
            {"label": label, "role": role, "values": values_for(output, value)}
            for label, role, value in series
        ],
    }


def bars_chart(chart_id, title, categories, series, *, unit=None):
    """Grouped bars: one group per category, one bar per series."""
    return {
        "id": chart_id,
        "kind": "bars",
        "title": title,
        "unit": unit,
        "axes": [{"name": "component", "unit": None, "values": list(categories)}],
        "series": [
            {
                "label": label,
                "role": role,
                "values": [finite(v) for v in values],
            }
            for label, role, values in series
        ],
    }


def series_chart(chart_id, title, axis, series, *, unit=None, log=False):
    """A time series over any axis (practice runs, optimizer updates)."""
    return {
        "id": chart_id,
        "kind": "time_series",
        "title": title,
        "unit": unit,
        "log": bool(log),
        "axes": [axis.document()],
        "series": [
            {"label": label, "role": role, "values": [finite(v) for v in values]}
            for label, role, values in series
        ],
    }


def validate_chart(chart):
    """Raise ValueError unless `chart` is a well-formed, bounded chart."""
    if type(chart) is not dict:
        raise TypeError("a chart is a mapping")
    if chart.get("kind") not in CHART_KINDS:
        raise ValueError("chart kind unknown")
    for key in ("id", "title"):
        if type(chart.get(key)) is not str or not chart[key]:
            raise ValueError(f"chart {key} required")
    axes = chart.get("axes")
    expected = {"scalar": 0, "field_2d": 2}.get(chart["kind"], 1)
    if type(axes) is not list or len(axes) != expected:
        raise ValueError("chart axes differ from its kind")
    for axis in axes:
        if type(axis.get("name")) is not str or type(axis.get("values")) is not list:
            raise ValueError("axis name and values required")
        if not 1 <= len(axis["values"]) <= MAX_POINTS:
            raise ValueError("axis length out of bounds")
    series = chart.get("series")
    if type(series) is not list or not 1 <= len(series) <= MAX_SERIES:
        raise ValueError("chart series out of bounds")
    shape = tuple(len(axis["values"]) for axis in axes)
    if chart["kind"] == "field_2d" and max(shape) > MAX_FIELD_SIDE:
        raise ValueError("field too large")
    for item in series:
        if type(item.get("label")) is not str or item.get("role") not in ROLES:
            raise ValueError("series label and role required")
        values = item.get("values")
        if values is None:
            continue
        if chart["kind"] == "scalar":
            _number(values)
        elif chart["kind"] == "field_2d":
            if len(values) != shape[0] or any(len(row) != shape[1] for row in values):
                raise ValueError("field shape differs from its axes")
            for row in values:
                for value in row:
                    _number(value)
        else:
            if type(values) is not list or len(values) != shape[0]:
                raise ValueError("series length differs from its axis")
            for value in values:
                _number(value)
    return chart


def _number(value):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        # A malformed chart is one refusal to every caller, whatever is wrong.
        raise ValueError("chart values are numbers or null")  # noqa: TRY004
    if not math.isfinite(value):
        raise ValueError("chart values are finite")
