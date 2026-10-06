"""The construction boundary's three layers agree (VALIDATOR boundary check).

A standing consistency test from the independent review of battery phase-4
session 1 (2026-10-05): the Attacker recorded 35 FAILING_TRIGGER findings
that were oracle defects, because advisory tools (check_design,
dry_validate, practice) were read as the boundary. The authoritative
boundary is three layers on the same input:

1. the validator door's strict parse (`strict_json.parse_strategy`);
2. the Challenge contract's compile (`compile_submission`);
3. Graphite's admission (`experiment.admit`).

Every attack category the session tried is refused, and the valid controls
are accepted, at each layer that sees them. A well-formed but out-of-contract
strategy passes the door, which checks JSON only, and is refused by the
compile and the admission. If a boundary changes, this test shows it even
when the Attacker's oracle also changes.

Synthetic inputs only; no deployment, network or spend.
"""

import copy
import json
import math

import pytest

from carbon.agent_campaign.graphite import experiment as ex
from carbon.battery.research import SCAFFOLD
from carbon.challenge_validator import scoring as cs
from carbon.challenge_validator import strict_json
from carbon.reconstruction.challenge_contracts import compile_submission

BATTERY = "battery-fastcharge-ageing-development-v1"
MAX_BYTES = 16384
KNN = {
    **SCAFFOLD,
    "backbone": "knn",
    "parameters": {"neighbours": 5, "train_fraction": 1.0},
}
#: The surfaces the battery Level-0 contract excludes, each tried by the
#: session as a top-level field and as a parameter.
EXCLUDED = (
    "pretrained_weights",
    "loss_expressions",
    "final_label_selection",
    "submitted_datasets",
    "label_method",
    "reference_solver_reuse",
)


def _with(path, value, base=SCAFFOLD):
    strategy = copy.deepcopy(base)
    node = strategy
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    return strategy


#: (case, strategy, the door parses it, the compile and admission accept it)
CASES = [
    ("control_scaffold_mlp", SCAFFOLD, True, True),
    ("control_knn_neighbours_5", KNN, True, True),
    ("nan_parameter", _with(("parameters", "width"), math.nan), False, False),
    ("inf_parameter", _with(("parameters", "steps"), math.inf), False, False),
    (
        "knn_neighbours_negative",
        _with(("parameters", "neighbours"), -5, KNN),
        True,
        False,
    ),
    ("nested_value_shape", _with(("parameters", "width"), {"value": 64}), True, False),
    (
        "unknown_parameter",
        _with(("parameters", "hidden_weights_file"), "w.npz"),
        True,
        False,
    ),
    ("unknown_top_field", _with(("unknown_field",), 1), True, False),
    *(
        (f"excluded_field_{name}", _with((name,), "x"), True, False)
        for name in EXCLUDED
    ),
    *(
        (f"excluded_parameter_{name}", _with(("parameters", name), "x"), True, False)
        for name in EXCLUDED
    ),
]


def _door_parses(strategy):
    text = json.dumps(strategy, allow_nan=True)
    try:
        strict_json.parse_strategy(text, max_bytes=MAX_BYTES)
    except strict_json.MalformedStrategy:
        return False
    return True


def _compile_accepts(strategy):
    try:
        compile_submission(strategy)
    except Exception:  # noqa: BLE001 -- any refusal is a refusal here
        return False
    return True


def _admit_accepts(strategy):
    try:
        ex.admit(strategy, 0, scoring=cs.scoring_for(BATTERY))
    except (ex.Unrebuildable, ex.NotServed):
        return False
    return True


def test_the_session_tried_every_category_covered_here():
    names = [case for case, *_ in CASES]
    # 2 controls and 18 malformed strategies; the 19th, "null", is tested below.
    assert len(names) == len(set(names)) == 2 + 18


@pytest.mark.parametrize(
    ("case", "strategy", "parses", "accepted"), CASES, ids=[c[0] for c in CASES]
)
def test_each_layer_refuses_or_accepts_consistently(case, strategy, parses, accepted):
    assert _door_parses(strategy) is parses, case
    assert _compile_accepts(strategy) is accepted, case
    assert _admit_accepts(strategy) is accepted, case
    # No layer accepts what an earlier one refused.
    if not parses:
        assert not accepted


def test_no_construction_is_refused_before_anything_runs():
    # A "null" strategy is not a construction: the door refuses it, and so
    # does the admission, by name.
    assert not _door_parses(None)
    with pytest.raises(ex.Unrebuildable) as refused:
        ex.admit(None, 0, scoring=cs.scoring_for(BATTERY))
    assert refused.value.code == "strategy_not_an_object"
