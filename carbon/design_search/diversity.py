"""Producer-only aggregate design-question diversity diagnostics.

The input bank and question law stay on the producer. Output is a closed
aggregate schema with no case, winner, reference value or registered ID.
This is a DEVELOPMENT report, not a power or score decision.
"""

from __future__ import annotations

import hashlib
import json
import math

from carbon.design_search import tasks

BANK_SCHEMA = "carbon.design-search.sealed-bank.v1"
LAW_SCHEMA = "carbon.design-search.question-law.v1"
REPORT_SCHEMA = "carbon.design-search.diversity-report.v1"
STATES = ("FEASIBLE_EXISTS", "NONE_FEASIBLE", "UNRESOLVED")


def _digest(body):
    data = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def _registered(value, schema, digest_field):
    if type(value) is not dict or value.get("schema") != schema:
        raise tasks.TaskError("registered producer input required")
    body = {k: v for k, v in value.items() if k != digest_field}
    if value.get(digest_field) != _digest(body):
        raise tasks.TaskError("producer registration digest mismatch")


def _mass(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise tasks.TaskError("law masses must be finite and non-negative")
    return float(value)


def _law_view(bins, cases, key, batch_size, *, drawable):
    winner_mass = {}
    status_mass = {state: 0.0 for state in STATES}
    close = refinement = 0.0
    for bin_ in bins:
        mass = bin_[key]
        case = cases[bin_["case"]]
        state = case["state"]
        status_mass[state] += mass
        close += mass * case["close_call"]
        refinement += mass * case["refinement_demand"]
        if state == "FEASIBLE_EXISTS":
            winner = case["winner"]
            winner_mass[winner] = winner_mass.get(winner, 0.0) + mass
    return {
        "expected_distinct_winners_per_batch": (
            sum(
                -math.expm1(batch_size * math.log1p(-mass)) if mass < 1 else 1.0
                for mass in winner_mass.values()
                if mass > 0
            )
            if drawable
            else None
        ),
        "status_mix": status_mass,
        "close_call_rate": close,
        "refinement_demand_rate": refinement,
        "rate_denominator": "all registered draws",
    }


def diversity_report(bank, law):
    """Compute P and Q aggregates for an iid registered grid/continuous law.

    A continuous law supplies masses of disjoint outcome-homogeneous regions,
    integrated under its registered P and Q densities. The producer owns that
    integration and evidence; this code does not infer it from grid atoms.
    """
    _registered(bank, BANK_SCHEMA, "seal_digest")
    _registered(law, LAW_SCHEMA, "registration_digest")
    if (
        bank.get("sealed") is not True
        or type(bank.get("cases")) is not list
        or not bank["cases"]
    ):
        raise tasks.TaskError("sealed nonempty bank required")
    if (
        law.get("kind") not in ("grid", "continuous")
        or law.get("draw_model") != "iid_with_replacement"
    ):
        raise tasks.TaskError("registered iid grid or continuous law required")
    if law["kind"] == "continuous" and not law.get("integration_evidence"):
        raise tasks.TaskError("continuous region masses require integration evidence")
    error_bound = _mass(law.get("mass_l1_error_bound"))
    if law["kind"] == "grid" and error_bound != 0:
        raise tasks.TaskError("enumerated grid masses require zero integration error")
    k = law.get("batch_size")
    if type(k) is not int or k <= 0:
        raise tasks.TaskError("positive registered batch size required")
    exposure = bank.get("exposure")
    if type(exposure) is not list or not exposure:
        raise tasks.TaskError("sealed bank exposure ledger required")
    remaining_by_support = []
    seen_support = set()
    for row in exposure:
        if (
            type(row) is not dict
            or set(row) != {"support_case", "limit", "used"}
            or type(row["support_case"]) is not str
            or not row["support_case"]
            or row["support_case"] in seen_support
            or type(row["limit"]) is not int
            or row["limit"] <= 0
            or type(row["used"]) is not int
            or not 0 <= row["used"] <= row["limit"]
        ):
            raise tasks.TaskError("sealed bank exposure row invalid")
        seen_support.add(row["support_case"])
        remaining_by_support.append(row["limit"] - row["used"])
    cases = {}
    for row in bank["cases"]:
        if (
            type(row) is not dict
            or set(row)
            != {"case", "state", "winner", "close_call", "refinement_demand"}
            or type(row["case"]) is not str
            or not row["case"]
            or row["case"] in cases
            or row["state"] not in STATES
            or type(row["close_call"]) is not bool
            or type(row["refinement_demand"]) is not bool
            or (row["state"] == "FEASIBLE_EXISTS")
            != (type(row["winner"]) is str and bool(row["winner"]))
        ):
            raise tasks.TaskError("sealed bank case invalid")
        cases[row["case"]] = row
    bins = law.get("bins")
    if type(bins) is not list or not bins:
        raise tasks.TaskError("registered question bins required")
    checked = []
    for bin_ in bins:
        if (
            type(bin_) is not dict
            or set(bin_) != {"case", "p_mass", "q_mass"}
            or bin_["case"] not in cases
        ):
            raise tasks.TaskError("question bin does not map to sealed bank")
        checked.append(
            {
                "case": bin_["case"],
                "p_mass": _mass(bin_["p_mass"]),
                "q_mass": _mass(bin_["q_mass"]),
            }
        )
    for key in ("p_mass", "q_mass"):
        if not math.isclose(sum(b[key] for b in checked), 1.0, abs_tol=1e-9):
            raise tasks.TaskError("question-law masses must sum to one")
    remaining = min(remaining_by_support)
    drawable = remaining >= k
    return {
        "schema": REPORT_SCHEMA,
        "material": "DEVELOPMENT",
        "law_kind": law["kind"],
        "draw_model": law["draw_model"],
        "batch_size": k,
        "basis": {
            "mass_l1_error_bound": error_bound,
            "expected_distinct_error_bound": k * error_bound if drawable else None,
        },
        "P": _law_view(checked, cases, "p_mass", k, drawable=drawable),
        "Q": _law_view(checked, cases, "q_mass", k, drawable=drawable),
        "exposure_remaining": remaining,
        "batch_drawable": drawable,
        "exposure_shortage": max(0, k - remaining),
        "claims": {"power_demonstrated": False, "scientifically_qualified": False},
    }


def seal_bank(body):
    """Producer helper for creating an integrity-bound bank input."""
    return {**body, "seal_digest": _digest(body)}


def register_law(body):
    """Producer helper; registration itself does not qualify a law."""
    return {**body, "registration_digest": _digest(body)}
