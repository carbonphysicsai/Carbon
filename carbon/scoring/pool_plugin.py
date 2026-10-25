"""Wiring a Challenge into the pool grader and its proof suite (plan POOL_PLUGIN_WIRING_PLAN_20261024).

`pool_grader` and `pool_proof_suite` know no Challenge. This module is the generic bridge: a Challenge
supplies a `ChallengeBinding` (plain callables and tuples, no Challenge list here) and gets back

- `pool_predictor`: the `predict(conditions, designs)` the grader calls, built from the Challenge's model
  server (`serve(input_rows) -> raw output rows`, the same query a practice or a receiver makes) and its
  `derive` (raw output row -> the derived objective and limit quantities, by the registered decision
  functions the sealed grader already uses);
- `BankLegs`: A and C (and the gates) from the sealed v2 grader's `measure` on a bank of cases, for a
  model named by a proof-suite descriptor;
- `make_plugin`: the `ProofPlugin` the proof suite runs.

A model input row is the target's fixed condition values plus the pool design:
`conditions = {"target_id": str, "fixed": {input_name: value}}` and `design_names` in the interface order.

Everything numeric the owner picks stays an argument of the suite, never here. The descriptor models for
the A and C legs follow the suite's names: the oracle returns the bank's references, `noisy` adds k times
the raw reference uncertainty with a seeded sign, `default` is the TRAIN-mean row, `in_distribution` and
`good` are the Challenge's real models, `perturbed` adds seeded layers, and `wrong_near_optimum` is the
oracle (its error lives only at pool designs, which the D leg grades).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from carbon.scoring import pool_proof_suite as suite

TRUTH_MODELS = ("oracle", "noisy", "wrong_near_optimum")


class PluginRefused(ValueError):
    """The binding or the bank cannot give a sound leg: the Challenge's wiring, not a candidate's failure."""


class TruthCheckStop(PluginRefused):
    """STOP, back to the Validator: truth outputs do not pass the law gates or the response leg, so the gate or
    the leg is miscalibrated against reality (or the check cannot run)."""


def _require(condition, reason):
    if not condition:
        raise PluginRefused(reason)


@dataclass(frozen=True)
class ChallengeBinding:
    kind: str
    version: str
    input_names: tuple  # the model's ordered input names
    design_names: (
        tuple  # the design variables, in the pool box order (a subset of input_names)
    )
    derive: object  # (inputs_row: dict, raw_output_row: list) -> {output: float}
    raw_u: object  # (inputs_row: dict, reference_row: list) -> list of U per raw output element
    train_mean_row: (
        object  # () -> the TRAIN-mean raw output row (the default model's answer)
    )
    serve_good: object  # (rows) -> raw output rows
    serve_train: object  # (rows) -> raw output rows, the TRAIN-fit model
    train_box: object  # (spec) -> ((lo, hi), ...) in design units
    # (rows) -> TRUE raw outputs for the bank rows that carry no reference (the probe rows), from the Challenge's
    # reference solver. Needed only for the truth-row check the perfect rule depends on (Validator, section 8).
    probe_truth: object = None


def model_input_row(binding, conditions, design):
    """The model's input row for one pool design: fixed conditions plus the design variables."""
    _require(
        type(conditions) is dict and type(conditions.get("fixed")) is dict,
        "conditions_need_a_fixed_dict",
    )
    _require(
        len(design) == len(binding.design_names), "design_does_not_match_design_names"
    )
    row = {
        **conditions["fixed"],
        **dict(zip(binding.design_names, design, strict=True)),
    }
    _require(
        set(row) == set(binding.input_names), "input_row_does_not_match_input_names"
    )
    return row


def pool_predictor(binding, serve):
    """predict(conditions, designs) -> derived outputs, one dict per design, from a raw-output model server."""

    def predict(conditions, designs):
        rows = [model_input_row(binding, conditions, d) for d in designs]
        raw = serve(rows)
        _require(
            type(raw) is list and len(raw) == len(rows),
            "serve_must_return_one_row_per_input",
        )
        return [binding.derive(row, out) for row, out in zip(rows, raw, strict=True)]

    return predict


