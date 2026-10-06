"""Cooling's construction boundary: its three layers agree (VALIDATOR-12).

The chip-cold-plate counterpart of battery's standing check
(`test_challenge_validator_boundary_consistency.py`, VALIDATOR-10, unchanged),
for the Graphite readiness gate's item P7. On the same input:

1. the validator door's strict parse (`strict_json.parse_strategy`);
2. the Challenge contract's compile (`compile_submission`);
3. Graphite's admission under cooling's scoring (`experiment.admit`).

Cooling's malformed set follows the attack categories the battery session
tried, in cooling's own vocabulary: non-finite values, an unknown or numeric
kernel-length token, nested `{"value": …}` parameters, unknown parameters and
fields, another backbone, another Challenge's id, and the excluded surfaces as
fields and as parameters. Two valid controls (the scaffold and another
registered length/ridge pair) are accepted by all three layers.

Synthetic inputs only; no deployment, network or spend.
"""

import copy
import json
import math

import pytest

from carbon.agent_campaign.graphite import experiment as ex
from carbon.challenge_validator import scoring as cs
from carbon.challenge_validator import strict_json
from carbon.cold_plate.research import SCAFFOLD
from carbon.reconstruction.challenge_contracts import compile_submission

COOLING = "chip-cold-plate"
BATTERY = "battery-fastcharge-ageing-development-v1"
MAX_BYTES = 16384
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


SECOND_VALID = _with(("parameters",), {"length": "length_4", "ridge": "ridge_1e_4"})

#: (case, strategy, the door parses it, the compile and admission accept it)
CASES = [
    ("control_scaffold", SCAFFOLD, True, True),
    ("control_length_4_ridge_1e_4", SECOND_VALID, True, True),
    ("nan_parameter", _with(("parameters", "length"), math.nan), False, False),
    ("inf_parameter", _with(("parameters", "ridge"), math.inf), False, False),
    ("unknown_length_token", _with(("parameters", "length"), "length_3"), True, False),
    ("numeric_length", _with(("parameters", "length"), 8.0), True, False),
    (
        "nested_value_shape",
        _with(("parameters", "length"), {"value": "length_8"}),
        True,
        False,
    ),
    ("unknown_parameter", _with(("parameters", "steps"), 10), True, False),
    ("unknown_top_field", _with(("unknown_field",), 1), True, False),
    ("other_backbone", _with(("backbone",), "neural_operator"), True, False),
    ("another_challenge_id", _with(("challenge_id",), BATTERY), True, False),
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
        ex.admit(strategy, 0, scoring=cs.scoring_for(COOLING))
    except (ex.Unrebuildable, ex.NotServed):
        return False
    return True


def test_the_cooling_cases_are_counted():
    names = [case for case, *_ in CASES]
    # 2 controls and 21 malformed strategies; "null" is tested below.
    assert len(names) == len(set(names)) == 2 + 21


@pytest.mark.parametrize(
    ("case", "strategy", "parses", "accepted"), CASES, ids=[c[0] for c in CASES]
)
def test_each_layer_refuses_or_accepts_consistently(case, strategy, parses, accepted):
    assert _door_parses(strategy) is parses, case
    assert _compile_accepts(strategy) is accepted, case
    assert _admit_accepts(strategy) is accepted, case
    if not parses:
        assert not accepted


def test_another_challenges_strategy_is_refused_by_name():
    with pytest.raises(ex.Unrebuildable) as refused:
        ex.admit(_with(("challenge_id",), BATTERY), 0, scoring=cs.scoring_for(COOLING))
    assert refused.value.code == cs.scoring_for(COOLING).wrong_challenge_code


def test_no_construction_is_refused_before_anything_runs():
    assert not _door_parses(None)
    with pytest.raises(ex.Unrebuildable) as refused:
        ex.admit(None, 0, scoring=cs.scoring_for(COOLING))
    assert refused.value.code == "strategy_not_an_object"
