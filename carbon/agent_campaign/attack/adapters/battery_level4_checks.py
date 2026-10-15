"""Declared L4 software probes; ordinary session views are unavailable.

Only exact AttackInput declarations select fixed Carbon-owned fixtures. No
session graph, timing record, GPU label or execution claim is run or trusted.
These probes test dispatch/rule/detector code, not actual host containment,
runtime predictions, fresh attack confirmation or GPU reproducibility.
"""

from __future__ import annotations

import dataclasses
import functools
import tempfile
from pathlib import Path
from types import SimpleNamespace

from carbon.agent_campaign.attack import engine
from carbon.agent_campaign.attack.adapter import (
    NO_ORACLE_EVIDENCE,
    NOT_RUN,
    AttackInput,
    Control,
    FamilyDef,
    OracleResult,
    family_oracle,
)
from carbon.level4 import compile as g5
from carbon.training_budget import analysis as budget_rules

COMPILE = "l4_compile_isolation"
COUNTING = "l4_compute_under_counting"
FINITE = "l4_nonfinite_outputs"
NAMES = frozenset({COMPILE, COUNTING, FINITE})
UNAVAILABLE = NO_ORACLE_EVIDENCE
DECLARED = "declared_development_software_probe_only"
UNSUPPORTED = "unsupported_declared_probe"
# Pinned before a mutation can change the code under test.
_PROGRAM = g5.PROGRAM
_PROVENANCE = g5.PROVENANCE
_SCOPES = g5.SCOPES
_DEADLINE = g5.DEADLINE_SECONDS
_R6_SLOW = budget_rules.R6_SLOW
_R7_MULTIPLE = budget_rules.R7_MULTIPLE


def _compile(value, *, weakened=False):
    """Exercise G5's real entry point with a nonexecuting capture runner."""
    import json

    from carbon.level4 import allowlist, graph

    cases = {
        "mainnet": ("mainnet", _DEADLINE),
        "unknown_scope": ("unknown", _DEADLINE),
        "unset_deadline": ("development", allowlist.HUMAN_INPUT),
        "development": ("development", _DEADLINE),
        "testnet": ("testnet", _DEADLINE),
    }
    scope, deadline = cases[value["case"]]
    required_block = scope not in _SCOPES or deadline == allowlist.HUMAN_INPUT
    loaded = allowlist.load()
    document = {
        "schema": graph.SCHEMA,
        "allowlist": loaded.version,
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {
                        "value": 0,
                        "name": "inputs/x",
                        "dtype": "float32",
                        "shape": [2, 1],
                    }
                ],
                "constants": [],
                "nodes": [],
                "outputs": [0],
            }
        },
    }
    parsed = graph.parse(graph.dumps(document), max_bytes=1 << 20)
    captured = []
    scratch = Path.cwd() / ".carbon-artifacts" / "l4-oracle-probes"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="g5-", dir=scratch) as directory:
        ledger = SimpleNamespace(root=Path(directory))

        def capture(_ledger, **request):
            # No worker/program execution. The fixture response is private to
            # this call and never returned as a compile measurement.
            captured.append(request)
            snapshot = ledger.root / "fixture-operation" / "snapshot"
            snapshot.mkdir(parents=True)
            (snapshot / "compile.json").write_text(
                json.dumps({"fixture_capture_only": True}),
                encoding="utf-8",
                newline="\n",
            )
            return {"operation": "fixture-operation"}

        try:
            g5.compile_in_isolation(
                {"forward": parsed},
                loaded,
                ledger=ledger,
                owner="fixture-owner",
                image=None,
                deadline_seconds=_DEADLINE if weakened else deadline,
                max_bytes=1 << 20,
                scope="development" if weakened else scope,
                runner=capture,
            )
        except g5.CompileBlocked:
            pass
        except g5.CompileInfraFailure as failure:
            raise engine.InfrastructureFailure("fixture_capture_failed") from failure
    call = captured[0] if captured else None
    return {
        "required_block": required_block,
        "dispatched": call is not None,
        "fixed_request": call is None
        or (
            call["source"] == _PROGRAM
            and call["provenance"] == _PROVENANCE
            and call["seconds"] == deadline
            and call["extra_resources"] == {}
            and "forward.json" in call["files"]
        ),
    }


def _compile_breached(result):
    if result["required_block"]:
        return result["dispatched"]
    return not result["dispatched"] or not result["fixed_request"]


def _counting(value, *, weakened=False):
    """Use the frozen R6/R7 functions, not an invented runtime tolerance."""
    from carbon.training_budget import analysis

    measured, predicted = {
        "slow_gather": (3.0, 1.0),
        "missing_safety_limit": (4.0, 2.0),
        "ordinary": (1.0, 1.0),
        "threshold": (1.5, 1.0),
    }[value["case"]]
    record = {
        "state": "COMPLETED",
        "phase": "F",
        "run_id": "fixture-r6",
        "run": {"note": "fixture-setting"},
        "time": {"wall_s": measured},
    }
    r6 = analysis.r6([record], lambda _r, _f: predicted, "fixture-formula")
    r7 = analysis.r7(predicted)
    factors = {} if weakened else r6["settings_needing_a_factor"]
    limit = None if weakened else r7["time_limit_s"]
    return {
        "expected_factor": (
            measured / predicted if measured / predicted > _R6_SLOW else None
        ),
        "factor": factors.get("fixture-setting"),
        "expected_limit": _R7_MULTIPLE * predicted,
        "limit": limit,
    }