def cached(predict):
    """Memoise a predictor by (conditions, design): the pool is small and a model's answer at a point never
    changes, so a grid of grader settings reuses every query. Returns (predict, stats).
    """
    memo = {}
    stats = {"calls": 0, "points_computed": 0}

    def predict_cached(conditions, designs):
        key = json.dumps(conditions, sort_keys=True, separators=(",", ":"))
        missing = [d for d in designs if (key, tuple(d)) not in memo]
        if missing:
            stats["calls"] += 1
            stats["points_computed"] += len(missing)
            for design, out in zip(missing, predict(conditions, missing), strict=True):
                memo[(key, tuple(design))] = out
        return [dict(memo[(key, tuple(d))]) for d in designs]

    return predict_cached, stats


@dataclass(frozen=True)
class BankLegs:
    """The sealed v2 grader on a bank of cases: `measure` is the adapter's, the rest its arguments."""

    binding: ChallengeBinding
    measure: object
    rows: list  # bank rows: {"case_id", "inputs": {name: value}, "reference": [..] | None, ...}
    arguments: dict  # definition, limits, objective, train_raw, names
    # How a TRUTH-based model (oracle, noisy, wrong_near_optimum) is credited on the probe rows, which carry no
    # reference: "perfect" (a truth obeys the physics laws, so the response leg is 1 and the law gates are not
    # held against it) or "measured" (graded as it stands). Required: the Validator confirms the rule.
    truth_probe_rule: str
    response_leg: str  # the A leg graded on probe rows
    ignored_gates: tuple  # the gates that grade probe responses (ignored for a truth model under "perfect")
    truth_tolerance: (
        float  # the oracle tolerance the truth-row check holds A_response to
    )
    state: dict  # {"truth_check": record} once `verify_truth_rows` has passed

    def outputs_for(self, descriptor):
        """Raw output rows on every bank row for a model descriptor."""
        binding, rows = self.binding, self.rows
        kind = descriptor.get("kind")
        default = [list(binding.train_mean_row()) for _ in rows]
        if kind == "default":
            return default
        if kind == "good":
            return _checked(binding.serve_good([r["inputs"] for r in rows]), rows)
        if kind == "in_distribution":
            return _checked(binding.serve_train([r["inputs"] for r in rows]), rows)
        if kind == "perturbed":
            base = self.outputs_for(descriptor["base"])
            return [
                [
                    value
                    + sum(
                        step * u * suite._sign(seed, "bank", row["case_id"], index)
                        for seed, step in descriptor["layers"]
                    )
                    for index, (value, u) in enumerate(
                        zip(out, self._u(row, out), strict=True)
                    )
                ]
                for row, out in zip(rows, base, strict=True)
            ]
        reference = [
            list(r["reference"]) if r.get("reference") is not None else list(d)
            for r, d in zip(rows, default, strict=True)
        ]
        if kind in ("oracle", "wrong_near_optimum"):
            return reference
        if kind == "noisy":
            k, seed = descriptor["k"], descriptor.get("seed", 0)
            return [
                [
                    (
                        value + k * u * suite._sign(seed, "bank", row["case_id"], index)
                        if row.get("reference") is not None
                        else value
                    )
                    for index, (value, u) in enumerate(
                        zip(out, self._u(row, out), strict=True)
                    )
                ]
                for row, out in zip(rows, reference, strict=True)
            ]
        raise PluginRefused("unknown_model_descriptor")

    def verify_truth_rows(self):
        """The Validator's check behind the perfect rule: with TRUE outputs on every row (the references, and the
        reference solver's on the probe rows), every law gate must pass and the response leg score within
        `truth_tolerance` of 1. Records the result; raises `TruthCheckStop` otherwise.
        """
        probe_truth = self.binding.probe_truth
        if probe_truth is None:
            raise TruthCheckStop(
                "truth_check_cannot_run_the_binding_supplies_no_probe_truth"
            )
        missing = [i for i, r in enumerate(self.rows) if r.get("reference") is None]
        supplied = (
            probe_truth([self.rows[i]["inputs"] for i in missing]) if missing else []
        )
        if type(supplied) is not list or len(supplied) != len(missing):
            raise TruthCheckStop("probe_truth_must_return_one_row_per_probe")
        outputs = [
            list(r["reference"]) if r.get("reference") is not None else None
            for r in self.rows
        ]
        for i, row in zip(missing, supplied, strict=True):
            outputs[i] = list(row)
        measured = self.measure(
            bank_rows=self.rows,
            outputs=outputs,
            repeats=[outputs, outputs],
            **self.arguments,
        )
        legs = measured.get("A_legs") or {}
        gates = measured.get("gates") or {}
        failed = sorted(name for name, ok in gates.items() if not ok)
        response = legs.get(self.response_leg)
        if (
            failed
            or type(response) not in (int, float)
            or response < 1.0 - self.truth_tolerance
        ):
            raise TruthCheckStop(
                f"truth_outputs_fail_the_checks: gates {failed}, response leg {response}"
            )
        self.state["truth_check"] = {"gates": sorted(gates), "response_leg": response}
        return self.state["truth_check"]

    def _u(self, row, out):
        reference = row.get("reference")
        u = self.binding.raw_u(
            row["inputs"], list(reference) if reference is not None else list(out)
        )
        _require(
            len(u) == len(out) and all(math.isfinite(x) and x >= 0 for x in u),
            "raw_u_must_match_the_outputs",
        )
        return u

    def legs(self, descriptor):
        """{"A", "C", "gates_ok"} for the descriptor's model on the bank, by the sealed v2 grader."""
        _require(
            self.truth_probe_rule in ("perfect", "measured"),
            "truth_probe_rule_must_be_perfect_or_measured",
        )
        # The perfect rule is for synthetic truth models only, and only after the truth-row check passed.
        perfect = (
            self.truth_probe_rule == "perfect"
            and descriptor.get("kind") in TRUTH_MODELS
        )
        _require(
            not perfect or "truth_check" in self.state,
            "truth_row_check_required_before_the_perfect_rule",
        )
        outputs = self.outputs_for(descriptor)
        measured = self.measure(
            bank_rows=self.rows,
            outputs=outputs,
            repeats=[outputs, outputs],
            **self.arguments,
        )
        a = measured.get("A")
        c = (measured.get("design_fidelity") or {}).get("C")
        gates = measured.get("gates") or {}
        a_legs_out = dict(measured.get("A_legs") or {})
        if perfect:
            a_legs = measured.get("A_legs")
            _require(
                type(a_legs) is dict
                and self.response_leg in a_legs
                and type(a) in (int, float),
                "the_response_leg_is_missing_from_A_legs",
            )
            _require(
                math.isclose(a, sum(a_legs.values()) / len(a_legs), abs_tol=1e-9),
                "A_is_not_the_mean_of_its_legs",
            )
            a = (sum(a_legs.values()) - a_legs[self.response_leg] + 1.0) / len(a_legs)
            a_legs_out = {**a_legs, self.response_leg: 1.0}
            gates = {
                name: ok for name, ok in gates.items() if name not in self.ignored_gates
            }
        gates_ok = all(bool(ok) for ok in gates.values())
        _require(
            all(type(v) in (int, float) and math.isfinite(v) for v in (a, c)),
            "measure_gave_no_finite_A_and_C",
        )
        return {"A": a, "C": c, "gates_ok": gates_ok, "A_legs": a_legs_out}


