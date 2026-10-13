"""Deterministic DEVELOPMENT advice; never qualification or solver execution."""

from __future__ import annotations

import bisect
import hashlib
import math
import time
from fractions import Fraction

from carbon.challenge_validator import validity

from . import configuration as cfg

RECEIPT_SCHEMA = "carbon.product.guard-receipt.v4"
PROBE_DERIVATION = "carbon.product.guard-local-sha256-counter.v1"


def development_pins(
    *,
    contract,
    envelope,
    reference_envelope,
    trust_map,
    reference,
    model,
    model_validity,
    reference_validity,
):
    """Content identities for a host's policy authoring; grants no authority."""
    return {
        "model_artifact": model.artifact_digest,
        "model_runtime": model.runtime_digest,
        "contract": cfg.digest(contract),
        "surrogate_envelope": cfg.digest(envelope),
        "reference_envelope": cfg.digest(reference_envelope),
        "model_validity": cfg.digest(cfg.declaration_body(model_validity)),
        "reference_validity": cfg.digest(cfg.declaration_body(reference_validity)),
        "reference_image": contract["reference_image"],
        "reference_record": None if reference is None else cfg.digest(reference),
        "trust_map": None if trust_map is None else cfg.digest(trust_map),
    }


def _inside(envelope, query):
    return all(v["low"] <= query[k] <= v["high"] for k, v in envelope["inputs"].items())


def _applicable(declaration, query):
    if isinstance(declaration, validity.Undeclared):
        return False
    if isinstance(declaration, validity.NoPropertyModel):
        return True
    return validity.applicability(declaration.models, query) is None


def _check(name, outcome, reason, **basis):
    return {"check": name, "outcome": outcome, "reason": reason, **basis}


def _verification_reasons(checks):
    return [
        check["reason"]
        for check in checks
        if check["outcome"]
        in ("FAIL", "UNRESOLVED", "FAILED_INFRA", "FAILED_REFERENCE")
    ]


def _vector(value, length):
    if type(value) in (int, float):
        value = [value]
    cfg.require(
        type(value) in (list, tuple) and len(value) == length,
        "prediction_shape_invalid",
    )
    return tuple(cfg.number(v) for v in value)