def _counting_breached(result):
    return (
        result["factor"] != result["expected_factor"]
        or result["limit"] != result["expected_limit"]
    )


@functools.cache
def _outputs(case):
    """Execute only Carbon-generated, parsed/validated CPU fixture graphs."""
    import jax
    import jax.numpy as jnp

    from carbon.level4 import allowlist, graph, interpret, specimens, validate
    from carbon.level4.tooling import lower_jax

    funcs = {
        "nan": lambda x: x / x,
        "positive_inf": lambda x: 1.0 / x,
        "negative_inf": lambda x: -1.0 / x,
        "finite": lambda x: x * 2.0 + 3.0,
        "finite_scaled": lambda x: x * 3.0 + 2.0,
    }
    with jax.default_device(jax.devices("cpu")[0]):
        inputs = jnp.asarray([[0.0], [1.0], [2.0]], dtype=jnp.float32)
        loaded = allowlist.load()
        doc = lower_jax.lower(
            lower_jax.trace(funcs[case], inputs),
            role="forward",
            allowlist=loaded,
            input_names=["inputs/x"],
        )
        parsed = graph.parse(graph.dumps(doc), max_bytes=1 << 20)
        validate.validate(parsed, loaded, caps=specimens.FIXTURE_CAPS)
        return tuple(interpret.rebuild(parsed, loaded)(inputs))


def _finite(value, *, weakened=False):
    import math

    import numpy as np

    from carbon.level4 import grade

    ids = ("fixture-a", "fixture-b", "fixture-c")
    outputs = _outputs(value["case"])
    # Independent scalar reference, so replacing G7 with an empty list or a
    # wrong case of the same count cannot pass this probe.
    expected = [
        name
        for row, name in enumerate(ids)
        if any(
            not math.isfinite(float(x))
            for output in outputs
            for x in np.asarray(output)[row].reshape(-1)
        )
    ]
    found = [] if weakened else grade.nonfinite_cases(outputs, ids)
    return {"expected": expected, "found": found}


def _finite_breached(result):
    return result["expected"] != result["found"]


def _definitions():
    return {
        COMPILE: (
            "construction_evaluation_isolation",
            "G5 scope/deadline/fixed-program dispatch probes; no worker execution or containment claim",
            _compile,
            _compile_breached,
            ("mainnet", "unknown_scope", "unset_deadline"),
            ("development", "testnet"),
        ),
        COUNTING: (
            "resource_and_failure_accounting",
            "frozen R6/R7 rule discrimination on fixture records; no actual runtime evidence",
            _counting,
            _counting_breached,
            ("slow_gather", "missing_safety_limit"),
            ("ordinary", "threshold"),
        ),
        FINITE: (
            "score_exploitation_and_tail_failures",
            "G7 finite-case detector on Carbon-owned CPU graph fixtures; no exam acceptance claim",
            _finite,
            _finite_breached,
            ("nan", "positive_inf", "negative_inf"),
            ("finite", "finite_scaled"),
        ),
    }


def family(name):
    check, description, boundary, breached, bad, valid = _definitions()[name]
    return engine.Family(
        name=name,
        check=check,
        description=description,
        boundary=boundary,
        specimen=lambda value: boundary(value, weakened=True),
        breached=breached,
        attacks=lambda: tuple((case, {"case": case}) for case in bad),
        control=lambda: not breached(boundary({"case": valid[0]})),
    )


def families():
    return tuple(
        FamilyDef(
            name=name,
            check=spec[0],
            boundary=spec[1],
            attack_example=spec[4][0],
            control_example=spec[5][0],
            family=family(name),
        )
        for name, spec in _definitions().items()
    )


def controls(split, version):
    if split not in ("trained", "held_out"):
        raise ValueError("split is trained or held_out")
    index = 0 if split == "trained" else 1
    return tuple(
        Control(
            name=f"{name}_{split}",
            family=name,
            split=split,
            version=version,
            check=lambda value={"case": spec[5][index]}, boundary=spec[
                2
            ], breached=spec[3]: not breached(boundary(value)),
            input_digest=engine.digest({"case": spec[5][index]}),
        )
        for name, spec in _definitions().items()
    )


def oracle(name, attempt):
    specs = _definitions()
    if name not in specs:
        raise ValueError("oracle_for_an_unknown_family: " + str(name))
    reason = UNAVAILABLE
    if type(attempt) is AttackInput:
        value = attempt.value
        supported = (*specs[name][4], *specs[name][5])
        if (
            type(value) is dict
            and set(value) == {"case"}
            and type(value["case"]) is str
            and value["case"] in supported
        ):
            return dataclasses.replace(
                family_oracle(family(name), attempt), reading=DECLARED
            )
        reason = UNSUPPORTED
    return OracleResult(
        family=name,
        attempt=(
            getattr(attempt, "name", "attempt")
            if type(getattr(attempt, "name", "attempt")) is str
            else "attempt"
        ),
        verdict=NOT_RUN,
        evidence_digest=engine.digest({"not_run": reason, "family": name}),
        reading=NO_ORACLE_EVIDENCE,
    )