def _checked(raw, rows):
    _require(
        type(raw) is list and len(raw) == len(rows),
        "serve_must_return_one_row_per_input",
    )
    return [list(r) for r in raw]


def practice_bank_legs(
    binding, *, truth_probe_rule, response_leg, ignored_gates, truth_tolerance
):
    """`BankLegs` on the Challenge version's PUBLIC practice grid, the exam's own v2 grader (Phase 1: the sealed A
    cases stay in custody for the final run). Registry-driven: nothing here names a Challenge.
    """
    from carbon.challenge_kit import physical_pack
    from carbon.scoring import physical_dual_pack as physical
    from carbon.scoring import practice_dual, practice_grid

    adapter = practice_grid.adapter(binding.kind, binding.version)
    _require(adapter is not None, "practice_version_not_registered")
    bank = practice_grid.practice_bank(binding.kind, binding.version)
    public = physical_pack.public_roles(adapter.CHALLENGE, binding.version)
    names = practice_grid.input_names(binding.kind, binding.version)
    _require(
        tuple(names) == tuple(binding.input_names),
        "binding_input_names_differ_from_the_interface",
    )
    rows = physical.bank_rows(bank, names)
    definition = {
        **adapter.definition(bank=bank, train_raw=public["train"]),
        "challenge": {"kind": binding.kind, "version": binding.version},
        "scope": practice_dual.SCOPE,
    }
    return BankLegs(
        binding=binding,
        measure=adapter.measure,
        rows=rows,
        arguments={
            "definition": definition,
            "limits": practice_dual._json(public["important_limit_definition"]),
            "objective": practice_dual._json(public["design_objective"]),
            "train_raw": public["train"],
            "names": names,
        },
        truth_probe_rule=truth_probe_rule,
        response_leg=response_leg,
        ignored_gates=tuple(ignored_gates),
        truth_tolerance=truth_tolerance,
        state={},
    )