class EnvelopeGuard:
    """One immutable configured DEVELOPMENT Guard around a trusted callable.

    Configurations are constructed through validation; query callers cannot
    replace policy or identities. None policy/reference/map keeps a named gap.
    Production mode, arbitrary contract execution, solver and telemetry are absent.
    """

    def __init__(
        self,
        *,
        contract,
        envelope,
        reference_envelope,
        trust_map,
        reference,
        policy,
        model,
        model_validity,
        reference_validity,
    ):
        try:
            cfg.require(
                type(model) is cfg.ModelBinding, "nominal_model_binding_required"
            )
            # Hash original document content, before internal numeric normalization.
            pins = development_pins(
                contract=contract,
                envelope=envelope,
                reference_envelope=reference_envelope,
                trust_map=trust_map,
                reference=reference,
                model=model,
                model_validity=model_validity,
                reference_validity=reference_validity,
            )
            model_envelope = cfg.envelope(envelope)
            solver_envelope = cfg.envelope(reference_envelope)
            names = model_envelope["inputs"]
            cfg.require(
                set(names) == set(solver_envelope["inputs"]),
                "reference_inputs_mismatch",
            )
            cfg.require(
                all(
                    v["unit"] == solver_envelope["inputs"][k]["unit"]
                    for k, v in names.items()
                ),
                "reference_input_units_mismatch",
            )
            parsed_contract = cfg.contract(contract, names)
            parsed_reference, reference_verification = cfg.reference(
                reference, parsed_contract["reference_image"], parsed_contract["family"]
            )
            model_declaration = cfg.declaration(model_validity, names)
            reference_declaration = cfg.declaration(reference_validity, names)
            parsed_map = cfg.native_map(
                trust_map,
                model.model_id,
                parsed_contract["reference_image"],
                names,
                parsed_contract["outputs"],
            )
            cfg.require(
                reference_verification is None
                or parsed_map is None
                or parsed_map["reference_verification"] == reference_verification,
                "reference_map_acceptance_mismatch",
            )
            parsed_policy = cfg.policy(
                policy,
                pins,
                names,
                parsed_contract["outputs"],
                parsed_contract["family"],
            )
            cfg.require(
                parsed_policy is None
                or parsed_policy["laws"]["mode"] != "EXPLICIT_NO_LAWS"
                or not any(
                    law["status"] == "ADOPTED" for law in parsed_contract["laws"]
                ),
                "explicit_no_laws_conflicts_with_adoption",
            )
            self._contract = cfg.freeze(parsed_contract)
            self._envelope = cfg.freeze(model_envelope)
            self._reference_envelope = cfg.freeze(solver_envelope)
            self._reference = cfg.freeze(parsed_reference)
            self._reference_verification = cfg.freeze(reference_verification)
            self._map = cfg.freeze(parsed_map)
            self._policy = cfg.freeze(parsed_policy)
            self._pins = cfg.freeze(
                {**pins, "policy": None if policy is None else cfg.digest(policy)}
            )
            self._model = model
            self._model_validity = model_declaration
            self._reference_validity = reference_declaration
            self._cells = (
                {}
                if parsed_map is None
                else {
                    (c["band"], c["y"], c["x"]): cfg.freeze(c)
                    for c in parsed_map["cells"]
                }
            )
        except cfg.GuardConfigurationError:
            raise
        except (
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
            OverflowError,
            RecursionError,
        ):
            raise cfg.GuardConfigurationError("malformed_guard_configuration") from None

    def _receipt(
        self,
        started,
        verdict,
        reasons,
        checks,
        *,
        query_digest=None,
        seed=None,
        probe_digest=None,
        planned=0,
        executed=0,
        calls=0,
        prediction=None,
    ):
        result = {
            "schema": RECEIPT_SCHEMA,
            "scope": "DEVELOPMENT",
            "evidence_basis": (
                "HUMAN_INPUT" if self._policy is None else self._policy["basis"]
            ),
            "verdict": verdict,
            "reasons": sorted(set(reasons)),
            "checks": checks,
            "prediction": prediction,
            "identities": dict(self._pins),
            "query_digest": query_digest,
            "probes": {
                "derivation": PROBE_DERIVATION,
                "seed": seed,
                "digest": probe_digest,
                "planned": planned,
                "executed": executed,
                "model_calls": calls,
            },
            "qualification_claim": False,
            "independent_pick_verification_required": True,
            "law_policy": (
                None if self._policy is None else cfg.thaw(self._policy["laws"])
            ),
            "b9_policy": (
                None if self._policy is None else cfg.thaw(self._policy["b9"])
            ),
            "reference": (
                None
                if self._reference is None
                else {
                    "status": self._reference["status"],
                    "acceptance_scope": cfg.thaw(self._reference["acceptance_scope"]),
                    "basis": "DECLARED_DEVELOPMENT_USE_NOT_QUALIFICATION",
                    "observables_basis": "HOST_DECLARED_NOT_VERIFIED_COVERAGE",
                    "verification_conditions_basis": (
                        "REGISTERED_DEVELOPMENT_CODE_VERIFICATION"
                        if self._reference_verification is not None
                        else "HOST_DECLARED_NOT_COMPARED"
                    ),
                    "application_conditions_basis": "HOST_DECLARED_USE_RESTRICTION",
                }
            ),
            "code_verification": (
                cfg.thaw(self._reference_verification)
                if self._reference_verification is not None
                else (
                    None
                    if self._map is None
                    else cfg.thaw(self._map["reference_verification"])
                )
            ),
        }
        result["decision_digest"] = cfg.digest(result)
        result["elapsed_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        result["latency_target_ms"] = (
            None if self._policy is None else self._policy["latency_target_ms"]
        )
        result["latency_target_basis"] = (
            "HUMAN_INPUT"
            if result["latency_target_ms"] is None
            else "DECLARED_DEVELOPMENT_POLICY"
        )
        return result

    def _points(self, query, seed):
        points = [(None, dict(query))]
        if not any(law["status"] == "ADOPTED" for law in self._contract["laws"]):
            return points
        seen = {tuple(sorted(query.items()))}
        for name in sorted(query):
            bounds = self._envelope["inputs"][name]
            for direction in (-1, 1):
                counter = f"{seed}|{name}|{direction}".encode()
                bits = int.from_bytes(hashlib.sha256(counter).digest()[:8], "big")
                distance = self._policy["probe_steps"][name] * (
                    0.5 + 0.5 * bits / 2**64
                )
                point = dict(query)
                point[name] = min(
                    bounds["high"],
                    max(bounds["low"], query[name] + direction * distance),
                )
                key = tuple(sorted(point.items()))
                if key not in seen:
                    seen.add(key)
                    points.append((name, point))
        return points

    def _reference_scope_matches(self, query):
        scope = self._reference["acceptance_scope"]
        return (
            scope["family"] == self._contract["family"]
            and (
                self._map is None
                or scope["family"] == self._map["reference_verification"]["family"]
            )
            and set(self._contract["outputs"]) <= set(scope["observables"])
            and all(
                value is not None and name in query and query[name] == value
                for name, value in scope["application_conditions"].items()
            )
        )

    def _map_checks(self, query):
        if self._map is None:
            return [_check("trust_map", "UNRESOLVED", "MAP_UNAVAILABLE")]
        spec = self._map["spec"]
        coordinates = []
        for axis in [*spec["axes"], spec["bands"]]:
            edges, value = axis["edges"], query[axis["name"]]
            if not edges[0] <= value <= edges[-1]:
                return [_check("trust_map", "UNRESOLVED", "QUERY_OUTSIDE_MAP")]
            coordinates.append(
                min(bisect.bisect_right(edges, value) - 1, len(edges) - 2)
            )
        x, y, band = coordinates
        cell = self._cells[band, y, x]
        base = {"cell": [band, y, x], "observed_count": cell["count"]}
        if cell["count"] < self._policy["min_cell_count"]:
            return [
                _check("trust_map", "UNRESOLVED", "MAP_SUPPORT_INSUFFICIENT", **base)
            ]
        checks = []
        for output, limits in self._policy["map_limits"].items():
            for layer, threshold in (
                ("error", "max_error_p90"),
                ("disagreement", "max_disagreement_p90"),
            ):
                value = cell[layer][output]["p90"]
                passed = value <= limits[threshold]
                checks.append(
                    _check(
                        f"map.{output}.{layer}",
                        "PASS" if passed else "FAIL",
                        "MAP_LIMIT_MET" if passed else "MAP_LOW_TRUST",
                        value=value,
                        limit=limits[threshold],
                        unit=limits["unit"],
                        **base,
                    )
                )
        return checks

    def _prediction(self, query):
        result = self._model.predict(dict(query))
        cfg.require(type(result) is cfg.Prediction, "nominal_prediction_required")
        cfg.closed(result.outputs, self._contract["outputs"])
        outputs = {
            name: _vector(result.outputs[name], desc["length"])
            for name, desc in self._contract["outputs"].items()
        }
        intervals = None
        if result.intervals is not None:
            cfg.closed(result.intervals, self._contract["outputs"])
            intervals = {}
            for name, desc in self._contract["outputs"].items():
                raw = result.intervals[name]
                cfg.closed(raw, {"lower", "upper"})
                low, high = _vector(raw["lower"], desc["length"]), _vector(
                    raw["upper"], desc["length"]
                )
                cfg.require(
                    all(a <= p <= b for a, p, b in zip(low, outputs[name], high)),
                    "prediction_interval_invalid",
                )
                intervals[name] = (low, high)
        return outputs, intervals

    def _b9_checks(self, query, outputs):
        policy = self._policy["b9"]
        if policy is None:
            return []
        temperatures = outputs["temperature_c"]
        basis = {
            "decision_id": policy["decision_id"],
            "threshold_c": policy["threshold_c"],
            "unit": "C",
            "observed_grid_points": len(temperatures),
            "advisory": True,
            "exam_gate": False,
            "candidate_failure": False,
            "verdict_input": True,
        }
        # Compare the serialized decimal values exactly. Binary subtraction at
        # 25.0 - 24.9 would otherwise falsely exceed the owner's strict 0.1 bar.
        deficit = max(
            Fraction(0),
            Fraction(str(query["t_amb_c"])) - Fraction(str(min(temperatures))),
        )
        exceeds = deficit > Fraction(str(policy["threshold_c"]))
        try:
            measured = float(deficit)
        except OverflowError:
            return [
                _check(
                    "policy.B9",
                    "UNRESOLVED",
                    "B9_ARITHMETIC_UNRESOLVED",
                    max_deficit_c=None,
                    **basis,
                )
            ]
        return [
            _check(
                "policy.B9",
                "FAIL" if exceeds else "PASS",
                "B9_BELOW_AMBIENT" if exceeds else "B9_DEFICIT_WITHIN_POLICY",
                max_deficit_c=measured,
                **basis,
            )
        ]

    def _uncertainty_checks(self, intervals):
        policy = self._policy["uncertainty"]
        if intervals is None:
            required = policy["mode"] == "REQUIRED"
            return [
                _check(
                    "uncertainty",
                    "UNRESOLVED" if required else "NOT_ASSESSED",
                    (
                        "REQUIRED_INTERVALS_UNAVAILABLE"
                        if required
                        else "GAP_EXPLICIT_NO_INTERVALS_POLICY"
                    ),
                )
            ]
        if policy["calibration"] is None:
            return [
                _check("uncertainty", "UNRESOLVED", "INTERVAL_CALIBRATION_UNAVAILABLE")
            ]
        checks = []
        for name, (low, high) in intervals.items():
            width = max(b - a for a, b in zip(low, high))
            limit = policy["max_width"][name]
            if not math.isfinite(width):
                checks.append(
                    _check(
                        f"uncertainty.{name}",
                        "UNRESOLVED",
                        "INTERVAL_ARITHMETIC_UNRESOLVED",
                        value=None,
                    )
                )
                continue
            passed = width <= limit["value"]
            checks.append(
                _check(
                    f"uncertainty.{name}",
                    "PASS" if passed else "FAIL",
                    "INTERVAL_WIDTH_MET" if passed else "INTERVAL_TOO_WIDE",
                    value=width,
                    limit=limit["value"],
                    unit=limit["unit"],
                    calibration_ref=policy["calibration"]["record_digest"],
                )
            )
        return checks

    def _law_checks(self, predictions, unresolved):
        checks = []
        if not any(law["status"] == "ADOPTED" for law in self._contract["laws"]):
            required = self._policy["laws"]["mode"] == "REQUIRED_ADOPTED"
            checks.append(
                _check(
                    "law",
                    "UNRESOLVED" if required else "NOT_ASSESSED",
                    (
                        "ADOPTED_LAWS_UNAVAILABLE"
                        if required
                        else "GAP_EXPLICIT_NO_LAWS_POLICY"
                    ),
                    verdict_input=required,
                    adopted_count=0,
                    diagnostic_count=len(self._contract["laws"]),
                )
            )
        for law in self._contract["laws"]:
            if law["status"] != "ADOPTED":
                checks.append(
                    _check(
                        f"law.{law['id']}",
                        "NOT_ASSESSED",
                        "DIAGNOSTIC_NOT_ADOPTED",
                        verdict_input=False,
                    )
                )
                continue
            spec = law["spec"]
            residuals = []
            if law["type"] == "prefix_invariance":
                base = predictions[0][2][spec["output"]][: spec["points"]]
                for axis, _, outputs in predictions[1:]:
                    if axis in spec["inputs"]:
                        other = outputs[spec["output"]][: spec["points"]]
                        residuals.append(max(abs(a - b) for a, b in zip(base, other)))
                incomplete = bool(set(spec["inputs"]) & set(unresolved))
            else:
                incomplete = bool(unresolved)
                for _, query, outputs in predictions:
                    values = outputs[spec["output"]]
                    if law["type"] == "initial_condition":
                        residuals.append(abs(values[0] - query[spec["input"]]))
                    else:
                        residuals.append(
                            max(
                                max(
                                    0.0,
                                    0.0 if spec["low"] is None else spec["low"] - v,
                                    0.0 if spec["high"] is None else v - spec["high"],
                                )
                                for v in values
                            )
                        )
            calibration = law["calibration"]
            residual = None if not residuals else max(residuals)
            if residual is not None and not math.isfinite(residual):
                residual = None
                outcome, reason = "UNRESOLVED", "LAW_ARITHMETIC_UNRESOLVED"
            elif residual is not None and residual > calibration["tolerance"]:
                outcome, reason = "FAIL", "ADOPTED_LAW_VIOLATION"
            elif incomplete or residual is None:
                outcome, reason = "UNRESOLVED", "ADOPTED_LAW_PROBES_UNRESOLVED"
            else:
                outcome, reason = "PASS", "ADOPTED_LAW_MET"
            checks.append(
                _check(
                    f"law.{law['id']}",
                    outcome,
                    reason,
                    verdict_input=True,
                    residual=residual,
                    observed_probes=len(residuals),
                    unresolved_axes=sorted(unresolved),
                    unit=calibration["unit"],
                    tolerance=calibration["tolerance"],
                    adoption_ref=law["adoption_ref"],
                    calibration_ref=calibration["record_digest"],
                )
            )
        return checks

    def evaluate(self, query, *, units):
        """Local advisory receipt. Timing is separate from replayable decision identity."""
        started = time.perf_counter_ns()
        checks = []
        try:
            cfg.closed(query, self._envelope["inputs"])
            cfg.closed(units, self._envelope["inputs"])
            cfg.require(
                all(units[k] == v["unit"] for k, v in self._envelope["inputs"].items()),
                "query_units_mismatch",
            )
            query = {name: cfg.number(value) for name, value in query.items()}
        except (cfg.GuardConfigurationError, KeyError, TypeError, AttributeError):
            return self._receipt(started, "REFUSE", ["INVALID_QUERY_OR_UNITS"], checks)
        query_digest = cfg.digest({"query": query, "units": units})
        if self._policy is None or self._policy["authority_ref"] is None:
            return self._receipt(
                started,
                "REFUSE",
                ["GUARD_POLICY_HUMAN_INPUT"],
                checks,
                query_digest=query_digest,
            )
        if self._reference is None:
            return self._receipt(
                started,
                "REFUSE",
                ["REFERENCE_ACCEPTANCE_UNAVAILABLE"],
                checks,
                query_digest=query_digest,
            )
        if self._reference["status"] != "READY":
            state = self._reference["status"]
            checks.append(
                _check(
                    "reference", state, "REFERENCE_UNAVAILABLE", candidate_failure=False
                )
            )
            return self._receipt(
                started,
                "REFUSE",
                ["REFERENCE_UNAVAILABLE"],
                checks,
                query_digest=query_digest,
            )
        if not self._reference_scope_matches(query):
            checks.append(
                _check(
                    "reference_acceptance_scope",
                    "UNRESOLVED",
                    "REFERENCE_ACCEPTANCE_SCOPE_MISMATCH",
                    candidate_failure=False,
                )
            )
            return self._receipt(
                started,
                "REFUSE",
                ["REFERENCE_ACCEPTANCE_SCOPE_MISMATCH"],
                checks,
                query_digest=query_digest,
            )
        reference_ok = _inside(self._reference_envelope, query) and _applicable(
            self._reference_validity, query
        )
        if not reference_ok:
            checks.append(
                _check(
                    "reference_applicability",
                    "UNRESOLVED",
                    "REFERENCE_APPLICABILITY_UNRESOLVED",
                    candidate_failure=False,
                )
            )
            return self._receipt(
                started,
                "REFUSE",
                ["REFERENCE_APPLICABILITY_UNRESOLVED"],
                checks,
                query_digest=query_digest,
            )
        model_ok = _inside(self._envelope, query) and _applicable(
            self._model_validity, query
        )
        if not model_ok:
            checks.append(
                _check(
                    "surrogate_applicability",
                    "UNRESOLVED",
                    "SURROGATE_APPLICABILITY_UNRESOLVED",
                    candidate_failure=False,
                )
            )
            return self._receipt(
                started,
                "VERIFY",
                ["SURROGATE_APPLICABILITY_UNRESOLVED"],
                checks,
                query_digest=query_digest,
            )
        checks.append(_check("applicability", "PASS", "DECLARED_SCOPE_MET"))
        seed = cfg.digest(
            {
                "derivation": PROBE_DERIVATION,
                "query": query,
                "policy": self._pins["policy"],
                "contract": self._pins["contract"],
            }
        )
        points = self._points(query, seed)
        probe_digest = cfg.digest([{"axis": axis, "query": q} for axis, q in points])
        predictions, unresolved, calls = [], set(), 0
        base_intervals = None
        for index, (axis, point) in enumerate(points):
            if not _applicable(self._model_validity, point):
                unresolved.add(axis)
                checks.append(
                    _check(
                        "probe_applicability",
                        "UNRESOLVED",
                        "PROBE_OUTSIDE_VALIDITY",
                        candidate_failure=False,
                    )
                )
                continue
            if not self._reference_scope_matches(point):
                unresolved.add(axis)
                checks.append(
                    _check(
                        "probe_applicability",
                        "UNRESOLVED",
                        "PROBE_OUTSIDE_REFERENCE_ACCEPTANCE_SCOPE",
                        candidate_failure=False,
                    )
                )
                continue
            if calls >= self._policy["max_model_calls"]:
                unresolved.update(
                    remaining_axis
                    for remaining_axis, _ in points[index:]
                    if remaining_axis is not None
                )
                checks.append(
                    _check("probe_budget", "UNRESOLVED", "MODEL_CALL_BUDGET_EXHAUSTED")
                )
                break
            calls += 1
            try:
                outputs, intervals = self._prediction(point)
            except cfg.GuardConfigurationError:
                checks.append(
                    _check(
                        "model_output",
                        "UNRESOLVED",
                        "MODEL_OUTPUT_UNAVAILABLE_OR_MALFORMED",
                    )
                )
                return self._receipt(
                    started,
                    "VERIFY",
                    _verification_reasons(checks),
                    checks,
                    query_digest=query_digest,
                    seed=seed,
                    probe_digest=probe_digest,
                    planned=len(points),
                    executed=len(predictions),
                    calls=calls,
                )
            except Exception:  # noqa: BLE001
                # Adapter failures are typed infra; exception details stay private.
                checks.append(
                    _check(
                        "model_execution",
                        "FAILED_INFRA",
                        "MODEL_EXECUTION_FAILED",
                        candidate_failure=False,
                    )
                )
                return self._receipt(
                    started,
                    "VERIFY",
                    _verification_reasons(checks),
                    checks,
                    query_digest=query_digest,
                    seed=seed,
                    probe_digest=probe_digest,
                    planned=len(points),
                    executed=len(predictions),
                    calls=calls,
                )
            predictions.append((axis, point, outputs))
            if axis is None:
                base_intervals = intervals
                checks.extend(self._b9_checks(point, outputs))
        checks.extend(self._map_checks(query))
        checks.extend(self._uncertainty_checks(base_intervals))
        checks.extend(self._law_checks(predictions, unresolved))
        reasons = _verification_reasons(checks)
        verdict = "VERIFY" if reasons else "TRUST"
        reasons = reasons or ["ALL_DECLARED_DEVELOPMENT_CHECKS_MET"]
        prediction = {name: list(v) for name, v in predictions[0][2].items()}
        return self._receipt(
            started,
            verdict,
            reasons,
            checks,
            query_digest=query_digest,
            seed=seed,
            probe_digest=probe_digest,
            planned=len(points),
            executed=len(predictions),
            calls=calls,
            prediction=prediction,
        )
