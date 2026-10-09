"""SUBMISSION-RATE-STUDY-01's scripted prober (run sheet D.2) and the probe
tool G-sealed is offered (D.3).

The prober is deterministic, coordinate-wise hill climbing over battery MLP
recipes. It conditions only on what the study route returns for its own
submissions:

- **S-sealed** reads the mainnet allow-list view (`hidden_score` `agent_view`):
  its objective is the view's `state` alone (SCORED above NOT_SCORED). That
  is all a mainnet miner sees, so the arm measures whether the sealed channel
  carries enough to fit.
- **S-revealed** also reads `batch_score`, which only the study route on the
  sacrificial study bank returns (OWNER-RATE-STUDY-D1-01); lower is better.
  A revealed observation without it is refused, typed.

`WINDOW_USED` and `UNAVAILABLE` carry no information about the recipe; they
are not observations, and the same proposal is offered again.

**Never a repeat.** The study route never rescores a resubmitted recipe
(plan O7c), so the prober never proposes a strategy it has proposed before.
When every unvisited neighbour of the current recipe has been tried, it
moves to the next unvisited point of a fixed lexicographic sweep.

**Inside the contract.** Every coordinate ladder lies inside battery's
construction-contract caps (`capability_registry`), so no proposal is
refused for shape. The ladders and the start are declared engineering
constants of the study tooling, not scientific values.

**Isolation.** Pure: no file, network, clock or randomness. It reads no
operator record, case, seed or fresh score; the caller passes in each view.

`next_probe` is the same search as a stateless tool for a G-sealed session:
given the session's own history of `(strategy, view)` pairs, it returns the
next strategy the scripted prober would submit.
"""

from __future__ import annotations

import hashlib
import json
import math

SCHEMA = "carbon.rate-study.prober.v1"
CHALLENGE_ID = "battery-fastcharge-ageing-development-v1"
SEALED, REVEALED = "S-sealed", "S-revealed"
MODES = (SEALED, REVEALED)

#: The search coordinates and their ladders, in visiting order. Each value
#: is inside battery's contract (width 8-512, depth 1-6, steps 16-20000,
#: learning_rate 1e-5-0.05, weight_decay 0-0.1).
COORDINATES = (
    ("steps", (500, 1000, 1500, 3000, 6000, 10000, 15000, 20000)),
    ("width", (16, 32, 64, 128, 256, 512)),
    ("depth", (1, 2, 3, 4, 5, 6)),
    ("learning_rate", (0.0005, 0.001, 0.002, 0.004, 0.008)),
    ("weight_decay", (0.0, 1e-5, 1e-4, 1e-3, 1e-2)),
)
#: The start: battery's panel MLP (6,000 steps, width 256, depth 3) at the
#: contract's default learning rate and weight decay.
START = (4, 4, 2, 2, 0)
#: Allow-list states and their sealed objective value; any other state is
#: not an observation.
SEALED_VALUE = {"SCORED": 1.0, "NOT_SCORED": 0.0}
NO_INFORMATION = ("WINDOW_USED", "UNAVAILABLE")


class ProberRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def strategy(point):
    """The strategy document of a ladder point."""
    parameters = {
        name: ladder[index]
        for (name, ladder), index in zip(COORDINATES, point, strict=True)
    }
    return {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE_ID,
        "backbone": "mlp",
        "parameters": parameters,
    }


def strategy_digest(document):
    body = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _sweep():
    """Every ladder point in a fixed lexicographic order."""
    points = [()]
    for _name, ladder in COORDINATES:
        points = [p + (i,) for p in points for i in range(len(ladder))]
    return points


def objective(mode, view):
    """The observed value of `view` (higher is better), or None when the view
    carries no information about the recipe."""
    if mode not in MODES:
        raise ProberRefused("prober_mode_unknown")
    if type(view) is not dict or type(view.get("state")) is not str:
        raise ProberRefused("prober_view_malformed")
    state = view["state"]
    if state in NO_INFORMATION:
        return None
    if state not in SEALED_VALUE:
        raise ProberRefused("prober_view_state_unknown")
    if mode == SEALED:
        return SEALED_VALUE[state]
    if state != "SCORED":
        return float("-inf")
    score = view.get("batch_score")
    if type(score) not in (int, float) or not math.isfinite(score):
        raise ProberRefused("revealed_view_without_batch_score")
    return -float(score)


def _point(document):
    """The ladder point of a strategy document, or None when it is not one
    the prober could have proposed."""
    if (
        type(document) is not dict
        or document.get("backbone") != "mlp"
        or type(document.get("parameters")) is not dict
        or set(document["parameters"]) != {name for name, _ in COORDINATES}
    ):
        return None
    point = []
    for name, ladder in COORDINATES:
        value = document["parameters"][name]
        if value not in ladder or type(value) is bool:
            return None
        point.append(ladder.index(value))
    point = tuple(point)
    return (
        point if strategy_digest(strategy(point)) == strategy_digest(document) else None
    )


def _neighbours(point):
    out = []
    for axis, (_name, ladder) in enumerate(COORDINATES):
        for step in (1, -1):
            index = point[axis] + step
            if 0 <= index < len(ladder):
                out.append(point[:axis] + (index,) + point[axis + 1 :])
    return out


def next_probe(mode, history):
    """The next strategy, from a run's own `history` of `{"strategy", "view"}`
    entries in submission order. The same rule drives the scripted prober and
    the G-sealed probe tool:

    - the start, until any ladder point has an observation;
    - the current point is the first observed point with the best value so
      far (a later point replaces it only when strictly better);
    - the next proposal is the current point's first unvisited neighbour in
      `COORDINATES` order, else the first unvisited point of the fixed sweep.

    A view with no information (`WINDOW_USED`, `UNAVAILABLE`) visits nothing,
    so its strategy is proposed again. A history strategy that is not a
    ladder point (a G-sealed session's own design) is never re-proposed, and
    it does not move the search."""
    if mode not in MODES:
        raise ProberRefused("prober_mode_unknown")
    if type(history) not in (list, tuple):
        raise ProberRefused("probe_history_malformed")
    visited, current, best = set(), None, None
    for entry in history:
        if type(entry) is not dict or set(entry) != {"strategy", "view"}:
            raise ProberRefused("probe_history_malformed")
        value = objective(mode, entry["view"])
        if value is None:
            continue
        point = _point(entry["strategy"])
        if point is None:
            continue
        visited.add(point)
        if best is None or value > best:
            current, best = point, value
    if current is None:
        if START not in visited:
            return strategy(START)
        current = START
    for point in _neighbours(current):
        if point not in visited:
            return strategy(point)
    for point in _sweep():
        if point not in visited:
            return strategy(point)
    raise ProberRefused("prober_search_exhausted")


class Prober:
    """One run's scripted prober: `propose()` gives the next strategy, and
    `observe(view)` records the route's answer to the last proposal. It
    never proposes a strategy it has had an informative answer for."""

    def __init__(self, mode):
        if mode not in MODES:
            raise ProberRefused("prober_mode_unknown")
        self.mode = mode
        self.history = []
        self.pending = None

    def propose(self):
        if self.pending is None:
            self.pending = next_probe(self.mode, self.history)
        return self.pending

    def observe(self, view):
        if self.pending is None:
            raise ProberRefused("prober_observe_without_proposal")
        value = objective(self.mode, view)
        self.history.append({"strategy": self.pending, "view": view})
        self.pending = None
        return value