def make_plugin(binding, bank_legs, sets, fresh_set):
    """The `ProofPlugin` for one Challenge version. `sets` are pool_grader.TargetSpec tuples (the Challenge's
    pools); `fresh_set(draw_seed)` draws a fresh set from the same region."""
    memo = {}

    def legs(descriptor, specs):
        key = json.dumps(descriptor, sort_keys=True, default=list)
        if key not in memo:
            memo[key] = bank_legs.legs(descriptor)
        return memo[key]

    def default_serve(rows):
        return [list(binding.train_mean_row()) for _ in rows]

    # Each real model's answer at a pool point never changes: ask once, reuse across the whole grid of settings.
    train_model, _ = cached(pool_predictor(binding, binding.serve_train))
    default_model, _ = cached(pool_predictor(binding, default_serve))
    good_model, _ = cached(pool_predictor(binding, binding.serve_good))
    return suite.ProofPlugin(
        sets=tuple(tuple(s) for s in sets),
        fresh_set=fresh_set,
        train_box=binding.train_box,
        train_model=train_model,
        default_model=default_model,
        good_model=good_model,
        legs=legs,
    )


def spec_from_source(document, binding):
    """A `pool_grader.TargetSpec` from Data Collection's custody document (`pool-source-<tid>.json`): the
    `build_target` inputs plus `design_names`. `limits` may be [output, kind, bound] rows or dicts. The design
    names must be the binding's, in the same order, so the box, the designs and the model rows line up.
    """
    from carbon.scoring import pool_grader

    _require(type(document) is dict, "pool_source_must_be_a_dict")
    _require(
        tuple(document.get("design_names", ())) == tuple(binding.design_names),
        "design_names_differ_from_the_binding",
    )
    conditions = document["conditions"]
    _require(
        type(conditions) is dict
        and type(conditions.get("fixed")) is dict
        and conditions.get("target_id")
        == document.get("target_id", conditions.get("target_id")),
        "conditions_must_be_target_id_and_fixed",
    )
    limits = []
    for row in document["limits"]:
        output, kind, bound = (
            (row["output"], row["kind"], row["bound"]) if isinstance(row, dict) else row
        )
        limits.append(pool_grader.Limit(output, kind, bound))
    outputs = document.get("outputs") or tuple(document["truths"][0])
    return pool_grader.build_target(
        target_id=conditions["target_id"],
        conditions=conditions,
        outputs=outputs,
        objective=document["objective"],
        sense=document["sense"],
        limits=limits,
        u=document["u"],
        box=document["box"],
        designs=document["designs"],
        truths=document["truths"],
        agen=document["agen"],
        start=document["start"],
        seed=document["seed"],
        public=bool(document.get("public", False)),
    )
