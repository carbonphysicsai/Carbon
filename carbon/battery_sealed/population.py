"""Battery's sealed-exam population: placed 4 scenarios x 35 EV4 candidates
(OWNER-BATTERY-EXAM-GRID-01; VALIDATOR_BATTERY_SEALED_RULINGS_20261022 §11).

**Law.** Each batch is a full grid: 4 fresh scenarios, each a (ambient, initial
state of charge) pair drawn at 4 decimals from the 420 grid's scenario hull
(ambient 5-34 C, soc0 0.12-0.48), crossed with EV4's 35 frozen candidates
(`ev.candidates(contract)`, c1 x c2 exactly), 140 cases in scenario-major
order. Every case is one cell of the 4 x 35 grid, so the registered `q`
(decision regret over the 35 candidates of a scenario) is defined on the batch.

**Disjointness.** A scenario is never one of EV4's development or verification
scenarios, and none of its 35 cases repeats a published Battery case (the
family's 4-decimal overlap key); the published set is validated before it is
cached and fails closed when missing or empty.

**Placement (placement only, never a label).** The public EV4 grid's mesh-20
plating margins (12 development scenarios, 35 candidates each) are interpolated
bilinearly in (ambient, soc0) to the drawn scenario; a scenario is accepted
when the interpolation predicts at least one candidate FEASIBLE and at least
one INFEASIBLE under the v2 window (margin >= 4.5 mV, margin <= -1.97 mV). A
seed whose scenarios cannot all be placed raises; the operator moves to the next
role (placement precedes every solve, so that is not a redraw) and records it.
The five EV4 development references that failed all sit at one corner (ambient
5 C, soc0 0.48, c1 = 2.0), so scenarios inside the box `EXCLUDED_CORNER` are not
drawn (a working decision for the Validator): a solver failure there would void
the scenario.

A DEVELOPMENT population; not qualified, and no LIVE or reward-bearing
evaluation may use it.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from .domain import INPUTS

POPULATION_VERSION = "carbon.battery.sealed-grid-4x35.v1"
REPOSITORY = Path(__file__).resolve().parents[2]
SCENARIOS = 4
CANDIDATE_COUNT = 35
CELLS = SCENARIOS * CANDIDATE_COUNT
#: The 420 grid's scenario hull (a test pins these to the EV4 contract's extremes).
HULL = {"t_amb_c": (5.0, 34.0), "soc0": (0.12, 0.48)}
PLACES = 4
#: The corner where all five EV4 reference failures sit (t_amb 5 C, soc0 0.48,
#: c1 = 2.0, any c2): scenarios with ambient below and soc0 above these are not drawn.
EXCLUDED_CORNER = {"t_amb_c_below": 10.0, "soc0_above": 0.42}
#: The v2 window's no-claim edges used for placement (plating_rereference).
FEASIBLE_AT_V, INFEASIBLE_AT_V = 4.5e-3, -1.97e-3
EV4 = (
    "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json",
    "fc6f504f3ff69b3add10099056b7a652a28112d3ca1d63ada2fb194aac2d3e18",
)
EV4_REFERENCES = (
    "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz",
    "ff10f9aea9097cd500d646ffe02f479d04401207b30a44aeee33566433e436cb",
)

_CACHE = {}


def _pinned(path_and_sha):
    path, pinned = path_and_sha
    raw = (REPOSITORY / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise RuntimeError(f"battery_sealed_pinned_file_differs: {path}")
    return raw


def contract():
    """The EV4 contract document and its 35 frozen candidates."""
    if "contract" not in _CACHE:
        from carbon.battery.value import contract as ev

        document = json.loads(_pinned(EV4))
        _CACHE["contract"] = (document, ev.candidates(document))
    return _CACHE["contract"]


def candidates():
    return contract()[1]


def ev4_scenario_conditions():
    """EV4's development and verification (ambient, soc0) conditions."""
    from carbon.battery.value import contract as ev

    document = contract()[0]
    return {
        (float(t), float(s))
        for scenario in ev.scenarios(document)
        for t, s in scenario["conditions"]
    }


def _grid():
    """{(ambient, soc0): {candidate id: mesh-20 plating margin or None}} from the
    public EV4 development references."""
    if "grid" not in _CACHE:
        from carbon.battery.value import contract as ev

        document, cands = contract()
        by_id = {}
        for line in gzip.decompress(_pinned(EV4_REFERENCES)).decode().splitlines():
            record = json.loads(line)
            by_id[record["case_id"]] = record
        grid = {}
        for scenario in ev.scenarios(document, "development"):
            (t, s), = scenario["conditions"]
            row = {}
            for candidate in cands:
                record = by_id[ev.case_id(document, scenario, candidate, 0)]
                ok = record.get("status") == "OK"
                row[candidate["id"]] = record["outputs"]["plating_margin_v"] if ok else None
            grid[(float(t), float(s))] = row
        _CACHE["grid"] = grid
    return _CACHE["grid"]


