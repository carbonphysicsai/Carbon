"""The battery quiz document, read without the quiz's science (VALIDATOR-19
slice Q).

A quiz document's schema, its digest, its shape check and the inputs it asks
a model to predict. These are plain data operations, kept apart from
`quiz_stratum` (which draws, selects and measures through
`battery.value.quiz`), so a validator surface can verify and keep a shipped
quiz without loading the value-analysis modules. DEVELOPMENT only; no LIVE
authority.
"""

from __future__ import annotations

import hashlib
import json

SCHEMA = "carbon.battery.quiz-stratum.v1"
#: The candidate inputs a Q3 grid job carries.
GRID_INPUTS = ("c1", "c2", "t_amb_c", "soc0")
#: A Q3 scenario's refine counts (quiz-registry-v8), counts only: lattice
#: points refined, refined solves that succeeded, and points whose settled
#: reference is still UNRESOLVED. Optional, so a quiz selected before v8
#: still checks.
REFINE_COUNTS = ("refine_points", "refined_ok", "residual")


class QuizRefused(ValueError):
    """A typed refusal; its code names no case, input, output or root."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


def check(value):
    """A quiz document, checked for shape, or refused."""
    if (
        type(value) is not dict
        or set(value) != {"schema", "role", "panel_version", "q2", "q3", "redraws"}
        or value["schema"] != SCHEMA
        or type(value["role"]) is not str
        or type(value["panel_version"]) is not int
        or type(value["q2"]) is not list
        or type(value["q3"]) is not list
        or type(value["redraws"]) is not dict
        or not all(
            type(c) is dict and set(c) == {"case_id", "inputs"} for c in value["q2"]
        )
        or not all(_scenario(s) for s in value["q3"])
    ):
        raise QuizRefused("quiz_document_malformed")
    return value


def _scenario(s):
    if type(s) is not dict or set(s) - {"refine"} != {
        "scenario_id",
        "condition",
        "grid",
    }:
        return False
    if "refine" not in s:
        return True
    refine = s["refine"]
    return (
        type(refine) is dict
        and set(refine) == set(REFINE_COUNTS)
        and all(type(v) is int and v >= 0 for v in refine.values())
    )


def inputs(value):
    """Every case the quiz asks a model to predict: case id to inputs."""
    found = {c["case_id"]: dict(c["inputs"]) for c in value["q2"]}
    for s in value["q3"]:
        for job in s["grid"]:
            found[job["case_id"]] = {k: job[k] for k in GRID_INPUTS}
    return found