def predicted_margins(t_amb, soc0):
    """Bilinear interpolation of the public mesh-20 plating margin of each
    candidate at (t_amb, soc0), or None where a corner reference is missing."""
    grid = _grid()
    ts = sorted({t for t, _ in grid})
    ss = sorted({s for _, s in grid})

    def bracket(values, x):
        for lo, hi in zip(values, values[1:], strict=False):
            if lo <= x <= hi:
                return lo, hi
        raise ValueError("outside the grid")

    t0, t1 = bracket(ts, t_amb)
    s0, s1 = bracket(ss, soc0)
    wt = (t_amb - t0) / (t1 - t0)
    ws = (soc0 - s0) / (s1 - s0)
    out = {}
    for candidate in candidates():
        cid = candidate["id"]
        corners = [grid[(t, s)][cid] for t in (t0, t1) for s in (s0, s1)]
        if any(v is None for v in corners):
            out[cid] = None
            continue
        a, b, c, d = corners  # (t0,s0) (t0,s1) (t1,s0) (t1,s1)
        out[cid] = (
            (1 - wt) * ((1 - ws) * a + ws * b) + wt * ((1 - ws) * c + ws * d)
        )
    return out


def scenario_admitted(t_amb, soc0):
    """Inside the hull at 4 decimals, not an EV4 scenario, not in the excluded corner."""
    if round(t_amb, PLACES) != t_amb or round(soc0, PLACES) != soc0:
        return False
    if not (
        HULL["t_amb_c"][0] <= t_amb <= HULL["t_amb_c"][1]
        and HULL["soc0"][0] <= soc0 <= HULL["soc0"][1]
    ):
        return False
    if (t_amb, soc0) in ev4_scenario_conditions():
        return False
    return not (
        t_amb < EXCLUDED_CORNER["t_amb_c_below"] and soc0 > EXCLUDED_CORNER["soc0_above"]
    )


def scenarios_of(cases):
    """The sorted (ambient, soc0) scenarios of a case list, or ValueError when
    the cases are not a full 4 x 35 grid on EV4's candidates."""
    wanted = {(c["c1"], c["c2"]) for c in candidates()}
    scenarios = sorted({(c["t_amb_c"], c["soc0"]) for c in cases})
    cells = {(c["t_amb_c"], c["soc0"], c["c1"], c["c2"]) for c in cases}
    if (
        len(cases) != CELLS
        or len(scenarios) != SCENARIOS
        or len(cells) != CELLS
        or any((c["c1"], c["c2"]) not in wanted for c in cases)
        or len({(c["c1"], c["c2"]) for c in cases if (c["t_amb_c"], c["soc0"]) == scenarios[0]})
        != CANDIDATE_COUNT
    ):
        raise ValueError("not a full 4 x 35 scenario x candidate grid")
    return scenarios


def admitted(case):
    """A grid cell: a candidate of EV4's 35 at an admitted scenario."""
    if set(case) != set(INPUTS):
        return False
    if (float(case["c1"]), float(case["c2"])) not in {
        (c["c1"], c["c2"]) for c in candidates()
    }:
        return False
    return scenario_admitted(float(case["t_amb_c"]), float(case["soc0"]))


def _published_key(case):
    """Whether `case` repeats a published Battery case (the family's overlap key)."""
    published, key = _published()
    return key(case) in published


_PUBLISHED = {}


def _published():
    """The published keys and the overlap key function, validated before they
    are cached: a missing evidence root or an empty published set fails closed."""
    if "set" not in _PUBLISHED:
        from carbon.challenge_validator.confirmation_sources import source_for

        if not (REPOSITORY / "docs" / "development" / "evidence").is_dir():
            raise RuntimeError("battery_sealed_published_evidence_missing")
        source = source_for("battery-sealed-exam")
        published = source.published(REPOSITORY)
        if not published:
            raise RuntimeError("battery_sealed_published_set_empty")
        _PUBLISHED["set"] = (frozenset(published), source.key)
    return _PUBLISHED["set"]


def _placeable(t_amb, soc0):
    """At least one candidate predicted FEASIBLE and one INFEASIBLE."""
    margins = [m for m in predicted_margins(t_amb, soc0).values() if m is not None]
    return (
        any(m >= FEASIBLE_AT_V for m in margins)
        and any(m <= INFEASIBLE_AT_V for m in margins)
    )


def draw(rng, count, *, max_attempts=None):
    """One placed 4 x 35 grid (140 cases, scenario-major, EV4's candidate
    order) and the scenario draws it took. `count` must be 140."""
    if count != CELLS:
        raise ValueError(f"a Battery sealed batch is one {SCENARIOS} x {CANDIDATE_COUNT} grid")
    max_attempts = max_attempts or 5_000
    chosen, attempts = [], 0
    while len(chosen) < SCENARIOS:
        if attempts >= max_attempts:
            raise RuntimeError(
                f"{attempts} scenario draws placed only {len(chosen)} of {SCENARIOS}"
            )
        attempts += 1
        t_amb = round(rng.uniform(*HULL["t_amb_c"]), PLACES)
        soc0 = round(rng.uniform(*HULL["soc0"]), PLACES)
        if (t_amb, soc0) in chosen or not scenario_admitted(t_amb, soc0):
            continue
        cases = [
            {"c1": c["c1"], "c2": c["c2"], "t_amb_c": t_amb, "soc0": soc0}
            for c in candidates()
        ]
        if any(_published_key(case) for case in cases) or not _placeable(t_amb, soc0):
            continue
        chosen.append((t_amb, soc0))
    cases = [
        {"c1": c["c1"], "c2": c["c2"], "t_amb_c": t_amb, "soc0": soc0}
        for t_amb, soc0 in chosen
        for c in candidates()
    ]
    return cases, attempts


__all__ = [
    "POPULATION_VERSION",
    "admitted",
    "draw",
    "predicted_margins",
    "scenario_admitted",
    "scenarios_of",
]
